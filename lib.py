
# -*- coding: utf-8 -*-
import os, json, math, requests, numpy as np, pandas as pd, yfinance as yf
from functools import lru_cache
import nltk
from nltk.sentiment import SentimentIntensityAnalyzer

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
    (PROFILE_PATH, {"profil":"Neutre"}),
    (LAST_SEARCH_PATH, {"last":"TTE.PA"}),
]:
    if not os.path.exists(p):
        with open(p,"w",encoding="utf-8") as f: json.dump(default, f)

UA = {"User-Agent":"Mozilla/5.0"}

# Sentiment (best effort)
try:
    nltk.data.find("sentiment/vader_lexicon.zip")
except LookupError:
    try: nltk.download("vader_lexicon")
    except Exception: pass
try:
    SIA = SentimentIntensityAnalyzer()
except Exception:
    SIA = None

PROFILE_PARAMS = {
    "Agressif": {"vol_max":0.08,"target_mult":1.10,"stop_mult":0.92,"entry_mult":0.990},
    "Neutre":   {"vol_max":0.05,"target_mult":1.07,"stop_mult":0.95,"entry_mult":0.990},
    "Prudent":  {"vol_max":0.03,"target_mult":1.05,"stop_mult":0.97,"entry_mult":0.995},
}
def get_profile_params(profile:str):
    return PROFILE_PARAMS.get(profile or "Neutre", PROFILE_PARAMS["Neutre"])

def load_profile():
    try:
        return json.load(open(PROFILE_PATH,"r",encoding="utf-8")).get("profil","Neutre")
    except Exception:
        return "Neutre"
def save_profile(p):
    try:
        json.dump({"profil":p}, open(PROFILE_PATH,"w",encoding="utf-8"), ensure_ascii=False, indent=2)
    except Exception:
        pass

def load_last_search():
    try:
        return json.load(open(LAST_SEARCH_PATH,"r",encoding="utf-8")).get("last","")
    except Exception:
        return ""
def save_last_search(t):
    try:
        json.dump({"last":t}, open(LAST_SEARCH_PATH,"w",encoding="utf-8"), ensure_ascii=False, indent=2)
    except Exception:
        pass

def load_mapping():
    try: return json.load(open(MAPPING_PATH,"r",encoding="utf-8"))
    except Exception: return {}
def save_mapping(m): json.dump(m, open(MAPPING_PATH,"w",encoding="utf-8"), ensure_ascii=False, indent=2)

def load_watchlist_ls():
    try: return json.load(open(WL_PATH,"r",encoding="utf-8"))
    except Exception: return []
def save_watchlist_ls(lst): json.dump(lst, open(WL_PATH,"w",encoding="utf-8"), ensure_ascii=False, indent=2)

def _norm(s): return (s or "").strip().upper()

_PARIS = {"AIR","ORA","MC","TTE","BNP","SGO","ENGI","SU","DG","ACA","GLE","RI","KER","HO","EN","CAP","AI","PUB","VIE","VIV","STM"}
def guess_yahoo_from_ls(ticker:str):
    if not ticker: return None
    t=_norm(ticker)
    if "." in t and not t.endswith(".LS"): return t
    if t.endswith(".LS"): return f"{t[:-3]}.L"
    if t=="TOTB": return "TOTB.F"
    if t.endswith("B") and not t.endswith("AB"): return f"{t}.F"
    if t in _PARIS: return f"{t}.PA"
    if len(t)<=6 and t.isalpha(): return f"{t}.PA"
    return t

def maybe_guess_yahoo(s):
    s=_norm(s)
    m=load_mapping().get(s)
    return m or guess_yahoo_from_ls(s)

