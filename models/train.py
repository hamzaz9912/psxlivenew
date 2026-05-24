#!/usr/bin/env python3
"""
PSX Model Training Module
Complete standalone training pipeline for persistent .pkl model artifacts.
- Trains XGBRegressor + MLPRegressor on historical price data (synthetic or CSV)
- Feature engineering (RSI, MA, MACD, etc.) matching project logic
- Telemetry logging: loss + per-epoch duration for `tail -f` monitoring
- Resilience: checkpoint every epoch/iter to models/checkpoints/latest_mlp_checkpoint.pkl
- Auto-resume from checkpoint on crash / OOM / interrupt
- Saves final production models to models/*.pkl (joblib format)
- No UI, no Streamlit, no API changes - pure backend training logic

Usage:
    python -m models.train          # or python models/train.py
    python -m models.train --symbol "KSE-100" --data sample_xausd_data.csv --epochs 100

Output artifacts:
    models/
      kse100_xgb.pkl
      kse100_mlp.pkl
      meta.json
    models/checkpoints/
      latest_mlp_checkpoint.pkl
"""

import os
import sys
import json
import time
import pickle
import argparse
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler
from sklearn.neural_network import MLPRegressor
from sklearn.metrics import mean_squared_error
import xgboost as xgb
from joblib import dump, load

# ─────────────────────────────────────────────────────────────────────────────
#  PATHS (relative to this file so folder is portable)
# ─────────────────────────────────────────────────────────────────────────────
HERE = Path(__file__).resolve().parent
MODELS_DIR = HERE
CHECKPOINT_DIR = HERE / "checkpoints"
CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)

LATEST_CHECKPOINT = CHECKPOINT_DIR / "latest_mlp_checkpoint.pkl"
XGB_MODEL_FILE = MODELS_DIR / "kse100_xgb.pkl"
MLP_MODEL_FILE = MODELS_DIR / "kse100_mlp.pkl"
META_FILE = MODELS_DIR / "meta.json"

# ─────────────────────────────────────────────────────────────────────────────
#  PURE INTERNAL HELPERS (no UI, no st. calls)
# ─────────────────────────────────────────────────────────────────────────────
def compute_rsi(series, period=14):
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(com=period - 1, min_periods=period).mean()
    avg_loss = loss.ewm(com=period - 1, min_periods=period).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def compute_macd(series, fast=12, slow=26, signal=9):
    ema_fast = series.ewm(span=fast, adjust=False).mean()
    ema_slow = series.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    return macd_line, signal_line

def generate_synthetic_historical(n_rows=5000, start_price=100.0, seed=42):
    """Generate realistic long historical price series for offline training."""
    np.random.seed(seed)
    dates = pd.date_range(end=datetime.now(), periods=n_rows, freq="5min")
    # Geometric brownian motion like prices
    returns = np.random.normal(0.00001, 0.001, n_rows)
    prices = start_price * np.cumprod(1 + returns)
    df = pd.DataFrame({
        "Date": dates,
        "Close": prices,
        "Open": prices * (1 + np.random.uniform(-0.001, 0.001, n_rows)),
        "High": prices * (1 + np.random.uniform(0, 0.002, n_rows)),
        "Low": prices * (1 + np.random.uniform(-0.002, 0, n_rows)),
        "Volume": np.random.randint(10000, 500000, n_rows)
    })
    return df

def load_or_generate_data(data_path=None, n_rows=5000):
    if data_path and Path(data_path).exists():
        df = pd.read_csv(data_path)
        # Try to normalize to have 'Close' and 'Date'
        if "close" in df.columns.str.lower():
            df = df.rename(columns={c: "Close" for c in df.columns if c.lower() == "close"})
        if "date" in df.columns.str.lower():
            df = df.rename(columns={c: "Date" for c in df.columns if c.lower() == "date"})
        if "Close" not in df.columns:
            # fallback: use first numeric column as Close
            num_cols = df.select_dtypes(include=[np.number]).columns.tolist()
            if num_cols:
                df = df.rename(columns={num_cols[0]: "Close"})
        if "Date" not in df.columns:
            df["Date"] = pd.date_range(end=datetime.now(), periods=len(df), freq="D")
        df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
        df = df.dropna(subset=["Close", "Date"]).reset_index(drop=True)
        print(f"[DATA] Loaded {len(df)} rows from {data_path}")
        return df
    print(f"[DATA] Generating synthetic historical data ({n_rows} rows) for training...")
    return generate_synthetic_historical(n_rows)

