"""Exploratory, report-only: one representation shift on FRESH-1 (an exposed partition).
A task whose public outputs are element-wise images of its inputs is re-posed as an
int -> element problem (spec space), solved by the unchanged engine, and lifted back to
map (lambda x. body) xs. Verdicts come from the frozen verifier, one query per task."""
import json, sys, time
from rsi5 import partitions, probes
from rsi5.dsl.terms import Lam, Prim, Var, apply
from rsi5.dsl.types import Arrow, INT, BOOL, ListOf, function_parts
from rsi5.dsl.vocabulary import VOCABULARIES
from rsi5.engine.bottomup import Engine
from rsi5.verifier import FrozenVerifier

BUDGET = int(sys.argv[1]) if len(sys.argv) > 1 else 100_000
tasks = partitions.load("fresh1")
verifier = {v: FrozenVerifier(tasks, step_budget=2000) for v in VOCABULARIES}
probe_set = probes.load()
registered = {v: {r["name"]: r for r in json.load(open(f"rsi5/results_p1/{v}_fresh1.json"))["records"]}
              for v in VOCABULARIES}

def elementwise(task):
    """x -> y table if every public output is the element-wise image of its input, else None."""
    request = partitions.request_type(task)
    inputs, output = function_parts(request)
    if len(inputs) != 1 or inputs[0] != ListOf(INT) or output.tag != "list":
        return None
    table = {}
    for (xs,), ys in task.examples:
        if not isinstance(ys, list) or len(ys) != len(xs):
            return None
        for x, y in zip(xs, ys):
            if table.setdefault(x, y) != y:
                return None
    return (output.args[0], table) if table else None

rows = []
for task in tasks:
    shaped = elementwise(task)
    row = {"name": task.name, "map_shaped": shaped is not None}
    if shaped is not None:
        element, table = shaped
        examples = [((x,), y) for x, y in sorted(table.items())]
        row["points"] = len(examples)
        for vname, vocabulary in VOCABULARIES.items():
            engine = Engine(vocabulary, max_size=20, step_budget=2000, max_lambda_depth=2)
            started = time.perf_counter()
            result = engine.search(examples, Arrow(INT, element), probes.inputs_for((INT,), probe_set), BUDGET)
            solved, program = False, None
            if result.term is not None:
                lifted = Lam(ListOf(INT), apply(Prim("map"), result.term, Var(0)))
                solved = bool(verifier[vname].verify(task.name, lifted, generation=0).verdict)
                program = str(result.term)
            row[vname] = {"match": result.term is not None, "solved": solved, "candidates": result.candidates_to_solution,
                          "program": program, "seconds": round(time.perf_counter() - started, 1)}
    for vname in VOCABULARIES:
        r = registered[vname][task.name]
        row.setdefault("registered", {})[vname] = r["candidates_to_solution"] if r["solved"] else None
    rows.append(row)
json.dump(rows, open(sys.argv[2], "w"), indent=1)
shaped = [r for r in rows if r["map_shaped"]]
print("FRESH-1 tasks:", len(rows), "| element-wise shaped on public examples:", len(shaped), "| budget per sub-problem:", BUDGET)
for r in shaped:
    def cell(v):
        c = r[v]
        return f"{c['candidates']:>7}" + ("" if c["solved"] else "✗") if c["match"] else "      —"
    def reg(v):
        c = r["registered"][v]
        return f"{c:>8}" if c is not None else "       —"
    print(f"{r['name'][:46]:46s} pts {r['points']:2d} | shifted: orig {cell('original')} rest {cell('restored')} | registered@1e6: orig {reg('original')} rest {reg('restored')}")
for v in VOCABULARIES:
    solved = [r for r in shaped if r[v]["solved"]]
    for b in (1000, 10000, 100000):
        if b <= BUDGET:
            print(v, f"shifted solves within {b:>6}:", sum(1 for r in solved if r[v]["candidates"] <= b), "of", len(shaped), "shaped tasks")
    reg5 = sum(1 for r in shaped if r["registered"][v] is not None and r["registered"][v] <= 100000)
    reg6 = sum(1 for r in shaped if r["registered"][v] is not None)
    print(v, "registered engine on the same shaped tasks: at 1e5", reg5, "| at 1e6", reg6, "| rejected matches after the shift:", sum(1 for r in shaped if r[v]["match"] and not r[v]["solved"]))
