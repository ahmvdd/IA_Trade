"""
paper_trading.py
Simulates trades on historical signal data with virtual capital.

Rules:
  - Start with STARTING_CAPITAL (10 000$)
  - Open a LONG position on the first BUY signal (1 unit at Close price)
  - Close the position on the next SELL signal
  - Only one position open at a time
  - Closed trades are saved to logs/paper_trades.csv
  - A summary is printed at the end of each run
"""

import pandas as pd
from pathlib import Path

STARTING_CAPITAL = 10_000.0
BACKTEST_PERIOD  = "2y"      # enough data for multiple BUY→SELL cycles

LOGS_DIR         = Path(__file__).parent.parent / "logs"
PAPER_TRADES_CSV = LOGS_DIR / "paper_trades.csv"

COLUMNS = [
    "Asset",
    "Entry Date", "Entry Price",
    "Exit Date",  "Exit Price",
    "PnL $", "PnL %",
    "Result",
]


# ── Core simulation ───────────────────────────────────────────────────────────

def run_simulation(df: pd.DataFrame, asset_name: str) -> pd.DataFrame:
    """Walk through the DataFrame and simulate BUY/SELL entries one at a time."""
    trades   = []
    position = None  # holds {"date": ..., "price": ...} when a trade is open

    for date, row in df.iterrows():
        signal = row["Signal"]
        price  = row["Close"]

        if signal == "BUY" and position is None:
            position = {"date": date, "price": price}

        elif signal == "SELL" and position is not None:
            entry_price = position["price"]
            pnl_dollar  = price - entry_price
            pnl_pct     = pnl_dollar / entry_price * 100

            trades.append({
                "Asset":       asset_name,
                "Entry Date":  str(position["date"]),
                "Entry Price": round(entry_price, 2),
                "Exit Date":   str(date),
                "Exit Price":  round(price, 2),
                "PnL $":       round(pnl_dollar, 2),
                "PnL %":       round(pnl_pct, 4),
                "Result":      "WIN" if pnl_dollar > 0 else "LOSS",
            })
            position = None

    return pd.DataFrame(trades, columns=COLUMNS) if trades else pd.DataFrame(columns=COLUMNS)


# ── Persistence ───────────────────────────────────────────────────────────────

def reset_paper_trades() -> None:
    """Delete paper_trades.csv so the next run starts with a clean slate.
    Call this once before iterating over all assets."""
    if PAPER_TRADES_CSV.exists():
        PAPER_TRADES_CSV.unlink()


def save_trades(trades: pd.DataFrame) -> None:
    """Append closed trades to paper_trades.csv (creates the file if missing)."""
    if trades.empty:
        return

    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    file_exists = PAPER_TRADES_CSV.exists()
    trades.to_csv(PAPER_TRADES_CSV, mode="a", header=not file_exists, index=False)


# ── Summary ───────────────────────────────────────────────────────────────────

def print_summary(trades: pd.DataFrame, asset_name: str, label: str = "Paper Trading") -> None:
    """Print a compact performance summary for one asset."""
    print(f"\n{'─'*60}")
    print(f"  {label} — {asset_name}")
    print(f"{'─'*60}")

    if trades.empty:
        print("  No completed trades (need at least one BUY→SELL cycle).")
        return

    total_trades = len(trades)
    wins         = (trades["Result"] == "WIN").sum()
    win_rate     = wins / total_trades * 100
    total_pnl    = trades["PnL $"].sum()
    capital      = STARTING_CAPITAL + total_pnl

    for _, t in trades.iterrows():
        icon = "✅" if t["Result"] == "WIN" else "🔴"
        print(
            f"  {icon}  {t['Entry Date']} → {t['Exit Date']}  |  "
            f"Entry: {t['Entry Price']:.2f}  Exit: {t['Exit Price']:.2f}  |  "
            f"P&L: {t['PnL $']:+.2f}$  ({t['PnL %']:+.2f}%)"
        )

    print(f"\n  Total trades : {total_trades}")
    print(f"  Win rate     : {win_rate:.1f}%  ({wins}/{total_trades})")
    print(f"  Total P&L    : {total_pnl:+.2f}$")
    print(f"  Capital now  : {capital:.2f}$  (started at {STARTING_CAPITAL:.0f}$)")


# ── Backtest ──────────────────────────────────────────────────────────────────

def run_backtest(ticker: str, asset_name: str) -> None:
    """
    Fetch 2 years of historical data, run the full signal pipeline, and
    simulate all BUY→SELL cycles.  Appends to paper_trades.csv (the file is
    cleared once before the loop in fetch_prices.main() via reset_paper_trades).

    The import is local to avoid a circular dependency:
      fetch_prices → paper_trading → fetch_prices
    """
    from fetch_prices import fetch, add_indicators, add_signals  # local to break circular import

    try:
        df = fetch(ticker, period=BACKTEST_PERIOD)
        df = add_indicators(df)
        df = add_signals(df)
    except ValueError as e:
        print(f"\n  [ERROR] Backtest fetch failed for {asset_name}: {e}")
        return

    trades = run_simulation(df, asset_name)
    save_trades(trades)
    print_summary(trades, asset_name, label=f"Backtest ({BACKTEST_PERIOD})")

    if not trades.empty:
        print(f"\n  Saved {len(trades)} trade(s) → {PAPER_TRADES_CSV}")


# ── Live simulation entry point ───────────────────────────────────────────────

def run_paper_trading(df: pd.DataFrame, asset_name: str) -> None:
    """90-day live simulation called from fetch_prices.py after signals are computed."""
    trades = run_simulation(df, asset_name)
    save_trades(trades)
    print_summary(trades, asset_name)

    if not trades.empty:
        print(f"\n  Saved {len(trades)} trade(s) → {PAPER_TRADES_CSV}")
