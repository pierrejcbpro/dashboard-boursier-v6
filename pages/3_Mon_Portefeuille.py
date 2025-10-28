# -*- coding: utf-8 -*-
"""
v6.4 — Mon Portefeuille (avancé)
- Tableau éditable (ajout/modif/suppression)
- Export / Import JSON (multi-appareils)
- Convertisseur LS Exchange -> Yahoo + mapping
- Recherche par nom / ISIN / WKN / Ticker
- Niveaux Entrée / Objectif / Stop + Décision IA
- Graphs perf pondérée (%) et PnL (€) PEA/CTO/Total
"""
import os, json
import numpy as np
import pandas as pd
import altair as alt
import streamlit as st

from lib import (
    fetch_prices, compute_metrics, price_levels_from_row, decision_label_from_row,
    style_variations, company_name_from_ticker, get_profile_params,
    resolve_identifier, find_ticker_by_name, load_mapping, save_mapping,
    maybe_guess_yahoo
)

st.set_page_config(page_title="Mon Portefeuille", page_icon="💼", layout="wide")
st.title("💼 Mon Portefeuille — PEA & CTO (avancé)")

# ---------------------------------------------------------
# Chemin de stockage local (persistant entre sessions)
# ---------------------------------------------------------
DATA_PATH = "data/portfolio.json"
os.makedirs("data", exist_ok=True)
if not os.path.exists(DATA_PATH):
    pd.DataFrame(columns=["Ticker","Type","Qty","PRU","Name"]).to_json(
        DATA_PATH, orient="records", indent=2, force_ascii=False
    )

# ---------------------------------------------------------
# Chargement + normalisation
# ---------------------------------------------------------
try:
    pf = pd.read_json(DATA_PATH)
except Exception:
    pf = pd.DataFrame(columns=["Ticker","Type","Qty","PRU","Name"])

# Colonnes minimales
for c, default in [("Ticker",""),("Type","PEA"),("Qty",0.0),("PRU",0.0),("Name","")]:
    if c not in pf.columns:
        pf[c] = default

# Nom automatique si manquant
mask_missing_name = pf["Name"].isna() | (pf["Name"].astype(str).str.strip() == "")
if mask_missing_name.any():
    pf.loc[mask_missing_name, "Name"] = pf.loc[mask_missing_name, "Ticker"].apply(company_name_from_ticker)
    pf.to_json(DATA_PATH, orient="records", indent=2, force_ascii=False)

# ---------------------------------------------------------
# Barre d’outils : Export / Import / Sauvegarde / Reset
# ---------------------------------------------------------
c_tools = st.columns([1,1,1,1,3])
with c_tools[0]:
    if st.button("💾 Sauvegarder"):
        pf.to_json(DATA_PATH, orient="records", indent=2, force_ascii=False)
        st.success("Portefeuille sauvegardé.")
with c_tools[1]:
    if st.button("🗑 Réinitialiser"):
        try:
            os.remove(DATA_PATH)
            pd.DataFrame(columns=["Ticker","Type","Qty","PRU","Name"]).to_json(
                DATA_PATH, orient="records", indent=2, force_ascii=False
            )
        except Exception:
            pass
        st.success("Portefeuille réinitialisé.")
        st.rerun()
with c_tools[2]:
    data_json = json.dumps(pf.to_dict(orient="records"), ensure_ascii=False, indent=2)
    st.download_button("⬇️ Export JSON", data_json, file_name="portfolio.json", mime="application/json")
with c_tools[3]:
    up = st.file_uploader("📥 Import JSON", type=["json"], label_visibility="collapsed")
    if up is not None:
        try:
            imported = pd.DataFrame(json.load(up))
            for c in ["Ticker","Type","Qty","PRU","Name"]:
                if c not in imported.columns:
                    imported[c] = "" if c in ("Ticker","Type","Name") else 0.0
            imported["Ticker"] = imported["Ticker"].astype(str).str.upper()
            imported.to_json(DATA_PATH, orient="records", indent=2, force_ascii=False)
            st.success("Portefeuille importé.")
            st.rerun()
        except Exception as e:
            st.error(f"Import impossible : {e}")

st.caption("💡 Astuce : utilise **Export JSON** pour synchroniser ton portefeuille entre tes appareils.")

st.divider()

