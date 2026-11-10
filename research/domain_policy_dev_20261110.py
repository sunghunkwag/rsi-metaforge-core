"""Non-audit engineering preflight: replay-conditioned mutation on synthetic TRAIN fixtures.

Task IDs are externally sourced, but generated examples and task-name oracles
are NOT independent upstream holdouts. No RSI success can be claimed.
"""
from collections import Counter, defaultdict
import hashlib
import json
import math
import os
from pathlib import Path
import random
import re
import statistics
import time

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "research/domain_policy_dev_manifest_20261110.json"
ARMS = ("persistent_domain", "frozen_mutation", "no_memory",
        "wiped_each_generation", "single_generation", "inverted_feedback")
SEEDS, GENERATIONS, PROPOSALS, PUBLIC, SHIFTED = 40, 3, 16, 8, 32


def blob_sha(data):
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()


def validate_manifest():
    m = json.loads(MANIFEST.read_text())
    assert m["main_sha"] == "c4f0a8627a1c9f37dd3aa6291b0eee0c78648210"
    for path, key in (("rsi2/data/source_list_tasks.json", "source_blob_sha"),
                      ("rsi2/data/split_manifest.json", "repo_split_blob_sha")):
        assert blob_sha((ROOT / path).read_bytes()) == m[key], path
    split = json.loads((ROOT / "rsi2/data/split_manifest.json").read_text())
    assert set(m["task_ids"]).issubset(set(split["train"]))
    assert not set(m["task_ids"]) & (set(split["test"]) | set(split["validation"]))
    assert len(m["task_ids"]) == len(set(m["task_ids"])) == 29
    return m


def task_op(name):
    if name == "reverse": return ("reverse", 0, 0, "listint")
    if name == "dup": return ("dup", 0, 0, "listint")
    m = re.fullmatch(r"(.+?) with k=(\d+)(?: and n=(\d+))?", name)
    assert m, name
    family, k, n = m.group(1), int(m.group(2)), int(m.group(3) or 0)
    kind = ("bool" if family in ("has-k", "is-mod-k")
            else "listbool" if family == "bool-identify-k" else "listint")
    return family, k, n, kind


def candidates():
    a = [("reverse", 0, 0, "listint"), ("dup", 0, 0, "listint"),
         ("identity", 0, 0, "listint")]
    for family in ("append-k", "prepend-k", "bool-identify-k", "has-k",
                   "sum-ge-k", "head-eq-k", "all-ge-k", "any-ge-k",
                   "append-index-k", "prepend-index-k",
                   "replace-all-with-index-k", "rotate-k", "is-mod-k"):
        kind = ("bool" if family in ("has-k", "sum-ge-k", "head-eq-k",
                                    "all-ge-k", "any-ge-k", "is-mod-k")
                else "listbool" if family == "bool-identify-k" else "listint")
        first = 0 if family in ("append-k", "prepend-k", "bool-identify-k",
                                "has-k", "sum-ge-k", "head-eq-k",
                                "all-ge-k", "any-ge-k") else 1
        a.extend((family, k, 0, kind) for k in range(first, 9))
    for family in ("modulo-k", "keep-mod-k"):
        a.extend((family, k, 0, "listint") for k in range(2, 9))
    for k in range(1, 9):
        for n in range(1, 6):
            a.append(("slice-k-n", k, n, "listint"))
    for k in range(0, 9):
        for n in range(2, 7):
            a.append(("caesar-cipher-k-modulo-n", k, n, "listint"))
    a += [("bool-even", 0, 0, "listbool"), ("bool-odd", 0, 0, "listbool")]
    a += [("bool-ge-k", k, 0, "listbool") for k in range(9)]
    a += [("constant-bool", k, 0, "bool") for k in range(2)]
    assert len(a) == len(set(a))
    return a


POOL = candidates()


