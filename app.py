
# -*- coding: utf-8 -*-
import streamlit as st
st.set_page_config(page_title="Dash Boursier v6", layout="wide", initial_sidebar_state="expanded")

st.markdown('''
<style>
:root { --bg:#0f1218; --panel:#1a1f29; --text:#e6e9ef; --muted:#9aa4b2; --pos:#2bb673; --neg:#e55353; --warn:#e6a100; }
.block-container {padding-top: 1rem;}
html, body, [data-testid="stAppViewContainer"] {background: var(--bg); color: var(--text);}
h1, h2, h3 {color: var(--text);}
div[data-testid="stMarkdownContainer"] p {color: var(--muted);}
hr {border: 1px solid #283042;}
</style>
''', unsafe_allow_html=True)

st.sidebar.header("⚙️ Paramètres")
profil = st.sidebar.radio("🎯 Profil IA", ["Agressif","Neutre","Prudent"], index=1, horizontal=True)
if st.sidebar.button("🔄 Recharger toute l'app"):
    st.cache_data.clear(); st.rerun()
st.session_state["profil"]=profil

st.title("💹 Dash Boursier — v6 (MA20/MA50 partout)")
st.markdown("Cette version simplifie l'analyse en se concentrant sur **MA20/MA50 + ATR** et des **décisions IA** cohérentes. "
            "Les variations 1j/7j/30j sont retirées des pages globales pour plus de lisibilité. "
            "La page **Recherche universelle** offre des horizons interactifs (jour, 7j, 30j, 1an, 5ans).")