# ---------------------------------------------------------
# Convertisseur LS Exchange -> Yahoo (mapping)
# ---------------------------------------------------------
with st.expander("🔁 Convertisseur LS Exchange → Yahoo (ajout au mapping)", expanded=False):
    ls_col1, ls_col2, ls_col3 = st.columns([1.2,1,1])
    with ls_col1:
        ls_in = st.text_input("Ticker LS Exchange (ex: TOTB, AIR, ORA, VOW3)", value="")
    with ls_col2:
        if st.button("🔎 Convertir"):
            if not ls_in.strip():
                st.warning("Renseigne un ticker LS.")
            else:
                guess = maybe_guess_yahoo(ls_in)
                if guess:
                    st.success(f"Proposition : **{ls_in.upper()} → {guess}**")
                    st.session_state["conv_guess"] = (ls_in.upper(), guess)
                else:
                    st.warning("Aucune proposition automatique.")
    with ls_col3:
        if st.button("✅ Enregistrer dans le mapping"):
            tup = st.session_state.get("conv_guess")
            if not tup:
                st.warning("Réalise d’abord une conversion.")
            else:
                src, sym = tup
                m = load_mapping()
                m[src] = sym
                save_mapping(m)
                st.success(f"Ajouté au mapping : {src} → {sym}")

# ---------------------------------------------------------
# Recherche par Nom / ISIN / WKN / Ticker
# ---------------------------------------------------------
with st.expander("🔎 Recherche & ajout par nom / ISIN / WKN / Ticker", expanded=False):
    q = st.text_input("Nom de l’entreprise, ISIN, WKN, ou Ticker", value="")
    cA, cB, cC = st.columns([1,1,1])
    with cA:
        if st.button("Rechercher"):
            if not q.strip():
                st.warning("Renseigne un identifiant ou un nom.")
            else:
                # 1) tentative de résolution directe (alias/ISIN/WKN/Ticker)
                sym, meta = resolve_identifier(q)
                if sym:
                    st.session_state["search_candidates"] = [{"symbol": sym, "shortname": company_name_from_ticker(sym), "exchDisp": ""}]
                else:
                    # 2) suggestions par nom via Yahoo
                    cands = find_ticker_by_name(q)
                    st.session_state["search_candidates"] = cands or []
                if not st.session_state["search_candidates"]:
                    st.info("Aucun résultat. Essaie un autre nom / identifiant.")
    with cB:
        add_type = st.selectbox("Type de compte", ["PEA","CTO"], index=0, key="search_add_type")
    with cC:
        add_qty = st.number_input("Quantité", min_value=0.0, step=1.0, value=0.0, key="search_add_qty")

    candidates = st.session_state.get("search_candidates", [])
    if candidates:
        labels = [f"{c.get('symbol','?')} — {c.get('shortname','')} ({c.get('exchDisp','')})" for c in candidates]
        sel = st.selectbox("Résultats", labels, index=0)
        if st.button("➕ Ajouter au portefeuille"):
            idx = labels.index(sel)
            sym = candidates[idx]["symbol"]
            name = candidates[idx].get("shortname") or company_name_from_ticker(sym)
            new_row = {"Ticker": sym.upper(), "Type": st.session_state["search_add_type"], "Qty": st.session_state["search_add_qty"], "PRU": 0.0, "Name": name}
            pf = pd.concat([pf, pd.DataFrame([new_row])], ignore_index=True)
            pf.to_json(DATA_PATH, orient="records", indent=2, force_ascii=False)
            st.success(f"Ajouté : {name} ({sym})")
            st.rerun()

st.divider()

