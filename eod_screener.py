"""
================================================================================
 EOD STOCK SCREENER & PORTFOLIO MANAGEMENT  --  ENGINE
================================================================================
 Importable module. The CONFIG dict at the top is the SINGLE source of defaults;
 the Streamlit UI and the CLI both pass a (possibly overridden) copy of this
 dict into run_scanner().

 Public API:
     get_default_config()       -> dict
     load_universe(path)        -> list[str]
     load_portfolio(path)       -> DataFrame
     run_scanner(config,
                 portfolio_df=None,
                 progress_cb=None,
                 status_cb=None) -> dict with keys:
         "new_signals"      : DataFrame
         "portfolio_updates": DataFrame
         "macro"            : dict
         "macro_ok"         : bool

 Dependencies:
     pip install -r requirements.txt
================================================================================
"""

from __future__ import annotations

import os
import warnings
from copy import deepcopy
from datetime import datetime
from typing import Callable, Optional

import numpy as np
import pandas as pd
import yfinance as yf

# Try the original pandas-ta first; fall back to pandas-ta-classic
# (a maintained fork that supports modern Python/NumPy versions).
try:
    import pandas_ta as ta
except ImportError:
    import pandas_ta_classic as ta

warnings.filterwarnings("ignore")


# ==============================================================================
# DEFAULT CONFIGURATION
# ==============================================================================
DEFAULT_CONFIG = {
    # ----- Universe & I/O ---------------------------------------------------
    "universe":        [],                   # list of tickers
    "history_period":  "2y",
    "total_equity":    100_000.0,
    "min_bars":        250,                  # skip tickers without enough history

    # ----- Module 1: Macro environment --------------------------------------
    "macro": {
        "enabled":              True,
        "spy_ticker":           "SPY",
        "spy_sma_length":       50,

        "ad_line_sma_length":   20,
        "ad_line_enabled":      False,       # disabled by default (no data source)

        "vix_ticker":           "^VIX",
        "vxv_ticker":           "^VIX3M",
        "vix_ratio_threshold":  1.0,

        "sector_sma_length":    10,
        "sector_slope_lookback": 5,
        "sector_check_enabled": True,
    },

    # ----- Module 2: Screener ------------------------------------------------
    "screener": {
        "ma_lengths":           [20, 50, 200],    # set any item to None to skip
        "ma_type":              "sma",            # "sma" or "ema"

        "obv_lookback":         20,

        "keltner_ema_length":   20,
        "keltner_atr_length":   20,
        "keltner_multiplier":   2.0,
        "keltner_breakout_lookback": 5,   # accept breakouts in the last N bars

        "volume_sma_length":    20,
        "volume_multiplier":    1.5,

        "whipsaw_pct":          0.01,

        "divergence_enabled":   True,
        "divergence_lookback":  20,
        "rsi_length":           14,
    },

    # ----- Module 3: Risk Management ----------------------------------------
    "risk": {
        "atr_length":           14,
        "atr_stop_multiplier":  2.0,
        "support_lookback":     10,

        "target_method":        "atr",            # "atr" or "resistance"
        "atr_target_multiplier": 6.0,
        "resistance_lookback":  60,

        "min_rr_ratio":         3.0,
        "risk_per_trade_pct":   0.02,

        "trailing_sma_length":  50,
    },

    # ----- Sector ETF map ---------------------------------------------------
    "sector_map_default": "SPY",
    "sector_map": {
        # Tech
        "AAPL":"XLK","MSFT":"XLK","NVDA":"XLK","AMD":"XLK","INTC":"XLK",
        "ORCL":"XLK","CSCO":"XLK","ADBE":"XLK","CRM":"XLK","IBM":"XLK",
        "QCOM":"XLK","TXN":"XLK","AVGO":"XLK","NOW":"XLK","INTU":"XLK",
        # Communications
        "GOOGL":"XLC","GOOG":"XLC","META":"XLC","NFLX":"XLC","DIS":"XLC",
        "T":"XLC","VZ":"XLC","TMUS":"XLC","CMCSA":"XLC",
        # Consumer Discretionary
        "AMZN":"XLY","TSLA":"XLY","HD":"XLY","NKE":"XLY","MCD":"XLY",
        "SBUX":"XLY","LOW":"XLY","TJX":"XLY","BKNG":"XLY",
        # Financials
        "JPM":"XLF","V":"XLF","MA":"XLF","BAC":"XLF","WFC":"XLF",
        "GS":"XLF","MS":"XLF","C":"XLF","AXP":"XLF","BLK":"XLF",
        "SCHW":"XLF","BRK-B":"XLF",
        # Healthcare
        "UNH":"XLV","LLY":"XLV","JNJ":"XLV","PFE":"XLV","ABBV":"XLV",
        "MRK":"XLV","TMO":"XLV","ABT":"XLV","DHR":"XLV","BMY":"XLV",
        # Energy
        "XOM":"XLE","CVX":"XLE","COP":"XLE","SLB":"XLE","EOG":"XLE",
        "OXY":"XLE","PSX":"XLE","MPC":"XLE",
        # Industrials
        "CAT":"XLI","BA":"XLI","HON":"XLI","UPS":"XLI","UNP":"XLI",
        "DE":"XLI","RTX":"XLI","LMT":"XLI","GE":"XLI",
        # Staples
        "WMT":"XLP","COST":"XLP","PG":"XLP","KO":"XLP","PEP":"XLP",
        "MO":"XLP","PM":"XLP","CL":"XLP",
        # Utilities
        "NEE":"XLU","DUK":"XLU","SO":"XLU","AEP":"XLU","D":"XLU","XEL":"XLU",
        # Materials
        "LIN":"XLB","APD":"XLB","SHW":"XLB","FCX":"XLB","NEM":"XLB",
        # Real Estate
        "AMT":"XLRE","PLD":"XLRE","CCI":"XLRE","EQIX":"XLRE","SPG":"XLRE",
    },
}


