# -*- coding: utf-8 -*-
"""
v6.9 — Recherche universelle
- Recherche par Nom / Ticker LS Exchange / ISIN / WKN → conversion Yahoo
- Mémoire de la dernière recherche
- Analyse IA complète (MA20/MA50/ATR, Entrée / Objectif / Stop, Décision IA)
- Graphique avec lignes de niveaux (périodes: Jour / 7j / 30j / 1 an / 5 ans)
- Actualités ciblées (liens cliquables + résumé court)
"""

import streamlit as st, pandas as pd, numpy as np, altair as alt
from lib import (
    fetch_prices, compute_metrics, price_levels_from_row, decision_label_from_row,
    company_name_from_ticker, get_profile_params, resolve_identifier,
    find_ticker_by_name, maybe_guess_yahoo
)

import requests, html, re

# ---------------- UI CONFIG ----------------
st.set_page_config(page_title="Recherche universelle", page_icon="🔍", layout="wide")
st.title("🔍 Recherche universelle")

# ---------------- HELPERS ----------------
def remember_last_search(symbol=None, query=None, period=None):
    if symbol is not None:
        st.session_state["ru_symbol"] = symbol
    if query is not None:
        st.session_state["ru_query"] = query
    if period is not None:
        st.session_state["ru_period"] = period

def get_last_search(default_period="30 jours"):
    return (
        st.session_state.get("ru_symbol", ""),
        st.session_state.get("ru_query", ""),
        st.session_state.get("ru_period", default_period),
    )

def google_news_titles_and_links(q, lang="fr", limit=6):
    """Mini fetch Google News RSS → [(title, link)] (sans dépendances externes)."""
    url = f"https://news.google.com/rss/search?q={requests.utils.quote(q)}&hl={lang}-{lang.upper()}&gl={lang.upper()}&ceid={lang.upper()}:{lang.upper()}"
    try:
        xml = requests.get(url, timeout=10).text
        # Très tolérant pour extraire title & link
        items = re.findall(r"<item>(.*?)</item>", xml, flags=re.S)
        out = []
        for it in items:
            tt = re.search(r"<title><!\[CDATA\[(.*?)\]\]></title>|<title>(.*?)</title>", it, flags=re.S)
            lk = re.search(r"<link>(.*?)</link>", it, flags=re.S)
            t = html.unescape((tt.group(1) or tt.group(2) or "").strip()) if tt else ""
            l = (lk.group(1).strip() if lk else "")
            if t and l:
                out.append((t, l))
            if len(out) >= limit:
                break
        return out
    except Exception:
        return []

def short_news_summary(titles):
    """Heuristique ultra-légère pour résumer le ton des titres (2-3 lignes)."""
    if not titles:
        return "Pas d’actualité saillante — mouvement possiblement technique (flux, arbitrages, macro)."
    pos_kw = ["résultats", "bénéfice", "guidance", "relève", "contrat", "approbation", "dividende", "rachat", "upgrade", "partenariat", "record"]
    neg_kw = ["profit warning", "avertissement", "enquête", "retard", "rappel", "amende", "downgrade", "abaisse", "procès", "licenciement", "chute"]
    s = 0
    for t, _ in titles:
        low = t.lower()
        if any(k in low for k in pos_kw): s += 1
        if any(k in low for k in neg_kw): s -= 1
    if s >= 1:
        return "Hausse soutenue par des nouvelles positives (résultats/contrats/relèvements)."
    elif s <= -1:
        return "Pression liée à des nouvelles défavorables (abaissements, enquêtes, retards)."
    else:
        return "Actualité mitigée/neutre : mouvement surtout technique (rotation sectorielle, macro)."

def risk_badge_from_row(row, profil="Neutre"):
    """Génère la décision IA (badge) à partir des indicateurs du row."""
    volmax = get_profile_params(profil)["vol_max"]
    return decision_label_from_row(row, held=False, vol_max=volmax)

def levels_from_row(row, profil="Neutre"):
    lv = price_levels_from_row(row, profil)
    return lv["entry"], lv["target"], lv["stop"]

def pretty_pct(x):
    return f"{x*100:+.2f}%" if pd.notna(x) else "—"

# ---------------- SIDEBAR ----------------
last_symbol, last_query, last_period = get_last_search()

with st.sidebar:
    st.markdown("### 🎛 Recherche")
    query = st.text_input("Nom / Ticker LS / ISIN / WKN / Yahoo", value=last_query)
    period = st.selectbox("Période du graphique", ["Jour", "7 jours", "30 jours", "1 an", "5 ans"],
                          index=["Jour","7 jours","30 jours","1 an","5 ans"].index(last_period))
    # profondeur pour fetch_prices
    days_map = {"Jour": 5, "7 jours": 10, "30 jours": 40, "1 an": 400, "5 ans": 1300}
    days_graph = days_map[period]
    if st.button("🔎 Lancer la recherche"):
        # 1) tentative résolution directe
        sym, src = resolve_identifier(query) if query.strip() else (None, None)
        if not sym:  # 2) essai via nom
            results = find_ticker_by_name(query) or []
            if results:
                sym = results[0]["symbol"]
        if not sym:  # 3) essai conversion LS simple
            sym = maybe_guess_yahoo(query) or query.strip().upper()
        remember_last_search(symbol=sym, query=query, period=period)
        st.rerun()

# Charger la recherche mémorisée
symbol = st.session_state.get("ru_symbol", "")