def resolve_identifier(id_or_ticker):
    raw=_norm(id_or_ticker)
    if not raw: return None,{}
    mapping=load_mapping()
    if raw in mapping: return mapping[raw],{"source":"mapping"}
    guess=maybe_guess_yahoo(raw)
    if guess:
        try:
            hist=yf.download(guess,period="5d",interval="1d",auto_adjust=False,progress=False,threads=False)
            if not hist.empty:
                mapping[raw]=guess; save_mapping(mapping)
                return guess,{"source":"heuristic"}
        except Exception: pass
    return None,{}

@lru_cache(maxsize=256)
def yahoo_search(query:str, region="FR", lang="fr-FR", quotesCount=20):
    url = "https://query2.finance.yahoo.com/v1/finance/search"
    params = {"q": query, "quotesCount": quotesCount, "newsCount": 0, "lang": lang, "region": region}
    try:
        r = requests.get(url, params=params, headers=UA, timeout=12)
        r.raise_for_status()
        data = r.json()
        quotes = data.get("quotes", [])
        out=[]
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

def find_ticker_by_name(company_name:str, prefer_markets=("Paris","XETRA","Frankfurt","NasdaqGS","NYSE")):
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
    return [r for _,r in ranked]

@lru_cache(maxsize=32)
def _read_tables(url:str):
    html=requests.get(url,headers=UA,timeout=20).text
    return pd.read_html(html)

def _extract_name_ticker(tables):
    table=None
    for df in tables:
        cols={str(c).lower() for c in df.columns}
        if (("company" in cols or "name" in cols) and ("ticker" in cols or "symbol" in cols)):
            table=df.copy(); break
    if table is None: table=tables[0].copy()
    table.rename(columns={c:str(c).lower() for c in table.columns}, inplace=True)
    tcol=next((c for c in table.columns if "ticker" in c or "symbol" in c), table.columns[0])
    ncol=next((c for c in table.columns if "company" in c or "name" in c), table.columns[1])
    out=table[[tcol,ncol]].copy(); out.columns=["ticker","name"]
    out["ticker"]=out["ticker"].astype(str).str.strip()
    return out.dropna().drop_duplicates(subset=["ticker"])

@lru_cache(maxsize=8)
def members_cac40():
    df=_extract_name_ticker(_read_tables("https://en.wikipedia.org/wiki/CAC_40"))
    df["ticker"]=df["ticker"].apply(lambda x: x if "." in x else f"{x}.PA"); df["index"]="CAC 40"; return df

def members(index_name:str):
    if index_name=="CAC 40": return members_cac40()
    return pd.DataFrame(columns=["ticker","name","index"])

@lru_cache(maxsize=64)
def fetch_prices_cached(tickers_tuple, period="120d"):
    tickers=list(tickers_tuple)
    if not tickers: return pd.DataFrame()
    try:
        data=yf.download(tickers,period=period,interval="1d",auto_adjust=False,group_by="ticker",threads=False,progress=False)
    except Exception: return pd.DataFrame()
    if data is None or len(data)==0: return pd.DataFrame()
    frames=[]
    if isinstance(data,pd.DataFrame) and {"Open","High","Low","Close"}.issubset(data.columns):
        df=data.copy(); df["Ticker"]=tickers[0]; frames.append(df)
    else:
        for t in tickers:
            try:
                if t in data and isinstance(data[t],pd.DataFrame):
                    df=data[t].copy(); df["Ticker"]=t; frames.append(df)
            except Exception: continue
    if not frames: return pd.DataFrame()
    out=pd.concat(frames); out.reset_index(inplace=True); return out

def fetch_prices(tickers, days=120):
    return fetch_prices_cached(tuple(tickers), period=f"{days}d")

