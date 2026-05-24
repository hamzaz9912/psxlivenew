#!/usr/bin/env python3
"""
Model Loader - production inference helper for the .pkl artifacts
created by models/train.py

Usage (from anywhere):
    from models.model_loader import load_latest_models
    models = load_latest_models()
    xgb_model = models["xgb"]
    mlp_model, scaler = models["mlp"], models["mlp_scaler"]
    pred = xgb_model.predict(features)
"""

from pathlib import Path
from joblib import load
import json

HERE = Path(__file__).resolve().parent

def get_model_paths():
    return {
        "xgb": HERE / "kse100_xgb.pkl",
        "mlp": HERE / "kse100_mlp.pkl",
        "mlp_scaler": HERE / "kse100_mlp_scaler.pkl",
        "meta": HERE / "meta.json",
        "checkpoint": HERE / "checkpoints" / "latest_mlp_checkpoint.pkl",
    }

def load_latest_models():
    """Load all trained .pkl models + scaler + metadata. Returns dict or None on failure."""
    paths = get_model_paths()
    try:
        result = {
            "xgb": load(paths["xgb"]),
            "mlp": load(paths["mlp"]),
            "mlp_scaler": load(paths["mlp_scaler"]),
            "meta": json.loads(paths["meta"].read_text()),
            "paths": {k: str(v) for k, v in paths.items()},
        }
        print(f"[LOADER] Successfully loaded models trained at {result['meta'].get('trained_at')}")
        return result
    except Exception as e:
        print(f"[LOADER] Could not load models: {e}")
        return None

if __name__ == "__main__":
    mods = load_latest_models()
    if mods:
        print("XGB type :", type(mods["xgb"]))
        print("MLP type :", type(mods["mlp"]))
        print("Features :", mods["meta"]["features"])
