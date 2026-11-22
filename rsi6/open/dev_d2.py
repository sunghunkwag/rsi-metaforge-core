"""Development check D2 of design r (the relay): leave one category out.

Development only: categories of the source pool, a scratch ledger, nothing here is evidence
(``rsi6/audit/design_panel_20261116/synthesize.json``, ``development_checks``, D2). The
measurement is the one of ``rsi6/results/dev_r_20261116/scripts/dev_r_d2.py``, the script as it
was run on 2026-11-16, whose outputs were not committed: the same order, seeds, budgets, arms and
summary. What differs is only where it reads and writes, so that the check can be repeated on a
machine that never held those outputs.

For the left-out category f in (jobshop, quadassign, pmedian): 8 development chains over the
registered ORDER without f's block and without bin packing (seeds 610000 + 1000 f + 100 j + k),
then relay, frozen and shuffled on f at the held-out budget (train 200, seeds
620000 + 1000 f + 10 j + s, s < 2), the three arms submitted as one batch interleaved pair by
pair. Measured: sigma-hat, tau-hat and the development effect; per chain, the library size and
the prior's concentration; the relay/frozen CPU ratio; the informative share by arm; and, per
acquisition, the prospective Spearman correlation of the rules dplus and dmean with the next
acquisition's per-cell confirmed-switch rate. The per-chain and per-acquisition values are
written out, so that the pre-written rules are applied to all 24 chains pooled and not to
summaries of summaries.

    python -m rsi6.open.dev_d2 <left-out category> --out DIR

``--out`` gets the scratch ledger (a copy of the committed ledger, extended by this check's
runs) and the summary. A stopped check started again with the same ``--out`` repeats at most one
chunk of runs. All arms of one category are measured by one process on one machine, so the CPU
ratio compares like with like; the machine is written into the summary.

``--smoke`` is a check of the plumbing and of nothing else: two chains, a tenth of the training
budget, seeds no development or registered run uses, files named ``smoke_*``. Its numbers mean
nothing and are not to be reported.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import platform
import shutil
import sys

os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("OMP_NUM_THREADS", "1")

import numpy as np

from rsi6.experiments import guard
from rsi6.kernel import ledger as ledgers
from rsi6.kernel.run import Cache
from rsi6.learner import design_r, designs, dispatch_extra
from rsi6.open import relay
from rsi6.open.relay_report import paired, productivity, spearman

LEFT_OUT = ("jobshop", "quadassign", "pmedian")
ORDER = ["jobshop"] * 3 + ["quadassign"] * 3 + ["pmedian"] * 3 + ["knapsack"] * 2
NAMES = ("relay", "frozen", "shuffled")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("category", choices=LEFT_OUT)
    parser.add_argument("--out", required=True)
    parser.add_argument("--smoke", action="store_true")
    args = parser.parse_args()
    f = args.category
    fi = LEFT_OUT.index(f)
    J = 2 if args.smoke else 8
    train = 20.0 if args.smoke else 200.0
    shift = 9000000 if args.smoke else 0                 # smoke seeds are no development or registered run's
    stem = ("smoke_" if args.smoke else "") + f"dev_r_d2n_{f}"
    os.makedirs(args.out, exist_ok=True)
    scratch = os.path.join(args.out, stem + ".jsonl")
    if guard.is_registered(scratch):
        raise SystemExit("development writes a scratch ledger, never a registered one")
    if not os.path.exists(scratch):
        shutil.copy(guard.MAIN, scratch)

    dispatch_extra.install()
    relay.wait_for_registered_drivers()
    ledger = ledgers.Ledger(scratch)
    cache = Cache(ledger)
    order = [c for c in ORDER if c != f]
    v = design_r.default()
    meta_b = {"train": train, "test_c": 2.0, "test_e": 1.0, "n_train": 16, "n_fresh": 24, "part": "A"}
    held_b = {"train": train, "test_c": 2.0, "test_e": 1.0, "n_train": 16, "n_fresh": 24}
    reg = {"version": v, "budgets": {"meta": meta_b, "retention": dict(meta_b, part="B")},
           "meta": {"chains": J, "chains_off": 0, "order": order, "seed_base": shift + 610000 + 1000 * fi,
                    "retention": {"chains": 0, "seed_base": 0, "plan": {}}}}
    if not ledger.select(type="r_stage_done", stage="meta"):
        relay.say = lambda *a: print(*a, flush=True)
        relay.run_meta(reg, cache, ledger)
        ledger.append({"type": "r_stage_done", "stage": "meta"})
    mem = relay.rebuild(ledger, reg)
    K = len(order)
    held_base = shift + 620000 + 1000 * fi
    seed_of = lambda j, s: held_base + 10 * j + s
    memory_of = {"relay": lambda j: mem["on"][j][K], "frozen": lambda j: None,
                 "shuffled": lambda j: design_r.shuffled(mem["on"][j][K], j)}
    jobs = [{"env": f, "version": v, "seed": seed_of(j, s), "budget": held_b, "memory": memory_of[name](j),
             "purpose": f"dev-d2:{name}:chain{j}"}
            for j in range(J) for s in range(2) for name in NAMES]
    got = relay.chunked(cache, jobs)
    arms = {name: got[k::3] for k, name in enumerate(NAMES)}
    chain_of = lambda seed: (seed - held_base) // 10
    out = {"left_out": f, "order": order, "accept": v["accept"], "version_digest": designs.digest(v), "chains": J,
           "smoke": bool(args.smoke),
           "machine": {"python": sys.version.split()[0], "numpy": np.__version__, "cpus": os.cpu_count(),
                       "platform": platform.platform(), "processor": _processor()}}
    for name in ("relay", "shuffled"):
        base = {r["seed"]: r for r in arms["frozen"]}
        d = {}
        for r in arms[name]:
            d.setdefault(chain_of(r["seed"]), []).append(r["acquired"] - base[r["seed"]]["acquired"])
        within = [np.std(x, ddof=1) for x in d.values() if len(x) > 1]
        sigma = float(np.sqrt(np.mean(np.square(within))))
        means = np.array([np.mean(d[j]) for j in sorted(d)])
        tau2 = max(0.0, float(means.var(ddof=1)) - (sigma ** 2) / 2)
        se = float(means.std(ddof=1) / math.sqrt(len(means)))
        out[f"{name} minus frozen"] = {"mean": float(means.mean()), "se": se, "sigma_hat": sigma, "tau_hat": math.sqrt(tau2),
                                       "chain_means": [float(x) for x in means],
                                       "pairs": [float(x) for j in sorted(d) for x in d[j]]}
    out["cpu_ratio_relay_over_frozen"] = paired(arms["relay"], arms["frozen"], chain_of)["cpu_ratio"]
    out["cpu_ratio_shuffled_over_frozen"] = paired(arms["shuffled"], arms["frozen"], chain_of)["cpu_ratio"]
    out["productivity"] = {name: productivity(rows) for name, rows in arms.items()}
    out["instances_scored_0"] = {name: int(sum(sum(1 for x in r["fresh_acquired"] if x == 0) for r in rows))
                                 for name, rows in arms.items()}
    relay_cfg = design_r.validate(v)["relay"]
    libs, conc, rho = [], [], {"dplus": [], "dmean": []}
    for j in range(J):
        final = mem["on"][j][K]
        pr = design_r.prior_from(final["entries"], relay_cfg) if final else None
        libs.append(len(pr["library"]) if pr else 0)
        if pr:
            p = np.exp(pr["w"]) / np.exp(pr["w"]).sum()
            conc.append(float(np.sort(p)[-3:].sum()))
        for k in range(1, K):
            m_k = mem["on"][j][k]
            nxt = [e for e in (mem["on"][j][k + 1] or {"entries": []})["entries"][len((m_k or {"entries": []})["entries"]):]
                   if e.get("kind") == design_r.KIND_STATS]
            if not m_k or not nxt:
                continue
            e = nxt[0]
            N, SW = np.asarray(e["N"]), np.asarray(e["SW"])
            keep = N >= 2
            if keep.sum() < 4:
                continue
            rate = SW[keep] / N[keep]
            for rule in rho:
                pr_k = design_r.prior_from(m_k["entries"], dict(relay_cfg, rule=rule))
                r_ = spearman(np.asarray(pr_k["w"])[keep], rate) if pr_k else None
                if r_ is not None:
                    rho[rule].append(r_)
    out["library_sizes"] = libs                                   # per chain
    out["prior_top3_mass"] = conc                                 # per chain
    out["prospective_spearman"] = rho                             # per acquisition (positions 1 to K-1 of every chain)
    gen = {}
    for s_ in ledger.select(type="r_memory"):
        gen.setdefault(s_["position"], []).append(cache.by_key[s_["run_key"]]["acquired"])
    out["generations"] = {k: float(np.mean(v_)) for k, v_ in sorted(gen.items())}
    json.dump(out, open(os.path.join(args.out, stem + ".json"), "w"), indent=1)
    print(json.dumps({k: v_ for k, v_ in out.items() if k not in ("generations",)}, indent=1))
    return 0


def _processor() -> str:
    try:
        for line in open("/proc/cpuinfo"):
            if line.startswith("model name"):
                return line.split(":", 1)[1].strip()
    except OSError:
        pass
    return platform.processor()


if __name__ == "__main__":
    sys.exit(main())
