"""Prepare the follow-up family split from local external-corpus metadata.

This module never executes a task, invokes synthesis, or selects from measured
performance. Preparation is separate from the read-only confirmation loader.
The audit loader lives in a different module and is absent from this API.
"""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import random

from ..corpus import parse_task
from ..types import Arrow, BOOL, INT, ListOf


SEED = 20261004
CONFIRMATION_FAMILIES = 6
AUDIT_FAMILIES = 8
SEARCH_EXAMPLES = 10
_ORIGINAL_DATA = Path(__file__).resolve().parents[1] / "data"
_DATA = Path(__file__).resolve().parent / "data"
_DECLARED_TYPES = {"int": INT, "bool": BOOL,
                   "list-of-int": ListOf(INT), "list-of-bool": ListOf(BOOL)}


def family(name: str) -> str:
    """Use the benchmark author's task-name prefix as a coarse family."""
    if not isinstance(name, str) or not name:
        raise ValueError("task names must be nonempty strings")
    return name.split(" with ", 1)[0]


def _json_key(value):
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise ValueError("examples must contain finite JSON values") from exc


def _distinct_examples(source):
    """Keep first input occurrence, rejecting any conflicting duplicate label."""
    seen, distinct = {}, []
    if not isinstance(source.get("examples"), list):
        raise ValueError("source examples must be a list")
    for example in source["examples"]:
        if not isinstance(example, dict) or "i" not in example or "o" not in example:
            raise ValueError("source examples must provide i and o")
        key, label = _json_key(example["i"]), _json_key(example["o"])
        if key in seen:
            if seen[key] != label:
                raise ValueError(f"conflicting duplicate labels for {source['name']!r}")
            continue
        seen[key] = label
        distinct.append({"inputs": [deepcopy(example["i"])],
                         "output": deepcopy(example["o"])})
    return distinct


def normalize_record(source: dict) -> dict | None:
    """Retain exact external I/O order and declared types; require eleven inputs."""
    if not isinstance(source, dict):
        raise ValueError("source task records must be objects")
    family(source.get("name"))
    declared = source.get("type")
    if not isinstance(declared, dict):
        raise ValueError("source task must declare input and output types")
    try:
        request = Arrow(_DECLARED_TYPES[declared["input"]], _DECLARED_TYPES[declared["output"]])
    except (KeyError, TypeError) as exc:
        raise ValueError("unsupported source input or output type") from exc
    distinct = _distinct_examples(source)
    if len(distinct) <= SEARCH_EXAMPLES:
        return None
    record = {"name": source["name"], "request_type": request.to_dict(),
              "examples": distinct[:SEARCH_EXAMPLES], "hidden": distinct[SEARCH_EXAMPLES:]}
    try:
        parse_task(record)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"examples disagree with declared types for {source['name']!r}") from exc
    return record


