#!/usr/bin/env python3
"""
Launcher for Module 3: Uploaded-file-triggered heavy training.
Should be invoked by UI when a file is uploaded, but can also be run manually with a path.
Runs a calibration then scales epochs to hit ~4-5 hours.
"""
import time
from datetime import datetime
from pathlib import Path
import sys
import traceback

from models import multi_module_trainer as mmt

LOG = Path(__file__).resolve().parent / 'logs' / 'launch_uploaded.log'
LOG.parent.mkdir(parents=True, exist_ok=True)

TARGET_SECONDS = 4.5 * 3600

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: run_uploaded.py <path_to_csv>")
        sys.exit(1)
    path = sys.argv[1]

try:
    calib_rows = 2000
    print(f"[LAUNCH-UPLOADED] Calibration run (1 epoch) on uploaded file {path}...")
    t0 = time.time()
    mmt.train_module_uploaded(path, epochs=1)
    calib_time = time.time() - t0
    print(f"[LAUNCH-UPLOADED] Calibration epoch time: {calib_time:.2f}s")

    # choose rows scaling based on file size
    rows = 50000
    est_epoch_time = max(1.0, calib_time * (rows / max(100, calib_rows)))
    epochs_needed = max(5, int(TARGET_SECONDS / est_epoch_time))
    epochs_needed = min(epochs_needed, 2000)

    print(f"[LAUNCH-UPLOADED] Estimated epoch time at {rows} rows: {est_epoch_time:.2f}s")
    print(f"[LAUNCH-UPLOADED] Will run {epochs_needed} epochs (~{(est_epoch_time*epochs_needed)/3600:.2f} hrs)")

    tstart = time.time()
    success = mmt.train_module_uploaded(path, epochs=epochs_needed)
    elapsed = time.time() - tstart
    print(f"[LAUNCH-UPLOADED] Finished: success={success} elapsed={(elapsed/3600):.2f} hrs")

except Exception:
    tb = traceback.format_exc()
    LOG.write_text(f"Timestamp: {datetime.now().isoformat()}\nError:\n{tb}\n")
    print(f"[LAUNCH-UPLOADED] Fatal error; logged to {LOG}")
    sys.exit(1)