# ---------------------------------------------------------
# Ajout rapide par identifiant (une ligne)
# ---------------------------------------------------------
st.subheader("➕ Ajout rapide par identifiant")
with st.form("add_line_form"):
    c1, c2, c3, c4 = st.columns([1.3,0.8,0.5,0.5])
    with c1: raw_id = st.text_input("Identifiant (Nom / Ticker / ISIN / WKN / alias)", placeholder="Ex: TotalEnergies ou AIR.PA ou US0378331005")
    with c2: acc = st.selectbox("Type", ["PEA","CTO"], index=0)
    with c3: qty = st.number_input("Qté", min_value=0.0, step=1.0, value=0.0)
    with c4: pru = st.number_input("PRU (€)", min_value=0.0, step=0.01, value=0.0)
    ok = st.form_submit_button("Ajouter")
    if ok:
        tick, _ = resolve_identifier(raw_id)
        if not tick:
            cands = find_ticker_by_name(raw_id)
            if cands:
                tick = cands[0]["symbol"]
                m = load_mapping(); m[raw_id.upper()] = tick; save_mapping(m)
        if not tick:
            st.warning("Impossible de trouver automatiquement. Essaie via la recherche par nom ci-dessus.")
        else:
            name = company_name_from_ticker(tick)
            new_row = {"Ticker": tick.upper(), "Type": acc, "Qty": qty, "PRU": pru, "Name": name}
            pf = pd.concat([pf, pd.DataFrame([new_row])], ignore_index=True)
            pf.to_json(DATA_PATH, orient="records", indent=2, force_ascii=False)
            st.success(f"Ajouté : {name} ({tick})")
            st.rerun()

st.divider()

# ---------------------------------------------------------
# Tableau éditable (data_editor)
# ---------------------------------------------------------
st.subheader("📝 Édition du portefeuille")
edited = st.data_editor(
    pf,
    num_rows="dynamic",
    use_container_width=True,
    hide_index=True,
    column_config={
        "Ticker": st.column_config.TextColumn(help="Ticker Yahoo Finance (ex: AIR.PA, TTE.PA, NVDA)"),
        "Type": st.column_config.SelectboxColumn(options=["PEA","CTO"], help="Type de compte"),
        "Qty": st.column_config.NumberColumn(format="%.2f", help="Quantité détenue"),
        "PRU": st.column_config.NumberColumn(format="%.4f", help="Prix de Revient Unitaire (€)"),
        "Name": st.column_config.TextColumn(help="Nom de la société")
    },
    key="pf_editor"
)

c_save, c_refresh = st.columns([1,1])
with c_save:
    if st.button("💾 Enregistrer le tableau"):
        # Normalise
        edited["Ticker"] = edited["Ticker"].astype(str).str.upper()
        edited["Type"] = edited["Type"].fillna("PEA")
        for c in ("Qty","PRU"):
            edited[c] = pd.to_numeric(edited[c], errors="coerce").fillna(0.0)
        # Remplit Name si vide
        need_name = edited["Name"].isna() | (edited["Name"].astype(str).str.strip()=="")
        edited.loc[need_name, "Name"] = edited.loc[need_name, "Ticker"].apply(company_name_from_ticker)
        edited.to_json(DATA_PATH, orient="records", indent=2, force_ascii=False)
        st.success("Tableau sauvegardé.")
        st.rerun()
with c_refresh:
    if st.button("🔄 Rafraîchir données (prix & indicateurs)"):
        st.cache_data.clear()
        st.rerun()

if edited.empty:
    st.info("Ajoute au moins une ligne puis sauvegarde."); st.stop()

# ---------------------------------------------------------
# Données de marché & indicateurs
# ---------------------------------------------------------
tickers = edited["Ticker"].dropna().astype(str).str.upper().unique().tolist()
hist = fetch_prices(tickers, days=120)
met = compute_metrics(hist)
merged = edited.merge(met, on="Ticker", how="left")

# ---------------------------------------------------------
# Tableau enrichi (Cours, Perf, Entrée/Stop/Objectif, IA)
# ---------------------------------------------------------
profil = st.session_state.get("profil", "Neutre")
volmax = get_profile_params(profil)["vol_max"]

rows = []
for _, r in merged.iterrows():
    name = r.get("Name") or company_name_from_ticker(r.get("Ticker","")) or r.get("Ticker","")
    px = float(r.get("Close", np.nan)) if pd.notna(r.get("Close", np.nan)) else np.nan
    qty = float(r.get("Qty", 0) or 0)
    pru = float(r.get("PRU", np.nan) or np.nan)

    levels = price_levels_from_row(r, profil)
    val = (px * qty) if np.isfinite(px) else np.nan
    perf = ((px / pru) - 1) * 100 if (np.isfinite(px) and np.isfinite(pru) and pru > 0) else np.nan
    dec = decision_label_from_row(r, held=True, vol_max=volmax)

    rows.append({
        "Type": r.get("Type",""),
        "Nom": name,
        "Ticker": r.get("Ticker",""),
        "Cours (€)": round(px,2) if np.isfinite(px) else None,
        "Qté": qty,
        "PRU (€)": pru if np.isfinite(pru) else None,
        "Valeur (€)": round(val,2) if np.isfinite(val) else None,
        "Perf%": round(perf,2) if np.isfinite(perf) else None,
        "Entrée (€)": levels["entry"],
        "Objectif (€)": levels["target"],
        "Stop (€)": levels["stop"],
        "Décision IA": dec
    })

