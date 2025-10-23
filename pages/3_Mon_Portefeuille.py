
# -*- coding: utf-8 -*-
import streamlit as st, pandas as pd, numpy as np, altair as alt, os, yfinance as yf
from lib import (fetch_prices, compute_metrics, decision_label_from_row, resolve_identifier,
                 load_mapping, save_mapping, get_profile_params, style_variations, price_levels_from_row, guess_yahoo_from_ls)

st.title("💼 Mon Portefeuille — Unifié (PEA/CTO) + Graphes de rentabilité")

profil = st.session_state.get("profil","Neutre")
volmax = get_profile_params(profil)["vol_max"]
PATH="data/portfolio.json"

if not os.path.exists(PATH):
    pd.DataFrame(columns=["Ticker","Type","Qty","PRU"]).to_json(PATH, orient="records", indent=2, force_ascii=False)

pf = pd.read_json(PATH)

st.subheader("🔁 Convertisseur LS Exchange → Yahoo")
ls = st.text_input("Ticker LS (ex: AIR, ORA, MC, TOTB)").strip().upper()
if ls:
    guess = guess_yahoo_from_ls(ls) or ""
    st.write(f"Proposition : **{guess or '—'}**")
    if st.button("✅ Enregistrer cette correspondance"):
        if guess:
            m = load_mapping(); m[ls] = guess; save_mapping(m)
            st.success(f"Association enregistrée : {ls} → {guess}")
        else:
            st.warning("Aucune proposition valable.")

st.subheader("Ajouter une ligne")
with st.form("add_line"):
    raw_id = st.text_input("Identifiant (Ticker / ISIN / WKN / alias)", placeholder="Ex: AIR.PA ou US0378331005 ou TOTB")
    acc = st.selectbox("Type (compte)", ["PEA","CTO"], index=0)
    qty = st.number_input("Quantité", min_value=0.0, step=1.0, value=0.0)
    pru = st.number_input("PRU (€)", min_value=0.0, step=0.01, value=0.0)
    submitted = st.form_submit_button("Ajouter")
    if submitted:
        tick, _ = resolve_identifier(raw_id)
        if not tick:
            st.warning("Impossible de résoudre automatiquement. Indique le ticker Yahoo :")
            tick = st.text_input("Ticker Yahoo (ex: AIR.PA, NVDA, TTE.PA)", key="manual_add")
        if tick:
            try:
                info = yf.Ticker(tick).get_info()
                name = info.get("shortName") or info.get("longName") or tick
            except Exception:
                name = tick
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
    rows.append({"Type":r.get("Type",""),"Nom":r.get("Name", r.get("Ticker","")), "Ticker":r.get("Ticker",""),
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
        pea = P[P["Type"]=="PEA"].groupby("Date").apply(weighted).reset_index().assign(Courbe="PEA")
        cto = P[P["Type"]=="CTO"].groupby("Date").apply(weighted).reset_index().assign(Courbe="CTO")
        tot = P.groupby("Date").apply(weighted).reset_index().assign(Courbe="Total")
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
