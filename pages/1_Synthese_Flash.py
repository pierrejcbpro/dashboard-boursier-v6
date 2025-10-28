# -*- coding: utf-8 -*-
"""
v7.0 — 🌍 Synthèse Marché
Indices: CAC 40, DAX 40, S&P 500, NASDAQ 100
- Profil IA partagé (Agressif / Neutre / Prudent)
- Périodes : Jour / 7 jours / 30 jours
- Résumé global + bar chart des variations moyennes par indice
- Top +10 et Top −10 (tableaux verticaux) avec Décision IA & niveaux
- Actu marché (Europe/US) avec titres cliquables + dates
"""

import streamlit as st
import pandas as pd
import numpy as np
import altair as alt
import requests, html, re
from datetime import datetime

from lib import (
    fetch_all_markets,  # agrège membres + prix + métriques + 'Indice' + 'name'
    get_profile_params,
    decision_label_from_row,
    price_levels_from_row,
    style_variations
)

# -------------------- UI CONFIG --------------------
st.set_page_config(page_title="Synthèse Marché", page_icon="🌍", layout="wide")
st.title("🌍 Synthèse Marché — Vue Globale & IA")

# -------------------- PARAMÈTRES --------------------
PERIODES = ["Jour", "7 jours", "30 jours"]
value_map = {"Jour": "pct_1d", "7 jours": "pct_7d", "30 jours": "pct_30d"}
days_hist_map = {"Jour": 60, "7 jours": 90, "30 jours": 150}  # historique pour métriques stables

with st.sidebar:
    st.markdown("### ⚙️ Paramètres")
    periode = st.radio("Période", PERIODES, index=0, horizontal=True)
    profil = st.session_state.get("profil", "Neutre")
    st.markdown(f"**Profil IA actif :** `{profil}`")

value_col = value_map[periode]
days_hist = days_hist_map[periode]
TOPN = 10

UNIVERSES = [
    ("CAC 40", ""),   # watchlist text inutilisée ici
    ("DAX 40", ""),
    ("S&P 500", ""),
    ("NASDAQ 100", "")
]

# -------------------- NEWS HELPERS --------------------
def google_news_titles_and_dates(q, lang="fr", limit=6):
    """Retourne [(title, link, date_str)] depuis Google News RSS (léger)."""
    url = f"https://news.google.com/rss/search?q={requests.utils.quote(q)}&hl={lang}-{lang.upper()}&gl={lang.upper()}&ceid={lang.upper()}:{lang.upper()}"
    try:
        xml = requests.get(url, timeout=10).text
        items = re.findall(r"<item>(.*?)</item>", xml, flags=re.S)
        out = []
        for it in items:
            tt = re.search(r"<title><!\[CDATA\[(.*?)\]\]></title>|<title>(.*?)</title>", it, flags=re.S)
            lk = re.search(r"<link>(.*?)</link>", it, flags=re.S)
            dt = re.search(r"<pubDate>(.*?)</pubDate>", it)
            t = html.unescape((tt.group(1) or tt.group(2) or "").strip()) if tt else ""
            l = (lk.group(1).strip() if lk else "")
            d = ""
            if dt:
                try:
                    d = datetime.strptime(dt.group(1).strip(), "%a, %d %b %Y %H:%M:%S %Z").strftime("%d/%m/%Y")
                except Exception:
                    d = dt.group(1).strip()
            if t and l:
                out.append((t, l, d))
            if len(out) >= limit:
                break
        return out
    except Exception:
        return []

def news_flash_for_region(region: str):
    """Récupère quelques titres pour un flash succinct par région."""
    query = "marché actions europe" if region == "EU" else "stock market us"
    lang = "fr" if region == "EU" else "en"
    return google_news_titles_and_dates(query, lang=lang, limit=5)

# -------------------- CHARGEMENT DONNÉES --------------------
with st.spinner("Chargement des marchés..."):
    data = fetch_all_markets(UNIVERSES, days_hist=days_hist)

if data.empty:
    st.warning("Aucune donnée disponible. Réessaie plus tard.")
    st.stop()

# On attend au minimum : 'Ticker','Close', value_col, 'Indice', 'name' (si présent)
if value_col not in data.columns:
    st.warning(f"Variation indisponible pour la période « {periode} ».") 
    st.stop()

valid = data.dropna(subset=[value_col]).copy()
if valid.empty:
    st.warning("Pas de variations calculables sur la sélection.")
    st.stop()

# -------------------- RÉSUMÉ GLOBAL --------------------
avg_var = valid[value_col].mean() * 100.0
nb_up = int((valid[value_col] > 0).sum())
nb_down = int((valid[value_col] < 0).sum())
tonalite = "haussière ✅" if avg_var > 0.15 else ("baissière ⚠️" if avg_var < -0.15 else "neutre ➖")

st.subheader(f"🧭 Résumé global ({periode})")
colA, colB = st.columns([1,1])
with colA:
    st.metric("Variation moyenne agrégée", f"{avg_var:+.2f}%")
    st.caption(f"Nombre de hausses : **{nb_up}** — baisses : **{nb_down}** — tonalité **{tonalite}**")
