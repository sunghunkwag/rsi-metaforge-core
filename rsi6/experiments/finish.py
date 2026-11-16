"""What remains of the registered program, run in its registered order.

    python -m rsi6.experiments.finish [--until STEP] [--log PATH]

The steps, each a driver that can be stopped and started again:

  1 process     process c to its last generation (alternating.py; amendment 3)
  2 external    its freeze record and its external gate on the reserves (external.py; amendments 3, 4)
  3 recursion   the recursion check (recursion.py; amendment 4)
  4 targets     the sealed target test of all three processes (targets.py; registration, amendments 1 to 4)

A step is run only after the one before has written the record of its end, and it is skipped
if its own record is there already, so this driver can be stopped and started again too. A
step is never run beside another writer of the ledger: while one holds the ledger's lock (for
example the driver of process c started by hand), this driver waits. After every step the
committed ledger is replaced by a verified copy of the working one. Nothing here decides
anything: every rule is in the drivers and in the registered files they read.

``--until`` stops after the named step (for example ``--until recursion`` leaves the target
test for later).
"""
from __future__ import annotations

import argparse
import fcntl
import os
import subprocess
import sys
import time

from rsi6.experiments import guard
from rsi6.kernel import ledger as ledgers

STEPS = [
    ("process", "rsi6.experiments.alternating",
     lambda L, reg: all(L.select(type="c_generation_done", generation=g) for g in range(1, reg["generations_planned"] + 1))),
    ("external", "rsi6.experiments.external", lambda L, reg: bool(L.select(type="external_gate", process="c"))),
    ("recursion", "rsi6.experiments.recursion", lambda L, reg: bool(L.select(type="recursion_done"))),
    ("targets", "rsi6.experiments.targets", lambda L, reg: bool(L.select(type="target_done"))),
]


def say(log, *parts) -> None:
    line = " ".join([time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())] + [str(p) for p in parts])
    print(line, flush=True)
    with open(log, "a") as handle:
        handle.write(line + "\n")


def wait_for_the_lock(path: str, log: str) -> None:
    """Return once no other process holds the ledger's lock (and release it at once: the step takes it)."""
    told = False
    while True:
        with open(os.path.realpath(path) + ".lock", "w") as handle:
            try:
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
                fcntl.flock(handle, fcntl.LOCK_UN)
                return
            except OSError:
                if not told:
                    say(log, "another driver is writing the ledger; waiting for it to end")
                    told = True
        time.sleep(60)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--until", choices=[name for name, _, _ in STEPS], default=STEPS[-1][0])
    parser.add_argument("--log", default=os.path.join(os.path.dirname(guard.LIVE), "finish.log"))
    args = parser.parse_args()
    path = guard.LIVE
    if not os.path.exists(path):
        raise SystemExit("there is no working ledger (ledger/live.jsonl)")
    env = dict(os.environ, OPENBLAS_NUM_THREADS="1", OMP_NUM_THREADS="1", PYTHONHASHSEED="0")
    for name, module, done in STEPS:
        ledger = ledgers.Ledger(path)
        reg = ledger.select(type="registration_c")[-1]["registration"]
        if done(ledger, reg):
            say(args.log, f"step {name}: recorded already")
        else:
            wait_for_the_lock(path, args.log)
            ledger = ledgers.Ledger(path)                  # another driver may have finished the step meanwhile
            if not done(ledger, reg):
                say(args.log, f"step {name}: python -m {module}")
                with open(args.log, "a") as out:
                    code = subprocess.run([sys.executable, "-u", "-m", module], env=env, stdout=out, stderr=subprocess.STDOUT).returncode
                ledger = ledgers.Ledger(path)
                if code != 0 or not done(ledger, reg):
                    say(args.log, f"step {name}: ended with code {code} without the record of its end; stopping")
                    return 1
            say(args.log, f"step {name}: done; committed ledger now {guard.checkpoint()} records")
        if name == args.until:
            break
    return 0


if __name__ == "__main__":
    sys.exit(main())
