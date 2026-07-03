#!/usr/bin/env python3
"""Phase J2 measurement (spec instrument; see docs/ISA_EXTENSION_SPEC.md).

Verifies the designer-supplied extended-ISA expressibility witnesses for the
four certified walls under the PROPOSED primitive set {BCAST(60), ZGT(61)},
and performs the requirement-(iii) non-degeneracy check: no OPEN designer
task's train vector is reachable at expanded length <= 2 in the extended
vocabulary.

Read-only on the repository; the runtime module is mutated in-memory only
(extension registries of this process). Deterministic: no randomness.

Usage (from the repository root):
    python3 docs/measure_witnesses_J.py > docs/witnesses_J.json
Committed output: docs/witnesses_J.json
"""
import sys, json, itertools
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import rsi_levels_metaforge_unified as M

# --- proposed primitive semantics (spec §1; in-memory grant, this process) --
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

VOCAB = list(range(M.N_BASE_OPS)) + [BCAST_ID, ZGT_ID]

# --- designer witnesses (spec §7; expanded base+ext token sequences) --------
WITNESSES = {
    # count_above_threshold: RED_ADD(ZGT(xs, BCAST(3, xs)))
    "T29": (4, 5, 3, 60, 61, 29),
    # argmax_index: RED_ADD(ZGT(BCAST(RED_MAX(xs), xs), SCAN_MAX(xs)))
    "T30": (4, 5, 30, 60, 4, 27, 61, 29),
    # first_greater_than_previous:
    # m = ZGT(TAIL(xs), xs); SELECT(n - RED_ADD(SCAN_MAX(m)), -1, RED_ADD(m))
    "T31": (4, 20, 4, 61, 5, 27, 29, 4, 16, 6, 10, 6, 0, 1, 10, 6, 29, 33),
    # longest_increasing_run:
    # m = ZGT(TAIL(xs), xs); s = SCAN_ADD(m); w = ones - m;
    # r = s - SCAN_MAX(s*w); RED_MAX(r) + 1
    "T32": (4, 20, 4, 61, 5, 5, 1, 60, 6, 24, 6, 28, 6, 8, 25, 27, 24, 30, 1, 9),
}

def run_prog(tokens, xs):
    stack = []
    inp = tuple(int(v) for v in xs)
    for t in tokens:
        M.step_op(stack, t, inp)
    if len(stack) != 1 or not isinstance(stack[0], int):
        raise M.VMCrash("bad_terminal_state")
    return stack[0]

tasks = {t.tid: t for t in M.build_sealed_tasks()}
out = {"witnesses": {}, "nondegeneracy_le2": {}}

for tid, toks in sorted(WITNESSES.items()):
    task = tasks[tid]
    fn = lambda xs, _t=toks: run_prog(_t, xs)
    train_ok = all(fn(list(xs)) == y for xs, y in task.train_pairs)
    hold_ok = task.holdout_gate(fn)
    cf_ok = task.cf_gate(fn)
    out["witnesses"][tid] = {
        "name": M.TASK_NAME_BY_TID[tid],
        "tokens": list(toks),
        "expanded_len": len(toks),
        "uses_BCAST": BCAST_ID in toks,
        "uses_ZGT": ZGT_ID in toks,
        "designer_supplied": True,
        "counts_as_solved": False,
        "gates": {"train": train_ok, "holdout": hold_ok, "cf": cf_ok},
    }

# --- non-degeneracy: no OPEN task solvable at expanded length <= 2 ----------
OPEN_TIDS = ("T18", "T21", "T22", "T29", "T30", "T31", "T32")
targets = {tid: M.task_target_vector(tasks[tid]) for tid in OPEN_TIDS}
hits = {}
n_programs = 0
for L in (1, 2):
    for prog in itertools.product(VOCAB, repeat=L):
        n_programs += 1
        vec = []
        ok = True
        for xs, _y in tasks["T29"].train_pairs:  # same TRAIN_INPUTS for all
            try:
                vec.append(run_prog(prog, xs))
            except M.VMCrash:
                ok = False
                break
        if not ok:
            continue
        vec = tuple(vec)
        for tid, tv in targets.items():
            if vec == tv:
                hits.setdefault(tid, []).append(list(prog))
out["nondegeneracy_le2"] = {
    "vocab_size": len(VOCAB),
    "programs_enumerated": n_programs,
    "open_task_hits_at_le2": hits,   # must be {}
}

print(json.dumps(out, indent=2, sort_keys=True))
