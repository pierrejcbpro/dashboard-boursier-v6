# -*- coding: utf-8 -*-
import streamlit as st, pandas as pd, numpy as np
from lib import (
    fetch_prices, compute_metrics, price_levels_from_row,
    decision_label_from_row, style_variations, company_name_from_ticker
)

st.set_page_config(page_title="Mon Portefeuille", page_icon="💼", layout="wide")
st.title("💼 Mon Portefeuille — Suivi Global, PEA & CTO")

if "portefeuille" not in st.session_state:
    st.session_state["portefeuille"] = pd.DataFrame(columns=["Ticker","Type","Quantité","Prix Achat (€)"])

port = st.session_state["portefeuille"]

st.subheader("Ajouter une ligne")
with st.form("ajout_ligne"):
    c1, c2, c3, c4 = st.columns(4)
    with c1: ticker = st.text_input("Ticker / ISIN / WKN").upper().strip()
    with c2: typ = st.selectbox("Type", ["PEA","CTO"])
    with c3: qty = st.number_input("Quantité", 1.0, 1e6, 10.0)
    with c4: prix = st.number_input("Prix Achat (€)", 0.0, 1e6, 100.0)
    ok = st.form_submit_button("➕ Ajouter")
    if ok and ticker:
        st.session_state["portefeuille"] = pd.concat([
            port,
            pd.DataFrame([[ticker,typ,qty,prix]], columns=port.columns)
        ], ignore_index=True)
        st.success(f"{ticker} ajouté."); st.rerun()

if port.empty:
    st.warning("Aucune position enregistrée."); st.stop()

st.subheader("📊 Positions actuelles")
px = fetch_prices(port["Ticker"].tolist(), days=60)
met = compute_metrics(px)
met = met.merge(port, on="Ticker", how="left")

def enrich_table(df):
    rows=[]
    for _,r in df.iterrows():
        name = company_name_from_ticker(r.get("Ticker",""))
        levels = price_levels_from_row(r, st.session_state.get("profil","Neutre"))
        dec = decision_label_from_row(r, True)
        rows.append({
            "Nom": name, "Ticker": r["Ticker"], "Type": r["Type"],
            "Cours (€)": round(r["Close"],2), "Quantité": r["Quantité"],
            "Valeur (€)": round(r["Quantité"]*r["Close"],2),
            "Achat (€)": round(r["Prix Achat (€)"],2),
            "P&L (€)": round(r["Quantité"]*(r["Close"]-r["Prix Achat (€)"]),2),
            "Entrée (€)": levels["entry"], "Objectif (€)": levels["target"], "Stop (€)": levels["stop"],
            "Décision IA": dec
        })
    return pd.DataFrame(rows)

st.dataframe(style_variations(enrich_table(met), ["P&L (€)"]), use_container_width=True)