def get_default_config() -> dict:
    """Return a deep copy of the default config so callers can mutate safely."""
    return deepcopy(DEFAULT_CONFIG)


# ==============================================================================
# STRATEGY PROFILES  --  Murphy-inspired presets
# ==============================================================================
# Each profile overrides Module 2 (screener) settings to match the strategy.
# Macro module is left untouched so the user can decide which environment to filter.
STRATEGY_PROFILES = {
    "custom": {
        "label": "🛠️ Custom (your sidebar settings)",
        "description": "Use the toggles and sliders in the sidebar exactly as configured.",
    },
    "breakout": {
        "label": "🚀 Profile 1: Pure Momentum Breakout",
        "description": (
            "Catches stocks exploding out of consolidation on heavy volume. "
            "Ride the wave with institutional money. Murphy: in trends, MAs rule and "
            "RSI is irrelevant (it stays overbought all the way up)."
        ),
        "screener": {
            # MA alignment ON: 20 > 50 (trend)
            "ma_alignment_enabled": True,
            "ma_lengths":           [20, 50],
            "ma_type":              "sma",
            # Keltner breakout ON, tight multiplier
            "keltner_enabled":           True,
            "keltner_ema_length":        20,
            "keltner_atr_length":        20,
            "keltner_multiplier":        1.5,
            "keltner_breakout_lookback": 5,
            # Volume surge ON, aggressive
            "volume_surge_enabled": True,
            "volume_multiplier":    1.25,
            "volume_sma_length":    20,
            # OBV ON (smart money confirmation)
            "obv_enabled":   True,
            "obv_lookback":  20,
            # RSI divergence OFF (Murphy: RSI is irrelevant in strong trends)
            "divergence_enabled": False,
            # Whipsaw filter ON (avoid false breakouts)
            "whipsaw_enabled": True,
            "whipsaw_pct":     0.01,
            # Profile-specific triggers OFF
            "pullback_enabled": False,
            "reversal_enabled": False,
        },
        "risk": {
            "atr_stop_multiplier": 2.0,  # wide stop for volatility
            "min_rr_ratio":        3.0,
        },
    },
    "pullback": {
        "label": "📉 Profile 2: Pullback / Dip Buy in Uptrend",
        "description": (
            "Safer, conservative entry: buy a healthy stock that's resting on its "
            "50-SMA support while RSI cools off. Murphy: markets move in waves — "
            "buy the support, don't chase highs."
        ),
        "screener": {
            # MA alignment uses only 50-SMA (price > 50 SMA, no 20/50/200 strict order)
            "ma_alignment_enabled": False,  # we use the pullback trigger instead
            "ma_lengths":           [50],
            "ma_type":              "sma",
            # Keltner OFF (we're not looking for a breakout)
            "keltner_enabled": False,
            # Volume surge OFF or very low (pullbacks have low volume)
            "volume_surge_enabled": False,
            "volume_multiplier":    1.0,
            "volume_sma_length":    20,
            # OBV optional
            "obv_enabled":  False,
            "obv_lookback": 20,
            # RSI divergence OFF (we WANT RSI to be low)
            "divergence_enabled": False,
            # Whipsaw OFF (no breakout to filter)
            "whipsaw_enabled": False,
            # Pullback trigger ON
            "pullback_enabled":        True,
            "pullback_tolerance_pct":  0.03,   # within 3% of 50-SMA
            "rsi_cooldown_lookback":   10,
            "rsi_length":              14,
            "reversal_enabled":        False,
        },
        "risk": {
            "atr_stop_multiplier": 1.5,  # tighter stop below the 50-SMA
            "min_rr_ratio":        3.0,
        },
    },
    "reversal": {
        "label": "🔄 Profile 3: Range Reversal / Oversold Bounce",
        "description": (
            "Stocks that crashed or chopped down to concrete-floor support, where "
            "institutions are quietly accumulating. Murphy: in ranges, MAs are "
            "useless (whipsaws) — RSI and volatility bands take over."
        ),
        "screener": {
            # MA alignment OFF entirely (Murphy's rule for ranges)
            "ma_alignment_enabled": False,
            "ma_lengths":           [],
            "ma_type":              "sma",
            # Keltner is used INVERSELY via reversal trigger; the standard upper-band
            # breakout check is OFF
            "keltner_enabled":           False,
            "keltner_ema_length":        20,
            "keltner_atr_length":        20,
            "keltner_multiplier":        2.0,
            "keltner_breakout_lookback": 5,
            # Volume surge ON (smart money accumulating at the bottom)
            "volume_surge_enabled": True,
            "volume_multiplier":    1.30,
            "volume_sma_length":    20,
            # OBV optional
            "obv_enabled":  False,
            "obv_lookback": 20,
            # RSI divergence OFF (we want oversold cross, not divergence)
            "divergence_enabled": False,
            # Whipsaw OFF
            "whipsaw_enabled": False,
            # Reversal trigger ON
            "pullback_enabled":  False,
            "reversal_enabled":  True,
            "reversal_lookback": 5,
            "rsi_length":        14,
        },
        "risk": {
            "atr_stop_multiplier": 1.0,  # tight stop below absolute low
            "min_rr_ratio":        3.0,
        },
    },
}


