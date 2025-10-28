# -*- coding: utf-8 -*-
import streamlit as st
import yfinance as yf
import pandas as pd
import altair as alt
from lib import (
    compute_metrics, price_levels_from_row, decision_label_from_row,
    news_summary, company_name_from_ticker, get_profile_params
)

st.set_page_config(page_title="Recherche Universelle", page_icon="🔍", layout="wide")
st.title("🔍 Recherche Universelle — Analyse complète d’une action")

profil = st.session_state.get("profil","Neutre")
params = get_profile_params(profil)

ticker = st.text_input("🔎 Ticker / ISIN / WKN :", st.session_state.get("dernier_ticker",""))
periode = st.selectbox("Période d’analyse :", ["30 jours","1 an","5 ans"], index=0)

if ticker:
    st.session_state["dernier_ticker"] = ticker
    data = yf.download(ticker, period="5y", interval="1d", progress=False)
    if data.empty:
        st.error("Impossible de récupérer les données.")
    else:
        if periode=="30 jours": d=data.tail(30)
        elif periode=="1 an": d=data.tail(252)
        else: d=data

        d = d.reset_index()
        st.altair_chart(
            alt.Chart(d).mark_line().encode(
                x="Date:T", y="Close:Q",
                tooltip=["Date:T","Close:Q"]
            ).properties(title=f"Évolution {ticker} ({periode})"),
            use_container_width=True
        )

        metrics = compute_metrics(data.assign(Ticker=ticker).reset_index().rename(columns={"index":"Date"}))
        if not metrics.empty:
            r = metrics.iloc[-1]
            levels = price_levels_from_row(r, profil)
            dec = decision_label_from_row(r, False)
            txt, sc, _ = news_summary(company_name_from_ticker(ticker), ticker)
            st.markdown(f"""
            ### 📈 Analyse IA — {company_name_from_ticker(ticker)}
            **Décision IA** : {dec}  
            **Entrée :** {levels['entry']:.2f} €  
            **Objectif :** {levels['target']:.2f} €  
            **Stop :** {levels['stop']:.2f} €  
            **Sentiment** : {txt} *(score {sc:.2f})*
            """)
