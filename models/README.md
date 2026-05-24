# PSX Model Training Folder

This directory contains the **complete, self-contained offline training pipeline** and the resulting persistent `.pkl` model files.

## Purpose
- Train on large historical data (synthetic or real CSV) outside the Streamlit app
- Survive 4-5 hour runs with automatic epoch checkpointing + resume
- Telemetry logging suitable for `tail -f models/train.log`
- Produce production-ready `.pkl` artifacts that can be loaded by inference code

## Files
- `train.py`           – Main training script (run this)
- `model_loader.py`    – Helper to load the generated .pkl models in any Python code
- `__init__.py`        – Package entrypoint
- `kse100_xgb.pkl`     – Trained XGBoost model (after running train)
- `kse100_mlp.pkl`     – Trained MLP neural net
- `kse100_mlp_scaler.pkl` – Fitted StandardScaler for the MLP
- `meta.json`          – Training metadata + feature list
- `checkpoints/latest_mlp_checkpoint.pkl` – Latest resilience checkpoint (safe to delete after full success)

## How to Run (complete training + .pkl generation)
```bash
# From project root
python -m models.train --epochs 30 --symbol "KSE-100"

# With your own historical CSV (must contain Close + Date columns)
python -m models.train --data sample_xausd_data.csv --epochs 50 --force

# Watch live telemetry in another terminal
tail -f models/train.log   # (redirect output when running)
```

## Resilience Features Implemented
- Checkpoint written **after every single training iteration**
- On restart: automatically resumes from last saved state
- Handles keyboard interrupt / OOM / system crash gracefully
- Telemetry: `[EPOCH 012/050] loss=0.000123 | time=0.045s`

## Integration (later, without touching current UI)
In any new or future code:
```python
from models.model_loader import load_latest_models
bundle = load_latest_models()
# use bundle["xgb"], bundle["mlp"] etc.
```

## Notes
- All training logic is **pure backend** – zero Streamlit / UI imports
- Feature engineering matches the math used in final.py / app.py
- No new heavy dependencies (uses existing sklearn + xgboost + joblib)
- GPU acceleration: current sklearn MLP is CPU-only. For true CUDA + DataLoader + pin_memory
  a future PyTorch version can be added here without changing any upstream signatures.

Generated models are safe to commit (small) or store in Git LFS / S3.

## All KSE-100 Brands Training
Use `python -m models.train_all_kse100 --all` (or --symbols "LUCK,OGDC,...") to generate individual .pkl models for every company in the full KSE-100 list (~120 tickers).

Each brand gets its own folder under `models/brands/<TICKER>/` containing:
- *_xgb.pkl, *_mlp.pkl, *_scaler.pkl, meta.json, per-brand checkpoint

A `brand_registry.json` is automatically maintained for easy discovery by future loaders.
Current example brands already trained: ENGRO, HBL, LUCK, MCB, OGDC, PPL (see brands/ for more).

