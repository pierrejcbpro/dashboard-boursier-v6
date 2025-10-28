# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd, numpy as np
from lib import (
    members, fetch_prices, compute_metrics, news_summary,
    decision_label_from_row, style_variations, get_profile_params,
    price_levels_from_row, load_watchlist_ls, company_name_from_ticker
)

st.set_page_config(page_title="Détail par Indice", page_icon="📊", layout="wide")
st.title("📊 Détail par Indice — CAC 40 / LS Exchange")

profil = st.session_state.get("profil", "Neutre")
params = get_profile_params(profil)
volmax = params["vol_max"]

univers = st.selectbox("Choisir un indice :", ["CAC 40","LS Exchange"], index=0)

if univers == "CAC 40":
    mem = members("CAC 40")
else:
    wl = load_watchlist_ls()
    mem = pd.DataFrame({"ticker": wl, "name": wl})

if mem.empty:
    st.warning("Aucune action trouvée."); st.stop()

px = fetch_prices(mem["ticker"].tolist(), days=120)
met = compute_metrics(px).merge(mem, left_on="Ticker", right_on="ticker", how="left")

top5 = met.sort_values("trend_score", ascending=False).head(5)
low5 = met.sort_values("trend_score", ascending=True).head(5)

def enrich(df):
    rows=[]
    for _,r in df.iterrows():
        name = r.get("name") or company_name_from_ticker(r.get("Ticker",""))
        tick = r.get("Ticker","")
        levels = price_levels_from_row(r, profil)
        txt,sc,_ = news_summary(name, tick)
        dec = decision_label_from_row(r, False, vol_max=volmax)
        rows.append({
            "Nom": name, "Ticker": tick, "Cours (€)": round(float(r.get("Close",np.nan)),2),
            "Écart MA20 %": round((r.get("gap20",0) or 0)*100,2),
            "Écart MA50 %": round((r.get("gap50",0) or 0)*100,2),
            "Entrée (€)": levels["entry"], "Objectif (€)": levels["target"], "Stop (€)": levels["stop"],
            "Décision IA": dec, "Sentiment": round(sc,2)
        })
    return pd.DataFrame(rows)

st.subheader("Top 5 haussières")
st.dataframe(style_variations(enrich(top5), ["Écart MA20 %","Écart MA50 %","Sentiment"]), use_container_width=True)

st.subheader("Top 5 baissières")
st.dataframe(style_variations(enrich(low5), ["Écart MA20 %","Écart MA50 %","Sentiment"]), use_container_width=True)
