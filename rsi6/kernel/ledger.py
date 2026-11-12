"""Append-only ledger. Every record carries the SHA-256 of the previous one.

The chain rule and the canonical form are those of ``SCLedger`` in the original runtime
(``h = sha256(prev + canon(record without h))``, canonical JSON with sorted keys and compact
separators), so a ledger written here verifies under that class's ``verify`` and the other way
round. Records live in a JSONL file; nothing is ever rewritten.
"""
from __future__ import annotations

import hashlib
import json
import os

GENESIS = "0" * 64


def canon(value) -> str:
    return json.dumps(value, separators=(",", ":"), sort_keys=True)


def digest(value) -> str:
    return hashlib.sha256(canon(value).encode()).hexdigest()


class Ledger:
    def __init__(self, path: str):
        self.path = path
        self.records = []
        if os.path.exists(path):
            with open(path) as handle:
                self.records = [json.loads(line) for line in handle if line.strip()]
            self.verify()

    def head(self) -> str:
        return self.records[-1]["h"] if self.records else GENESIS

    def append(self, record: dict) -> dict:
        body = dict(record)
        body["idx"] = len(self.records)
        body["prev"] = self.head()
        body["h"] = hashlib.sha256((body["prev"] + canon(body)).encode()).hexdigest()
        os.makedirs(os.path.dirname(os.path.abspath(self.path)), exist_ok=True)
        with open(self.path, "a") as handle:
            handle.write(canon(body) + "\n")
        self.records.append(body)
        return body

    def verify(self) -> None:
        prev = GENESIS
        for i, record in enumerate(self.records):
            if record["idx"] != i or record["prev"] != prev:
                raise AssertionError(f"ledger chain broken at {i}")
            body = {k: v for k, v in record.items() if k != "h"}
            if hashlib.sha256((prev + canon(body)).encode()).hexdigest() != record["h"]:
                raise AssertionError(f"ledger record altered at {i}")
            prev = record["h"]

    def select(self, **where) -> list:
        return [r for r in self.records if all(r.get(k) == v for k, v in where.items())]
