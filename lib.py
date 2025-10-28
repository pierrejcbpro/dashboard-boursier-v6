# -*- coding: utf-8 -*-
import os, json, math, requests, numpy as np, pandas as pd, yfinance as yf
from functools import lru_cache
import nltk
from nltk.sentiment import SentimentIntensityAnalyzer

# =========================
# FICHIERS & PRESETS
# =========================
DATA_DIR = "data"
MAPPING_PATH = os.path.join(DATA_DIR, "id_mapping.json")
WL_PATH = os.path.join(DATA_DIR, "watchlist_ls.json")
PROFILE_PATH = os.path.join(DATA_DIR, "profile.json")
LAST_SEARCH_PATH = os.path.join(DATA_DIR, "last_search.json")

os.makedirs(DATA_DIR, exist_ok=True)
_defaults = [
    (MAPPING_PATH, {}),
    (WL_PATH, []),
    (PROFILE_PATH, {"profil": "Neutre"}),
    (LAST_SEARCH_PATH, {"last": "TTE.PA"}),
]
for p, default in _defaults:
    if not os.path.exists(p):
        with open(p, "w", encoding="utf-8") as f:
            json.dump(default, f)

UA = {"User-Agent": "Mozilla/5.0"}

# =========================
# SENTIMENT (VADER)
# =========================
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

# =========================
# PROFILS IA
# =========================
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

# =========================
# MAPPING / WATCHLIST
# =========================
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

# =========================
# LS EXCHANGE → YAHOO
# =========================
def _norm(s): return (s or "").strip().upper()

_PARIS = {"AIR","ORA","MC","TTE","BNP","SGO","ENGI","SU","DG","ACA","GLE","RI","KER","HO","EN","CAP","AI","PUB","VIE","VIV","STM"}

def guess_yahoo_from_ls(ticker: str):
    if not ticker: return None
    t = _norm(ticker)
    if "." in t and not t.endswith(".LS"):
        return t
    if t.endswith(".LS"):
        return f"{t[:-3]}.L"
    if t == "TOTB":
        return "TOTB.F"
    if t.endswith("B") and not t.endswith("AB"):
        return f"{t}.F"
    if t in _PARIS:
        return f"{t}.PA"
    if len(t) <= 6 and t.isalpha():
        return f"{t}.PA"
    return t

def maybe_guess_yahoo(s):
    s = _norm(s)
    m = load_mapping().get(s)
    return m or guess_yahoo_from_ls(s)

def resolve_identifier(id_or_ticker):
    raw = _norm(id_or_ticker)
    if not raw: return None, {}
    mapping = load_mapping()
    if raw in mapping:
        return mapping[raw], {"source": "mapping"}
    guess = maybe_guess_yahoo(raw)
    if guess:
        try:
            hist = yf.download(guess, period="5d", interval="1d", auto_adjust=False, progress=False, threads=False)
            if not hist.empty:
                mapping[raw] = guess
                save_mapping(mapping)
                return guess, {"source": "heuristic"}
        except Exception:
            pass
    return None, {}

# =========================
# RECHERCHE YAHOO
# =========================
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
        sym  = (r.get("symbol") or "").upper()
        if any(pm.lower() in exch for pm in prefer_markets): score += 3
        if q.lower() in name: score += 2
        if q.lower() in sym.lower(): score += 1
        ranked.append((score, r))
    ranked.sort(key=lambda x: x[0], reverse=True)
    return [r for _, r in ranked]

# =========================
# (… toutes tes autres sections : fetch_prices, compute_metrics, IA, etc …)
# [garde ton code tel quel ici]
# =========================

# =========================
# 🎨 AJOUT : SURBRILLANCE ADAPTATIVE CLAIR / SOMBRE
# =========================
def detect_dark_mode():
    """Détecte si le thème Streamlit est sombre (pour adapter les couleurs)."""
    try:
        import streamlit as st
        base = (st.get_option("theme.base") or "").lower()
        return "dark" in base
    except Exception:
        return False

def highlight_near_entry_adaptive(row, col="Proximité (%)"):
    """Surbrillance douce autour de l’entrée (2 %) adaptée au thème."""
    dark = detect_dark_mode()
    if pd.notna(row.get(col)) and abs(row.get(col)) <= 2:
        bg = "rgba(0,255,200,0.12)" if dark else "#fff9c4"
        return [f"background-color:{bg}; font-weight:600"] * len(row)
    return [""] * len(row)

def color_proximity_adaptive(v):
    """Colore la cellule Proximité (%) en fonction de la distance à l’entrée."""
    if pd.isna(v): return ""
    dark = detect_dark_mode()
    if abs(v) <= 2:
        return "background-color:rgba(0,255,150,0.2); color:#00ffcc" if dark else "background-color:#e6f4ea; color:#0b8043"
    if abs(v) <= 5:
        return "background-color:rgba(255,255,150,0.15); color:#ffeb3b" if dark else "background-color:#fff8e1; color:#a67c00"
    return "background-color:rgba(255,0,0,0.15); color:#ff6666" if dark else "background-color:#ffebee; color:#b71c1c"