def compute_metrics(df:pd.DataFrame)->pd.DataFrame:
    cols=["Ticker","Date","Close","ATR14","MA20","MA50","gap20","gap50","trend_score"]
    if df is None or df.empty: return pd.DataFrame(columns=cols)
    df=df.copy()
    if "Date" not in df.columns:
        df=df.reset_index().rename(columns={df.index.name or "index":"Date"})
    need={"Ticker","Date","High","Low","Close"}
    if need - set(df.columns): return pd.DataFrame(columns=cols)
    df=df.sort_values(["Ticker","Date"])
    df["PrevClose"]=df.groupby("Ticker")["Close"].shift(1)
    df["TR"]=np.maximum(df["High"]-df["Low"], np.maximum((df["High"]-df["PrevClose"]).abs(), (df["Low"]-df["PrevClose"]).abs()))
    df["ATR14"]=df.groupby("Ticker")["TR"].transform(lambda s:s.rolling(14,min_periods=5).mean())
    df["MA20"]=df.groupby("Ticker")["Close"].transform(lambda s:s.rolling(20,min_periods=5).mean())
    df["MA50"]=df.groupby("Ticker")["Close"].transform(lambda s:s.rolling(50,min_periods=10).mean())
    last=df.groupby("Ticker").tail(1)[["Ticker","Date","Close","ATR14","MA20","MA50"]].copy()
    last["gap20"]=last.apply(lambda r: (r["Close"]/r["MA20"]-1) if (not np.isnan(r["MA20"]) and r["MA20"]!=0) else np.nan, axis=1)
    last["gap50"]=last.apply(lambda r: (r["Close"]/r["MA50"]-1) if (not np.isnan(r["MA50"]) and r["MA50"]!=0) else np.nan, axis=1)
    last["trend_score"]=0.6*last["gap20"]+0.4*last["gap50"]
    return last.reset_index(drop=True)

@lru_cache(maxsize=256)
def google_news_titles(query, lang="fr"):
    url=f"https://news.google.com/rss/search?q={requests.utils.quote(query)}&hl={lang}-{lang.upper()}&gl={lang.upper()}&ceid={lang.upper()}:{lang.upper()}"
    try:
        xml=requests.get(url,headers=UA,timeout=12).text
        import xml.etree.ElementTree as ET
        root=ET.fromstring(xml)
        items=[(it.findtext("title") or "", it.findtext("link") or "") for it in root.iter("item")]
        return items[:10]
    except Exception: return []

def filter_company_news(ticker, company_name, items):
    if not items: return []
    tkr=(ticker or "").lower()
    name=(company_name or "").lower()
    name_short = name.split(" ")[0] if name else ""
    keep=[]
    for title,link in items:
        tl=title.lower()
        if (tkr and tkr in tl) or (name and name in tl) or (name_short and name_short in tl):
            keep.append((title,link))
    return keep

def news_summary(name,ticker,lang="fr"):
    items=google_news_titles(f"{name} {ticker}",lang) or google_news_titles(name,lang)
    items=filter_company_news(ticker, name, items)
    titles=[t for t,_ in items]
    if not titles: return ("Pas d’actualité saillante — mouvement technique / macro.",0.0,[])
    POS=["résultats","bénéfice","contrat","relève","guidance","record","upgrade","partenariat","dividende","approbation"]
    NEG=["profit warning","retard","procès","amende","downgrade","abaisse","enquête","rappel","départ","incident"]
    scores=[]
    for t in titles:
        s=0.0
        if SIA:
            try: s=SIA.polarity_scores(t.lower())["compound"]
            except Exception: s=0.0
        tl=t.lower()
        if any(k in tl for k in POS): s+=0.2
        if any(k in tl for k in NEG): s-=0.2
        scores.append(s)
    m=float(np.mean(scores)) if scores else 0.0
    txt=("Hausse soutenue par des nouvelles positives." if m>0.15
         else "Baisse liée à des nouvelles défavorables." if m<-0.15
         else "Actualité mitigée/neutre — mouvement surtout technique.")
    return (txt,m,items)

