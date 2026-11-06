"""The one door to J: start J's process, hand it a request file, read its response file.

The agent process never imports J's package. This module starts J in a new
interpreter with ``multiprocessing``'s spawn start method; only inside that
child is the package run (``runpy.run_module``). The child inherits no module
state from the agent. Requests carry paths and plain values; responses come
back as J's canonical JSON. J's process runs under the RSS watchdog.

The sealing audit (J's ``audit.py``) allows this module, and no other, to
name J's package, and only as the literal below.
"""
from __future__ import annotations

import hashlib
import json
import multiprocessing
from pathlib import Path

from .watchdog import RSS_CAP_BYTES, run_watched

JUDGE = "rsi4.judge"


class JudgeUnavailable(RuntimeError):
    """J's process did not produce a response."""


def _serve(argv: list[str]) -> None:
    """Runs in the spawned child only."""
    import runpy
    import sys
    sys.argv = [JUDGE, *argv]
    runpy.run_module(JUDGE, run_name="__main__", alter_sys=True)


def ask(request: dict, workdir: Path, *, cap_bytes: int = RSS_CAP_BYTES) -> dict:
    """Send ``request`` to J and return J's response (a dict with ``ok``)."""
    workdir = Path(workdir)
    workdir.mkdir(parents=True, exist_ok=True)
    body = json.dumps(request, sort_keys=True, indent=1)
    tag = hashlib.sha256(body.encode("utf-8")).hexdigest()[:16]
    count = len(list(workdir.glob("request_*.json")))
    request_path = workdir / f"request_{count:05d}_{tag}.json"
    response_path = workdir / f"response_{count:05d}_{tag}.json"
    request_path.write_text(body + "\n", encoding="utf-8")
    context = multiprocessing.get_context("spawn")
    process = context.Process(target=_serve, args=(["--request", str(request_path),
                                                    "--response", str(response_path)],))
    status = run_watched(process, cap_bytes=cap_bytes, log_path=workdir / "watchdog.jsonl",
                         label=f"J {request.get('op')}")
    if status["exitcode"] != 0 or not response_path.exists():
        raise JudgeUnavailable(f"J exited with {status}")
    response = json.loads(response_path.read_text(encoding="utf-8"))
    response["_process"] = status
    return response
