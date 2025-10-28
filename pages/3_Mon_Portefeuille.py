
# -*- coding: utf-8 -*-
"""
v6.4 — Mon Portefeuille (avancé et complet)
- Tableau éditable (ajout/modif/suppression)
- Export / Import JSON (multi-appareils)
- Convertisseur LS Exchange -> Yahoo + mapping
- Recherche par nom / ISIN / WKN / Ticker
- Niveaux Entrée / Objectif / Stop + Décision IA (pastilles)
- Graphiques de performance pondérée (%) et PnL (€) PEA/CTO/Total
- Affichage des valeurs € et % dans les infobulles
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
# Sauvegarde locale du portefeuille
# ---------------------------------------------------------
DATA_PATH = "data/portfolio.json"
os.makedirs("data", exist_ok=True)

if not os.path.exists(DATA_PATH):
    pd.DataFrame(columns=["Ticker","Type","Qty","PRU","Name"]).to_json(
        DATA_PATH, orient="records", indent=2, force_ascii=False
    )

try:
    pf = pd.read_json(DATA_PATH)
except Exception:
    pf = pd.DataFrame(columns=["Ticker","Type","Qty","PRU","Name"])

for c, default in [("Ticker",""),("Type","PEA"),("Qty",0.0),("PRU",0.0),("Name","")]:
    if c not in pf.columns:
        pf[c] = default

# Remplir automatiquement le Nom si manquant
mask_missing_name = pf["Name"].isna() | (pf["Name"].astype(str).str.strip() == "")
if mask_missing_name.any():
    pf.loc[mask_missing_name, "Name"] = pf.loc[mask_missing_name, "Ticker"].apply(company_name_from_ticker)
    pf.to_json(DATA_PATH, orient="records", indent=2, force_ascii=False)

# ---------------------------------------------------------
# Barre d’outils : Sauvegarde / Reset / Export / Import
# ---------------------------------------------------------
c_tools = st.columns([1,1,1,1])
with c_tools[0]:
    if st.button("💾 Sauvegarder"):
        pf.to_json(DATA_PATH, orient="records", indent=2, force_ascii=False)
        st.success("✅ Portefeuille sauvegardé.")
with c_tools[1]:
    if st.button("🗑 Réinitialiser"):
        try:
            os.remove(DATA_PATH)
        except:
            pass
        pd.DataFrame(columns=["Ticker","Type","Qty","PRU","Name"]).to_json(
            DATA_PATH, orient="records", indent=2, force_ascii=False
        )
        st.success("♻️ Réinitialisé.")
        st.rerun()
with c_tools[2]:
    data_json = json.dumps(pf.to_dict(orient="records"), ensure_ascii=False, indent=2)
    st.download_button("⬇️ Export JSON", data_json, file_name="portfolio.json", mime="application/json")
with c_tools[3]:
    up = st.file_uploader("📥 Import JSON", type=["json"], label_visibility="collapsed")
    if up is not None:
        try:
            imported = pd.DataFrame(json.load(up))
            # normalise colonnes
            for c in ["Ticker","Type","Qty","PRU","Name"]:
                if c not in imported.columns:
                    imported[c] = "" if c in ("Ticker","Type","Name") else 0.0
            imported["Ticker"] = imported["Ticker"].astype(str).str.upper()
            imported.to_json(DATA_PATH, orient="records", indent=2, force_ascii=False)
            st.success("✅ Import réussi.")
            st.rerun()
        except Exception as e:
            st.error(f"Erreur import : {e}")

st.caption("💡 Astuce : utilise **Export/Import JSON** pour synchroniser ton portefeuille entre appareils.")
st.divider()

# ---------------------------------------------------------
# Convertisseur LS Exchange -> Yahoo (mapping)
# ---------------------------------------------------------
with st.expander("🔁 Convertisseur LS Exchange → Yahoo"):
    col1, col2, col3 = st.columns([1.3,1,1])
    with col1:
        ls_in = st.text_input("Ticker LS Exchange (ex: TOTB, AIR, ORA, VOW3)", value="")
    with col2:
        if st.button("🔍 Convertir"):
            if not ls_in.strip():
                st.warning("Entre un ticker LS Exchange.")
            else:
                guess = maybe_guess_yahoo(ls_in)
                if guess:
                    st.session_state["conv_guess"] = (ls_in.upper(), guess)
                    st.success(f"➡️ Proposition : {ls_in.upper()} → {guess}")
                else:
                    st.warning("Aucune correspondance trouvée.")
    with col3:
        if st.button("✅ Enregistrer"):
            tup = st.session_state.get("conv_guess")
            if not tup:
                st.warning("Fais d'abord une conversion.")
            else:
                src, sym = tup
                m = load_mapping()
                m[src] = sym
                save_mapping(m)
                st.success(f"✅ Ajouté : {src} → {sym}")

# ---------------------------------------------------------
# Recherche par nom / ISIN / WKN / Ticker
# ---------------------------------------------------------
with st.expander("🔎 Recherche & ajout par nom / ISIN / WKN / Ticker"):
    q = st.text_input("Nom, ISIN, WKN ou Ticker", value="")
    add_type = st.selectbox("Type de compte", ["PEA","CTO"], index=0)
    add_qty = st.number_input("Quantité", min_value=0.0, step=1.0, value=0.0)

    if st.button("Rechercher"):
        if not q.strip():
            st.warning("Renseigne un nom ou un identifiant.")
        else:
            sym, meta = resolve_identifier(q)
            if not sym:
                cands = find_ticker_by_name(q)
                st.session_state["search_candidates"] = cands or []
            else:
                st.session_state["search_candidates"] = [{"symbol": sym, "shortname": company_name_from_ticker(sym)}]

    candidates = st.session_state.get("search_candidates", [])
    if candidates:
        labels = [f"{c.get('symbol','?')} — {c.get('shortname','')}" for c in candidates]
        sel = st.selectbox("Résultats trouvés", labels)
        if st.button("➕ Ajouter au portefeuille"):
            idx = labels.index(sel)
            sym = candidates[idx]["symbol"]
            name = candidates[idx].get("shortname") or company_name_from_ticker(sym)
            new_row = {"Ticker": sym.upper(), "Type": add_type, "Qty": add_qty, "PRU": 0.0, "Name": name}
            pf = pd.concat([pf, pd.DataFrame([new_row])], ignore_index=True)
            pf.to_json(DATA_PATH, orient="records", indent=2, force_ascii=False)
            st.success(f"✅ Ajouté : {name} ({sym})")
            st.rerun()

st.divider()

# ---------------------------------------------------------
# Ajout rapide
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
# Tableau principal éditable
# ---------------------------------------------------------
st.subheader("📝 Mon Portefeuille")
edited = st.data_editor(
    pf,
    num_rows="dynamic",
    use_container_width=True,
    hide_index=True,
    column_config={
        "Ticker": st.column_config.TextColumn("Ticker", help="ex: AIR.PA, TTE.PA, NVDA"),
        "Type": st.column_config.SelectboxColumn("Type", options=["PEA","CTO"]),
        "Qty": st.column_config.NumberColumn("Qté", format="%.2f"),
        "PRU": st.column_config.NumberColumn("PRU (€)", format="%.4f"),
        "Name": st.column_config.TextColumn("Nom de la société")
    },
    key="pf_editor"
)

c_save, c_refresh = st.columns([1,1])
with c_save:
    if st.button("💾 Enregistrer les modifications"):
        edited["Ticker"] = edited["Ticker"].astype(str).str.upper()
        # Remplit Name si vide
        need_name = edited["Name"].isna() | (edited["Name"].astype(str).str.strip()=="")
        edited.loc[need_name, "Name"] = edited.loc[need_name, "Ticker"].apply(company_name_from_ticker)
        edited.to_json(DATA_PATH, orient="records", indent=2, force_ascii=False)
        st.success("✅ Modifications sauvegardées.")
        st.rerun()
with c_refresh:
    if st.button("🔄 Rafraîchir données (prix & indicateurs)"):
        st.cache_data.clear()
        st.rerun()

if edited.empty:
    st.info("Ajoute au moins une ligne puis sauvegarde.")
    st.stop()

# ---------------------------------------------------------
# Données & Analyse IA
# ---------------------------------------------------------
tickers = edited["Ticker"].dropna().astype(str).str.upper().unique().tolist()
hist = fetch_prices(tickers, days=120)
met = compute_metrics(hist)
merged = edited.merge(met, on="Ticker", how="left")

profil = st.session_state.get("profil", "Neutre")
volmax = get_profile_params(profil)["vol_max"]

rows = []
for _, r in merged.iterrows():
    name = r.get("Name") or company_name_from_ticker(r.get("Ticker",""))
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
        "PRU (€)": round(pru,2) if np.isfinite(pru) else None,
        "Valeur (€)": round(val,2) if np.isfinite(val) else None,
        "Perf%": round(perf,2) if np.isfinite(perf) else None,
        "Entrée (€)": levels["entry"],
        "Objectif (€)": levels["target"],
        "Stop (€)": levels["stop"],
        "Décision IA": dec
    })

out = pd.DataFrame(rows)
st.subheader("📋 Synthèse positions (IA intégrée)")
st.dataframe(style_variations(out, ["Perf%"]), use_container_width=True, hide_index=True)

# ---------------------------------------------------------
# Graphiques performance & PnL (90 jours) + tooltips explicites
# ---------------------------------------------------------
st.subheader("📈 Évolution du portefeuille (90 jours)")

hist90 = fetch_prices(tickers, days=100)
if hist90.empty or "Date" not in hist90.columns:
    st.caption("Pas assez d'historique pour générer les graphes.")
else:
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
        # Poids = valeur courante (pour moyenne pondérée)
        last_px = d["Close"].iloc[-1]
        d["Poids"] = last_px * qty
        perf_rows.append(d[["Date","Perf%","Type","Poids"]])
        pnl_rows.append(d[["Date","PnL€","Type"]])

    charts_drawn = False

    if perf_rows:
        P = pd.concat(perf_rows, ignore_index=True)
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
                tooltip=[alt.Tooltip("Date:T"), "Courbe:N", alt.Tooltip("Perf%:Q", format=".2f")]
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
                tooltip=[alt.Tooltip("Date:T"), "Type:N", alt.Tooltip("PnL€:Q", format=".2f")]
            ).properties(height=280, title="Gain/Perte cumulés (€)")
            st.altair_chart(chE, use_container_width=True)
            charts_drawn = True

    if not charts_drawn:
        st.caption("Graphes indisponibles : données insuffisantes sur 90 jours.")
