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
import numpy as np
from pathlib import Path

STARTING_CAPITAL = 10_000.0
RISK_FREE_RATE   = 0.05   # annualised, used for Sharpe Ratio (US T-bill ~5%)
BACKTEST_PERIOD  = "2y"      # enough data for multiple BUY→SELL cycles

LOGS_DIR         = Path(__file__).parent.parent / "logs"
PAPER_TRADES_CSV = LOGS_DIR / "paper_trades.csv"

COL_PNL_DOLLAR = "PnL $"
COL_PNL_PCT    = "PnL %"

COLUMNS = [
    "Asset",
    "Entry Date", "Entry Price",
    "Exit Date",  "Exit Price",
    COL_PNL_DOLLAR, COL_PNL_PCT,
    "Result",
]


# ── Financial metrics ─────────────────────────────────────────────────────────

def compute_metrics(trades: pd.DataFrame) -> dict:
    """
    Compute Sharpe Ratio, Max Drawdown, and Win Rate from closed trades.

    - Sharpe  : annualised (sqrt(252)) using per-trade % returns
    - Drawdown: max peak-to-trough loss on cumulative P&L curve
    - Win Rate: % of trades with positive P&L
    """
    if trades.empty:
        return {"sharpe": None, "max_drawdown": None, "win_rate": None, "total_trades": 0}

    returns = trades[COL_PNL_PCT].values / 100   # decimal form

    # Sharpe — annualise assuming ~252 trading days per year
    mean_r = np.mean(returns)
    std_r  = np.std(returns, ddof=1)
    daily_rf = RISK_FREE_RATE / 252
    sharpe = float((mean_r - daily_rf) / std_r * np.sqrt(252)) if std_r > 0 else None

    # Max Drawdown on cumulative P&L curve
    cumulative  = np.cumsum(trades[COL_PNL_DOLLAR].values)
    running_max = np.maximum.accumulate(cumulative)
    drawdowns   = cumulative - running_max
    max_drawdown = float(drawdowns.min())

    wins     = (trades["Result"] == "WIN").sum()
    win_rate = float(wins / len(trades) * 100)

    return {
        "sharpe":       round(sharpe, 3) if sharpe is not None else None,
        "max_drawdown": round(max_drawdown, 2),
        "win_rate":     round(win_rate, 1),
        "total_trades": len(trades),
        "total_pnl":    round(float(trades[COL_PNL_DOLLAR].sum()), 2),
    }


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
                COL_PNL_DOLLAR:       round(pnl_dollar, 2),
                COL_PNL_PCT:       round(pnl_pct, 4),
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
    total_pnl    = trades[COL_PNL_DOLLAR].sum()
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
