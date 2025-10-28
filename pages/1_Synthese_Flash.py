# -*- coding: utf-8 -*-
import streamlit as st, pandas as pd, numpy as np, altair as alt
from lib import (
    fetch_all_markets, style_variations, load_watchlist_ls, save_watchlist_ls,
    load_profile, save_profile, news_summary, select_top_actions
)

st.set_page_config(page_title="Synthèse Flash", page_icon="⚡", layout="wide")
st.title("⚡ Synthèse Flash — Marché Global")

# ---------------- Sidebar : Période + Profil + Watchlist LS ----------------
periode = st.sidebar.radio("Période d’analyse", ["Jour","7 jours","30 jours"], index=0)
value_col = {"Jour":"pct_1d","7 jours":"pct_7d","30 jours":"pct_30d"}[periode]

profil = st.sidebar.radio("Profil IA", ["Prudent","Neutre","Agressif"], index=["Prudent","Neutre","Agressif"].index(load_profile()))
if st.sidebar.button("💾 Mémoriser le profil"):
    save_profile(profil)
    st.sidebar.success("Profil sauvegardé.")

with st.sidebar.expander("📝 Watchlist LS Exchange (facultatif)"):
    current = load_watchlist_ls()
    wl_txt = st.text_area("Tickers LS séparés par virgules (ex: TOTB, AIR, ORA)", value=",".join(current), height=80)
    if st.button("✅ Enregistrer watchlist"):
        lst = [x.strip().upper() for x in wl_txt.replace("\n", ",").split(",") if x.strip()]
        save_watchlist_ls(lst)
        st.success("Watchlist LS mise à jour. Recharger la page si besoin.")

# ---------------- Données marchés ----------------
MARKETS = [("CAC 40", None), ("LS Exchange", None)]
# On télécharge toujours assez d'historique pour calculer J/7/30 (120 j)
data = fetch_all_markets(MARKETS, days_hist=120)

if data.empty:
    st.warning("Aucune donnée disponible (vérifie la connectivité ou la watchlist LS).")
    st.stop()

# Garantir l'existence des colonnes de variations (lib.compute_metrics les crée déjà)
for c in ["pct_1d","pct_7d","pct_30d"]:
    if c not in data.columns:
        data[c] = np.nan

valid = data.dropna(subset=["Close"]).copy()

# ---------------- Résumé global ----------------
avg = (valid[value_col].dropna().mean() * 100.0) if not valid.empty else np.nan
up = int((valid[value_col] > 0).sum())
down = int((valid[value_col] < 0).sum())

st.markdown(f"### 🧭 Résumé global ({periode})")
if np.isfinite(avg):
    st.markdown(f"**Variation moyenne : {avg:+.2f}%** — {up} hausses / {down} baisses")
else:
    st.markdown("Variation indisponible pour cette période (jeu de données trop court).")

# Petites phrases “macro” best effort basées sur la dispersion
disp = (valid[value_col].std() * 100.0) if not valid.empty else np.nan
if np.isfinite(disp):
    if disp < 1.0:
        st.caption("Tonalité neutre, mouvements techniques sans catalyseurs majeurs.")
    elif disp < 2.5:
        st.caption("Volatilité modérée, leadership concentré sur quelques dossiers.")
    else:
        st.caption("Marché très dispersé : rotation sectorielle / flux macro dominants.")

st.divider()

# ---------------- Top / Flop ----------------
st.subheader(f"🏆 Top hausses & ⛔ Baisses — {periode}")

def prep_table(df, asc=False, n=5):
    if df.empty: return pd.DataFrame()
    cols = ["Ticker","name","Close", value_col, "Indice"]
    for c in cols:
        if c not in df.columns: df[c] = np.nan
    out = df.sort_values(value_col, ascending=asc).head(n).copy()
    out.rename(columns={"name":"Société","Close":"Cours (€)"}, inplace=True)
    out["Variation %"] = (out[value_col] * 100).round(2)
    out["Cours (€)"] = out["Cours (€)"].round(2)
    return out[["Indice","Société","Ticker","Cours (€)","Variation %"]]

col1, col2 = st.columns(2)
with col1:
    top = prep_table(valid.dropna(subset=[value_col]), asc=False, n=5)
    if top.empty:
        st.info("Pas de hausses calculables.")
    else:
        st.dataframe(style_variations(top, ["Variation %"]), use_container_width=True, hide_index=True)
with col2:
    flop = prep_table(valid.dropna(subset=[value_col]), asc=True, n=5)
    if flop.empty:
        st.info("Pas de baisses calculables.")
    else:
        st.dataframe(style_variations(flop, ["Variation %"]), use_container_width=True, hide_index=True)

# ---------------- Résumé actus (2–3 lignes) sur le Top & Flop ----------------
st.markdown("### 📰 Actualités (résumé 2–3 lignes)")
def short_news(row):
    nm = str(row.get("Société") or "")
    tk = str(row.get("Ticker") or "")
    txt, score, items = news_summary(nm, tk, lang="fr")
    return txt

if not top.empty:
    st.markdown("**Top hausses — explication probable**")
    for _, r in top.iterrows():
        st.markdown(f"- **{r['Société']} ({r['Ticker']})** : {short_news(r)}")
if not flop.empty:
    st.markdown("**Plus fortes baisses — explication probable**")
    for _, r in flop.iterrows():
        st.markdown(f"- **{r['Société']} ({r['Ticker']})** : {short_news(r)}")

st.divider()

# ---------------- Sélection IA — Opportunités idéales ----------------
st.subheader("🚀 Sélection IA — Opportunités idéales (TOP 5)")

top_actions = select_top_actions(valid, profile=profil, n=5)
if top_actions.empty:
    st.info("Aucune opportunité claire détectée aujourd’hui selon l’IA.")
else:
    st.dataframe(top_actions, use_container_width=True, hide_index=True)

# ---------------- Graph barres (option visuelle simple) ----------------
st.markdown("### 📊 Visualisation rapide")
def bar_chart(df, title):
    if df.empty: 
        st.caption("—")
        return
    d = df.copy()
    d["Label"] = d["Société"].astype(str) + " (" + d["Ticker"].astype(str) + ")"
    chart = (
        alt.Chart(d)
        .mark_bar()
        .encode(
            x=alt.X("Label:N", sort="-y", title=""),
            y=alt.Y("Variation %:Q", title="Variation (%)"),
            color=alt.Color("Variation %:Q", scale=alt.Scale(scheme="redyellowgreen")),
            tooltip=["Société","Ticker","Variation %","Cours (€)","Indice"]
        )
        .properties(height=320, title=title)
    )
    st.altair_chart(chart, use_container_width=True)

col3, col4 = st.columns(2)
with col3: bar_chart(top, f"Top 5 hausses ({periode})")
with col4: bar_chart(flop, f"Top 5 baisses ({periode})")
