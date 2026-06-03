#!/usr/bin/env python3
"""
Multi-module isolated trainers for PSX models.
- Provides 4 independent pipelines (40-brands, 100-brands, uploaded file, intraday)
- Each pipeline uses its own checkpoint and final model path
- Each pipeline runs independently (can be invoked separately or via run_all_modules)
- Uses PyTorch (if available) for GPU-optimized training with non_blocking transfers
- Does NOT modify any UI or external endpoints; only implements backend training logic

Usage examples:
    from models.multi_module_trainer import train_module_40, train_module_100, train_module_uploaded, train_module_intraday, run_all_modules
    train_module_40(epochs=40)
    run_all_modules()

Notes:
    - Checkpoints: models/checkpoints/latest_checkpoint_<module>.pt
    - Final models: models/module_models/<module>/model.pt (+ scaler + meta.json)
"""

from pathlib import Path
import time
import traceback
import json
from datetime import datetime
from multiprocessing import Process

import numpy as np
from joblib import dump

# Import existing data helpers (unchanged signatures)
from models.train import generate_synthetic_historical, prepare_features

# Try to import torch; fall back gracefully
try:
    import torch
    import torch.nn as nn
    from torch.utils.data import TensorDataset, DataLoader
    _TORCH = True
except Exception:
    torch = None
    nn = None
    TensorDataset = None
    DataLoader = None
    _TORCH = False

ROOT = Path(__file__).resolve().parent
CHECKPOINT_DIR = ROOT / "checkpoints"
CHECKPOINT_DIR.mkdir(exist_ok=True, parents=True)
MODULE_MODELS_DIR = ROOT / "module_models"
MODULE_MODELS_DIR.mkdir(exist_ok=True, parents=True)
LOG_DIR = ROOT / "logs"
LOG_DIR.mkdir(exist_ok=True, parents=True)

# Authoritative KSE list reused (subset for 40-brands module)
KSE100_TICKERS = [
    "HBL","UBL","MCB","NBP","ABL","BAFL","MEBL","JSBL","FABL","BAHL",
    "AKBL","SNBL","BOP","SCBPL","SILK","KASB","OGDC","PPL","POL","MARI",
    "PSO","APL","SNGP","SSGC","OGRA","HASCOL","BYCO","SHEL","TOTAL","GASF",
    "APMJ","LUCK","DGKC","MLCF","PIOC","KOHC","ACPL","CHCC","BWCL","FCCL",
    "THCCL","DSKC","GWLC","JVDC","FFC","EFERT","FFBL","FATIMA","DAWH","AGL",
    "EPCL","ENGRO","HUBC","KEL","KAPCO","LOTTE","ARL","NRL","PACE","POWER",
    "TPEL","NCPL","GTYR","WPIL","SYS","TRG","NETSOL","AVN","IBFL","CMPL",
    "PTCL","INDU","ATLH","PSMC","AGTL","MTL","HINOON","GHGL","ATRL","NESTLE",
    "UNILEVER","NATF","COLG","UNITY","ALNOOR","WAVES","SHIELD","BIFO","ILP","NML",
    "GATM","CTM","KTML","SPLC","ASTL","DSFL","LOTCHEM","YOUW","GSK","SEARL",
    "GLAXO","ORIX","AGP","ICI","BERGER","SITARA","LEINER","LOADS","RCML","EFOODS",
]
KSE100_TICKERS = list(dict.fromkeys(KSE100_TICKERS))


def _device():
    if _TORCH and torch.cuda.is_available():
        return torch.device('cuda')
    return torch.device('cpu') if _TORCH else None


def _save_checkpoint(module_name: str, ckpt: dict):
    path = CHECKPOINT_DIR / f"latest_checkpoint_{module_name}.pt"
    try:
        if _TORCH and isinstance(ckpt.get('model_state'), dict):
            torch.save(ckpt, path)
        else:
            # fallback to joblib for non-torch content
            dump(ckpt, path.with_suffix('.pkl'))
    except Exception:
        # last-resort: write json metadata
        try:
            meta_path = path.with_suffix('.json')
            meta = {k: str(v) for k, v in ckpt.items() if k != 'model_state' and k != 'optimizer_state'}
            meta['saved_at'] = datetime.now().isoformat()
            meta_path.write_text(json.dumps(meta, indent=2))
        except Exception:
            pass


