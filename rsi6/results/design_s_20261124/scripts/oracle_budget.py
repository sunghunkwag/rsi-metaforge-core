"""Development diagnostic (scratch, no ledger): does the adopted version acquire more when the training budget is larger?
If not, a category is limited by what a weight vector can express, not by the search."""
import json, os, sys, multiprocessing
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1"); os.environ.setdefault("OMP_NUM_THREADS", "1")
from rsi6.kernel.run import measure, BUDGET
from rsi6.learner import designs

def one(job):
    r = measure(job)["record"]
    return {"env": r["env"], "seed": r["seed"], "train": r["budget"]["train"], "untrained": r["untrained"], "acquired": r["acquired"],
            "gain": r["gain"], "learned": r["report"].get("learned"), "iterations": r["report"].get("iterations"),
            "cpu": r["cpu"]["acquire"] + r["cpu"]["apply"], "used": r["units"]["train_used"] / r["units"]["train_limit"]}

if __name__ == "__main__":
    out, spec = sys.argv[1], json.loads(sys.argv[2])          # {"category": [[budgets], n_seeds], ...}
    version = designs.validate(dict(designs.default("a"), **{"model.batch": 2}))
    jobs = [{"env": c, "version": version, "seed": 739900 + s, "budget": dict(BUDGET, train=float(b)), "purpose": "dev-oracle"}
            for c, (budgets, n) in spec.items() for b in budgets for s in range(1, n + 1)]
    with multiprocessing.get_context("fork").Pool(2) as pool:
        rows = []
        for row in pool.imap_unordered(one, jobs, chunksize=1):
            rows.append(row)
            json.dump(rows, open(out, "w"), indent=0)
    print("done", len(rows))
