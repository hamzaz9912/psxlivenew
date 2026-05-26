#!/usr/bin/env python3
"""
KSE-100 ALL BRANDS - GPU (PyTorch) Training Pipeline
Trains separate XGB + PyTorch MLP models for every brand on GPU (CUDA if available).

Features:
- Per-brand isolated folders: models/brands/<TICKER>/
  - <TICKER>_xgb.pkl
  - <TICKER>_mlp.pt          ← PyTorch weights
  - <TICKER>_mlp_scaler.pkl
  - meta.json + pytorch_meta.json
- Live terminal telemetry: [EPOCH 012/040] loss=... for every brand
- Epoch checkpoints per brand (safe to interrupt 4-5 hour runs)
- Resume support per brand
- Same KSE-100 ticker list as the CPU version

Target runtime: 4-5 hours for full KSE-100 on a typical consumer GPU
(with ~30-40 epochs and larger synthetic data per brand).

Commands:

    # Train specific brands (recommended to start)
    python -m models.train_all_kse100_gpu --symbols "LUCK,OGDC,ENGRO,HBL,MCB,PPL" --epochs 35

    # Full KSE-100 run (will take ~4-5 hours on GPU)
    python -m models.train_all_kse100_gpu --all --epochs 40

    # Quick test (first 6 brands only)
    python -m models.train_all_kse100_gpu --all --limit 6 --epochs 15

    # Watch live training in another terminal
    Get-Content models/brands/train_gpu.log -Wait -Tail 50     # PowerShell
    tail -f models/brands/train_gpu.log                        # Git Bash / WSL

After training, models are ready for inference (see model_loader or custom code).
"""

import argparse
import json
import time
from pathlib import Path
from datetime import datetime

import numpy as np
import torch
from joblib import dump

# Reuse data prep + XGB trainer (CPU, fast)
from models.train import (
    generate_synthetic_historical,
    prepare_features,
    train_xgb,
)

# New GPU trainer
from models.train_pytorch import (
    train_mlp_pytorch,
    save_pytorch_brand_model,
)

# ─────────────────────────────────────────────────────────────────────────────
# SAME AUTHORITATIVE KSE-100 LIST (from train_all_kse100.py)
# ─────────────────────────────────────────────────────────────────────────────
KSE100_TICKERS = [
    # Banking (16)
    "HBL", "UBL", "MCB", "NBP", "ABL", "BAFL", "MEBL", "JSBL", "FABL", "BAHL",
    "AKBL", "SNBL", "BOP", "SCBPL", "SILK", "KASB",
    # Oil & Gas (15)
    "OGDC", "PPL", "POL", "MARI", "PSO", "APL", "SNGP", "SSGC", "OGRA", "HASCOL",
    "BYCO", "SHEL", "TOTAL", "GASF", "APMJ",
    # Cement (13)
    "LUCK", "DGKC", "MLCF", "PIOC", "KOHC", "ACPL", "CHCC", "BWCL", "FCCL", "THCCL",
    "DSKC", "GWLC", "JVDC",
    # Fertilizer (8)
    "FFC", "EFERT", "FFBL", "FATIMA", "DAWH", "AGL", "EPCL", "ENGRO",
    # Power & Energy (12)
    "HUBC", "KEL", "KAPCO", "LOTTE", "ARL", "NRL", "PACE", "POWER", "TPEL", "NCPL",
    "GTYR", "WPIL",
    # Technology (7)
    "SYS", "TRG", "NETSOL", "AVN", "IBFL", "CMPL", "PTCL",
    # Automobile (8)
    "INDU", "ATLH", "PSMC", "AGTL", "MTL", "HINOON", "GHGL", "ATRL",
    # Food & Beverages (9)
    "NESTLE", "UNILEVER", "NATF", "COLG", "UNITY", "ALNOOR", "WAVES", "SHIELD", "BIFO",
    # Textiles (10)
    "ILP", "NML", "GATM", "CTM", "KTML", "SPLC", "ASTL", "DSFL", "LOTCHEM", "YOUW",
    # Pharmaceuticals (6)
    "GSK", "SEARL", "GLAXO", "ORIX", "AGP",
    # Chemicals (7)
    "ICI", "BERGER", "SITARA", "LEINER", "LOADS", "RCML", "EFOODS",
    # Paper & Board (3)
    "PKGS", "CPPL",
    # Sugar & Allied (4)
    "JDW", "SHFA",
    # Miscellaneous (6)
    "THAL", "PEL", "SIEM", "SAIF", "MACFL", "MARTIN",
]
KSE100_TICKERS = list(dict.fromkeys(KSE100_TICKERS))

