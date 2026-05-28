# 📈 EOD Stock Screener & Portfolio Manager

A modular, configuration-driven End-of-Day stock screener and portfolio
management system built in Python. Three-module architecture:

1. **Macro / Sector kill-switch** — SPY trend, AD-line breadth, VIX/VXV term
   structure, and per-ticker sector relative strength.
2. **EOD Screener** — MA alignment, OBV breakout, Keltner-channel breakout,
   volume surge, whipsaw filter, and an optional bearish-RSI-divergence
   blocker.
3. **Risk & Portfolio** — ATR-based stops, R/R-ratio gate, position sizing,
   ratchet-up trailing stops, and volume-confirmed exits.

Two front-ends:

- **`app.py`** — Streamlit web UI (sidebar config, universe selector, live
  progress, downloadable Excel/CSV).
- **`run_cli.py`** — Command-line runner that writes `eod_report.xlsx`.

---

## Quick start

```bash
git clone https://github.com/<you>/eod-screener.git
cd eod-screener
pip install -r requirements.txt
streamlit run app.py
```

Then open the URL Streamlit prints (typically <http://localhost:8501>).

### CLI usage

```bash
# Scan first 200 S&P 500 names
python run_cli.py --universe sp500 --max 200

# Scan Russell 2000 with a portfolio file
python run_cli.py --universe russell2000 --portfolio portfolio_sample.csv

# Scan everything (S&P 500 + Russell 2000) with custom equity & risk
python run_cli.py --universe both --max 500 --equity 250000 --risk-pct 1.5
```

---

## Universes included

| File | Tickers | Notes |
|------|---------|-------|
| `universes/sp500.csv` | 502 | S&P 500 (vintage list — some symbols delisted/merged) |
| `universes/russell2000.csv` | 1,909 | Russell 2000 small-caps (vintage) |

Both lists are static snapshots — many tickers have been delisted, merged, or
renamed over time. The screener handles missing data gracefully (it just
skips tickers yfinance can't resolve), but for production use you should
refresh these lists from a current source.

### Use your own universe

Either:

- Upload a CSV with a `Ticker` column in the Streamlit app, **or**
- Replace `universes/sp500.csv` with your list, **or**
- Pass `--universe sp500` after putting your tickers in that file.

---

## Configuration

Every knob — moving-average lengths, ATR multipliers, the divergence-blocker
toggle, all of it — lives in the `DEFAULT_CONFIG` dict at the top of
`eod_screener.py`. The Streamlit sidebar exposes all of these as widgets.

A few highlights:

| Setting | Default | Where |
|---|---|---|
| MA alignment lengths | `[20, 50, 200]` | `screener.ma_lengths` (set any element to `None` to skip it) |
| OBV lookback | 20 bars | `screener.obv_lookback` |
| Keltner ATR multiplier | 2.0 | `screener.keltner_multiplier` |
| Volume surge multiplier | 1.5× | `screener.volume_multiplier` |
| Whipsaw filter | 1% above breakout | `screener.whipsaw_pct` |
| ATR stop multiplier | 2.0 | `risk.atr_stop_multiplier` |
| Minimum R/R ratio | 3.0 | `risk.min_rr_ratio` |
| Risk per trade | 2% of equity | `risk.risk_per_trade_pct` |

---

## Portfolio format

CSV or XLSX with three columns:

```csv
Ticker,Entry_Price,Entry_Date
AAPL,180.50,2025-08-15
MSFT,415.20,2025-09-03
```

Optional column `Current_Stop` is honored if present — the trailing stop will
only ratchet **up** from that value, never down.

See `portfolio_sample.csv` for a working example.

---

## Output

The Streamlit app shows three tabs (New Signals, Portfolio, Macro) and offers
downloads as Excel (`.xlsx` with three sheets) or CSV.

The CLI writes `eod_report.xlsx` with sheets:

- **New_Signals** — `Ticker, Entry_Price, Initial_Stop, Target, R_R_Ratio, Shares_To_Buy, Risk_$`
- **Portfolio** — `Ticker, Entry_Price, Entry_Date, Current_Price, Trailing_Stop, Unrealized_%, Action (HOLD/SELL)`
- **Macro** — every kill-switch check and its result

---

## Two things to know

### 1. NYSE Advance-Decline line is a placeholder

`yfinance` does not provide it. `fetch_ad_line()` returns `None`, and the
breadth check soft-passes with a status message. To enable it: plug your
own data source (Stooq, Norgate, EODHD, paid feed) into that function and
flip the `AD-line check` checkbox in the sidebar.

### 2. `pandas-ta` & NumPy 2.0

Some `pandas-ta` releases broke with NumPy 2.0 (the `NaN` import issue).
If `pip install` complains, either:

- Use `pip install pandas-ta-classic` (a maintained fork with the same API),
  or
- Pin NumPy: `pip install "numpy<2.0"` before installing `pandas-ta`.

---

## Deploy to Streamlit Community Cloud

1. Push this repo to GitHub.
2. Go to <https://share.streamlit.io> and connect the repo.
3. Set **Main file path** to `app.py`, Python 3.10+ runtime.
4. Click Deploy.

The free tier handles small universes (up to a few hundred tickers) fine.
For full Russell 2000 scans you'll want local execution.

---

## Project structure

```
eod-screener/
├── app.py                    # Streamlit UI
├── eod_screener.py           # Engine: data, indicators, modules 1-3, orchestration
├── run_cli.py                # Command-line runner
├── requirements.txt
├── portfolio_sample.csv
├── universes/
│   ├── sp500.csv             # 502 tickers
│   └── russell2000.csv       # 1,909 tickers
├── README.md
├── LICENSE
└── .gitignore
```

---

## Disclaimer

This software is for educational and research purposes only. Nothing in this
repository constitutes investment advice. Past performance does not guarantee
future results. You are responsible for any decisions you make using this
tool. The authors accept no liability for losses incurred from its use.

---

## License

MIT — see [LICENSE](LICENSE).
