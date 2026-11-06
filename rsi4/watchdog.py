"""RSS watchdog: a worker over the memory cap is stopped and the breach logged (F9, §7).

The learned failure-memory arm of RSI-3 peaked at 4.5 GB. Here every worker
process (a training run, or J's process) runs under a watchdog thread in its
parent that reads the child's resident set size from ``/proc/<pid>/status``
every ``interval`` seconds. Over the cap (3 GB by default), it kills the child
and appends a breach record to the log; the run does not continue. It also
reports each worker's peak RSS, which every results file lists (D5).

It makes no decision about the system's learning and reads no task.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import threading
import time

RSS_CAP_BYTES = 3 * 1024 ** 3


def rss_bytes(pid: int) -> int | None:
    """Resident set size of ``pid`` in bytes; None where /proc is unavailable or the process is gone."""
    try:
        with open(f"/proc/{pid}/status", encoding="ascii") as handle:
            for line in handle:
                if line.startswith("VmRSS:"):
                    return int(line.split()[1]) * 1024
    except (OSError, ValueError):
        return None
    return None


def run_watched(process, *, cap_bytes: int = RSS_CAP_BYTES, log_path: Path | None = None,
                label: str = "worker", interval: float = 0.25) -> dict:
    """Start ``process`` (a multiprocessing.Process), watch it until it ends, return its record."""
    state = {"peak": 0, "breach": None, "monitored": False}
    process.start()

    def watch():
        while process.is_alive():
            rss = rss_bytes(process.pid)
            if rss is not None:
                state["monitored"] = True
                state["peak"] = max(state["peak"], rss)
                if rss > cap_bytes:
                    state["breach"] = rss
                    process.kill()
                    return
            time.sleep(interval)

    thread = threading.Thread(target=watch, daemon=True)
    thread.start()
    process.join()
    thread.join(timeout=5)
    record = {"label": label, "pid": process.pid, "exitcode": process.exitcode,
              "peak_rss_bytes": state["peak"], "cap_bytes": int(cap_bytes),
              "breach": state["breach"] is not None, "monitored": state["monitored"]}
    if state["breach"] is not None:
        record["breach_rss_bytes"] = state["breach"]
    if log_path is not None and (record["breach"] or not record["monitored"]):
        log_path = Path(log_path)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(dict(record, time=time.time(), host_pid=os.getpid()),
                                    sort_keys=True) + "\n")
    return record
