# -*- coding: utf-8 -*-
"""
v6.4 — Mon Portefeuille (stable & complet)
- Tableau éditable (ajout/modif/suppression)
- Export / Import JSON (multi-appareils)
- Convertisseur LS Exchange → Yahoo
- Recherche par nom / ISIN / WKN / Ticker
- Niveaux Entrée / Objectif / Stop + Décision IA (pastilles)
- Graphiques performance (%) et PnL (€)
"""

import os, json, numpy as np, pandas as pd, altair as alt, streamlit as st
from lib import (
    fetch_prices, compute_metrics, price_levels_from_row, decision_label_from_row,
    style_variations, company_name_from_ticker, get_profile_params,
    resolve_identifier, find_ticker_by_name, load_mapping, save_mapping,
    maybe_guess_yahoo
)

# --- Config
st.set_page_config(page_title="Mon Portefeuille", page_icon="💼", layout="wide")
st.title("💼 Mon Portefeuille — PEA & CTO")

# --- Chargement portefeuille JSON
DATA_PATH = "data/portfolio.json"
os.makedirs("data", exist_ok=True)

if not os.path.exists(DATA_PATH):
    pd.DataFrame(columns=["Ticker", "Type", "Qty", "PRU", "Name"]).to_json(
        DATA_PATH, orient="records", indent=2, force_ascii=False
    )

try:
    pf = pd.read_json(DATA_PATH)
except Exception:
    pf = pd.DataFrame(columns=["Ticker", "Type", "Qty", "PRU", "Name"])

for c, default in [("Ticker", ""), ("Type", "PEA"), ("Qty", 0.0), ("PRU", 0.0), ("Name", "")]:
    if c not in pf.columns:
        pf[c] = default

# --- Outils sauvegarde / import-export
cols = st.columns(4)
with cols[0]:
    if st.button("💾 Sauvegarder"):
        pf.to_json(DATA_PATH, orient="records", indent=2, force_ascii=False)
        st.success("✅ Sauvegardé.")
with cols[1]:
    if st.button("🗑 Réinitialiser"):
        os.remove(DATA_PATH)
        pd.DataFrame(columns=["Ticker","Type","Qty","PRU","Name"]).to_json(DATA_PATH, orient="records", indent=2)
        st.success("♻️ Réinitialisé."); st.rerun()
with cols[2]:
    st.download_button("⬇️ Exporter", json.dumps(pf.to_dict(orient="records"), ensure_ascii=False, indent=2),
                       file_name="portfolio.json", mime="application/json")
with cols[3]:
    up = st.file_uploader("📥 Importer JSON", type=["json"], label_visibility="collapsed")
    if up:
        try:
            imp = pd.DataFrame(json.load(up))
            for c in ["Ticker","Type","Qty","PRU","Name"]:
                if c not in imp.columns:
                    imp[c] = "" if c in ("Ticker","Type","Name") else 0.0
            imp.to_json(DATA_PATH, orient="records", indent=2, force_ascii=False)
            st.success("✅ Importé."); st.rerun()
        except Exception as e:
            st.error(f"Erreur : {e}")

st.divider()

# --- Convertisseur LS → Yahoo
with st.expander("🔁 Convertisseur LS Exchange → Yahoo"):
    c1, c2, c3 = st.columns(3)
    with c1: ls = st.text_input("Ticker LS Exchange (ex: TOTB)", "")
    with c2:
        if st.button("🔍 Convertir"):
            if not ls.strip():
                st.warning("Indique un ticker.")
            else:
                y = maybe_guess_yahoo(ls)
                if y:
                    st.session_state["conv"] = (ls.upper(), y)
                    st.success(f"{ls.upper()} → {y}")
                else:
                    st.warning("Aucune correspondance trouvée.")
    with c3:
        if st.button("✅ Enregistrer"):
            pair = st.session_state.get("conv")
            if not pair:
                st.warning("Aucune conversion active.")
            else:
                src, dst = pair
                m = load_mapping(); m[src] = dst; save_mapping(m)
                st.success(f"Ajouté : {src} → {dst}")

st.divider()

# --- Recherche ajout
with st.expander("🔎 Recherche par nom / ISIN / WKN / Ticker"):
    q = st.text_input("Nom ou identifiant", "")
    t = st.selectbox("Type", ["PEA", "CTO"])
    qty = st.number_input("Qté", min_value=0.0, step=1.0)
    if st.button("Rechercher"):
        if not q.strip():
            st.warning("Entre un terme.")
        else:
            sym, _ = resolve_identifier(q)
            if sym:
                st.session_state["search_res"] = [{"symbol": sym, "shortname": company_name_from_ticker(sym)}]
            else:
                st.session_state["search_res"] = find_ticker_by_name(q) or []
    res = st.session_state.get("search_res", [])
    if res:
        labels = [f"{r['symbol']} — {r.get('shortname','')}" for r in res]
        sel = st.selectbox("Résultats", labels)
        if st.button("➕ Ajouter"):
            i = labels.index(sel)
            sym = res[i]["symbol"]
            nm = res[i].get("shortname", sym)
            pf = pd.concat([pf, pd.DataFrame([{"Ticker": sym.upper(), "Type": t, "Qty": qty, "PRU": 0.0, "Name": nm}])], ignore_index=True)
            pf.to_json(DATA_PATH, orient="records", indent=2, force_ascii=False)
            st.success(f"Ajouté : {nm} ({sym})"); st.rerun()

