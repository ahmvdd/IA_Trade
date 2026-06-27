"""
ml_model.py
Random Forest classifier that predicts 5-day forward return direction.

Target   : if Close[J+5] > Close[J] by >+1% → BUY
           if Close[J+5] < Close[J] by < -1% → SELL
           otherwise                          → HOLD
Features : RSI, SMA_20, SMA_50, Close, Volume, daily_return (%)
Balancing: SMOTE oversampling on the training set so BUY/SELL are not
           drowned out by the majority HOLD class.
Training : 2 years of historical data, chronological 80/20 split (no shuffle).
"""

import pandas as pd
from pathlib import Path
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, classification_report
from imblearn.over_sampling import SMOTE
import joblib
try:
    from xgboost import XGBClassifier
    XGBOOST_AVAILABLE = True
except ImportError:
    XGBOOST_AVAILABLE = False

MODELS_DIR = Path(__file__).parent.parent / "models"
FEATURES   = ["RSI", "SMA_20", "SMA_50", "Close", "Volume", "daily_return",
              "macd", "macd_signal", "macd_diff"]

FORWARD_DAYS   = 5     # how many days ahead we predict
BUY_THRESHOLD  =  1.0  # % gain to label BUY
SELL_THRESHOLD = -1.0  # % loss to label SELL


# ── Helpers ───────────────────────────────────────────────────────────────────

def _model_path(ticker: str, prefix: str = "rf") -> Path:
    safe = ticker.replace('=', '_').replace('^', '_').replace('-', '_')
    return MODELS_DIR / f"{prefix}_{safe}.pkl"


def _build_features(df: pd.DataFrame) -> pd.DataFrame:
    """Append daily_return and drop rows missing any required feature."""
    out = df.copy()
    out["daily_return"] = out["Close"].pct_change() * 100
    available = [f for f in FEATURES if f in out.columns]
    return out.dropna(subset=available)


def _build_target(df: pd.DataFrame) -> pd.Series:
    """
    Label each row based on the % return FORWARD_DAYS days from now:
      BUY  — future return > +BUY_THRESHOLD %
      SELL — future return < SELL_THRESHOLD %
      HOLD — everything else
    """
    future_close   = df["Close"].shift(-FORWARD_DAYS)
    forward_return = (future_close - df["Close"]) / df["Close"] * 100

    target = pd.Series("HOLD", index=df.index)
    target[forward_return >  BUY_THRESHOLD]  = "BUY"
    target[forward_return <  SELL_THRESHOLD] = "SELL"
    return target


# ── Training ──────────────────────────────────────────────────────────────────

def train_model(ticker: str, asset_name: str) -> dict:
    """
    Fetch 2 years of data, build features + forward-return target, apply SMOTE
    to balance BUY/SELL/HOLD in the training set, then train RF and XGBoost
    side-by-side and persist both models.

    Returns a dict with accuracy and classification_report for each model.
    """
    from fetch_prices import fetch, add_indicators, add_signals  # local — breaks circular import

    print(f"\n{'─'*60}")
    print(f"  ML Training — {asset_name}")
    print(f"{'─'*60}")

    try:
        df = fetch(ticker, period="2y")
        df = add_indicators(df)
        df = add_signals(df)
    except ValueError as e:
        print(f"  [ERROR] {e}")
        return {}

    data           = _build_features(df).copy()
    data["target"] = _build_target(data)
    data           = data.dropna(subset=["target"])

    active_features = [f for f in FEATURES if f in data.columns]
    X = data[active_features]
    y = data["target"]

    print("  Class distribution before SMOTE:")
    for label, count in y.value_counts().items():
        print(f"    {label:4s} : {count}")

    # ── Chronological split ───────────────────────────────────────────────────
    split = int(len(X) * 0.8)
    X_train, X_test = X.iloc[:split], X.iloc[split:]
    y_train, y_test = y.iloc[:split], y.iloc[split:]

    # ── SMOTE ─────────────────────────────────────────────────────────────────
    min_class_size = y_train.value_counts().min()
    k = min(5, min_class_size - 1)
    smote = SMOTE(k_neighbors=k, random_state=42)
    x_train_bal, y_train_bal = smote.fit_resample(X_train, y_train)

    print(f"\n  Train / Test : {len(x_train_bal)} / {len(X_test)} rows (after SMOTE)")

    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    results = {}

    # ── Random Forest ─────────────────────────────────────────────────────────
    rf = RandomForestClassifier(
        n_estimators=200, max_depth=8, min_samples_leaf=5,
        max_features="sqrt", random_state=42, n_jobs=-1,
    )
    rf.fit(x_train_bal, y_train_bal)
    y_pred_rf  = rf.predict(X_test)
    acc_rf     = accuracy_score(y_test, y_pred_rf)
    report_rf  = classification_report(y_test, y_pred_rf, zero_division=0, output_dict=True)
    joblib.dump(rf, _model_path(ticker, "rf"))
    results["rf"] = {"accuracy": acc_rf, "report": report_rf}

    # ── XGBoost ───────────────────────────────────────────────────────────────
    if XGBOOST_AVAILABLE:
        label_map    = {"BUY": 0, "HOLD": 1, "SELL": 2}
        label_unmap  = {v: k for k, v in label_map.items()}
        y_train_enc  = pd.Series(y_train_bal).map(label_map)

        xgb = XGBClassifier(
            n_estimators=200, max_depth=6, learning_rate=0.05,
            subsample=0.8, colsample_bytree=0.8,
            eval_metric="mlogloss",
            random_state=42, n_jobs=-1,
        )
        xgb.fit(x_train_bal, y_train_enc)
        y_pred_xgb_enc = xgb.predict(X_test)
        y_pred_xgb     = pd.Series(y_pred_xgb_enc).map(label_unmap).values
        acc_xgb        = accuracy_score(y_test, y_pred_xgb)
        report_xgb     = classification_report(y_test, y_pred_xgb, zero_division=0, output_dict=True)
        joblib.dump(xgb, _model_path(ticker, "xgb"))
        results["xgb"] = {"accuracy": acc_xgb, "report": report_xgb, "label_map": label_map}

    # ── Comparison table ──────────────────────────────────────────────────────
    print(f"\n  {'Model':<20} {'Accuracy':>10}  {'F1-BUY':>8}  {'F1-SELL':>8}  {'F1-HOLD':>8}")
    print(f"  {'─'*60}")
    for name, res in results.items():
        r   = res["report"]
        f1b = r.get("BUY",  {}).get("f1-score", 0)
        f1s = r.get("SELL", {}).get("f1-score", 0)
        f1h = r.get("HOLD", {}).get("f1-score", 0)
        print(f"  {name.upper():<20} {res['accuracy']:>10.1%}  {f1b:>8.2f}  {f1s:>8.2f}  {f1h:>8.2f}")

    print(f"\n  Models saved → {MODELS_DIR}")
    return results


# ── Inference ─────────────────────────────────────────────────────────────────

def predict_signal(df: pd.DataFrame, ticker: str) -> pd.Series:
    """
    Load the saved model and return an ML_Signal Series aligned with df.index.
    Rows without valid features (NaN warm-up rows) default to HOLD.
    Falls back gracefully if no model file exists yet.
    """
    path = _model_path(ticker)

    if not path.exists():
        print(f"  [ML] No model for {ticker} — run fetch_prices.py first")
        return df["Signal"].rename("ML_Signal")

    model  = joblib.load(path)
    data   = _build_features(df)

    result = pd.Series("HOLD", index=df.index, name="ML_Signal")
    result.loc[data.index] = model.predict(data[FEATURES])

    return result
