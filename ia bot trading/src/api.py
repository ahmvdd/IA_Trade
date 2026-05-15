"""
api.py
Flask REST API for the trading bot.

Endpoints:
  GET /prices/<asset>  — last 30 days of OHLCV + indicators + signal
  GET /trades          — full trade log from logs/trades.csv

Run with:
  python src/api.py
"""

from flask import Flask, jsonify
from flask_cors import CORS
import json
import pandas as pd

# Reuse the existing pipeline — no logic duplication
from fetch_prices import fetch, add_indicators, add_signals, COMMODITIES
from logger import TRADES_CSV
from paper_trading import PAPER_TRADES_CSV
from ml_model import predict_signal

app = Flask(__name__)
CORS(app)  # allow requests from the Angular dev server on port 4200

# Reverse lookup: "GC=F" → "Gold", "CL=F" → "Oil"
TICKER_TO_NAME = {ticker: name for name, ticker in COMMODITIES.items()}
VALID_TICKERS  = set(COMMODITIES.values())


# ── Helpers ───────────────────────────────────────────────────────────────────

def df_to_records(df: pd.DataFrame) -> list:
    """Convert a DataFrame to a list of JSON-safe dicts.

    Uses pandas' own JSON serialiser (which maps NaN → null correctly),
    then parses it back so Flask can re-serialise the clean Python objects.
    A plain .to_dict() doesn't work because float columns can't hold None —
    NaN would survive into the final JSON as an invalid literal.
    """
    df = df.copy()
    df.index = df.index.astype(str)   # date objects → "YYYY-MM-DD" strings
    df.index.name = "date"

    # orient="index" produces {"YYYY-MM-DD": {col: val, ...}, ...}
    raw = json.loads(df.to_json(orient="index"))
    return [{"date": date, **values} for date, values in raw.items()]


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/prices/<asset>", methods=["GET"])
def get_prices(asset: str):
    """
    Return the last 30 days of prices, indicators, and signal for one asset.

    URL parameter:
      asset — ticker symbol: GC=F (Gold) or CL=F (Oil)

    Example:
      GET /prices/GC=F
    """
    if asset not in VALID_TICKERS:
        return jsonify({
            "error": f"Unknown asset '{asset}'. Valid tickers: {sorted(VALID_TICKERS)}"
        }), 404

    try:
        df = fetch(asset)           # download OHLCV (90 days for warm-up)
        df = add_indicators(df)     # RSI-14, SMA-20, SMA-50
        df = add_signals(df)        # BUY / SELL / HOLD
    except ValueError as e:
        return jsonify({"error": str(e)}), 503  # yfinance failure or no data

    records = df_to_records(df.tail(30))   # trim to the last 30 trading days

    return jsonify({
        "asset": asset,
        "name":  TICKER_TO_NAME[asset],
        "count": len(records),
        "data":  records,
    })


@app.route("/trades", methods=["GET"])
def get_trades():
    """
    Return the full trade log (signal-change events) from logs/trades.csv.

    Returns an empty list when no trades have been recorded yet.
    """
    if not TRADES_CSV.exists():
        return jsonify({"count": 0, "trades": []})

    df = pd.read_csv(TRADES_CSV)
    df = df.where(pd.notnull(df), None)   # NaN → null in JSON

    return jsonify({
        "count":  len(df),
        "trades": df.to_dict(orient="records"),
    })


@app.route("/paper-trades", methods=["GET"])
def get_paper_trades():
    """
    Return all closed paper trades from logs/paper_trades.csv.

    Each record contains: Asset, Entry Date, Entry Price, Exit Date,
    Exit Price, PnL $, PnL %, Result.

    Returns an empty list when no trades have been recorded yet
    (run fetch_prices.py to generate them).
    """
    if not PAPER_TRADES_CSV.exists():
        return jsonify({"count": 0, "trades": []})

    df = pd.read_csv(PAPER_TRADES_CSV)
    df = df.where(pd.notnull(df), None)

    return jsonify({
        "count":  len(df),
        "trades": df.to_dict(orient="records"),
    })


@app.route("/ml-signals/<asset>", methods=["GET"])
def get_ml_signals(asset: str):
    """
    Return the last 30 days of OHLCV + indicators with both the rule-based
    Signal and the Random Forest ML_Signal for comparison.

    Requires the model to have been trained first (run fetch_prices.py).

    Example:
      GET /ml-signals/GC=F
    """
    if asset not in VALID_TICKERS:
        return jsonify({
            "error": f"Unknown asset '{asset}'. Valid tickers: {sorted(VALID_TICKERS)}"
        }), 404

    try:
        df = fetch(asset)
        df = add_indicators(df)
        df = add_signals(df)
    except ValueError as e:
        return jsonify({"error": str(e)}), 503

    df["ML_Signal"] = predict_signal(df, asset)

    records = df_to_records(df.tail(30))

    return jsonify({
        "asset": asset,
        "name":  TICKER_TO_NAME[asset],
        "count": len(records),
        "data":  records,
    })


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # debug=True enables auto-reload on code changes — disable in production
    app.run(debug=True, host='0.0.0.0', port=5001)  # bind IPv4 + IPv6