def prepare_features(df, target_col="Close"):
    """Internal feature engineering - identical math to project but pure pandas."""
    df = df.copy()
    df[target_col] = pd.to_numeric(df[target_col], errors="coerce")
    df = df.dropna(subset=[target_col]).reset_index(drop=True)

    df["RSI"] = compute_rsi(df[target_col], period=14)
    df["MA_10"] = df[target_col].rolling(10).mean()
    df["MA_20"] = df[target_col].rolling(20).mean()
    df["Volatility"] = df[target_col].rolling(10).std()
    macd, signal = compute_macd(df[target_col])
    df["MACD"] = macd
    df["Signal"] = signal
    df["Return"] = df[target_col].pct_change()
    df["Target"] = df[target_col].shift(-1)

    feat_cols = [target_col, "RSI", "MA_10", "MA_20", "Volatility", "MACD", "Signal", "Return"]
    clean = df.dropna(subset=feat_cols + ["Target"]).copy()
    return clean, feat_cols, target_col

# ─────────────────────────────────────────────────────────────────────────────
#  TELEMETRY + RESILIENT TRAINING (the "internal ML training logic")
# ─────────────────────────────────────────────────────────────────────────────
def train_with_telemetry_and_checkpoint(X, y, max_epochs=50, resume=True):
    """
    Core training routine with:
    - Per-epoch console telemetry (loss + wall time) for tail -f
    - Checkpoint at end of every epoch/iter to support 5-hour crash recovery
    - Warm-start partial training for MLP to allow resume
    """
    print("\n[TRAIN] Starting resilient MLP training with telemetry...")
    print(f"[TRAIN] Samples: {len(X)}, Max iters/epochs: {max_epochs}")
    print("[TRAIN] Progress will be printed every epoch - safe to tail -f this process\n")

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    model = MLPRegressor(
        hidden_layer_sizes=(128, 64, 32),
        activation="relu",
        solver="adam",
        alpha=0.0001,
        batch_size=256,
        learning_rate="adaptive",
        max_iter=1,          # we control the loop manually
        warm_start=True,     # critical for checkpoint resume
        early_stopping=False,
        random_state=42
    )

    start_epoch = 0
    best_loss = float("inf")
    loss_history = []

    # RESUME from checkpoint if exists
    if resume and LATEST_CHECKPOINT.exists():
        try:
            ckpt = load(LATEST_CHECKPOINT)
            model = ckpt["model"]
            scaler = ckpt["scaler"]
            start_epoch = ckpt.get("epoch", 0)
            loss_history = ckpt.get("loss_history", [])
            X_scaled = scaler.transform(X)  # re-apply same scaler
            print(f"[RESUME] Found checkpoint - continuing from epoch {start_epoch + 1}")
        except Exception as e:
            print(f"[RESUME] Checkpoint load failed ({e}), starting fresh")

    # Manual epoch loop for telemetry + checkpointing (the key internal logic)
    for epoch in range(start_epoch, max_epochs):
        t0 = time.time()

        # One "epoch" = one partial_fit call (sklearn MLP warm_start style)
        model.partial_fit(X_scaled, y)

        # Compute training loss (MSE on same data for telemetry)
        preds = model.predict(X_scaled)
        current_loss = mean_squared_error(y, preds)
        loss_history.append(current_loss)

        dt = time.time() - t0

        # TELEMETRY LOG (clean for background monitoring)
        print(f"[EPOCH {epoch+1:03d}/{max_epochs}] loss={current_loss:.6f} | time={dt:.3f}s | "
              f"lr={getattr(model, 'learning_rate_', 'n/a')} | n_iter={model.n_iter_}")

        # 5-HOUR FAILURE INSURANCE: checkpoint after EVERY epoch
        ckpt = {
            "model": model,
            "scaler": scaler,
            "epoch": epoch,
            "loss_history": loss_history,
            "timestamp": datetime.now().isoformat(),
            "samples": len(X)
        }
        dump(ckpt, LATEST_CHECKPOINT)

        if current_loss < best_loss:
            best_loss = current_loss

        # Optional early stop (small improvement)
        if len(loss_history) > 5 and abs(loss_history[-1] - loss_history[-5]) < 1e-8:
            print("[TRAIN] Early stopping - loss plateau reached")
            break

    # Final fit report
    print(f"\n[TRAIN] MLP training complete. Final loss: {loss_history[-1]:.6f}")
    print(f"[TRAIN] Checkpoint left at: {LATEST_CHECKPOINT}")

    return model, scaler, loss_history

