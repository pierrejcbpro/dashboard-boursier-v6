# -*- coding: utf-8 -*-
import streamlit as st, pandas as pd, numpy as np
from lib import (fetch_all_markets, news_summary, decision_label_from_row, style_variations,
                 get_profile_params, price_levels_from_row, load_watchlist_ls, save_watchlist_ls,
                 company_name_from_ticker)

st.title("🏠 Synthèse Flash IA — CAC 40 + LS Exchange (FR/DE)")

profil = st.session_state.get("profil","Neutre")
volmax = get_profile_params(profil)["vol_max"]

st.sidebar.markdown("### 🔁 Watchlist LS Exchange (FR/DE)")
wl_text = st.sidebar.text_area("Tickers LS (ex: AIR, ORA, MC, TOTB, VOW3)",
                               value=",".join(load_watchlist_ls()), height=80)
if st.sidebar.button("💾 Enregistrer watchlist"):
    new_list=[x.strip().upper() for x in wl_text.replace("\n",",").replace(";",",").split(",") if x.strip()]
    save_watchlist_ls(new_list); st.success("Watchlist LS enregistrée."); st.rerun()

markets=[("CAC 40","wiki"),("LS Exchange","ls")]
data = fetch_all_markets(markets, days_hist=120)
if data.empty:
    st.warning("Aucune donnée disponible."); st.stop()

valid = data.dropna(subset=["trend_score","Close","ATR14"]).copy()
valid["Cours"] = valid["Close"].round(2)

# Classements
top10 = valid.sort_values("trend_score", ascending=False).head(10)
low10 = valid.sort_values("trend_score", ascending=True).head(10)

def build_table(df):
    rows=[]
    for _,r in df.iterrows():
        name = r.get("name") or company_name_from_ticker(r.get("Ticker","")) or r.get("Ticker","")
        tick = r.get("Ticker","")
        levels = price_levels_from_row(r, profil); entry, target, stop = levels["entry"], levels["target"], levels["stop"]
        dec = decision_label_from_row(r, held=False, vol_max=volmax)
        txt,score,_ = news_summary(name, tick)
        rows.append({"Nom":name,"Ticker":tick,"Indice":r.get("Indice",""),
                     "Cours": round(float(r.get("Close", np.nan)),2) if pd.notna(r.get("Close", np.nan)) else None,
                     "Écart MA20 %":round((r.get("gap20",np.nan) or np.nan)*100,2),
                     "Écart MA50 %":round((r.get("gap50",np.nan) or np.nan)*100,2),
                     "Entrée (€)":entry,"Objectif (€)":target,"Stop (€)":stop,
                     "Décision IA":dec,"Sentiment":round(score,2)})
    return pd.DataFrame(rows)

st.subheader("🏆 Top 10 — Tendance haussière")
df_up = build_table(top10)
st.dataframe(style_variations(df_up, ["Écart MA20 %","Écart MA50 %","Sentiment"]), use_container_width=True, hide_index=True)

st.subheader("📉 Top 10 — Tendance baissière")
df_dn = build_table(low10)
st.dataframe(style_variations(df_dn, ["Écart MA20 %","Écart MA50 %","Sentiment"]), use_container_width=True, hide_index=True)
