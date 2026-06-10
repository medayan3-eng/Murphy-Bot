"""
================================================================================
EOD STOCK SCREENER — Murphy Methodology
================================================================================
Iron Filter (5 hard conditions) + Fibonacci Dashboard.

PART A — Iron Filter (ALL conditions must pass):
   1. Price ≥ $3  AND  20-day avg volume ≥ 750,000 shares
   2. Sector outperforms SPY over last 50 days (relative strength > 1)
   3. Current price > SMA50  AND  Current price > SMA200
   4. Higher-High AND Higher-Low (Dow Theory uptrend, verified mathematically)
   5. Pullback volume < Rising-wave volume (no panic / distribution)

PART B — Fibonacci Dashboard (for passers only):
   - Wave start (last swing low) → Wave end (last swing high)
   - Fib retracements: 23.6%, 38.2%, 50.0%, 61.8%
   - Current price and live retracement %

Data: Yahoo Finance (free, via yfinance).
================================================================================
"""
from __future__ import annotations

import os
from copy import deepcopy
from datetime import datetime
from typing import Callable, Optional

import numpy as np
import pandas as pd

try:
    import yfinance as yf
except ImportError:
    yf = None


# ==============================================================================
# DEFAULT CONFIG
# ==============================================================================
DEFAULT_CONFIG = {
    "min_price":            3.0,
    "min_avg_volume":       750_000,
    "sector_rs_lookback":   50,
    "sma_fast":             50,
    "sma_slow":             200,
    "swing_window":         5,
    "min_bars":             250,
    "macro": {
        "enabled":           True,
        "spy_ticker":        "SPY",
        "spy_sma_length":    50,
        "vix_enabled":       True,
        "vix_ticker":        "^VIX",
        "vix_threshold":     25.0,
        "vxv_enabled":       True,
        "vxv_ticker":        "^VIX3M",
        "vxv_ratio_max":     1.0,
        "sector_rs_enabled": True,
    },
    "risk": {
        "equity":              10000.0,
        "risk_per_trade_pct":  0.02,
        "atr_length":          14,
        "atr_stop_multiplier": 2.0,
    },
    "universe":         [],
    "history_period":   "2y",
}


def get_default_config() -> dict:
    return deepcopy(DEFAULT_CONFIG)


# ==============================================================================
# SECTOR ETF MAP
# ==============================================================================
SECTOR_ETF_MAP = {
    "Technology": "XLK", "Information Technology": "XLK",
    "Healthcare": "XLV", "Health Care": "XLV",
    "Financials": "XLF", "Financial Services": "XLF",
    "Consumer Discretionary": "XLY", "Consumer Cyclical": "XLY",
    "Communication Services": "XLC",
    "Industrials": "XLI",
    "Consumer Staples": "XLP", "Consumer Defensive": "XLP",
    "Energy": "XLE",
    "Utilities": "XLU",
    "Real Estate": "XLRE",
    "Materials": "XLB", "Basic Materials": "XLB",
}
ALL_SECTOR_ETFS = sorted(set(SECTOR_ETF_MAP.values()))


# ==============================================================================
# UNIVERSE / PORTFOLIO LOADING
# ==============================================================================
def load_universe(path: str) -> list[str]:
    df = pd.read_csv(path)
    col = "Ticker" if "Ticker" in df.columns else df.columns[0]
    return df[col].astype(str).str.upper().str.strip().tolist()


def load_portfolio(path_or_df) -> pd.DataFrame:
    if isinstance(path_or_df, pd.DataFrame):
        df = path_or_df.copy()
    elif isinstance(path_or_df, str):
        if not os.path.exists(path_or_df):
            return pd.DataFrame(columns=["Ticker", "Entry_Price", "Entry_Date"])
        if path_or_df.lower().endswith((".xlsx", ".xls")):
            df = pd.read_excel(path_or_df, engine="openpyxl")
        else:
            df = pd.read_csv(path_or_df)
    else:
        return pd.DataFrame(columns=["Ticker", "Entry_Price", "Entry_Date"])
    df["Ticker"] = df["Ticker"].astype(str).str.upper().str.strip()
    df["Entry_Price"] = pd.to_numeric(df["Entry_Price"], errors="coerce")
    if "Entry_Date" in df.columns:
        df["Entry_Date"] = pd.to_datetime(df["Entry_Date"], errors="coerce")
    return df.dropna(subset=["Ticker", "Entry_Price"]).reset_index(drop=True)