def _load_checkpoint(module_name: str):
    path = CHECKPOINT_DIR / f"latest_checkpoint_{module_name}.pt"
    if path.exists() and _TORCH:
        try:
            return torch.load(path, map_location=_device())
        except Exception:
            return None
    # try pkl
    pkl = path.with_suffix('.pkl')
    if pkl.exists():
        try:
            import joblib
            return joblib.load(pkl)
        except Exception:
            return None
    return None


class _SimpleMLP(nn.Module):
    def __init__(self, input_dim: int):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(input_dim, 256),
            nn.ReLU(),
            nn.Linear(256, 128),
            nn.ReLU(),
            nn.Linear(128, 64),
            nn.ReLU(),
            nn.Linear(64, 1),
        )

    def forward(self, x):
        return self.net(x).squeeze(-1)


def _train_generic(module_name: str, X: np.ndarray, y: np.ndarray, epochs: int = 40, batch_size: int = 512, num_workers: int = 4, pin_memory: bool = True):
    """Generic isolated PyTorch training loop with per-epoch checkpointing and robust error logging."""
    start_time = time.time()
    device = _device()
    use_torch = _TORCH and device is not None
    module_dir = MODULE_MODELS_DIR / module_name
    module_dir.mkdir(parents=True, exist_ok=True)

    error_log = LOG_DIR / f"{module_name}_error.log"

    # prepare data
    X = X.astype('float32')
    y = y.astype('float32')

    if use_torch:
        tensor_X = torch.tensor(X)
        tensor_y = torch.tensor(y)
        dataset = TensorDataset(tensor_X, tensor_y)
        loader = DataLoader(dataset, batch_size=batch_size, shuffle=True, num_workers=num_workers, pin_memory=pin_memory)

        model = _SimpleMLP(X.shape[1]).to(device)
        optimizer = torch.optim.Adam(model.parameters(), lr=0.0008)
        criterion = nn.MSELoss()

        # resume
        ck = _load_checkpoint(module_name)
        start_epoch = 0
        loss_history = []
        if ck and isinstance(ck, dict) and 'model_state' in ck:
            try:
                model.load_state_dict(ck['model_state'])
                optimizer.load_state_dict(ck.get('optimizer_state', {}))
                start_epoch = ck.get('epoch', 0) + 1
                loss_history = ck.get('loss_history', [])
                print(f"[{module_name}] Resuming from checkpoint epoch {start_epoch}")
            except Exception:
                start_epoch = 0

        try:
            for epoch in range(start_epoch, epochs):
                t0 = time.time()
                model.train()
                batch_losses = []
                for xb, yb in loader:
                    xb = xb.to(device, non_blocking=True)
                    yb = yb.to(device, non_blocking=True)

                    optimizer.zero_grad(set_to_none=True)
                    pred = model(xb)
                    loss = criterion(pred, yb)
                    loss.backward()
                    optimizer.step()

                    batch_losses.append(loss.item())

                avg_loss = float(np.mean(batch_losses)) if batch_losses else 0.0
                loss_history.append(avg_loss)
                dt = time.time() - t0
                print(f"[{module_name}] [EPOCH {epoch+1:03d}/{epochs}] loss={avg_loss:.6f} | time={dt:.2f}s | device={device}")

                # checkpoint
                ckpt = {
                    'model_state': model.state_dict(),
                    'optimizer_state': optimizer.state_dict(),
                    'scaler': None,
                    'epoch': epoch,
                    'loss_history': loss_history,
                    'timestamp': datetime.now().isoformat()
                }
                _save_checkpoint(module_name, ckpt)

                # runtime error protection: if exception after 3 hours, log
                if time.time() - start_time >= 3 * 3600:
                    # no-op here; exceptions will be logged below if thrown
                    pass

            # final save
            torch.save(model.state_dict(), module_dir / 'model.pt')
            dump({'dummy': 'scaler_not_used'}, module_dir / 'scaler.pkl')
            meta = {
                'module': module_name,
                'trained_at': datetime.now().isoformat(),
                'epochs': epochs,
                'final_loss': loss_history[-1] if loss_history else None,
                'device': str(device),
            }
            (module_dir / 'meta.json').write_text(json.dumps(meta, indent=2))
            print(f"[{module_name}] Training complete. Model saved to {module_dir / 'model.pt'}")
            return True

        except Exception as e:
            tb = traceback.format_exc()
            elapsed = time.time() - start_time
            err_msg = f"Timestamp: {datetime.now().isoformat()}\nElapsed: {elapsed}s\nError:\n{tb}\n"
            error_log.write_text(err_msg)
            print(f"[{module_name}] ERROR occurred; logged to {error_log}")
            # attempt to save best-effort checkpoint
            try:
                ckpt = {
                    'model_state': model.state_dict(),
                    'optimizer_state': optimizer.state_dict(),
                    'scaler': None,
                    'epoch': epoch,
                    'loss_history': loss_history,
                    'timestamp': datetime.now().isoformat()
                }
                _save_checkpoint(module_name, ckpt)
            except Exception:
                pass
            return False

    else:
        # Fallback: lightweight sklearn-like incremental train (existing code path preserved)
        # Use original MLPRegressor partial_fit loop but isolated per module
        from sklearn.neural_network import MLPRegressor
        from sklearn.preprocessing import StandardScaler
        from sklearn.metrics import mean_squared_error

        scaler = StandardScaler()
        Xs = scaler.fit_transform(X)
        model = MLPRegressor(hidden_layer_sizes=(256,128,64), max_iter=1, warm_start=True, random_state=42)

        start_epoch = 0
        loss_history = []
        ck = _load_checkpoint(module_name)
        if ck and isinstance(ck, dict) and 'model' in ck:
            try:
                model = ck['model']
                scaler = ck['scaler']
                start_epoch = ck.get('epoch', 0)
                loss_history = ck.get('loss_history', [])
                Xs = scaler.transform(X)
                print(f"[{module_name}] Resuming sklearn checkpoint epoch {start_epoch}")
            except Exception:
                start_epoch = 0

        try:
            for epoch in range(start_epoch, epochs):
                t0 = time.time()
                model.partial_fit(Xs, y)
                preds = model.predict(Xs)
                cur_loss = float(mean_squared_error(y, preds))
                loss_history.append(cur_loss)
                dt = time.time() - t0
                print(f"[{module_name}] [EPOCH {epoch+1:03d}/{epochs}] loss={cur_loss:.6f} | time={dt:.2f}s")

                ckpt = {
                    'model': model,
                    'scaler': scaler,
                    'epoch': epoch,
                    'loss_history': loss_history,
                    'timestamp': datetime.now().isoformat()
                }
                _save_checkpoint(module_name, ckpt)

            # save final
            dump(model, module_dir / 'model.pkl')
            dump(scaler, module_dir / 'scaler.pkl')
            meta = {'module': module_name, 'trained_at': datetime.now().isoformat(), 'epochs': epochs, 'final_loss': loss_history[-1] if loss_history else None}
            (module_dir / 'meta.json').write_text(json.dumps(meta, indent=2))
            print(f"[{module_name}] Sklearn training complete. Saved to {module_dir}")
            return True

        except Exception:
            tb = traceback.format_exc()
            elapsed = time.time() - start_time
            err_msg = f"Timestamp: {datetime.now().isoformat()}\nElapsed: {elapsed}s\nError:\n{tb}\n"
            error_log.write_text(err_msg)
            print(f"[{module_name}] ERROR occurred; logged to {error_log}")
            return False


