#!/usr/bin/env python3
"""Phase J2 measurement (spec instrument; see docs/ISA_EXTENSION_SPEC.md §3b, §8).

Extended-ISA re-encoding MDL over the frozen Phase G Track 2 archive, plus
the extended-ISA reachability preview for the wall train vectors, under the
PROPOSED primitive set {BCAST(60), ZGT(61)}.

Instrument definition (frozen with the spec):

  For every elite e in the frozen Phase G archive (SHA-verified load),
  expand its surface tokens with the archive's own vocabulary macros
  (100 -> [4,4,25], 103 -> [100,100,25]) and execute on the 20 frozen
  TRAIN_INPUTS. Elites that crash or leave a non-single-int stack on any
  train input are excluded (counted). behavior(e) = the 20-output vector.

  Shortest-program tables are built by the runtime's own untruncated
  observational-equivalence enumeration (build_enum_table) at surface_max=6
  for four vocabularies: base (34 ops), base+BCAST, base+ZGT,
  base+BCAST+ZGT. For elite e and vocabulary V:
      len_V(e) = min(expanded_len(e), len(table_V.solutions[behavior(e)]))
                 (table term only if behavior(e) is reachable in table_V)
  saving_P(e) = len_base(e) - len_ext_P(e)   (>= 0 by construction)
  MDL delta for primitive set P = sum_e saving_P(e) - defcost(P),
  defcost(P) = 2 per primitive (declared convention: one naming token plus
  one catalog entry; the frozen Phase E macro accounting defines defcost
  only for base-op bodies, which new primitives by definition lack).

Under the frozen Phase E greedy macro accounting itself the delta is 0 by
construction (no base-op body exists to match), reported in the spec as
exactly that.

Deterministic: no randomness; archive load is SHA-verified; enumeration is
the runtime's own deterministic engine. Read-only on the repository; the
runtime module is mutated in-memory only (extension registries of this
process).

Usage (from the repository root):
    python3 docs/measure_mdl_extension_J.py > docs/mdl_extension_J.json
Committed output: docs/mdl_extension_J.json (progress lines go to stderr)
"""
import sys, json, gc
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import rsi_levels_metaforge_unified as M

def _zgt_impl(stack, inp):
    b = M._pop_list(stack)
    a = M._pop_list(stack)
    n = min(len(a), len(b))
    M._push(stack, tuple(1 if a[i] > b[i] else 0 for i in range(n)))

BCAST_ID, ZGT_ID = 60, 61
M.EXT_IMPL[BCAST_ID] = M.DORMANT_CAPABILITY_CATALOG["BCAST"].impl
M.EXT_TYPES[BCAST_ID] = (("i", "l"), ("l",))
M.EXT_IMPL[ZGT_ID] = _zgt_impl
M.EXT_TYPES[ZGT_ID] = (("l", "l"), ("l",))

BASE = list(range(M.N_BASE_OPS))
VOCABS = {
    "base": BASE,
    "base+BCAST": BASE + [BCAST_ID],
    "base+ZGT": BASE + [ZGT_ID],
    "base+BCAST+ZGT": BASE + [BCAST_ID, ZGT_ID],
}
SURFACE_MAX = 6
CLASS_CAP = 2_500_000

# --- 1. load frozen Phase G archive (SHA-verified by the runtime loader) ----
doc = M.anchor_load_archive_g()
vocab_macros = {int(k): tuple(v) for k, v in
                doc["meta"]["vocabulary_macros"].items()}

def expand(tokens):
    out = []
    for t in tokens:
        if t in vocab_macros:
            out.extend(expand(vocab_macros[t]))
        else:
            out.append(t)
    return tuple(out)

def train_vector(expanded):
    vec = []
    for xs in M.TRAIN_INPUTS:
        stack = []
        inp = tuple(int(v) for v in xs)
        try:
            for t in expanded:
                M.step_op(stack, t, inp)
        except M.VMCrash:
            return None
        if len(stack) != 1 or not isinstance(stack[0], int):
            return None
        vec.append(stack[0])
    return tuple(vec)

elites = []
excluded = 0
for cell, entry in sorted(doc["archive"].items()):
    exp = expand(entry["tokens"])
    vec = train_vector(exp)
    if vec is None:
        excluded += 1
        continue
    elites.append({"cell": cell, "expanded_len": len(exp), "vec": vec})

# --- 2. shortest-program tables per vocabulary ------------------------------
wall_targets = M.wall_targets()
tables = {}
for name, vocab in VOCABS.items():
    tab = M.build_enum_table(M.SearcherState(), surface_max=SURFACE_MAX,
                             class_cap=CLASS_CAP, vocab_override=vocab)
    tables[name] = {
        "lens": {vec: len(toks) for vec, toks in tab.solutions.items()},
        "walls_found": {tid: {"length": len(tab.solutions[tv]),
                              "tokens": list(tab.solutions[tv])}
                        for tid, tv in wall_targets.items()
                        if tv in tab.solutions},
        "classes_per_len": list(tab.classes_per_len),
        "truncated": tab.truncated,
        "solutions_count": len(tab.solutions),
    }
    del tab
    gc.collect()
    print(f"[table {name}] classes_per_len={tables[name]['classes_per_len']}"
          f" truncated={tables[name]['truncated']}"
          f" walls_found={sorted(tables[name]['walls_found'])}",
          file=sys.stderr, flush=True)

# --- 3. per-elite savings ----------------------------------------------------
base_lens = tables["base"]["lens"]
report = {"archive": {"n_elites_total": len(doc["archive"]),
                      "n_excluded_crash_or_nonint": excluded,
                      "n_scored": len(elites)},
          "instrument": {"surface_max": SURFACE_MAX, "class_cap": CLASS_CAP,
                         "defcost_per_primitive": 2,
                         "train_inputs": len(M.TRAIN_INPUTS)},
          "tables": {n: {k: v for k, v in t.items() if k != "lens"}
                     for n, t in tables.items()},
          "mdl": {}}

for name in ("base+BCAST", "base+ZGT", "base+BCAST+ZGT"):
    ext_lens = tables[name]["lens"]
    total_saving = 0
    improved = []
    for e in elites:
        b = e["expanded_len"]
        if e["vec"] in base_lens:
            b = min(b, base_lens[e["vec"]])
        x = b
        if e["vec"] in ext_lens:
            x = min(x, ext_lens[e["vec"]])
        s = b - x
        if s > 0:
            improved.append({"cell": e["cell"], "saving": s,
                             "from": b, "to": x})
            total_saving += s
    n_prims = name.count("+")
    defcost = 2 * n_prims
    report["mdl"][name] = {
        "total_saving_tokens": total_saving,
        "defcost": defcost,
        "net": total_saving - defcost,
        "mdl_positive": total_saving > defcost,
        "elites_improved": len(improved),
        "improved_detail": improved[:20],
    }

print(json.dumps(report, indent=2, sort_keys=True))