# ---------------- CONTENU PRINCIPAL ----------------
if not symbol:
    st.info("Tape un **nom d’entreprise**, un **ticker LS Exchange**, un **ISIN**, un **WKN** ou directement un **ticker Yahoo** dans la barre latérale, puis clique **Lancer la recherche**.")
    st.stop()

# 1) Télécharger historique pour le graphique (jours variables)
hist_graph = fetch_prices([symbol], days=days_graph)
# 2) Télécharger historique fixe (120 jours) pour les indicateurs IA
hist_full = fetch_prices([symbol], days=120)
metrics = compute_metrics(hist_full)

if metrics.empty:
    st.warning("Impossible de calculer les indicateurs sur cette valeur (historique insuffisant).")
    st.stop()

row = metrics.iloc[0]  # compute_metrics renvoie 1 ligne par Ticker (dernier point)
name = company_name_from_ticker(symbol)

# ---- Header carte info / stats
col1, col2, col3, col4 = st.columns([1.6, 1, 1, 1])
with col1:
    st.markdown(f"## {name}  \n`{symbol}`")
    st.caption("Analyse IA basée sur MA20/MA50/ATR (120 jours fixes).")
with col2:
    st.metric("Cours", f"{row['Close']:.2f}")
with col3:
    st.metric("MA20 / MA50",
              f"{(row['MA20'] if pd.notna(row['MA20']) else np.nan):.2f} / {(row['MA50'] if pd.notna(row['MA50']) else np.nan):.2f}")
with col4:
    st.metric("ATR14", f"{(row['ATR14'] if pd.notna(row['ATR14']) else np.nan):.2f}")

# Variations
v1d = row.get("pct_1d", np.nan)
v7d = row.get("pct_7d", np.nan)
v30 = row.get("pct_30d", np.nan)
st.markdown(
    f"**Variations** — 1j: {pretty_pct(v1d)} · 7j: {pretty_pct(v7d)} · 30j: {pretty_pct(v30)}"
)

st.divider()

# ---- Analyse IA : niveaux + décision
profil = st.session_state.get("profil", "Neutre")
entry, target, stop = levels_from_row(row, profil)
decision = risk_badge_from_row(row, profil)

cA, cB = st.columns([1.2, 2])
with cA:
    st.subheader("🧠 Synthèse IA")
    bullets = []
    # Tendance
    if pd.notna(row.get("MA20")) and pd.notna(row.get("MA50")):
        if row["Close"] >= row["MA20"] >= row["MA50"]:
            bullets.append("Tendance **haussière** (Cours > MA20 > MA50).")
        elif row["Close"] <= row["MA20"] <= row["MA50"]:
            bullets.append("Tendance **baissière** (Cours < MA20 < MA50).")
        else:
            bullets.append("Structure **mixte / en consolidation** (MA20/MA50 non alignées).")
    # Volatilité simple
    vol = (abs(row["MA20"] - row["MA50"]) / row["MA50"] * 100) if (pd.notna(row["MA20"]) and pd.notna(row["MA50"]) and row["MA50"] != 0) else np.nan
    if pd.notna(vol):
        if vol < 2: bullets.append("Volatilité : **faible** (MA20 proche MA50).")
        elif vol < 5: bullets.append("Volatilité : **modérée**.")
        else: bullets.append("Volatilité : **élevée** (écart MA important).")

    st.markdown(
        f"- **Décision IA** : {decision}\n"
        f"- **Entrée** ≈ **{entry:.2f}** · **Objectif** ≈ **{target:.2f}** · **Stop** ≈ **{stop:.2f}**\n"
        + ("\n".join([f"- {b}" for b in bullets]) if bullets else "")
    )

with cB:
    st.subheader(f"📈 Graphique — {period}")
    if hist_graph.empty or "Date" not in hist_graph.columns:
        st.caption("Pas assez d'historique pour afficher le graphique.")
    else:
        d = hist_graph[hist_graph["Ticker"] == symbol].copy()
        d = d.sort_values("Date")
        base = alt.Chart(d).mark_line().encode(
            x=alt.X("Date:T", title=""),
            y=alt.Y("Close:Q", title="Cours"),
            tooltip=[alt.Tooltip("Date:T"), alt.Tooltip("Close:Q", format=".2f")]
        ).properties(height=380)

        levels_df = pd.DataFrame({
            "y": [entry, target, stop],
            "label": ["Entrée ~", "Objectif ~", "Stop ~"]
        })
        rules = alt.Chart(levels_df).mark_rule(strokeDash=[6,4]).encode(
            y="y:Q",
            color=alt.value("#888"),
            tooltip=["label:N","y:Q"]
        )
        st.altair_chart(base + rules, use_container_width=True)

st.divider()

# ---- Actualités ciblées (liens + résumé)
st.subheader("📰 Actualités récentes ciblées")
news = google_news_titles_and_links(f"{name} {symbol}", lang="fr", limit=6)
if not news:
    news = google_news_titles_and_links(name, lang="fr", limit=6)

if news:
    st.markdown("**Résumé IA (2–3 lignes)**")
    st.info(short_news_summary(news))
    st.markdown("**Articles**")
    for title, link in news:
        st.markdown(f"- [{title}]({link})")
else:
    st.caption("Aucune actualité immédiatement disponible pour cette valeur.")

# ---- Footer memo
remember_last_search(symbol=symbol, query=query if 'query' in locals() else last_query, period=period)
