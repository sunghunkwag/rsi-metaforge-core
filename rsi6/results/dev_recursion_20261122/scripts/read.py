"""The reading of PREDICTION.md.   python3 -I read.py DIR --out FILE.json"""
import argparse, glob, json, os, random, statistics as st

def quantile(xs, q):
    xs = sorted(xs); pos = q * (len(xs) - 1); lo = int(pos); hi = min(lo + 1, len(xs) - 1)
    return xs[lo] + (xs[hi] - xs[lo]) * (pos - lo)

parser = argparse.ArgumentParser()
parser.add_argument("directory"); parser.add_argument("--out", required=True)
parser.add_argument("--boot", type=int, default=10000); parser.add_argument("--seed", type=int, default=20261123)
args = parser.parse_args()
docs = {}
for path in sorted(glob.glob(os.path.join(args.directory, "**", "recursion_*.json"), recursive=True)):
    d = json.load(open(path))
    if not d.get("smoke"):
        docs[d["k"]] = d
ks = sorted(docs)
arms = ("recursive", "frozen", "random")
value = {a: [docs[k]["arms"][a].get("assessment", {}).get("value", 0.0) for k in ks] for a in arms}
rng = random.Random(args.seed)
def boot(xs):
    means = [st.fmean(rng.choice(xs) for _ in xs) for _ in range(args.boot)]
    return {"mean": st.fmean(xs), "q05": quantile(means, 0.05), "q95": quantile(means, 0.95)}
out = {"repetitions": ks, "arms": {}, "differences": {}}
for a in arms:
    rows = [docs[k]["arms"][a] for k in ks]
    out["arms"][a] = dict(boot(value[a]), nominees=sum(1 for r in rows if r["nominee"] is not None),
                          learned_something=sum(1 for r in rows if r["learned_changes"]),
                          rounds=sorted(r["iterations"] for r in rows), values=value[a],
                          nominee_changes=[sorted(r.get("nominee_changes") or {}) for r in rows])
for a, b in (("recursive", "frozen"), ("recursive", "random"), ("frozen", "random")):
    out["differences"][f"{a}-{b}"] = boot([x - y for x, y in zip(value[a], value[b])])
D = out["differences"]["recursive-frozen"]
out["signal"] = bool(D["q05"] > 0 and out["arms"]["recursive"]["q05"] > 0)
out["neither_produced_a_step"] = bool(all(out["arms"][a]["q05"] <= 0 for a in arms))
json.dump(out, open(args.out, "w"), indent=1, sort_keys=True)
print(f"repetitions {len(ks)}")
for a in arms:
    r = out["arms"][a]
    print(f"{a:9s} mean value {r['mean']:+.4f} (5 % point {r['q05']:+.4f}, 95 % {r['q95']:+.4f}) nominees {r['nominees']}/{len(ks)} learned something {r['learned_something']}/{len(ks)} rounds {r['rounds'][0]}-{r['rounds'][-1]}")
for name, r in out["differences"].items():
    print(f"{name:18s} {r['mean']:+.4f} (5 % point {r['q05']:+.4f}, 95 % {r['q95']:+.4f})")
print("signal:", out["signal"], "| neither improver produced a step:", out["neither_produced_a_step"])