BRANDS_ROOT = Path(__file__).parent / "brands"
BRANDS_ROOT.mkdir(parents=True, exist_ok=True)

LOG_FILE = BRANDS_ROOT / "train_gpu.log"
REGISTRY_FILE = BRANDS_ROOT / "brand_registry_gpu.json"


def get_brand_dir(symbol: str) -> Path:
    d = BRANDS_ROOT / symbol.upper()
    d.mkdir(parents=True, exist_ok=True)
    return d


def train_one_brand_gpu(symbol: str, epochs: int = 40, rows: int = 30000, force: bool = False) -> dict:
    """Train XGB + PyTorch MLP for one ticker on GPU and save artifacts."""
    symbol = symbol.upper().strip()
    brand_dir = get_brand_dir(symbol)
    ckpt_path = brand_dir / "checkpoint_mlp.pt"

    print(f"\n{'='*65}")
    print(f"[{symbol}] GPU TRAINING START  | epochs={epochs} | synthetic_rows={rows}")
    print(f"Output: {brand_dir}")

    # Per-brand synthetic data (different seed)
    seed = abs(hash(symbol)) % 100000
    df = generate_synthetic_historical(n_rows=rows, start_price=100.0 + (seed % 250), seed=seed)

    clean, feat_cols, _ = prepare_features(df)
    X = clean[feat_cols].values.astype(np.float32)
    y = clean["Target"].values.astype(np.float32)

    # 1. XGB (CPU - very fast)
    print(f"[{symbol}] Training XGBoost...")
    xgb_model = train_xgb(X, y)
    dump(xgb_model, brand_dir / f"{symbol}_xgb.pkl")

    # 2. PyTorch MLP on GPU (with live telemetry + per-epoch checkpoint)
    print(f"[{symbol}] Training PyTorch MLP on GPU...")
    mlp_model, mlp_scaler, loss_hist = train_mlp_pytorch(
        X, y,
        max_epochs=epochs,
        batch_size=512,
        lr=0.0008,
        device="auto",
        checkpoint_path=ckpt_path,
        resume=not force,
    )

    save_pytorch_brand_model(mlp_model, mlp_scaler, brand_dir, symbol)

    meta = {
        "symbol": symbol,
        "framework": "pytorch+gpu",
        "trained_at": datetime.now().isoformat(),
        "n_samples": len(clean),
        "features": feat_cols,
        "epochs": epochs,
        "synthetic_rows": rows,
        "final_loss": float(loss_hist[-1]) if loss_hist else None,
        "xgb_file": f"{symbol}_xgb.pkl",
        "mlp_file": f"{symbol}_mlp.pt",
        "mlp_scaler": f"{symbol}_mlp_scaler.pkl",
        "device_used": "cuda" if torch.cuda.is_available() else "cpu",
    }
    (brand_dir / "meta.json").write_text(json.dumps(meta, indent=2))

    print(f"[{symbol}] ✓ DONE — 3 model files + meta saved")
    return meta


