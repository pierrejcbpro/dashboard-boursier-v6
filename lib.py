# -*- coding: utf-8 -*-
"""
lib.py — Bibliothèque centrale du Dashboard Boursier
Version stable compatible v6.9
Inclut :
- Fonctions d’import, recherche, et indicateurs techniques
- Gestion du profil IA
- Surbrillance adaptative clair/sombre
"""

import os, json, math, requests, numpy as np, pandas as pd, yfinance as yf
from functools import lru_cache

# --- Chemins
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

# --- Profils IA
PROFILE_PARAMS = {
    "Agressif": {"vol_max": 0.08, "target_mult": 1.10, "stop_mult": 0.92, "entry_mult": 0.990},
    "Neutre":   {"vol_max": 0.05, "target_mult": 1.07, "stop_mult": 0.95, "entry_mult": 0.990},
    "Prudent":  {"vol_max": 0.03, "target_mult": 1.05, "stop_mult": 0.97, "entry_mult": 0.995},
}

def get_profile_params(profile: str):
    return PROFILE_PARAMS.get(profile or "Neutre", PROFILE_PARAMS["Neutre"])

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

# --- Mapping
def load_mapping():
    try:
        return json.load(open(MAPPING_PATH, "r", encoding="utf-8"))
    except Exception:
        return {}

