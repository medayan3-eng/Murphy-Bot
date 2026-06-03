"""
================================================================================
 EOD STOCK SCREENER  --  STREAMLIT APP
================================================================================
 Run locally:
     streamlit run app.py

 Deploy to Streamlit Community Cloud:
     1. Push this repo to GitHub.
     2. Connect the repo at https://share.streamlit.io
     3. Set app.py as the main file. Python 3.10+.
================================================================================
"""
from __future__ import annotations

import io
import os
from datetime import datetime

import pandas as pd
import streamlit as st

from eod_screener import (
    STRATEGY_PROFILES,
    apply_strategy_profile,
    get_default_config,
    get_macro_snapshot,
    load_portfolio,
    load_universe,
    run_scanner,
)

# ==============================================================================
# Page setup
# ==============================================================================
st.set_page_config(
    page_title="EOD Screener Terminal",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ------------------------------------------------------------------------------
# Professional dark "trading terminal" styling
# ------------------------------------------------------------------------------
st.markdown("""
<style>
    /* Import a professional monospace font for numbers */
    @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;700&family=Inter:wght@400;500;600;700&display=swap');

    /* ---- Global ---- */
    html, body, [class*="css"] {
        font-family: 'Inter', -apple-system, sans-serif !important;
    }

    /* ---- Main container ---- */
    .main .block-container {
        padding-top: 1.5rem;
        padding-bottom: 3rem;
        max-width: 1400px;
    }

    /* ---- Header banner (gradient with subtle border) ---- */
    .terminal-header {
        background: linear-gradient(135deg, #0a1929 0%, #1a3a5c 50%, #0d2847 100%);
        padding: 1.5rem 2rem;
        border-radius: 12px;
        border-left: 4px solid #00d4ff;
        margin-bottom: 1.5rem;
        box-shadow: 0 4px 20px rgba(0, 212, 255, 0.15);
    }
    .terminal-header h1 {
        color: #ffffff !important;
        font-size: 1.85rem !important;
        font-weight: 700 !important;
        margin: 0 !important;
        letter-spacing: -0.5px;
    }
    .terminal-header .subtitle {
        color: #8bb8d9;
        font-size: 0.9rem;
        margin-top: 0.4rem;
        font-weight: 400;
    }
    .terminal-header .ticker-tape {
        color: #00d4ff;
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.75rem;
        letter-spacing: 2px;
        margin-top: 0.6rem;
        opacity: 0.7;
    }

    /* ---- Section headers ---- */
    h2, h3 {
        color: #1a3a5c !important;
        font-weight: 600 !important;
        letter-spacing: -0.3px;
    }

    /* ---- Metric cards (top of main panel) ---- */
    [data-testid="stMetricValue"] {
        font-family: 'JetBrains Mono', monospace !important;
        font-weight: 700 !important;
        font-size: 1.6rem !important;
    }
    [data-testid="stMetricLabel"] {
        font-weight: 500 !important;
        text-transform: uppercase;
        letter-spacing: 0.8px;
        font-size: 0.72rem !important;
        opacity: 0.75;
    }
    [data-testid="stMetric"] {
        background: linear-gradient(180deg, #f8fafc 0%, #f1f5f9 100%);
        padding: 1rem 1.2rem;
        border-radius: 10px;
        border-left: 3px solid #00d4ff;
        box-shadow: 0 1px 3px rgba(0,0,0,0.04);
    }

    /* ---- Buttons ---- */
    .stButton button {
        font-weight: 600 !important;
        letter-spacing: 0.3px;
        border-radius: 8px !important;
        transition: all 0.2s ease;
    }
    .stButton button[kind="primary"] {
        background: linear-gradient(135deg, #00a8cc 0%, #006d8f 100%) !important;
        border: none !important;
        box-shadow: 0 2px 8px rgba(0, 168, 204, 0.3);
    }
    .stButton button[kind="primary"]:hover {
        transform: translateY(-1px);
        box-shadow: 0 4px 12px rgba(0, 168, 204, 0.5);
    }

    /* ---- Tabs ---- */
    .stTabs [data-baseweb="tab-list"] {
        gap: 4px;
        border-bottom: 2px solid #e2e8f0;
    }
    .stTabs [data-baseweb="tab"] {
        font-weight: 600 !important;
        padding: 0.7rem 1.2rem !important;
        border-radius: 8px 8px 0 0 !important;
    }
    .stTabs [aria-selected="true"] {
        background: linear-gradient(180deg, #00d4ff20 0%, transparent 100%) !important;
        border-bottom: 3px solid #00a8cc !important;
    }

    /* ---- DataFrames ---- */
    .stDataFrame {
        border-radius: 8px;
        overflow: hidden;
        box-shadow: 0 1px 3px rgba(0,0,0,0.06);
    }

    /* ---- Sidebar polish ---- */
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #f8fafc 0%, #f1f5f9 100%);
        border-right: 1px solid #e2e8f0;
    }
    [data-testid="stSidebar"] h2 {
        color: #0a1929 !important;
        font-size: 1.1rem !important;
        text-transform: uppercase;
        letter-spacing: 1px;
        padding-bottom: 0.5rem;
        border-bottom: 2px solid #00d4ff;
        margin-bottom: 1rem !important;
    }

    /* ---- Status badges ---- */
    .status-badge {
        display: inline-block;
        padding: 4px 12px;
        border-radius: 20px;
        font-size: 0.75rem;
        font-weight: 600;
        letter-spacing: 0.5px;
        text-transform: uppercase;
    }
    .status-green {
        background: #d1fae5;
        color: #065f46;
        border: 1px solid #6ee7b7;
    }
    .status-yellow {
        background: #fef3c7;
        color: #92400e;
        border: 1px solid #fcd34d;
    }
    .status-red {
        background: #fee2e2;
        color: #991b1b;
        border: 1px solid #fca5a5;
    }

    /* ---- Info boxes ---- */
    .stAlert {
        border-radius: 8px !important;
        border-left-width: 4px !important;
    }

    /* ---- Hide Streamlit branding (keep header visible for mobile sidebar toggle!) ---- */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    /* DO NOT hide `header` — that hides the hamburger menu (☰) on mobile,
       which is the only way to open the sidebar on small screens. */

    /* ---- Section divider ---- */
    .section-divider {
        height: 1px;
        background: linear-gradient(90deg, transparent 0%, #cbd5e1 50%, transparent 100%);
        margin: 2rem 0 1.5rem 0;
    }
</style>
""", unsafe_allow_html=True)

# Professional header banner
st.markdown("""
<div class="terminal-header">
    <h1>📈 EOD SCREENER TERMINAL</h1>
    <div class="subtitle">Macro Regime Filter · Multi-Indicator Technical Screener · ATR Risk Engine · Trailing Exit Logic</div>
    <div class="ticker-tape">●  LIVE EOD ANALYTICS  ●  ATR-BASED RISK MODEL  ●  LIQUIDITY-GATED UNIVERSE  ●</div>
</div>
""", unsafe_allow_html=True)

UNIVERSE_DIR = "universes"


# ==============================================================================
# Helpers
# ==============================================================================
@st.cache_data(show_spinner=False)
def _load_universe_cached(path: str) -> list[str]:
    return load_universe(path)


@st.cache_data(ttl=600, show_spinner=False)
def _macro_snapshot_cached(spy_sma_len: int, vix_threshold: float) -> dict:
    """Cached for 10 minutes so reopening the page doesn't re-download."""
    cfg = get_default_config()
    cfg["macro"]["spy_sma_length"]      = spy_sma_len
    cfg["macro"]["vix_ratio_threshold"] = vix_threshold
    return get_macro_snapshot(cfg)


def _to_excel_bytes(new_signals: pd.DataFrame,
                    portfolio_updates: pd.DataFrame,
                    macro_info: dict) -> bytes:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as xl:
        (new_signals if not new_signals.empty
            else pd.DataFrame([{"Note": "No new signals"}])).to_excel(
            xl, sheet_name="New_Signals", index=False)
        (portfolio_updates if not portfolio_updates.empty
            else pd.DataFrame([{"Note": "Empty portfolio"}])).to_excel(
            xl, sheet_name="Portfolio", index=False)
        pd.DataFrame(list(macro_info.items()),
                     columns=["Check", "Result"]).to_excel(
            xl, sheet_name="Macro", index=False)
    return buf.getvalue()


# ==============================================================================
# Sidebar -- CONFIG controls
# ==============================================================================
with st.sidebar:
    st.header("⚙️ Configuration")

    # ---- Universe -----------------------------------------------------------
    st.subheader("Universe")
    universe_choice = st.radio(
        "Source",
        ["🔥 High-Momentum (531)", "S&P 500 (502)", "Russell 2000 (1,909)",
         "Both S&P + R2K (2,411)", "Custom tickers", "Upload CSV"],
        index=0,
    )

    custom_universe: list[str] = []
    if universe_choice == "🔥 High-Momentum (531)":
        custom_universe = _load_universe_cached(f"{UNIVERSE_DIR}/high_momentum.csv")
    elif universe_choice == "S&P 500 (502)":
        custom_universe = _load_universe_cached(f"{UNIVERSE_DIR}/sp500.csv")
    elif universe_choice == "Russell 2000 (1,909)":
        custom_universe = _load_universe_cached(f"{UNIVERSE_DIR}/russell2000.csv")
    elif universe_choice == "Both S&P + R2K (2,411)":
        sp = _load_universe_cached(f"{UNIVERSE_DIR}/sp500.csv")
        r2 = _load_universe_cached(f"{UNIVERSE_DIR}/russell2000.csv")
        custom_universe = sorted(set(sp) | set(r2))
    elif universe_choice == "Custom tickers":
        text = st.text_area(
            "Tickers (comma- or newline-separated)",
            value="AAPL, MSFT, NVDA, AMD, GOOGL, META, AMZN, TSLA",
            height=120,
        )
        custom_universe = [t.strip().upper() for t in text.replace("\n", ",").split(",") if t.strip()]
    elif universe_choice == "Upload CSV":
        up = st.file_uploader("CSV with a 'Ticker' column", type=["csv"], key="univ_up")
        if up is not None:
            df = pd.read_csv(up)
            col = "Ticker" if "Ticker" in df.columns else df.columns[0]
            custom_universe = df[col].astype(str).str.upper().str.strip().tolist()

    # Adapt the slider's upper bound to the actual universe size.
    # Use a key tied to the universe choice so the slider resets when the
    # universe changes (otherwise Streamlit keeps the old value, which can
    # be smaller than the new universe and looks like a bug).
    universe_size = max(len(custom_universe), 10)
    default_max = universe_size   # scan ALL by default
    slider_key = f"max_tickers_{universe_choice}_{universe_size}"
    max_tickers = st.slider(
        "Max tickers to scan",
        min_value=10, max_value=universe_size,
        value=default_max, step=10,
        key=slider_key,
        help=f"You have {universe_size} tickers available. "
             f"Default is to scan all. Cap lower to test faster. "
             f"~200 tickers ≈ 1–2 min, ~500 ≈ 3–5 min.",
    )
    if len(custom_universe) > max_tickers:
        custom_universe = custom_universe[:max_tickers]
    st.caption(f"**{len(custom_universe)}** of {universe_size} tickers selected")

    # ---- Equity & risk ------------------------------------------------------
    st.subheader("Account")
    total_equity      = st.slider("Total equity ($)",
                                  min_value=1_000, max_value=50_000,
                                  value=10_000, step=500,
                                  help="Your total trading account size. "
                                       "The screener uses this to size positions.")
    risk_per_trade    = st.slider("Risk per trade (%)", 0.1, 5.0, 2.0, 0.1) / 100

    # ---- Macro module -------------------------------------------------------
    st.subheader("Module 1 — Macro")
    st.caption("Each check has an ON/OFF toggle. Disabled checks are skipped (treated as PASS).")

    macro_enabled = st.checkbox("Enable macro kill-switch (master)", value=True,
                                help="If OFF, all macro checks are bypassed and "
                                     "new signals are always allowed.")

    # SPY trend check
    spy_trend_on = st.checkbox("✅ SPY trend check", value=True,
                               help="SPY price must be above its SMA")
    if spy_trend_on:
        spy_sma = st.slider("  SPY trend SMA length", 5, 400, 50, key="spy_sma",
                            help="SPY must close above this moving average")
    else:
        spy_sma = 50  # placeholder, ignored

    # Sector relative-strength check
    sector_check = st.checkbox("✅ Sector relative-strength check", value=True,
                               help="Stock's sector ETF must be outperforming SPY")
    if sector_check:
        sector_sma = st.slider("  Sector ratio SMA length", 3, 60, 10, key="sector_sma",
                               help="SMA length on sector/SPY ratio")
    else:
        sector_sma = 10

    # AD-line check
    ad_line_enabled = st.checkbox("⬜ AD-line check", value=False,
                                  help="Needs an external data source. "
                                       "yfinance does not provide this.")

    vix_threshold = 1.0  # Fixed; displayed on main screen


    # ---- Screener module ----------------------------------------------------
    st.subheader("Module 2 — Screener")
    st.caption("Each filter has an ON/OFF toggle. Turn off filters to find more candidates.")

    # MA alignment
    ma_align_on = st.checkbox("✅ Moving-average alignment", value=True,
                              help="Close > MA1 > MA2 > MA3 (trend filter)")
    if ma_align_on:
        ma_type  = st.selectbox("  MA type", ["sma", "ema"], index=0, key="ma_type")
        ma_input = st.text_input("  MA lengths (comma-sep, 'None' to skip a slot)",
                                 value="20, 50, 200", key="ma_input")
        ma_lengths = []
        for tok in ma_input.split(","):
            tok = tok.strip()
            if tok.lower() in ("none", ""):
                ma_lengths.append(None)
            else:
                try: ma_lengths.append(int(tok))
                except ValueError: pass
    else:
        ma_type, ma_lengths = "sma", []  # empty list = filter disabled

    # OBV breakout
    obv_on = st.checkbox("✅ OBV breakout", value=True,
                        help="On-Balance Volume must be at a new local high")
    if obv_on:
        obv_lookback = st.slider("  OBV lookback (days)", 5, 60, 20, key="obv_lb")
    else:
        obv_lookback = 20

    # Keltner breakout
    keltner_on = st.checkbox("✅ Keltner channel breakout", value=True,
                            help="Price crossed above the upper Keltner band")
    if keltner_on:
        keltner_ema      = st.slider("  Keltner EMA length", 5, 60, 20, key="kc_ema")
        keltner_atr      = st.slider("  Keltner ATR length", 5, 60, 20, key="kc_atr")
        keltner_mult     = st.slider("  Keltner ATR multiplier", 1.0, 4.0, 2.0, 0.1, key="kc_mult")
        keltner_lookback = st.slider("  Breakout lookback (days)", 1, 20, 5, key="kc_lb",
                                     help="Higher = catches stocks that broke out recently, "
                                          "not just today.")
    else:
        keltner_ema, keltner_atr, keltner_mult, keltner_lookback = 20, 20, 2.0, 5

    # Volume surge
    vol_on = st.checkbox("✅ Volume surge", value=True,
                        help="Today's volume must exceed N× the average")
    if vol_on:
        vol_mult = st.slider("  Volume surge multiplier", 1.0, 5.0, 1.5, 0.1, key="vol_mult")
        vol_sma  = st.slider("  Volume SMA length", 5, 60, 20, key="vol_sma")
    else:
        vol_mult, vol_sma = 0.0, 20  # 0.0 = always passes

    # Whipsaw filter
    whipsaw_on = st.checkbox("✅ Whipsaw filter", value=True,
                            help="Price must be N% above the breakout level (avoid fakes)")
    if whipsaw_on:
        whipsaw_pct = st.slider("  Whipsaw filter (%)", 0.0, 5.0, 1.0, 0.1, key="wp") / 100
    else:
        whipsaw_pct = -1.0  # any close above the band passes

    # Bearish RSI divergence blocker
    divergence_on = st.checkbox("✅ Bearish-RSI-divergence blocker", value=True,
                                help="Reject if price is at a new high but RSI is lower")
    if divergence_on:
        rsi_len      = st.slider("  RSI length", 5, 30, 14, key="rsi_len")
        div_lookback = st.slider("  Divergence lookback", 10, 60, 20, key="div_lb")
    else:
        rsi_len, div_lookback = 14, 20

    # ---- Mandatory liquidity & price floor (cannot be disabled) ----
    st.markdown("---")
    st.markdown("**🔒 Mandatory Liquidity Floor** *(cannot be disabled)*")
    st.caption("Hard rules to prevent flagging untradeable penny stocks. "
               "ATR/Keltner are the real volatility filters — Beta intentionally not used.")
    min_price = st.number_input(
        "Minimum price ($)",
        min_value=0.5, max_value=50.0, value=2.0, step=0.5,
        help="Reject stocks below this price. Defaults to $2 to avoid penny stocks "
             "which have huge spreads and easy manipulation.",
    )
    min_avg_volume = st.number_input(
        "Minimum avg daily volume (shares)",
        min_value=50_000, max_value=10_000_000, value=500_000, step=50_000,
        help="Reject illiquid names. 500K shares/day = you can enter/exit without "
             "destroying price even on panic days.",
    )


    # ---- Risk module --------------------------------------------------------
    st.subheader("Module 3 — Risk")
    atr_len           = st.slider("ATR length", 5, 30, 14)
    atr_stop_mult     = st.slider("ATR stop multiplier", 0.5, 5.0, 2.0, 0.1)
    support_lookback  = st.slider("Support lookback (days)", 3, 30, 10)
    target_method     = st.selectbox("Target method", ["atr", "resistance"], index=0)
    atr_target_mult   = st.slider("ATR target multiplier", 1.0, 12.0, 6.0, 0.5)
    resist_lookback   = st.slider("Resistance lookback", 20, 250, 60)
    min_rr            = st.slider("Minimum R/R ratio", 1.0, 6.0, 3.0, 0.1)
    trail_sma         = st.slider("Trailing trend SMA", 10, 200, 50)

    history_period    = st.selectbox("History to download",
                                     ["1y", "2y", "5y"], index=1)


# ==============================================================================
# Main area -- Strategy Profile selector (Murphy's rule)
# ==============================================================================
st.subheader("🎯 Strategy Profile")
st.caption(
    "Murphy's iron rule (Ch. 10): match the indicator to the market environment. "
    "Trend indicators (MAs) win in trends and lose in ranges; oscillators (RSI) "
    "win in ranges and give false signals in trends. Pick the right profile for "
    "what you're hunting today."
)

profile_keys   = list(STRATEGY_PROFILES.keys())
profile_labels = [STRATEGY_PROFILES[k]["label"] for k in profile_keys]
# Add a virtual "best_of_all" option that runs all 3 real profiles
BEST_OF_ALL_LABEL = "🏆 Best of All Profiles — Top 5 strongest across breakout + pullback + reversal"
profile_labels_ext = profile_labels + [BEST_OF_ALL_LABEL]
selected_label = st.selectbox(
    "Choose a strategy", profile_labels_ext, index=0,
    help="Selecting a profile auto-overrides Module 2 filters. "
         "Module 1 (macro) and Module 3 (risk) stay as configured. "
         "'Best of All' runs all three trading profiles and surfaces the "
         "5 strongest setups overall — no matter which profile flagged them."
)
if selected_label == BEST_OF_ALL_LABEL:
    selected_profile = "best_of_all"
else:
    selected_profile = profile_keys[profile_labels.index(selected_label)]

# Show description
if selected_profile == "best_of_all":
    st.success("🏆 **Best of All mode active** — the scanner will evaluate every stock against ALL three profiles (breakout, pullback, reversal) and return the Top 5 strongest candidates overall. Full signals always rank above near-misses; within each tier, ranking is by R/R (signals) or filter pass rate (near-misses).")
    with st.expander("How does this work?"):
        st.markdown("""
**Step 1.** Download data once for the universe.

**Step 2.** For each of the 3 profiles (breakout, pullback, reversal):
- Apply that profile's filter configuration
- Run every stock through the filters
- Collect signals (full pass) and near-misses (partial pass)
- Tag each result with the profile name

**Step 3.** Pool all results, deduplicate by ticker (keep the highest-scoring instance), and rank:
- ✅ Full signals first (passed every filter + R/R ≥ minimum)
- 🎯 Near-misses second (didn't pass everything but close)

**Step 4.** Return the top 5 — they could be all from one profile, or 2-2-1, or any mix. The selection is purely by strength.

This is the most permissive mode — it surfaces the absolute best setups regardless of market regime classification.
""")
else:
    desc = STRATEGY_PROFILES[selected_profile].get("description", "")
    if desc:
        if selected_profile == "custom":
            st.info(f"ℹ️ {desc}")
        else:
            st.success(f"✅ **Active profile:** {desc}")
            with st.expander("See what this profile overrides"):
                prof = STRATEGY_PROFILES[selected_profile]
                if "screener" in prof:
                    st.markdown("**Screener (Module 2) overrides:**")
                    screener_df = pd.DataFrame(
                        [(k, str(v)) for k, v in prof["screener"].items()],
                        columns=["Setting", "Value"]
                    )
                    st.dataframe(screener_df, use_container_width=True, hide_index=True)
            if "risk" in prof:
                st.markdown("**Risk (Module 3) overrides:**")
                risk_df = pd.DataFrame(
                    [(k, str(v)) for k, v in prof["risk"].items()],
                    columns=["Setting", "Value"]
                )
                st.dataframe(risk_df, use_container_width=True, hide_index=True)

st.markdown("---")


# ==============================================================================
# Main area -- Market State panel (always visible)
# ==============================================================================
st.subheader("🌍 Market State")
st.caption("Check the broader market BEFORE deciding to scan. Refreshes every 10 minutes.")

ms_col1, ms_col2, ms_col3, ms_col4 = st.columns(4)
refresh_col1, refresh_col2 = st.columns([4, 1])

with st.spinner("Loading market state..."):
    try:
        snap = _macro_snapshot_cached(int(spy_sma), float(vix_threshold))
    except Exception as e:
        snap = None
        st.error(f"Could not load market state: {e}")

if snap:
    # --- SPY trend
    with ms_col1:
        if snap["spy_price"] and snap["spy_sma"]:
            delta_pct = (snap["spy_price"] / snap["spy_sma"] - 1) * 100
            arrow = "🟢" if delta_pct > 0 else "🔴"
            label = "above" if delta_pct > 0 else "below"
            st.metric(
                "SPY (S&P 500 ETF)",
                f"${snap['spy_price']:.2f}",
                f"{arrow} {abs(delta_pct):.2f}% {label} SMA{snap['spy_sma_len']}",
                delta_color="off",
                help=f"SPY's current price. The SMA{snap['spy_sma_len']} "
                     f"(50-day average) is ${snap['spy_sma']:.2f}. "
                     f"Price above SMA = uptrend (good for new long signals)."
            )
        else:
            st.metric("SPY", "N/A")

    # --- VIX (Fear gauge)
    with ms_col2:
        if snap["vix"] is not None:
            # VIX color logic
            if snap["vix"] < 15:
                vix_label = "🟢 Calm"
            elif snap["vix"] < 20:
                vix_label = "🟡 Normal"
            elif snap["vix"] < 30:
                vix_label = "🟠 Elevated"
            else:
                vix_label = "🔴 Fear"
            st.metric("VIX (Fear Index)", f"{snap['vix']:.2f}", vix_label,
                      delta_color="off")
        else:
            st.metric("VIX", "N/A")

    # --- VIX/VXV term structure
    with ms_col3:
        if snap["vix_ratio"] is not None:
            ratio_label = "🟢 Contango" if snap["vix_ok"] else "🔴 Backwardation"
            st.metric("VIX/VXV Ratio",
                      f"{snap['vix_ratio']:.3f}",
                      f"{ratio_label} (<{snap['vix_threshold']:.2f}={'OK' if snap['vix_ok'] else 'WARN'})",
                      delta_color="off")
        else:
            st.metric("VIX/VXV", "N/A")

    # --- Overall verdict
    with ms_col4:
        if snap["spy_ok"] and snap["vix_ok"]:
            verdict = "🟢 GO"
            verdict_text = "Conditions favorable"
        elif not snap["spy_ok"] and not snap["vix_ok"]:
            verdict = "🔴 STOP"
            verdict_text = "Trend down + high fear"
        else:
            verdict = "🟡 CAUTION"
            verdict_text = "Mixed signals"
        st.metric("Verdict", verdict, verdict_text, delta_color="off")

    # Refresh button
    with refresh_col2:
        if st.button("🔄 Refresh", use_container_width=True,
                     help="Force-refresh market data (clears 10-min cache)"):
            _macro_snapshot_cached.clear()
            st.rerun()

st.markdown("---")


# ==============================================================================
# Main area -- Portfolio uploader + Run button
# ==============================================================================
left, right = st.columns([1, 1])
with left:
    st.subheader("📁 Existing portfolio (optional)")
    port_up = st.file_uploader(
        "Upload CSV or Excel with columns: Ticker, Entry_Price, Entry_Date "
        "(Shares optional)",
        type=["csv", "xlsx"], key="port_up",
    )
    portfolio_df = None
    if port_up is not None:
        try:
            if port_up.name.lower().endswith(".xlsx"):
                # Explicit engine + read first sheet, drop fully-empty rows
                portfolio_df = pd.read_excel(port_up, engine="openpyxl", sheet_name=0)
            else:
                portfolio_df = pd.read_csv(port_up)
            # Clean up: drop rows where ALL relevant columns are NaN
            portfolio_df = portfolio_df.dropna(how="all")
            # Drop rows missing Ticker (likely empty template rows)
            if "Ticker" in portfolio_df.columns:
                portfolio_df = portfolio_df[portfolio_df["Ticker"].notna()]
                portfolio_df = portfolio_df.reset_index(drop=True)
            if portfolio_df.empty:
                st.warning("⚠️ No valid rows found in the uploaded file. "
                          "Make sure you have at least one row with a Ticker.")
                portfolio_df = None
            else:
                st.success(f"✅ Loaded {len(portfolio_df)} position(s)")
                st.dataframe(portfolio_df, use_container_width=True, hide_index=True)
        except Exception as e:
            st.error(f"❌ Couldn't read the file: {type(e).__name__}: {e}")
            st.caption("Make sure columns are exactly: **Ticker**, **Entry_Price**, **Entry_Date** "
                       "(headers in row 1). Download the template above for the correct format.")
            portfolio_df = None
    else:
        sample_path = "portfolio_sample.csv"
        if os.path.exists(sample_path):
            if st.checkbox("Use sample portfolio", value=False):
                portfolio_df = pd.read_csv(sample_path)
                st.dataframe(portfolio_df, use_container_width=True, hide_index=True)

with right:
    st.subheader("▶️ Run scan")
    st.caption(
        "Scanning is rate-limited by yfinance. Larger universes take longer; "
        "the 'Max tickers' slider in the sidebar lets you cap runtime."
    )
    run_clicked = st.button("Run EOD scan", type="primary", use_container_width=True)


# ==============================================================================
# Build CONFIG from sidebar
# ==============================================================================
def build_config() -> dict:
    cfg = get_default_config()
    cfg["universe"]        = custom_universe
    cfg["total_equity"]    = float(total_equity)
    cfg["history_period"]  = history_period

    cfg["macro"].update({
        "enabled":              macro_enabled,
        "spy_trend_enabled":    spy_trend_on,
        "spy_sma_length":       int(spy_sma),
        "vix_ratio_threshold":  float(vix_threshold),
        "sector_check_enabled": sector_check,
        "sector_sma_length":    int(sector_sma),
        "ad_line_enabled":      ad_line_enabled,
    })
    cfg["screener"].update({
        # Filter on/off toggles
        "ma_alignment_enabled":      ma_align_on,
        "obv_enabled":               obv_on,
        "keltner_enabled":           keltner_on,
        "volume_surge_enabled":      vol_on,
        "whipsaw_enabled":           whipsaw_on,
        # Filter parameters
        "ma_lengths":         ma_lengths,
        "ma_type":            ma_type,
        "obv_lookback":       int(obv_lookback),
        "keltner_ema_length": int(keltner_ema),
        "keltner_atr_length": int(keltner_atr),
        "keltner_multiplier": float(keltner_mult),
        "keltner_breakout_lookback": int(keltner_lookback),
        "volume_sma_length":  int(vol_sma),
        "volume_multiplier":  float(vol_mult),
        "whipsaw_pct":        float(whipsaw_pct),
        "divergence_enabled": divergence_on,
        "divergence_lookback": int(div_lookback),
        "rsi_length":         int(rsi_len),
        # Mandatory liquidity floors (always active, cannot be disabled)
        "min_price":          float(min_price),
        "min_avg_volume":     int(min_avg_volume),
    })
    cfg["risk"].update({
        "atr_length":             int(atr_len),
        "atr_stop_multiplier":    float(atr_stop_mult),
        "support_lookback":       int(support_lookback),
        "target_method":          target_method,
        "atr_target_multiplier":  float(atr_target_mult),
        "resistance_lookback":    int(resist_lookback),
        "min_rr_ratio":           float(min_rr),
        "risk_per_trade_pct":     float(risk_per_trade),
        "trailing_sma_length":    int(trail_sma),
    })

    # Apply strategy profile LAST so it overrides sidebar settings.
    # 'best_of_all' is a virtual profile — leave sidebar settings as base
    # and flag the engine to run all 3 real profiles internally.
    if selected_profile == "best_of_all":
        cfg["best_of_all_mode"] = True
    else:
        cfg = apply_strategy_profile(cfg, selected_profile)
    return cfg


# ==============================================================================
# Execute
# ==============================================================================
if run_clicked:
    if not custom_universe:
        st.error("Universe is empty -- choose a source or paste tickers in the sidebar.")
        st.stop()

    cfg = build_config()
    progress_bar = st.progress(0.0)
    status_box   = st.empty()

    def prog(f, m=""):
        progress_bar.progress(f)
        if m:
            status_box.info(m)

    def status(m):
        status_box.info(m)

    with st.spinner("Running scan..."):
        try:
            result = run_scanner(cfg, portfolio_df=portfolio_df,
                                 progress_cb=prog, status_cb=status)
        except Exception as e:
            st.error(f"Scan failed: {type(e).__name__}: {e}")
            st.stop()

    progress_bar.empty()
    status_box.empty()
    st.session_state["last_result"] = result
    st.session_state["last_config"] = cfg

# ==============================================================================
# Render results
# ==============================================================================
if "last_result" in st.session_state:
    result = st.session_state["last_result"]
    new_signals      = result["new_signals"]
    portfolio_updates = result["portfolio_updates"]
    macro_info        = result["macro"]
    macro_ok          = result["macro_ok"]

    st.markdown("---")

    # Macro banner
    macro_label = macro_info.get("overall", "n/a")
    if macro_label == "PASS":
        st.success(f"🟢 **Macro Environment: PASS** — new signals enabled "
                   f"({result['timestamp']:%Y-%m-%d %H:%M:%S})")
    elif macro_label == "FAIL":
        st.warning(f"🟡 **Macro Environment: FAIL** — new signals suppressed; "
                   f"portfolio still managed.")
    else:
        st.info(f"Macro kill-switch disabled.")

    # Scan stats banner
    stats = result.get("stats", {})
    if stats:
        s1, s2, s3, s4 = st.columns(4)
        s1.metric("Tickers requested",  f"{stats.get('requested', 0):,}")
        s2.metric("Successfully downloaded", f"{stats.get('downloaded', 0):,}")
        s3.metric("Have full indicators", f"{stats.get('indicators_ok', 0):,}")
        s4.metric("Total scan time", f"{stats.get('t_download_s', 0) + stats.get('t_indicators_s', 0) + stats.get('t_screen_s', 0):.1f}s")

    near_misses = result.get("near_misses", pd.DataFrame())
    best_of_all = result.get("best_of_all")  # None unless best_of_all mode was on

    if best_of_all is not None:
        # Best-of-All mode: show the special top-5 tab as the FIRST tab
        top_picks = best_of_all.get("top_picks", pd.DataFrame())
        tab_boa, tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(
            [f"🏆 Top 5 Best Picks ({len(top_picks)})",
             f"🆕 New Signals ({len(new_signals)})",
             f"🎯 Top Near-Misses ({len(near_misses)})",
             f"📊 Portfolio ({len(portfolio_updates)})",
             "🌍 Macro Detail",
             "🔍 Diagnostics",
             "📚 How It Works"]
        )

        with tab_boa:
            if top_picks.empty:
                st.info("No candidates qualified across any of the 3 profiles. "
                        "Either the macro environment blocked everything or no stocks "
                        "have enough indicator strength right now.")
            else:
                st.markdown(
                    "### 🏆 Top 5 Strongest Setups Across All Profiles\n"
                    "These are the **5 strongest candidates** from running every stock "
                    "through **all three profiles** (Breakout · Pullback · Reversal). "
                    "Each row is tagged with the profile that flagged it. Full signals "
                    "always rank above near-misses."
                )

                # Reorder columns so Type/Profile are visible first
                preferred = ["Type", "Profile", "Ticker", "Score", "Price", "Beta",
                             "Entry_Price", "Initial_Stop", "Target", "R_R_Ratio",
                             "Shares_To_Buy", "Risk_$", "Passed", "Failed"]
                cols_order = [c for c in preferred if c in top_picks.columns]
                cols_order += [c for c in top_picks.columns if c not in cols_order]
                display_df = top_picks[cols_order]

                st.dataframe(
                    display_df,
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "Score":         st.column_config.NumberColumn("Score",  format="%.0f%%"),
                        "Price":         st.column_config.NumberColumn("Price",  format="$%.2f"),
                        "Entry_Price":   st.column_config.NumberColumn("Entry",  format="$%.2f"),
                        "Initial_Stop":  st.column_config.NumberColumn("Stop",   format="$%.2f"),
                        "Target":        st.column_config.NumberColumn("Target", format="$%.2f"),
                        "R_R_Ratio":     st.column_config.NumberColumn("R/R",    format="%.2f"),
                        "Shares_To_Buy": st.column_config.NumberColumn("Shares", format="%d"),
                        "Risk_$":        st.column_config.NumberColumn("Risk $", format="$%.2f"),
                        "Beta":          st.column_config.NumberColumn("Beta",   format="%.2f"),
                    },
                )

                # Profile distribution summary
                if "Profile" in top_picks.columns:
                    st.markdown("#### Profile breakdown:")
                    profile_counts = top_picks["Profile"].value_counts()
                    cols = st.columns(len(profile_counts))
                    for i, (prof, count) in enumerate(profile_counts.items()):
                        cols[i].metric(f"{prof}", f"{count} pick(s)")

                # Show per-profile counts
                with st.expander("📊 Per-profile evaluation details"):
                    pp = best_of_all.get("per_profile", {})
                    for prof_name, prof_result in pp.items():
                        n_sig = len(prof_result.get("signals", []))
                        n_nm  = len(prof_result.get("near_misses", []))
                        st.markdown(f"**{prof_name.capitalize()}**: "
                                    f"{n_sig} full signals · {n_nm} near-misses")
    else:
        # Normal single-profile mode: standard 6 tabs
        tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(
            [f"🆕 New Signals ({len(new_signals)})",
             f"🎯 Top Near-Misses ({len(near_misses)})",
             f"📊 Portfolio ({len(portfolio_updates)})",
             "🌍 Macro Detail",
             "🔍 Diagnostics",
             "📚 How It Works"]
        )

    with tab1:
        if new_signals.empty:
            st.info("No stocks passed ALL filters today.")
            diag = result.get("diagnostics", {})
            if diag:
                st.markdown("👉 **Check the 'Top Near-Misses' tab** — these are the closest "
                            "candidates that missed only 1-2 filters. They might be worth "
                            "watching tomorrow.")
        else:
            st.dataframe(
                new_signals,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Score":         st.column_config.NumberColumn("Score", format="%.0f%%"),
                    "Entry_Price":   st.column_config.NumberColumn("Entry", format="$%.2f"),
                    "Initial_Stop":  st.column_config.NumberColumn("Stop",  format="$%.2f"),
                    "Target":        st.column_config.NumberColumn("Target", format="$%.2f"),
                    "R_R_Ratio":     st.column_config.NumberColumn("R/R",   format="%.2f"),
                    "Shares_To_Buy": st.column_config.NumberColumn("Shares", format="%d"),
                    "Risk_$":        st.column_config.NumberColumn("Risk $", format="$%.2f"),
                    "Beta":          st.column_config.NumberColumn("Beta",   format="%.2f"),
                },
            )
            tot_risk = new_signals["Risk_$"].sum()
            st.metric("Total $ at risk across new signals", f"${tot_risk:,.2f}")

    with tab2:
        if near_misses.empty:
            st.info("No candidates to evaluate (possibly because no tickers had "
                   "valid data, or all of them passed and are in New Signals).")
        else:
            st.caption("Top 10 stocks ranked by % of filters passed. "
                       "Use this to find stocks that are CLOSE to triggering — they may set up over the next few days.")
            # Clean number formatting, no row background colors
            st.dataframe(
                near_misses,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Score": st.column_config.NumberColumn("Score", format="%.0f%%"),
                    "Price": st.column_config.NumberColumn("Price", format="$%.2f"),
                    "Beta":  st.column_config.NumberColumn("Beta",  format="%.2f"),
                },
            )
            st.caption("**Score** = % of enabled filters passed. "
                       "**Passed** = which filters this stock satisfies. "
                       "**Failed** = which filters this stock is missing.")

    with tab3:
        if portfolio_updates.empty:
            st.info("No portfolio positions to evaluate.")
        else:
            # Clean numeric formatting, no row coloring
            col_cfg = {}
            for col in portfolio_updates.columns:
                lc = col.lower()
                if lc in ("entry_price", "current_price", "stop", "trailing_stop",
                          "target", "atr", "initial_stop"):
                    col_cfg[col] = st.column_config.NumberColumn(col, format="$%.2f")
                elif lc in ("p_l_%", "pl_pct", "pnl_%", "return_%"):
                    col_cfg[col] = st.column_config.NumberColumn(col, format="%.2f%%")
                elif lc in ("beta",):
                    col_cfg[col] = st.column_config.NumberColumn(col, format="%.2f")
                elif lc in ("shares",):
                    col_cfg[col] = st.column_config.NumberColumn(col, format="%d")
                elif lc in ("days_held", "days"):
                    col_cfg[col] = st.column_config.NumberColumn(col, format="%d")
            st.dataframe(
                portfolio_updates,
                use_container_width=True,
                hide_index=True,
                column_config=col_cfg,
            )

    with tab4:
        macro_df = pd.DataFrame(list(macro_info.items()),
                                columns=["Check", "Result"])
        st.dataframe(macro_df, use_container_width=True, hide_index=True)

    with tab5:
        diag = result.get("diagnostics", {})
        if not diag:
            st.info("No diagnostics available (macro kill-switch blocked the scan).")
        else:
            st.markdown("### Funnel: how many tickers passed each filter")
            st.caption("Each row shows how many tickers got past that filter. "
                       "Look for the biggest drop — that's where most candidates are eliminated.")
            funnel_rows = [
                ("Evaluated (had data)",          diag.get("evaluated", 0)),
                ("→ Liquidity & price floor",     diag.get("liquidity_ok", 0)),
                ("→ Sector strength OK",          diag.get("sector_rs_ok", 0)),
                ("→ MA alignment",                diag.get("ma_alignment", 0)),
                ("→ OBV breakout",                diag.get("obv_breakout", 0)),
                ("→ Keltner breakout",            diag.get("keltner_breakout", 0)),
                ("→ Volume surge",                diag.get("volume_surge", 0)),
                ("→ Whipsaw filter",              diag.get("whipsaw_filter", 0)),
                ("→ No bearish divergence",       diag.get("divergence_ok", 0)),
                ("→ Pullback trigger",            diag.get("pullback_trigger", 0)),
                ("→ Reversal trigger",            diag.get("reversal_trigger", 0)),
                ("→ ALL filters passed together", diag.get("all_filters_ok", 0)),
                ("→ Valid stop level",            diag.get("valid_stop", 0)),
                ("→ R/R ratio met",               diag.get("rr_ok", 0)),
                ("→ Final signals",               diag.get("final", 0)),
            ]
            diag_df = pd.DataFrame(funnel_rows, columns=["Step", "Count"])
            st.dataframe(diag_df, use_container_width=True, hide_index=True)

            if diag["final"] == 0 and diag["evaluated"] > 0:
                # Find the biggest narrow point
                st.markdown("### 💡 Suggestions to find more candidates")
                tips = []
                if diag["ma_alignment"] < diag["evaluated"] * 0.1:
                    tips.append("- **MA alignment** is rejecting most stocks. "
                                "Try removing the 200-SMA: change `MA lengths` to `20, 50, None`.")
                if diag["keltner_breakout"] < diag["evaluated"] * 0.05:
                    tips.append("- **Keltner breakout** is the bottleneck. "
                                "Increase `Keltner breakout lookback` in the sidebar (try 10 or 15).")
                if diag["volume_surge"] < diag["evaluated"] * 0.1:
                    tips.append("- **Volume surge** is too strict. "
                                "Lower `Volume surge multiplier` to 1.2 or 1.0.")
                if diag["rr_ok"] < diag["all_filters_ok"] * 0.5 and diag["all_filters_ok"] > 0:
                    tips.append("- **R/R ratio** is too high. "
                                "Lower `Minimum R/R ratio` from 3.0 to 2.0.")
                if not tips:
                    tips.append("- The market may genuinely have no setups today. "
                                "The strict filters are designed to flag only the best opportunities.")
                for t in tips:
                    st.markdown(t)

    with tab6:
        st.markdown("""
## 📖 Complete Scanner Documentation

This document explains in detail what the scanner does, how it works, what each indicator means,
where data comes from, and how to interpret every output.

---

### 🎯 The Big Picture

This is an **End-of-Day (EOD) stock screener** designed to find **swing-trade entries** with
favorable risk/reward, while filtering out trades that go against the broader market.

It runs **three independent modules** in sequence:

1. **Module 1 — Macro Kill-Switch** — Is the overall market healthy enough to take trades?
2. **Module 2 — EOD Screener** — Which stocks pass all technical filters today?
3. **Module 3 — Portfolio Manager** — Update stops/exits on positions you already own.

If Module 1 fails, Module 2 is **automatically skipped** — no new trades when the regime is hostile.
Module 3 always runs, because risk management must continue regardless of regime.

---

### 📡 Data Source

- **Primary source**: [Yahoo Finance](https://finance.yahoo.com) via the `yfinance` Python library.
- **Frequency**: End-of-day OHLCV (Open, High, Low, Close, Volume) — daily bars only.
- **History pulled**: 2 years per ticker (default), so we have enough data for 200-day moving averages and beta computation.
- **Cost**: Free. No API key required.
- **Limitations**: Yahoo data can have occasional gaps or delisted tickers. The scanner silently skips any ticker with fewer than 250 bars of history.
- **Delay**: Yahoo Finance data updates after the US market closes (~4:30 PM ET / ~23:30 Israel time). Run the scanner after that for the freshest data.

---

### 🌍 MODULE 1 — Macro Kill-Switch

**Purpose**: Stop generating buy signals when the overall market environment is dangerous.
A great stock setup in a falling market is usually still a losing trade.

It evaluates **3-4 checks**. If too many fail, the scanner halts before evaluating individual stocks.

#### Check 1: SPY trend (S&P 500 above/below moving average)
- **What**: Is SPY (the S&P 500 ETF) trading above its 50-day Simple Moving Average?
- **Why**: SPY above SMA50 = market in uptrend = safer to buy. Below = downtrend = stand aside.
- **Calculation**: Pull SPY's last 250 daily closes, compute `SMA(50)`, compare today's close to it.

#### Check 2: VIX absolute level
- **What**: Is the VIX (volatility index) below a threshold (default 25)?
- **Why**: VIX above 25 = elevated fear = trades are riskier. VIX above 30 = panic territory.
- **VIX zones**: <15 calm · 15-20 normal · 20-25 elevated · 25-30 stressed · >30 fear/panic.

#### Check 3: VIX/VXV term structure
- **What**: Ratio of VIX (1-month vol) to VXV (3-month vol).
- **Why**: When **VIX > VXV** (ratio > 1.0), short-term fear is higher than long-term — typically a sign of acute stress and a contrarian buy signal *only after* the spike resolves.
- **For buyers**: Default behavior is to require ratio < 1.0 (normal term structure).

#### Check 4: Sector relative strength (per stock)
- **What**: For each stock, compare its sector ETF's 60-day return to SPY's 60-day return.
- **Why**: Buy stocks in **leading sectors**, avoid lagging ones.
- **Mapping** (hardcoded by sector ETF):
  - Tech → XLK · Healthcare → XLV · Financials → XLF · Energy → XLE
  - Industrials → XLI · Consumer Discretionary → XLY · Staples → XLP
  - Utilities → XLU · Materials → XLB · Real Estate → XLRE · Communications → XLC

**Result**: Module 1 returns 🟢 GREEN / 🟡 YELLOW / 🔴 RED.
- 🟢 = all checks pass → proceed to scan
- 🟡 = mixed signals → scan but warn
- 🔴 = market unsafe → halt scanner

---

### 🔬 MODULE 2 — EOD Technical Screener

**Purpose**: Find stocks with clean technical setups for swing entries (typical 5-30 day holding period).

Each filter is **independent** and can be toggled ON/OFF. A stock must pass **all enabled filters** to be flagged as a "New Signal."

#### Pre-filter A: Liquidity & price floor (MANDATORY, cannot be disabled)
- **Min price** (default $2): Rejects penny stocks. They have enormous spreads, are easily manipulated, and the R/R numbers look great on paper but evaporate on execution.
- **Min avg volume** (default 500,000 shares/day): Rejects illiquid names. If you can't exit on a panic day without destroying the price, you don't really own a tradable position.
- **Why it's not optional**: These aren't "preferences" — they're protection against scanning untradeable stocks. The scanner can be perfectly correct technically and still bankrupt you via slippage.

#### Why we DON'T use a Beta filter (deliberate design choice)
- **What Beta is**: An academic CAPM statistic measuring 1-year price covariance vs SPY.
- **The problem**: It's a backward-looking measure of *past* volatility. A stock with Beta=0.7 last year that JUST started a clean breakout today is **exactly** what we want to catch — and a Beta filter would reject it.
- **The conflict**: We already use ATR (real-time, absolute volatility) via Keltner channels, volume surge, and ATR-based stops. ATR is the technical analyst's volatility measure. Beta is the academic finance professor's. They don't belong in the same pipeline.
- **What we do instead**: Beta is **computed and displayed** in the output table for reference, but never used to gate signals. The ATR-based filters do the real work.

#### Filter 1: Moving Average alignment
- **What**: Price > MA(fast) > MA(slow), e.g., Close > SMA(20) > SMA(50).
- **Why**: Confirms an established uptrend at multiple time scales.
- **Defaults**: Fast=20, Slow=50. Can also use 50/200 for stronger trends.
- **Murphy quote**: "The trend is your friend. MA alignment confirms the trend is intact."

#### Filter 2: OBV (On-Balance Volume) breakout
- **What**: Is OBV breaking above its highest level in the past N days (default 20)?
- **Why**: OBV is a cumulative volume indicator. When OBV makes new highs **before** price, smart money is accumulating. Watch for the price to follow.
- **Formula**: OBV adds volume on up days, subtracts it on down days.

#### Filter 3: Keltner Channel breakout
- **What**: Today's close > Upper Keltner Band (recent breakouts within last 5 days also count).
- **Why**: Keltner Channels use ATR-based bands around an EMA. A close above the upper band = volatility breakout = momentum thrust.
- **Formula**: Upper = EMA(20) + 1.5 × ATR(20). Tighter than Bollinger (which uses std dev).
- **Lookback window**: Default 5 days — catches recent breakouts not just today's cross.

#### Filter 4: Volume surge
- **What**: Today's volume > N × the 20-day average volume (default 1.5x).
- **Why**: Big volume confirms institutional participation, not retail-only moves.
- **Tip**: Lower to 1.25 in quiet markets, raise to 2.0 to be very selective.

#### Filter 5: Whipsaw filter
- **What**: Did the stock recently chop sideways without a clear trend? If so, reject.
- **Why**: Whipsaw markets eat your stop-losses. We want trending environments only.
- **Calculation**: Looks at the spread between recent highs/lows vs ATR — if too small, the stock is range-bound.

#### Filter 6: No bearish RSI divergence
- **What**: Reject if price is making a new high but RSI is making a *lower* high.
- **Why**: Classic warning sign that momentum is fading even as price rises — often precedes reversals.
- **Default**: RSI(14), 20-day lookback for divergence detection.

#### Optional Filter A: Pullback trigger (used by "pullback" strategy)
- **What**: Did the stock pull back to its 50-day SMA and bounce, with RSI cooling from overbought to neutral?
- **Why**: Buying dips in uptrends has higher win rate than chasing breakouts.

#### Optional Filter B: Reversal trigger (used by "reversal" strategy)
- **What**: Did price pierce the lower Keltner band and recover, with RSI crossing back above oversold?
- **Why**: Mean-reversion setup for range-bound markets.

---

### 🎯 Strategy Profiles (Murphy-Inspired)

A dropdown at the top of the main screen overrides Module 2 with one of three preset configurations:

| Profile | Best For | Key Filters | Stop |
|---|---|---|---|
| **Custom** | DIY users | Whatever you set in sidebar | Sidebar setting |
| **Breakout** | Strong trending markets | MA 20/50, Keltner 1.5x, Vol 1.25x, OBV ON, divergence OFF | 2.0 × ATR |
| **Pullback** | Mid-trend dip buying | Pullback trigger + RSI cool-and-turn near 50-SMA | 1.5 × ATR |
| **Reversal** | Range-bound markets | Reversal trigger + lower Keltner pierce + RSI oversold cross | 1.0 × ATR |

Macro and Risk modules are **NOT** overridden by profiles — macro is environmental, risk is personal.

---

### 💰 MODULE 3 — Risk Management

**Purpose**: For every signal AND every existing portfolio position, determine:
1. Where to place the **initial stop loss**
2. Where to set the **target** (for R/R calculation)
3. How many **shares to buy** based on your risk tolerance
4. Whether to **update trailing stops** on existing positions
5. Whether **volume-confirmed exit** is triggered

#### Position sizing — the math
- **Inputs**: Total equity ($), Risk per trade (%), Entry price, Stop price.
- **Formula**: `Shares = (Equity × Risk%) / (Entry - Stop)`
- **Example**: $10,000 equity, 2% risk = $200 risk budget. Entry $50, Stop $48 = $2 risk per share. Shares = $200 / $2 = **100 shares**.

#### ATR-based stop loss
- **Why ATR (Average True Range)?** Volatility-adjusted stops — wider stops for volatile stocks, tighter for calm ones.
- **Formula**: `Initial Stop = Entry - (ATR_multiplier × ATR(14))`
- **Defaults**: 2.0× ATR for breakout, 1.5× for pullback, 1.0× for reversal.

#### Target & R/R gating
- **Target**: Calculated based on recent swing high or N × ATR projection.
- **R/R Ratio**: `(Target - Entry) / (Entry - Stop)`. Default minimum = **3.0** — only take trades where potential upside is 3× the risk.

#### Trailing stop "ratchet"
For positions in your portfolio:
- As price rises, the stop ratchets **UP** (never down).
- Trailing logic: `New Stop = max(Current Stop, Floor - ATR_multiplier × ATR)`
- **The ATR multiplier matches your initial stop** — if you entered with a 2× ATR stop (Breakout profile), the trailing stop also uses 2× ATR. This gives the trade room to breathe through normal intraday noise instead of getting stopped out by a single wick.
- **Floor**: The maximum of (recent swing low, trend SMA) — anchors the stop to meaningful support, not random low points.

#### Volume-confirmed exit
- **Why**: A stop hit on huge volume = distribution = real selling. A stop hit on light volume = noise — often whipsaws back up.
- **Logic**: Only exit if `Close < Stop` AND `Volume > Average Volume`.

---

### 📊 Output Tabs Explained

#### 🆕 New Signals
Stocks that passed **ALL** enabled filters today. Each row shows:
- **Entry_Price** — current close
- **Initial_Stop** — where to set stop-loss order
- **Target** — where to take profit (or trail from)
- **R_R_Ratio** — risk/reward ratio
- **Shares_To_Buy** — calculated by position sizer
- **Risk_$** — dollar amount at risk if stopped out
- **Beta** — volatility vs SPY

#### 🎯 Top Near-Misses
The 10 highest-scoring stocks that **didn't** pass all filters. Each shows:
- **Score** — % of enabled filters passed
- **Passed** — which filters this stock satisfies
- **Failed** — which filters this stock is missing
- Color coded: 🟢 ≥80% · 🟡 60-80% · 🔴 <60%

Use this to find setups that may trigger in the next 1-3 days.

#### 📊 Portfolio
For each position you uploaded:
- **Action** — HOLD / EXIT / UPDATE_STOP
- **Trailing_Stop** — new ratcheted stop level
- **P_L_%** — current profit/loss percentage
- **Reason** — why this action was chosen

#### 🌍 Macro Detail
Detailed breakdown of every macro check with its raw values.

#### 🔍 Diagnostics
Funnel view: how many tickers passed each filter step. Auto-suggestions appear when 0 final signals are found.

---

### ⚙️ Configuration: What Each Setting Means

#### Universe
- **🔥 High-Momentum (531)** — Curated high-beta names from Finviz Beta>1.5 filter
- **S&P 500** — Large caps only
- **Russell 2000** — Small caps
- **Custom / Upload** — Your own list

#### Account
- **Total equity** — Used only for position sizing calculation
- **Risk per trade %** — Max % of equity at risk on one trade (default 2%)

#### Module 1 — Macro
- All four checks can be individually toggled
- Thresholds (SMA length, VIX level) configurable

#### Module 2 — Screener
- Each filter has ON/OFF toggle
- Sub-parameters appear only when filter is enabled

---

### 🧮 Performance Notes

- **531 tickers** ≈ 2-4 minutes per full scan
- **2,400 tickers** (S&P+R2K) ≈ 5-8 minutes
- Most time is spent downloading from Yahoo (network-bound)
- Indicator computation is fast (~10ms per ticker)
- Use the **Max tickers** slider to cap if testing

---

### ⚠️ Limitations & Honest Caveats

1. **Past data only** — All filters are based on historical OHLCV. No fundamentals, no news, no earnings dates.
2. **No tick data** — EOD bars only. Intraday signals require different infrastructure.
3. **Yahoo data quality** — Generally good but occasional bad ticks. Use as one input, not gospel.
4. **No backtest engine yet** — These filters are based on Murphy's classic patterns but haven't been statistically backtested here.
5. **Not financial advice** — This is a tool to find candidates worth researching, not a list of stocks to blindly buy.

---

### 📚 Background Reading

The filter logic is inspired by:
- **John Murphy** — *Technical Analysis of the Financial Markets*
- **Alexander Elder** — *Trading for a Living* (Triple Screen system)
- **Van K. Tharp** — *Trade Your Way to Financial Freedom* (position sizing math)
- **Linda Raschke** — Volume-confirmed exits

---

*Built with Python, pandas, pandas-ta-classic, yfinance, and Streamlit.*
        """)

    # Downloads
    st.markdown("### 💾 Download")
    c1, c2, c3 = st.columns(3)
    ts = result["timestamp"].strftime("%Y%m%d_%H%M%S")
    with c1:
        st.download_button(
            "📥 Excel report",
            data=_to_excel_bytes(new_signals, portfolio_updates, macro_info),
            file_name=f"eod_report_{ts}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )
    with c2:
        if not new_signals.empty:
            st.download_button(
                "📥 Signals CSV",
                data=new_signals.to_csv(index=False).encode("utf-8"),
                file_name=f"signals_{ts}.csv",
                mime="text/csv",
                use_container_width=True,
            )
    with c3:
        if not portfolio_updates.empty:
            st.download_button(
                "📥 Portfolio CSV",
                data=portfolio_updates.to_csv(index=False).encode("utf-8"),
                file_name=f"portfolio_{ts}.csv",
                mime="text/csv",
                use_container_width=True,
            )

else:
    # Welcome screen when no scan has been run yet
    col_a, col_b = st.columns([2, 1])
    with col_a:
        st.markdown("""
        ### 👋 Welcome to EOD Screener Terminal

        This is a **professional-grade end-of-day stock screener** that combines:

        - 🌍 **Macro regime filter** — only trade when conditions favor longs
        - 🔬 **9 technical indicators** — MA alignment, OBV, Keltner, RSI divergence, beta, and more
        - 💰 **ATR-based risk engine** — automatic stops and position sizing
        - 🎯 **Strategy profiles** — preset configurations for breakout, pullback, or reversal trades

        **To get started:**
        1. 👈 Configure your universe and filters in the sidebar
        2. (Optional) Upload your current portfolio CSV for tracking
        3. Click **🚀 Run EOD scan** at the top

        While the scan runs, the progress bar will show what's happening.
        Typical scan times: 531 tickers ≈ 3 min, 2,400 tickers ≈ 6 min.
        """)
    with col_b:
        st.markdown("""
        <div style="background:linear-gradient(135deg,#1a3a5c,#0a1929);padding:1.5rem;border-radius:10px;color:#fff;">
        <h4 style="color:#00d4ff;margin-top:0;">📊 Quick Stats</h4>
        <p style="margin:0.3rem 0;"><b>Universe</b>: 531 high-beta stocks</p>
        <p style="margin:0.3rem 0;"><b>Data</b>: Yahoo Finance EOD</p>
        <p style="margin:0.3rem 0;"><b>Indicators</b>: 9 technical filters</p>
        <p style="margin:0.3rem 0;"><b>Risk model</b>: ATR-based</p>
        <p style="margin:0.3rem 0;"><b>Cost</b>: Free</p>
        </div>
        """, unsafe_allow_html=True)

    st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)

    with st.expander("📖 **What does this scanner actually do?** (Click to expand full documentation)", expanded=False):
        st.markdown("""
### The Big Picture

This is an **End-of-Day (EOD) stock screener** designed to find **swing-trade entries** with
favorable risk/reward, while filtering out trades that go against the broader market.

It runs **three independent modules** in sequence:

1. **Module 1 — Macro Kill-Switch** — Is the overall market healthy enough to take trades?
2. **Module 2 — EOD Screener** — Which stocks pass all technical filters today?
3. **Module 3 — Portfolio Manager** — Update stops/exits on positions you already own.

If Module 1 fails, Module 2 is **automatically skipped** — no new trades when the regime is hostile.
Module 3 always runs, because risk management must continue regardless of regime.

---

### 📡 Data Source: Yahoo Finance

- **Source**: [Yahoo Finance](https://finance.yahoo.com) via `yfinance` Python library
- **Frequency**: End-of-day OHLCV bars (daily)
- **History**: 2 years per ticker
- **Cost**: Free, no API key
- **Caveat**: Run after US market close (~23:30 Israel time) for freshest data

---

### 🌍 MODULE 1 — Macro Kill-Switch

**Stops the scanner when the market environment is hostile.** A great setup in a falling market is usually still a losing trade.

**4 checks**:

1. **SPY trend** — Is S&P 500 above its 50-day SMA? Below = downtrend, stand aside.
2. **VIX level** — Below 25? Above = elevated fear → riskier trades.
3. **VIX/VXV ratio** — Below 1.0? Above = acute short-term stress.
4. **Sector RS** — For each stock, is its sector ETF outperforming SPY over 60 days?

**Result**: 🟢 GREEN (all pass) · 🟡 YELLOW (mixed) · 🔴 RED (halt scanner)

---

### 🔬 MODULE 2 — Technical Screener

Each filter can be toggled. A stock must pass **ALL enabled filters** to be a "New Signal."

| # | Filter | What it checks | Why |
|---|---|---|---|
| Pre | **Liquidity & price floor** 🔒 | Price ≥ $2 AND avg vol ≥ 500K | Prevents flagging untradeable penny stocks (mandatory) |
| 1 | **MA alignment** | Price > SMA20 > SMA50 | Confirms multi-timeframe uptrend |
| 2 | **OBV breakout** | OBV at 20-day high | Volume leading price = accumulation |
| 3 | **Keltner breakout** | Close > Upper Keltner Band | Volatility breakout = momentum thrust |
| 4 | **Volume surge** | Today's vol > 1.5× avg(20) | Institutional participation |
| 5 | **Whipsaw filter** | Trend is clean, not choppy | Avoid range-bound chop |
| 6 | **RSI divergence** | No bearish divergence | Catch momentum loss early |
| 7* | **Pullback trigger** | Bounce off SMA50 + RSI cool-and-turn | For "pullback" strategy |
| 8* | **Reversal trigger** | Lower Keltner pierce + RSI oversold cross | For "reversal" strategy |

*Filters 7-8 are used by their respective strategy profiles.

> **Why no Beta filter?** Beta is an academic CAPM statistic measuring past 1-year covariance with SPY. It conflicts with the ATR/Keltner-based technical analysis we actually use, and would reject exactly the kind of setups we want — previously quiet stocks that JUST started a clean breakout. ATR is the technical analyst's true volatility measure. Beta is still **shown** in the output table for reference, never used to filter.

---

### 💰 MODULE 3 — Risk Management

#### Position sizing math
`Shares = (Equity × Risk%) / (Entry - Stop)`

Example: $10,000 equity, 2% risk, Entry $50, Stop $48 → $200 risk / $2 per share = **100 shares**

#### ATR-based stop loss
`Initial Stop = Entry - (ATR_multiplier × ATR(14))`

Defaults: 2.0× ATR (breakout) · 1.5× ATR (pullback) · 1.0× ATR (reversal)

#### R/R ratio gate
`R/R = (Target - Entry) / (Entry - Stop)` — Minimum 3.0 by default

#### Trailing stop "ratchet"
`New Stop = max(Current Stop, Floor - ATR_multiplier × ATR)` — uses the **same** ATR multiplier as your entry stop (2× for Breakout, 1.5× for Pullback). Only moves up, never down. Gives the trade room to breathe through normal noise.

#### Volume-confirmed exit
Exit only if `Close < Stop` AND `Volume > Avg Volume` — avoids whipsaw exits on light volume.

---

### 🎯 Strategy Profiles

A dropdown at the top of the page overrides Module 2:

- **Custom** — Use sidebar settings as-is
- **Breakout** — Pure momentum: MA 20/50, Keltner 1.5×, Vol 1.25×, OBV ON, divergence OFF, stop 2× ATR
- **Pullback** — Dip-buy: pullback trigger near SMA50, RSI cool-and-turn, stop 1.5× ATR
- **Reversal** — Range-bound: lower Keltner pierce + RSI oversold cross, stop 1× ATR

---

### 📊 Outputs

- **New Signals** — Stocks passing ALL filters today
- **Top Near-Misses** — 10 closest setups (might trigger soon)
- **Portfolio** — Updated stops/actions for owned positions
- **Macro Detail** — Raw values of every macro check
- **Diagnostics** — Funnel: how many stocks passed each step
        """)
    st.info("👈 Configure in the sidebar, optionally upload a portfolio, then click **🚀 Run EOD scan**.")