st.divider()

# --- Tableau principal
st.subheader("📝 Mon Portefeuille")
edited = st.data_editor(
    pf, num_rows="dynamic", use_container_width=True, hide_index=True,
    column_config={
        "Ticker": st.column_config.TextColumn("Ticker"),
        "Type": st.column_config.SelectboxColumn("Type", options=["PEA","CTO"]),
        "Qty": st.column_config.NumberColumn("Qté", format="%.2f"),
        "PRU": st.column_config.NumberColumn("PRU (€)", format="%.2f"),
        "Name": st.column_config.TextColumn("Nom"),
    }
)

c1, c2 = st.columns(2)
with c1:
    if st.button("💾 Enregistrer les modifs"):
        edited["Ticker"] = edited["Ticker"].astype(str).str.upper()
        edited.to_json(DATA_PATH, orient="records", indent=2, force_ascii=False)
        st.success("✅ Sauvegardé."); st.rerun()
with c2:
    if st.button("🔄 Rafraîchir"):
        st.cache_data.clear(); st.rerun()

if edited.empty:
    st.info("Ajoute une action pour commencer."); st.stop()

# --- Analyse IA
tickers = edited["Ticker"].dropna().unique().tolist()
hist = fetch_prices(tickers, days=120)
met = compute_metrics(hist)
merged = edited.merge(met, on="Ticker", how="left")

profil = st.session_state.get("profil", "Neutre")
volmax = get_profile_params(profil)["vol_max"]

rows = []
for _, r in merged.iterrows():
    px = float(r.get("Close", np.nan))
    qty = float(r.get("Qty", 0))
    pru = float(r.get("PRU", np.nan))
    name = r.get("Name") or company_name_from_ticker(r.get("Ticker"))
    levels = price_levels_from_row(r, profil)
    val = px * qty if np.isfinite(px) else np.nan
    perf = ((px / pru) - 1) * 100 if (np.isfinite(px) and np.isfinite(pru) and pru > 0) else np.nan
    dec = decision_label_from_row(r, held=True, vol_max=volmax)
    rows.append({
        "Type": r["Type"],
        "Nom": name,
        "Ticker": r["Ticker"],
        "Cours (€)": round(px,2) if np.isfinite(px) else None,
        "Qté": qty,
        "PRU (€)": round(pru,2) if np.isfinite(pru) else None,
        "Valeur (€)": round(val,2) if np.isfinite(val) else None,
        "Perf%": round(perf,2) if np.isfinite(perf) else None,
        "Entrée (€)": levels["entry"],
        "Objectif (€)": levels["target"],
        "Stop (€)": levels["stop"],
        "Décision IA": dec
    })

out = pd.DataFrame(rows)
st.dataframe(style_variations(out, ["Perf%"]), use_container_width=True, hide_index=True)

# --- Graphiques
st.subheader("📈 Performance 90 jours")
hist90 = fetch_prices(tickers, days=100)
if hist90.empty or "Date" not in hist90.columns:
    st.caption("Pas assez d'historique.")
else:
    df = []
    for _, r in edited.iterrows():
        t, q, pru, tp = r["Ticker"], r["Qty"], r["PRU"], r["Type"]
        d = hist90[hist90["Ticker"] == t].copy()
        if d.empty: continue
        d["Perf%"] = (d["Close"] / pru - 1) * 100
        d["PnL€"] = (d["Close"] - pru) * q
        d["Type"] = tp
        df.append(d[["Date","Perf%","PnL€","Type"]])
    if df:
        D = pd.concat(df)
        ch1 = alt.Chart(D).mark_line().encode(x="Date:T", y="Perf%:Q", color="Type:N",
                                              tooltip=["Date:T","Perf%:Q","Type"]).properties(title="Rentabilité (%)")
        ch2 = alt.Chart(D).mark_line().encode(x="Date:T", y="PnL€:Q", color="Type:N",
                                              tooltip=["Date:T","PnL€:Q","Type"]).properties(title="Gain/Perte (€)")
        st.altair_chart(ch1, use_container_width=True)
        st.altair_chart(ch2, use_container_width=True)
