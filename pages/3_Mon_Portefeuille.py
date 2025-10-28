# -*- coding: utf-8 -*-
"""
v6.8 — Mon Portefeuille (benchmark + IA stable)
- Analyse IA basée sur 120 jours fixes
- Graphique dynamique avec benchmark (CAC/DAX/S&P/NASDAQ)
- Comparaison synthétique chiffrée
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

# --- Choix période + benchmark
periode = st.sidebar.radio("Période (graphique)", ["1 jour", "7 jours", "30 jours"], index=0)
days_map = {"1 jour": 2, "7 jours": 10, "30 jours": 35}
days_hist = days_map[periode]

benchmark_label = st.sidebar.selectbox(
    "Indice de référence (benchmark)",
    ["CAC 40", "DAX", "S&P 500", "NASDAQ 100"],
    index=0
)
benchmark_tickers = {"CAC 40": "^FCHI", "DAX": "^GDAXI", "S&P 500": "^GSPC", "NASDAQ 100": "^NDX"}
benchmark_symbol = benchmark_tickers[benchmark_label]

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

# --- Boutons gestion
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

# --- Analyse IA stable (120j)
tickers = edited["Ticker"].dropna().unique().tolist()
hist_full = fetch_prices(tickers, days=120)
met = compute_metrics(hist_full)
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
    gain_eur = (px - pru) * qty if np.isfinite(px) and np.isfinite(pru) else np.nan
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
        "Gain/Perte (€)": round(gain_eur,2) if np.isfinite(gain_eur) else None,
        "Perf%": round(perf,2) if np.isfinite(perf) else None,
        "Entrée (€)": levels["entry"],
        "Objectif (€)": levels["target"],
        "Stop (€)": levels["stop"],
        "Décision IA": dec
    })
out = pd.DataFrame(rows)
st.dataframe(style_variations(out, ["Perf%"]), use_container_width=True, hide_index=True)

# --- Synthèse performance
def synthese_perf(df, t):
    df = df[df["Type"] == t]
    if df.empty: return 0, 0
    val = df["Valeur (€)"].sum()
    gain = df["Gain/Perte (€)"].sum()
    pct = (gain / (val - gain) * 100) if val - gain != 0 else 0
    return gain, pct

pea_gain, pea_pct = synthese_perf(out, "PEA")
cto_gain, cto_pct = synthese_perf(out, "CTO")
tot_gain, tot_pct = out["Gain/Perte (€)"].sum(), (
    (out["Gain/Perte (€)"].sum() / (out["Valeur (€)"].sum() - out["Gain/Perte (€)"].sum()) * 100)
    if out["Valeur (€)"].sum() > 0 else 0
)
st.markdown(f"""
### 📊 Synthèse {periode}
**PEA** : {pea_gain:+.2f} € ({pea_pct:+.2f}%)  
**CTO** : {cto_gain:+.2f} € ({cto_pct:+.2f}%)  
**Total** : {tot_gain:+.2f} € ({tot_pct:+.2f}%)
""")

# --- Graphique comparé au benchmark
st.subheader(f"📈 Portefeuille vs {benchmark_label} ({periode})")
hist_graph = fetch_prices(tickers + [benchmark_symbol], days=days_hist)
if hist_graph.empty or "Date" not in hist_graph.columns:
    st.caption("Pas assez d'historique.")
else:
    df = []
    for _, r in edited.iterrows():
        t, q, pru, tp = r["Ticker"], r["Qty"], r["PRU"], r["Type"]
        d = hist_graph[hist_graph["Ticker"] == t].copy()
        if d.empty: continue
        d["Valeur"] = d["Close"] * q
        d["Type"] = tp
        df.append(d[["Date","Valeur","Type"]])
    if df:
        D = pd.concat(df)
        agg = D.groupby(["Date","Type"]).agg({"Valeur":"sum"}).reset_index()
        tot = agg.groupby("Date")["Valeur"].sum().reset_index().assign(Type="Total")

        # Benchmark
        bmk = hist_graph[hist_graph["Ticker"] == benchmark_symbol].copy()
        bmk = bmk.assign(Type=benchmark_label, Valeur=bmk["Close"] / bmk["Close"].iloc[0] * tot["Valeur"].iloc[0])

        full = pd.concat([agg, tot, bmk])
        base = full.groupby("Type").apply(lambda g: g.assign(Pct=(g["Valeur"]/g["Valeur"].iloc[0]-1)*100)).reset_index(drop=True)

        # Comparaison texte
        perf_port = base[base["Type"]=="Total"]["Pct"].iloc[-1]
        perf_bmk = base[base["Type"]==benchmark_label]["Pct"].iloc[-1]
        diff = perf_port - perf_bmk
        msg = f"✅ Votre portefeuille surperforme le {benchmark_label} de {diff:+.2f}%." if diff > 0 else f"⚠️ Votre portefeuille sous-performe le {benchmark_label} de {abs(diff):.2f}%."
        st.markdown(f"**{msg}**")

        # Graphique
        chart = alt.Chart(base).mark_line().encode(
            x="Date:T",
            y=alt.Y("Pct:Q", title="Variation (%)"),
            color=alt.Color("Type:N", scale=alt.Scale(scheme="category10")),
            tooltip=["Date:T","Type:N","Pct:Q"]
        ).properties(height=400)
        st.altair_chart(chart, use_container_width=True)
