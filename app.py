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
    page_title="EOD Stock Screener",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("📈 EOD Stock Screener & Portfolio Manager")
st.caption(
    "Macro kill-switch • Multi-filter EOD screener • ATR-based risk management "
    "• Volume-confirmed trailing exits"
)

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

    # Beta filter (volatility vs SPY)
    beta_on = st.checkbox("✅ Beta filter (vs SPY)", value=True,
                          help="Only keep stocks with beta above the threshold. "
                               "High beta = high volatility = bigger moves.")
    if beta_on:
        beta_min = st.slider("  Minimum beta", 0.5, 3.0, 1.5, 0.1, key="beta_min",
                            help="1.0 = moves with market. 1.5 = 50% more volatile. "
                                 "2.0+ = aggressive, high-volatility names.")
        beta_lb = st.slider("  Beta lookback (days)", 60, 504, 252, 21, key="beta_lb",
                           help="How much history to use. 252 = 1 year.")
    else:
        beta_min, beta_lb = 1.5, 252


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
selected_label = st.selectbox(
    "Choose a strategy", profile_labels, index=0,
    help="Selecting a profile auto-overrides Module 2 filters. "
         "Module 1 (macro) and Module 3 (risk) stay as configured."
)
selected_profile = profile_keys[profile_labels.index(selected_label)]

# Show description
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
    port_up = st.file_uploader("CSV: Ticker, Entry_Price, Entry_Date",
                               type=["csv", "xlsx"], key="port_up")
    portfolio_df = None
    if port_up is not None:
        if port_up.name.lower().endswith(".xlsx"):
            portfolio_df = pd.read_excel(port_up)
        else:
            portfolio_df = pd.read_csv(port_up)
        st.dataframe(portfolio_df, use_container_width=True, hide_index=True)
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
        # Beta filter
        "beta_filter_enabled": beta_on,
        "beta_min":            float(beta_min),
        "beta_lookback":       int(beta_lb),
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

    # Apply strategy profile LAST so it overrides sidebar settings
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

    tab1, tab2, tab3, tab4, tab5 = st.tabs(
        [f"🆕 New Signals ({len(new_signals)})",
         f"🎯 Top Near-Misses ({len(near_misses)})",
         f"📊 Portfolio ({len(portfolio_updates)})",
         "🌍 Macro Detail",
         "🔍 Diagnostics"]
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
            st.dataframe(new_signals, use_container_width=True, hide_index=True)
            tot_risk = new_signals["Risk_$"].sum()
            st.metric("Total $ at risk across new signals", f"${tot_risk:,.2f}")

    with tab2:
        if near_misses.empty:
            st.info("No candidates to evaluate (possibly because no tickers had "
                   "valid data, or all of them passed and are in New Signals).")
        else:
            st.caption("Top 10 stocks ranked by % of filters passed. "
                       "Use this to find stocks that are CLOSE to triggering — they may set up over the next few days.")
            # Color scoring
            def _score_color(v):
                if v >= 80:   return "background-color:#1f5a1f"  # green
                if v >= 60:   return "background-color:#5a5a1f"  # yellow
                return "background-color:#5a1f1f"                # red
            def _style_row(row):
                return [_score_color(row["Score"])] * len(row)
            st.dataframe(near_misses.style.apply(_style_row, axis=1),
                         use_container_width=True, hide_index=True)
            st.caption("**Score** = % of enabled filters passed. "
                       "**Passed** = which filters this stock satisfies. "
                       "**Failed** = which filters this stock is missing.")

    with tab3:
        if portfolio_updates.empty:
            st.info("No portfolio positions to evaluate.")
        else:
            def _row_style(row):
                if row["Action"] == "SELL":   return ["background-color:#5a1f1f"] * len(row)
                if row["Action"] == "HOLD":   return ["background-color:#1f3a1f"] * len(row)
                return [""] * len(row)
            st.dataframe(portfolio_updates.style.apply(_row_style, axis=1),
                         use_container_width=True, hide_index=True)

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
                ("→ Beta filter passed",          diag.get("beta_ok", 0)),
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
    st.info("👈 Configure in the sidebar, optionally upload a portfolio, then click **Run EOD scan**.")