def build_transfer(source_records, original_names, seed=SEED):
    """Return manifest and both record lists using names and one seeded RNG."""
    if type(seed) is not int:
        raise ValueError("split seed must be an integer")
    source_records, original_names = list(source_records), list(original_names)
    if len(original_names) != len(set(original_names)):
        raise ValueError("original selected task names must be unique")
    excluded_families = sorted({family(name) for name in original_names})
    eligible, ineligible, all_names = {}, [], set()
    for source in source_records:
        if not isinstance(source, dict):
            raise ValueError("source task records must be objects")
        name = source.get("name")
        family(name)
        if name in all_names:
            raise ValueError("source task names must be unique")
        all_names.add(name)
        record = normalize_record(source)
        if record is None:
            ineligible.append({"name": name, "distinct_inputs": len(_distinct_examples(source)),
                               "reason": "fewer than ten search inputs plus one disjoint hidden input"})
        else:
            eligible[name] = record
    if any(name not in eligible for name in original_names):
        raise ValueError("original selected names must occur in the eligible source corpus")
    excluded = sorted(name for name in eligible if family(name) in excluded_families)
    remaining = sorted(set(eligible) - set(excluded))
    groups = {}
    for name in remaining:
        groups.setdefault(family(name), []).append(name)
    shuffled = sorted(groups)
    rng = random.Random(seed)
    rng.shuffle(shuffled)
    if len(shuffled) < CONFIRMATION_FAMILIES + AUDIT_FAMILIES:
        raise ValueError("not enough untouched families for the fixed follow-up split")
    confirmation_families = shuffled[:CONFIRMATION_FAMILIES]
    audit_families = shuffled[CONFIRMATION_FAMILIES:CONFIRMATION_FAMILIES + AUDIT_FAMILIES]
    selected = [rng.choice(groups[group]) for group in confirmation_families + audit_families]
    confirmation = selected[:CONFIRMATION_FAMILIES]
    audit = selected[CONFIRMATION_FAMILIES:]
    manifest = {
        "version": 1, "seed": seed,
        "purpose": "separate follow-up transfer; no original experiment files are changed",
        "source_file": "rsi2/data/source_list_tasks.json",
        "source_records": len(source_records), "eligible_records": len(eligible),
        "ineligible_records": sorted(ineligible, key=lambda item: item["name"]),
        "original_selected_names": sorted(original_names),
        "excluded_families": excluded_families, "excluded_eligible_names": excluded,
        "remaining_names": remaining, "remaining_families": groups,
        "shuffled_families": shuffled,
        "confirmation_families": confirmation_families, "audit_families": audit_families,
        "unused_families": shuffled[CONFIRMATION_FAMILIES + AUDIT_FAMILIES:],
        "confirmation": confirmation, "audit": audit,
        "sample_counts": {"confirmation": CONFIRMATION_FAMILIES, "audit": AUDIT_FAMILIES},
        "grouping_rule": "name.split(' with ', 1)[0]",
        "selection_rule": "shuffle sorted untouched families with Random(seed); first six confirmation, next eight audit; choose one sorted member per family with the same RNG",
        "normalization": "deduplicate inputs preserving order; first ten search examples and all remaining hidden examples; preserve declared external types and exact I/O",
        "limits": ["Task-name families are a coarse author-supplied grouping, not a proof of semantic independence.",
                   "Both follow-up partitions come from the same external benchmark as the original study.",
                   "Only one identity is sampled per family; six confirmation and eight audit tasks give limited statistical resolution.",
                   "No selection uses solver, evaluator, learned-policy, or original-result performance."],
    }
    return manifest, [eligible[name] for name in confirmation], [eligible[name] for name in audit]


def prepare(output_dir=None, source_path=None, original_manifest_path=None):
    """Write only the separate transfer files; reproducible preparation is offline."""
    output_dir = Path(output_dir) if output_dir is not None else _DATA
    source_path = Path(source_path) if source_path is not None else _ORIGINAL_DATA / "source_list_tasks.json"
    original_manifest_path = (Path(original_manifest_path) if original_manifest_path is not None
                              else _ORIGINAL_DATA / "split_manifest.json")
    destination = output_dir.resolve()
    if destination == _ORIGINAL_DATA.resolve() or _ORIGINAL_DATA.resolve() in destination.parents:
        raise ValueError("follow-up preparation cannot write original experiment data")
    source = json.loads(source_path.read_text(encoding="utf-8"))
    original = json.loads(original_manifest_path.read_text(encoding="utf-8"))
    selected = [name for split in ("train", "validation", "test") for name in original[split]]
    manifest, confirmation, audit = build_transfer(source, selected)
    observed = (manifest["source_records"], manifest["eligible_records"],
                len(manifest["original_selected_names"]), len(manifest["remaining_names"]),
                len(manifest["remaining_families"]))
    if observed != (217, 207, 60, 47, 26):
        raise ValueError(f"local source metadata disagrees with the preregistered follow-up population: {observed}")
    manifest["source_repository"] = original["source_repository"]
    manifest["source_commit"] = original["source_commit"]
    payloads = {"manifest.json": manifest, "confirmation.json": confirmation, "audit.json": audit}
    serialized = {name: json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
                  for name, value in payloads.items()}
    output_dir.mkdir(parents=True, exist_ok=True)
    for name, contents in serialized.items():
        (output_dir / name).write_text(contents, encoding="utf-8")
    return manifest


def load_confirmation(data_dir=None):
    """Read the fixed confirmation partition without preparing or changing files."""
    directory = Path(data_dir) if data_dir is not None else _DATA
    records = json.loads((directory / "confirmation.json").read_text(encoding="utf-8"))
    return [parse_task(record) for record in records]


def main():
    manifest = prepare()
    print(json.dumps({"seed": manifest["seed"], "eligible_records": manifest["eligible_records"],
                      "remaining_identities": len(manifest["remaining_names"]),
                      "remaining_families": len(manifest["remaining_families"]),
                      "confirmation_tasks": len(manifest["confirmation"]),
                      "audit_tasks": len(manifest["audit"])}, indent=2))


if __name__ == "__main__":
    main()