# ==============================================================================
# DATA FETCHING
# ==============================================================================
def _flatten_yf_df(df) -> Optional[pd.DataFrame]:
    if df is None or df.empty:
        return None
    if isinstance(df.columns, pd.MultiIndex):
        df = df.copy()
        df.columns = df.columns.get_level_values(0)
    needed = ["Open", "High", "Low", "Close", "Volume"]
    if not all(c in df.columns for c in needed):
        return None
    return df[needed].dropna()


def fetch_ohlcv_batch(tickers: list[str], period: str = "2y",
                      status_cb: Optional[Callable[[str], None]] = None) -> dict:
    if yf is None:
        raise ImportError("yfinance not installed")
    out = {}
    chunk_size = 50
    for chunk_idx in range(0, len(tickers), chunk_size):
        chunk = tickers[chunk_idx:chunk_idx + chunk_size]
        if status_cb:
            status_cb(f"Downloading {chunk_idx+1}–{min(chunk_idx+chunk_size,len(tickers))} of {len(tickers)}…")
        try:
            data = yf.download(chunk, period=period, interval="1d",
                               group_by="ticker", auto_adjust=True,
                               progress=False, threads=True)
        except Exception:
            continue
        for t in chunk:
            try:
                if len(chunk) == 1:
                    sub = data
                elif isinstance(data.columns, pd.MultiIndex) and t in data.columns.levels[0]:
                    sub = data[t]
                else:
                    continue
                flat = _flatten_yf_df(sub)
                if flat is not None and not flat.empty:
                    out[t] = flat
            except Exception:
                continue
    return out


