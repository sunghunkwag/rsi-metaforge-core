"""Crossing curves, increments, second differences and the K1-K7 rules from run summaries (OWNER_DIRECTIVE.md §8).

    python -m swarm.report --results RUN_DIR --output report.md [--replay] [--full-replay]

Reads every ``<arm>_seed<seed>/summary.json`` under ``--results`` and
writes a Markdown report: per arm and seed the crossing curve X(g), its
increment ΔX(g), the second difference over the last half of the run,
the logical budget spent, frontier motion (archive size, fraction
crossed, mean generations-to-crossing, Kb margins at admission),
substrate growth (primitives forged, library size, self-edits adopted and
the solve delta that admitted each), channel statistics (retrieval hit
rate, field norms, mapper residual) and the collapse detectors
(rejections per certificate, live-call failures, self-edit regressions).
Then the decisive comparisons K1-K6 by their registered pass rules, and
K7 when ``--replay`` is given (ledger replay of every run; ``--full-replay``
re-runs the Kb and crossing solves too). No prediction is scored here:
PREDICTIONS.md is scored by hand in RESULTS.md against these numbers.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

ARM_ORDER = ["SWARM_FULL", "SWARM_RECORDS", "SWARM_NO_MAPPER", "SWARM_NO_SELFEDIT",
             "SWARM_NO_BREAKER_REGRET", "SWARM_SHUFFLED_FIELD", "SWARM_FROZEN"]


def load_runs(results: Path) -> dict:
    runs = {}
    for path in sorted(Path(results).glob("*_seed*/summary.json")):
        summary = json.loads(path.read_text(encoding="utf-8"))
        runs[(summary["arm"], int(summary["seed"]))] = summary
    return runs


def curve(summary: dict) -> list:
    """X(g): cumulative crossings after each generation."""
    return [g["crossings_cumulative"] for g in summary["generations"]]


def increments(x: list) -> list:
    return [x[0]] + [b - a for a, b in zip(x, x[1:])] if x else []


def second_differences(x: list) -> list:
    dx = increments(x)
    return [b - a for a, b in zip(dx, dx[1:])]


def last_half(values: list) -> list:
    return values[len(values) // 2:] if values else []


def compounding(summary: dict) -> dict:
    """K6 per run: every second difference over the last half >= 0; otherwise the peak generation."""
    x = curve(summary)
    d2 = second_differences(x)
    tail = last_half(d2)
    dx = increments(x)
    peak = (max(range(len(dx)), key=lambda i: (dx[i], -i)) + 1) if dx else None
    return {"passes": bool(tail) and all(v >= 0 for v in tail), "last_half_second_differences": tail,
            "sum_last_half": sum(tail), "peak_increment_generation": peak,
            "peak_increment": max(dx) if dx else 0}


def frontier(summary: dict) -> dict:
    final = summary["final"]
    counts = final["archive"]
    gens = final.get("generations_to_crossing", [])
    margins = [g["kb_margin_mean"] for g in summary["generations"] if g.get("kb_margin_mean") is not None]
    return {"archive": counts["total"], "crossed": counts["crossed"], "open": counts["open"],
            "markers": counts["marker"],
            "fraction_crossed": counts["crossed"] / counts["total"] if counts["total"] else 0.0,
            "never_crossed_fraction": (counts["total"] - counts["crossed"]) / counts["total"] if counts["total"] else 0.0,
            "mean_generations_to_crossing": sum(gens) / len(gens) if gens else None,
            "kb_margin_mean": sum(margins) / len(margins) if margins else None}


def substrate(summary: dict) -> dict:
    gens = summary["generations"]
    adopted = []
    for g in gens:
        for d in g["self_edits"]["decisions"]:
            if d["adopted"]:
                adopted.append({"generation": g["generation"], "kind": d["kind"],
                                "solves": f"{d['incumbent_solved']}->{d['candidate_solved']}"})
    tree = summary["final"]["tree"]
    return {"primitives_forged": tree["primitives_forged"], "library_entries": tree["library_entries"],
            "self_edits_proposed": sum(g["self_edits"]["proposed"] for g in gens),
            "self_edits_adopted": len(adopted), "adopted": adopted,
            "regressions": sum(1 for g in gens for d in g["self_edits"]["decisions"]
                               if d["reason"].startswith("regressed")),
            "learned_entries": sum(len(g["learned"]) for g in gens)}


def channel(summary: dict) -> dict:
    gens = summary["generations"]
    crossings = sum(g["crossings"] for g in gens)
    hits = sum(g["retrieval_hits"] for g in gens)
    last = gens[-1] if gens else {}
    return {"retrieval_hit_rate": hits / crossings if crossings else None,
            "breaker_norm": (last.get("field") or {}).get("breaker_norm"),
            "builder_norm": (last.get("field") or {}).get("builder_norm"),
            "mapper_pairs": (last.get("mapper") or {}).get("pairs"),
            "mapper_residual": (last.get("mapper") or {}).get("residual")}


def detectors(summary: dict) -> dict:
    gens = summary["generations"]
    rejections = {}
    proposals = sum(g["proposals"] for g in gens)
    for g in gens:
        for cert, n in g["rejections"].items():
            rejections[cert] = rejections.get(cert, 0) + n
    return {"proposals": proposals, "admitted": sum(g["admitted"] for g in gens),
            "rejections": rejections,
            "kb_rejection_rate": rejections.get("Kb", 0) / proposals if proposals else None,
            "wake_failures": sum(1 for g in gens if g["wake_failed"]),
            "kernel_failures": {"admission": sum(g.get("kernel_failed", 0) for g in gens),
                                "mined_checks": sum(g.get("mined_checks_failed", 0) for g in gens),
                                "crossing_checks": sum(g.get("crossing_checks_failed", 0) for g in gens),
                                "judge": sum(g.get("judge_failed", 0) for g in gens)},
            "forge_candidates": sum(g.get("forge_candidates", 0) for g in gens),
            "executors": summary["final"].get("executors")}


def budget(summary: dict) -> dict:
    last = summary["generations"][-1]["budget_cumulative"] if summary["generations"] else {}
    return {agent: last.get(agent, {}).get("evaluations", 0) for agent in ("breaker", "builder", "kernel")} | \
        {f"{agent}_steps": last.get(agent, {}).get("steps", 0) for agent in ("breaker", "builder", "kernel")}


def comparisons(runs: dict) -> dict:
    """K1-K6 by the registered pass rules, every seed."""
    seeds = sorted({seed for _, seed in runs})

    def final_x(arm, seed):
        run = runs.get((arm, seed))
        return curve(run)[-1] if run and run["generations"] else None

    out = {}
    for name, other, text in (("K1", "SWARM_NO_SELFEDIT", "substrate change produces crossings"),
                              ("K2", "SWARM_RECORDS", "the latent channel beats records"),
                              ("K3", "SWARM_NO_MAPPER", "the mapper matters"),
                              ("K4", "SWARM_SHUFFLED_FIELD", "the channel carries information")):
        per_seed = {seed: (final_x("SWARM_FULL", seed), final_x(other, seed)) for seed in seeds}
        decided = {s: v for s, v in per_seed.items() if None not in v}
        out[name] = {"comparison": f"SWARM_FULL vs {other}", "rule": f"X_S0(G) > X_other(G) on every seed: {text}",
                     "per_seed": per_seed,
                     "passes": bool(decided) and len(decided) == len(seeds) and all(a > b for a, b in decided.values())}
    per_seed = {}
    for seed in seeds:
        s0, s4 = runs.get(("SWARM_FULL", seed)), runs.get(("SWARM_NO_BREAKER_REGRET", seed))
        if s0 and s4:
            f0, f4 = frontier(s0), frontier(s4)
            per_seed[seed] = {"mean_generations_to_crossing": (f0["mean_generations_to_crossing"],
                                                              f4["mean_generations_to_crossing"]),
                              "never_crossed_fraction": (f0["never_crossed_fraction"], f4["never_crossed_fraction"])}
    def k5_seed(v):
        a, b = v["mean_generations_to_crossing"]
        c, d = v["never_crossed_fraction"]
        return a is not None and b is not None and a < b and c < d
    out["K5"] = {"comparison": "SWARM_FULL vs SWARM_NO_BREAKER_REGRET",
                 "rule": "mean generations-to-crossing lower and never-crossed fraction lower in S0, every seed",
                 "per_seed": per_seed,
                 "passes": bool(per_seed) and len(per_seed) == len(seeds) and all(k5_seed(v) for v in per_seed.values())}
    k6 = {seed: compounding(runs[("SWARM_FULL", seed)]) for seed in seeds if ("SWARM_FULL", seed) in runs}
    out["K6"] = {"comparison": "SWARM_FULL compounding",
                 "rule": "second difference of X(g) >= 0 over the last half of the run on every seed",
                 "per_seed": k6, "passes": bool(k6) and len(k6) == len(seeds) and all(v["passes"] for v in k6.values())}
    return out


def k7(results: Path, runs: dict, full: bool) -> dict:
    from swarm.kernel import hashes
    from swarm.kernel.replay import replay
    report = {"kernel_pins_ok": hashes.verify() == hashes.pinned(), "runs": {}}
    for (arm, seed), summary in runs.items():
        run_dir = Path(results) / f"{arm}_seed{seed}"
        try:
            out = replay(run_dir, full=full)
            report["runs"][f"{arm}_seed{seed}"] = {"chain_ok": out["chain_ok"], "entries": out["entries"],
                                                  "certificates": out["certificates"], "crossings": out["crossings"],
                                                  "disagreements": out["disagreements"], "digest": out["digest"],
                                                  "full": full}
        except Exception as exc:          # a missing artifact is a failure of K7, reported as such
            report["runs"][f"{arm}_seed{seed}"] = {"chain_ok": False, "error": str(exc)}
    report["passes"] = report["kernel_pins_ok"] and all(
        r.get("chain_ok") and not r.get("disagreements") for r in report["runs"].values())
    return report


def _fmt(value, digits=3):
    if value is None:
        return "-"
    if isinstance(value, float):
        return f"{value:.{digits}f}"
    return str(value)


def render(runs: dict, comparisons_report: dict, k7_report: dict | None) -> str:
    arms = [a for a in ARM_ORDER if any(arm == a for arm, _ in runs)] + \
           sorted({arm for arm, _ in runs} - set(ARM_ORDER))
    seeds = sorted({seed for _, seed in runs})
    lines = ["# SWARM report", "",
             "Crossing curves of self-posed task archives under the frozen kernel. Not a benchmark result.", ""]
    lines += ["## Crossing curves X(g)", "", "| Arm | Seed | G | X(G) | ΔX by generation | last-half second differences | peak ΔX (gen) | Builder candidates |",
              "| --- | --- | --- | --- | --- | --- | --- | --- |"]
    for arm in arms:
        for seed in seeds:
            run = runs.get((arm, seed))
            if not run:
                continue
            x = curve(run)
            comp = compounding(run)
            lines.append(f"| {arm} | {seed} | {len(x)} | {x[-1] if x else 0} | {' '.join(str(v) for v in increments(x))} | "
                         f"{' '.join(str(v) for v in comp['last_half_second_differences'])} | "
                         f"{comp['peak_increment']} (g{comp['peak_increment_generation']}) | {budget(run)['builder']} |")
    lines += ["", "## Frontier motion", "", "| Arm | Seed | archive | crossed | open | markers | fraction crossed | never crossed | mean gens-to-crossing | mean Kb margin |",
              "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
    for arm in arms:
        for seed in seeds:
            run = runs.get((arm, seed))
            if not run:
                continue
            f = frontier(run)
            lines.append(f"| {arm} | {seed} | {f['archive']} | {f['crossed']} | {f['open']} | {f['markers']} | "
                         f"{_fmt(f['fraction_crossed'])} | {_fmt(f['never_crossed_fraction'])} | "
                         f"{_fmt(f['mean_generations_to_crossing'], 2)} | {_fmt(f['kb_margin_mean'])} |")
    lines += ["", "## Substrate growth", "", "| Arm | Seed | primitives forged | library entries | learned entries | self-edits adopted / proposed | regressions caught | adopted edits (gen: kind, solves) |",
              "| --- | --- | --- | --- | --- | --- | --- | --- |"]
    for arm in arms:
        for seed in seeds:
            run = runs.get((arm, seed))
            if not run:
                continue
            s = substrate(run)
            adopted = "; ".join(f"g{a['generation']}: {a['kind']} {a['solves']}" for a in s["adopted"]) or "-"
            lines.append(f"| {arm} | {seed} | {s['primitives_forged']} | {s['library_entries']} | {s['learned_entries']} | "
                         f"{s['self_edits_adopted']} / {s['self_edits_proposed']} | {s['regressions']} | {adopted} |")
    lines += ["", "## Channel and collapse detectors", "", "| Arm | Seed | retrieval hit rate | breaker norm | builder norm | mapper pairs | mapper residual | proposals | admitted | rejections | Kb rejection rate | wake failures | kernel failures (admission / mined / crossing / judge) | forge candidates |",
              "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
    for arm in arms:
        for seed in seeds:
            run = runs.get((arm, seed))
            if not run:
                continue
            c, d = channel(run), detectors(run)
            rejections = " ".join(f"{k}:{v}" for k, v in sorted(d["rejections"].items()) if v)
            lines.append(f"| {arm} | {seed} | {_fmt(c['retrieval_hit_rate'])} | {_fmt(c['breaker_norm'])} | {_fmt(c['builder_norm'])} | "
                         f"{_fmt(c['mapper_pairs'])} | {_fmt(c['mapper_residual'])} | {d['proposals']} | {d['admitted']} | {rejections or '-'} | "
                         f"{_fmt(d['kb_rejection_rate'])} | {d['wake_failures']} | "
                         f"{d['kernel_failures']['admission']} / {d['kernel_failures']['mined_checks']} / "
                         f"{d['kernel_failures']['crossing_checks']} / {d['kernel_failures']['judge']} | {d['forge_candidates']} |")
    lines += ["", "## Logical budget (cumulative candidate evaluations / interpreter steps)", "",
              "| Arm | Seed | Breaker steps | Builder candidates | Builder steps | Kernel candidates | Kernel steps | wall seconds |",
              "| --- | --- | --- | --- | --- | --- | --- | --- |"]
    for arm in arms:
        for seed in seeds:
            run = runs.get((arm, seed))
            if not run:
                continue
            b = budget(run)
            lines.append(f"| {arm} | {seed} | {b['breaker_steps']} | {b['builder']} | {b['builder_steps']} | {b['kernel']} | {b['kernel_steps']} | {run['wall_seconds']:.0f} |")
    lines += ["", "## Decisive comparisons", "", "| # | Comparison | Rule | Per seed | Passes |", "| --- | --- | --- | --- | --- |"]
    for name, item in comparisons_report.items():
        per_seed = "; ".join(f"seed {s}: {json.dumps(v, default=str)}" for s, v in item["per_seed"].items()) or "-"
        lines.append(f"| {name} | {item['comparison']} | {item['rule']} | {per_seed} | {'yes' if item['passes'] else 'no'} |")
    if k7_report is not None:
        lines += ["", "## K7 integrity", "", f"Kernel pins unchanged: {'yes' if k7_report['kernel_pins_ok'] else 'no'}. "
                  f"Replay ({'full' if any(r.get('full') for r in k7_report['runs'].values()) else 'fast'}):", ""]
        for name, r in sorted(k7_report["runs"].items()):
            lines.append(f"- {name}: chain {'ok' if r.get('chain_ok') else 'BROKEN'}, "
                         f"{r.get('certificates', '-')} certificates, {r.get('crossings', '-')} crossings, "
                         f"disagreements {r.get('disagreements', r.get('error'))}, digest {r.get('digest', '-')}")
        lines.append(f"\nK7 passes: {'yes' if k7_report['passes'] else 'no'}")
    return "\n".join(lines) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--replay", action="store_true")
    parser.add_argument("--full-replay", action="store_true")
    parser.add_argument("--json", type=Path, default=None, help="also write the numbers as JSON")
    args = parser.parse_args(argv)
    runs = load_runs(args.results)
    if not runs:
        raise SystemExit(f"no summaries under {args.results}")
    comparison_report = comparisons(runs)
    k7_report = k7(args.results, runs, args.full_replay) if (args.replay or args.full_replay) else None
    args.output.write_text(render(runs, comparison_report, k7_report), encoding="utf-8")
    if args.json is not None:
        numbers = {f"{arm}_seed{seed}": {"curve": curve(run), "frontier": frontier(run), "substrate": substrate(run),
                                         "channel": channel(run), "detectors": detectors(run), "budget": budget(run),
                                         "compounding": compounding(run), "wall_seconds": run["wall_seconds"]}
                   for (arm, seed), run in runs.items()}
        args.json.write_text(json.dumps({"runs": numbers, "comparisons": comparison_report, "k7": k7_report},
                                        indent=1, default=str) + "\n", encoding="utf-8")
    print(f"wrote {args.output}")


if __name__ == "__main__":
    main()
