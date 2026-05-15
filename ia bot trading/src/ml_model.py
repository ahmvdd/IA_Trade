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

MODELS_DIR = Path(__file__).parent.parent / "models"
FEATURES   = ["RSI", "SMA_20", "SMA_50", "Close", "Volume", "daily_return"]

FORWARD_DAYS   = 5     # how many days ahead we predict
BUY_THRESHOLD  =  1.0  # % gain to label BUY
SELL_THRESHOLD = -1.0  # % loss to label SELL


# ── Helpers ───────────────────────────────────────────────────────────────────

def _model_path(ticker: str) -> Path:
    return MODELS_DIR / f"rf_{ticker.replace('=', '_')}.pkl"


def _build_features(df: pd.DataFrame) -> pd.DataFrame:
    """Append daily_return and drop rows missing any required feature."""
    out = df.copy()
    out["daily_return"] = out["Close"].pct_change() * 100
    return out.dropna(subset=FEATURES)


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

def train_model(ticker: str, asset_name: str) -> None:
    """
    Fetch 2 years of data, build features + forward-return target, apply SMOTE
    to balance BUY/SELL/HOLD in the training set, then train and save the model.

    Local import of fetch_prices avoids the circular dependency:
      fetch_prices → ml_model → fetch_prices
    """
    from fetch_prices import fetch, add_indicators, add_signals  # local — breaks circular import

    print(f"\n{'─'*60}")
    print(f"  ML Training — {asset_name}")
    print(f"{'─'*60}")

    try:
        df = fetch(ticker, period="2y")
        df = add_indicators(df)
        df = add_signals(df)        # needed only to keep the pipeline consistent
    except ValueError as e:
        print(f"  [ERROR] {e}")
        return

    data          = _build_features(df).copy()
    data["target"] = _build_target(data)

    # Drop the last FORWARD_DAYS rows — their target is NaN (no future close yet)
    data = data.dropna(subset=["target"])

    X = data[FEATURES]
    y = data["target"]

    print("  Class distribution before SMOTE:")
    for label, count in y.value_counts().items():
        print(f"    {label:4s} : {count}")

    # ── Chronological split ───────────────────────────────────────────────────
    split = int(len(X) * 0.8)
    X_train, X_test = X.iloc[:split], X.iloc[split:]
    y_train, y_test = y.iloc[:split], y.iloc[split:]

    # ── SMOTE — only on training set, never on test set ───────────────────────
    # k_neighbors is capped at (min_class_size - 1) to avoid errors when a
    # minority class has very few samples.
    min_class_size = y_train.value_counts().min()
    k = min(5, min_class_size - 1)

    smote = SMOTE(k_neighbors=k, random_state=42)
    x_train_bal, y_train_bal = smote.fit_resample(X_train, y_train)

    print("\n  Class distribution after SMOTE (train only):")
    for label, count in pd.Series(y_train_bal).value_counts().items():
        print(f"    {label:4s} : {count}")

    # ── Model ─────────────────────────────────────────────────────────────────
    model = RandomForestClassifier(
        n_estimators=200,
        max_depth=8,
        min_samples_leaf=5,
        max_features="sqrt",
        random_state=42,
        n_jobs=-1,
    )
    model.fit(x_train_bal, y_train_bal)

    # ── Evaluation ────────────────────────────────────────────────────────────
    y_pred   = model.predict(X_test)
    accuracy = accuracy_score(y_test, y_pred)

    print(f"\n  Train / Test  : {len(x_train_bal)} / {len(X_test)} rows (after SMOTE)")
    print(f"  Accuracy      : {accuracy:.1%}")
    print(f"\n{classification_report(y_test, y_pred, zero_division=0)}")

    # ── Persist ───────────────────────────────────────────────────────────────
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, _model_path(ticker))
    print(f"  Model saved → {_model_path(ticker)}")


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