def decision_label_from_row(row, held=False, vol_max=0.05):
    px=float(row.get("Close", math.nan))
    ma20=float(row.get("MA20", math.nan)) if pd.notna(row.get("MA20", math.nan)) else math.nan
    ma50=float(row.get("MA50", math.nan)) if pd.notna(row.get("MA50", math.nan)) else math.nan
    atr=float(row.get("ATR14", math.nan)) if pd.notna(row.get("ATR14", math.nan)) else math.nan
    pru=float(row.get("PRU", math.nan)) if "PRU" in row else math.nan
    if not math.isfinite(px): return "👁️ Surveiller"
    vol=(atr/px) if (math.isfinite(atr) and px>0) else 0.03
    trend=(1 if math.isfinite(ma20) and px>=ma20 else 0)+(1 if math.isfinite(ma50) and px>=ma50 else 0)
    score=0.0
    score+=0.5*(1 if trend==2 else 0 if trend==1 else -1)
    if math.isfinite(pru) and pru>0: score+=0.2*(1 if px>pru*1.02 else -1 if px<pru*0.98 else 0)
    score+=0.3*(-1 if vol>vol_max else 1)
    if held:
        if score>0.5: return "🟢 Acheter"
        if score<-0.2: return "🔴 Vendre"
        return "🟠 Garder"
    else:
        if score>0.3: return "🟢 Acheter"
        if score<-0.2: return "🚫 Éviter"
        return "👁️ Surveiller"

def price_levels_from_row(row, profile="Neutre"):
    p=get_profile_params(profile)
    px=float(row.get("Close", math.nan))
    ma20=float(row.get("MA20", math.nan)) if pd.notna(row.get("MA20", math.nan)) else math.nan
    base=ma20 if math.isfinite(ma20) else px
    if not math.isfinite(base): return {"entry":math.nan,"target":math.nan,"stop":math.nan}
    return {"entry":round(base*p["entry_mult"],2),"target":round(base*p["target_mult"],2),"stop":round(base*p["stop_mult"],2)}

def style_variations(df, cols):
    def color_var(v):
        if pd.isna(v): return ""
        if v>0: return "background-color:#e8f5e9; color:#0b8f3a"
        if v<0: return "background-color:#ffebee; color:#d5353a"
        return "background-color:#e8f0fe; color:#1e88e5"
    sty=df.style
    for c in cols:
        if c in df.columns: sty=sty.applymap(color_var, subset=[c])
    return sty

@lru_cache(maxsize=1024)
def company_name_from_ticker(ticker: str) -> str:
    if not ticker: return ""
    try:
        t = yf.Ticker(ticker)
        name = None
        try:
            name = t.fast_info.get("shortName", None)
        except Exception:
            pass
        if not name:
            info = t.get_info()
            name = info.get("shortName") or info.get("longName")
        return name or ticker
    except Exception:
        return ticker

def dividends_summary(ticker:str):
    try:
        t = yf.Ticker(ticker)
        div = t.dividends
        if div is None or div.empty:
            return [], None
        div = div.sort_index(ascending=False)
        recent = [(str(idx.date()), float(val)) for idx,val in div.head(8).items()]
        px = t.history(period="5d")["Close"].iloc[-1]
        trailing = float(div.head(4).sum()/px) if px and px>0 else None
        return recent, trailing
    except Exception:
        return [], None

def fetch_all_markets(markets, days_hist=90):
    frames=[]
    for idx, source in markets:
        if idx=="CAC 40":
            mem=members("CAC 40")
        elif idx=="LS Exchange":
            ls_list = load_watchlist_ls()
            tickers=[maybe_guess_yahoo(x) or x for x in ls_list] if ls_list else []
            mem=pd.DataFrame({"ticker": tickers, "name": ls_list})
        else:
            continue
        if mem.empty: continue
        px=fetch_prices(mem["ticker"].tolist(), days=days_hist)
        if px.empty: continue
        met=compute_metrics(px).merge(mem, left_on="Ticker", right_on="ticker", how="left")
        met["Indice"]=idx
        frames.append(met)
    return pd.concat(frames, ignore_index=True, sort=False) if frames else pd.DataFrame()
