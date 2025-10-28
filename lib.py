# -*- coding: utf-8 -*-
"""
v7.0 — Library (lib.py)
- Cohérente avec Synthèse Flash + Portefeuille + Recherche
- Ajout des variations pct_1d / pct_7d / pct_30d
- fetch_all_markets multi-index (CAC, DAX, S&P, NASDAQ, LS Exchange)
- Amélioration stabilité et cohérence avec MA20 / MA50 / IA
"""

import os, json, math, requests, numpy as np, pandas as pd, yfinance as yf
from functools import lru_cache
import nltk
from nltk.sentiment import SentimentIntensityAnalyzer

# -------------------------------------------------------------------
# 📁 Setup
# -------------------------------------------------------------------
DATA_DIR = "data"
MAPPING_PATH = os.path.join(DATA_DIR, "id_mapping.json")
WL_PATH = os.path.join(DATA_DIR, "watchlist_ls.json")
PROFILE_PATH = os.path.join(DATA_DIR, "profile.json")
LAST_SEARCH_PATH = os.path.join(DATA_DIR, "last_search.json")

for p in [DATA_DIR]:
    os.makedirs(p, exist_ok=True)

for p, default in [
    (MAPPING_PATH, {}),
    (WL_PATH, []),
    (PROFILE_PATH, {"profil": "Neutre"}),
    (LAST_SEARCH_PATH, {"last": "TTE.PA"}),
]:
    if not os.path.exists(p):
        with open(p, "w", encoding="utf-8") as f:
            json.dump(default, f)

UA = {"User-Agent": "Mozilla/5.0"}

# -------------------------------------------------------------------
# 🧠 Sentiment Analyzer
# -------------------------------------------------------------------
try:
    nltk.data.find("sentiment/vader_lexicon.zip")
except LookupError:
    try:
        nltk.download("vader_lexicon")
    except Exception:
        pass
try:
    SIA = SentimentIntensityAnalyzer()
except Exception:
    SIA = None

# -------------------------------------------------------------------
# ⚙️ Profil IA
# -------------------------------------------------------------------
PROFILE_PARAMS = {
    "Agressif": {"vol_max": 0.08, "target_mult": 1.10, "stop_mult": 0.92, "entry_mult": 0.990},
    "Neutre":   {"vol_max": 0.05, "target_mult": 1.07, "stop_mult": 0.95, "entry_mult": 0.990},
    "Prudent":  {"vol_max": 0.03, "target_mult": 1.05, "stop_mult": 0.97, "entry_mult": 0.995},
}
def get_profile_params(profile: str):
    return PROFILE_PARAMS.get(profile or "Neutre", PROFILE_PARAMS["Neutre"])

# -------------------------------------------------------------------
# 📦 Profils / Watchlist / Mapping / Recherche
# -------------------------------------------------------------------
def load_profile():
    try:
        return json.load(open(PROFILE_PATH, "r", encoding="utf-8")).get("profil", "Neutre")
    except Exception:
        return "Neutre"
