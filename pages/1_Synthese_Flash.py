# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd, numpy as np
from lib import (
    fetch_all_markets, news_summary, decision_label_from_row,
    style_variations, get_profile_params, price_levels_from_row,
    load_watchlist_ls, save_watchlist_ls, company_name_from_ticker
)

st.set_page_config(page_title="Synthèse Flash IA", page_icon="🌍", layout="wide")
st.title("🌍 Synthèse Flash IA — CAC 40 + LS Exchange (FR/DE)")

# --- PROFIL IA
profil = st.session_state.get("profil", "Neutre")
params = get_profile_params(profil)
volmax = params["vol_max"]

# --- WATCHLIST LS Exchange
st.sidebar.subheader("🎛️ Watchlist LS Exchange")
wl_text = st.sidebar.text_area(
    "Tickers LS (ex: AIR, ORA, MC, TOTB, VOW3)", 
    value=",".join(load_watchlist_ls()), height=80
)
if st.sidebar.button("💾 Enregistrer"):
    new = [t.strip().upper() for t in wl_text.replace("\n", ",").replace(";", ",").split(",") if t.strip()]
    save_watchlist_ls(new)
    st.success("✅ Watchlist LS sauvegardée."); st.rerun()

# --- FETCH
markets = [("CAC 40","wiki"),("LS Exchange","ls")]
data = fetch_all_markets(markets, days_hist=150)
if data.empty: st.warning("Aucune donnée disponible."); st.stop()
data = data.dropna(subset=["trend_score", "Close"])

def build_table(df):
    rows=[]
    for _,r in df.iterrows():
        name = r.get("name") or company_name_from_ticker(r.get("Ticker",""))
        tick = r.get("Ticker","")
        levels = price_levels_from_row(r, profil)
        entry, target, stop = levels["entry"], levels["target"], levels["stop"]
        dec = decision_label_from_row(r, False, vol_max=volmax)
        txt, sc, _ = news_summary(name, tick)
        rows.append({
            "Nom": name, "Ticker": tick, "Indice": r.get("Indice",""),
            "Cours (€)": round(float(r.get("Close",np.nan)),2),
            "Écart MA20 %": round((r.get("gap20",0) or 0)*100,2),
            "Écart MA50 %": round((r.get("gap50",0) or 0)*100,2),
            "Entrée (€)": entry, "Objectif (€)": target, "Stop (€)": stop,
            "Décision IA": dec, "Sentiment": round(sc,2)
        })
    return pd.DataFrame(rows)

st.subheader("🏆 Top 10 hausses")
df_up = build_table(data.sort_values("trend_score", ascending=False).head(10))
st.dataframe(style_variations(df_up, ["Écart MA20 %","Écart MA50 %","Sentiment"]), use_container_width=True)

st.subheader("📉 Top 10 baisses")
df_dn = build_table(data.sort_values("trend_score", ascending=True).head(10))
st.dataframe(style_variations(df_dn, ["Écart MA20 %","Écart MA50 %","Sentiment"]), use_container_width=True)
