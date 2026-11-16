"""Development runs of the discovery of open mechanisms, on source categories only.

    python -m rsi6.open.run_dev --ledger PATH [--mode recursive|frozen|uniform|shuffled]
                                [--lineages N] [--steps N] [--migrate N] [--envs a,b,c] [--seed N]

Nothing written by a development run is evidence: it is how the mechanism of discovery is
built and debugged. It refuses the registered ledgers and every category that is not in the
source pool.
"""
from __future__ import annotations

import argparse
import os
import shutil
import sys
import time

os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("OMP_NUM_THREADS", "1")

import numpy as np

from rsi6 import environments
from rsi6.experiments import guard
from rsi6.kernel import ledger as ledgers
from rsi6.kernel import roles
from rsi6.kernel.run import Cache
from rsi6.learner import designs
from rsi6.open import discovery


def say(*parts) -> None:
    print(time.strftime("%H:%M:%S"), *parts, flush=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ledger", required=True)
    parser.add_argument("--mode", default="recursive", choices=["recursive", "frozen", "uniform", "shuffled"])
    parser.add_argument("--lineages", type=int, default=2)
    parser.add_argument("--steps", type=int, default=20)
    parser.add_argument("--migrate", type=int, default=5)
    parser.add_argument("--envs", default="jobshop,knapsack,pmedian,quadassign")
    parser.add_argument("--seeds", default="1,2,3")
    parser.add_argument("--confirm", default="101,102")
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()
    if guard.is_registered(args.ledger):
        raise SystemExit("development runs use a scratch ledger")
    envs = args.envs.split(",")
    registered = ledgers.Ledger(guard.MAIN)
    for e in envs:
        if roles.effective_role(environments.load(e).category, registered) != "source":
            raise SystemExit(f"{e} is not a source category: development runs stay on the source pool")
    if not os.path.exists(args.ledger):                # a development ledger starts as a copy of the committed one: same roles, same lock
        shutil.copy(guard.MAIN, args.ledger)
    guard.single_writer(args.ledger)
    ledger = ledgers.Ledger(args.ledger)
    cache = Cache(ledger)
    seeds = [int(x) for x in args.seeds.split(",")]
    confirm = [int(x) for x in args.confirm.split(",")]
    rng = np.random.default_rng(args.seed)
    memo = {}
    start = designs.default("o")
    lineages = [discovery.Lineage(f"{args.mode}{k}", start, envs, seeds, confirm, cache, ledger,
                                  np.random.default_rng([args.seed, k]), mode=args.mode, memo=memo) for k in range(args.lineages)]
    say(f"start: score {lineages[0].parent_score:.4f} cpu {lineages[0].parent_cpu:.0f} on {envs}")
    for t in range(args.steps):
        for L in lineages:
            r = L.step()
            show = []
            for c in r["candidates"]:
                if c.get("key") is None:
                    show.append("-")
                elif "value" in c:
                    show.append(f"{c['screen']:+.3f}>{c['value']:+.3f}" + (f">{c['confirmation']:+.3f}" if "confirmation" in c else ""))
                else:
                    show.append(f"{c['screen']:+.3f}")
            say(f"{L.name} step {t}: parent {r['parent_score']:.4f}{' -> %.4f' % r['parent_score_after'] if r['accepted'] else ''}",
                " ".join(show), f"| library {r['library']} kd {r['knobs']['kd']}")
        if args.migrate and (t + 1) % args.migrate == 0 and len(lineages) > 1:
            discovery.migrate(lineages, rng, ledger)
    for L in lineages:
        say(f"{L.name}: final {L.parent_score:.4f} after {len(L.accepted)} acceptances", L.accepted)
    return 0


if __name__ == "__main__":
    sys.exit(main())
