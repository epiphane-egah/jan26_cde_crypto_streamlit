import json
import subprocess
import sys
import time
from collections import Counter


def log(event, severity="INFO", **fields):
    print(json.dumps({"severity": severity, "event": event, **fields}), flush=True)


cmd = sys.argv[1:] or ["dbt", "build"]
start = time.time()

log("dbt_job_started", job="dbt", command=" ".join(cmd))
result = subprocess.run(cmd)
duration = round(time.time() - start, 2)

# --- Résumé depuis run_results.json ---
try:
    with open("target/run_results.json") as f:
        counts = Counter(r["status"] for r in json.load(f)["results"])
    log("dbt_run_summary", job="dbt",
        success=counts.get("success", 0),
        error=counts.get("error", 0),
        skipped=counts.get("skipped", 0),
        passed=counts.get("pass", 0),
        failed=counts.get("fail", 0),
        warned=counts.get("warn", 0))
except FileNotFoundError:
    log("dbt_run_summary_missing", severity="WARNING", job="dbt")

# --- Log final succès / échec ---
if result.returncode == 0:
    log("dbt_job_success", job="dbt", duration_s=duration)
else:
    log("dbt_job_failed", severity="ERROR", job="dbt",
        exit_code=result.returncode, duration_s=duration)

sys.exit(result.returncode)