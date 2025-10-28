# -*- coding: utf-8 -*-
"""
💹 Dash Boursier — Version 7.0
Page d’accueil principale (Synthèse, Profil IA, Navigation)
"""

import streamlit as st
from lib import get_profile_params, load_profile, save_profile

# ---------------------------------------------------------
# 🧠 CONFIGURATION GÉNÉRALE
# ---------------------------------------------------------
st.set_page_config(
    page_title="Dash Boursier v7.0",
    page_icon="💹",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ---------------------------------------------------------
# 🎛️ PROFIL IA — MÉMORISATION ET MISE À JOUR
# ---------------------------------------------------------
st.sidebar.title("🧭 Paramètres IA")

profil_actuel = load_profile()
profil = st.sidebar.radio(
    "Sélectionne ton profil d’investisseur :",
    ["Prudent", "Neutre", "Agressif"],
    index=["Prudent", "Neutre", "Agressif"].index(profil_actuel)
)

if profil != profil_actuel:
    save_profile(profil)
    st.session_state["profil"] = profil
    st.toast(f"Profil IA mis à jour → {profil}", icon="🤖")

params = get_profile_params(profil)

# ---------------------------------------------------------
# 🏠 PAGE D’ACCUEIL / SYNTHÈSE
# ---------------------------------------------------------
st.title("💹 Dash Boursier — v7.0")
st.caption("🧠 Piloté par IA — Analyse multi-marchés, portefeuille dynamique et veille intelligente.")

st.markdown("""
### 📘 Nouveautés de la version 7.0
- ⚡ **Synthèse Flash IA** : multi-marchés (🇫🇷 CAC40, 🇩🇪 DAX, 🇺🇸 NASDAQ, LS Exchange), Top/Flop + sélection IA TOP 10  
- 💼 **Portefeuille IA** : calculs en € et %, surbrillance des zones d’achat (🟢⚠️🔴), répartition et benchmark  
- 🔍 **Recherche universelle** : analyse MA20/MA50/ATR, IA complète, actualités datées, ajout direct au portefeuille  
- 📊 **Synthèse globale IA** : détection automatique du momentum de marché (🟢 proche achat / ⚠️ neutre / 🔴 éloigné)  
- 🧠 **Profil IA mémorisé** entre sessions (Prudent / Neutre / Agressif)
- 🌙 Interface homogène, lisible jour/nuit
""")

st.divider()

# ---------------------------------------------------------
# ⚙️ PARAMÈTRES ACTUELS DU PROFIL
# ---------------------------------------------------------
st.subheader("⚙️ Paramètres IA actifs")

col1, col2, col3 = st.columns(3)
with col1:
    st.metric("Profil", profil)
with col2:
    st.metric("Volatilité max", f"{params['vol_max']*100:.1f}%")
with col3:
    st.metric("Horizon", params.get("horizon", "6–12 mois"))

st.info(
    f"🤖 **Mode IA : {profil}** — "
    f"Analyse automatique adaptée à ton profil de risque (volatilité max {params['vol_max']*100:.1f}%)."
)

st.divider()

# ---------------------------------------------------------
# 🚀 NAVIGATION RAPIDE
# ---------------------------------------------------------
st.markdown("""
### 🗺️ Navigation rapide

- ⚡ **Synthèse Flash IA**  
  Vue globale **multi-marchés** avec Top/Flop, sélection IA TOP 10 et actualités.

- 💼 **Mon Portefeuille IA**  
  Suivi interactif PEA/CTO, graphiques %, €, **benchmark** contre indices, et **répartition visuelle**.

- 🔍 **Recherche universelle**  
  Analyse complète d’une action : indicateurs techniques, **Synthèse IA**, actualités datées, ajout direct au portefeuille.

- 📈 **(Bientôt)** Détail par Indice  
  Vue IA dédiée pour CAC40, DAX, NASDAQ et S&P500 (TOP5 IA + leaders sectoriels).
""")

st.divider()
st.success("✅ Application prête — choisis une page dans le menu à gauche pour démarrer ton analyse IA.")
