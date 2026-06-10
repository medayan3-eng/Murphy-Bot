"""
================================================================================
EOD STOCK SCREENER — Streamlit App (Murphy Methodology)
================================================================================
Run locally:
    streamlit run app.py
Deploy:
    Push to GitHub → connect repo at https://share.streamlit.io
================================================================================
"""
import os
from datetime import datetime

import pandas as pd
import streamlit as st

from eod_screener import (
    get_default_config,
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

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;700&family=Inter:wght@400;500;600;700&display=swap');

html, body, [class*="css"] { font-family: 'Inter', -apple-system, sans-serif !important; }

.main .block-container { padding-top: 1.5rem; padding-bottom: 3rem; max-width: 1400px; }

.terminal-header {
    background: linear-gradient(135deg, #0a1929 0%, #1a3a5c 50%, #0d2847 100%);
    padding: 1.5rem 2rem; border-radius: 12px; border-left: 4px solid #00d4ff;
    margin-bottom: 1.5rem; box-shadow: 0 4px 20px rgba(0, 212, 255, 0.15);
}
.terminal-header h1 {
    color: #ffffff !important; font-size: 1.85rem !important;
    font-weight: 700 !important; margin: 0 !important; letter-spacing: -0.5px;
}
.terminal-header .subtitle { color: #8bb8d9; font-size: 0.9rem; margin-top: 0.4rem; }
.terminal-header .ticker-tape {
    color: #00d4ff; font-family: 'JetBrains Mono', monospace;
    font-size: 0.75rem; letter-spacing: 2px; margin-top: 0.6rem; opacity: 0.7;
}

h2, h3 { color: #1a3a5c !important; font-weight: 600 !important; }

[data-testid="stMetricValue"] {
    font-family: 'JetBrains Mono', monospace !important;
    font-weight: 700 !important; font-size: 1.6rem !important;
}
[data-testid="stMetricLabel"] {
    font-weight: 500 !important; text-transform: uppercase;
    letter-spacing: 0.8px; font-size: 0.72rem !important; opacity: 0.75;
}
[data-testid="stMetric"] {
    background: linear-gradient(180deg, #f8fafc 0%, #f1f5f9 100%);
    padding: 1rem 1.2rem; border-radius: 10px; border-left: 3px solid #00d4ff;
    box-shadow: 0 1px 3px rgba(0,0,0,0.04);
}

.stButton button { font-weight: 600 !important; border-radius: 8px !important; }
.stButton button[kind="primary"] {
    background: linear-gradient(135deg, #00a8cc 0%, #006d8f 100%) !important;
    border: none !important; box-shadow: 0 2px 8px rgba(0, 168, 204, 0.3);
}

.stTabs [data-baseweb="tab"] { font-weight: 600 !important; padding: 0.7rem 1.2rem !important; }
.stTabs [aria-selected="true"] {
    background: linear-gradient(180deg, #00d4ff20 0%, transparent 100%) !important;
    border-bottom: 3px solid #00a8cc !important;
}

[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #f8fafc 0%, #f1f5f9 100%);
    border-right: 1px solid #e2e8f0;
}
[data-testid="stSidebar"] h2 {
    color: #0a1929 !important; font-size: 1.1rem !important;
    text-transform: uppercase; letter-spacing: 1px;
    padding-bottom: 0.5rem; border-bottom: 2px solid #00d4ff;
    margin-bottom: 1rem !important;
}

#MainMenu { visibility: hidden; }
footer { visibility: hidden; }
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="terminal-header">
    <h1>📈 EOD SCREENER TERMINAL</h1>
    <div class="subtitle">Murphy Methodology · Iron Filter · Fibonacci Dashboard</div>
    <div class="ticker-tape">●  DOW THEORY HH/HL  ●  VOLUME CONFIRMATION  ●  FIBONACCI RETRACEMENTS  ●</div>
</div>
""", unsafe_allow_html=True)

UNIVERSE_DIR = "universes"


# ==============================================================================
# Cached helpers
# ==============================================================================
@st.cache_data(ttl=3600)
def _load_universe_cached(path):
    return load_universe(path)


# ==============================================================================
# SIDEBAR — Configuration
# ==============================================================================
st.sidebar.title("⚙️  Configuration")

# ---- Universe ----
st.sidebar.subheader("Universe")

universe_choice = st.sidebar.radio(
    "Source",
    ["🔥 High-Momentum", "S&P 500", "Russell 2000", "Both S&P + R2K",
     "Custom tickers", "Upload CSV"],
    index=0,
)

custom_universe: list[str] = []
if universe_choice == "🔥 High-Momentum":
    p = f"{UNIVERSE_DIR}/high_momentum.csv"
    if os.path.exists(p):
        custom_universe = _load_universe_cached(p)
elif universe_choice == "S&P 500":
    p = f"{UNIVERSE_DIR}/sp500.csv"
    if os.path.exists(p):
        custom_universe = _load_universe_cached(p)
elif universe_choice == "Russell 2000":
    p = f"{UNIVERSE_DIR}/russell2000.csv"
    if os.path.exists(p):
        custom_universe = _load_universe_cached(p)
elif universe_choice == "Both S&P + R2K":
    sp = _load_universe_cached(f"{UNIVERSE_DIR}/sp500.csv") if os.path.exists(f"{UNIVERSE_DIR}/sp500.csv") else []
    r2 = _load_universe_cached(f"{UNIVERSE_DIR}/russell2000.csv") if os.path.exists(f"{UNIVERSE_DIR}/russell2000.csv") else []
    custom_universe = sorted(set(sp) | set(r2))
elif universe_choice == "Custom tickers":
    text = st.sidebar.text_area("Tickers (comma or newline separated)",
                                 placeholder="AAPL, NVDA, TSLA")
    custom_universe = [t.strip().upper() for t in text.replace(",", "\n").split() if t.strip()]
elif universe_choice == "Upload CSV":
    f = st.sidebar.file_uploader("CSV with 'Ticker' column", type=["csv"])
    if f is not None:
        df_u = pd.read_csv(f)
        col = "Ticker" if "Ticker" in df_u.columns else df_u.columns[0]
        custom_universe = df_u[col].astype(str).str.upper().str.strip().tolist()

# Max tickers
if custom_universe:
    universe_size = max(len(custom_universe), 10)
    slider_key = f"max_tickers_{universe_choice}_{universe_size}"
    max_tickers = st.sidebar.slider(
        "Max tickers to scan", min_value=10, max_value=universe_size,
        value=universe_size, step=10, key=slider_key,
        help=f"You have {universe_size} tickers available. Cap lower for faster scans.",
    )
    if len(custom_universe) > max_tickers:
        custom_universe = custom_universe[:max_tickers]
    st.sidebar.caption(f"**{len(custom_universe)}** of {universe_size} tickers selected")
else:
    st.sidebar.warning("⚠️ No tickers loaded.")

# ---- Iron Filter parameters ----
st.sidebar.subheader("Iron Filter")
st.sidebar.caption("All 5 conditions are MANDATORY (Murphy rules).")
min_price = st.sidebar.number_input(
    "Min price ($)", min_value=0.5, max_value=50.0, value=3.0, step=0.5,
    help="Condition 1: Reject stocks below this price.",
)
min_avg_volume = st.sidebar.number_input(
    "Min avg 20-day volume (shares)",
    min_value=50_000, max_value=10_000_000, value=750_000, step=50_000,
    help="Condition 1: Reject illiquid names.",
)
sector_rs_lookback = st.sidebar.slider(
    "Sector RS lookback (days)", min_value=20, max_value=120, value=50, step=10,
    help="Condition 2: Window for sector vs SPY return comparison.",
)
swing_window = st.sidebar.slider(
    "Swing pivot window (bars)", min_value=3, max_value=10, value=5, step=1,
    help="Condition 4: How far to look on each side to confirm a swing high/low. "
         "Smaller = more sensitive to short swings. Larger = only major pivots.",
)

# ---- Macro ----
st.sidebar.subheader("Macro Regime")
macro_enabled = st.sidebar.checkbox("Enable macro kill-switch", value=True,
    help="If macro fails, the scanner halts before evaluating individual stocks.")
vix_enabled = st.sidebar.checkbox("VIX check", value=True)
vix_threshold = 25.0
if vix_enabled:
    vix_threshold = st.sidebar.slider("VIX threshold", 15.0, 40.0, 25.0, 0.5,
                                       help="Above this = market stressed.")
vxv_enabled = st.sidebar.checkbox("VIX/VXV term structure", value=True)
sector_rs_enabled = st.sidebar.checkbox("Sector relative strength", value=True,
    help="Slows the scan a bit (~5–10 minutes for 500 tickers) because it needs "
         "yfinance.info per ticker.")

# ---- Account / risk ----
st.sidebar.subheader("Account")
equity = st.sidebar.slider("Total equity ($)", 1000, 100000, 10000, 1000)
risk_pct = st.sidebar.slider("Risk per trade (%)", 0.5, 5.0, 2.0, 0.25)
atr_stop_mult = st.sidebar.slider("ATR stop multiplier (portfolio)", 0.5, 4.0, 2.0, 0.25,
    help="For trailing stops on portfolio positions.")


# ==============================================================================
# Build config from sidebar
# ==============================================================================
def build_config() -> dict:
    cfg = get_default_config()
    cfg["universe"] = custom_universe
    cfg["min_price"] = float(min_price)
    cfg["min_avg_volume"] = int(min_avg_volume)
    cfg["sector_rs_lookback"] = int(sector_rs_lookback)
    cfg["swing_window"] = int(swing_window)
    cfg["macro"]["enabled"] = bool(macro_enabled)
    cfg["macro"]["vix_enabled"] = bool(vix_enabled)
    cfg["macro"]["vix_threshold"] = float(vix_threshold)
    cfg["macro"]["vxv_enabled"] = bool(vxv_enabled)
    cfg["macro"]["sector_rs_enabled"] = bool(sector_rs_enabled)
    cfg["risk"]["equity"] = float(equity)
    cfg["risk"]["risk_per_trade_pct"] = float(risk_pct) / 100
    cfg["risk"]["atr_stop_multiplier"] = float(atr_stop_mult)
    return cfg


# ==============================================================================
# Main area — Portfolio upload + Run button
# ==============================================================================
left, right = st.columns([1, 1])

with left:
    st.subheader("📁  Existing Portfolio (optional)")
    port_up = st.file_uploader(
        "Upload CSV or Excel with columns: Ticker, Entry_Price, Entry_Date (Shares optional)",
        type=["csv", "xlsx"], key="port_up",
    )
    portfolio_df = None
    if port_up is not None:
        try:
            if port_up.name.lower().endswith(".xlsx"):
                portfolio_df = pd.read_excel(port_up, engine="openpyxl", sheet_name=0)
            else:
                portfolio_df = pd.read_csv(port_up)
            portfolio_df = portfolio_df.dropna(how="all")
            if "Ticker" in portfolio_df.columns:
                portfolio_df = portfolio_df[portfolio_df["Ticker"].notna()]
                portfolio_df = portfolio_df.reset_index(drop=True)
            if portfolio_df.empty:
                st.warning("⚠️ No valid rows found.")
                portfolio_df = None
            else:
                st.success(f"✅ Loaded {len(portfolio_df)} position(s)")
                st.dataframe(portfolio_df, use_container_width=True, hide_index=True)
        except Exception as e:
            st.error(f"❌ Couldn't read the file: {type(e).__name__}: {e}")
            portfolio_df = None

with right:
    st.subheader("▶️  Run Scan")
    st.caption("Scanning is rate-limited by Yahoo. Bigger universes take longer; "
               "sector RS adds ~5–10 minutes per 500 tickers.")
    run_clicked = st.button("🚀 Run EOD scan", type="primary", use_container_width=True)


# ==============================================================================
# Execute scan
# ==============================================================================
if run_clicked:
    if not custom_universe:
        st.error("Universe is empty — pick a source in the sidebar.")
        st.stop()

    cfg = build_config()
    progress = st.progress(0.0)
    status   = st.empty()

    def _progress(frac, msg):
        progress.progress(min(max(frac, 0.0), 1.0))
        status.caption(msg)
    def _status(msg):
        status.caption(msg)

    with st.spinner("Scanning…"):
        result = run_scanner(cfg, portfolio_df=portfolio_df,
                              progress_cb=_progress, status_cb=_status)

    progress.empty(); status.empty()
    st.session_state["last_result"] = result


# ==============================================================================
# Display results
# ==============================================================================
result = st.session_state.get("last_result")
if result is not None:
    passers           = result.get("passers", pd.DataFrame())
    portfolio_updates = result.get("portfolio_updates", pd.DataFrame())
    macro_info        = result.get("macro", {})
    macro_ok          = result.get("macro_ok", True)
    diag              = result.get("diagnostics", {})
    stats             = result.get("stats", {})

    # ---- Market state header ----
    st.markdown("### Market State")
    cols = st.columns(4)
    cols[0].metric("SPY", macro_info.get("SPY", "—"))
    cols[1].metric("VIX", macro_info.get("VIX", "—"), help=macro_info.get("VIX status", ""))
    cols[2].metric("VIX/VXV ratio", macro_info.get("VIX/VXV ratio", "—"),
                  help=macro_info.get("Term structure", ""))
    overall = "🟢 GREEN — scan proceeded" if macro_ok else "🔴 RED — scan halted"
    cols[3].metric("Macro verdict", overall)

    if not macro_ok:
        st.error("⚠️ Macro kill-switch fired. Iron filter was not run. "
                 "Wait for the regime to improve or disable macro checks in the sidebar.")

    # ---- Scan stats ----
    if stats:
        st.markdown("### Scan Stats")
        c = st.columns(4)
        c[0].metric("Tickers requested", f"{stats.get('requested', 0):,}")
        c[1].metric("Downloaded", f"{stats.get('downloaded', 0):,}")
        c[2].metric("Full indicators", f"{stats.get('indicators_ok', 0):,}")
        c[3].metric("Total time",
                    f"{stats.get('t_download_s', 0) + stats.get('t_indicators_s', 0) + stats.get('t_screen_s', 0):.1f}s")

    # ---- Tabs ----
    tab_passers, tab_portfolio, tab_macro, tab_diag, tab_help = st.tabs([
        f"🎯 Iron Filter Passers ({len(passers)})",
        f"📊 Portfolio ({len(portfolio_updates)})",
        "🌍 Macro Detail",
        "🔍 Diagnostics",
        "📚 How It Works",
    ])

    # ============================
    # Tab: Passers (Fibonacci dashboard)
    # ============================
    with tab_passers:
        if passers.empty:
            st.info(
                "**No stocks passed all 5 iron-filter conditions.**\n\n"
                "This is normal — Murphy's iron filter is strict. Check the Diagnostics tab "
                "to see which condition narrowed the funnel most."
            )
        else:
            st.markdown(f"### 🎯 {len(passers)} stock(s) passed Murphy's Iron Filter")
            st.caption("Sorted by current retracement % (smallest pullback = strongest stock). "
                       "Each row shows the rising-wave measurement, the 4 Fibonacci retracement "
                       "targets, and the live retracement %.")

            st.dataframe(
                passers,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Price":              st.column_config.NumberColumn("Price",  format="$%.2f"),
                    "Wave_Low":           st.column_config.NumberColumn("Wave Low",  format="$%.2f"),
                    "Wave_High":          st.column_config.NumberColumn("Wave High", format="$%.2f"),
                    "Wave_Size_%":        st.column_config.NumberColumn("Wave %",  format="%.1f%%"),
                    "Fib_23.6%":          st.column_config.NumberColumn("23.6% retrace", format="$%.2f"),
                    "Fib_38.2%":          st.column_config.NumberColumn("38.2% retrace", format="$%.2f"),
                    "Fib_50.0%":          st.column_config.NumberColumn("50.0% retrace", format="$%.2f"),
                    "Fib_61.8%":          st.column_config.NumberColumn("61.8% retrace", format="$%.2f"),
                    "Current_Retrace_%":  st.column_config.NumberColumn("Now retraced", format="%.1f%%"),
                    "Days_Since_High":    st.column_config.NumberColumn("Days off high", format="%d"),
                    "Vol_Ratio":          st.column_config.NumberColumn("Vol ratio", format="%.2f",
                                                                        help="<1.0 = pullback on lower volume (passes)"),
                    "Sector_RS":          st.column_config.NumberColumn("Sector RS", format="%.2f",
                                                                        help=">1.0 = sector beats SPY"),
                },
            )

            st.caption(
                "📖 **How to read this:** Each stock is in a confirmed uptrend (HH/HL) and "
                "currently pulling back on lower volume than its rising wave. The Fibonacci "
                "levels show where classical retracement support might appear. "
                "**Current Retrace %** tells you how far the pullback has gone — "
                "23.6% = shallow, 38.2% = classical, 50.0% = Dow midpoint, 61.8% = golden ratio "
                "(last line of trend defense)."
            )

    # ============================
    # Tab: Portfolio
    # ============================
    with tab_portfolio:
        if portfolio_updates.empty:
            st.info("Upload a portfolio CSV/Excel to track P/L and trailing stops.")
        else:
            st.dataframe(
                portfolio_updates,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Entry_Price":   st.column_config.NumberColumn("Entry",   format="$%.2f"),
                    "Current_Price": st.column_config.NumberColumn("Current", format="$%.2f"),
                    "P_L_%":         st.column_config.NumberColumn("P/L %",   format="%.2f%%"),
                    "Trailing_Stop": st.column_config.NumberColumn("Stop",    format="$%.2f"),
                    "ATR":           st.column_config.NumberColumn("ATR",     format="$%.2f"),
                    "Days_Held":     st.column_config.NumberColumn("Days",    format="%d"),
                },
            )

    # ============================
    # Tab: Macro detail
    # ============================
    with tab_macro:
        if macro_info:
            df_m = pd.DataFrame(list(macro_info.items()), columns=["Check", "Result"])
            st.dataframe(df_m, use_container_width=True, hide_index=True)
        else:
            st.info("Macro checks disabled.")

    # ============================
    # Tab: Diagnostics
    # ============================
    with tab_diag:
        if not diag:
            st.info("No diagnostics (macro halted or scan didn't run).")
        else:
            st.markdown("### Iron Filter Funnel")
            st.caption("How many tickers passed each consecutive condition.")
            rows = [
                ("Evaluated (had ≥250 bars)",          diag.get("evaluated", 0)),
                ("→ #1  Price/Volume floor",           diag.get("passed_liquidity", 0)),
                ("→ #2  Sector RS > SPY",              diag.get("passed_sector_rs", 0)),
                ("→ #3  Price > SMA50 AND SMA200",     diag.get("passed_ma", 0)),
                ("→ #4  HH and HL structure",          diag.get("passed_hh_hl", 0)),
                ("→ #5  Pullback vol < Rising vol",    diag.get("passed_vol_conf", 0)),
                ("→ ✅ PASSED ALL (Fibonacci shown)",   diag.get("final", 0)),
            ]
            df_d = pd.DataFrame(rows, columns=["Step", "Count"])
            st.dataframe(df_d, use_container_width=True, hide_index=True)

            evaluated = diag.get("evaluated", 0)
            final     = diag.get("final", 0)
            if evaluated > 0:
                rate = 100.0 * final / evaluated
                st.metric("Final pass rate", f"{rate:.1f}%",
                          help=f"{final} of {evaluated} stocks passed all 5 conditions")

    # ============================
    # Tab: How It Works
    # ============================
    with tab_help:
        st.markdown("""
## 📚 How the Murphy Iron Filter Works

This scanner implements a strict, rule-based methodology derived from
**John Murphy's Technical Analysis of the Financial Markets**.
It does **not** generate buy signals — it filters out noise and presents
the *measurements you need to decide for yourself*.

---

### Part A — The Iron Filter (5 conditions, ALL mandatory)

#### Condition 1 — Liquidity & Price Floor
- **Price ≥ $3** (no penny stocks — huge spreads, easy manipulation)
- **Avg 20-day volume ≥ 750,000 shares** (real institutional liquidity)
- **Why:** A perfect technical setup is worthless if you can't enter/exit cleanly.

#### Condition 2 — Sector Relative Strength
- The stock's **sector ETF** must outperform SPY over the last 50 days
- Ratio computed as: `(1 + sector_50d_return) / (1 + spy_50d_return) > 1`
- **Why:** Murphy's sector rotation principle — you want to fish in leading sectors,
  not lagging ones. In geopolitical events (war, recession fears, etc.) certain
  sectors lead and others lag dramatically.

#### Condition 3 — Multi-Timeframe Trend
- Current price must be **above both SMA50 AND SMA200**
- **Why:** SMA50 confirms the medium-term trend; SMA200 confirms the long-term trend.
  Buying below the 200 SMA is fighting the major trend.

#### Condition 4 — Dow Theory: Higher Highs & Higher Lows
- Scanner mathematically finds the last 2 confirmed swing highs and swing lows
- **Test:** Most recent swing high > previous swing high
- **AND:**  Most recent swing low > previous swing low
- **AND:**  The sequence makes structural sense: most recent low precedes most recent high
- **Why:** This is the most rigorous definition of an uptrend in technical analysis.
  Murphy considers HH+HL the foundation of trend-following.

#### Condition 5 — Pullback Volume Confirmation
- After the most recent swing high, the stock starts pulling back
- Compute: **avg volume on pullback days** vs **avg volume on rising-wave days**
- **Required:** pullback_volume < rising_wave_volume (ratio < 1.0)
- **Why:** If the pullback happens on *higher* volume than the rise, that's
  institutional distribution / panic — a major warning. We only want quiet pullbacks
  in healthy uptrends.

---

### Part B — The Fibonacci Dashboard

For each stock that passes all 5 conditions, the scanner shows:

#### Wave measurement
- **Wave Low** = most recent confirmed swing low (start of the rising wave)
- **Wave High** = most recent confirmed swing high (end of the rising wave)
- **Wave Size %** = total size of the rising wave

#### Fibonacci retracement levels (from wave high, retracing toward wave low):
| Level | Meaning |
|-------|---------|
| **23.6%** | Shallow correction — typical of strong momentum stocks |
| **38.2%** | First classical support — common bounce zone |
| **50.0%** | Dow's psychological midpoint — half retrace |
| **61.8%** | Golden ratio — last line of trend defense |

#### Live state
- **Current price** (latest close)
- **Current retracement %** — exactly how far the pullback has gone

---

### How to use the dashboard

The scanner sorts passers by **current retracement % ascending** (smallest pullback
first). This puts the strongest stocks at the top.

Use the Fibonacci levels as **decision frames**, not as automatic triggers:
- Price near 23.6% = pullback is shallow → momentum still strong
- Price near 38.2% = classical buy-the-dip zone
- Price near 50.0% = halfway retrace, watch for hold or break
- Price below 61.8% = trend is at risk

---

### Data source

All data comes from **Yahoo Finance** via the `yfinance` library.
End-of-day OHLCV only. Free, no API key.
Best run after the US market closes (~23:30 Israel time).

### Performance
- High-Momentum (~500 tickers): **2–5 minutes**
- Both S&P + R2K (~2,400 tickers): **8–15 minutes** (with sector RS)
- Sector RS check uses `yfinance.info` per ticker — slow but accurate.
""")

else:
    # Welcome screen
    st.markdown("""
### 👋 Welcome to the Murphy EOD Screener

This scanner uses a **rigorous 5-condition iron filter** based on John Murphy's
classic principles, then presents a **Fibonacci dashboard** for the stocks that pass.

**To run:**
1. 👈 Pick a universe in the sidebar (High-Momentum is fastest)
2. Optionally upload your portfolio CSV
3. Click **🚀 Run EOD scan**

While the scan runs, you'll see live progress. Open the **📚 How It Works** tab
after the scan for full documentation.
""")
    st.info("👈 Configure in the sidebar, then click **🚀 Run EOD scan**.")
