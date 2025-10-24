# -*- coding: utf-8 -*-
import streamlit as st, pandas as pd, numpy as np, altair as alt
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

avg_score = float(valid["trend_score"].mean())*100
avg_vol = float((valid["ATR14"]/valid["Close"]).mean()*100)
st.subheader("Résumé IA du marché")
st.markdown(f"- **Score moyen** : {avg_score:+.2f}%  \n- **Volatilité moyenne (ATR/Close)** : {avg_vol:.2f}%")

tmp=valid.copy(); tmp["vol"]=tmp["ATR14"]/tmp["Close"]
risky = tmp.sort_values(["trend_score","vol"], ascending=[False, False]).head(10)
risky = risky[risky["vol"]>tmp["vol"].median()].head(3)
safe = tmp[tmp["trend_score"]>0].sort_values(["vol","trend_score"], ascending=[True, False]).head(3)

def build_table(df):
    rows=[]
    for _,r in df.iterrows():
        name = r.get("name") or company_name_from_ticker(r.get("Ticker","")) or r.get("Ticker","")
        tick = r.get("Ticker","")
        levels = price_levels_from_row(r, profil); entry, target, stop = levels["entry"], levels["target"], levels["stop"]
        dec = decision_label_from_row(r, held=False, vol_max=volmax)
        txt,score,_ = news_summary(name, tick)
        rows.append({"Nom":name,"Ticker":tick,"Indice":r.get("Indice",""),
                     "Écart MA20 %":round((r.get("gap20",np.nan) or np.nan)*100,2),
                     "Écart MA50 %":round((r.get("gap50",np.nan) or np.nan)*100,2),
                     "Vol%":round(float(r["ATR14"]/r["Close"]*100),2) if r["Close"] else np.nan,
                     "Entrée (€)":entry,"Objectif (€)":target,"Stop (€)":stop,
                     "Décision IA":dec,"Sentiment":round(score,2)})
    return pd.DataFrame(rows)

c1,c2=st.columns(2)
with c1:
    st.subheader("🔥 3 actions à fort potentiel (risque élevé)")
    df_risky = build_table(risky)
    st.dataframe(style_variations(df_risky, ["Écart MA20 %","Écart MA50 %","Vol%","Sentiment"]),
                 use_container_width=True, hide_index=True)
with c2:
    st.subheader("🛡️ 3 actions à risque moindre (trend solide)")
    df_safe = build_table(safe)
    st.dataframe(style_variations(df_safe, ["Écart MA20 %","Écart MA50 %","Vol%","Sentiment"]),
                 use_container_width=True, hide_index=True)