out = pd.DataFrame(rows)
st.subheader("📋 Synthèse positions (avec IA)")
st.dataframe(style_variations(out, ["Perf%"]), use_container_width=True, hide_index=True)

# ---------------------------------------------------------
# Graphiques : Perf pondérée (%) et PnL (€) — 90 jours
# ---------------------------------------------------------
st.subheader("📈 Évolution du portefeuille (90 jours)")

hist90 = fetch_prices(tickers, days=100)
if hist90.empty or "Date" not in hist90.columns:
    st.caption("Historique insuffisant pour tracer les graphes.")
else:
    # 1) Prépare perfs par ligne (pondération par valeur courante)
    perf_rows, pnl_rows = [], []
    for _, pos in edited.iterrows():
        t = pos.get("Ticker")
        typ = pos.get("Type")
        pru = pos.get("PRU")
        qty = pos.get("Qty")
        if not t or not np.isfinite(pru) or pru <= 0 or not np.isfinite(qty):
            continue
        d = hist90[hist90["Ticker"] == t].copy()
        if d.empty:
            continue
        d = d[["Date","Close"]].copy()
        d["Perf%"] = (d["Close"] / pru - 1) * 100.0
        d["PnL€"] = (d["Close"] - pru) * qty
        d["Type"] = typ
        # poids = valeur courante
        last_px = d["Close"].iloc[-1]
        d["Poids"] = last_px * qty
        perf_rows.append(d[["Date","Perf%","Type","Poids"]])
        pnl_rows.append(d[["Date","PnL€","Type"]])

    charts_drawn = False

    if perf_rows:
        P = pd.concat(perf_rows, ignore_index=True)
        # Agrégations pondérées par date & type
        def wavg(g):
            w = g["Poids"].replace(0, np.nan)
            if w.isna().all():
                return pd.Series({"Perf%": np.nan})
            return pd.Series({"Perf%": float(np.average(g["Perf%"], weights=w))})

        pea = P[P["Type"]=="PEA"].groupby("Date", as_index=False).apply(wavg)
        if not pea.empty: pea["Courbe"]="PEA"
        cto = P[P["Type"]=="CTO"].groupby("Date", as_index=False).apply(wavg)
        if not cto.empty: cto["Courbe"]="CTO"
        tot = P.groupby("Date", as_index=False).apply(wavg)
        if not tot.empty: tot["Courbe"]="Total"

        Gp = pd.concat([df for df in [pea, cto, tot] if not df.empty], ignore_index=True)
        if not Gp.empty:
            chp = alt.Chart(Gp).mark_line().encode(
                x=alt.X("Date:T", title=""),
                y=alt.Y("Perf%:Q", title="Rentabilité (%)"),
                color=alt.Color("Courbe:N"),
                tooltip=[alt.Tooltip("Date:T"), "Courbe", "Perf%:Q"]
            ).properties(height=280, title="Performance pondérée (%)")
            st.altair_chart(chp, use_container_width=True)
            charts_drawn = True

    if pnl_rows:
        E = pd.concat(pnl_rows, ignore_index=True)
        if not E.empty:
            En = E.groupby(["Date","Type"], as_index=False)["PnL€"].sum()
            EnTot = En.groupby("Date", as_index=False)["PnL€"].sum().assign(Type="Total")
            G€ = pd.concat([En, EnTot], ignore_index=True)
            chE = alt.Chart(G€).mark_line().encode(
                x=alt.X("Date:T", title=""),
                y=alt.Y("PnL€:Q", title="Gain / Perte (€)"),
                color=alt.Color("Type:N"),
                tooltip=[alt.Tooltip("Date:T"), "Type", "PnL€:Q"]
            ).properties(height=280, title="Gain/Perte cumulés (€)")
            st.altair_chart(chE, use_container_width=True)
            charts_drawn = True

    if not charts_drawn:
        st.caption("Graphes indisponibles : données insuffisantes sur 90 jours.")
