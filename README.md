# Trading Terminal

An AI-powered, full-stack trading dashboard for commodity futures. A Python data pipeline fetches live market data, computes technical indicators, generates rule-based signals, and trains a Random Forest classifier to predict 5-day forward returns. An Angular frontend renders everything in a Bloomberg Terminal-inspired dark UI — live price chart, signal history, paper-trading backtest, and side-by-side ML vs rule-based signal comparison.

> **Paper trading only — no real capital is ever used.**

---

## Screenshots

| Prices & ML Signals | Trade Log | Paper Trading |
|---|---|---|
| ![Prices](docs/screenshots/prices.png) | ![Trades](docs/screenshots/trades.png) | ![Paper Trading](docs/screenshots/paper-trading.png) |

---

## Tech Stack

| Layer | Technology |
|---|---|
| **Data & Indicators** | Python 3.14, yfinance, pandas, numpy, ta |
| **Machine Learning** | scikit-learn (RandomForestClassifier), imbalanced-learn (SMOTE), joblib |
| **REST API** | Flask 3, flask-cors |
| **Frontend** | Angular 21 — standalone components, Signals API, computed() |
| **Charts** | Chart.js 4.5, ng2-charts 10 |
| **Styling** | Pure CSS — IBM Plex Mono, Bloomberg Terminal theme |

---

## Project Structure

```
.
├── ia bot trading/                  # Python backend
│   ├── src/
│   │   ├── fetch_prices.py          # Orchestrator: fetch → indicators → signals → ML → backtest
│   │   ├── logger.py                # Signal-change event logger → logs/trades.csv
│   │   ├── paper_trading.py         # Backtest engine (2y) + live simulation (90d)
│   │   ├── ml_model.py              # Random Forest training, SMOTE, inference
│   │   └── api.py                   # Flask REST API (4 endpoints)
│   ├── logs/
│   │   ├── trades.csv               # Signal-change audit trail
│   │   └── paper_trades.csv         # Closed paper trades with P&L
│   ├── models/
│   │   ├── rf_GC_F.pkl              # Trained model — Gold
│   │   └── rf_CL_F.pkl              # Trained model — Oil
│   └── requirements.txt
│
└── trading-dashboard/               # Angular frontend
    └── src/app/
        ├── prices/                  # Live chart, indicator table, ML signal column
        ├── trades/                  # Signal-change log
        ├── paper-trading/           # Backtest results, P&L stats
        ├── services/
        │   └── api.service.ts       # Typed HTTP client for all endpoints
        └── models/
            └── types.ts             # Shared TypeScript interfaces
```

---

## Getting Started

### Prerequisites

- Python 3.11+
- Node.js 18+ and npm

### 1 — Backend

```bash
cd "ia bot trading"

# Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

# Install all dependencies
pip install -r requirements.txt

# Train ML models, run backtest, populate logs (takes ~30s on first run)
python src/fetch_prices.py

# Start the API server  →  http://localhost:5001
python src/api.py
```

### 2 — Frontend

```bash
cd trading-dashboard

npm install

# Start the dev server  →  http://localhost:4200
ng serve
```

---

## API Reference

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/prices/<ticker>` | Last 30 days — OHLCV, RSI-14, SMA-20/50, rule-based signal |
| `GET` | `/trades` | Full signal-change audit trail from `logs/trades.csv` |
| `GET` | `/paper-trades` | All closed backtest trades with entry/exit prices and P&L |
| `GET` | `/ml-signals/<ticker>` | Same as `/prices` plus `ML_Signal` from the Random Forest model |

**Valid tickers:** `GC=F` (Gold futures), `CL=F` (WTI Crude Oil futures)

```bash
# Examples
curl http://localhost:5001/prices/GC=F
curl http://localhost:5001/ml-signals/CL=F
curl http://localhost:5001/paper-trades
```

---

## How It Works

### 1. Data Pipeline

Prices are downloaded via **yfinance** — 90-day window for live display, 2-year window for training and backtest. Two technical indicators are computed with the **ta** library:

| Indicator | Description |
|---|---|
| RSI-14 | Relative Strength Index — momentum oscillator |
| SMA-20 / SMA-50 | Simple Moving Averages — trend filters |

### 2. Rule-Based Signal Strategy

Signals fire on RSI threshold crossovers to avoid triggering on every candle inside an extreme zone:

| Signal | Condition |
|---|---|
| **BUY** | RSI crosses **above 40** — oversold recovery |
| **SELL** | RSI crosses **below 60** — overbought reversal |
| **HOLD** | All other candles |

### 3. Machine Learning — Random Forest Classifier

The ML layer learns directly from price history rather than hand-coded rules.

**Target variable** — 5-day forward return direction:

```
return_J5 = (Close[J+5] − Close[J]) / Close[J] × 100

