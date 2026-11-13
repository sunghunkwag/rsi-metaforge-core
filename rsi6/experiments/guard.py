"""Guards shared by the drivers that write to the ledger after process c was registered.

The ledger is append-only and its chain is kept in memory by whoever writes: two writers at
once break it. Since amendment 3 there are two files: ``ledger/live.jsonl``, the working ledger
the drivers write, and ``ledger/main.jsonl``, the committed one, which is replaced by verified
copies of the working ledger at checkpoints. This module holds

``single_writer``   an exclusive lock for the lifetime of a driver (a sidecar file next to the
                    ledger; a second driver on the same ledger stops at once);
``same_history``    the check that the committed ledger is a prefix of the working one, so that
                    no driver continues the shorter of two histories;
``checkpoint``      the copy of the working ledger over the committed one, after both checks;
``amendment``       the ledger record of an amendment file, in the shape of the earlier ones.

    python -m rsi6.experiments.guard checkpoint
"""
from __future__ import annotations

import fcntl
import hashlib
import json
import os
import sys
import time

from rsi6.kernel import ledger as ledgers

HERE = os.path.dirname(os.path.abspath(__file__))
REGISTRY = os.path.join(os.path.dirname(HERE), "registry")
MAIN = os.path.join(os.path.dirname(HERE), "ledger", "main.jsonl")
LIVE = os.path.join(os.path.dirname(HERE), "ledger", "live.jsonl")
_HELD = []                                             # lock files stay open as long as the process lives


def is_registered(path: str) -> bool:
    """Whether the path is one of the two registered ledger files (symbolic links resolved)."""
    real = os.path.realpath(path)
    return real in (os.path.realpath(MAIN), os.path.realpath(LIVE))


def single_writer(path: str) -> None:
    """Hold an exclusive lock on the ledger at ``path`` until this process ends."""
    handle = open(os.path.realpath(path) + ".lock", "w")
    try:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        handle.close()
        raise SystemExit(f"another driver is writing {path}: two writers would break the chain")
    _HELD.append(handle)


def _lines(path: str) -> list:
    return [line for line in open(path).read().split("\n") if line.strip()]


def same_history(path: str) -> None:
    """Refuse to work on a registered ledger that is not the longest history: the committed
    ledger must be a prefix of the working one, and a driver must use the working one."""
    if not is_registered(path) or not (os.path.exists(MAIN) and os.path.exists(LIVE)):
        return
    main, live = _lines(MAIN), _lines(LIVE)
    if live[:len(main)] != main:
        raise SystemExit("ledger/main.jsonl is not a prefix of ledger/live.jsonl: the two histories differ; nothing is written")
    if os.path.realpath(path) == os.path.realpath(MAIN) and len(live) > len(main):
        raise SystemExit("ledger/live.jsonl is ahead of ledger/main.jsonl: run the driver on the working ledger, or checkpoint first")


def working() -> str:
    """The ledger a driver writes by default: the working ledger if it exists."""
    return LIVE if os.path.exists(LIVE) else MAIN


def checkpoint() -> int:
    """Replace the committed ledger by the working one, after verifying the chain of the working
    ledger and that the committed one is a prefix of it. A last line that a driver was still
    writing is left out. Returns the number of records committed."""
    lines = _lines(LIVE)
    try:
        json.loads(lines[-1])
    except ValueError:
        lines = lines[:-1]
    main = _lines(MAIN)
    if lines[:len(main)] != main:
        raise SystemExit("ledger/main.jsonl is not a prefix of ledger/live.jsonl: no checkpoint")
    temporary = MAIN + ".checkpoint"
    with open(temporary, "w") as handle:
        handle.write("\n".join(lines) + "\n")
    ledgers.Ledger(temporary).verify()
    os.replace(temporary, MAIN)
    return len(lines)


def amendment(ledger, number: int, what: str) -> dict:
    """The record of amendment ``number``: appended once, in the shape of the earlier ones. If
    it is there already, the file must still be the one that was recorded."""
    relative = f"rsi6/registry/amendment_{number}.json"
    sha = hashlib.sha256(open(os.path.join(REGISTRY, f"amendment_{number}.json"), "rb").read()).hexdigest()
    recorded = ledger.select(type="amendment", amendment=number)
    if recorded:
        if recorded[-1]["record_sha256"] != sha:
            raise SystemExit(f"amendment {number}: the file differs from the one recorded in the ledger")
        return recorded[-1]
    return ledger.append({"type": "amendment", "amendment": number, "record": relative, "record_sha256": sha,
                          "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "what": what})


AMENDMENT_4 = ("after generation 1 of process c: a recursion check after the process; generalised assignment takes the role of flow "
               "shop if its adapter is admitted; readings fixed before any run on a reserve or a target (when the external gate "
               "counts as passed, what process c spent, what 'not behind the compute-matched arm' means, how a matched budget is "
               "raised). The file was committed during generation 2, before its climb had run; this record follows the end of the "
               "process because its driver was writing the ledger")


if __name__ == "__main__":
    if sys.argv[1:] == ["checkpoint"]:
        print("committed", checkpoint(), "records")
    else:
        raise SystemExit(__doc__)