def run_op(op, xs):
    family, k, n, _ = op
    if family == "identity": return xs[:]
    if family == "reverse": return xs[::-1]
    if family == "dup": return xs + xs
    if family == "append-k": return xs + [k]
    if family == "prepend-k": return [k] + xs
    if family == "modulo-k": return [v % k for v in xs]
    if family == "keep-mod-k": return [v for v in xs if v % k == 0]
    if family == "caesar-cipher-k-modulo-n": return [(v + k) % n for v in xs]
    if family == "slice-k-n": return xs[k - 1:k - 1 + n]
    if family == "rotate-k":
        q = k % len(xs) if xs else 0
        return xs[-q:] + xs[:-q] if q else xs[:]
    if family in ("append-index-k", "prepend-index-k", "replace-all-with-index-k"):
        v = xs[k - 1] if 1 <= k <= len(xs) else None
        if v is None: return xs[:]
        if family == "append-index-k": return xs + [v]
        if family == "prepend-index-k": return [v] + xs
        return [v] * len(xs)
    if family == "bool-identify-k": return [v == k for v in xs]
    if family == "has-k": return k in xs
    if family == "is-mod-k": return all(v % k == 0 for v in xs)
    if family == "sum-ge-k": return sum(xs) >= k
    if family == "head-eq-k": return bool(xs) and xs[0] == k
    if family == "all-ge-k": return all(v >= k for v in xs)
    if family == "any-ge-k": return any(v >= k for v in xs)
    if family == "bool-even": return [v % 2 == 0 for v in xs]
    if family == "bool-odd": return [v % 2 != 0 for v in xs]
    if family == "bool-ge-k": return [v >= k for v in xs]
    if family == "constant-bool": return bool(k)
    raise ValueError(op)


def examples(name):
    rng = random.Random(int.from_bytes(hashlib.sha256(name.encode()).digest()[:8], "big"))
    public, shifted = [], []
    for i in range(PUBLIC + SHIFTED):
        length = rng.randrange(13) if i < PUBLIC else (i - PUBLIC) % 33
        xs = [rng.randrange(-8, 21) for _ in range(length)]
        (public if i < PUBLIC else shifted).append(xs)
    return public, shifted


def domain(op, public):
    if op[3] != "listint": return op[3]
    mean_delta = sum(len(run_op(op, xs)) - len(xs) for xs in public) / len(public)
    return "grow" if mean_delta > .2 else "shrink" if mean_delta < -.2 else "preserve"


def choose(pool, episodes, dom, seed, gen, task_index, phase, pass_index, arm):
    gen_key = 0 if arm == "frozen_mutation" else gen
    rng = random.Random(1000003 * (seed + 1) + 1009 * gen_key
                        + 103 * phase + 17 * task_index + 13 * pass_index)
    counts = defaultdict(lambda: [0, 0])
    if arm not in ("frozen_mutation", "no_memory"):
        for d, family, success in episodes:
            if d == dom:
                counts[family][0] += 1
                counts[family][1] += int((not success) if arm == "inverted_feedback" else success)
    ranked = []
    for idx in pool:
        tries, hits = counts[POOL[idx][0]]
        weight = ((hits + 1) / (tries + 2)
                  if arm not in ("frozen_mutation", "no_memory") else 1.0)
        u = min(1 - 1e-12, max(1e-12, rng.random()))
        ranked.append((math.log(weight) - math.log(-math.log(u)), idx))
    ranked.sort(reverse=True)
    return [idx for _, idx in ranked[:PROPOSALS]]