def apply_strategy_profile(cfg: dict, profile_key: str) -> dict:
    """Override cfg with a strategy profile's settings. 'custom' leaves cfg alone."""
    if profile_key not in STRATEGY_PROFILES or profile_key == "custom":
        return cfg
    profile = STRATEGY_PROFILES[profile_key]
    if "screener" in profile:
        cfg["screener"].update(profile["screener"])
    if "risk" in profile:
        cfg["risk"].update(profile["risk"])
    cfg["_active_profile"] = profile_key
    return cfg


# ==============================================================================
# DATA FETCHING  --  batched for speed
# ==============================================================================
def _flatten_yf(df: pd.DataFrame, ticker: Optional[str] = None) -> Optional[pd.DataFrame]:
    """yfinance can return MultiIndex columns; normalize to OHLCV single-level."""
    if df is None or df.empty:
        return None
    if isinstance(df.columns, pd.MultiIndex):
        # MultiIndex: ('Open', 'AAPL'), etc. Slice to one ticker if specified.
        if ticker and ticker in df.columns.get_level_values(1):
            df = df.xs(ticker, axis=1, level=1)
        else:
            df.columns = df.columns.get_level_values(0)
    df = df.rename(columns=str.title)
    needed = ["Open", "High", "Low", "Close", "Volume"]
    if not all(c in df.columns for c in needed):
        return None
    return df[needed].dropna()


def fetch_ohlcv(ticker: str, period: str = "2y") -> Optional[pd.DataFrame]:
    """Single-ticker fetch. Returns None on failure."""
    try:
        df = yf.download(ticker, period=period, progress=False, auto_adjust=False)
        return _flatten_yf(df, ticker)
    except Exception:
        return None


def fetch_ohlcv_batch(
    tickers: list[str],
    period: str = "2y",
    chunk_size: int = 50,
    status_cb: Optional[Callable[[str], None]] = None,
) -> dict[str, pd.DataFrame]:
    """Batched download. ~5-10x faster than serial for large universes."""
    out: dict[str, pd.DataFrame] = {}
    tickers = list(dict.fromkeys(tickers))  # dedupe, preserve order

    for i in range(0, len(tickers), chunk_size):
        chunk = tickers[i:i + chunk_size]
        if status_cb:
            status_cb(f"Downloading {i + len(chunk)}/{len(tickers)} tickers...")
        try:
            data = yf.download(
                tickers=chunk, period=period, progress=False,
                auto_adjust=False, group_by="ticker", threads=True,
            )
        except Exception:
            continue

        for t in chunk:
            try:
                if len(chunk) == 1:
                    sub = data
                else:
                    if t not in data.columns.get_level_values(0):
                        continue
                    sub = data[t]
                flat = _flatten_yf(sub, t)
                if flat is not None and not flat.empty:
                    out[t] = flat
            except Exception:
                continue
    return out


def fetch_ad_line() -> Optional[pd.DataFrame]:
    """
    PLACEHOLDER -- yfinance has no native NYSE Advance-Decline line.
    Plug in Stooq/Norgate/EODHD here and return DataFrame with 'Close' column
    indexed by date. The breadth check soft-passes when this returns None.
    """
    return None


def load_universe(path: str) -> list[str]:
    """Load a CSV with a 'Ticker' column. Returns list of uppercase tickers."""
    df = pd.read_csv(path)
    col = "Ticker" if "Ticker" in df.columns else df.columns[0]
    return df[col].astype(str).str.upper().str.strip().tolist()


