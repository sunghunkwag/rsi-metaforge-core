"""RESERVE: eligible source tasks that no split and no design decision ever used.

RSI-2's corpus is DreamCoder's 217 list tasks, 207 of them eligible
(RSI-2's DATASET.md). A seeded shuffle selected 60 of these into TRAIN (36),
VALIDATION (12) and TEST (12) (rsi2/data/split_manifest.json). The other
147 were never part of any RSI-3 run.

RSI-2's follow-up research used one task from each of 14 families outside
the 60's families, as its confirmation and audit sets
(RSI-2's research/data/manifest.json). Those 14 families are excluded here.

What remains forms two partitions:

- **RESERVE-NEAR.** Unselected tasks whose family (the name before
  " with ") has a member among the 60: other parameter values of routines
  the splits contain. There are 100.
- **RESERVE-FAR.** Unselected tasks in the families that RSI-2's research
  left unused (its manifest's ``unused_families``), which no split
  contains. There are 12.
- **RESERVE-FAR2.** Unselected tasks in the 14 families RSI-2's research
  drew its confirmation and audit tasks from, other than those tasks
  themselves. No split contains these families, and no run has used these
  tasks. There are 21, in 5 families. They were added after the
  RESERVE-NEAR and RESERVE-FAR results (RESERVE_RESULTS.md), as a second
  test of transfer to new families.

Records are built by RSI-2's own normalizer
(``rsi2.research.transfer.normalize_record``): the first ten distinct inputs
are public and the rest hidden, exactly as the corpus was built. Hidden
examples reach only the frozen verifier.

TEST stays sealed. Its file is never read, and every reserve task differs
from every TEST task by name. Some reserve tasks are parameter variants of
TEST families. That is a property of the corpus, not a reading of TEST.
"""
from __future__ import annotations

import json
from pathlib import Path

from rsi2.corpus import parse_task
from rsi2.research.transfer import family, normalize_record

_RSI2 = Path(__file__).resolve().parents[1] / "rsi2"
SOURCE = _RSI2 / "data" / "source_list_tasks.json"
MANIFEST = _RSI2 / "data" / "split_manifest.json"
RESEARCH = _RSI2 / "research" / "data" / "manifest.json"


def reserve_names() -> dict:
    """The two partitions' task names (sorted), from the committed manifests only."""
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    research = json.loads(RESEARCH.read_text(encoding="utf-8"))
    selected = set(manifest["train"]) | set(manifest["validation"]) | set(manifest["test"])
    selected_families = {family(name) for name in selected}
    unused = set(research["unused_families"])
    rest = [name for name in manifest["eligible_names"] if name not in selected]
    near = sorted(n for n in rest if family(n) in selected_families)
    far = sorted(n for n in rest if family(n) not in selected_families and family(n) in unused)
    research_families = set(research["confirmation_families"]) | set(research["audit_families"])
    research_tasks = set(research["confirmation"]) | set(research["audit"])
    far2 = sorted(n for n in rest if family(n) in research_families
                  and n not in research_tasks)
    return {"near": near, "far": far, "far2": far2}


def load_reserve(partition: str) -> list:
    """Parsed tasks of one partition ("near", "far" or "far2"), in name order."""
    names = reserve_names()[partition]
    wanted = set(names)
    source = json.loads(SOURCE.read_text(encoding="utf-8"))
    records = {}
    for item in source:
        if item.get("name") in wanted:
            record = normalize_record(item)
            if record is None:
                raise ValueError(f"reserve task {item['name']!r} is not eligible")
            records[item["name"]] = record
    if set(records) != wanted:
        raise ValueError("reserve names missing from the source")
    return [parse_task(records[name]) for name in names]
