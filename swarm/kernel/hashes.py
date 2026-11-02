"""Hash pins of the frozen kernel and of the pinned mutable evaluator (OWNER_DIRECTIVE.md §2, §9).

``PINS`` is written by ``python -m swarm.kernel.hashes --write`` and is
checked by ``verify()`` when ``swarm.kernel`` is imported: a mismatch
raises ``KernelTampered`` and no run can start. The pins are also copied
into ``experiment_config.json`` at registration (P5); after that, the
kernel does not change. ``hashes.py`` itself is pinned only by the config.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

KERNEL = Path(__file__).resolve().parent
ROOT = KERNEL.parents[1]
KERNEL_FILES = ("checker_lang.py", "executor.py", "vault.py", "budget.py", "ledger.py",
                "replay.py", "admit.py", "crossing.py", "snapshot.py", "archive.py")
# The one file of the Builder's mutable tree that is pinned: the evaluator,
# whose METER is the only source of the Builder's evaluation counts.
PINNED_MUTABLE = ("builder/mutable/evaluator.py",)
PIN_PATH = KERNEL / "pins.json"


class KernelTampered(RuntimeError):
    pass


def sha256_of(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def current() -> dict:
    pins = {name: sha256_of(KERNEL / name) for name in KERNEL_FILES}
    pins.update({name: sha256_of(ROOT / "swarm" / name) for name in PINNED_MUTABLE})
    return pins


def pinned() -> dict:
    if not PIN_PATH.exists():
        return {}
    return json.loads(PIN_PATH.read_text(encoding="utf-8"))


def verify() -> dict:
    """Raise unless every pinned file hashes to its pin; returns the pins."""
    expected = pinned()
    if not expected:
        raise KernelTampered("kernel pins are missing (swarm/kernel/pins.json)")
    actual = current()
    changed = sorted(name for name in expected if actual.get(name) != expected[name])
    missing = sorted(name for name in actual if name not in expected)
    if changed or missing:
        raise KernelTampered(f"kernel files changed: {changed}; unpinned: {missing}")
    return expected


def write() -> dict:
    pins = current()
    PIN_PATH.write_text(json.dumps(pins, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    return pins


if __name__ == "__main__":
    import sys
    if "--write" in sys.argv:
        print(json.dumps(write(), indent=1))
    else:
        print(json.dumps(verify(), indent=1))
