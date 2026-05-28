"""
Run the screener from the command line. Writes eod_report.xlsx in CWD.

    python run_cli.py --universe sp500 --max 200
    python run_cli.py --universe russell2000 --portfolio portfolio_sample.csv
    python run_cli.py --universe both --max 500 --equity 250000
"""
from __future__ import annotations

import argparse
import os
import sys

import pandas as pd

from eod_screener import (
    get_default_config,
    load_portfolio,
    load_universe,
    run_scanner,
)

UNIVERSES = {
    "sp500":       "universes/sp500.csv",
    "russell2000": "universes/russell2000.csv",
}


def main() -> int:
    ap = argparse.ArgumentParser(description="EOD Stock Screener CLI")
    ap.add_argument("--universe", choices=["sp500", "russell2000", "both"],
                    default="sp500")
    ap.add_argument("--max", type=int, default=200,
                    help="Max tickers to scan (default 200)")
    ap.add_argument("--portfolio", default="portfolio_sample.csv",
                    help="Portfolio CSV path (default: portfolio_sample.csv)")
    ap.add_argument("--equity", type=float, default=100_000.0)
    ap.add_argument("--risk-pct", type=float, default=2.0,
                    help="Risk per trade in percent (default 2.0)")
    ap.add_argument("--output", default="eod_report.xlsx")
    args = ap.parse_args()

    # Load universe
    if args.universe == "both":
        tickers = sorted(set(load_universe(UNIVERSES["sp500"])) |
                         set(load_universe(UNIVERSES["russell2000"])))
    else:
        tickers = load_universe(UNIVERSES[args.universe])
    tickers = tickers[: args.max]
    print(f"Universe: {args.universe} -> {len(tickers)} tickers")

    # Portfolio
    portfolio_df = None
    if args.portfolio and os.path.exists(args.portfolio):
        portfolio_df = load_portfolio(args.portfolio)
        print(f"Portfolio: {args.portfolio} -> {len(portfolio_df)} positions")
    else:
        print("Portfolio: none")

    # Config
    cfg = get_default_config()
    cfg["universe"]     = tickers
    cfg["total_equity"] = args.equity
    cfg["risk"]["risk_per_trade_pct"] = args.risk_pct / 100

    def _p(f, m=""):
        if m: print(f"  [{f*100:5.1f}%] {m}")

    result = run_scanner(cfg, portfolio_df=portfolio_df, progress_cb=_p)

    new_signals      = result["new_signals"]
    portfolio_updates = result["portfolio_updates"]
    macro            = result["macro"]

    # Write Excel
    with pd.ExcelWriter(args.output, engine="openpyxl") as xl:
        (new_signals if not new_signals.empty
            else pd.DataFrame([{"Note": "No new signals"}])).to_excel(
            xl, sheet_name="New_Signals", index=False)
        (portfolio_updates if not portfolio_updates.empty
            else pd.DataFrame([{"Note": "Empty portfolio"}])).to_excel(
            xl, sheet_name="Portfolio", index=False)
        pd.DataFrame(list(macro.items()),
                     columns=["Check", "Result"]).to_excel(
            xl, sheet_name="Macro", index=False)

    print("\n" + "=" * 60)
    print(f"Macro: {macro.get('overall', 'n/a')}")
    print(f"New Signals: {len(new_signals)}")
    print(f"Portfolio:   {len(portfolio_updates)}")
    print(f"Wrote: {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
