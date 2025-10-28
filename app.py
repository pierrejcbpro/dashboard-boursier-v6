
# -*- coding: utf-8 -*-
import streamlit as st
from lib import load_profile, save_profile

st.set_page_config(page_title="Dash Boursier v6.4 — Portefeuille multi‑appareils + Top10/10 + Mémoire", layout="wide", initial_sidebar_state="expanded")

# ---- Sidebar (profil persistant) ----
current = load_profile()
if "profil" not in st.session_state:
    st.session_state["profil"] = current

st.sidebar.header("⚙️ Paramètres")
choice = st.sidebar.radio("🎯 Profil IA", ["Agressif","Neutre","Prudent"],
                          index={"Agressif":0,"Neutre":1,"Prudent":2}[st.session_state["profil"]], horizontal=True)
if choice != st.session_state["profil"]:
    st.session_state["profil"] = choice
    save_profile(choice)

st.sidebar.caption("⚠️ Données différées ~15 min (Yahoo Finance).")
if st.sidebar.button("🔄 Recharger l'app"):
    st.cache_data.clear(); st.rerun()

st.title("💹 Dash Boursier — v6.4")
st.markdown("- **Profil IA** mémorisé entre sessions.
- **Portefeuille** : export/import JSON, graph **%** et **€**.
- **Synthèse Flash** : **Top 10 hausses** + **Top 10 baisses** (vertical) + **Cours**.
- **Détail Indice** : **Cours** ajouté.
- **Recherche** : mémorise **la dernière action** consultée.")
