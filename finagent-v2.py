import os
import gradio as gr
import yfinance as yf
import requests
import re
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mpdates
import mplfinance as mpf
from dotenv import load_dotenv
from mistralai import Mistral

# Chargement des variables .env
load_dotenv()
api_key = os.getenv("MISTRAL_API_KEY")
model_name = os.getenv("MISTRAL_MODEL")
if not api_key:
    raise EnvironmentError("Le fichier .env doit contenir MISTRAL_API_KEY")

client = Mistral(api_key=api_key)
token_store = {"token": None}


# Extraction du ticker depuis un texte
class TickerExtractor:
    def __init__(self, client):
        self.client = client

    def extract(self, text):
        for pat in [r'\$([A-Z]{1,5})\b', r'\b([A-Z]{1,5})(?=\s+stock)', r'\b([A-Z]{1,5})\b']:
            for sym in re.findall(pat, text.upper()):
                try:
                    if yf.Ticker(sym).history(period="1d").empty:
                        continue
                    return sym
                except:
                    continue
        msgs = [{"role": "system", "content": "Extract a stock ticker."},
                {"role": "user", "content": text}]
        resp = self.client.chat.complete(model=model_name, messages=msgs)
        sym = resp.choices[0].message.content.strip().upper()
        try:
            return sym if not yf.Ticker(sym).history(period="1d").empty else None
        except:
            return None


# Agent d’analyse financière
class FinancialAgent:
    def __init__(self, client):
        self.client = client
        self.extractor = TickerExtractor(client)

    def analyze(self, ticker, message, period):
        sym = ticker.strip().upper() or self.extractor.extract(message)
        if not sym:
            return None, "Pas de ticker valide détecté", None
        df = yf.Ticker(sym).history(period=period)
        if df.empty:
            return None, f"Aucune donnée pour {sym}", None
        df['SMA20'] = df['Close'].rolling(20).mean()
        df['SMA50'] = df['Close'].rolling(50).mean()
        df['RSI'] = self.rsi(df['Close'])
        df['MACD'], df['Signal'] = self.macd(df['Close'])

        prompt = (f"Analyse technique {sym}: Clôture {df['Close'].iloc[-1]:.2f}, RSI {df['RSI'].iloc[-1]:.2f}, "
                  f"MACD {df['MACD'].iloc[-1]:.2f}/{df['Signal'].iloc[-1]:.2f}")
        msgs = [{"role": "system", "content": "You are expert."},
                {"role": "user", "content": prompt}]
        resp = self.client.chat.complete(model=model_name, messages=msgs)
        return df, resp.choices[0].message.content, sym

    def rsi(self, p, period=14):
        d = p.diff()
        u = d.clip(lower=0).rolling(period).mean()
        d2 = -d.clip(upper=0).rolling(period).mean()
        return 100 - 100 / (1 + u / d2)

    def macd(self, p, fast=12, slow=26, signal=9):
        e1 = p.ewm(span=fast).mean()
        e2 = p.ewm(span=slow).mean()
        m = e1 - e2
        sig = m.ewm(span=signal).mean()
        return m, sig


# Dessins
class Plotter:
    @staticmethod
    def tech(df):
        fig, (a1, a2) = plt.subplots(2, 1, figsize=(10, 5))
        a1.plot(df.index, df['RSI'])
        a1.axhline(70, color='r')
        a1.axhline(30, color='g')
        a1.set_title('RSI')
        a2.plot(df.index, df['MACD'], label='MACD')
        a2.plot(df.index, df['Signal'], label='Signal')
        a2.legend()
        a2.set_title('MACD')
        return fig
    @staticmethod
    def candlestick_chart(df):
        df_candle = df[['Open', 'High', 'Low', 'Close']].copy()
        df_candle.index.name = 'Date'
        return mpf.plot(df_candle, type='candle', style='charles', volume=False, returnfig=True)


agent = FinancialAgent(client)
plotter = Plotter()

# Auth handlers
def login_user(username, password):
    try:
        resp = requests.post("http://localhost:8000/login", data={"username": username, "password": password})
        if resp.status_code == 200:
            token_store["token"] = resp.json()["access_token"]
            return (
                "<div class='alert-success'>🔓 Connecté avec succès !</div>",
                gr.update(visible=False),
                gr.update(visible=False),
                gr.update(visible=True),
                gr.update(visible=True)
                
            )
        return (
            "<div class='alert-error'>🚫 Identifiants invalides. Veuillez réessayer.</div>",
            gr.update(visible=True),
            gr.update(visible=True),
            gr.update(visible=False),
            gr.update(visible=False)
        )
    except Exception as e:
        return (
            f"<div class='alert-error'>❌ Erreur interne : {str(e)}</div>",
            gr.update(visible=True),
            gr.update(visible=True),
            gr.update(visible=False),
            gr.update(visible=False)
        )

def register_user(username, password):
    try:
        resp = requests.post("http://localhost:8000/register", json={"username": username, "password": password})

        if resp.status_code == 200:
            return "<div class='alert-success'>✅ Utilisateur créé avec succès.</div>"

        detail = resp.json().get("detail", "")

        if "existe déjà" in detail.lower():
            return "<div class='alert-error'>🚫 Ce compte existe déjà. Veuillez choisir un autre nom.</div>"

        if "mot de passe" in detail.lower() and "faible" in detail.lower():
            return (
                "<div class='alert-error'>🔐 Mot de passe trop faible. "
                "Utilisez au moins 8 caractères, une majuscule, une minuscule, un chiffre et un caractère spécial.</div>"
            )

        return f"<div class='alert-error'>❌ Erreur: {detail}</div>"

    except Exception as e:
        return f"<div class='alert-error'>❌ Erreur interne: {str(e)}</div>"

