# -*- coding: utf-8 -*-
import streamlit as st, pandas as pd, altair as alt, numpy as np, yfinance as yf
from lib import (resolve_identifier, load_mapping, save_mapping, compute_metrics, news_summary,
                 decision_label_from_row, get_profile_params, price_levels_from_row, company_name_from_ticker,
                 google_news_titles, filter_company_news, find_ticker_by_name, dividends_summary)

st.title("🔎 Recherche Universelle — par Nom / Ticker / ISIN / WKN + MA20/MA50 & Niveaux IA + Actus")

profil = st.session_state.get("profil","Neutre")
volmax = get_profile_params(profil)["vol_max"]
show_div = st.session_state.get("use_dividends", False)

with st.expander("🔍 Rechercher par nom (Yahoo suggestions)", expanded=True):
    q = st.text_input("Nom de l'entreprise (ex: TotalEnergies, Airbus, LVMH)")
    selected_symbol = None
    if st.button("Rechercher"):
        cands = find_ticker_by_name(q)
        if not cands:
            st.warning("Aucune correspondance trouvée.")
        else:
            options = [f"{c['symbol']} — {c['shortname']} ({c['exchDisp']})" for c in cands]
            i = st.selectbox("Résultats :", options, index=0)
            if st.button("✅ Utiliser ce résultat"):
                idx = options.index(i); selected_symbol = cands[idx]["symbol"]
                m = load_mapping(); m[q.upper()] = selected_symbol; save_mapping(m)
                st.success(f"Ajouté au mapping : {q} → {selected_symbol}")

raw = st.text_input("Ou saisis directement un Identifiant (Ticker / ISIN / WKN / alias)", placeholder="Ex: TTE.PA, NVDA, US0378331005, TOTB").strip().upper()

tick = None
if 'selected_symbol' in locals() and selected_symbol:
    tick = selected_symbol
elif raw:
    tick, meta = resolve_identifier(raw)
else:
    st.stop()

if not tick:
    st.warning("Identifiant non reconnu. Essaie la recherche par nom.")
    st.stop()

name = company_name_from_ticker(tick)
st.info(f"Analyse de **{name} ({tick})**")

period = st.sidebar.radio("Période", ["Jour","7 jours","30 jours","1 an","5 ans"], index=2)
period_map = {"Jour":"1d","7 jours":"7d","30 jours":"30d","1 an":"1y","5 ans":"5y"}
yf_period = period_map[period]

try:
    if yf_period=="1d":
        data = yf.download(tick, period="1d", interval="5m", auto_adjust=False, progress=False)
        if data.empty:
            data = yf.download(tick, period="5d", interval="1d", auto_adjust=False, progress=False)
    else:
        data = yf.download(tick, period=yf_period, interval="1d", auto_adjust=False, progress=False)
except Exception as e:
    st.error(f"Impossible de récupérer l'historique: {e}"); st.stop()
if data.empty:
    st.warning("Aucune donnée pour ce ticker."); st.stop()

d = data.reset_index().rename(columns={data.index.name or "index":"Date"})
d["MA20"] = d["Close"].rolling(20, min_periods=5).mean()
d["MA50"] = d["Close"].rolling(50, min_periods=10).mean()

try:
    m = compute_metrics(d.assign(Ticker=tick)[["Date","Open","High","Low","Close","Ticker"]])
    row = m.tail(1).iloc[0] if not m.empty else pd.Series({"Close": float(d["Close"].iloc[-1])})
except Exception:
    row = pd.Series({"Close": float(d["Close"].iloc[-1])})
levels = price_levels_from_row(row, profil)
entry, target, stop = levels["entry"], levels["target"], levels["stop"]

base = alt.Chart(d).mark_line().encode(
    x=alt.X("Date:T", title=""),
    y=alt.Y("Close:Q", title="Cours"),
    tooltip=[alt.Tooltip("Date:T"), alt.Tooltip("Close:Q", format=".2f")]
).properties(title=f"{name} ({tick}) — {period}", height=360)
ma20_line = alt.Chart(d).mark_line(color="#4FC3F7").encode(x="Date:T", y="MA20:Q")
ma50_line = alt.Chart(d).mark_line(color="#81D4FA").encode(x="Date:T", y="MA50:Q")
entry_line = alt.Chart(pd.DataFrame({"y":[entry]})).mark_rule(color="#e6a100").encode(y="y:Q")
target_line = alt.Chart(pd.DataFrame({"y":[target]})).mark_rule(color="#2bb673").encode(y="y:Q")
stop_line = alt.Chart(pd.DataFrame({"y":[stop]})).mark_rule(color="#e55353").encode(y="y:Q")
st.altair_chart(base + ma20_line + ma50_line + entry_line + target_line + stop_line, use_container_width=True)

st.markdown(f"**Seuils IA ({profil})** — 📈 Entrée: **{entry}** · 🎯 Objectif: **{target}** · 🛑 Stop: **{stop}**")

items = filter_company_news(tick, name, google_news_titles(f"{name} {tick}", "fr"))
st.subheader("📰 Articles liés à l'entreprise")
if items:
    for t,u in items[:8]:
        st.markdown(f"- [{t}]({u})")
else:
    st.caption("Aucune actualité spécifique trouvée.")

txt,score,_ = news_summary(name, tick)
dec = decision_label_from_row(row, held=False, vol_max=get_profile_params(profil)["vol_max"])
st.subheader("🧠 Analyse IA")
st.write(f"**Décision** : {dec} — Sentiment: {score:+.2f}")
st.write(f"Actu: {txt}")

if show_div:
    st.subheader("💰 Dividendes (optionnel)")
    recents, trailing = dividends_summary(tick)
    if recents:
        st.markdown("**Derniers dividendes** :")
        st.dataframe(pd.DataFrame(recents, columns=["Date","Montant"]).assign(Monnaie="local"),
                     hide_index=True, use_container_width=True)
    if trailing is not None:
        st.markdown(f"**Rendement (approx.)** : ~{trailing*100:.2f}% (trailing 4 paiements)")
    if not recents and trailing is None:
        st.caption("Aucun dividende trouvé.")
