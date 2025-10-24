
# -*- coding: utf-8 -*-
import streamlit as st
st.set_page_config(page_title="Dash Boursier v6.2 — Smart Search", layout="wide", initial_sidebar_state="expanded")

st.sidebar.header("⚙️ Paramètres")
profil = st.sidebar.radio("🎯 Profil IA", ["Agressif","Neutre","Prudent"], index=1, horizontal=True)
if st.sidebar.button("🔄 Recharger toute l'app"):
    st.cache_data.clear(); st.rerun()
st.session_state["profil"]=profil

st.title("💹 Dash Boursier — v6.2 (Smart Search par nom + IA)")
st.markdown("Accueil → **Synthèse Flash**. Utilise les pages pour Indices, Portefeuille et Recherche universelle.")