with colB:
    # bar chart par indice
    grp = (valid.groupby("Indice")[value_col].mean().reset_index()
                  .rename(columns={value_col: "Variation"}))
    grp["Variation"] = grp["Variation"] * 100.0
    chart = alt.Chart(grp).mark_bar().encode(
        x=alt.X("Indice:N", sort="-y"),
        y=alt.Y("Variation:Q", title="Variation moyenne (%)"),
        color=alt.condition(
            alt.datum.Variation >= 0,
            alt.value("#0b8f3a"),  # vert
            alt.value("#d5353a")   # rouge
        ),
        tooltip=["Indice", alt.Tooltip("Variation:Q", format=".2f")]
    ).properties(height=260)
    st.altair_chart(chart, use_container_width=True)

st.divider()

# -------------------- TOPS & FLOPS --------------------
st.subheader(f"🏆 Top +{TOPN} et 🚨 Top −{TOPN} — {periode}")

def build_table(set_df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    if set_df.empty:
        return pd.DataFrame()
    for _, r in set_df.iterrows():
        px = float(r.get("Close", np.nan))
        name = r.get("name") or r.get("Name") or r.get("Ticker")
        # Décision IA & niveaux (profil partagé)
        dec = decision_label_from_row(r, held=False, vol_max=get_profile_params(profil)["vol_max"])
        lv = price_levels_from_row(r, profil)
        rows.append({
            "Indice": r.get("Indice",""),
            "Nom": str(name),
            "Ticker": r.get("Ticker",""),
            "Cours (€)": round(px,2) if np.isfinite(px) else None,
            "Variation (%)": round(r.get(value_col, 0)*100, 2) if pd.notna(r.get(value_col)) else None,
            "Décision IA": dec,
            "Entrée (€)": lv["entry"],
            "Objectif (€)": lv["target"],
            "Stop (€)": lv["stop"]
        })
    return pd.DataFrame(rows)

# Sélection top/bottom
top = (valid.sort_values(value_col, ascending=False)
            .groupby("Indice", group_keys=False)
            .apply(lambda g: g.head(TOPN // 2))  # équilibrer entre indices
            .reset_index(drop=True))

# pour garantir TOPN global si nécessaire
top = (valid.sort_values(value_col, ascending=False).head(TOPN)
       if len(top) < TOPN else top)

low = (valid.sort_values(value_col, ascending=True)
            .groupby("Indice", group_keys=False)
            .apply(lambda g: g.head(TOPN // 2))
            .reset_index(drop=True))
low = (valid.sort_values(value_col, ascending=True).head(TOPN)
       if len(low) < TOPN else low)

tab_top = build_table(top)
tab_low = build_table(low)

def color_variations(df: pd.DataFrame) -> pd.io.formats.style.Styler:
    def _color(v):
        if pd.isna(v): return ""
        if v > 0: return "background-color:#e8f5e9; color:#0b8f3a"
        if v < 0: return "background-color:#ffebee; color:#d5353a"
        return "background-color:#e8f0fe; color:#1e88e5"
    sty = df.style.applymap(_color, subset=["Variation (%)"])
    return sty

st.markdown("### 🟢 Top hausses")
if tab_top.empty:
    st.info("Aucune valeur éligible.")
else:
    st.dataframe(color_variations(tab_top), use_container_width=True, hide_index=True)

st.markdown("### 🔴 Top baisses")
if tab_low.empty:
    st.info("Aucune valeur éligible.")
else:
    st.dataframe(color_variations(tab_low), use_container_width=True, hide_index=True)

st.divider()

# -------------------- FLASH ACTU MARCHÉ --------------------
st.subheader("📰 Flash actu marché (daté)")

colEU, colUS = st.columns(2)
with colEU:
    st.markdown("**Europe (CAC / DAX)**")
    eu_news = news_flash_for_region("EU")
    if eu_news:
        for t, l, d in eu_news:
            st.markdown(f"- [{t}]({l})" + (f" *(publié le {d})*" if d else ""))
    else:
        st.caption("Pas d'actualité européenne détectée.")
with colUS:
    st.markdown("**États-Unis (S&P / Nasdaq)**")
    us_news = news_flash_for_region("US")
    if us_news:
        for t, l, d in us_news:
            st.markdown(f"- [{t}]({l})" + (f" *(publié le {d})*" if d else ""))
    else:
        st.caption("Pas d'actualité US détectée.")

# -------------------- SYNTHÈSE IA GLOBALE --------------------
st.divider()
st.subheader("🧠 Synthèse IA globale (2–3 lignes)")
# heuristique simple selon la dispersion et la moyenne :
spread = valid[value_col].std() * 100
sector_tone = (
    "tonalité **haussière** portée par les grandes capitalisations"
    if avg_var > 0.2 and nb_up > nb_down else
    "tonalité **baissière** avec pression sur les valeurs sensibles aux taux"
    if avg_var < -0.2 and nb_down > nb_up else
    "marché **neutre / rotation** sectorielle, mouvements techniques"
)
st.info(
    f"Variation moyenne **{avg_var:+.2f}%** — {nb_up} hausses / {nb_down} baisses — "
    f"dispersion **{spread:.2f} pts** : {sector_tone}."
)
