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

try:
    import torch
    import torch.nn as nn
    from torch.utils.data import TensorDataset, DataLoader
    _TORCH_AVAILABLE = True
except Exception:
    _TORCH_AVAILABLE = False
    torch = None
    nn = None
    TensorDataset = None
    DataLoader = None


class _TorchSklearnLikeWrapper:
    def __init__(self, model, scaler, device):
        self._model = model
        self._scaler = scaler
        self._device = device
        self.n_iter_ = 0

    def predict(self, X):
        import numpy as _np
        Xs = _np.asarray(X, dtype=_np.float32)
        Xs = self._scaler.transform(Xs)
        with torch.no_grad():
            t = torch.tensor(Xs, dtype=torch.float32).to(self._device)
            out = self._model(t).cpu().numpy()
        return out

    def __getattr__(self, item):
        return getattr(self._model, item)


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
    print("\n[TRAIN] Starting resilient MLP training with telemetry...")
    print(f"[TRAIN] Samples: {len(X)}, Max iters/epochs: {max_epochs}")
    print("[TRAIN] Progress will be printed every epoch - safe to tail -f this process\n")

    scaler = StandardScaler()
    # reduce memory by using float32
    X = X.astype('float32')
    X_scaled = scaler.fit_transform(X)

    use_torch = os.environ.get("PSX_FORCE_TORCH_GPU") == "1" and _TORCH_AVAILABLE and torch.cuda.is_available()

    start_epoch = 0
    best_loss = float("inf")
    loss_history = []

    ERROR_LOG = CHECKPOINT_DIR / "train_error.log"

    if use_torch:
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        print(f"[TRAIN] Using PyTorch on device: {device}")

        # build dataset + loader with streaming options
        X_t = torch.tensor(X_scaled, dtype=torch.float32)
        y_t = torch.tensor(y.astype('float32'))
        dataset = TensorDataset(X_t, y_t)
        loader = DataLoader(dataset, batch_size=256, shuffle=True, num_workers=4, pin_memory=True)

        model = nn.Sequential(
            nn.Linear(X_t.shape[1], 128),
            nn.ReLU(),
            nn.Linear(128, 64),
            nn.ReLU(),
            nn.Linear(64, 32),
            nn.ReLU(),
            nn.Linear(32, 1),
        ).to(device)

        optimizer = torch.optim.Adam(model.parameters(), lr=0.001)
        criterion = nn.MSELoss()

        # Resume from torch checkpoint if available
        if resume and LATEST_CHECKPOINT.exists():
            try:
                ck = torch.load(LATEST_CHECKPOINT, map_location=device)
                if isinstance(ck, dict) and "model_state" in ck:
                    model.load_state_dict(ck["model_state"])
                    optimizer.load_state_dict(ck.get("optimizer_state", {}))
                    scaler = ck.get("scaler", scaler)
                    start_epoch = ck.get("epoch", 0) + 1
                    loss_history = ck.get("loss_history", [])
                    print(f"[RESUME] Loaded PyTorch checkpoint, continuing from epoch {start_epoch}")
            except Exception as e:
                print(f"[RESUME] Torch checkpoint load failed ({e}), starting fresh")

        run_start = time.time()
        try:
            for epoch in range(start_epoch, max_epochs):
                t0 = time.time()
                epoch_losses = []

                for xb, yb in loader:
                    xb = xb.to(device, non_blocking=True)
                    yb = yb.to(device, non_blocking=True)

                    optimizer.zero_grad(set_to_none=True)
                    preds = model(xb).squeeze(-1)
                    loss = criterion(preds, yb)
                    loss.backward()
                    optimizer.step()

                    epoch_losses.append(loss.item())

                avg_loss = float(np.mean(epoch_losses))
                loss_history.append(avg_loss)
                dt = time.time() - t0

                print(f"[EPOCH {epoch+1:03d}/{max_epochs}] loss={avg_loss:.6f} | time={dt:.3f}s | device={device}")

                # checkpoint per epoch
                ckpt = {
                    "model_state": model.state_dict(),
                    "optimizer_state": optimizer.state_dict(),
                    "scaler": scaler,
                    "epoch": epoch,
                    "loss_history": loss_history,
                    "timestamp": datetime.now().isoformat(),
                }
                torch.save(ckpt, LATEST_CHECKPOINT)

                if avg_loss < best_loss:
                    best_loss = avg_loss

                # early stop
                if len(loss_history) > 5 and abs(loss_history[-1] - loss_history[-5]) < 1e-8:
                    print("[TRAIN] Early stopping - loss plateau reached")
                    break

                # check runtime; if exception after 3 hours should be logged (handled below)
            print(f"\n[TRAIN] PyTorch MLP training complete. Final loss: {loss_history[-1]:.6f}")
            print(f"[TRAIN] Checkpoint left at: {LATEST_CHECKPOINT}")

        except (MemoryError, RuntimeError, Exception) as e:
            elapsed = time.time() - run_start
            if elapsed >= 3 * 3600:
                import traceback
                tb = traceback.format_exc()
                ERROR_LOG.write_text(f"Timestamp: {datetime.now().isoformat()}\nError after {elapsed} seconds:\n{tb}\n")
                print(f"[ERROR] Critical error after 3+ hours logged to {ERROR_LOG}")
                # return best-effort state
                ckpt = {
                    "model_state": model.state_dict(),
                    "optimizer_state": optimizer.state_dict(),
                    "scaler": scaler,
                    "epoch": epoch,
                    "loss_history": loss_history,
                    "timestamp": datetime.now().isoformat(),
                }
                torch.save(ckpt, LATEST_CHECKPOINT)
                return _TorchSklearnLikeWrapper(model, scaler, device), scaler, loss_history
            else:
                raise

        return _TorchSklearnLikeWrapper(model, scaler, device), scaler, loss_history

    # fallback to sklearn MLP path (original behavior)
    model = MLPRegressor(
        hidden_layer_sizes=(128, 64, 32),
        activation="relu",
        solver="adam",
        alpha=0.0001,
        batch_size=256,
        learning_rate="adaptive",
        max_iter=1,
        warm_start=True,
        early_stopping=False,
        random_state=42
    )

    # RESUME from checkpoint if exists
    if resume and LATEST_CHECKPOINT.exists():
        try:
            ckpt = load(LATEST_CHECKPOINT)
            # sklearn checkpoint expected format
            if isinstance(ckpt, dict) and "model" in ckpt:
                model = ckpt["model"]
                scaler = ckpt["scaler"]
                start_epoch = ckpt.get("epoch", 0)
                loss_history = ckpt.get("loss_history", [])
                X_scaled = scaler.transform(X)  # re-apply same scaler
                print(f"[RESUME] Found checkpoint - continuing from epoch {start_epoch + 1}")
        except Exception as e:
            print(f"[RESUME] Checkpoint load failed ({e}), starting fresh")

    run_start = time.time()
    for epoch in range(start_epoch, max_epochs):
        t0 = time.time()
        try:
            model.partial_fit(X_scaled, y)
        except MemoryError as e:
            elapsed = time.time() - run_start
            if elapsed >= 3 * 3600:
                import traceback
                tb = traceback.format_exc()
                ERROR_LOG.write_text(f"Timestamp: {datetime.now().isoformat()}\nMemoryError after {elapsed} seconds:\n{tb}\n")
                print(f"[ERROR] MemoryError after 3+ hours logged to {ERROR_LOG}")
                break
            else:
                raise

        preds = model.predict(X_scaled)
        current_loss = mean_squared_error(y, preds)
        loss_history.append(current_loss)

        dt = time.time() - t0
        print(f"[EPOCH {epoch+1:03d}/{max_epochs}] loss={current_loss:.6f} | time={dt:.3f}s | "
              f"lr={getattr(model, 'learning_rate_', 'n/a')} | n_iter={getattr(model, 'n_iter_', 'n/a')}")

        # checkpoint per epoch
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

        if len(loss_history) > 5 and abs(loss_history[-1] - loss_history[-5]) < 1e-8:
            print("[TRAIN] Early stopping - loss plateau reached")
            break

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