def load_portfolio(path_or_df) -> pd.DataFrame:
    """Load positions. Accepts a file path OR an already-loaded DataFrame."""
    if isinstance(path_or_df, pd.DataFrame):
        df = path_or_df.copy()
    elif isinstance(path_or_df, str):
        if not os.path.exists(path_or_df):
            return pd.DataFrame(columns=["Ticker", "Entry_Price", "Entry_Date"])
        if path_or_df.lower().endswith((".xlsx", ".xls")):
            df = pd.read_excel(path_or_df)
        else:
            df = pd.read_csv(path_or_df)
    else:
        return pd.DataFrame(columns=["Ticker", "Entry_Price", "Entry_Date"])

    if df.empty:
        return df
    df["Ticker"]     = df["Ticker"].astype(str).str.upper().str.strip()
    df["Entry_Date"] = pd.to_datetime(df["Entry_Date"])
    df["Entry_Price"] = df["Entry_Price"].astype(float)
    return df


# ==============================================================================
# INDICATORS
# ==============================================================================
def _ma(series: pd.Series, length: int, kind: str = "sma") -> pd.Series:
    return ta.ema(series, length=length) if kind == "ema" else ta.sma(series, length=length)


def add_indicators(df: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    out = df.copy()
    sc, rk = cfg["screener"], cfg["risk"]

    for L in sc["ma_lengths"]:
        if L is not None:
            out[f"MA_{L}"] = _ma(out["Close"], L, sc["ma_type"])

    out["OBV"]      = ta.obv(out["Close"], out["Volume"])
    out["EMA_K"]    = ta.ema(out["Close"], length=sc["keltner_ema_length"])
    out["ATR_K"]    = ta.atr(out["High"], out["Low"], out["Close"], length=sc["keltner_atr_length"])
    out["KC_UPPER"] = out["EMA_K"] + sc["keltner_multiplier"] * out["ATR_K"]
    out["KC_LOWER"] = out["EMA_K"] - sc["keltner_multiplier"] * out["ATR_K"]
    out["VOL_SMA"]  = ta.sma(out["Volume"], length=sc["volume_sma_length"])
    out["RSI"]      = ta.rsi(out["Close"], length=sc["rsi_length"])
    out["ATR_R"]    = ta.atr(out["High"], out["Low"], out["Close"], length=rk["atr_length"])
    out["TREND_SMA"] = ta.sma(out["Close"], length=rk["trailing_sma_length"])
    return out


# ==============================================================================
# MODULE 1 -- MACRO / SECTOR ENVIRONMENT
# ==============================================================================
def check_market_trend(cfg: dict) -> tuple[bool, str]:
    m = cfg["macro"]
    if not m.get("spy_trend_enabled", True):
        return True, "SPY trend check disabled"
    spy = fetch_ohlcv(m["spy_ticker"], period="1y")
    if spy is None:
        return False, "SPY data unavailable"
    spy["SMA"] = ta.sma(spy["Close"], length=m["spy_sma_length"])
    last = spy.iloc[-1]
    ok = bool(last["Close"] > last["SMA"])
    return ok, f"SPY {last['Close']:.2f} {'>' if ok else '<='} SMA{m['spy_sma_length']} {last['SMA']:.2f}"


def check_market_breadth(cfg: dict) -> tuple[bool, str]:
    m = cfg["macro"]
    if not m["ad_line_enabled"]:
        return True, "AD line disabled"
    ad = fetch_ad_line()
    if ad is None or ad.empty:
        return True, "AD line data not configured -- skipped"
    ad["SMA"] = ta.sma(ad["Close"], length=m["ad_line_sma_length"])
    last = ad.iloc[-1]
    ok = bool(last["Close"] > last["SMA"])
    return ok, f"AD {last['Close']:.2f} {'>' if ok else '<='} SMA{m['ad_line_sma_length']}"


def check_vix_term_structure(cfg: dict) -> tuple[bool, str]:
    m = cfg["macro"]
    vix = fetch_ohlcv(m["vix_ticker"], period="3mo")
    vxv = fetch_ohlcv(m["vxv_ticker"], period="3mo")
    if vix is None or vxv is None:
        return False, "VIX/VXV data unavailable"
    df = pd.concat([vix["Close"].rename("VIX"), vxv["Close"].rename("VXV")], axis=1).dropna()
    if df.empty:
        return False, "VIX/VXV merge empty"
    ratio = df["VIX"].iloc[-1] / df["VXV"].iloc[-1]
    ok = bool(ratio < m["vix_ratio_threshold"])
    return ok, f"VIX/VXV={ratio:.3f} (<{m['vix_ratio_threshold']}: {ok})"


def check_sector_strength(ticker: str, cfg: dict, data_cache: dict) -> tuple[bool, str]:
    """Per-ticker. Uses cached sector ETF & SPY data."""
    m = cfg["macro"]
    if not m["sector_check_enabled"]:
        return True, "sector check disabled"
    sector_etf = cfg["sector_map"].get(ticker.upper(), cfg["sector_map_default"])
    if sector_etf == m["spy_ticker"]:
        return True, "no sector mapping -- skipped"

    sec = data_cache.get(sector_etf)
    if sec is None:
        sec = fetch_ohlcv(sector_etf, period="6mo")
    spy = data_cache.get(m["spy_ticker"])
    if spy is None:
        spy = fetch_ohlcv(m["spy_ticker"], period="6mo")
    if sec is None or spy is None:
        return False, "sector/SPY unavailable"

    ratio = (sec["Close"] / spy["Close"]).dropna()
    sma = ta.sma(ratio, length=m["sector_sma_length"]).dropna()
    if len(sma) < m["sector_slope_lookback"] + 1:
        return False, "sector SMA too short"
    slope = sma.iloc[-1] - sma.iloc[-1 - m["sector_slope_lookback"]]
    return bool(slope > 0), f"{sector_etf}/SPY slope={slope:+.4f}"


def macro_kill_switch(cfg: dict) -> tuple[bool, dict]:
    if not cfg["macro"]["enabled"]:
        return True, {"status": "disabled"}
    trend_ok, t_msg   = check_market_trend(cfg)
    breadth_ok, b_msg = check_market_breadth(cfg)
    vix_ok, v_msg     = check_vix_term_structure(cfg)
    overall = trend_ok and breadth_ok and vix_ok
    return overall, {
        "market_trend":   t_msg,
        "market_breadth": b_msg,
        "vix_term":       v_msg,
        "overall":        "PASS" if overall else "FAIL",
    }


def get_macro_snapshot(cfg: dict) -> dict:
    """
    Return numeric macro values for UI display (not just pass/fail strings).
    This is what the Streamlit app calls to show the "Market State" panel.
    """
    snap = {
        "spy_price": None, "spy_sma": None, "spy_ok": None,
        "vix": None, "vxv": None, "vix_ratio": None, "vix_ok": None,
        "vix_threshold": cfg["macro"]["vix_ratio_threshold"],
        "spy_sma_len":   cfg["macro"]["spy_sma_length"],
    }
    m = cfg["macro"]

    spy = fetch_ohlcv(m["spy_ticker"], period="1y")
    if spy is not None and not spy.empty:
        spy["SMA"] = ta.sma(spy["Close"], length=m["spy_sma_length"])
        last = spy.iloc[-1]
        snap["spy_price"] = float(last["Close"])
        snap["spy_sma"]   = float(last["SMA"]) if not pd.isna(last["SMA"]) else None
        if snap["spy_sma"]:
            snap["spy_ok"] = snap["spy_price"] > snap["spy_sma"]

    vix = fetch_ohlcv(m["vix_ticker"], period="3mo")
    vxv = fetch_ohlcv(m["vxv_ticker"], period="3mo")
    if vix is not None and vxv is not None:
        df = pd.concat([vix["Close"].rename("VIX"),
                        vxv["Close"].rename("VXV")], axis=1).dropna()
        if not df.empty:
            snap["vix"] = float(df["VIX"].iloc[-1])
            snap["vxv"] = float(df["VXV"].iloc[-1])
            snap["vix_ratio"] = snap["vix"] / snap["vxv"]
            snap["vix_ok"] = snap["vix_ratio"] < m["vix_ratio_threshold"]

    snap["overall_ok"] = bool(snap.get("spy_ok") and snap.get("vix_ok"))
    return snap


# ==============================================================================
# MODULE 2 -- SCREENER
# ==============================================================================
def check_ma_alignment(df: pd.DataFrame, cfg: dict) -> bool:
    if not cfg["screener"].get("ma_alignment_enabled", True):
        return True
    lengths = [L for L in cfg["screener"]["ma_lengths"] if L is not None]
    if not lengths:
        return True
    row = df.iloc[-1]
    vals = [row["Close"]] + [row.get(f"MA_{L}") for L in lengths]
    if any(pd.isna(v) for v in vals):
        return False
    return all(vals[i] > vals[i + 1] for i in range(len(vals) - 1))


def check_obv_breakout(df: pd.DataFrame, cfg: dict) -> bool:
    if not cfg["screener"].get("obv_enabled", True):
        return True
    lb = cfg["screener"]["obv_lookback"]
    if len(df) < lb + 1:
        return False
    obv = df["OBV"]
    return bool(obv.iloc[-1] >= obv.iloc[-lb - 1:-1].max())


def check_keltner_breakout(df: pd.DataFrame, cfg: dict) -> bool:
    """
    Detect a recent Keltner upper-band breakout.
    Default: the close must currently be above the upper band, AND a fresh
    cross from below must have occurred within the last `breakout_lookback`
    bars (default 5). This is looser than "must cross today" so the screener
    catches stocks that broke out recently and are still above the band.
    """
    if not cfg["screener"].get("keltner_enabled", True):
        return True
    lb = cfg["screener"].get("keltner_breakout_lookback", 5)
    if len(df) < lb + 2:
        return False
    if pd.isna(df["KC_UPPER"].iloc[-1]) or df["Close"].iloc[-1] <= df["KC_UPPER"].iloc[-1]:
        return False
    # Find a cross from <= to > within the last lb bars
    window = df.iloc[-lb - 1:]
    for i in range(1, len(window)):
        prev_c, prev_u = window["Close"].iloc[i - 1], window["KC_UPPER"].iloc[i - 1]
        curr_c, curr_u = window["Close"].iloc[i],     window["KC_UPPER"].iloc[i]
        if pd.isna(prev_u) or pd.isna(curr_u):
            continue
        if prev_c <= prev_u and curr_c > curr_u:
            return True
    return False


def check_volume_surge(df: pd.DataFrame, cfg: dict) -> bool:
    if not cfg["screener"].get("volume_surge_enabled", True):
        return True
    row = df.iloc[-1]
    if pd.isna(row["VOL_SMA"]) or row["VOL_SMA"] == 0:
        return False
    return bool(row["Volume"] > cfg["screener"]["volume_multiplier"] * row["VOL_SMA"])


def check_whipsaw_filter(df: pd.DataFrame, cfg: dict) -> bool:
    if not cfg["screener"].get("whipsaw_enabled", True):
        return True
    row = df.iloc[-1]
    if pd.isna(row["KC_UPPER"]):
        return False
    return bool(row["Close"] >= row["KC_UPPER"] * (1 + cfg["screener"]["whipsaw_pct"]))


def check_divergence_blocker(df: pd.DataFrame, cfg: dict) -> bool:
    """Return True if PASSES (no bearish divergence)."""
    sc = cfg["screener"]
    if not sc["divergence_enabled"]:
        return True
    lb = sc["divergence_lookback"]
    if len(df) < lb * 2:
        return True

    curr_close = df["Close"].iloc[-1]
    if curr_close < df["Close"].iloc[-lb:].max():
        return True  # not at a new high -> blocker inactive

    prev_window = df.iloc[-2 * lb:-lb]
    if prev_window.empty:
        return True
    prev_peak_idx = prev_window["Close"].idxmax()
    prev_peak_rsi = prev_window.loc[prev_peak_idx, "RSI"]
    curr_rsi = df["RSI"].iloc[-1]
    if pd.isna(prev_peak_rsi) or pd.isna(curr_rsi):
        return True
    return not (curr_rsi < prev_peak_rsi)


def screen_stock(df: pd.DataFrame, cfg: dict) -> tuple[bool, dict]:
    checks = {
        "ma_alignment":     check_ma_alignment(df, cfg),
        "obv_breakout":     check_obv_breakout(df, cfg),
        "keltner_breakout": check_keltner_breakout(df, cfg),
        "volume_surge":     check_volume_surge(df, cfg),
        "whipsaw_filter":   check_whipsaw_filter(df, cfg),
        "divergence_ok":    check_divergence_blocker(df, cfg),
        "pullback_trigger": check_pullback_trigger(df, cfg),
        "reversal_trigger": check_reversal_trigger(df, cfg),
    }
    return all(checks.values()), checks


# ==============================================================================
# PROFILE-SPECIFIC TRIGGERS  (Pullback, Reversal)
# ==============================================================================
def check_pullback_trigger(df: pd.DataFrame, cfg: dict) -> bool:
    """
    Pullback in uptrend trigger (Murphy's classic dip-buy):
      - Price must be near (within `pullback_tolerance_pct`) the 50-SMA.
      - Price is above the 50-SMA (uptrend still intact).
      - RSI dipped below 50 in the last `rsi_cooldown_lookback` bars AND is now
        turning back up (today's RSI > yesterday's RSI).
    """
    sc = cfg["screener"]
    if not sc.get("pullback_enabled", False):
        return True
    if len(df) < 60:
        return False

    # Need a 50-SMA column
    sma50_col = "MA_50"
    if sma50_col not in df.columns or pd.isna(df[sma50_col].iloc[-1]):
        return False

    last = df.iloc[-1]
    sma50 = float(last[sma50_col])
    price = float(last["Close"])

    # Uptrend intact
    if price <= sma50:
        return False

    # Near the SMA50 (within tolerance %)
    tol = sc.get("pullback_tolerance_pct", 0.03)
    if (price - sma50) / sma50 > tol:
        return False

    # RSI cooled and now turning up
    lb = sc.get("rsi_cooldown_lookback", 10)
    rsi = df["RSI"].iloc[-lb:]
    if pd.isna(rsi.iloc[-1]) or pd.isna(rsi.iloc[-2]):
        return False
    if rsi.min() >= 50:
        return False  # never cooled
    if rsi.iloc[-1] <= rsi.iloc[-2]:
        return False  # not turning up
    return True


def check_reversal_trigger(df: pd.DataFrame, cfg: dict) -> bool:
    """
    Range / oversold reversal trigger (Linda Raschke / Murphy oscillator setup):
      - Within the last `reversal_lookback` bars, the LOW dipped below the
        lower Keltner band (extreme oversold).
      - Today the close is back inside the Keltner channel (above lower band).
      - RSI is currently above 30 and was below 30 within the lookback
        (oversold cross from below).
    """
    sc = cfg["screener"]
    if not sc.get("reversal_enabled", False):
        return True
    if len(df) < 30:
        return False
    if "KC_LOWER" not in df.columns:
        return False

    lb = sc.get("reversal_lookback", 5)
    window = df.iloc[-lb - 1:]
    last = df.iloc[-1]

    # Back inside channel today
    if pd.isna(last["KC_LOWER"]) or last["Close"] <= last["KC_LOWER"]:
        return False

    # At some point in the window, the LOW pierced the lower band
    pierced = (window["Low"] < window["KC_LOWER"]).any()
    if not pierced:
        return False

    # RSI: was oversold, now recovered
    rsi_window = df["RSI"].iloc[-lb - 1:]
    if pd.isna(last["RSI"]) or last["RSI"] <= 30:
        return False
    if (rsi_window < 30).sum() == 0:
        return False
    return True


# ==============================================================================
# MODULE 3 -- RISK & PORTFOLIO
# ==============================================================================
def find_local_support(df: pd.DataFrame, lookback: int) -> float:
    return float(df["Low"].iloc[-lookback:].min())


def calculate_initial_stop(df: pd.DataFrame, cfg: dict) -> float:
    rk = cfg["risk"]
    support = find_local_support(df, rk["support_lookback"])
    atr = float(df["ATR_R"].iloc[-1])
    return support - rk["atr_stop_multiplier"] * atr


def calculate_target(df: pd.DataFrame, entry: float, cfg: dict) -> float:
    rk = cfg["risk"]
    if rk["target_method"] == "atr":
        atr = float(df["ATR_R"].iloc[-1])
        return entry + rk["atr_target_multiplier"] * atr
    hi = df["High"].iloc[-rk["resistance_lookback"]:-1].max()
    return float(hi) if not pd.isna(hi) else entry


def check_rr_ratio(entry: float, stop: float, target: float, cfg: dict) -> tuple[bool, float]:
    risk_amt = entry - stop
    if risk_amt <= 0:
        return False, 0.0
    rr = (target - entry) / risk_amt
    return rr >= cfg["risk"]["min_rr_ratio"], rr


def calculate_position_size(entry: float, stop: float, cfg: dict) -> int:
    per_share_risk = entry - stop
    if per_share_risk <= 0:
        return 0
    dollar_risk = cfg["total_equity"] * cfg["risk"]["risk_per_trade_pct"]
    return int(dollar_risk // per_share_risk)


def calculate_trailing_stop(df: pd.DataFrame, entry_date, prior_stop, cfg: dict) -> float:
    rk = cfg["risk"]
    entry_date = pd.to_datetime(entry_date)
    in_trade = df[df.index >= entry_date]
    if in_trade.empty:
        in_trade = df.tail(rk["support_lookback"])

    swing_low = float(in_trade["Low"].iloc[-rk["support_lookback"]:].min())
    trend_sma = df["TREND_SMA"].iloc[-1]
    if pd.isna(trend_sma):
        trend_sma = swing_low
    floor = max(swing_low, float(trend_sma))
    atr = float(df["ATR_R"].iloc[-1])
    raw = floor - rk["atr_stop_multiplier"] * atr

    if prior_stop is None or pd.isna(prior_stop):
        return raw
    return max(raw, float(prior_stop))


def check_volume_exit(df: pd.DataFrame, trailing_stop: float) -> bool:
    row = df.iloc[-1]
    if pd.isna(row["VOL_SMA"]):
        return False
    return bool(row["Close"] < trailing_stop and row["Volume"] > row["VOL_SMA"])


# ==============================================================================
# ORCHESTRATION
# ==============================================================================
def evaluate_new_signals(cfg: dict, data_cache: dict) -> tuple[pd.DataFrame, dict]:
    """Return (signals_df, diagnostics_dict).
    Diagnostics count how many tickers passed each filter step - useful for
    debugging "0 results" and showing the user where the funnel narrows.
    """
    rows = []
    diag = {
        "evaluated": 0, "sector_rs_ok": 0,
        "ma_alignment": 0, "obv_breakout": 0, "keltner_breakout": 0,
        "volume_surge": 0, "whipsaw_filter": 0, "divergence_ok": 0,
        "pullback_trigger": 0, "reversal_trigger": 0,
        "all_filters_ok": 0, "valid_stop": 0, "rr_ok": 0, "final": 0,
    }

    for ticker in cfg["universe"]:
        df = data_cache.get(ticker)
        if df is None or len(df) < cfg["min_bars"]:
            continue
        diag["evaluated"] += 1

        if cfg["macro"]["enabled"]:
            rs_ok, _ = check_sector_strength(ticker, cfg, data_cache)
            if not rs_ok:
                continue
        diag["sector_rs_ok"] += 1

        # Run each filter individually for diagnostics
        checks = {
            "ma_alignment":     check_ma_alignment(df, cfg),
            "obv_breakout":     check_obv_breakout(df, cfg),
            "keltner_breakout": check_keltner_breakout(df, cfg),
            "volume_surge":     check_volume_surge(df, cfg),
            "whipsaw_filter":   check_whipsaw_filter(df, cfg),
            "divergence_ok":    check_divergence_blocker(df, cfg),
            "pullback_trigger": check_pullback_trigger(df, cfg),
            "reversal_trigger": check_reversal_trigger(df, cfg),
        }
        for k, v in checks.items():
            if v:
                diag[k] += 1
        if not all(checks.values()):
            continue
        diag["all_filters_ok"] += 1

        entry = float(df["Close"].iloc[-1])
        stop  = calculate_initial_stop(df, cfg)
        if stop >= entry:
            continue
        diag["valid_stop"] += 1
        target = calculate_target(df, entry, cfg)
        rr_ok, rr = check_rr_ratio(entry, stop, target, cfg)
        if not rr_ok:
            continue
        diag["rr_ok"] += 1
        shares = calculate_position_size(entry, stop, cfg)
        if shares <= 0:
            continue
        diag["final"] += 1

        rows.append({
            "Ticker":        ticker,
            "Entry_Price":   round(entry, 2),
            "Initial_Stop":  round(stop, 2),
            "Target":        round(target, 2),
            "R_R_Ratio":     round(rr, 2),
            "Shares_To_Buy": shares,
            "Risk_$":        round((entry - stop) * shares, 2),
        })
    return pd.DataFrame(rows), diag


def evaluate_portfolio(cfg: dict, data_cache: dict, portfolio: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, pos in portfolio.iterrows():
        ticker = pos["Ticker"]
        df = data_cache.get(ticker)
        if df is None or df.empty:
            rows.append({"Ticker": ticker, "Current_Price": np.nan,
                         "Trailing_Stop": np.nan, "Action": "DATA_MISSING"})
            continue
        prior_stop = pos.get("Current_Stop", None)
        tstop = calculate_trailing_stop(df, pos["Entry_Date"], prior_stop, cfg)
        current = float(df["Close"].iloc[-1])
        sell = check_volume_exit(df, tstop)
        rows.append({
            "Ticker":        ticker,
            "Entry_Price":   pos["Entry_Price"],
            "Entry_Date":    pd.to_datetime(pos["Entry_Date"]).date(),
            "Current_Price": round(current, 2),
            "Trailing_Stop": round(tstop, 2),
            "Unrealized_%":  round((current / pos["Entry_Price"] - 1) * 100, 2),
            "Action":        "SELL" if sell else "HOLD",
        })
    return pd.DataFrame(rows)


def run_scanner(
    config: dict,
    portfolio_df: Optional[pd.DataFrame] = None,
    progress_cb: Optional[Callable[[float, str], None]] = None,
    status_cb:   Optional[Callable[[str], None]] = None,
) -> dict:
    """
    Run the full pipeline. Both callbacks are optional and used by the UI.
        progress_cb(fraction_0_to_1, message_str)
        status_cb(message_str)
    """
    cfg = deepcopy(config)
    def _p(f, m=""):
        if progress_cb: progress_cb(min(max(f, 0.0), 1.0), m)
    def _s(m):
        if status_cb: status_cb(m)

    # 1) Macro
    _p(0.05, "Checking macro environment...")
    macro_ok, macro_info = macro_kill_switch(cfg)
    _s(f"Macro: {macro_info.get('overall', 'n/a')}")

    # 2) Build full ticker set: universe + portfolio + sector ETFs + SPY
    portfolio = load_portfolio(portfolio_df) if portfolio_df is not None else pd.DataFrame(
        columns=["Ticker", "Entry_Price", "Entry_Date"])
    sector_etfs = set(cfg["sector_map"].values())
    sector_etfs.add(cfg["macro"]["spy_ticker"])

    all_tickers = sorted(set(cfg["universe"]) |
                         set(portfolio["Ticker"].tolist()) |
                         sector_etfs)

    # 3) Batched OHLCV download
    _p(0.10, f"Fetching OHLCV for {len(all_tickers)} symbols...")
    raw_cache = fetch_ohlcv_batch(
        all_tickers, period=cfg["history_period"], status_cb=status_cb,
    )
    _s(f"Fetched {len(raw_cache)}/{len(all_tickers)} symbols")

    # 4) Enrich with indicators
    _p(0.70, "Computing indicators...")
    data_cache = {}
    for t, df in raw_cache.items():
        if len(df) >= 50:
            try:
                data_cache[t] = add_indicators(df, cfg)
            except Exception:
                continue

    # 5) Module 2 (gated by macro)
    _p(0.85, "Screening universe...")
    if macro_ok:
        new_signals, diagnostics = evaluate_new_signals(cfg, data_cache)
    else:
        new_signals, diagnostics = pd.DataFrame(), {}

    # 6) Module 3 (always run; risk mgmt must work even when macro fails)
    _p(0.95, "Evaluating portfolio...")
    portfolio_updates = evaluate_portfolio(cfg, data_cache, portfolio)

    _p(1.0, "Done.")
    return {
        "new_signals":       new_signals,
        "portfolio_updates": portfolio_updates,
        "diagnostics":       diagnostics,
        "macro":             macro_info,
        "macro_ok":          macro_ok,
        "data_cache":        data_cache,    # exposed for charting in the UI
        "timestamp":         datetime.now(),
    }
