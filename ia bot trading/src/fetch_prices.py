"""
fetch_prices.py
Fetches price data for Gold (GC=F) and Oil (CL=F), computes technical
indicators (RSI-14, SMA-20, SMA-50), applies a simple signal logic, and
prints the last 10 rows with all columns.
"""

import yfinance as yf
import pandas as pd
from ta.momentum import RSIIndicator
from ta.trend import SMAIndicator
from logger import log_signals
from paper_trading import run_paper_trading, run_backtest, reset_paper_trades

# ── Configuration ────────────────────────────────────────────────────────────

COMMODITIES = {
    "Gold": "GC=F",
    "Oil":  "CL=F",
}

# We fetch 90 days so that SMA-50 and RSI-14 have enough warm-up rows.
# Only the last 10 rows are displayed at the end.
FETCH_PERIOD   = "90d"
DISPLAY_ROWS   = 10
INTERVAL       = "1d"

RSI_PERIOD     = 14
SMA_SHORT      = 20
SMA_LONG       = 50
RSI_BUY        = 40   # BUY when RSI crosses above this (oversold recovery)
RSI_SELL       = 60   # SELL when RSI crosses below this (overbought reversal)

# ── Data fetching ─────────────────────────────────────────────────────────────

def fetch(ticker: str, period: str = FETCH_PERIOD) -> pd.DataFrame:
    """Download OHLCV data and return a clean single-level DataFrame."""
    data = yf.download(ticker, period=period, interval=INTERVAL, progress=False)

    if data.empty:
        raise ValueError(f"No data returned for ticker '{ticker}'. Check your internet connection.")

    # yfinance may return a MultiIndex (price_type, ticker) — flatten to single-level
    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.get_level_values(0)

    data = data[["Open", "High", "Low", "Close", "Volume"]].round(2)
    data.index = data.index.date
    return data

# ── Indicators ────────────────────────────────────────────────────────────────

def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Compute RSI-14, SMA-20, and SMA-50 and append them as new columns."""
    close = df["Close"]

    df["RSI"]    = RSIIndicator(close=close, window=RSI_PERIOD).rsi().round(2)
    df["SMA_20"] = SMAIndicator(close=close, window=SMA_SHORT).sma_indicator().round(2)
    df["SMA_50"] = SMAIndicator(close=close, window=SMA_LONG).sma_indicator().round(2)

    return df

# ── Signal logic ──────────────────────────────────────────────────────────────

def add_signals(df: pd.DataFrame) -> pd.DataFrame:
    """
    RSI-crossover signal strategy:
      BUY  — RSI crosses above RSI_BUY (40): oversold recovery
               previous row RSI <= 40  AND current row RSI > 40
      SELL — RSI crosses below RSI_SELL (60): overbought reversal
               previous row RSI >= 60  AND current row RSI < 60
      HOLD — everything else

    Using crossovers rather than static levels prevents the signal from
    firing on every row inside an extreme zone (only the exit from the
    zone triggers the event).  Thresholds 40/60 are used instead of the
    classic 30/70 because Gold has been in a strong uptrend for 2 years
    and RSI rarely dips below 30.
    """
    rsi = df["RSI"]

    buy_signal  = (rsi > RSI_BUY)  & (rsi.shift(1) <= RSI_BUY)
    sell_signal = (rsi < RSI_SELL) & (rsi.shift(1) >= RSI_SELL)

    df["Signal"] = "HOLD"
    df.loc[buy_signal,  "Signal"] = "BUY"
    df.loc[sell_signal, "Signal"] = "SELL"

    return df

# ── Display ───────────────────────────────────────────────────────────────────

def print_table(name: str, df: pd.DataFrame) -> None:
    """Print the last DISPLAY_ROWS rows with indicators and signal."""
    tail = df.tail(DISPLAY_ROWS).copy()
    tail.index.name = "Date"

    # Colour-code the signal for readability in the terminal
    def fmt_signal(s: str) -> str:
        if s == "BUY":
            return "✅ BUY "
        if s == "SELL":
            return "🔴 SELL"
        return "   HOLD"

    tail["Signal"] = tail["Signal"].apply(fmt_signal)

    print(f"\n{'='*75}")
    print(f"  {name}  — last {DISPLAY_ROWS} trading days  (indicators computed on {len(df)} days)")
    print(f"{'='*75}")
    print(tail[["Close", "RSI", "SMA_20", "SMA_50", "Signal"]].to_string())
    print()

# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    print("\nFetching commodity prices and computing indicators …")
    reset_paper_trades()  # clear CSV once so all assets' backtests append cleanly

    for name, ticker in COMMODITIES.items():
        try:
            df = fetch(ticker)
            df = add_indicators(df)
            df = add_signals(df)
            print_table(name, df)
            log_signals(df, name)
            run_backtest(ticker, name)   # 2-year historical simulation (overwrites CSV)
            run_paper_trading(df, name)  # 90-day live simulation (appends new cycles)
        except ValueError as e:
            print(f"\n[ERROR] {e}")

if __name__ == "__main__":
    main()