def save_mapping(m):
    json.dump(m, open(MAPPING_PATH, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

# --- Conversion LS / Yahoo
_PARIS = {"AIR","ORA","MC","TTE","BNP","SGO","ENGI","SU","DG","ACA","GLE","RI","KER","HO","EN","CAP","AI","PUB","VIE","VIV","STM"}

def guess_yahoo_from_ls(ticker: str):
    if not ticker: return None
    t = ticker.strip().upper()
    if "." in t and not t.endswith(".LS"): return t
    if t.endswith(".LS"): return f"{t[:-3]}.L"
    if t == "TOTB": return "TOTB.F"
    if t in _PARIS: return f"{t}.PA"
    if len(t) <= 6 and t.isalpha(): return f"{t}.PA"
    return t

def maybe_guess_yahoo(s):
    s = s.strip().upper()
    m = load_mapping().get(s)
    return m or guess_yahoo_from_ls(s)

def resolve_identifier(id_or_ticker):
    raw = id_or_ticker.strip().upper()
    if not raw: return None, {}
    mapping = load_mapping()
    if raw in mapping: return mapping[raw], {"source": "mapping"}
    guess = maybe_guess_yahoo(raw)
    if guess:
        try:
            hist = yf.download(guess, period="5d", interval="1d", progress=False, threads=False)
            if not hist.empty:
                mapping[raw] = guess
                save_mapping(mapping)
                return guess, {"source": "heuristic"}
        except Exception:
            pass
    return None, {}

# --- Téléchargement prix et calculs
@lru_cache(maxsize=256)
def fetch_prices_cached(tickers_tuple, period="120d"):
    tickers = list(tickers_tuple)
    if not tickers: return pd.DataFrame()
    try:
        data = yf.download(tickers, period=period, interval="1d", group_by="ticker", threads=False, progress=False)
    except Exception:
        return pd.DataFrame()
    frames = []
    if isinstance(data, pd.DataFrame) and {"Open","High","Low","Close"}.issubset(data.columns):
        df = data.copy(); df["Ticker"] = tickers[0]; frames.append(df)
    else:
        for t in tickers:
            if t in data and isinstance(data[t], pd.DataFrame):
                df = data[t].copy(); df["Ticker"] = t; frames.append(df)
    if not frames: return pd.DataFrame()
    out = pd.concat(frames)
    out.reset_index(inplace=True)
    return out

def fetch_prices(tickers, days=120):
    return fetch_prices_cached(tuple(tickers), period=f"{days}d")

def compute_metrics(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty: return pd.DataFrame()
    df = df.copy()
    if "Date" not in df.columns:
        df = df.reset_index().rename(columns={df.index.name or "index": "Date"})
    df = df.sort_values(["Ticker", "Date"])
    df["PrevClose"] = df.groupby("Ticker")["Close"].shift(1)
    df["TR"] = np.maximum(df["High"] - df["Low"], np.maximum((df["High"] - df["PrevClose"]).abs(), (df["Low"] - df["PrevClose"]).abs()))
    df["ATR14"] = df.groupby("Ticker")["TR"].transform(lambda s: s.rolling(14, min_periods=5).mean())
    df["MA20"] = df.groupby("Ticker")["Close"].transform(lambda s: s.rolling(20, min_periods=5).mean())
    df["MA50"] = df.groupby("Ticker")["Close"].transform(lambda s: s.rolling(50, min_periods=10).mean())
    last = df.groupby("Ticker").tail(1)[["Ticker","Date","Close","ATR14","MA20","MA50"]]
    last["gap20"] = (last["Close"]/last["MA20"]-1).where(last["MA20"].notna())
    last["gap50"] = (last["Close"]/last["MA50"]-1).where(last["MA50"].notna())
    last["trend_score"] = 0.6*last["gap20"] + 0.4*last["gap50"]
    return last.reset_index(drop=True)

# --- Décision IA
def decision_label_from_row(row, held=False, vol_max=0.05):
    px = row.get("Close", np.nan)
    ma20, ma50, atr = row.get("MA20", np.nan), row.get("MA50", np.nan), row.get("ATR14", np.nan)
    pru = row.get("PRU", np.nan)
    if not np.isfinite(px): return "👁️ Surveiller"
    vol = (atr/px) if (np.isfinite(atr) and px>0) else 0.03
    trend = sum([px >= ma20 if np.isfinite(ma20) else False,
                 px >= ma50 if np.isfinite(ma50) else False])
    score = 0.5*(1 if trend==2 else 0 if trend==1 else -1)
    if np.isfinite(pru) and pru>0: score += 0.2*(1 if px>pru*1.02 else -1 if px<pru*0.98 else 0)
    score += 0.3*(-1 if vol>vol_max else 1)
    if held:
        if score>0.5: return "🟢 Acheter"
        if score<-0.2: return "🔴 Vendre"
        return "🟠 Garder"
    else:
        if score>0.3: return "🟢 Acheter"
        if score<-0.2: return "🚫 Éviter"
        return "👁️ Surveiller"

def price_levels_from_row(row, profile="Neutre"):
    p = get_profile_params(profile)
    px, ma20 = row.get("Close", np.nan), row.get("MA20", np.nan)
    base = ma20 if np.isfinite(ma20) else px
    if not np.isfinite(base): return {"entry": np.nan, "target": np.nan, "stop": np.nan}
    return {"entry": round(base*p["entry_mult"],2), "target": round(base*p["target_mult"],2), "stop": round(base*p["stop_mult"],2)}

# --- Styles adaptatifs clair/sombre
def detect_dark_mode():
    try:
        import streamlit as st
        base = (st.get_option("theme.base") or "").lower()
        return "dark" in base
    except Exception:
        return False

def highlight_near_entry_adaptive(row, col="Proximité (%)"):
    dark = detect_dark_mode()
    bg = "rgba(0,255,200,0.15)" if dark else "#fff9c4"
    if pd.notna(row.get(col)) and abs(row.get(col)) <= 2:
        return [f"background-color:{bg}; font-weight:600"] * len(row)
    return [""] * len(row)

def color_proximity_adaptive(v):
    if pd.isna(v): return ""
    dark = detect_dark_mode()
    if abs(v) <= 2:
        return "background-color:rgba(0,255,150,0.2); color:#00ffcc" if dark else "background-color:#e6f4ea; color:#0b8043"
    if abs(v) <= 5:
        return "background-color:rgba(255,255,150,0.15); color:#ffeb3b" if dark else "background-color:#fff8e1; color:#a67c00"
    return "background-color:rgba(255,0,0,0.15); color:#ff6666" if dark else "background-color:#ffebee; color:#b71c1c"