def train_xgb(X, y):
    """Fast XGB training (no epoch loop needed - single fit)."""
    print("[TRAIN] Training XGBoost regressor...")
    model = xgb.XGBRegressor(
        n_estimators=300,
        learning_rate=0.04,
        max_depth=5,
        subsample=0.8,
        colsample_bytree=0.8,
        random_state=42,
        verbosity=0,
        n_jobs=-1
    )
    model.fit(X, y)
    print("[TRAIN] XGB training finished.")
    return model

# ─────────────────────────────────────────────────────────────────────────────
#  MAIN PIPELINE (saves the .pkl files)
# ─────────────────────────────────────────────────────────────────────────────
def main(symbol="KSE-100", data_path=None, epochs=30, force=False):
    print("=" * 70)
    print("PSX HISTORICAL MODEL TRAINING - PERSISTENT .pkl ARTIFACTS")
    print("=" * 70)
    print(f"Symbol     : {symbol}")
    print(f"Data source: {data_path or 'synthetic'}")
    print(f"Epochs     : {epochs}")
    print(f"Checkpoint : {LATEST_CHECKPOINT}")
    print(f"Output dir : {MODELS_DIR}")
    print("=" * 70)

    # 1. Data
    df = load_or_generate_data(data_path, n_rows=8000 if not data_path else 0)

    # 2. Features (internal logic)
    clean_df, feat_cols, target_col = prepare_features(df)
    print(f"[PREP] Clean samples after features: {len(clean_df)} | Features: {feat_cols}")

    X = clean_df[feat_cols].values
    y = clean_df["Target"].values

    # 3. XGB (always full train - fast)
    xgb_model = train_xgb(X, y)
    dump(xgb_model, XGB_MODEL_FILE)
    print(f"[SAVE] {XGB_MODEL_FILE}")

    # 4. MLP with full resilience + telemetry
    mlp_model, mlp_scaler, loss_curve = train_with_telemetry_and_checkpoint(
        X, y, max_epochs=epochs, resume=not force
    )
    dump(mlp_model, MLP_MODEL_FILE)
    dump(mlp_scaler, MODELS_DIR / "kse100_mlp_scaler.pkl")
    print(f"[SAVE] {MLP_MODEL_FILE}")
    print(f"[SAVE] {MODELS_DIR / 'kse100_mlp_scaler.pkl'}")

    # 5. Meta
    meta = {
        "symbol": symbol,
        "trained_at": datetime.now().isoformat(),
        "n_samples": len(clean_df),
        "features": feat_cols,
        "xgb_file": str(XGB_MODEL_FILE.name),
        "mlp_file": str(MLP_MODEL_FILE.name),
        "mlp_scaler_file": "kse100_mlp_scaler.pkl",
        "final_mlp_loss": float(loss_curve[-1]) if loss_curve else None,
        "mlp_n_iter": int(getattr(mlp_model, "n_iter_", 0)),
        "checkpoint_used": str(LATEST_CHECKPOINT) if LATEST_CHECKPOINT.exists() else None,
        "python_version": sys.version,
    }
    with open(META_FILE, "w") as f:
        json.dump(meta, f, indent=2)
    print(f"[SAVE] {META_FILE}")

    # 6. Optional: remove temp checkpoint after successful full run (or keep for resume)
    if LATEST_CHECKPOINT.exists():
        print(f"[INFO] Training checkpoint retained at {LATEST_CHECKPOINT} for future resume.")

    print("\n✅ ALL MODELS SAVED AS .pkl - ready for production loading")
    print("   (These can now be loaded by any inference code without retraining)")
    print("=" * 70)

    return meta

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="PSX Model Training - .pkl Generator")
    parser.add_argument("--symbol", default="KSE-100", help="Asset symbol for naming")
    parser.add_argument("--data", dest="data_path", default=None, help="Path to CSV with historical Close/Date")
    parser.add_argument("--epochs", type=int, default=25, help="Number of training epochs/iters for MLP")
    parser.add_argument("--force", action="store_true", help="Ignore existing checkpoint and start fresh")
    args = parser.parse_args()

    main(symbol=args.symbol, data_path=args.data_path, epochs=args.epochs, force=args.force)


# ─────────────────────────────────────────────────────────────────────────────
# Public exports for all-brands training (pure internal logic, no UI)
# ─────────────────────────────────────────────────────────────────────────────
__all__ = [
    "compute_rsi", "compute_macd", "generate_synthetic_historical",
    "load_or_generate_data", "prepare_features",
    "train_with_telemetry_and_checkpoint", "train_xgb",
    "main"
]
