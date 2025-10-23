
# -*- coding: utf-8 -*-
import streamlit as st, pandas as pd
from lib import members, fetch_prices, compute_metrics, news_summary, decision_label_from_row, style_variations, get_profile_params, price_levels_from_row

st.title("📊 Analyse par Indice — MA20/MA50 & IA")

profil = st.session_state.get("profil","Neutre")
volmax = get_profile_params(profil)["vol_max"]

idx = st.selectbox("Indice", ["CAC 40","DAX 40","NASDAQ 100","S&P 500","Dow Jones"], index=0)
if st.sidebar.button("🔄 Rafraîchir cet indice"):
    st.cache_data.clear(); st.rerun()

mem = members(idx)
if mem.empty: st.warning("Constituants introuvables."); st.stop()

px = fetch_prices(mem["ticker"].tolist(), days=150)
met = compute_metrics(px).merge(mem, left_on="Ticker", right_on="ticker", how="left")
if met.empty: st.warning("Prix indisponibles."); st.stop()

top5 = met.sort_values("trend_score", ascending=False).head(5)
low5 = met.sort_values("trend_score", ascending=True).head(5)

def enrich_table(df):
    rows=[]
    for _,r in df.iterrows():
        name=r.get("name", r.get("Ticker"))
        tick=r.get("Ticker","")
        levels=price_levels_from_row(r, profil)
        txt,score,_=news_summary(str(name), tick)
        dec=decision_label_from_row(r, held=False, vol_max=volmax)
        rows.append({"Nom":name,"Ticker":tick,
                     "Écart MA20 %":round((r.get("gap20",0) or 0)*100,2),
                     "Écart MA50 %":round((r.get("gap50",0) or 0)*100,2),
                     "Entrée (€)":levels["entry"],"Objectif (€)":levels["target"],"Stop (€)":levels["stop"],
                     "Décision IA":dec,"Sentiment":round(score,2)})
    return pd.DataFrame(rows)

st.subheader("Top 5 tendance haussière")
st.dataframe(style_variations(enrich_table(top5), ["Écart MA20 %","Écart MA50 %","Sentiment"]), use_container_width=True, hide_index=True)
st.subheader("Top 5 tendance baissière")
st.dataframe(style_variations(enrich_table(low5), ["Écart MA20 %","Écart MA50 %","Sentiment"]), use_container_width=True, hide_index=True)
