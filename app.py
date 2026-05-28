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
        ["S&P 500 (502)", "Russell 2000 (1,909)", "Both (2,411)",
         "Custom tickers", "Upload CSV"],
        index=0,
    )

    custom_universe: list[str] = []
    if universe_choice == "S&P 500 (502)":
        custom_universe = _load_universe_cached(f"{UNIVERSE_DIR}/sp500.csv")
    elif universe_choice == "Russell 2000 (1,909)":
        custom_universe = _load_universe_cached(f"{UNIVERSE_DIR}/russell2000.csv")
    elif universe_choice == "Both (2,411)":
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

    max_tickers = st.slider(
        "Max tickers to scan", min_value=10, max_value=2500, value=200, step=10,
        help="Caps the universe to control runtime. 200 tickers ≈ 1–2 min.",
    )
    if len(custom_universe) > max_tickers:
        custom_universe = custom_universe[:max_tickers]
    st.caption(f"**{len(custom_universe)}** tickers selected")

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
    macro_enabled     = st.checkbox("Enable macro kill-switch", value=True)
    spy_sma           = st.number_input("SPY trend SMA", 5, 400, 50)
    vix_threshold     = st.slider("VIX/VXV ceiling", 0.5, 2.0, 1.0, 0.05)
    sector_check      = st.checkbox("Sector relative-strength check", value=True)
    sector_sma        = st.number_input("Sector ratio SMA", 3, 60, 10)
    ad_line_enabled   = st.checkbox("AD-line check (needs data source)", value=False,
                                    help="yfinance has no NYSE AD line. Plug your "
                                         "own source into fetch_ad_line().")

    # ---- Screener module ----------------------------------------------------
    st.subheader("Module 2 — Screener")
    ma_type   = st.selectbox("MA type", ["sma", "ema"], index=0)
    ma_input  = st.text_input("MA lengths (comma-sep, use 'None' to skip)",
                              value="20, 50, 200")
    ma_lengths = []
    for tok in ma_input.split(","):
        tok = tok.strip()
        if tok.lower() in ("none", ""):
            ma_lengths.append(None)
        else:
            try: ma_lengths.append(int(tok))
            except ValueError: pass

    obv_lookback      = st.slider("OBV lookback (days)", 5, 60, 20)
    keltner_ema       = st.slider("Keltner EMA length", 5, 60, 20)
    keltner_atr       = st.slider("Keltner ATR length", 5, 60, 20)
    keltner_mult      = st.slider("Keltner ATR multiplier", 1.0, 4.0, 2.0, 0.1)
    vol_mult          = st.slider("Volume surge multiplier", 1.0, 5.0, 1.5, 0.1)
    vol_sma           = st.slider("Volume SMA length", 5, 60, 20)
    whipsaw_pct       = st.slider("Whipsaw filter (%)", 0.0, 5.0, 1.0, 0.1) / 100
    divergence_on     = st.checkbox("Bearish-RSI-divergence blocker", value=True)
    rsi_len           = st.slider("RSI length", 5, 30, 14)
    div_lookback      = st.slider("Divergence lookback", 10, 60, 20)

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
            st.metric(
                f"SPY vs SMA{snap['spy_sma_len']}",
                f"${snap['spy_price']:.2f}",
                f"{delta_pct:+.2f}% vs SMA",
                delta_color="normal",
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
        "enabled":             macro_enabled,
        "spy_sma_length":      int(spy_sma),
        "vix_ratio_threshold": float(vix_threshold),
        "sector_check_enabled": sector_check,
        "sector_sma_length":   int(sector_sma),
        "ad_line_enabled":     ad_line_enabled,
    })
    cfg["screener"].update({
        "ma_lengths":         ma_lengths,
        "ma_type":            ma_type,
        "obv_lookback":       int(obv_lookback),
        "keltner_ema_length": int(keltner_ema),
        "keltner_atr_length": int(keltner_atr),
        "keltner_multiplier": float(keltner_mult),
        "volume_sma_length":  int(vol_sma),
        "volume_multiplier":  float(vol_mult),
        "whipsaw_pct":        float(whipsaw_pct),
        "divergence_enabled": divergence_on,
        "divergence_lookback": int(div_lookback),
        "rsi_length":         int(rsi_len),
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

    tab1, tab2, tab3 = st.tabs(
        [f"🆕 New Signals ({len(new_signals)})",
         f"📊 Portfolio ({len(portfolio_updates)})",
         "🌍 Macro Detail"]
    )

    with tab1:
        if new_signals.empty:
            st.info("No new buy signals.")
        else:
            st.dataframe(new_signals, use_container_width=True, hide_index=True)
            tot_risk = new_signals["Risk_$"].sum()
            st.metric("Total $ at risk across new signals", f"${tot_risk:,.2f}")

    with tab2:
        if portfolio_updates.empty:
            st.info("No portfolio positions to evaluate.")
        else:
            def _row_style(row):
                if row["Action"] == "SELL":   return ["background-color:#5a1f1f"] * len(row)
                if row["Action"] == "HOLD":   return ["background-color:#1f3a1f"] * len(row)
                return [""] * len(row)
            st.dataframe(portfolio_updates.style.apply(_row_style, axis=1),
                         use_container_width=True, hide_index=True)

    with tab3:
        macro_df = pd.DataFrame(list(macro_info.items()),
                                columns=["Check", "Result"])
        st.dataframe(macro_df, use_container_width=True, hide_index=True)

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
