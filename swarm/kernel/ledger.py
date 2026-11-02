"""Append-only hash-chained ledger (OWNER_DIRECTIVE.md §2, Phase K's K3).

Every admission, certificate outcome, crossing, self-edit decision, mapper
refit and generation summary is one entry. An entry's hash covers its
index, kind, payload and the previous hash, so no entry can be altered,
reordered or dropped without breaking the chain (``verify``). Payloads are
JSON with sorted keys; the ledger can be written to and read back from a
JSONL file, and ``replay.py`` re-derives certificates and crossings from it.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

GENESIS = "0" * 64


def _canonical(payload) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


def entry_hash(index: int, kind: str, payload, previous: str) -> str:
    blob = f"{index}|{kind}|{_canonical(payload)}|{previous}"
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


class Ledger:
    def __init__(self):
        self.entries: list = []

    @property
    def head(self) -> str:
        return self.entries[-1]["hash"] if self.entries else GENESIS

    def append(self, kind: str, payload: dict) -> dict:
        index = len(self.entries)
        entry = {"index": index, "kind": kind, "payload": json.loads(_canonical(payload)),
                 "prev": self.head}
        entry["hash"] = entry_hash(index, kind, entry["payload"], entry["prev"])
        self.entries.append(entry)
        return entry

    def verify(self) -> bool:
        previous = GENESIS
        for index, entry in enumerate(self.entries):
            if entry["index"] != index or entry["prev"] != previous:
                return False
            if entry["hash"] != entry_hash(index, entry["kind"], entry["payload"], previous):
                return False
            previous = entry["hash"]
        return True

    def of_kind(self, kind: str) -> list:
        return [e for e in self.entries if e["kind"] == kind]

    def write(self, path: Path) -> None:
        text = "".join(_canonical(e) + "\n" for e in self.entries)
        Path(path).write_text(text, encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> "Ledger":
        ledger = cls()
        for line in Path(path).read_text(encoding="utf-8").splitlines():
            if line.strip():
                ledger.entries.append(json.loads(line))
        if not ledger.verify():
            raise ValueError("ledger chain broken")
        return ledger

    def digest(self) -> str:
        return hashlib.sha256(self.head.encode("utf-8")).hexdigest()[:16]