def build_registry():
    """Scan brands/ and write brand_registry_gpu.json"""
    registry = {
        "generated_at": datetime.now().isoformat(),
        "total_brands": 0,
        "framework": "pytorch-gpu",
        "brands": {},
    }

    for brand_dir in sorted(BRANDS_ROOT.iterdir()):
        if not brand_dir.is_dir() or brand_dir.name.startswith("."):
            continue
        symbol = brand_dir.name
        meta_file = brand_dir / "meta.json"
        if meta_file.exists():
            try:
                meta = json.loads(meta_file.read_text())
                registry["brands"][symbol] = {
                    "path": str(brand_dir),
                    "xgb": str(brand_dir / f"{symbol}_xgb.pkl"),
                    "mlp_pt": str(brand_dir / f"{symbol}_mlp.pt"),
                    "scaler": str(brand_dir / f"{symbol}_mlp_scaler.pkl"),
                    "meta": str(meta_file),
                    "trained_at": meta.get("trained_at"),
                    "final_loss": meta.get("final_loss"),
                    "device": meta.get("device_used"),
                }
            except Exception:
                pass

    registry["total_brands"] = len(registry["brands"])
    REGISTRY_FILE.write_text(json.dumps(registry, indent=2))
    print(f"\n[REGISTRY] Updated {REGISTRY_FILE} with {registry['total_brands']} GPU-trained brands")
    return registry


def main(all_brands=False, symbols=None, limit=None, epochs=40, rows=30000, force=False):
    print("=" * 70)
    print("KSE-100 PER-BRAND GPU TRAINING (PyTorch + CUDA)")
    print("=" * 70)
    print(f"Total KSE-100 tickers: {len(KSE100_TICKERS)}")
    print(f"Epochs per brand   : {epochs}")
    print(f"Rows per brand     : {rows:,}")
    print(f"Expected full run  : ~4-5 hours on mid-range GPU (tune --epochs)")
    print(f"Output root        : {BRANDS_ROOT}")
    print("=" * 70)

    if symbols:
        to_train = [s.strip().upper() for s in symbols.split(",") if s.strip()]
    elif all_brands:
        to_train = KSE100_TICKERS.copy()
    else:
        to_train = ["LUCK", "OGDC", "ENGRO", "HBL", "MCB", "PPL", "FFC", "SYS"][:8]

    if limit:
        to_train = to_train[:int(limit)]

    print(f"\nWill train {len(to_train)} brand(s): {', '.join(to_train)}")
    print("Training progress will be printed live below.\n")

    start = time.time()
    results = []

    for idx, sym in enumerate(to_train, 1):
        print(f"\n[{idx}/{len(to_train)}] === {sym} ===")
        try:
            meta = train_one_brand_gpu(sym, epochs=epochs, rows=rows, force=force)
            results.append(meta)
        except Exception as e:
            print(f"[{sym}] ERROR: {e}")
            import traceback
            traceback.print_exc()

    reg = build_registry()

    elapsed = time.time() - start
    print("\n" + "=" * 70)
    print(f"[OK] GPU BRAND TRAINING FINISHED in {elapsed/60:.1f} minutes")
    print(f"   Successfully trained: {len(results)} / {len(to_train)}")
    print(f"   Registry: {REGISTRY_FILE}")
    print(f"   All per-brand models: {BRANDS_ROOT}/<SYMBOL>/")
    print("=" * 70)

    return reg


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train GPU models for ALL KSE-100 brands (PyTorch)")
    parser.add_argument("--all", action="store_true", help="Train every ticker in full KSE-100 list")
    parser.add_argument("--symbols", type=str, default=None, help="Comma-separated, e.g. LUCK,OGDC,ENGRO")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of brands (for testing)")
    parser.add_argument("--epochs", type=int, default=40, help="PyTorch epochs per brand (higher = longer training)")
    parser.add_argument("--rows", type=int, default=30000, help="Synthetic rows per brand (more rows = slower)")
    parser.add_argument("--force", action="store_true", help="Ignore checkpoints and retrain from scratch")
    args = parser.parse_args()

    main(
        all_brands=args.all,
        symbols=args.symbols,
        limit=args.limit,
        epochs=args.epochs,
        rows=args.rows,
        force=args.force,
    )
