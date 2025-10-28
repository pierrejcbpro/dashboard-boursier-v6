# -*- coding: utf-8 -*-
"""
Dash Boursier — Version 6.4
Page d'accueil principale
"""
import streamlit as st
from lib import get_profile_params

# ---------------------------------------------------------
# 🧠 CONFIGURATION DE BASE
# ---------------------------------------------------------
st.set_page_config(
    page_title="Dash Boursier v6.4",
    page_icon="💹",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ---------------------------------------------------------
# 🎛️ PROFIL IA (Prudent / Neutre / Agressif)
# ---------------------------------------------------------
if "profil" not in st.session_state:
    st.session_state["profil"] = "Neutre"

st.sidebar.title("🧭 Paramètres IA")

profil = st.sidebar.radio(
    "Sélectionne ton profil d'investisseur :",
    ["Prudent", "Neutre", "Agressif"],
    index=["Prudent", "Neutre", "Agressif"].index(st.session_state["profil"])
)

if profil != st.session_state["profil"]:
    st.session_state["profil"] = profil
    st.toast(f"Profil IA mis à jour → {profil}", icon="🤖")

params = get_profile_params(profil)

# ---------------------------------------------------------
# 🏠 PAGE D’ACCUEIL / SYNTHÈSE
# ---------------------------------------------------------
st.title("💹 Dash Boursier — v6.4")

st.markdown("""
### 📘 Nouveautés de la version 6.4
- **Profil IA** mémorisé entre sessions.
- **Portefeuille** : export/import JSON, graph **%** et **€**.
- **Synthèse Flash** : **Top 10 hausses** + **Top 10 baisses** (vertical) + **Cours**.
- **Détail Indice** : **Cours** ajouté.
- **Recherche universelle** : mémorise **la dernière action** consultée.
- **Analyse IA** : recommandations enrichies avec zones **Entrée / Cible / Stop**.
- **Thème pro** + interface harmonisée.
""")

st.divider()

# ---------------------------------------------------------
# 🧩 RÉSUMÉ RAPIDE DU PROFIL
# ---------------------------------------------------------
st.subheader("⚙️ Paramètres du profil IA actuel")

col1, col2, col3 = st.columns(3)
with col1:
    st.metric("Profil", profil)
with col2:
    st.metric("Volatilité max", f"{params['vol_max']*100:.1f}%")
with col3:
    st.metric("Horizon", params.get("horizon", "6-12 mois"))

st.info(
    f"🧠 **Mode IA actif : {profil}** — "
    f"analyse automatique selon ton profil de risque et la volatilité max ({params['vol_max']*100:.1f}%)."
)

st.divider()

# ---------------------------------------------------------
# 🔍 NAVIGATION RAPIDE
# ---------------------------------------------------------
st.markdown("""
### 🚀 Navigation rapide
- 🌍 **Synthèse Flash IA** : Vue globale CAC40 + LS Exchange (France & Allemagne)
- 📊 **Détail par indice** : Focus sur CAC40 ou LS Exchange
- 💼 **Mon Portefeuille** : Suivi complet avec PEA/CTO, gains/pertes et sauvegarde
- 🔍 **Recherche universelle** : Analyse complète d’une action (graphique 30j / 1an / 5ans + articles)
""")

st.divider()
st.success("✅ Application prête — sélectionne une page dans le menu à gauche pour commencer.")
