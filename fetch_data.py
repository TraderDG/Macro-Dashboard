#!/usr/bin/env python3
"""
MACRO DASHBOARD - DATA PIPELINE
================================
Fetches real data from FRED + Yahoo Finance.
Outputs 3 CSV files into the data/ folder.

Install:  pip install pandas yfinance fredapi
Run:      python fetch_data.py
"""

import os, sys
import pandas as pd
import yfinance as yf
from fredapi import Fred
from datetime import datetime

FRED_API_KEY = "322621bac2b61ab1143c00b17e7988b9"
START        = "2005-01-01"
END          = datetime.today().strftime("%Y-%m-%d")
OUT          = os.path.join(os.path.dirname(__file__), "data")

def log(msg): print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

# ─── FRED ─────────────────────────────────────────────────────────
def get_fred(fred, series_id, col):
    log(f"  FRED {series_id} → {col}")
    try:
        s  = fred.get_series(series_id, observation_start=START, observation_end=END)
        df = pd.DataFrame({"date": s.index, col: s.values})
        df["date"] = pd.to_datetime(df["date"]).dt.normalize()
        df = df.dropna(subset=[col]).drop_duplicates("date").sort_values("date")
        # Forward-fill to daily (macro data is monthly/weekly)
        rng = pd.date_range(df["date"].min(), END, freq="D")
        df  = df.set_index("date").reindex(rng).ffill().reset_index()
        df.columns = ["date", col]
        df["date"] = df["date"].dt.strftime("%Y-%m-%d")
        df[col]    = pd.to_numeric(df[col], errors="coerce")
        return df
    except Exception as e:
        log(f"  ⚠ FAILED {series_id}: {e}")
        return pd.DataFrame(columns=["date", col])

# ─── YFINANCE ─────────────────────────────────────────────────────
def get_yf(tickers, rename=None):
    log(f"  yfinance {tickers}")
    try:
        raw = yf.download(tickers, start=START, end=END,
                          auto_adjust=True, progress=False)
        if isinstance(tickers, str) or len(tickers) == 1:
            t   = tickers if isinstance(tickers, str) else tickers[0]
            col = rename.get(t, t) if rename else t
            df  = raw[["Close"]].rename(columns={"Close": col}).reset_index()
        else:
            close = raw["Close"] if "Close" in raw.columns else raw.xs("Close", axis=1, level=0)
            df = close.reset_index()

        df = df.rename(columns={"Date": "date", "Datetime": "date"})
        df["date"] = pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d")
        if rename:
            df = df.rename(columns=rename)
        for c in df.columns:
            if c != "date":
                df[c] = pd.to_numeric(df[c], errors="coerce")
        df = df.dropna(how="all", subset=[c for c in df.columns if c != "date"])
        df = df.drop_duplicates("date").sort_values("date")
        return df
    except Exception as e:
        log(f"  ⚠ FAILED yfinance: {e}")
        return pd.DataFrame()

# ─── MERGE ────────────────────────────────────────────────────────
def merge(frames):
    if not frames: return pd.DataFrame()
    out = frames[0]
    for f in frames[1:]:
        if not f.empty:
            out = pd.merge(out, f, on="date", how="outer")
    return out.sort_values("date").drop_duplicates("date")

# ─── EXPORT ───────────────────────────────────────────────────────
def save(df, name):
    path = os.path.join(OUT, name)
    df["date"] = pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d")
    df = df.sort_values("date").drop_duplicates("date")
    non_date = [c for c in df.columns if c != "date"]
    df = df.dropna(subset=non_date, how="all")
    df.to_csv(path, index=False, float_format="%.4f")
    log(f"  ✓ {name}: {len(df)} rows × {len(df.columns)-1} cols → {path}")

# ─── MAIN ─────────────────────────────────────────────────────────
def main():
    os.makedirs(OUT, exist_ok=True)
    fred = Fred(api_key=FRED_API_KEY)

    # ── market.csv ──────────────────────────────────────────────
    log("=" * 50)
    log("MARKET.CSV")
    tickers = ["IWM","SPY","QQQ","XLK","XLY","XLF","XLI","XLB","XLE","XLV","XLP","XLU","XLRE"]
    mkt = get_yf(tickers)
    save(mkt, "market.csv")

    # ── liquidity.csv ────────────────────────────────────────────
    log("=" * 50)
    log("LIQUIDITY.CSV")
    liq_fred = {
        "M2":     "M2SL",
        "FED_BS": "WALCL",
        "FFR":    "FEDFUNDS",
        "T10Y":   "DGS10",
        "T2Y":    "DGS2",
        "CPI":    "CPIAUCSL",
    }
    frames = [get_fred(fred, sid, col) for col, sid in liq_fred.items()]
    save(merge(frames), "liquidity.csv")

    # ── credit.csv ───────────────────────────────────────────────
    log("=" * 50)
    log("CREDIT.CSV")
    hy  = get_fred(fred, "BAMLH0A0HYM2", "HY_SPREAD")
    ig  = get_fred(fred, "BAMLC0A0CM",   "IG_SPREAD")
    t10 = get_fred(fred, "DGS10",        "T10Y")
    mkt_credit = get_yf(
        ["DX-Y.NYB", "CL=F", "XLF", "KRE"],
        rename={"DX-Y.NYB": "DXY", "CL=F": "OIL"}
    )
    save(merge([hy, ig, t10, mkt_credit]), "credit.csv")

    log("=" * 50)
    log("DONE — files saved to data/")

if __name__ == "__main__":
    main()