# ---------------------- Module entry points ----------------------

def train_module_40(epochs: int = 40, rows_per_brand: int = 20000):
    """Train dedicated 40-brand pipeline.
    Saves to models/module_models/module_40_brands/
    """
    module_name = 'module_40_brands'
    # pick first 40 tickers
    tickers = KSE100_TICKERS[:40]

    # aggregate synthetic history across tickers into one dataset for this module
    all_X = []
    all_y = []
    for t in tickers:
        seed = abs(hash(t)) % 100000
        df = generate_synthetic_historical(n_rows=rows_per_brand, seed=seed)
        clean, feat_cols, _ = prepare_features(df)
        all_X.append(clean[feat_cols].values)
        all_y.append(clean['Target'].values)

    X = np.vstack(all_X)
    y = np.concatenate(all_y)

    return _train_generic(module_name, X, y, epochs=epochs, batch_size=512)


def train_module_100(epochs: int = 40, rows_per_brand: int = 25000):
    """Train dedicated 100-brand pipeline.
    Saves to models/module_models/module_100_brands/
    """
    module_name = 'module_100_brands'
    tickers = KSE100_TICKERS[:100]
    all_X = []
    all_y = []
    for t in tickers:
        seed = abs(hash(t)) % 100000
        df = generate_synthetic_historical(n_rows=rows_per_brand, seed=seed)
        clean, feat_cols, _ = prepare_features(df)
        all_X.append(clean[feat_cols].values)
        all_y.append(clean['Target'].values)

    X = np.vstack(all_X)
    y = np.concatenate(all_y)

    return _train_generic(module_name, X, y, epochs=epochs, batch_size=1024)


