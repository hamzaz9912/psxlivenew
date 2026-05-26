#!/usr/bin/env python3
"""
PyTorch GPU-accelerated MLP trainer for PSX brand models.
- Uses CUDA if available, else falls back to CPU.
- Same feature engineering as models/train.py
- Full telemetry: prints [EPOCH xxx] loss + time every epoch (perfect for tail -f)
- Per-epoch checkpoint + resume support (crash-safe for long 4-5h runs)
- Designed for per-brand separate training (see train_all_kse100_gpu.py)

Usage (inside the all-brands script or standalone):
    from models.train_pytorch import train_mlp_pytorch
    model, scaler, loss_hist = train_mlp_pytorch(X, y, max_epochs=40, device='cuda')
"""

import time
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler
from joblib import dump, load

import torch
import torch.nn as nn
from torch.utils.data import TensorDataset, DataLoader

# Reuse proven data prep from the existing CPU trainer
from models.train import (
    generate_synthetic_historical,
    prepare_features,
)

# ─────────────────────────────────────────────────────────────────────────────
#  MODEL DEFINITION (matches previous sklearn 128-64-32 architecture)
# ─────────────────────────────────────────────────────────────────────────────
class BrandMLP(nn.Module):
    def __init__(self, input_dim: int):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(input_dim, 128),
            nn.ReLU(),
            nn.Linear(128, 64),
            nn.ReLU(),
            nn.Linear(64, 32),
            nn.ReLU(),
            nn.Linear(32, 1),
        )

    def forward(self, x):
        return self.net(x).squeeze(-1)


# ─────────────────────────────────────────────────────────────────────────────
#  MAIN GPU/CPU TRAINING FUNCTION WITH TELEMETRY
# ─────────────────────────────────────────────────────────────────────────────
def train_mlp_pytorch(
    X: np.ndarray,
    y: np.ndarray,
    max_epochs: int = 40,
    batch_size: int = 512,
    lr: float = 0.001,
    device: str = "auto",
    checkpoint_path: Path | None = None,
    resume: bool = True,
) -> tuple[BrandMLP, StandardScaler, list[float]]:
    """
    Train a PyTorch MLP on GPU (or CPU fallback) with live epoch telemetry.

    Returns:
        model (BrandMLP on target device), scaler, loss_history
    """
    if device == "auto":
        device = "cuda" if torch.cuda.is_available() else "cpu"

    device = torch.device(device)
    print(f"\n[PYTORCH] Using device: {device}  (CUDA available: {torch.cuda.is_available()})")

    # Scale features (same as before)
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    X_t = torch.tensor(X_scaled, dtype=torch.float32)
    y_t = torch.tensor(y, dtype=torch.float32)

    dataset = TensorDataset(X_t, y_t)
    loader = DataLoader(dataset, batch_size=batch_size, shuffle=True, pin_memory=(device.type == "cuda"))

    model = BrandMLP(input_dim=X.shape[1]).to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=lr)
    criterion = nn.MSELoss()

    start_epoch = 0
    loss_history: list[float] = []
    best_loss = float("inf")

    # Resume from checkpoint if exists
    if resume and checkpoint_path and checkpoint_path.exists():
        try:
            ckpt = torch.load(checkpoint_path, map_location=device)
            model.load_state_dict(ckpt["model_state"])
            optimizer.load_state_dict(ckpt["optimizer_state"])
            scaler = ckpt["scaler"]
            start_epoch = ckpt.get("epoch", 0) + 1
            loss_history = ckpt.get("loss_history", [])
            X_t = torch.tensor(scaler.transform(X), dtype=torch.float32).to(device)  # re-scale if needed
            print(f"[RESUME] Continuing PyTorch training from epoch {start_epoch}")
        except Exception as e:
            print(f"[RESUME] Checkpoint load failed ({e}), starting fresh")

    print(f"[PYTORCH] Training for up to {max_epochs} epochs | batch_size={batch_size}")
    print("[PYTORCH] Live loss will be printed every epoch — safe to tail -f\n")

    model.train()
    for epoch in range(start_epoch, max_epochs):
        t0 = time.time()
        epoch_losses = []

        for xb, yb in loader:
            xb = xb.to(device, non_blocking=True)
            yb = yb.to(device, non_blocking=True)

            optimizer.zero_grad(set_to_none=True)
            pred = model(xb)
            loss = criterion(pred, yb)
            loss.backward()
            optimizer.step()

            epoch_losses.append(loss.item())

        avg_loss = float(np.mean(epoch_losses))
        loss_history.append(avg_loss)

        dt = time.time() - t0

        # TELEMETRY - exactly what user wants to see in terminal
        print(f"[EPOCH {epoch+1:03d}/{max_epochs}] loss={avg_loss:.6f} | time={dt:.2f}s | device={device}")

        # Save checkpoint after every epoch (4-5 hour crash protection)
        if checkpoint_path:
            ckpt = {
                "model_state": model.state_dict(),
                "optimizer_state": optimizer.state_dict(),
                "scaler": scaler,
                "epoch": epoch,
                "loss_history": loss_history,
                "timestamp": datetime.now().isoformat(),
            }
            torch.save(ckpt, checkpoint_path)

        if avg_loss < best_loss:
            best_loss = avg_loss

        # Simple early stop
        if len(loss_history) > 8 and abs(loss_history[-1] - loss_history[-5]) < 1e-8:
            print("[PYTORCH] Early stopping - loss plateau")
            break

    print(f"\n[PYTORCH] Training complete. Final loss: {loss_history[-1]:.6f}")
    if checkpoint_path:
        print(f"[PYTORCH] Checkpoint saved at: {checkpoint_path}")

    return model, scaler, loss_history


def save_pytorch_brand_model(model: BrandMLP, scaler: StandardScaler, brand_dir: Path, symbol: str):
    """Save PyTorch model + scaler for one brand."""
    brand_dir.mkdir(parents=True, exist_ok=True)

    # Save weights
    torch.save(model.state_dict(), brand_dir / f"{symbol}_mlp.pt")

    # Save scaler
    dump(scaler, brand_dir / f"{symbol}_mlp_scaler.pkl")

    # Small metadata for the neural net
    meta = {
        "framework": "pytorch",
        "input_dim": model.net[0].in_features,
        "architecture": "128-64-32-1",
        "saved_at": datetime.now().isoformat(),
    }
    (brand_dir / "pytorch_meta.json").write_text(__import__("json").dumps(meta, indent=2))

    print(f"[{symbol}] Saved PyTorch model → {brand_dir / f'{symbol}_mlp.pt'}")


if __name__ == "__main__":
    # Quick self-test
    print("=== PyTorch GPU Trainer Self-Test ===")
    df = generate_synthetic_historical(n_rows=8000, seed=42)
    clean, feat_cols, _ = prepare_features(df)
    X = clean[feat_cols].values
    y = clean["Target"].values

    model, scaler, hist = train_mlp_pytorch(
        X, y,
        max_epochs=5,
        batch_size=256,
        device="auto",
        checkpoint_path=Path("models/brands/_test_checkpoint.pt"),
        resume=False,
    )
    print("Self-test passed. Final loss:", hist[-1])
