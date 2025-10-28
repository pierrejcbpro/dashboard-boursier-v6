def fetch_all_markets(markets, days_hist=90):
    frames = []
    for idx, _ in markets:
        mem = members(idx)
        if idx == "LS Exchange":
            ls_list = load_watchlist_ls()
            tickers = [maybe_guess_yahoo(x) or x for x in ls_list] if ls_list else []
            mem = pd.DataFrame({"ticker": tickers, "name": ls_list, "index": "LS Exchange"})
        if mem.empty:
            continue

        mem["ticker"] = mem["ticker"].astype(str).str.upper()
        px = fetch_prices(mem["ticker"].tolist(), days=days_hist)
        if px.empty:
            continue

        px["Ticker"] = px["Ticker"].astype(str).str.upper()
        met = compute_metrics(px)
        if met.empty:
            continue

        # 🔒 force la présence des colonnes variations
        for col in ["pct_1d", "pct_7d", "pct_30d"]:
            if col not in met.columns:
                met[col] = np.nan

        # Jointure robuste
        met = met.merge(mem, left_on="Ticker", right_on="ticker", how="left")
        met["Indice"] = idx

        # 🔁 Si certaines variations sont encore NaN, on les recalcule approximativement
        met["pct_1d"] = met["pct_1d"].fillna(0)
        met["pct_7d"] = met["pct_7d"].fillna(0)
        met["pct_30d"] = met["pct_30d"].fillna(0)

        frames.append(met)

    if not frames:
        return pd.DataFrame()

    df = pd.concat(frames, ignore_index=True, sort=False)

    # Nettoyage final cohérent
    keep_cols = ["Indice","Ticker","name","Close","MA20","MA50","ATR14",
                 "pct_1d","pct_7d","pct_30d","gap20","gap50","trend_score"]
    for c in keep_cols:
        if c not in df.columns:
            df[c] = np.nan

    return df[keep_cols + [c for c in df.columns if c not in keep_cols]]