def seed_run(seed, tasks):
    support = [(i, t) for i, t in enumerate(tasks)
               if hashlib.sha256(t.encode()).digest()[0] % 3 != 0]
    evaluation = [(i, t) for i, t in enumerate(tasks)
                  if hashlib.sha256(t.encode()).digest()[0] % 3 == 0]
    result = {}
    for arm in ARMS:
        episodes, counters, cpu, checkpoints = [], Counter(), Counter(), []
        wall0 = time.perf_counter_ns()
        for gen in range(1, GENERATIONS + 1):
            if arm == "wiped_each_generation": episodes.clear()
            support_passes = (3 if arm == "single_generation" and gen == 3
                              else 0 if arm == "single_generation" else 1)
            for pass_index in range(support_passes):
                for task_index, name in support:
                    oracle = task_op(name)
                    public, _ = examples(name)
                    dom = domain(oracle, public)
                    pool = [i for i, op in enumerate(POOL) if op[3] == oracle[3]]
                    t0 = time.process_time_ns()
                    selected = choose(pool, episodes, dom, seed, gen,
                                      task_index, 1, pass_index, arm)
                    cpu["generator_ns"] += time.process_time_ns() - t0
                    for idx in selected:
                        candidate, matched = POOL[idx], True
                        counters["support_candidates"] += 1
                        for xs in public:
                            t0 = time.process_time_ns()
                            got = run_op(candidate, xs)
                            cpu["interpreter_ns"] += time.process_time_ns() - t0
                            t0 = time.process_time_ns()
                            want = run_op(oracle, xs)
                            cpu["oracle_ns"] += time.process_time_ns() - t0
                            counters["support_vm_calls"] += 1
                            counters["support_oracle_calls"] += 1
                            if got != want: matched = False
                        if arm not in ("frozen_mutation", "no_memory"):
                            episodes.append((dom, candidate[0], matched))
            cases = []
            for task_index, name in evaluation:
                oracle = task_op(name)
                public, shifted = examples(name)
                dom = domain(oracle, public)
                pool = [i for i, op in enumerate(POOL) if op[3] == oracle[3]]
                t0 = time.process_time_ns()
                selected = choose(pool, episodes, dom, seed, gen, task_index, 2, 0, arm)
                cpu["generator_ns"] += time.process_time_ns() - t0
                public_mask = full_mask = 0
                for position, idx in enumerate(selected):
                    candidate = POOL[idx]
                    public_ok = shifted_ok = True
                    counters["eval_candidates"] += 1
                    for example_index, xs in enumerate(public + shifted):
                        t0 = time.process_time_ns()
                        got = run_op(candidate, xs)
                        cpu["interpreter_ns"] += time.process_time_ns() - t0
                        t0 = time.process_time_ns()
                        want = run_op(oracle, xs)
                        cpu["oracle_ns"] += time.process_time_ns() - t0
                        counters["eval_vm_calls"] += 1
                        counters["eval_oracle_calls"] += 1
                        if got != want:
                            if example_index < PUBLIC: public_ok = False
                            else: shifted_ok = False
                    if public_ok: public_mask |= 1 << position
                    if public_ok and shifted_ok: full_mask |= 1 << position
                cases.append({"task": name, "domain": dom, "selected": selected,
                              "public_mask": public_mask, "full_mask": full_mask,
                              "passed": bool(full_mask),
                              "spurious_public_fit": bool(public_mask and not full_mask)})
            checkpoints.append({"generation": gen, "cases": cases,
                                "counters": dict(counters), "cpu_ns": dict(cpu),
                                "episodes": len(episodes)})
        result[arm] = {"checkpoints": checkpoints,
                       "total_wall_ns": time.perf_counter_ns() - wall0}
    return result


def bootstrap(diffs, reps=2000):
    rng = random.Random(20261110)
    values = []
    for _ in range(reps):
        values.append(sum(diffs[rng.randrange(len(diffs))] for _ in diffs) / len(diffs))
    values.sort()
    return [round(100 * values[int(.025 * reps)], 4),
            round(100 * values[int(.975 * reps)], 4)]


