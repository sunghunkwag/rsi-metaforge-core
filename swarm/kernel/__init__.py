"""The frozen kernel: checker language and executor, witness vault, budget meter, ledger and replay,
admission certificates, crossing check, archive, snapshots (OWNER_DIRECTIVE.md §2).

Importing this package verifies the hash pins of every kernel file and of
the pinned mutable evaluator (``hashes.py``); a mismatch raises and no run
can start.
"""
from . import hashes as _hashes

PINS = _hashes.verify()
