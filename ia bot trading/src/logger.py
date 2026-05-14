"""
logger.py
Detects signal changes in a DataFrame produced by fetch_prices.py,
appends new events to logs/trades.csv, and prints a console summary.

A "signal change" is any row where the Signal value differs from the
previous row (HOLD → BUY, BUY → HOLD, BUY → SELL, etc.).
"""

import os
import pandas as pd
from pathlib import Path

# Path is relative to the project root, one level above src/
LOGS_DIR   = Path(__file__).parent.parent / "logs"
TRADES_CSV = LOGS_DIR / "trades.csv"

# Columns written to the CSV (and shown in the summary)
LOG_COLUMNS = ["Date", "Asset", "Signal", "Close", "RSI", "SMA_20"]


def detect_changes(df: pd.DataFrame, asset_name: str) -> pd.DataFrame:
    """
    Return a DataFrame of rows where the signal changed compared to
    the previous row. Ignores the very first row (no prior signal to compare).
    """
    # Compare each row's signal with the one before it
    signal_changed = df["Signal"] != df["Signal"].shift(1)

    # The first row always looks like a "change" — skip it
    signal_changed.iloc[0] = False

    changed_rows = df[signal_changed].copy()
    changed_rows.index.name = "Date"
    changed_rows = changed_rows.reset_index()  # make Date a regular column

    # Keep only the columns we want to log
    changed_rows = changed_rows[["Date", "Close", "RSI", "SMA_20", "Signal"]]
    changed_rows.insert(1, "Asset", asset_name)  # inject asset name as second column

    return changed_rows


def save_to_csv(events: pd.DataFrame) -> None:
    """
    Append new signal-change events to trades.csv.
    Creates the file with headers if it does not exist yet;
    appends without headers if it does.
    """
    LOGS_DIR.mkdir(parents=True, exist_ok=True)

    file_exists = TRADES_CSV.exists()
    events.to_csv(
        TRADES_CSV,
        mode="a",           # always append — never overwrite history
        header=not file_exists,
        index=False,
    )


def print_summary(events: pd.DataFrame, asset_name: str) -> None:
    """Print a compact summary of detected signal changes to the console."""
    print(f"\n{'─'*60}")
    print(f"  Signal changes detected for {asset_name}: {len(events)}")
    print(f"{'─'*60}")

    if events.empty:
        print("  No signal changes in this period.")
        return

    for _, row in events.iterrows():
        signal = row["Signal"]
        icon   = "✅" if signal == "BUY" else ("🔴" if signal == "SELL" else "⬜")
        print(
            f"  {icon}  {row['Date']}  |  {signal:<4}  |  "
            f"Close: {row['Close']:.2f}  |  RSI: {row['RSI']:.1f}  |  SMA20: {row['SMA_20']:.2f}"
        )


def log_signals(df: pd.DataFrame, asset_name: str) -> None:
    """
    Main entry point called from fetch_prices.py.
    Detects changes, saves them, and prints the summary.
    """
    events = detect_changes(df, asset_name)
    save_to_csv(events)
    print_summary(events, asset_name)

    if not events.empty:
        print(f"\n  Saved {len(events)} event(s) → {TRADES_CSV}")