def summarize(raw):
    summaries, pairs = {}, {}
    for gen in range(GENERATIONS):
        summaries[str(gen + 1)] = {}
        for arm in ARMS:
            cases = [c for seed in raw for c in seed[arm]["checkpoints"][gen]["cases"]]
            n = len(cases)
            summaries[str(gen + 1)][arm] = {
                "passed": sum(c["passed"] for c in cases), "total": n,
                "pass_rate": round(sum(c["passed"] for c in cases) / n, 6),
                "spurious_public_fit": sum(c["spurious_public_fit"] for c in cases),
                "domains": {d: {"passed": sum(c["passed"] for c in cases if c["domain"] == d),
                                "total": sum(c["domain"] == d for c in cases)}
                            for d in sorted(set(c["domain"] for c in cases))}}
        for other in ARMS[1:]:
            wins = losses = ties = 0
            seed_diffs = []
            for seed in raw:
                a = [x["passed"] for x in seed["persistent_domain"]["checkpoints"][gen]["cases"]]
                b = [x["passed"] for x in seed[other]["checkpoints"][gen]["cases"]]
                wins += sum(x and not y for x, y in zip(a, b))
                losses += sum(y and not x for x, y in zip(a, b))
                ties += sum(x == y for x, y in zip(a, b))
                seed_diffs.append((sum(a) - sum(b)) / len(a))
            pairs[f"gen{gen+1}_vs_{other}"] = {
                "wins": wins, "losses": losses, "ties": ties,
                "difference_pp": round(100 * statistics.mean(seed_diffs), 4),
                "seed_cluster_bootstrap_95ci_pp": bootstrap(seed_diffs)}
    costs = {}
    for arm in ARMS:
        last = [seed[arm]["checkpoints"][-1] for seed in raw]
        costs[arm] = {"counters": dict(sum((Counter(x["counters"]) for x in last), Counter())),
                      "cpu_ns": dict(sum((Counter(x["cpu_ns"]) for x in last), Counter())),
                      "wall_ns": sum(seed[arm]["total_wall_ns"] for seed in raw)}
    total = len(raw) * len(raw[0]["persistent_domain"]["checkpoints"][-1]["cases"])
    retention_loss = sum(a["passed"] and not b["passed"] for seed in raw for a, b in zip(
        seed["persistent_domain"]["checkpoints"][0]["cases"],
        seed["persistent_domain"]["checkpoints"][2]["cases"])) / total
    frozen_cpu = sum(costs["frozen_mutation"]["cpu_ns"].values())
    cpu_ratios = {a: round(sum(costs[a]["cpu_ns"].values()) / frozen_cpu, 5) for a in ARMS}
    counters_equal = len({tuple(sorted(costs[a]["counters"].items())) for a in ARMS}) == 1
    h1 = all(pairs[f"gen3_vs_{b}"]["difference_pp"] >= 5
             and pairs[f"gen3_vs_{b}"]["seed_cluster_bootstrap_95ci_pp"][0] > 0
             for b in ("frozen_mutation", "no_memory"))
    gains = [min(pairs[f"gen{g}_vs_{b}"]["difference_pp"]
                 for b in ("frozen_mutation", "no_memory")) for g in (1, 2, 3)]
    domains = summaries["3"]["persistent_domain"]["domains"]
    no_domain_regress = all(
        domains[d]["passed"] >= summaries["3"][b]["domains"].get(d, {"passed": 0})["passed"]
        for d in domains for b in ("frozen_mutation", "no_memory"))
    h2 = gains[0] < gains[1] < gains[2] and no_domain_regress
    h3 = retention_loss <= .05
    h4 = summaries["3"]["inverted_feedback"]["passed"] <= max(
        summaries["3"][b]["passed"] for b in ("frozen_mutation", "no_memory"))
    h5 = counters_equal and all(.9 <= ratio <= 1.1 for ratio in cpu_ratios.values())
    return {"per_generation": summaries, "paired": pairs, "costs": costs,
            "retention_loss_rate": retention_loss, "cpu_ratios_to_frozen": cpu_ratios,
            "hypotheses": {"H1": h1, "H2": h2, "H3": h3, "H4": h4, "H5": h5},
            "preregistered_success": all((h1, h2, h3, h4, h5)),
            "development_only": True}


def report(summary):
    lines = ["# Domain-conditioned mutation replay: development preflight, 2026-11-10",
             "", "**NOT an independent RSI audit.** Synthetic task-name oracles using "
             "pre-existing TRAIN names, not upstream examples or independent holdouts.",
             "", "Preregistration: [PREREG_DOMAIN_POLICY_DEV_20261110.md]"
             "(PREREG_DOMAIN_POLICY_DEV_20261110.md).",
             "Disclosure of inspected local engineering run: "
             "[DISCLOSURE_DOMAIN_POLICY_DEV_20261110.md]"
             "(DISCLOSURE_DOMAIN_POLICY_DEV_20261110.md).",
             "40 independent paired seed trajectories; 3 checkpoints; "
             "32 synthetic shifted inputs; 16 unique candidates per task/checkpoint.",
             "", "| Generation | " + " | ".join(ARMS) + " |",
             "|---|" + "---:|" * len(ARMS)]
    for gen, arms in summary["per_generation"].items():
        lines.append("| " + gen + " | " + " | ".join(
            f'{arms[a]["passed"]}/{arms[a]["total"]}' for a in ARMS) + " |")
    lines += ["", "## Paired wins / losses / ties and seed-clustered 95% CI", ""]
    for key, p in summary["paired"].items():
        lines.append(f'- {key}: {p["wins"]}/{p["losses"]}/{p["ties"]}; '
                     f'{p["difference_pp"]:+.4f} pp; CI {p["seed_cluster_bootstrap_95ci_pp"]}')
    lines += ["", "## Measured compute", ""]
    for arm, c in summary["costs"].items():
        lines.append(f'- {arm}: counts={c["counters"]}; CPU_ns={c["cpu_ns"]}; '
                     f'wall_ns={c["wall_ns"]}; CPU/frozen={summary["cpu_ratios_to_frozen"][arm]}')
    lines += ["", f'Retention loss={summary["retention_loss_rate"]:.6f}',
              f'Hypotheses={summary["hypotheses"]}',
              f'**preregistered_success={str(summary["preregistered_success"]).lower()}**',
              "", "Limitations: generated task-name oracles are NOT the external upstream "
              "examples; shifted inputs are synthetic; interpreter calls are toy Python "
              "functions, not RSI-2 VM calls; OS CPU timing is noisy. Neither the "
              "inspected local engineering run nor this repository replay is independent "
              "confirmatory evidence of multi-generation RSI or AGI. Spent tasks and "
              "original hidden holdouts were not opened.", ""]
    return "\n".join(lines)


