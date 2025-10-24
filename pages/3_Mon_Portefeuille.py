# -*- coding: utf-8 -*-
import streamlit as st, pandas as pd, numpy as np, altair as alt, os
from lib import (fetch_prices, compute_metrics, decision_label_from_row, resolve_identifier,
                 load_mapping, save_mapping, get_profile_params, style_variations, price_levels_from_row,
                 guess_yahoo_from_ls, company_name_from_ticker, find_ticker_by_name)

st.title("💼 Mon Portefeuille — Unifié (PEA/CTO) + Graphes de rentabilité + 🔎 Recherche par nom")

profil = st.session_state.get("profil","Neutre")
volmax = get_profile_params(profil)["vol_max"]
PATH="data/portfolio.json"

if not os.path.exists(PATH):
    pd.DataFrame(columns=["Ticker","Type","Qty","PRU"]).to_json(PATH, orient="records", indent=2, force_ascii=False)

pf = pd.read_json(PATH)

if "Name" not in pf.columns:
    pf["Name"] = ""
missing = pf["Name"].isna() | (pf["Name"].astype(str).str.strip() == "")
if missing.any():
    pf.loc[missing, "Name"] = pf.loc[missing, "Ticker"].apply(company_name_from_ticker)
    pf.to_json(PATH, orient="records", indent=2, force_ascii=False)

with st.expander("🔎 Rechercher un titre par nom (suggestions Yahoo)", expanded=False):
    q = st.text_input("Nom de l'entreprise (ex: TotalEnergies, Airbus, LVMH)")
    if st.button("Rechercher"):
        cands = find_ticker_by_name(q)
        if not cands:
            st.warning("Aucune correspondance trouvée.")
        else:
            opt = [f"{c['symbol']} — {c['shortname']} ({c['exchDisp']})" for c in cands]
            sel = st.selectbox("Choisis le bon titre", opt, index=0)
            if st.button("✅ Utiliser cette valeur"):
                idx = opt.index(sel)
                sym = cands[idx]["symbol"]
                m=load_mapping(); m[q.upper()] = sym; save_mapping(m)
                st.success(f"Ajouté au mapping : {q} → {sym}")

st.subheader("Ajouter une ligne")
with st.form("add_line"):
    raw_id = st.text_input("Identifiant (Nom / Ticker / ISIN / WKN / alias)", placeholder="Ex: TotalEnergies ou AIR.PA ou US0378331005")
    acc = st.selectbox("Type (compte)", ["PEA","CTO"], index=0)
    qty = st.number_input("Quantité", min_value=0.0, step=1.0, value=0.0)
    pru = st.number_input("PRU (€)", min_value=0.0, step=0.01, value=0.0)
    submitted = st.form_submit_button("Ajouter")
    if submitted:
        tick, _ = resolve_identifier(raw_id)
        if not tick:
            cands = find_ticker_by_name(raw_id)
            if cands:
                tick = cands[0]["symbol"]
                m=load_mapping(); m[raw_id.upper()] = tick; save_mapping(m)
        if not tick:
            st.warning("Impossible de trouver automatiquement. Indique le ticker Yahoo :")
            tick = st.text_input("Ticker Yahoo (ex: AIR.PA, NVDA, TTE.PA)", key="manual_add")
        if tick:
            name = company_name_from_ticker(tick)
            new = {"Ticker":tick.upper(),"Type":acc,"Qty":qty,"PRU":pru,"Name":name}
            pf = pd.concat([pf, pd.DataFrame([new])], ignore_index=True)
            pf.to_json(PATH, orient="records", indent=2, force_ascii=False)
            st.success(f"Ajouté : {name} ({tick})")

st.subheader("Éditer mon portefeuille")
edited = st.data_editor(pf, num_rows="dynamic", use_container_width=True, key="pf_editor")

c1,c2,c3 = st.columns(3)
with c1:
    if st.button("💾 Sauvegarder"):
        edited.to_json(PATH, orient="records", indent=2, force_ascii=False)
        st.success("Sauvegardé.")
with c2:
    if st.button("🗑 Réinitialiser"):
        if os.path.exists(PATH): os.remove(PATH)
        st.rerun()