def train_module_uploaded(uploaded_csv_path: str, epochs: int = 30):
    """Triggered when UI uploads a CSV. Trains on that dataset only and saves to module_uploaded_data.
    Does not override production models.
    """
    module_name = 'module_uploaded_data'
    p = Path(uploaded_csv_path)
    if not p.exists():
        raise FileNotFoundError(uploaded_csv_path)

    import pandas as pd
    df = pd.read_csv(p)
    clean, feat_cols, _ = prepare_features(df)
    X = clean[feat_cols].values
    y = clean['Target'].values

    return _train_generic(module_name, X, y, epochs=epochs, batch_size=256)


def train_module_intraday(epochs: int = 80, rows: int = 100000):
    """High-frequency intraday training loop optimized for short-term forecasting.
    Saves to module_intraday.
    """
    module_name = 'module_intraday'
    df = generate_synthetic_historical(n_rows=rows, seed=12345)
    clean, feat_cols, _ = prepare_features(df)
    X = clean[feat_cols].values
    y = clean['Target'].values

    # smaller batch size for high-frequency patterns
    return _train_generic(module_name, X, y, epochs=epochs, batch_size=1024)


def _run_wrapper(func, *args, **kwargs):
    """Run module in try/except to ensure isolation and logging."""
    module = kwargs.get('module_name') or func.__name__
    try:
        print(f"[ORCH] Starting {module} at {datetime.now().isoformat()}")
        result = func(*args)
        print(f"[ORCH] Finished {module} with result: {result}")
    except Exception:
        tb = traceback.format_exc()
        errfile = LOG_DIR / f"{module}_fatal.log"
        errfile.write_text(f"Timestamp: {datetime.now().isoformat()}\nError:\n{tb}\n")
        print(f"[ORCH] {module} failed; logged to {errfile}")


def run_all_modules():
    """Start all four modules in separate processes to guarantee isolation.
    Processes run concurrently and do not affect each other on failure.
    """
    procs = []
    mapping = [
        (train_module_40, (), {}),
        (train_module_100, (), {}),
        (train_module_intraday, (), {}),
        # Note: uploaded module should be triggered by UI; provide example placeholder
        # (train_module_uploaded, ('/path/to/uploaded.csv',), {}),
    ]

    for func, args, kwargs in mapping:
        p = Process(target=_run_wrapper, args=(func,)+args, kwargs=kwargs)
        p.start()
        procs.append(p)

    # wait for completion
    for p in procs:
        p.join()


if __name__ == '__main__':
    # quick local runner for convenience
    run_all_modules()
