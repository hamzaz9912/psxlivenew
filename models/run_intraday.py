#!/usr/bin/env python3
"""
Launcher for Module 4: Intraday training heavy-run for 4-5 hours.
"""
import time
from datetime import datetime
from pathlib import Path
import sys
import traceback

from models import multi_module_trainer as mmt

LOG = Path(__file__).resolve().parent / 'logs' / 'launch_intraday.log'
LOG.parent.mkdir(parents=True, exist_ok=True)

TARGET_SECONDS = 4.5 * 3600

try:
    calib_rows = 5000
    print(f"[LAUNCH-INTRADAY] Calibration run (1 epoch) with {calib_rows} rows...")
    t0 = time.time()
    mmt.train_module_intraday(epochs=1, rows=calib_rows)
    calib_time = time.time() - t0
    print(f"[LAUNCH-INTRADAY] Calibration epoch time: {calib_time:.2f}s")

    rows = 120000
    est_epoch_time = max(1.0, calib_time * (rows / max(1000, calib_rows)))
    epochs_needed = max(10, int(TARGET_SECONDS / est_epoch_time))
    epochs_needed = min(epochs_needed, 3000)

    print(f"[LAUNCH-INTRADAY] Estimated epoch time at {rows} rows: {est_epoch_time:.2f}s")
    print(f"[LAUNCH-INTRADAY] Will run {epochs_needed} epochs (~{(est_epoch_time*epochs_needed)/3600:.2f} hrs)")

    tstart = time.time()
    success = mmt.train_module_intraday(epochs=epochs_needed, rows=rows)
    elapsed = time.time() - tstart
    print(f"[LAUNCH-INTRADAY] Finished: success={success} elapsed={(elapsed/3600):.2f} hrs")

except Exception:
    tb = traceback.format_exc()
    LOG.write_text(f"Timestamp: {datetime.now().isoformat()}\nError:\n{tb}\n")
    print(f"[LAUNCH-INTRADAY] Fatal error; logged to {LOG}")
    sys.exit(1)