# ==============================================================================
# INDICATORS (only what's needed)
# ==============================================================================
def add_indicators(df: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    df = df.copy()
    df["SMA_fast"] = df["Close"].rolling(cfg["sma_fast"]).mean()
    df["SMA_slow"] = df["Close"].rolling(cfg["sma_slow"]).mean()
    df["VOL_SMA"]  = df["Volume"].rolling(20).mean()

    # ATR for trailing stops (portfolio module)
    h_l  = df["High"] - df["Low"]
    h_pc = (df["High"] - df["Close"].shift()).abs()
    l_pc = (df["Low"]  - df["Close"].shift()).abs()
    tr   = pd.concat([h_l, h_pc, l_pc], axis=1).max(axis=1)
    df["ATR"] = tr.rolling(cfg["risk"]["atr_length"]).mean()
    return df


# ==============================================================================
# MACRO KILL-SWITCH
# ==============================================================================
def get_macro_snapshot(cfg: dict, data_cache: dict) -> tuple[bool, dict]:
    info = {}
    passed, total = 0, 0

    spy = data_cache.get(cfg["macro"]["spy_ticker"])
    if spy is not None and len(spy) >= cfg["macro"]["spy_sma_length"]:
        c = float(spy["Close"].iloc[-1])
        s = float(spy["Close"].rolling(cfg["macro"]["spy_sma_length"]).mean().iloc[-1])
        ok = c > s
        info["SPY"] = f"{c:.2f}"
        info["SPY vs SMA50"] = "above ✅" if ok else "below ❌"
        total += 1
        if ok: passed += 1

    if cfg["macro"]["vix_enabled"]:
        vix = data_cache.get(cfg["macro"]["vix_ticker"])
        if vix is not None and not vix.empty:
            v = float(vix["Close"].iloc[-1])
            ok = v < cfg["macro"]["vix_threshold"]
            info["VIX"] = f"{v:.2f}"
            info["VIX status"] = (
                "calm 🟢" if v < 15 else "normal 🟢" if v < 20 else
                "elevated 🟡" if v < 25 else "stressed 🟠" if v < 30 else "fear 🔴"
            )
            total += 1
            if ok: passed += 1

    if cfg["macro"]["vxv_enabled"]:
        vix = data_cache.get(cfg["macro"]["vix_ticker"])
        vxv = data_cache.get(cfg["macro"]["vxv_ticker"])
        if vix is not None and vxv is not None and not vix.empty and not vxv.empty:
            r = float(vix["Close"].iloc[-1]) / float(vxv["Close"].iloc[-1])
            ok = r < cfg["macro"]["vxv_ratio_max"]
            info["VIX/VXV ratio"] = f"{r:.2f}"
            info["Term structure"] = "normal ✅" if ok else "stressed ❌"
            total += 1
            if ok: passed += 1

    macro_ok = total == 0 or passed >= max(1, total - 1)
    return macro_ok, info


_TICKER_SECTOR_CACHE: dict[str, str] = {}


def _resolve_sector_etf(ticker: str) -> Optional[str]:
    """Lazily resolve sector via yfinance.info. Cached per process."""
    if ticker in _TICKER_SECTOR_CACHE:
        return SECTOR_ETF_MAP.get(_TICKER_SECTOR_CACHE[ticker])
    if yf is None:
        return None
    try:
        info = yf.Ticker(ticker).info
        sec = info.get("sector")
        if sec:
            _TICKER_SECTOR_CACHE[ticker] = sec
            return SECTOR_ETF_MAP.get(sec)
    except Exception:
        pass
    return None


def check_sector_strength(ticker: str, cfg: dict, data_cache: dict) -> tuple[bool, dict]:
    """Condition 2: sector outperforms SPY over the lookback window."""
    if not cfg["macro"]["sector_rs_enabled"]:
        return True, {"ratio": None, "sector_etf": None}

    sector_etf = _resolve_sector_etf(ticker)
    if sector_etf is None:
        # Unknown sector → pass (don't gate on missing data)
        return True, {"ratio": None, "sector_etf": None}

    sec_df = data_cache.get(sector_etf)
    spy_df = data_cache.get(cfg["macro"]["spy_ticker"])
    lb = cfg["sector_rs_lookback"]
    if sec_df is None or spy_df is None or len(sec_df) < lb+1 or len(spy_df) < lb+1:
        return True, {"ratio": None, "sector_etf": sector_etf}

    sec_ret = sec_df["Close"].iloc[-1] / sec_df["Close"].iloc[-lb-1] - 1.0
    spy_ret = spy_df["Close"].iloc[-1] / spy_df["Close"].iloc[-lb-1] - 1.0
    ratio = (1.0 + sec_ret) / (1.0 + spy_ret)
    return ratio > 1.0, {
        "ratio": float(ratio),
        "sector_etf": sector_etf,
        "sector_ret_pct": float(sec_ret * 100),
        "spy_ret_pct":    float(spy_ret * 100),
    }


# ==============================================================================
# IRON FILTER CHECKS
# ==============================================================================
def check_liquidity_and_price(df: pd.DataFrame, cfg: dict) -> tuple[bool, float, float]:
    price = float(df["Close"].iloc[-1])
    avg_vol = (float(df["VOL_SMA"].iloc[-1]) if "VOL_SMA" in df.columns and
               not pd.isna(df["VOL_SMA"].iloc[-1]) else float(df["Volume"].tail(20).mean()))
    if pd.isna(price) or pd.isna(avg_vol):
        return False, price, avg_vol
    if price < cfg["min_price"] or avg_vol < cfg["min_avg_volume"]:
        return False, price, avg_vol
    return True, price, avg_vol


def check_ma_position(df: pd.DataFrame) -> bool:
    close = df["Close"].iloc[-1]
    sma_fast = df["SMA_fast"].iloc[-1]
    sma_slow = df["SMA_slow"].iloc[-1]
    if pd.isna(sma_fast) or pd.isna(sma_slow):
        return False
    return close > sma_fast and close > sma_slow


def find_swing_highs_lows(df: pd.DataFrame, window: int = 5) -> tuple[list[int], list[int]]:
    """Confirmed pivots only (the last `window` bars are excluded)."""
    highs = df["High"].values
    lows  = df["Low"].values
    n = len(df)
    swing_highs, swing_lows = [], []
    for i in range(window, n - window):
        win_h = highs[i - window:i + window + 1]
        win_l = lows[i - window:i + window + 1]
        if highs[i] == win_h.max():
            if not swing_highs or i - swing_highs[-1] >= window:
                swing_highs.append(i)
        if lows[i] == win_l.min():
            if not swing_lows or i - swing_lows[-1] >= window:
                swing_lows.append(i)
    return swing_highs, swing_lows


def check_hh_hl_structure(df: pd.DataFrame, cfg: dict) -> tuple[bool, Optional[dict]]:
    swing_highs, swing_lows = find_swing_highs_lows(df, cfg["swing_window"])
    if len(swing_highs) < 2 or len(swing_lows) < 2:
        return False, None
    h_curr_i, h_prev_i = swing_highs[-1], swing_highs[-2]
    l_curr_i, l_prev_i = swing_lows[-1],  swing_lows[-2]
    h_curr = float(df["High"].iloc[h_curr_i])
    h_prev = float(df["High"].iloc[h_prev_i])
    l_curr = float(df["Low"].iloc[l_curr_i])
    l_prev = float(df["Low"].iloc[l_prev_i])
    if not (h_curr > h_prev and l_curr > l_prev):
        return False, None
    # Wave must be: low → high in order
    if l_curr_i >= h_curr_i:
        return False, None
    return True, {
        "h_curr_idx": h_curr_i, "h_prev_idx": h_prev_i,
        "l_curr_idx": l_curr_i, "l_prev_idx": l_prev_i,
        "h_curr": h_curr, "h_prev": h_prev,
        "l_curr": l_curr, "l_prev": l_prev,
    }


def check_pullback_volume(df: pd.DataFrame, swing_info: dict) -> tuple[bool, Optional[float]]:
    l_i, h_i = swing_info["l_curr_idx"], swing_info["h_curr_idx"]
    n = len(df)
    if h_i >= n - 1:
        return False, None
    rising   = df["Volume"].iloc[l_i:h_i + 1]
    pullback = df["Volume"].iloc[h_i + 1:n]
    if len(rising) < 2 or len(pullback) < 1:
        return False, None
    r_avg = float(rising.mean()); p_avg = float(pullback.mean())
    if r_avg == 0 or pd.isna(r_avg) or pd.isna(p_avg):
        return False, None
    ratio = p_avg / r_avg
    return ratio < 1.0, ratio


def calculate_fibonacci_levels(df: pd.DataFrame, swing_info: dict) -> dict:
    l_i, h_i = swing_info["l_curr_idx"], swing_info["h_curr_idx"]
    wave_low  = float(df["Low"].iloc[l_i])
    wave_high = float(df["High"].iloc[h_i])
    wave_size = wave_high - wave_low
    current   = float(df["Close"].iloc[-1])
    if wave_size > 0:
        current_retrace = (wave_high - current) / wave_size * 100
        wave_size_pct   = wave_size / wave_low * 100 if wave_low > 0 else 0
    else:
        current_retrace = 0.0
        wave_size_pct   = 0.0
    return {
        "wave_low":              wave_low,
        "wave_high":             wave_high,
        "wave_low_date":         df.index[l_i],
        "wave_high_date":        df.index[h_i],
        "wave_size_pct":         wave_size_pct,
        "fib_23_6":              wave_high - 0.236 * wave_size,
        "fib_38_2":              wave_high - 0.382 * wave_size,
        "fib_50_0":              wave_high - 0.500 * wave_size,
        "fib_61_8":              wave_high - 0.618 * wave_size,
        "current_price":         current,
        "current_retracement_pct": current_retrace,
        "days_since_high":       len(df) - 1 - h_i,
    }


def check_iron_filter(ticker: str, df: pd.DataFrame, cfg: dict,
                      data_cache: dict) -> tuple[bool, dict]:
    """Run all 5 conditions. Returns (all_passed, details)."""
    details = {"ticker": ticker, "reasons_failed": []}

    ok, price, avg_vol = check_liquidity_and_price(df, cfg)
    details["price"] = price; details["avg_vol"] = avg_vol
    if not ok:
        details["reasons_failed"].append("Price/Volume floor")
        return False, details
    details["passed_1"] = True

    if cfg["macro"]["sector_rs_enabled"]:
        ok, si = check_sector_strength(ticker, cfg, data_cache)
        details["sector_etf"]   = si.get("sector_etf")
        details["sector_ratio"] = si.get("ratio")
        if not ok:
            details["reasons_failed"].append("Sector RS ≤ SPY")
            return False, details
    details["passed_2"] = True

    if not check_ma_position(df):
        details["reasons_failed"].append("Price ≤ SMA50 or SMA200")
        return False, details
    details["passed_3"] = True

    ok, swing = check_hh_hl_structure(df, cfg)
    if not ok:
        details["reasons_failed"].append("No HH/HL structure")
        return False, details
    details["passed_4"] = True
    details["swing_info"] = swing

    ok, vol_ratio = check_pullback_volume(df, swing)
    details["vol_ratio"] = vol_ratio
    if not ok:
        details["reasons_failed"].append("Pullback vol ≥ rising vol")
        return False, details
    details["passed_5"] = True

    details["fib"] = calculate_fibonacci_levels(df, swing)
    return True, details


# ==============================================================================
# ORCHESTRATOR
# ==============================================================================
def evaluate_iron_filter_universe(cfg: dict, data_cache: dict) -> dict:
    rows = []
    diag = {
        "evaluated": 0, "passed_liquidity": 0, "passed_sector_rs": 0,
        "passed_ma": 0, "passed_hh_hl": 0, "passed_vol_conf": 0, "final": 0,
    }
    for ticker in cfg["universe"]:
        df = data_cache.get(ticker)
        if df is None or len(df) < cfg["min_bars"]:
            continue
        diag["evaluated"] += 1
        passed, details = check_iron_filter(ticker, df, cfg, data_cache)
        if details.get("passed_1"): diag["passed_liquidity"] += 1
        if details.get("passed_2"): diag["passed_sector_rs"] += 1
        if details.get("passed_3"): diag["passed_ma"] += 1
        if details.get("passed_4"): diag["passed_hh_hl"] += 1
        if details.get("passed_5"): diag["passed_vol_conf"] += 1
        if not passed:
            continue
        diag["final"] += 1
        fib = details["fib"]
        rows.append({
            "Ticker":            ticker,
            "Price":             round(details["price"], 2),
            "Wave_Low":          round(fib["wave_low"], 2),
            "Wave_Low_Date":     fib["wave_low_date"].strftime("%Y-%m-%d"),
            "Wave_High":         round(fib["wave_high"], 2),
            "Wave_High_Date":    fib["wave_high_date"].strftime("%Y-%m-%d"),
            "Wave_Size_%":       round(fib["wave_size_pct"], 1),
            "Fib_23.6%":         round(fib["fib_23_6"], 2),
            "Fib_38.2%":         round(fib["fib_38_2"], 2),
            "Fib_50.0%":         round(fib["fib_50_0"], 2),
            "Fib_61.8%":         round(fib["fib_61_8"], 2),
            "Current_Retrace_%": round(fib["current_retracement_pct"], 1),
            "Days_Since_High":   fib["days_since_high"],
            "Vol_Ratio":         round(details["vol_ratio"], 2) if details.get("vol_ratio") else None,
            "Sector_RS":         round(details["sector_ratio"], 2) if details.get("sector_ratio") else None,
        })
    df_out = pd.DataFrame(rows)
    if not df_out.empty:
        df_out = df_out.sort_values("Current_Retrace_%", ascending=True).reset_index(drop=True)
    return {"passers": df_out, "diagnostics": diag}


# ==============================================================================
# PORTFOLIO
# ==============================================================================
def evaluate_portfolio(cfg: dict, data_cache: dict, portfolio_df: pd.DataFrame) -> pd.DataFrame:
    if portfolio_df is None or portfolio_df.empty:
        return pd.DataFrame()
    rows = []
    today = datetime.now()
    for _, pos in portfolio_df.iterrows():
        ticker = pos["Ticker"]
        df = data_cache.get(ticker)
        if df is None or df.empty:
            rows.append({
                "Ticker": ticker, "Entry_Price": pos["Entry_Price"],
                "Current_Price": None, "P_L_%": None, "Days_Held": None,
                "Trailing_Stop": None, "ATR": None, "Status": "no data",
            })
            continue
        current = float(df["Close"].iloc[-1])
        entry   = float(pos["Entry_Price"])
        pl_pct  = (current - entry) / entry * 100
        days_held = None
        if "Entry_Date" in pos and pd.notna(pos["Entry_Date"]):
            days_held = (today - pos["Entry_Date"]).days
        atr = None; trailing = None
        if "ATR" in df.columns and not pd.isna(df["ATR"].iloc[-1]):
            atr = float(df["ATR"].iloc[-1])
            recent_low = float(df["Low"].tail(10).min())
            trailing = max(recent_low - cfg["risk"]["atr_stop_multiplier"] * atr, entry * 0.90)
        rows.append({
            "Ticker":         ticker,
            "Entry_Price":    round(entry, 2),
            "Current_Price":  round(current, 2),
            "P_L_%":          round(pl_pct, 2),
            "Days_Held":      days_held,
            "Trailing_Stop":  round(trailing, 2) if trailing else None,
            "ATR":            round(atr, 2) if atr else None,
            "Status":         ("below stop ⚠️" if (trailing and current < trailing) else "OK ✅"),
        })
    return pd.DataFrame(rows)


# ==============================================================================
# RUN SCANNER
# ==============================================================================
def run_scanner(
    config: dict,
    portfolio_df: Optional[pd.DataFrame] = None,
    progress_cb: Optional[Callable[[float, str], None]] = None,
    status_cb:   Optional[Callable[[str], None]] = None,
) -> dict:
    import time
    cfg = deepcopy(config)
    def _p(f, m):
        if progress_cb: progress_cb(f, m)
    def _s(m):
        if status_cb: status_cb(m)

    all_tickers = list(cfg["universe"])
    if cfg["macro"]["enabled"]:
        all_tickers.append(cfg["macro"]["spy_ticker"])
        if cfg["macro"]["vix_enabled"]:
            all_tickers.append(cfg["macro"]["vix_ticker"])
        if cfg["macro"]["vxv_enabled"]:
            all_tickers.append(cfg["macro"]["vxv_ticker"])
        if cfg["macro"]["sector_rs_enabled"]:
            all_tickers.extend(ALL_SECTOR_ETFS)
    if portfolio_df is not None and not portfolio_df.empty:
        all_tickers.extend(portfolio_df["Ticker"].tolist())
    all_tickers = sorted(set(all_tickers))

    _p(0.05, f"Preparing {len(all_tickers)} symbols…")
    t0 = time.time()
    _p(0.10, "Downloading OHLCV from Yahoo…")
    raw = fetch_ohlcv_batch(all_tickers, period=cfg["history_period"], status_cb=status_cb)
    t_dl = time.time() - t0
    _s(f"Fetched {len(raw)}/{len(all_tickers)} in {t_dl:.1f}s")

    t1 = time.time()
    _p(0.65, "Computing indicators…")
    cache = {}
    skipped = 0
    for t, df in raw.items():
        if len(df) < 50:
            skipped += 1; continue
        try:
            cache[t] = add_indicators(df, cfg)
        except Exception:
            continue
    t_ind = time.time() - t1

    _p(0.75, "Evaluating macro regime…")
    macro_ok, macro_info = get_macro_snapshot(cfg, cache)

    t2 = time.time()
    _p(0.85, "Running iron filter on universe…")
    if macro_ok:
        scan = evaluate_iron_filter_universe(cfg, cache)
        passers = scan["passers"]; diag = scan["diagnostics"]
    else:
        passers = pd.DataFrame(); diag = {}
    t_sc = time.time() - t2

    _p(0.95, "Evaluating portfolio…")
    portfolio = evaluate_portfolio(cfg, cache, portfolio_df)

    _p(1.0, "Done.")
    return {
        "passers":           passers,
        "portfolio_updates": portfolio,
        "diagnostics":       diag,
        "macro":             macro_info,
        "macro_ok":          macro_ok,
        "data_cache":        cache,
        "timestamp":         datetime.now(),
        "stats": {
            "requested":      len(all_tickers),
            "downloaded":     len(raw),
            "indicators_ok":  len(cache),
            "skipped_short":  skipped,
            "t_download_s":   round(t_dl, 1),
            "t_indicators_s": round(t_ind, 1),
            "t_screen_s":     round(t_sc, 1),
        },
    }
