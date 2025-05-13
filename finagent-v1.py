import os
import gradio as gr
import yfinance as yf
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mpdates
import yaml
from datetime import datetime
from mplfinance.original_flavor import candlestick_ohlc
from mistralai import Mistral
import re
from dotenv import load_dotenv, find_dotenv

# Load Mistral config
# Charger les variables d'environnement
load_dotenv(find_dotenv())

# Lire la clé API
api_key = os.getenv("MISTRAL_API_KEY")
model_name = os.getenv("MISTRAL_MODEL")

# Vérification
if not api_key:
    raise EnvironmentError("Le fichier .env doit contenir MISTRAL_API_KEY")

# Client Mistral
client = Mistral(api_key=api_key)

class TickerExtractor:
    def __init__(self, client): self.client=client
    def extract(self,text):
        for pat in [r'\$([A-Z]{1,5})\b',r'\b([A-Z]{1,5})(?=\s+stock)',r'\b([A-Z]{1,5})\b']:
            for sym in re.findall(pat,text.upper()):
                try:
                    if yf.Ticker(sym).history(period="1d").empty: continue
                    return sym
                except: continue
        # AI fallback
        msgs=[{"role":"system","content":"Extract a stock ticker."},
              {"role":"user","content":text}]
        resp= self.client.chat.complete(model=model_name,messages=msgs)
        sym=resp.choices[0].message.content.strip().upper()
        try:
            return sym if not yf.Ticker(sym).history(period="1d").empty else None
        except:
            return None

class FinancialAgent:
    def __init__(self,client): self.client=client; self.extractor=TickerExtractor(client)
    def analyze(self,ticker,message,period):
        sym = ticker.strip().upper() or self.extractor.extract(message)
        if not sym: return None,"Pas de ticker valide détecté"
        df = yf.Ticker(sym).history(period=period)
        if df.empty: return None,f"Aucune donnée pour {sym}"
        df['SMA20']=df['Close'].rolling(20).mean()
        df['SMA50']=df['Close'].rolling(50).mean()
        df['RSI'] = self.rsi(df['Close'])
        df['MACD'],df['Signal']=self.macd(df['Close'])
        # AI prompt
        prompt=(f"Analyse technique {sym}: Clôture {df['Close'].iloc[-1]:.2f}, RSI {df['RSI'].iloc[-1]:.2f}, "
                f"MACD {df['MACD'].iloc[-1]:.2f}/{df['Signal'].iloc[-1]:.2f}")
        msgs=[{"role":"system","content":"You are expert."},
              {"role":"user","content":prompt}]
        resp=self.client.chat.complete(model=model_name,messages=msgs)
        return df,resp.choices[0].message.content
    def rsi(self,p,period=14):
        d=p.diff();u=d.clip(lower=0).rolling(period).mean();d2=-d.clip(upper=0).rolling(period).mean()
        return 100-100/(1+u/d2)
    def macd(self,p,fast=12,slow=26,signal=9):
        e1=p.ewm(span=fast).mean();e2=p.ewm(span=slow).mean();m=e1-e2; sig=m.ewm(span=signal).mean(); return m,sig

class Plotter:
    @staticmethod
    def price(df,sym):
        df2=df.copy();df2.index=pd.to_datetime(df2.index); df2['D']=mpdates.date2num(df2.index)
        fig,ax=plt.subplots(figsize=(10,4))
        candlestick_ohlc(ax,df2[['D','Open','High','Low','Close']].values,width=0.6)
        ax.plot(df2['D'],df2['SMA20'],label='SMA20')
        ax.plot(df2['D'],df2['SMA50'],label='SMA50')
        ax.legend()
        ax.set_title(f'Graphique de {sym}')
        return fig
    @staticmethod
    def tech(df):
        fig,(a1,a2)=plt.subplots(2,1,figsize=(10,5))
        a1.plot(df.index,df['RSI']);a1.axhline(70,color='r');a1.axhline(30,color='g');a1.set_title('RSI')
        a2.plot(df.index,df['MACD'],label='MACD');a2.plot(df.index,df['Signal'],label='Signal');a2.legend();a2.set_title('MACD')
        return fig

# Ticker dropdown options
default_tickers = ["AAPL", "GOOG", "MSFT", "TSLA", "META", "AMZN", "NVDA", "NFLX", "BRK-B", "JNJ"]

agent=FinancialAgent(client)
plotter=Plotter()

def process(message, ticker, period, history):
    if history is None:
        history = []
    df, analysis = agent.analyze(ticker, message, period)
    history.append({"role": "user", "content": message})
    history.append({"role": "assistant", "content": analysis if analysis else "Pas d'analyse disponible."})
    if df is None:
        return history, None, None
    return history, plotter.price(df, ticker or df), plotter.tech(df)


with gr.Blocks() as demo:
    gr.Markdown("## 📊 Assistant Financier avec IA + Analyse Technique")
    ticker_in = gr.Dropdown(label='Sélection rapide de ticker', choices=default_tickers, value=None, interactive=True)
    ticker_text = gr.Textbox(label='Ou entrez un ticker manuellement (ex: AAPL)', placeholder="Optionnel si rempli ci-dessus")
    period_in = gr.Dropdown(['1d','1mo','3mo','6mo','1y','2y','5y'],value='1y', label='Période')
    msg_in = gr.Textbox(label='Requête naturelle (ex: Analyse de Tesla)', placeholder="Tapez une requête libre...")
    bot = gr.Chatbot(label="Chat", type='messages')
    price_plot = gr.Plot(label='📈 Graphique de prix')
    tech_plot = gr.Plot(label='📉 Indicateurs techniques')
    submit = gr.Button('Lancer l\'analyse')

    submit.click(
        fn=lambda msg, drop, text, period, hist: process(msg, text or drop, period, hist),
        inputs=[msg_in, ticker_in, ticker_text, period_in, bot],
        outputs=[bot, price_plot, tech_plot]
    )

demo.launch()
