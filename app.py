"""
Murphy Scanner - סורק מניות לפי תורת ג'ון מרפי
Technical Analysis of the Financial Markets + Intermarket Analysis
תומך ב-4,700+ מניות עם סריקה מהירה במצב batch
"""

import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
import os, warnings
warnings.filterwarnings('ignore')

st.set_page_config(
    page_title="Murphy Scanner",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ─────────────────────────────────────────────
# DARK TERMINAL STYLING
# ─────────────────────────────────────────────
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&family=IBM+Plex+Sans:wght@300;400;600&display=swap');
    html, body, [class*="css"] { font-family: 'IBM Plex Sans', sans-serif; background-color: #0d1117; color: #c9d1d9; }
    .stApp { background-color: #0d1117; }
    .main .block-container { padding: 1.5rem 2rem; }
    h1 { font-family: 'IBM Plex Mono', monospace; color: #58a6ff; font-size: 1.6rem; letter-spacing: 0.05em; }
    h2 { font-family: 'IBM Plex Mono', monospace; color: #58a6ff; font-size: 1.1rem; border-bottom: 1px solid #21262d; padding-bottom: 0.4rem; }
    .stButton>button { background: #1f6feb; color: white; border: none; border-radius: 6px; font-family: 'IBM Plex Mono', monospace; font-size: 0.85rem; padding: 0.5rem 1.2rem; width: 100%; }
    .stButton>button:hover { background: #388bfd; }
    .stSelectbox>div>div { background: #161b22; border: 1px solid #30363d; color: #c9d1d9; border-radius: 6px; }
    .stNumberInput>div>div>input { background: #161b22; border: 1px solid #30363d; color: #c9d1d9; font-family: 'IBM Plex Mono', monospace; }
    .stTextInput>div>div>input { background: #161b22; border: 1px solid #30363d; color: #c9d1d9; }
    .stTextArea>div>div>textarea { background: #161b22; border: 1px solid #30363d; color: #c9d1d9; font-family: 'IBM Plex Mono', monospace; font-size: 0.8rem; }
    .stDataFrame { background: #161b22; }
    .stDataFrame thead th { background: #21262d !important; color: #58a6ff !important; font-family: 'IBM Plex Mono', monospace; font-size: 0.75rem; }
    .stDataFrame tbody td { font-family: 'IBM Plex Mono', monospace; font-size: 0.78rem; color: #c9d1d9; }
    .stTabs [data-baseweb="tab-list"] { background: #161b22; border-bottom: 1px solid #21262d; gap: 0; }
    .stTabs [data-baseweb="tab"] { background: transparent; color: #8b949e; font-family: 'IBM Plex Mono', monospace; font-size: 0.82rem; padding: 0.6rem 1.2rem; border-bottom: 2px solid transparent; }
    .stTabs [aria-selected="true"] { color: #58a6ff; border-bottom: 2px solid #1f6feb; background: transparent; }
    .metric-card { background: #161b22; border: 1px solid #21262d; border-radius: 8px; padding: 1rem 1.2rem; margin-bottom: 0.5rem; }
    .metric-label { font-size: 0.72rem; color: #8b949e; text-transform: uppercase; letter-spacing: 0.08em; font-family: 'IBM Plex Mono', monospace; }
    .metric-value { font-size: 1.4rem; font-weight: 600; font-family: 'IBM Plex Mono', monospace; margin: 0.2rem 0; }
    .metric-change { font-size: 0.82rem; font-family: 'IBM Plex Mono', monospace; }
    .green { color: #3fb950; } .red { color: #f85149; } .neutral { color: #8b949e; } .yellow { color: #d29922; }
    .section-header { background: #161b22; border-left: 3px solid #1f6feb; padding: 0.5rem 0.8rem; margin: 1rem 0 0.8rem 0; font-family: 'IBM Plex Mono', monospace; font-size: 0.82rem; color: #58a6ff; }
    .warning-box { background: #3d2c00; border: 1px solid #9e6a03; border-radius: 6px; padding: 0.8rem 1rem; margin: 0.5rem 0; font-size: 0.82rem; color: #d29922; }
    .trap-box { background: #4c1217; border: 1px solid #f85149; border-radius: 6px; padding: 0.8rem 1rem; margin: 0.5rem 0; font-size: 0.82rem; color: #f85149; }
    .info-box { background: #0c2d6b; border: 1px solid #1f6feb; border-radius: 6px; padding: 0.8rem 1rem; margin: 0.5rem 0; font-size: 0.82rem; color: #58a6ff; }
    div[data-testid="stSidebar"] { background: #161b22; border-right: 1px solid #21262d; }
    .stProgress > div > div > div > div { background-color: #1f6feb; }
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────
# 1. TICKER UNIVERSE - מקבצי CSV
# ─────────────────────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

def load_tickers_from_files():
    """
    טוען מניות מהקבצים: sp500_tickers.csv, nasdaq_tickers.csv, nyse_tickers.csv
    מחפש בתיקיית הסקריפט - פשוט שים את הקבצים ליד app.py
    """
    sources = {
        'S&P 500':  os.path.join(SCRIPT_DIR, 'sp500_tickers.csv'),
        'Nasdaq':   os.path.join(SCRIPT_DIR, 'nasdaq_tickers.csv'),
        'NYSE':     os.path.join(SCRIPT_DIR, 'nyse_tickers.csv'),
    }
    results = {}
    for name, path in sources.items():
        if os.path.exists(path):
            try:
                df = pd.read_csv(path)
                col = 'Ticker' if 'Ticker' in df.columns else df.columns[0]
                tickers = df[col].str.strip().str.upper().dropna().tolist()
                tickers = [t for t in tickers if t and len(t) <= 5 and t.replace('-','').isalpha()]
                results[name] = tickers
            except Exception as e:
                results[name] = []
        else:
            results[name] = []
    return results

def get_universe(mode, custom_text=""):
    ticker_sources = load_tickers_from_files()
    sp500  = ticker_sources.get('S&P 500', [])
    nasdaq = ticker_sources.get('Nasdaq', [])
    nyse   = ticker_sources.get('NYSE', [])

    custom = []
    if custom_text.strip():
        custom = [t.strip().upper() for t in custom_text.replace(',', '\n').split('\n') if t.strip()]

    if mode == "S&P 500 בלבד":
        base = sp500
    elif mode == "Nasdaq בלבד":
        base = nasdaq
    elif mode == "NYSE בלבד":
        base = nyse
    elif mode == "S&P 500 + Nasdaq":
        base = list(dict.fromkeys(sp500 + nasdaq))
    elif mode == "Custom בלבד":
        base = custom
    else:  # כל המניות
        base = list(dict.fromkeys(sp500 + nasdaq + nyse))

    combined = list(dict.fromkeys(base + custom))
    return combined, ticker_sources


# ─────────────────────────────────────────────
# 2. INDICATOR CALCULATIONS (לפי מרפי)
# ─────────────────────────────────────────────
def calc_rsi_wilder(series, period=14):
    """RSI בשיטת Wilder's Smoothing - מרפי עמ' 240"""
    delta = series.diff()
    gain  = delta.clip(lower=0)
    loss  = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))

def calc_atr(df, period=14):
    """ATR - שלושת רכיבי True Range לפי מרפי"""
    hl = df['High'] - df['Low']
    hc = (df['High'] - df['Close'].shift(1)).abs()
    lc = (df['Low']  - df['Close'].shift(1)).abs()
    tr = pd.concat([hl, hc, lc], axis=1).max(axis=1)
    return tr.ewm(alpha=1/period, min_periods=period, adjust=False).mean()

def calc_failure_swing_bullish(df, lookback=20):
    """
    Bullish Failure Swing לפי מרפי עמ' 242:
    1. RSI יורד מתחת ל-30 פעמיים
    2. השפל השני של RSI גבוה מהראשון (Higher Low)
    3. המחיר עשה Lower Low בין שני השפלים
    4. אישור מחיר: סגירה מעל שיא הביניים
    """
    if len(df) < lookback + 5:
        return False
    recent = df.tail(lookback)
    below30 = recent[recent['RSI'] < 30]
    if len(below30) < 2:
        return False
    p1_idx, p2_idx = below30.index[0], below30.index[-1]
    if p1_idx == p2_idx:
        return False
    rsi1, rsi2 = below30['RSI'].loc[p1_idx], below30['RSI'].loc[p2_idx]
    price1, price2 = below30['Close'].loc[p1_idx], below30['Close'].loc[p2_idx]
    # Higher Low RSI + Lower Low Price = Divergence
    if not (rsi2 > rsi1 and price2 < price1):
        return False
    # אישור מחיר: סגירה מעל שיא הביניים
    inter_high = recent.loc[p1_idx:p2_idx, 'Close'].max()
    return df['Close'].iloc[-1] > inter_high

def calc_failure_swing_bearish(df, lookback=20):
    """Bearish Failure Swing לפי מרפי עמ' 242"""
    if len(df) < lookback + 5:
        return False
    recent = df.tail(lookback)
    above70 = recent[recent['RSI'] > 70]
    if len(above70) < 2:
        return False
    p1_idx, p2_idx = above70.index[0], above70.index[-1]
    if p1_idx == p2_idx:
        return False
    rsi1, rsi2 = above70['RSI'].loc[p1_idx], above70['RSI'].loc[p2_idx]
    price1, price2 = above70['Close'].loc[p1_idx], above70['Close'].loc[p2_idx]
    if not (rsi2 < rsi1 and price2 > price1):
        return False
    inter_low = recent.loc[p1_idx:p2_idx, 'Close'].min()
    return df['Close'].iloc[-1] < inter_low


# ─────────────────────────────────────────────
# 3. BATCH DOWNLOAD - הלב של הסריקה המהירה
# ─────────────────────────────────────────────
BATCH_SIZE = 100   # yfinance מאפשר ~100 טיקרים במקביל

def download_batch(tickers, period='1y', interval='1d'):
    """הורדת batch של טיקרים ב-yfinance"""
    ticker_str = ' '.join(tickers)
    try:
        raw = yf.download(
            ticker_str,
            period=period,
            interval=interval,
            progress=False,
            auto_adjust=True,
            group_by='ticker',
            threads=True
        )
        return raw
    except Exception:
        return None

def extract_ticker_df(raw, ticker):
    """חילוץ DataFrame של מניה בודדת מה-batch"""
    try:
        if isinstance(raw.columns, pd.MultiIndex):
            if ticker in raw.columns.get_level_values(0):
                df = raw[ticker].copy()
                df = df.dropna(subset=['Close', 'Volume'])
                return df if len(df) > 30 else None
        else:
            # מניה בודדת - raw הוא כבר ה-df
            df = raw.dropna(subset=['Close', 'Volume'])
            return df if len(df) > 30 else None
    except Exception:
        return None


# ─────────────────────────────────────────────
# 4. SCAN ENGINE - batch מהיר
# ─────────────────────────────────────────────
def run_scan(tickers, spy_daily, progress_placeholder, status_placeholder):
    trend_results    = []
    reversion_results = []
    processed = 0
    skipped   = 0
    total     = len(tickers)

    # חלוקה ל-batches
    batches = [tickers[i:i+BATCH_SIZE] for i in range(0, total, BATCH_SIZE)]
    n_batches = len(batches)

    # הורדת Weekly בנפרד (batch נפרד)
    status_placeholder.markdown(
        '<div class="info-box">⬇️ מוריד נתונים שבועיים (batch ראשוני)...</div>',
        unsafe_allow_html=True
    )
    weekly_data = {}
    w_batches = [tickers[i:i+BATCH_SIZE] for i in range(0, total, BATCH_SIZE)]
    for wb in w_batches:
        raw_w = download_batch(wb, period='2y', interval='1wk')
        if raw_w is not None:
            for t in wb:
                df_w = extract_ticker_df(raw_w, t)
                if df_w is not None and len(df_w) >= 14:
                    df_w['RSI_W'] = calc_rsi_wilder(df_w['Close'], 14)
                    weekly_data[t] = df_w

    # סריקה יומית batch by batch
    for b_idx, batch in enumerate(batches):
        pct = (b_idx + 1) / n_batches
        progress_placeholder.progress(
            pct,
            text=f"Batch {b_idx+1}/{n_batches} · עיבוד {min((b_idx+1)*BATCH_SIZE, total)}/{total} מניות"
        )

        raw_d = download_batch(batch, period='1y', interval='1d')
        if raw_d is None:
            skipped += len(batch)
            continue

        for ticker in batch:
            try:
                df = extract_ticker_df(raw_d, ticker)
                if df is None or len(df) < 60:
                    skipped += 1
                    continue

                # ── פילטר נזילות ──
                last_close = df['Close'].iloc[-1]
                avg_vol    = df['Volume'].rolling(20).mean().iloc[-1]
                if last_close < 5.0 or pd.isna(avg_vol) or avg_vol < 500_000:
                    skipped += 1
                    continue

                # ── אינדיקטורים יומיים ──
                df['SMA50']  = df['Close'].rolling(50).mean()
                df['SMA200'] = df['Close'].rolling(200).mean()
                df['RSI']    = calc_rsi_wilder(df['Close'], 14)
                df['ATR']    = calc_atr(df, 14)

                # Volume Ratio + Max 5d
                df['Vol_SMA20']      = df['Volume'].rolling(20).mean()
                df['Vol_Ratio']      = df['Volume'] / df['Vol_SMA20'].replace(0, np.nan)
                df['Max_Vol_Ratio_5d'] = df['Vol_Ratio'].rolling(5).max()

                # גבולות אופקיים 6 חודשים (126 ימי מסחר) - shift(1) = לא כולל היום
                df['H_Peak_126']   = df['High'].rolling(126).max().shift(1)
                df['L_Trough_126'] = df['Low'].rolling(126).min().shift(1)

                last = df.iloc[-1]
                close      = last['Close']
                sma50      = last['SMA50']
                sma200     = last['SMA200']
                rsi        = last['RSI']
                atr        = last['ATR']
                max_vol_r  = last['Max_Vol_Ratio_5d']
                peak_126   = last['H_Peak_126']
                trough_126 = last['L_Trough_126']

                if pd.isna(sma50) or pd.isna(sma200) or pd.isna(rsi) or pd.isna(atr):
                    skipped += 1
                    continue

                # ── Weekly RSI ──
                w_rsi      = np.nan
                w_rsi_prev = np.nan
                if ticker in weekly_data:
                    w_df = weekly_data[ticker]
                    if len(w_df) >= 2:
                        w_rsi      = w_df['RSI_W'].iloc[-1]
                        w_rsi_prev = w_df['RSI_W'].iloc[-3] if len(w_df) >= 4 else np.nan

                # ── RS Slope vs SPY ──
                rs_slope = np.nan
                try:
                    merged = df[['Close']].join(spy_daily[['Close']], rsuffix='_spy', how='inner')
                    if len(merged) >= 25:
                        merged['RS'] = merged['Close'] / merged['Close_spy']
                        rs_slope = float(np.polyfit(range(20), merged['RS'].iloc[-20:].values, 1)[0])
                except Exception:
                    pass

                # ── Failure Swings ──
                bull_div  = calc_failure_swing_bullish(df)
                bear_div  = calc_failure_swing_bearish(df)

                processed += 1

                # ════════════════════════════════
                # TAB 2: TREND FOLLOWING
                # ════════════════════════════════
                in_uptrend     = close > sma50 and sma50 > sma200
                vol_confirmed  = (not pd.isna(max_vol_r)) and max_vol_r >= 1.5
                near_resistance = (
                    not pd.isna(peak_126)
                    and peak_126 > 0
                    and close >= peak_126 * 0.97
                )

                if in_uptrend and vol_confirmed and not near_resistance:
                    dist_res = ((peak_126 - close) / close * 100) if not pd.isna(peak_126) else np.nan
                    trend_results.append({
                        'Ticker':               ticker,
                        'Close $':              round(close, 2),
                        'SMA50':                round(sma50, 2),
                        'SMA200':               round(sma200, 2),
                        'RSI יומי':             round(rsi, 1),
                        'RSI שבועי':            round(w_rsi, 1) if not pd.isna(w_rsi) else None,
                        'Vol Ratio Max 5d':     round(max_vol_r, 2),
                        'RS_Slope':             round(rs_slope, 7) if not pd.isna(rs_slope) else 0,
                        'התנגדות 6m':           round(peak_126, 2) if not pd.isna(peak_126) else None,
                        'מרחק התנגדות %':       round(dist_res, 1) if not pd.isna(dist_res) else None,
                        'ATR':                  round(atr, 2),
                        'Stop 2×ATR':           round(close - 2 * atr, 2),
                    })

                # ════════════════════════════════
                # TAB 3: MEAN REVERSION
                # ════════════════════════════════
                oversold  = rsi < 30
                overbought = rsi > 70

                if oversold or overbought:
                    flag     = ""
                    priority = 1

                    if oversold:
                        status = "🟢 Oversold – קנייה פוטנציאלית"
                        # Breakdown Trap: Weekly RSI שבר מתחת ל-50
                        if not pd.isna(w_rsi) and w_rsi < 50:
                            flag     = "⚠️ Institutional Breakdown Trap"
                            priority = 0
                        if bull_div:
                            flag     = "✅ Bullish Failure Swing מאושר"
                            priority = 2
                    else:
                        status = "🔴 Overbought – מכירה פוטנציאלית"
                        if bear_div:
                            flag     = "✅ Bearish Failure Swing מאושר"
                            priority = 2

                    reversion_results.append({
                        'Ticker':       ticker,
                        'Close $':      round(close, 2),
                        'RSI יומי':     round(rsi, 1),
                        'RSI שבועי':    round(w_rsi, 1) if not pd.isna(w_rsi) else None,
                        'סטאטוס':       status,
                        'סיגנל':        flag,
                        'SMA50':        round(sma50, 2),
                        'SMA200':       round(sma200, 2),
                        'תמיכה 6m':    round(trough_126, 2) if not pd.isna(trough_126) else None,
                        'ATR':          round(atr, 2),
                        'עדיפות':       priority,
                    })

            except Exception:
                skipped += 1
                continue

    # Sort
    df_trend = pd.DataFrame(trend_results)
    if len(df_trend) > 0:
        df_trend = df_trend.sort_values('RS_Slope', ascending=False).reset_index(drop=True)
        df_trend.drop(columns=['RS_Slope'], inplace=True)

    df_rev = pd.DataFrame(reversion_results)
    if len(df_rev) > 0:
        df_rev = df_rev.sort_values('עדיפות', ascending=False).reset_index(drop=True)
        df_rev.drop(columns=['עדיפות'], inplace=True)

    return df_trend, df_rev, processed, skipped


# ─────────────────────────────────────────────
# 5. MARKET DASHBOARD
# ─────────────────────────────────────────────
@st.cache_data(ttl=900)
def get_market_data():
    benchmarks  = {'SPY':'S&P 500','QQQ':'Nasdaq 100','IWM':'Russell 2000','DIA':'Dow Jones'}
    intermarket = {'UUP':'Dollar','TLT':'אג"ח 20Y','GLD':'זהב','USO':'נפט','TIP':'TIPS'}
    sectors     = {
        'XLK':'Tech','XLF':'Financials','XLV':'Health','XLY':'Consumer Disc',
        'XLP':'Staples','XLE':'Energy','XLI':'Industrials','XLB':'Materials',
        'XLRE':'Real Estate','XLU':'Utilities','XLC':'Communication'
    }
    all_t = list(benchmarks) + list(intermarket) + list(sectors)
    results = {}
    try:
        raw = yf.download(' '.join(all_t), period='5d', interval='1d',
                          progress=False, auto_adjust=True, group_by='ticker')
        for t in all_t:
            try:
                df_t = raw[t].dropna() if isinstance(raw.columns, pd.MultiIndex) else raw.dropna()
                if len(df_t) >= 2:
                    c = df_t['Close'].iloc[-1]
                    p = df_t['Close'].iloc[-2]
                    w = df_t['Close'].iloc[0]
                    results[t] = {
                        'close': round(c,2),
                        'chg_d': round((c-p)/p*100,2),
                        'chg_w': round((c-w)/w*100,2)
                    }
            except Exception:
                pass
    except Exception:
        pass
    return results, benchmarks, intermarket, sectors


# ─────────────────────────────────────────────
# 6. CHART & EXECUTION
# ─────────────────────────────────────────────
@st.cache_data(ttl=1800)
def get_chart_data(ticker):
    df = yf.download(ticker, period='14mo', interval='1d', progress=False, auto_adjust=True)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df

def detect_gap(df):
    """
    Breakaway / Runaway Gap - מרפי עמ' 94-96
    Upside gap: Low[today] > High[yesterday]
    """
    for i in range(min(15, len(df)-2), 0, -1):
        idx = len(df) - i - 1
        if idx < 1: continue
        if df['Low'].iloc[idx] > df['High'].iloc[idx-1]:
            return {
                'gap_date': df.index[idx],
                'gap_low':  df['Low'].iloc[idx],
                'days_ago': i
            }
    return None

def calc_measuring_target(df, gap_info):
    """
    Measuring Rule לפי מרפי עמ' 95-96:
    הגאפ = נקודת אמצע המגמה.
    מרחק (תחילת מגמה → גאפ) = מרחק (גאפ → מטרה)
    Target = gap_low + (gap_low - trend_origin)
    """
    gap_idx = df.index.get_loc(gap_info['gap_date'])
    window  = df.iloc[max(0, gap_idx-63):gap_idx]
    origin  = window['Low'].min()
    target  = gap_info['gap_low'] + (gap_info['gap_low'] - origin)
    return origin, target

def fib_levels(swing_low, swing_high):
    """
    Fibonacci Retracement לפי מרפי עמ' 85:
    33%, 50%, 66% של ה-Swing המלא - לא של נר בודד!
    """
    r = swing_high - swing_low
    return {
        'f33': round(swing_high - r*0.333, 2),
        'f50': round(swing_high - r*0.500, 2),
        'f66': round(swing_high - r*0.666, 2),
    }

def build_chart(df, ticker):
    d = df.copy()
    d['SMA50']       = d['Close'].rolling(50).mean()
    d['SMA200']      = d['Close'].rolling(200).mean()
    d['RSI']         = calc_rsi_wilder(d['Close'], 14)
    d['ATR']         = calc_atr(d, 14)
    d['H_Peak_126']  = d['High'].rolling(126).max().shift(1)
    d['L_Trough_126']= d['Low'].rolling(126).min().shift(1)

    gap = detect_gap(d)
    gap_target = trend_origin = None
    if gap:
        trend_origin, gap_target = calc_measuring_target(d, gap)

    fig = make_subplots(rows=2, cols=1, shared_xaxes=True,
                        row_heights=[0.68,0.32], vertical_spacing=0.04)

    # נרות
    fig.add_trace(go.Candlestick(
        x=d.index, open=d['Open'], high=d['High'], low=d['Low'], close=d['Close'],
        increasing_line_color='#3fb950', decreasing_line_color='#f85149',
        increasing_fillcolor='#3fb950', decreasing_fillcolor='#f85149',
        name=ticker, line=dict(width=1)
    ), row=1, col=1)

    fig.add_trace(go.Scatter(x=d.index, y=d['SMA50'],  name='SMA 50',
        line=dict(color='#58a6ff', width=1.5)), row=1, col=1)
    fig.add_trace(go.Scatter(x=d.index, y=d['SMA200'], name='SMA 200',
        line=dict(color='#d29922', width=1.5)), row=1, col=1)

    # קווי Support/Resistance אופקיים
    pk = d['H_Peak_126'].iloc[-1]
    tr_ = d['L_Trough_126'].iloc[-1]
    if not pd.isna(pk):
        fig.add_hline(y=pk,  line_dash='dash', line_color='#f85149', line_width=1,
                      annotation_text=f'התנגדות 6m ${pk:.2f}',
                      annotation_font_color='#f85149', row=1, col=1)
    if not pd.isna(tr_):
        fig.add_hline(y=tr_, line_dash='dash', line_color='#3fb950', line_width=1,
                      annotation_text=f'תמיכה 6m ${tr_:.2f}',
                      annotation_font_color='#3fb950', row=1, col=1)

    if gap and gap_target:
        fig.add_hline(y=gap_target, line_dash='dot', line_color='#bc8cff', line_width=2,
                      annotation_text=f'🎯 מטרה ${gap_target:.2f}',
                      annotation_font_color='#bc8cff', row=1, col=1)
        fig.add_vrect(x0=gap['gap_date'], x1=d.index[-1],
                      fillcolor='rgba(188,140,255,0.04)', row=1, col=1)

    # RSI panel
    fig.add_trace(go.Scatter(x=d.index, y=d['RSI'], name='RSI 14',
        line=dict(color='#79c0ff', width=1.5),
        fill='tozeroy', fillcolor='rgba(121,192,255,0.05)'), row=2, col=1)
    for level, color in [(70,'#f85149'),(50,'#8b949e'),(30,'#3fb950')]:
        fig.add_hline(y=level, line_dash='dash', line_color=color, line_width=0.8, row=2, col=1)

    fig.update_layout(
        template='plotly_dark', paper_bgcolor='#0d1117', plot_bgcolor='#0d1117',
        font=dict(family='IBM Plex Mono', size=11, color='#c9d1d9'),
        title=dict(text=f'  {ticker}', font=dict(size=14, color='#58a6ff')),
        xaxis_rangeslider_visible=False,
        legend=dict(orientation='h', yanchor='bottom', y=1.02, bgcolor='rgba(0,0,0,0)', font=dict(size=10)),
        height=620, margin=dict(l=10, r=20, t=50, b=10)
    )
    fig.update_yaxes(gridcolor='#21262d', zerolinecolor='#21262d')
    fig.update_xaxes(gridcolor='#21262d')
    fig.update_yaxes(title_text='מחיר ($)', row=1, col=1)
    fig.update_yaxes(title_text='RSI', row=2, col=1, range=[0,100])
    return fig, d, gap, gap_target, trend_origin

def calc_position(close, atr, account, risk_pct, sw_low, sw_high, gap_target, peak_126):
    """
    כניסה מפוצלת 50/50 לפי מרפי:
    כניסה 1 = שוק | כניסה 2 = Fib 33%-50%
    Stop = 2×ATR מתחת לממוצע הכניסה
    Target = התנגדות הקרובה / Measuring Rule
    """
    fibs      = fib_levels(sw_low, sw_high)
    entry1    = close
    entry2    = (fibs['f33'] + fibs['f50']) / 2
    avg_entry = (entry1 + entry2) / 2
    stop      = avg_entry - 2 * atr
    risk_ps   = avg_entry - stop
    risk_amt  = account * (risk_pct / 100)
    total_sh  = risk_amt / risk_ps if risk_ps > 0 else 0
    sh1 = sh2 = total_sh / 2

    targets = [t for t in [gap_target, peak_126 if not pd.isna(peak_126) else None]
               if t and t > close]
    target = min(targets) if targets else close + 3 * risk_ps
    rr = (target - avg_entry) / risk_ps if risk_ps > 0 else 0

    return dict(
        entry1=round(entry1,2), entry2=round(entry2,2),
        avg_entry=round(avg_entry,2), stop=round(stop,2), target=round(target,2),
        rr=round(rr,2), sh1=int(sh1), sh2=int(sh2),
        cost1=round(sh1*entry1,0), cost2=round(sh2*entry2,0),
        risk_amt=round(risk_amt,0), fibs=fibs
    )


# ─────────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────────
# בדיקת קבצים
ticker_sources = load_tickers_from_files()
sp_count  = len(ticker_sources.get('S&P 500', []))
nq_count  = len(ticker_sources.get('Nasdaq', []))
ny_count  = len(ticker_sources.get('NYSE', []))
total_unique = len(list(dict.fromkeys(
    ticker_sources.get('S&P 500',[]) +
    ticker_sources.get('Nasdaq',[]) +
    ticker_sources.get('NYSE',[])
)))

with st.sidebar:
    st.markdown("## 📊 Murphy Scanner")
    st.markdown(
        "<div style='font-size:0.72rem;color:#8b949e;'>לפי תורת ג'ון מרפי</div>",
        unsafe_allow_html=True
    )
    st.divider()

    # סטטוס קבצים
    def file_status(name, count):
        icon = "✅" if count > 0 else "❌"
        color = "#3fb950" if count > 0 else "#f85149"
        return f'<span style="color:{color};font-family:IBM Plex Mono;font-size:0.75rem;">{icon} {name}: {count}</span>'

    st.markdown(
        f"{file_status('S&P 500', sp_count)}<br>"
        f"{file_status('Nasdaq', nq_count)}<br>"
        f"{file_status('NYSE', ny_count)}<br>"
        f'<span style="color:#58a6ff;font-family:IBM Plex Mono;font-size:0.75rem;">📋 סה"כ ייחודי: {total_unique}</span>',
        unsafe_allow_html=True
    )

    st.divider()

    universe_mode = st.selectbox("🌍 יקום סריקה", [
        "כל המניות (S&P+Nasdaq+NYSE)",
        "S&P 500 + Nasdaq",
        "S&P 500 בלבד",
        "Nasdaq בלבד",
        "NYSE בלבד",
        "Custom בלבד",
    ])

    custom_text = st.text_area(
        "➕ מניות נוספות",
        placeholder="TSLA\nNVDA\nMETA",
        height=80,
        help="יתוספו לכל יקום שנבחר"
    )

    st.divider()

    # אזהרת זמן
    mode_counts = {
        "כל המניות (S&P+Nasdaq+NYSE)": total_unique,
        "S&P 500 + Nasdaq": sp_count + nq_count,
        "S&P 500 בלבד": sp_count,
        "Nasdaq בלבד": nq_count,
        "NYSE בלבד": ny_count,
        "Custom בלבד": 0,
    }
    est = mode_counts.get(universe_mode, 0)
    # ~100 מניות per batch, ~8 שניות לבatch = ~0.08 שניות למניה
    est_min = max(1, int(est * 0.08 / 60))
    st.markdown(
        f'<div style="font-size:0.75rem;color:#8b949e;font-family:IBM Plex Mono;">'
        f'⏱️ ~{est} מניות<br>זמן משוער: {est_min}–{est_min+5} דקות</div>',
        unsafe_allow_html=True
    )

    scan_btn = st.button("🚀 הרץ סריקה")

    if st.session_state.get('scan_done'):
        st.markdown(f"""
        <div style='font-size:0.73rem;color:#3fb950;margin-top:0.5rem;font-family:IBM Plex Mono;'>
        ✅ {st.session_state.get('scan_time','')}<br>
        עובד: {st.session_state.get('processed',0)}<br>
        מגמה: {st.session_state.get('trend_count',0)} מניות<br>
        RSI קיצוני: {st.session_state.get('rev_count',0)} מניות
        </div>""", unsafe_allow_html=True)

    st.divider()
    st.markdown(
        "<div style='font-size:0.68rem;color:#484f58;'>שים sp500_tickers.csv,<br>nasdaq_tickers.csv,<br>nyse_tickers.csv<br>ליד app.py</div>",
        unsafe_allow_html=True
    )


# ─────────────────────────────────────────────
# TABS
# ─────────────────────────────────────────────
tab1, tab2, tab3, tab4 = st.tabs([
    "📊 מצב השוק",
    "📈 Trend Following",
    "📉 Mean Reversion",
    "⚙️ ניתוח & ביצוע",
])


# ═══════════════════════════════════════════
# TAB 1 - MARKET DASHBOARD
# ═══════════════════════════════════════════
with tab1:
    st.markdown("## 📊 מצב השוק")
    mdata, bmarks, imarket, scts = get_market_data()

    def mcard(ticker, name, data):
        if ticker not in data:
            return f'<div class="metric-card"><div class="metric-label">{name}</div><div class="metric-value neutral">N/A</div></div>'
        d = data[ticker]
        cls = "green" if d['chg_d'] > 0 else "red"
        arr = "▲" if d['chg_d'] > 0 else "▼"
        wcls = "green" if d['chg_w'] > 0 else "red"
        return f"""<div class="metric-card">
            <div class="metric-label">{ticker} · {name}</div>
            <div class="metric-value {cls}">${d['close']:,.2f}</div>
            <div class="metric-change {cls}">{arr} {abs(d['chg_d']):.2f}% יום &nbsp;|&nbsp;
            <span class="{wcls}">{'+' if d['chg_w']>0 else ''}{d['chg_w']:.2f}% שבוע</span></div>
        </div>"""

    st.markdown('<div class="section-header">📌 מדדים ראשיים</div>', unsafe_allow_html=True)
    cols = st.columns(4)
    for col, (t,n) in zip(cols, bmarks.items()):
        col.markdown(mcard(t,n,mdata), unsafe_allow_html=True)

    # פרשנות Intermarket
    st.markdown('<div class="section-header">🌐 אינטרמרקט (מרפי: דולר ↔ סחורות ↔ אג"ח ↔ מניות)</div>', unsafe_allow_html=True)
    msgs = []
    uup_chg = mdata.get('UUP',{}).get('chg_d',0)
    tlt_chg = mdata.get('TLT',{}).get('chg_d',0)
    gld_chg = mdata.get('GLD',{}).get('chg_d',0)
    uso_chg = mdata.get('USO',{}).get('chg_d',0)
    if uup_chg >  0.3: msgs.append("💵 <b>דולר עולה</b> → לחץ על סחורות / זהב. שלילי לEmergingMarkets.")
    if uup_chg < -0.3: msgs.append("💵 <b>דולר יורד</b> → תמיכה בסחורות, זהב. חיובי לשווקים מתעוררים.")
    if tlt_chg >  0.3: msgs.append("📄 <b>אג\"ח עולה (תשואות יורדות)</b> → חיובי ל-Growth, REITS.")
    if tlt_chg < -0.3: msgs.append("📄 <b>אג\"ח יורד (תשואות עולות)</b> → לחץ על מכפילים גבוהים, REITS.")
    if gld_chg >  0.5: msgs.append("🥇 <b>זהב עולה</b> → ציפיות אינפלציה / חשש מסיכון.")
    if uso_chg >  1.0: msgs.append("🛢️ <b>נפט עולה</b> → תמיכה ב-Energy, לחץ על Consumer.")
    if msgs:
        st.markdown(f'<div class="info-box">{"<br>".join(msgs)}</div>', unsafe_allow_html=True)

    cols = st.columns(5)
    for col, (t,n) in zip(cols, imarket.items()):
        col.markdown(mcard(t,n,mdata), unsafe_allow_html=True)

    st.markdown('<div class="section-header">🔄 Sector Rotation (ממוין לפי שבוע)</div>', unsafe_allow_html=True)
    sec_rows = []
    for t, n in scts.items():
        if t in mdata:
            d = mdata[t]
            sec_rows.append({'ETF': f"{t} – {n}", 'מחיר': f"${d['close']:,.2f}",
                             'יום %': d['chg_d'], 'שבוע %': d['chg_w']})
    if sec_rows:
        df_s = pd.DataFrame(sec_rows).sort_values('שבוע %', ascending=False)
        st.dataframe(
            df_s.style
                .format({'יום %': '{:+.2f}%', 'שבוע %': '{:+.2f}%'})
                .applymap(lambda v: f"color:{'#3fb950' if v>0 else '#f85149'};font-family:IBM Plex Mono;font-size:0.8rem;"
                          if isinstance(v, float) else "font-family:IBM Plex Mono;font-size:0.8rem;",
                          subset=['יום %','שבוע %'])
                .set_properties(**{'background-color':'#161b22','color':'#c9d1d9'}),
            use_container_width=True, height=370
        )

    c1,c2 = st.columns(2)
    with c1:
        st.markdown("""<div class="metric-card" style="font-size:0.78rem;line-height:1.9;">
        <div class="metric-label">קשרים בין-שוקיים לפי מרפי</div><br>
        🔵 דולר ↑ → סחורות ↓ → אינפלציה ↓ → אג"ח ↑ → מניות ↑<br>
        🟡 דולר ↓ → סחורות ↑ → אינפלציה ↑ → אג"ח ↓ → לחץ על מניות<br>
        🔴 תשואות ↑ → לחץ על P/E גבוה, REITS, Utilities<br>
        🟢 תשואות ↓ → נוח ל-Growth, Tech, REITS
        </div>""", unsafe_allow_html=True)
    with c2:
        st.markdown("""<div class="metric-card" style="font-size:0.78rem;line-height:1.9;">
        <div class="metric-label">Sector Rotation – מחזוריות עסקית (מרפי)</div><br>
        📍 שלב 1 – מיתון: אג"ח ↑, Utilities, Staples<br>
        📍 שלב 2 – התאוששות: מניות ↑, Financials, Tech<br>
        📍 שלב 3 – התרחבות: סחורות ↑, Energy, Materials<br>
        📍 שלב 4 – האטה: Defensives, Health Care
        </div>""", unsafe_allow_html=True)


# ─────────────────────────────────────────────
# SCAN TRIGGER
# ─────────────────────────────────────────────
if scan_btn:
    tickers, _ = get_universe(universe_mode, custom_text)
    if not tickers:
        st.error("לא נמצאו מניות. בדוק שהקבצים נמצאים ליד app.py")
    else:
        prog = st.progress(0, text="מאתחל...")
        stat = st.empty()
        with st.spinner(f"מוריד SPY כבסיס RS..."):
            spy = yf.download('SPY', period='1y', interval='1d', progress=False, auto_adjust=True)
            if isinstance(spy.columns, pd.MultiIndex):
                spy.columns = spy.columns.get_level_values(0)

        stat.markdown(
            f'<div class="info-box">🚀 סורק {len(tickers)} מניות ב-batches של {BATCH_SIZE}...</div>',
            unsafe_allow_html=True
        )
        df_trend, df_rev, proc, skip = run_scan(tickers, spy, prog, stat)

        prog.empty()
        stat.empty()

        st.session_state.df_trend     = df_trend
        st.session_state.df_reversion = df_rev
        st.session_state.scan_done    = True
        st.session_state.scan_time    = datetime.now().strftime('%d/%m %H:%M')
        st.session_state.processed    = proc
        st.session_state.skipped      = skip
        st.session_state.trend_count  = len(df_trend)
        st.session_state.rev_count    = len(df_rev)
        st.session_state.all_tickers  = tickers
        st.rerun()


# ═══════════════════════════════════════════
# TAB 2 - TREND FOLLOWING
# ═══════════════════════════════════════════
with tab2:
    st.markdown("## 📈 Trend Following Scanner")
    st.markdown("""<div class="info-box">
    <b>קריטריונים (מרפי):</b>&nbsp;
    ✅ Close &gt; SMA50 &gt; SMA200 &nbsp;|&nbsp;
    ✅ Max Volume Ratio 5d ≥ 1.5 (breakout מוסדי) &nbsp;|&nbsp;
    ✅ לא בתוך 3% מהתנגדות 6 חודשים &nbsp;|&nbsp;
    📊 ממוין לפי RS vs SPY
    </div>""", unsafe_allow_html=True)

    df_t = st.session_state.get('df_trend')
    if df_t is None or len(df_t) == 0:
        st.markdown('<div class="warning-box">⏳ הרץ סריקה מהסרגל השמאלי.</div>', unsafe_allow_html=True)
    else:
        st.markdown(f"**{len(df_t)} מניות עמדו בכל הקריטריונים**")
        disp = df_t.copy()
        styled = (disp.style
            .format({'Close $':'${:.2f}','SMA50':'${:.2f}','SMA200':'${:.2f}',
                     'ATR':'${:.2f}','Stop 2×ATR':'${:.2f}',
                     'Vol Ratio Max 5d':'{:.2f}×',
                     'RSI יומי':'{:.1f}','מרחק התנגדות %':'{:+.1f}%',
                     'התנגדות 6m':'${:.2f}'}, na_rep='—')
            .background_gradient(subset=['RSI יומי'], cmap='RdYlGn', vmin=30, vmax=70)
            .set_properties(**{'background-color':'#161b22','color':'#c9d1d9',
                               'font-family':'IBM Plex Mono','font-size':'0.78rem'})
        )
        st.dataframe(styled, use_container_width=True, height=520)
        st.download_button("📥 CSV", df_t.to_csv(index=False,encoding='utf-8-sig'),
                           "trend.csv","text/csv")


# ═══════════════════════════════════════════
# TAB 3 - MEAN REVERSION
# ═══════════════════════════════════════════
with tab3:
    st.markdown("## 📉 Mean Reversion Scanner")
    st.markdown("""<div class="info-box">
    <b>קריטריונים (מרפי עמ' 241-244):</b>&nbsp;
    ✅ RSI יומי &lt; 30 או &gt; 70 &nbsp;|&nbsp;
    ⚠️ Institutional Breakdown Trap = Weekly RSI &lt; 50 &nbsp;|&nbsp;
    ✅ Failure Swing = Divergence + אישור מחיר
    </div>""", unsafe_allow_html=True)

    df_r = st.session_state.get('df_reversion')
    if df_r is None or len(df_r) == 0:
        st.markdown('<div class="warning-box">⏳ הרץ סריקה מהסרגל השמאלי.</div>', unsafe_allow_html=True)
    else:
        traps     = df_r[df_r['סיגנל'].str.contains('Trap', na=False)]
        confirmed = df_r[df_r['סיגנל'].str.contains('מאושר', na=False)]

        c1,c2,c3 = st.columns(3)
        c1.markdown(f'<div class="metric-card"><div class="metric-label">סה"כ RSI קיצוני</div><div class="metric-value neutral">{len(df_r)}</div></div>', unsafe_allow_html=True)
        c2.markdown(f'<div class="metric-card"><div class="metric-label">Failure Swing מאושר ✅</div><div class="metric-value green">{len(confirmed)}</div></div>', unsafe_allow_html=True)
        c3.markdown(f'<div class="metric-card"><div class="metric-label">Breakdown Traps ⚠️</div><div class="metric-value red">{len(traps)}</div></div>', unsafe_allow_html=True)

        if len(traps) > 0:
            st.markdown(
                f'<div class="trap-box">⚠️ <b>{len(traps)} Institutional Breakdown Traps</b> – '
                f'מניות שנראות Oversold אבל Weekly RSI שבר מתחת ל-50. המוסדיים יוצאים – אל תיקנה!</div>',
                unsafe_allow_html=True
            )

        st.dataframe(
            df_r.style
                .format({'Close $':'${:.2f}','SMA50':'${:.2f}','SMA200':'${:.2f}',
                         'RSI יומי':'{:.1f}','תמיכה 6m':'${:.2f}','ATR':'${:.2f}'}, na_rep='—')
                .set_properties(**{'background-color':'#161b22','color':'#c9d1d9',
                                   'font-family':'IBM Plex Mono','font-size':'0.78rem'}),
            use_container_width=True, height=520
        )
        st.download_button("📥 CSV", df_r.to_csv(index=False,encoding='utf-8-sig'),
                           "reversion.csv","text/csv")


# ═══════════════════════════════════════════
# TAB 4 - CHART & EXECUTION
# ═══════════════════════════════════════════
with tab4:
    st.markdown("## ⚙️ ניתוח גרפי & חישוב כניסה")

    # איסוף טיקרים לrופדאון
    pool = []
    for key in ('df_trend','df_reversion'):
        df_k = st.session_state.get(key)
        if df_k is not None and len(df_k) > 0:
            pool += df_k['Ticker'].tolist()
    if custom_text.strip():
        pool += [t.strip().upper() for t in custom_text.replace(',','\n').split('\n') if t.strip()]
    if not pool:
        pool = ['AAPL','NVDA','MSFT','SPY','QQQ']
    pool = list(dict.fromkeys(pool))

    ca, cb = st.columns([3,2])
    with ca:
        sel = st.selectbox("📌 מתוצאות הסורק", pool)
    with cb:
        man = st.text_input("🔍 טיקר ידני", placeholder="NVDA")

    ticker_to_use = man.strip().upper() if man.strip() else sel

    if ticker_to_use:
        with st.spinner(f"טוען {ticker_to_use}..."):
            try:
                df_c = get_chart_data(ticker_to_use)
                if df_c is None or len(df_c) < 60:
                    st.error("לא ניתן לטעון נתונים.")
                else:
                    fig, da, gap, gap_tgt, t_origin = build_chart(df_c, ticker_to_use)
                    st.plotly_chart(fig, use_container_width=True)

                    last = da.iloc[-1]
                    cl   = last['Close']
                    at   = last['ATR']
                    s50  = last['SMA50']
                    s200 = last['SMA200']
                    rsi_ = last['RSI']
                    pk_  = last['H_Peak_126']
                    tr_  = last['L_Trough_126']

                    # סיכום טכני
                    st.markdown('<div class="section-header">📐 סיכום טכני</div>', unsafe_allow_html=True)
                    r1,r2,r3,r4 = st.columns(4)
                    trend_s = "עולה ✅" if cl>s50>s200 else "יורד ⬇️" if cl<s50<s200 else "מעורב ↔️"
                    rsi_s   = f"OB 🔴 ({rsi_:.0f})" if rsi_>70 else f"OS 🟢 ({rsi_:.0f})" if rsi_<30 else f"נייטרל ({rsi_:.0f})"
                    gap_s   = f"✅ לפני {gap['days_ago']}d" if gap else "—"
                    r1.markdown(f'<div class="metric-card"><div class="metric-label">מגמה</div><div class="metric-value" style="font-size:1rem;">{trend_s}</div></div>', unsafe_allow_html=True)
                    r2.markdown(f'<div class="metric-card"><div class="metric-label">RSI 14</div><div class="metric-value" style="font-size:1rem;">{rsi_s}</div></div>', unsafe_allow_html=True)
                    r3.markdown(f'<div class="metric-card"><div class="metric-label">ATR</div><div class="metric-value" style="font-size:1rem;">${at:.2f}</div></div>', unsafe_allow_html=True)
                    r4.markdown(f'<div class="metric-card"><div class="metric-label">Gap</div><div class="metric-value" style="font-size:1rem;">{gap_s}</div></div>', unsafe_allow_html=True)

                    if gap and gap_tgt:
                        st.markdown(f"""<div class="info-box">
                        🔺 <b>Measuring Gap (מרפי עמ' 95-96)</b> – לפני {gap['days_ago']} ימים &nbsp;|&nbsp;
                        Gap Low: ${gap['gap_low']:.2f} &nbsp;|&nbsp; Trend Origin: ${t_origin:.2f}<br>
                        <b>🎯 Target = ${gap_tgt:.2f}</b>
                        ({((gap_tgt-cl)/cl*100):+.1f}% מהמחיר הנוכחי)
                        </div>""", unsafe_allow_html=True)

                    # ── Position Sizing ──
                    st.markdown('<div class="section-header">💰 כניסה מפוצלת + ניהול סיכון</div>', unsafe_allow_html=True)
                    pa, pb = st.columns([1,2])
                    with pa:
                        acc   = st.number_input("💼 הון ($)", value=10000, min_value=1000, step=1000)
                        rsk   = st.number_input("⚠️ סיכון %", value=1.0, min_value=0.25, max_value=5.0, step=0.25)
                        st.markdown("**Swing לחישוב Fibonacci:**")
                        sw_lo = st.number_input("Swing Low $",  value=float(round(tr_ if not pd.isna(tr_) else cl*0.85, 2)))
                        sw_hi = st.number_input("Swing High $", value=float(round(pk_ if not pd.isna(pk_) else cl*1.15, 2)))

                    with pb:
                        if sw_hi > sw_lo and sw_hi > cl:
                            ps = calc_position(cl, at, acc, rsk, sw_lo, sw_hi, gap_tgt, pk_)
                            rr_cls = "green" if ps['rr'] >= 2 else "red"
                            rr_msg = "✅ R:R מספק" if ps['rr'] >= 2 else "❌ R:R לא מספק (< 1:2)"
                            st.markdown(f"""<div class="metric-card">
                            <div class="metric-label">תכנית כניסה מפוצלת</div><br>
                            <table style="width:100%;font-family:IBM Plex Mono;font-size:0.8rem;color:#c9d1d9;border-collapse:collapse;">
                            <tr><td style="color:#8b949e;padding:3px 0;">כניסה 1 (50% שוק)</td>
                                <td><b>${ps['entry1']:.2f}</b> × {ps['sh1']} מניות = <b>${ps['cost1']:,.0f}</b></td></tr>
                            <tr><td style="color:#8b949e;padding:3px 0;">כניסה 2 (50% Limit)</td>
                                <td><b>${ps['entry2']:.2f}</b> × {ps['sh2']} מניות = <b>${ps['cost2']:,.0f}</b></td></tr>
                            <tr><td style="color:#8b949e;padding:3px 0;">ממוצע כניסה</td>
                                <td><b>${ps['avg_entry']:.2f}</b></td></tr>
                            <tr><td style="color:#f85149;padding:3px 0;">🛑 Stop Loss (2×ATR)</td>
                                <td><b>${ps['stop']:.2f}</b> &nbsp;({((ps['avg_entry']-ps['stop'])/ps['avg_entry']*100):.1f}% מתחת)</td></tr>
                            <tr><td style="color:#3fb950;padding:3px 0;">🎯 מטרה</td>
                                <td><b>${ps['target']:.2f}</b></td></tr>
                            <tr><td style="color:#8b949e;padding:3px 0;">סיכון $</td>
                                <td>${ps['risk_amt']:,.0f} ({rsk}%)</td></tr>
                            </table><br>
                            <div style="font-size:1.1rem;font-family:IBM Plex Mono;" class="{rr_cls}">
                            R:R = 1:{ps['rr']:.1f} &nbsp; {rr_msg}
                            </div></div>""", unsafe_allow_html=True)

                            if ps['rr'] < 2:
                                st.markdown("""<div class="trap-box">
                                ⛔ <b>Mathematical Risk/Reward Unfavorable</b><br>
                                יחס R:R מתחת ל-1:2. לפי מרפי – אל תיכנס לעסקה שהסיכוי לא שווה את הסיכון.
                                </div>""", unsafe_allow_html=True)

                            f = ps['fibs']
                            st.markdown(f"""<div class="metric-card" style="margin-top:0.5rem;">
                            <div class="metric-label">📐 Fibonacci Retracement (מרפי עמ' 85 – 33/50/66% של Swing)</div><br>
                            <span style="font-family:IBM Plex Mono;font-size:0.82rem;">
                            33%: <b>${f['f33']}</b> &nbsp;|&nbsp; 50%: <b>${f['f50']}</b> &nbsp;|&nbsp; 66%: <b>${f['f66']}</b>
                            </span></div>""", unsafe_allow_html=True)
            except Exception as e:
                st.error(f"שגיאה: {e}")

# FOOTER
st.divider()
st.markdown("""<div style='text-align:center;font-size:0.68rem;color:#484f58;font-family:IBM Plex Mono;'>
Murphy Scanner · "Technical Analysis of the Financial Markets" + "Intermarket Analysis" · John J. Murphy
· לצרכי מחקר בלבד · אינו המלצת השקעה
</div>""", unsafe_allow_html=True)