BUY  if return_J5 > +1%
SELL if return_J5 < −1%
HOLD otherwise
```

Predicting a forward return rather than the next rule-based signal makes the model data-driven and independent of the rule-based strategy.

**Feature set:**

| Feature | Rationale |
|---|---|
| RSI | Momentum state |
| SMA_20 / SMA_50 | Short and long-term trend |
| Close | Absolute price level |
| Volume | Market participation |
| daily_return | Recent price velocity |

**Class imbalance — SMOTE:**
In commodity futures, HOLD dominates (~60–80% of candles). Training naively on raw class frequencies produces a model that predicts HOLD almost exclusively. SMOTE (Synthetic Minority Over-sampling Technique) generates synthetic BUY and SELL samples to balance the training set, forcing the model to learn all three classes.

```
Before SMOTE  →  BUY: 229  HOLD: 122  SELL: 104  (Gold, 2y)
After SMOTE   →  BUY: 185  HOLD: 185  SELL: 185
```

**Model configuration:**

```python
RandomForestClassifier(
    n_estimators  = 200,
    max_depth     = 8,
    min_samples_leaf = 5,
    max_features  = "sqrt",
    random_state  = 42,
    n_jobs        = -1,
)
```

**Training protocol:**
- 2-year dataset split 80 / 20 **chronologically** — future data is never used to train the model
- SMOTE applied on the training split only — the test set is never touched
- Models serialised to `models/rf_GC_F.pkl` and `models/rf_CL_F.pkl` via joblib
- Retrained automatically on every `fetch_prices.py` run

### 4. Paper Trading Engine

`paper_trading.py` simulates a long-only strategy against the rule-based signals:

1. **Open** a long position (1 unit at Close price) on every BUY signal
2. **Close** the position on the next SELL signal
3. Record entry date, entry price, exit date, exit price, P&L ($, %), WIN / LOSS

Two simulation modes run on every `fetch_prices.py` execution:

| Mode | Data window | Behaviour |
|---|---|---|
| **Backtest** | 2 years | Rewrites `paper_trades.csv` with a clean full history |
| **Live** | 90 days | Appends any newly closed cycles |

### 5. Trade Logger

`logger.py` detects rows where the signal transitions (HOLD → BUY, BUY → SELL, etc.) and appends them to `logs/trades.csv` — a compact audit trail of signal events rather than every price row.

---

## Dashboard

**Prices view**
- Asset selector — Gold / Oil
- Stats bar — Last Price, RSI(14), rule-based Signal, **ML Signal** — with count-up animation on load
- Chart.js line chart — Close price, SMA-20, SMA-50, BUY/SELL dot markers
- Last 10 candles table with both **SIGNAL** and **ML SIGNAL** columns for side-by-side comparison

**Trades view**
- Full signal-change audit trail, BUY / SELL / HOLD colour-coded

**Paper Trading view**
- Summary card — Total Trades, Win Rate, Loss Rate, Total P&L, Current Capital, Avg Win, Avg Loss, Avg P&L per trade
- Closed-trade table — entry/exit dates and prices, P&L, WIN rows tinted green / LOSS rows tinted red

---

## Design Decisions

**Why RSI 40/60 instead of the classic 30/70?**
Gold has been in a structural uptrend for two years. RSI rarely reaches 30 in a trending market, producing zero BUY signals over the full 2-year window. The 40/60 crossover generates enough signal events for a meaningful backtest while still identifying momentum reversals.

**Why chronological train/test split?**
Financial time-series data has a temporal dependency — future price information must never leak into the training set. A random split would allow the model to train on data from 2025 and test on 2024, creating look-ahead bias and inflated accuracy.

**Why forward return J+5 instead of next-day rule-based signal?**
Predicting the exact rule-based signal the next day couples the ML model to the hand-coded strategy — the model would just learn to approximate the rules. Predicting the 5-day forward return makes the ML layer independent: it learns directly from price outcomes, not from the rule-based labels.

---

## Notes

- Flask runs on port **5001** — macOS Sequoia reserves port 5000 for AirPlay Receiver
- The backtest resets `paper_trades.csv` on every run to prevent duplicate accumulation
- ML models are retrained on every `fetch_prices.py` run — training takes ~5s per asset on a modern CPU
