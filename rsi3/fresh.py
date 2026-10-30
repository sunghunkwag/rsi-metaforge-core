"""FRESH: held-out list tasks from outside RSI-2's corpus, frozen before any run used them.

Every partition inside RSI-2's corpus has now been used. VALIDATION and
the three RESERVE partitions were each run and their results read, so a
design made after reading them is not tested cleanly on them. FRESH comes
from a different file: DreamCoder's second list-task set,
``data/list_tasks2.json`` in ``ellisk42/ec`` at commit
cb0e63f5c33cd2de360b791038b0f5272750270e (MIT license). That file holds
174,258 generated list programs, most of them pipelines of two or three
routines. RSI-2's corpus is DreamCoder's first file, ``list_tasks.json``.

Two partitions, chosen by rules over names and declared types only. No
task was run to select them.

- **FRESH-1 (single routines).**
  - Selected: every task that is one routine applied to the input, has
    declared types RSI-2 supports, and has at least nine distinct inputs.
  - Excluded: any task whose corpus-style name (``"add-k with k=10"``) is a
    name in RSI-2's corpus. 54 were excluded this way, so none is a TEST
    task.
  - Result: 33 tasks. Most are routines with parameters the corpus never
    uses (-2, 10). The rest are routines the corpus does not contain:
    ``intersperse-k``, ``positions``, ``uniq``, ``identify-is-prime``,
    ``replace-index-k-with-n`` and others.
- **FRESH-2 (two-stage pipelines).**
  - Pool: tasks that are exactly two routines in sequence, the second
    applied to the first's output, with the same type and example rules.
    There are 5,835.
  - Selected: 100 of them, drawn with ``random.Random(SEED)``.
  - This partition measures composition. No arm was ever trained on a
    pipeline.

**Example protocol.** Each source task has ten examples, fewer than RSI-2's
rule of ten search inputs plus a hidden one. Here the first ``PUBLIC``
distinct inputs (8), in source order, are public. The rest (1 or 2) are
hidden and reach only the frozen verifier. Searches see two fewer examples
than on the corpus, which makes FRESH harder than RESERVE for every arm.

The selected source records are committed verbatim in
``data/fresh_tasks.json``. ``build`` re-derives them from the source file
when it is present (``tests/test_fresh.py``). TEST stays sealed: no file of
it is read here.
"""
from __future__ import annotations

import json
from pathlib import Path
import random
import re

from rsi2.corpus import Task, infer_request_type
from rsi2.research.transfer import _DECLARED_TYPES, _distinct_examples, _json_key
from rsi2.types import Arrow, unify

SEED = 20261030
PUBLIC = 8
PIPELINES = 100
SOURCE_COMMIT = "cb0e63f5c33cd2de360b791038b0f5272750270e"
DATA = Path(__file__).resolve().parent / "data" / "fresh_tasks.json"
CORPUS = Path(__file__).resolve().parents[1] / "rsi2" / "data" / "source_list_tasks.json"

_COMPONENT = re.compile(r"\(([a-z\-]+)((?: \((?:dyn|static) \. -?\d+\))*)\)")
_ARGUMENT = re.compile(r"\((dyn|static) \. (-?\d+)\)")


def components(name: str) -> list:
    """``"((add-k (dyn . 0) (static . 3)))"`` -> ``[("add-k", [("dyn", 0), ("static", 3)])]``."""
    found = []
    for match in _COMPONENT.finditer(name[1:-1]):
        found.append((match.group(1), [(kind, int(value))
                                       for kind, value in _ARGUMENT.findall(match.group(2))]))
    return found


def corpus_style_name(routine: str, arguments) -> str:
    statics = [value for kind, value in arguments if kind == "static"]
    if not statics:
        return routine
    if len(statics) == 1:
        return f"{routine} with k={statics[0]}"
    return f"{routine} with k={statics[0]} and n={statics[1]}"


def _eligible(record) -> bool:
    declared = record.get("type", {})
    if declared.get("input") not in _DECLARED_TYPES or declared.get("output") not in _DECLARED_TYPES:
        return False
    return len(_distinct_examples(record)) > PUBLIC


def build(source_records, corpus_names) -> dict:
    """Both partitions' source records, by the rules above (names and types only)."""
    single, pipelines = [], []
    for record in source_records:
        parts = components(record["name"])
        if not parts or not _eligible(record):
            continue
        flows = [[value for kind, value in args if kind == "dyn"] for _, args in parts]
        if len(parts) == 1 and flows == [[0]]:
            if corpus_style_name(*parts[0]) not in corpus_names:
                single.append(record)
        elif len(parts) == 2 and flows == [[0], [1]]:
            pipelines.append(record)
    pipelines.sort(key=lambda r: r["name"])
    chosen = random.Random(SEED).sample(pipelines, PIPELINES)
    chosen.sort(key=lambda r: r["name"])
    single.sort(key=lambda r: r["name"])
    return {"fresh1": single, "fresh2": chosen, "pipeline_pool": len(pipelines)}


def to_task(record) -> Task:
    """Public = the first PUBLIC distinct inputs in source order; the rest are hidden."""
    distinct = _distinct_examples(record)
    request = Arrow(_DECLARED_TYPES[record["type"]["input"]],
                    _DECLARED_TYPES[record["type"]["output"]])

    def pairs(values):
        return tuple((tuple(item["inputs"]), item["output"]) for item in values)

    examples, hidden = pairs(distinct[:PUBLIC]), pairs(distinct[PUBLIC:])
    if not hidden or {_json_key(list(x)) for x, _ in examples} & {_json_key(list(x))
                                                                 for x, _ in hidden}:
        raise ValueError(f"bad split for {record['name']!r}")
    unify(infer_request_type(examples + hidden), request)
    return Task(record["name"], request, examples, hidden)


def load_fresh(partition: str) -> list:
    """Parsed tasks of "fresh1" or "fresh2", in name order, from the committed records."""
    data = json.loads(DATA.read_text(encoding="utf-8"))
    return [to_task(record) for record in data[partition]]