with c3:
    if st.button("🔄 Rafraîchir données"):
        st.cache_data.clear(); st.rerun()

if edited.empty:
    st.info("Ajoutez des lignes (Ticker requis)."); st.stop()

tickers = edited["Ticker"].dropna().unique().tolist()
hist = fetch_prices(tickers, days=120)
met = compute_metrics(hist)
merged = edited.merge(met, on="Ticker", how="left")

rows=[]
for _,r in merged.iterrows():
    px=float(r.get("Close", np.nan)); q=float(r.get("Qty",0) or 0); pru=float(r.get("PRU", np.nan) or np.nan)
    levels = price_levels_from_row(r, profil)
    val = (px*q) if np.isfinite(px) else 0.0
    perf = ((px/pru)-1)*100 if (np.isfinite(px) and np.isfinite(pru) and pru>0) else np.nan
    dec = decision_label_from_row(r, held=True, vol_max=volmax)
    rows.append({"Type":r.get("Type",""),"Nom":r.get("Name") or company_name_from_ticker(r.get("Ticker","")) or r.get("Ticker",""),
                 "Ticker":r.get("Ticker",""),
                 "Cours":round(px,2) if np.isfinite(px) else None, "PRU":pru, "Qté":q, "Valeur":round(val,2),
                 "Perf%":round(perf,2) if np.isfinite(perf) else None,
                 "Entrée (€)":levels["entry"], "Objectif (€)":levels["target"], "Stop (€)":levels["stop"],
                 "Décision IA":dec})
out=pd.DataFrame(rows)
st.subheader("Vue portefeuille")
st.dataframe(style_variations(out, ["Perf%"]), use_container_width=True, hide_index=True)

st.subheader("📈 Rentabilité 90 jours — PEA / CTO / Total")
hist90 = fetch_prices(tickers, days=100)
if not hist90.empty and "Date" in hist90.columns:
    perf_rows=[]
    for _, pos in edited.iterrows():
        t = pos.get("Ticker"); typ = pos.get("Type"); pru = pos.get("PRU")
        if not t or not np.isfinite(pru) or pru<=0: continue
        d = hist90[hist90["Ticker"]==t].copy()
        if d.empty: continue
        d = d[["Date","Close"]].copy()
        d["Perf%"] = (d["Close"]/pru - 1)*100.0
        d["Type"] = typ
        d["Ticker"] = t
        try:
            last_px = d["Close"].iloc[-1]; qty = float(edited.loc[edited["Ticker"]==t, "Qty"].iloc[0] or 0)
            d["Poids"] = last_px*qty
        except Exception:
            d["Poids"] = 1.0
        perf_rows.append(d)
    if perf_rows:
        P = pd.concat(perf_rows, ignore_index=True)
        def weighted(group):
            w = group["Poids"].replace(0, np.nan)
            if w.isna().all(): return pd.Series({"Perf%": np.nan})
            return pd.Series({"Perf%": (group["Perf%"]*w/w.sum()).sum()})
        pea = (P[P["Type"]=="PEA"].groupby("Date", as_index=False).apply(weighted)
               .assign(Courbe="PEA").reset_index(drop=True))
        cto = (P[P["Type"]=="CTO"].groupby("Date", as_index=False).apply(weighted)
               .assign(Courbe="CTO").reset_index(drop=True))
        tot = (P.groupby("Date", as_index=False).apply(weighted)
               .assign(Courbe="Total").reset_index(drop=True))
        G = pd.concat([pea, cto, tot], ignore_index=True)
        ch = alt.Chart(G).mark_line().encode(
            x=alt.X("Date:T", title=""),
            y=alt.Y("Perf%:Q", title="Rentabilité (%)"),
            color=alt.Color("Courbe:N", scale=alt.Scale(domain=["PEA","CTO","Total"])),
            tooltip=[alt.Tooltip("Date:T"), "Courbe","Perf%:Q"]
        ).properties(height=360)
        st.altair_chart(ch, use_container_width=True)
    else:
        st.caption("Pas assez de données pour construire le graphe.")
else:
    st.caption("Historique indisponible.")
