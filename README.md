# 🤖 AI_AGENTS

AI_AGENTS est un projet Python qui met en œuvre un agent conversationnel intelligent reposant sur les modèles de langage Mistral via leur API. Le projet offre une base simple et flexible pour intégrer l'IA générative dans des applications personnalisées.

---

## 🚀 Fonctionnalités

- 🔐 Authentification via clé API Mistral
- 📡 Requêtes HTTP à l'API `mistral.ai`
- ⚙️ Configuration facile via un fichier `.env`
- 💬 Interaction dynamique avec le modèle `mistral-medium`
- ✅ Installation guidée via Anaconda

---

## 📁 Structure du projet

---

## 🛠️ Prérequis

- [Python 3.10+](https://www.python.org/)
- [Anaconda](https://www.anaconda.com/) (recommandé)
- Une clé API valide depuis [Mistral AI](https://console.mistral.ai/)

---

## ⚙️ Installation

### 1. Cloner le dépôt

```bash
git clone https://github.com/ala2020-cyber/AI_AGENTS_fINANCIAL_ANALYSIS.git
cd AI_AGENTS
```

### 2. Créer un environnement virtuel avec Anaconda

```bash
conda create -n ai_agents_env python=3.10
conda activate ai_agents_env
```

### 3. Installer les dépendances

```bash
pip install -r requirements.txt
```

### 🔐 Configuration API

## Créer un fichier .env à la racine du projet :

```bash
MISTRAL_API_KEY=your_mistral_api_key
MISTRAL_MODEL=mistral-medium
```