def main():
    manifest = validate_manifest()
    tasks = manifest["task_ids"]
    raw = [seed_run(seed, tasks) for seed in range(SEEDS)]
    summary = summarize(raw)
    tested_sha = os.environ.get("GITHUB_SHA", "local-engineering")
    run_id = os.environ.get("GITHUB_RUN_ID", "not-in-actions")
    ci_url = f"https://github.com/sunghunkwag/rsi-metaforge-core/actions/runs/{run_id}"
    pr_url = "https://github.com/sunghunkwag/rsi-metaforge-core/pull/60"
    payload = {"provenance": {
        "tested_source_sha": tested_sha, "ci_url": ci_url, "draft_pr": pr_url,
        "manifest_commit": "9a1159519b3adf5126160b3069396c4ecd34beec",
        "prereg_commit": "a6cf494c0edb6ae4765b9e1afbf585cadd51c60f",
        "source_blob": manifest["source_blob_sha"],
        "split_blob": manifest["repo_split_blob_sha"],
        "seed_count": SEEDS, "generations": GENERATIONS,
        "proposals_per_task": PROPOSALS, "public_examples": PUBLIC,
        "synthetic_shifted_examples": SHIFTED,
        "eval_task_ids": [t for t in tasks if hashlib.sha256(t.encode()).digest()[0] % 3 == 0],
        "support_task_ids": [t for t in tasks if hashlib.sha256(t.encode()).digest()[0] % 3 != 0]},
        "summary": summary, "raw_seed_trajectories": raw}
    dest = ROOT / "research/results/domain_policy_dev_raw_20261110.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists(): raise RuntimeError("spent preflight: results already exist")
    dest.write_text(json.dumps(payload, separators=(",", ":"), sort_keys=True) + "\n")
    (ROOT / "research/RESULTS_DOMAIN_POLICY_DEV_20261110.md").write_text(
        report(summary) + f"\nTested source SHA: `{tested_sha}`. "
        f"[One-shot CI]({ci_url}); [Draft PR #60]({pr_url}).\n")
    readme = ROOT / "README.md"
    marker = "\n## Research note: domain-policy development preflight (2026-11-10)\n"
    if marker in readme.read_text(): raise RuntimeError("spent preflight: README already updated")
    readme.write_text(readme.read_text() + marker + "\n" +
        "Synthetic TRAIN-only engineering study, NOT independent RSI evidence. "
        f"40 paired seed trajectories, three checkpoints, 32 synthetic shifted inputs; "
        f"final persistent {summary['per_generation']['3']['persistent_domain']['passed']}/"
        f"{summary['per_generation']['3']['persistent_domain']['total']}, "
        f"frozen {summary['per_generation']['3']['frozen_mutation']['passed']}/"
        f"{summary['per_generation']['3']['frozen_mutation']['total']}; "
        f"preregistered_success={str(summary['preregistered_success']).lower()}. "
        "[report](research/RESULTS_DOMAIN_POLICY_DEV_20261110.md), "
        "[complete raw JSON](research/results/domain_policy_dev_raw_20261110.json), "
        "[preregistration](research/PREREG_DOMAIN_POLICY_DEV_20261110.md). "
        f"Tested source SHA `{tested_sha}`; [one-shot CI]({ci_url}); "
        f"[Draft PR #60]({pr_url}). "
        "No independent multi-generation learning-to-learn claim.\n")
    print(json.dumps({"completed": True, "summary": summary,
                      "raw_bytes": dest.stat().st_size}))


if __name__ == "__main__":
    main()
