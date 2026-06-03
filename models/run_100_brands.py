#!/usr/bin/env python3
"""
Launcher for Module 2: 100 Brands training with auto-scaling to 4-5 hours.
"""
import time
from datetime import datetime
from pathlib import Path
import sys
import traceback

from models import multi_module_trainer as mmt

LOG = Path(__file__).resolve().parent / 'logs' / 'launch_100_brands.log'
LOG.parent.mkdir(parents=True, exist_ok=True)

TARGET_SECONDS = 4.5 * 3600

try:
    calib_rows = 2000
    print(f"[LAUNCH-100] Calibration run (1 epoch) with {calib_rows} rows/brand...")
    t0 = time.time()
    mmt.train_module_100(epochs=1, rows_per_brand=calib_rows)
    calib_time = time.time() - t0
    print(f"[LAUNCH-100] Calibration epoch time: {calib_time:.2f}s")

    rows_per_brand = 60000
    est_epoch_time = max(1.0, calib_time * (rows_per_brand / calib_rows))
    epochs_needed = max(5, int(TARGET_SECONDS / est_epoch_time))
    epochs_needed = min(epochs_needed, 1500)

    print(f"[LAUNCH-100] Estimated epoch time at {rows_per_brand} rows: {est_epoch_time:.2f}s")
    print(f"[LAUNCH-100] Will run {epochs_needed} epochs (~{(est_epoch_time*epochs_needed)/3600:.2f} hrs)")

    tstart = time.time()
    success = mmt.train_module_100(epochs=epochs_needed, rows_per_brand=rows_per_brand)
    elapsed = time.time() - tstart
    print(f"[LAUNCH-100] Finished: success={success} elapsed={(elapsed/3600):.2f} hrs")

except Exception:
    tb = traceback.format_exc()
    LOG.write_text(f"Timestamp: {datetime.now().isoformat()}\nError:\n{tb}\n")
    print(f"[LAUNCH-100] Fatal error; logged to {LOG}")
    sys.exit(1)