def logout_user():
    token_store["token"] = None
    return (
        "<div class='alert-success'>🔒 Déconnecté avec succès.</div>",
        gr.update(visible=True),
        gr.update(visible=True),
        gr.update(visible=False),
        gr.update(visible=False)
    )
 
def run_analysis(ticker, message, period):
    df, result, sym = agent.analyze(ticker, message, period)
    if df is None:
        return result, None

    # Création du plot du signal (si la colonne existe)
    if 'Buy_Signal' in df.columns:
        signal_plot = mpf.make_addplot(df['Buy_Signal'], type='scatter', markersize=100, marker='^', color='g')
        candlestick_fig = plotter.candlestick_chart(df, extra_plots=[signal_plot])[0]
    else:
        candlestick_fig = plotter.candlestick_chart(df)[0]

    return result, candlestick_fig, plotter.tech(df)


# Interface Gradio
with gr.Blocks(css="""
    #navbar {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 0.7rem 1.2rem;
        background-color: #1f2937; /* Bleu foncé */
        color: white;
        border-bottom: 2px solid #e5e7eb;
    }

    .navbar-title {
        font-size: 1.3rem;
        font-weight: bold;
        color: white;
        margin: 0;
    }

    .logout-btn {
        background-color: transparent;
        color: #cbd5e1;
        border: 1px solid #cbd5e1;
        padding: 0.4rem 0.8rem;
        border-radius: 6px;
        font-size: 0.85rem;
        transition: all 0.2s ease;
    }

    .logout-btn:hover {
        background-color: #ffffff22;
        color: #ffffff;
        border-color: #ffffff;
    }

    .alert-success {
        background-color: #d1fae5;
        color: #065f46;
        padding: 0.6rem;
        border: 1px solid #10b981;
        border-radius: 6px;
        margin-bottom: 10px;
    }

    .alert-error {
        background-color: #fee2e2;
        color: #991b1b;
        padding: 0.6rem;
        border: 1px solid #ef4444;
        border-radius: 6px;
        margin-bottom: 10px;
    }
               

    .alert-success, .alert-error {
    animation: fadeOut 1s ease-out 3s forwards;
    /* fadeOut démarre après 3s, dure 1s, puis garde le dernier état (forwards) */
    }
               

    @keyframes fadeOut {
        from {
            opacity: 1;
        }
        to {
            opacity: 0;
            visibility: hidden;
        }
    }

    
    .navbar-title {
    font-size: 1.8rem;         /* Taille de police plus grande */
    font-weight: 700;          /* Gras fort pour l'impact visuel */
    color: #ffffff;            /* Couleur blanche pour contraste sur fond foncé */
    margin: 0;
    letter-spacing: 0.5px;     /* Légère espacement des lettres pour lisibilité */
    font-family: 'Segoe UI', sans-serif;  /* Police moderne */
    }
    /* Pour garder la navbar sticky en haut si besoin */
    /* #navbar {
        position: sticky;
        top: 0;
        z-index: 100;
    } */
""") as demo:
    
    # Barre de navigation


    with gr.Column(visible=True) as login_section:
        with gr.Group():
            gr.Markdown("### 🔐 Authentification ")
            user = gr.Textbox(label="Nom d'utilisateur", placeholder="Entrez votre nom")
            pwd = gr.Textbox(label="Mot de passe", type="password", placeholder="Entrez votre mot de passe")

        with gr.Row():
            login_btn = gr.Button("🔑 Se connecter", visible=True)
            register_btn = gr.Button("📝 S'inscrire", visible=True)

    status = gr.Markdown("")

    with gr.Column(visible=False) as secure_section:
        gr.Markdown("📊 Analyse Financière avec Mistral 🎯", elem_classes="navbar-title")
        logout_btn = gr.Button("Se déconnecter", visible=False, elem_classes="logout-btn")


        with gr.Row():
            ticker = gr.Dropdown(["AAPL", "MSFT", "GOOGL", "TSLA", "AMZN"], label="Sélection du Ticker")
            period = gr.Dropdown(["5d", "1mo", "3mo", "6mo", "1y"], value="1mo", label="Période")

        message = gr.Textbox(label="Texte sécurisé", placeholder="Ex: Analyse technique de TSLA pour le mois dernier")
        run_btn = gr.Button("Analyser")

        response_box = gr.Textbox(label="Réponse IA")
        candle_plot = gr.Plot(label='📈 Graphique de prix')
        rsi_macd_plot = gr.Plot(label="📈 Indicateurs techniques (RSI et MACD)")
        

    # Callbacks
    login_btn.click(
        login_user,
        inputs=[user, pwd],
        outputs=[status, login_section, register_btn, logout_btn, secure_section]
    )

    register_btn.click(
        register_user,
        inputs=[user, pwd],
        outputs=[status]
    )

    logout_btn.click(
        logout_user,
        outputs=[status, login_section, register_btn, logout_btn, secure_section]
    )

    run_btn.click(
        run_analysis,
        inputs=[ticker, message, period],
        outputs=[response_box, candle_plot,rsi_macd_plot]
    )

demo.launch()
