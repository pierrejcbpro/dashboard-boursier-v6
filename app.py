# -*- coding: utf-8 -*-
import streamlit as st
st.set_page_config(page_title="Dash Boursier v6.3 — Smart Search + Toggles + Dividendes", layout="wide", initial_sidebar_state="expanded")

st.sidebar.header("⚙️ Paramètres")
profil = st.sidebar.radio("🎯 Profil IA", ["Agressif","Neutre","Prudent"], index=1, horizontal=True)
st.sidebar.checkbox("Afficher MA20/MA50/ATR dans tous les tableaux (si dispo)", value=True, key="show_indics")
st.sidebar.checkbox("Activer le module Dividendes (optionnel)", value=False, key="use_dividends")
if st.sidebar.button("🔄 Recharger toute l'app"):
    st.cache_data.clear(); st.rerun()
st.session_state["profil"]=profil

st.title("💹 Dash Boursier — v6.3")
st.markdown("**Nouveautés** : 🔎 recherche par *nom* (autocomplete), 👁️ toggle MA20/MA50/ATR, 💰 dividendes (option).")