def save_profile(p):
    try:
        json.dump({"profil": p}, open(PROFILE_PATH, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    except Exception:
        pass

def load_last_search():
    try:
        return json.load(open(LAST_SEARCH_PATH, "r", encoding="utf-8")).get("last", "")
    except Exception:
        return ""
def save_last_search(t):
    try:
        json.dump({"last": t}, open(LAST_SEARCH_PATH, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    except Exception:
        pass

def load_mapping():
    try:
        return json.load(open(MAPPING_PATH, "r", encoding="utf-8"))
    except Exception:
        return {}
def save_mapping(m):
    json.dump(m, open(MAPPING_PATH, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

def load_watchlist_ls():
    try:
        return json.load(open(WL_PATH, "r", encoding="utf-8"))
    except Exception:
        return []
def save_watchlist_ls(lst):
    json.dump(lst, open(WL_PATH, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

# -------------------------------------------------------------------
# 🔄 Conversion ticker LS → Yahoo
# -------------------------------------------------------------------
def _norm(s): return (s or "").strip().upper()

_PARIS = {"AIR","ORA","MC","TTE","BNP","SGO","ENGI","SU","DG","ACA","GLE","RI","KER","HO","EN","CAP","AI","PUB","VIE","VIV","STM"}
def guess_yahoo_from_ls(ticker: str):
    if not ticker: return None
    t = _norm(ticker)
    if "." in t and not t.endswith(".LS"): return t
    if t.endswith(".LS"): return f"{t[:-3]}.L"
    if t == "TOTB": return "TOTB.F"
    if t.endswith("B") and not t.endswith("AB"): return f"{t}.F"
    if t in _PARIS: return f"{t}.PA"
    if len(t) <= 6 and t.isalpha(): return f"{t}.PA"
    return t

def maybe_guess_yahoo(s):
    s = _norm(s)
    m = load_mapping().get(s)
    return m or guess_yahoo_from_ls(s)

# -------------------------------------------------------------------
# 🔎 Recherche Yahoo Finance
# -------------------------------------------------------------------
@lru_cache(maxsize=256)
def yahoo_search(query: str, region="FR", lang="fr-FR", quotesCount=20):
    url = "https://query2.finance.yahoo.com/v1/finance/search"
    params = {"q": query, "quotesCount": quotesCount, "newsCount": 0, "lang": lang, "region": region}
    try:
        r = requests.get(url, params=params, headers=UA, timeout=12)
        r.raise_for_status()
        data = r.json()
        quotes = data.get("quotes", [])
        out = []
        for q in quotes:
            out.append({
                "symbol": q.get("symbol"),
                "shortname": q.get("shortname") or q.get("longname") or "",
                "longname": q.get("longname") or q.get("shortname") or "",
                "exchDisp": q.get("exchDisp") or "",
                "typeDisp": q.get("typeDisp") or "",
            })
        return out
    except Exception:
        return []

def find_ticker_by_name(company_name: str, prefer_markets=("Paris","XETRA","Frankfurt","NasdaqGS","NYSE")):
    if not company_name: return []
    q = company_name.strip()
    res = yahoo_search(q)
    if not res: return []
    eq = [r for r in res if (r.get("typeDisp","").lower() in ("equity","action","stock","actions") or r.get("symbol",""))]
    ranked=[]
    for r in eq:
        score = 0
        exch = (r.get("exchDisp") or "").lower()
        name = (r.get("shortname") or r.get("longname") or "").lower()
        sym = (r.get("symbol") or "").upper()
        if any(pm.lower() in exch for pm in prefer_markets): score += 3
        if q.lower() in name: score += 2
        if q.lower() in sym.lower(): score += 1
        ranked.append((score, r))
    ranked.sort(key=lambda x: x[0], reverse=True)
    return [r for _, r in ranked]

# -------------------------------------------------------------------
# 📈 Téléchargement des cours et métriques
# -------------------------------------------------------------------
@lru_cache(maxsize=64)
def fetch_prices_cached(tickers_tuple, period="120d"):
    tickers = list(tickers_tuple)
    if not tickers: return pd.DataFrame()
    try:
        data = yf.download(tickers, period=period, interval="1d",
                           auto_adjust=False, group_by="ticker",
                           threads=False, progress=False)
    except Exception:
        return pd.DataFrame()

    if data is None or len(data) == 0:
        return pd.DataFrame()

    frames = []
    if isinstance(data, pd.DataFrame) and {"Open","High","Low","Close"}.issubset(data.columns):
        df = data.copy()
        df["Ticker"] = tickers[0]
        frames.append(df)
    else:
        for t in tickers:
            try:
                if t in data and isinstance(data[t], pd.DataFrame):
                    df = data[t].copy()
                    df["Ticker"] = t
                    frames.append(df)
            except Exception:
                continue
    if not frames:
        return pd.DataFrame()
    out = pd.concat(frames)
    out.reset_index(inplace=True)
    return out

def fetch_prices(tickers, days=120):
    return fetch_prices_cached(tuple(tickers), period=f"{days}d")

# -------------------------------------------------------------------
# 🧮 Calcul des indicateurs techniques
# -------------------------------------------------------------------
def compute_metrics(df: pd.DataFrame) -> pd.DataFrame:
    cols = ["Ticker","Date","Close","ATR14","MA20","MA50","gap20","gap50","trend_score","pct_1d","pct_7d","pct_30d"]
    if df is None or df.empty:
        return pd.DataFrame(columns=cols)

    df = df.copy()
    if "Date" not in df.columns:
        df = df.reset_index().rename(columns={df.index.name or "index": "Date"})
    need = {"Ticker","Date","High","Low","Close"}
    if need - set(df.columns):
        return pd.DataFrame(columns=cols)

    df = df.sort_values(["Ticker","Date"])
    df["PrevClose"] = df.groupby("Ticker")["Close"].shift(1)
    df["TR"] = np.maximum(df["High"]-df["Low"],
                np.maximum((df["High"]-df["PrevClose"]).abs(), (df["Low"]-df["PrevClose"]).abs()))
    df["ATR14"] = df.groupby("Ticker")["TR"].transform(lambda s: s.rolling(14,min_periods=5).mean())
    df["MA20"] = df.groupby("Ticker")["Close"].transform(lambda s: s.rolling(20,min_periods=5).mean())
    df["MA50"] = df.groupby("Ticker")["Close"].transform(lambda s: s.rolling(50,min_periods=10).mean())

    # Ajout variations (1j / 7j / 30j)
    df["pct_1d"] = df.groupby("Ticker")["Close"].pct_change(1)
    df["pct_7d"] = df.groupby("Ticker")["Close"].pct_change(7)
    df["pct_30d"] = df.groupby("Ticker")["Close"].pct_change(30)

    last = df.groupby("Ticker").tail(1)[["Ticker","Date","Close","ATR14","MA20","MA50","pct_1d","pct_7d","pct_30d"]].copy()
    last["gap20"] = last.apply(lambda r: (r["Close"]/r["MA20"]-1) if (not np.isnan(r["MA20"]) and r["MA20"]!=0) else np.nan, axis=1)
    last["gap50"] = last.apply(lambda r: (r["Close"]/r["MA50"]-1) if (not np.isnan(r["MA50"]) and r["MA50"]!=0) else np.nan, axis=1)
    last["trend_score"] = 0.6*last["gap20"] + 0.4*last["gap50"]
    return last.reset_index(drop=True)

# -------------------------------------------------------------------
# 🌍 Agrégation des marchés (multi-indices)
# -------------------------------------------------------------------
def members(index_name: str):
    index_urls = {
        "CAC 40": "https://en.wikipedia.org/wiki/CAC_40",
        "DAX 40": "https://en.wikipedia.org/wiki/DAX",
        "S&P 500": "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies",
        "NASDAQ 100": "https://en.wikipedia.org/wiki/Nasdaq-100",
    }
    url = index_urls.get(index_name)
    if not url:
        return pd.DataFrame(columns=["ticker","name","index"])
    try:
        html = requests.get(url, headers=UA, timeout=20).text
        tables = pd.read_html(html)
        df = None
        for t in tables:
            cols = {str(c).lower() for c in t.columns}
            if any("symbol" in c or "ticker" in c for c in cols):
                df = t
                break
        if df is None:
            df = tables[0]
        df.columns = [str(c).lower() for c in df.columns]
        tcol = next((c for c in df.columns if "symbol" in c or "ticker" in c), df.columns[0])
        ncol = next((c for c in df.columns if "company" in c or "name" in c), df.columns[1])
        out = df[[tcol, ncol]].copy()
        out.columns = ["ticker", "name"]
        out["ticker"] = out["ticker"].astype(str).str.strip()
        out["index"] = index_name
        if index_name in ("CAC 40", "DAX 40"):
            out["ticker"] = out["ticker"].apply(lambda x: guess_yahoo_from_ls(x))
        return out.dropna().drop_duplicates(subset=["ticker"])
    except Exception:
        return pd.DataFrame(columns=["ticker","name","index"])

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
        px = fetch_prices(mem["ticker"].tolist(), days=days_hist)
        if px.empty:
            continue
        met = compute_metrics(px).merge(mem, left_on="Ticker", right_on="ticker", how="left")
        met["Indice"] = idx
        frames.append(met)
    return pd.concat(frames, ignore_index=True, sort=False) if frames else pd.DataFrame()
