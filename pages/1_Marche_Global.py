
# -*- coding: utf-8 -*-
import streamlit as st, pandas as pd, numpy as np, altair as alt
from lib import fetch_all_markets, news_summary, decision_label_from_row, style_variations, get_profile_params, price_levels_from_row

st.title("🌍 Marché Global — Classement par tendance (MA20/MA50)")

profil = st.session_state.get("profil","Neutre")
volmax = get_profile_params(profil)["vol_max"]

if st.sidebar.button("🔄 Rafraîchir données globales"):
    st.cache_data.clear(); st.rerun()

markets=[("CAC 40",""),("DAX 40",""),("NASDAQ 100",""),("S&P 500",""),("Dow Jones","")]
data = fetch_all_markets(markets, days_hist=120)
if data.empty: st.warning("Aucune donnée disponible."); st.stop()

valid = data.dropna(subset=["trend_score"]).copy()
top = valid.sort_values("trend_score", ascending=False).head(5)
low = valid.sort_values("trend_score", ascending=True).head(5)

def bar(df, title):
    d=df.copy()
    d["Name"]=d.get("name", d.get("Ticker","")).astype(str)
    d["score"]=d["trend_score"]*100
    d["color"]=np.where(d["score"]>=0,"Hausses","Baisses")
    ch=alt.Chart(d).mark_bar().encode(
        x=alt.X("Name:N", sort="-y", title="Société"),
        y=alt.Y("score:Q", title="Score tendance (×100)"),
        color=alt.Color("color:N", scale=alt.Scale(domain=["Hausses","Baisses"], range=["#2bb673","#e55353"]), legend=None),
        tooltip=["Name","Ticker",alt.Tooltip("score",format=".2f")]
    ).properties(title=title, height=300)
    st.altair_chart(ch, use_container_width=True)

c1,c2=st.columns(2)
with c1: bar(top, "Top 5 — tendance haussière")
with c2: bar(low, "Top 5 — tendance baissière")

def table_ai(df):
    rows=[]
    for _,r in df.iterrows():
        name=r.get("name", r.get("Ticker"))
        tick=r.get("Ticker","")
        levels=price_levels_from_row(r, profil)
        txt,score,_=news_summary(str(name), tick)
        dec=decision_label_from_row(r, held=False, vol_max=volmax)
        rows.append({"Nom":name,"Ticker":tick,
                     "Écart MA20 %":round((r.get("gap20",np.nan) or np.nan)*100,2),
                     "Écart MA50 %":round((r.get("gap50",np.nan) or np.nan)*100,2),
                     "Entrée (€)":levels["entry"],"Objectif (€)":levels["target"],"Stop (€)":levels["stop"],
                     "Décision IA":dec,"Sentiment":round(score,2)})
    return pd.DataFrame(rows)

st.subheader("Analyses IA — Top (tendance)")
df_top = table_ai(top)
st.dataframe(style_variations(df_top, ["Écart MA20 %","Écart MA50 %","Sentiment"]), use_container_width=True, hide_index=True)
st.subheader("Analyses IA — Low (tendance)")
df_low = table_ai(low)
st.dataframe(style_variations(df_low, ["Écart MA20 %","Écart MA50 %","Sentiment"]), use_container_width=True, hide_index=True)
