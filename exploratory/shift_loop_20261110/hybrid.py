"""Hybrid shift loop: exploratory harness (report-only, outside the package).

The rsi5 engine is used unchanged. Around it:
  S  spec-space shifts: an element-wise or value-filter task is re-posed as an int -> element
     problem and its solution lifted back with map / filter.
  F  fusion in output bit-vector space: two partial solutions and a separating predicate from
     the engine's pools are merged into one `if` term. Switch "F" fuses everywhere, "f" only
     inside the int -> element sub-problems of S.
  C  constants abduced from the examples (differences, ratios, new output values, decision
     boundaries) and admitted as size-1 constants whose printed form is a base-language term.
  L  learned abstractions (lambda-term compression), inlined before any term leaves the engine.
  A  apoptosis: the search vocabulary of each space (element space, list space) can be cut to
     a kept subset of symbols.
  E  entropy: seeded random mutation of near-miss programs (a subterm replaced by another pool
     program of its type) after search and fusion fail, on a tenth of the budget.
  R  representation search: when S does not apply or fails, a tenth of the budget enumerates
     list programs A over the input; each A under which the outputs are the element-wise image
     of A(xs), or A(xs) filtered by a predicate on the value, is a re-representation; the first
     two get an int -> element sub-search, lifted as map f (A xs) or filter p (A xs).
Dream tasks (dream.py) are extra tasks with known answers that the driver composes from its
own verified programs; they travel to the workers like any public task.

Process layout as in rsi5.phase1: the guard is installed, the workers are forked before any
partition is loaded, they seal the loader packages and receive public examples only; the
driver holds the tasks and the frozen verifier (one query per task per run: a loop of n runs
puts up to n programs per task to the same hidden examples). The pool is an executor that
never replaces a worker; a worker forked after the loaders were imported refuses to search.
Budget unit: one engine candidate (a constructed term evaluated on its points); a fused or
lifted candidate checked by the reference interpreter also counts one. Not counted: the
bit-mask scan of fusion, the reference re-checks, and everything the driver does.

The engine ends a search at the first size level that adds no new behaviour. With a cut
vocabulary that happens at once (no size-2 program) although larger programs exist, so this
harness keeps the search going until PATIENCE levels in a row are empty. The engine file is
not changed; with the full vocabulary the rule never fires before the budget.
"""
from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor
import hashlib
import json
import multiprocessing
import os
import random
import sys
import time

from rsi5 import guard, partitions, probes
from rsi5.dsl.evaluator import evaluate as reference_evaluate
from rsi5.dsl.terms import Int, Lam, Prim, Var, apply, shift, term_from_dict, term_to_dict
from rsi5.dsl.types import Arrow, BOOL, INT, ListOf, Type, arrows, function_parts
from rsi5.dsl.vocabulary import VOCABULARIES, Vocabulary
import rsi5.engine.bottomup as bu
from rsi5.engine.closures import Fail, STEP_BUDGET, compile_term, run_closure
from rsi5.engine.oe import ERR

LIST_INT = ListOf(INT)
MAX_SIZE, STEPS, LAMBDA_DEPTH = 20, 2000, 2
CONST_RANGE = 64
FUSE_CAP = 3000

# ---- admitted abstractions and constants: inlined whenever a term is built -----------------------
ADMITTED: dict = {}          # name -> witness Term (closed, base language)
CONST_WITNESS: dict = {}     # int -> closed base-language Term


def beta(witness, arguments):
    """The witness applied to argument terms, beta-reduced (arguments live outside its binders)."""
    n = len(arguments)
    body = witness
    for _ in range(n):
        if body.tag != "lam":
            raise ValueError("witness has fewer binders than arguments")
        body = body.children[0]

    def visit(term, depth):
        tag = term.tag
        if tag == "var":
            index = term.value
            if index < depth:
                return term
            position = index - depth                 # 0 = innermost parameter = last argument
            if position >= n:
                raise ValueError("witness is not closed")
            return shift(arguments[n - 1 - position], depth)
        if tag == "lam":
            return Lam(term.value, visit(term.children[0], depth + 1))
        if tag == "app":
            return apply(visit(term.children[0], depth), visit(term.children[1], depth))
        return term
    return visit(body, 0)


# ---- an empty level is not the end of a cut vocabulary's programs ----------------------------------
PATIENCE = 6                 # empty levels in a row before a search counts as exhausted
_base_ensure = bu.Context.ensure


def _ensure(self, size):
    _base_ensure(self, size)
    engine = self.engine
    if self is engine.top:
        if all(context.added_at_level == 0 for context in engine.contexts):
            engine.empty_levels = getattr(engine, "empty_levels", 0) + 1
            if engine.empty_levels < PATIENCE:
                self.added_at_level = 1       # read by the engine's stop rule only
        else:
            engine.empty_levels = 0


bu.Context.ensure = _ensure

_base_term = bu.Expr.term.fget


_ASKED = {"depth": 0, "last": None}      # the last program whose term the engine asked for


def _term(self):
    _ASKED["depth"] += 1
    try:
        if self._term is None:
            if self.kind == "prim" and self.head in ADMITTED:
                self._term = beta(ADMITTED[self.head], [a.term for a in self.args])
            elif self.kind == "const" and type(self.head) is int and self.head in CONST_WITNESS:
                self._term = CONST_WITNESS[self.head]
            else:
                return _base_term(self)
        return self._term
    finally:
        _ASKED["depth"] -= 1
        if _ASKED["depth"] == 0:
            _ASKED["last"] = self


bu.Expr.term = property(_term)


def learned_in(*exprs) -> list:
    """Names of the admitted abstractions these engine programs are built with: what the search
    itself used, as opposed to what a finished term can be folded into afterwards."""
    found, stack = set(), [e for e in exprs if e is not None]
    while stack:
        expr = stack.pop()
        if expr.kind == "prim" and expr.head in ADMITTED:
            found.add(expr.head)
        if expr.args:
            stack.extend(a for a in expr.args if isinstance(a, bu.Expr))
    return sorted(found)


def _vector_of(witness):
    value, error = run_closure(compile_term(witness), ())
    if error is not None:
        raise ValueError(f"witness does not compile to a value: {error}")

    def one(*values):
        budget = [STEP_BUDGET]
        current = value
        try:
            for v in values:
                current = current(v, budget)
        except RecursionError:
            raise Fail("recursion")
        return current
    return bu._guarded(one)


def constant_table(base, limit=CONST_RANGE, max_size=7) -> dict:
    """Shortest base-language term for every integer in [-limit, limit], built from the base
    constants with add, sub and mul; deterministic."""
    best = {c: (1, Int(c)) for c in sorted(base)}
    by_size = {1: sorted(base)}
    for size in range(3, max_size + 1, 2):
        found = {}
        for left in range(1, size - 1, 2):
            right = size - 1 - left
            for a in by_size.get(left, ()):
                for b in by_size.get(right, ()):
                    for name, value in (("add", a + b), ("sub", a - b), ("mul", a * b)):
                        if -limit <= value <= limit and value not in best and value not in found:
                            found[value] = apply(Prim(name), best[a][1], best[b][1])
        for value in sorted(found):
            best[value] = (size, found[value])
        by_size[size] = sorted(found)
    return {value: term for value, (_, term) in best.items()}


# ---- C: constants from the examples ---------------------------------------------------------------
def abduce_constants(table=None, examples=None, limit=4) -> list:
    """Integers the examples point to. ``table`` is an element-wise x -> y table (ints or
    bools); ``examples`` are whole-task (inputs, output) pairs with list[int] input."""
    found = []

    def take(value):
        if type(value) is int and -CONST_RANGE <= value <= CONST_RANGE and value not in found:
            found.append(value)
    if table:
        pairs = sorted(table.items())
        numeric = all(type(y) is int for _, y in pairs)
        if numeric:
            differences = {y - x for x, y in pairs}
            if len(differences) == 1:
                take(differences.pop())
            ratios = {y // x for x, y in pairs if x != 0 and y % x == 0}
            if len(ratios) == 1 and all(x == 0 or y % x == 0 for x, y in pairs):
                take(ratios.pop())
            inputs = {x for x, _ in pairs}
            for value in sorted({y for _, y in pairs} - inputs):         # values the outputs introduce
                take(value)
        labels = sorted({(y if type(y) is bool else y) for _, y in pairs}, key=repr)
        if len(labels) == 2:                                             # decision boundaries
            for (x1, y1), (x2, y2) in zip(pairs, pairs[1:]):
                if y1 != y2:
                    take(x2)
                    take(x1)
    if examples:
        for inputs, output in examples:
            if isinstance(output, list) and all(type(v) is int for v in output):
                seen = set(inputs[0]) if isinstance(inputs[0], list) else {inputs[0]}
                for value in output:
                    if value not in seen:
                        take(value)
            elif type(output) is int and isinstance(inputs[0], list) and output not in inputs[0]:
                pass
    return found[:limit]


# ---- S: spec-space shifts ---------------------------------------------------------------------------
def element_table(examples):
    """x -> y if every output is the element-wise image of its input, else None."""
    table = {}
    for (xs,), ys in examples:
        if not isinstance(ys, list) or len(ys) != len(xs):
            return None
        for x, y in zip(xs, ys):
            if table.setdefault(x, y) != y or type(table[x]) is not type(y):
                return None
    return table or None


def filter_table(examples):
    """x -> kept? if every output is its input filtered by a predicate on the value, else None."""
    table = {}
    changed = False
    for (xs,), ys in examples:
        if not isinstance(ys, list):
            return None
        kept = set(ys)
        if [x for x in xs if x in kept] != ys:
            return None
        changed = changed or len(ys) != len(xs)
        for x in xs:
            if table.setdefault(x, x in kept) != (x in kept):
                return None
    return table if table and changed else None


# ---- F: fusion in output bit-vector space ---------------------------------------------------------
def fuse(engine, expected, output_type, limit=3):
    """`if c a b` candidates from the top context's pools: a matches where c holds, b elsewhere.
    Returns up to ``limit`` (size, c, a, b) tuples, smallest first."""
    top = engine.top
    n = len(expected)
    full = (1 << n) - 1
    best_term = {}
    for expr in top.pools.get(output_type, ()):
        mask = 0
        outputs = expr.outputs
        for i in range(n):
            value = outputs[i]
            if value is not ERR and value == expected[i] and type(value) is type(expected[i]):
                mask |= 1 << i
        if mask and (mask not in best_term or expr.size < best_term[mask].size):
            best_term[mask] = expr
    best_pred = {}
    for expr in top.pools.get(BOOL, ()):
        mask, usable = 0, True
        outputs = expr.outputs
        for i in range(n):
            value = outputs[i]
            if value is ERR:
                usable = False
                break
            if value:
                mask |= 1 << i
        if usable and 0 < mask < full and (mask not in best_pred or expr.size < best_pred[mask].size):
            best_pred[mask] = expr
    terms = sorted(best_term.items(), key=lambda kv: (kv[1].size, kv[1].ident))[:FUSE_CAP]
    preds = sorted(best_pred.items(), key=lambda kv: (kv[1].size, kv[1].ident))[:FUSE_CAP]
    found = []
    for truth, c in preds:
        rest = full & ~truth
        a = next((e for m, e in terms if m & truth == truth), None)
        if a is None:
            continue
        b = next((e for m, e in terms if m & rest == rest), None)
        if b is None:
            continue
        found.append((1 + c.size + a.size + b.size, c.ident, c, a, b))
    found.sort(key=lambda item: (item[0], item[1]))
    return [(size, c, a, b) for size, _, c, a, b in found[:limit]], len(terms), len(preds)


# ---- E: seeded mutation of near-miss programs -----------------------------------------------------
def mutants(engine, expected, output_type, rng, limit):
    """Up to ``limit`` terms: a near-miss program of the top context (at least half of the public
    outputs right) with one top-context subterm replaced by a random pool program of its type."""
    top = engine.top
    n = len(expected)
    scored = []
    for expr in top.pools.get(output_type, ()):
        outputs = expr.outputs
        hits = sum(1 for i in range(n) if outputs[i] is not ERR and outputs[i] == expected[i]
                   and type(outputs[i]) is type(expected[i]))
        if hits < n and 2 * hits >= n:
            scored.append((-hits, expr.size, expr.ident, expr))
    scored.sort(key=lambda item: item[:3])
    parents = [item[3] for item in scored[:8]]
    if not parents:
        return
    pools = {type_: list(entries) for type_, entries in top.pools.items()}

    def sites(expr, path=()):
        found = [(path, expr)] if path else []
        if expr.kind == "prim":
            for i, argument in enumerate(expr.args):
                if argument.kind != "lam":
                    found.extend(sites(argument, path + (i,)))
        return found

    def rebuild(expr, path, replacement):
        if not path:
            return replacement
        arguments = [rebuild(a, path[1:], replacement) if j == path[0] else a.term
                     for j, a in enumerate(expr.args)]
        if expr.head in ADMITTED:
            return beta(ADMITTED[expr.head], arguments)
        return apply(Prim(expr.head), *arguments)

    for _ in range(limit):
        parent = parents[rng.randrange(len(parents))]
        positions = sites(parent)
        if not positions:
            continue
        path, old = positions[rng.randrange(len(positions))]
        pool = pools.get(old.type)
        if not pool:
            continue
        new = pool[rng.randrange(len(pool))]
        if new is old:
            continue
        yield rebuild(parent, path, new.term)


def _fast_match(body, examples) -> bool:
    try:
        fn = compile_term(body)
    except (ValueError, KeyError):
        return False
    for inputs, expected in examples:
        value, error = run_closure(fn, tuple(reversed(inputs)), STEPS)
        if error is not None or value != expected or type(value) is not type(expected):
            return False
    return True


# ---- R: re-representations of the input found among the engine's own list programs ----------------
def preimages(engine, examples, output_type, limit=2):
    """(kind, pool program A, table, element type) for list programs A of the top context under
    which the task is element-wise (map) or a value filter. The bare input is left to S.
    Returns (candidates, number of programs tested)."""
    n = len(examples)
    expected = [output for _, output in examples]
    found, seen, tested = [], set(), 0
    for expr in engine.top.pools.get(LIST_INT, ()):
        if expr.kind == "var":
            continue
        values = expr.outputs[:n]
        if any(v is ERR for v in values):
            continue
        tested += 1
        pseudo = [((values[i],), expected[i]) for i in range(n)]
        table = element_table(pseudo)
        kind, element = "map", output_type.args[0]
        if table is not None and all(x == y and type(x) is type(y) for x, y in table.items()):
            continue                                   # A itself would be the answer; the engine checks that
        if table is None and output_type == LIST_INT:
            table, kind, element = filter_table(pseudo), "filter", BOOL
        if table is None or len(table) < 3:
            continue
        signature = (kind, tuple(sorted(table.items())))
        if signature in seen:
            continue
        seen.add(signature)
        found.append((kind, expr, table, element))
        if len(found) >= limit:
            break
    return found, tested


# ---- one task, in a worker ------------------------------------------------------------------------
_STATE = {"spec": None, "vocabulary": None, "spaces": None, "probes": None, "table": None}


def _restrict(vocabulary, keep):
    """The vocabulary cut to the kept symbols (primitive and abstraction names, 'int:<v>')."""
    if keep is None:
        return vocabulary
    keep = set(keep)
    primitives = tuple(p for p in vocabulary.primitives if p in keep)
    constants = tuple(c for c in vocabulary.integer_constants if f"int:{c}" in keep)
    admitted = {name: entry for name, entry in vocabulary.admitted.items() if name in keep}
    return Vocabulary(vocabulary.name, primitives, constants, vocabulary.boolean_constants, admitted)


def _init_worker():
    guard.install()
    guard.seal_task_data()
    _STATE["probes"] = probes.load()
    _STATE["late"] = guard.preloaded()


def _ready(_) -> int:
    return os.getpid()


def _install(spec):
    if _STATE["spec"] == spec["id"]:
        return
    for name in list(ADMITTED):
        bu.VECTOR.pop(name, None)
    ADMITTED.clear()
    vocabulary = VOCABULARIES[spec["vocabulary"]]
    for name, type_dict, witness_dict in spec["abstractions"]:
        witness = term_from_dict(witness_dict)
        ADMITTED[name] = witness
        bu.VECTOR[name] = _vector_of(witness)
        vocabulary = vocabulary.with_admitted(name, Type.from_dict(type_dict), witness)
    constants = [c for c in spec.get("constants", ()) if c not in vocabulary.integer_constants]
    _STATE["table"] = constant_table(VOCABULARIES[spec["vocabulary"]].integer_constants)
    for c in constants:
        CONST_WITNESS[c] = _STATE["table"][c]
    if constants:
        vocabulary = Vocabulary(vocabulary.name, vocabulary.primitives, vocabulary.integer_constants
                                + tuple(constants), vocabulary.boolean_constants, vocabulary.admitted)
    _STATE["vocabulary"] = vocabulary
    keep = spec.get("keep") or {}
    _STATE["spaces"] = {"elem": _restrict(vocabulary, keep.get("elem")),
                        "list": _restrict(vocabulary, keep.get("list"))}
    _STATE["spec"] = spec["id"]


def _with_constants(vocabulary, constants):
    table = _STATE["table"]
    extra = tuple(c for c in constants if c not in vocabulary.integer_constants and c in table)
    for c in extra:
        CONST_WITNESS[c] = table[c]
    if not extra:
        return vocabulary
    return Vocabulary(vocabulary.name, vocabulary.primitives, vocabulary.integer_constants + extra,
                      vocabulary.boolean_constants, vocabulary.admitted)


def _matches(term, examples) -> bool:
    for inputs, expected in examples:
        result = reference_evaluate(term, tuple(inputs), step_budget=STEPS)
        if not result.ok or result.value != expected:
            return False
    return True


def _search(vocabulary, examples, request, budget, use_fusion, entropy=None):
    """Engine search plus, if it ends without a match, one fusion pass and, with ``entropy``
    (a seeded random.Random), mutation of near misses on a tenth of the budget. Returns
    (term or None, candidates spent, route, fusion statistics)."""
    input_types, output_type = function_parts(request)
    engine = bu.Engine(vocabulary, max_size=MAX_SIZE, step_budget=STEPS, max_lambda_depth=LAMBDA_DEPTH)
    inputs = probes.inputs_for(input_types, _STATE["probes"])
    reserve = budget // 10 if entropy is not None else 0
    _ASKED["last"] = None
    result = engine.search(examples, request, inputs, budget - reserve)
    if result.term is not None:
        return result.term, result.candidates_to_solution, "search", {"used": learned_in(_ASKED["last"])}
    spent = result.candidates
    expected = [output for _, output in examples]
    if use_fusion and len(input_types) == 1:
        triples, n_terms, n_preds = fuse(engine, expected, output_type)
        for _, c, a, b in triples:
            spent += 1
            term = Lam(input_types[0], apply(Prim("if"), c.term, a.term, b.term))
            if _matches(term, examples):
                return term, spent, "fused", {"used": learned_in(c, a, b), "pools": (n_terms, n_preds)}
    if entropy is not None and len(input_types) == 1:
        for body in mutants(engine, expected, output_type, entropy, reserve):
            spent += 1
            if _fast_match(body, examples):
                term = Lam(input_types[0], body)
                if _matches(term, examples):
                    return term, spent, "mutated", {"used": None}
    return None, spent, None, None


def solve(job) -> dict:
    task, spec = job
    if _STATE.get("late"):
        raise RuntimeError("this worker was forked after these modules were imported and may hold "
                           f"hidden examples: {_STATE['late']}")
    _install(spec)
    switches = spec["components"]
    budget = spec["budget"]
    request = Type.from_dict(task.request)
    input_types, output_type = function_parts(request)
    examples = task.examples
    record = {"name": task.name, "term": None, "route": None, "candidates": 0, "to_solution": None,
              "constants": [], "used": None}
    started = time.perf_counter()
    spent = 0
    spaces = _STATE["spaces"]
    entropy = None
    if switches.get("E"):
        seed = hashlib.sha256(f"{spec.get('seed', 0)}|{task.name}".encode()).hexdigest()
        entropy = random.Random(seed)
    listy = len(input_types) == 1 and input_types[0] == LIST_INT and output_type.tag == "list"
    shifts = []
    if switches.get("S") and listy:
        table = element_table(examples)
        if table is not None and all(x == y and type(x) is type(y) for x, y in table.items()):
            table = None                              # the identity: the direct route has it at once
            listy = False
        if table is not None:
            shifts.append(("map", table, output_type.args[0]))
        elif listy and output_type == LIST_INT:
            table = filter_table(examples)
            if table is not None:
                shifts.append(("filter", table, BOOL))
    for kind, table, element in shifts:
        sub_examples = [((x,), y) for x, y in sorted(table.items())]
        vocabulary = spaces["elem"]
        if switches.get("C"):
            constants = abduce_constants(table=table)
            record["constants"] = constants
            vocabulary = _with_constants(vocabulary, constants)
        term, used, route, how = _search(vocabulary, sub_examples, Arrow(INT, element), budget // 2,
                                         switches.get("F") or switches.get("f"), entropy)
        spent += used if term is None else 0
        if term is not None:
            lifted = Lam(LIST_INT, apply(Prim(kind), term, Var(0)))
            if _matches(lifted, examples):
                record.update(term=term_to_dict(lifted), route=f"{kind}+{route}", to_solution=spent + used,
                              used=how["used"])
                spent += used
                break
            spent += used
    if record["term"] is None and switches.get("R") and len(input_types) == 1 \
            and input_types[0] == LIST_INT and output_type.tag == "list":
        scan = min(budget // 10, max(0, budget - spent) // 4)
        engine = bu.Engine(spaces["list"], max_size=MAX_SIZE, step_budget=STEPS, max_lambda_depth=LAMBDA_DEPTH)
        _ASKED["last"] = None
        scanned = engine.search(examples, request, probes.inputs_for(input_types, _STATE["probes"]), scan)
        if scanned.term is not None:
            record.update(term=term_to_dict(scanned.term), route="search",
                          to_solution=spent + scanned.candidates_to_solution, used=learned_in(_ASKED["last"]))
            spent += scanned.candidates_to_solution
        else:
            spent += scanned.candidates
            candidates, tested = preimages(engine, examples, output_type)
            spent += tested
            share = max(0, budget - spent) // 3
            for kind, expr, table, element in candidates:
                sub_examples = [((x,), y) for x, y in sorted(table.items())]
                vocabulary = spaces["elem"]
                if switches.get("C"):
                    vocabulary = _with_constants(vocabulary, abduce_constants(table=table))
                term, used, route, how = _search(vocabulary, sub_examples, Arrow(INT, element), share,
                                                 switches.get("F") or switches.get("f"), entropy)
                if term is not None:
                    lifted = Lam(LIST_INT, apply(Prim(kind), term, expr.term))
                    if _matches(lifted, examples):
                        both = None if how["used"] is None else sorted(set(how["used"]) | set(learned_in(expr)))
                        record.update(term=term_to_dict(lifted), route=f"re+{kind}+{route}",
                                      to_solution=spent + used, used=both)
                        spent += used
                        break
                spent += used
    if record["term"] is None:
        vocabulary = spaces["list"]
        if switches.get("C"):
            constants = abduce_constants(examples=examples) if len(input_types) == 1 else []
            record["constants"] = record["constants"] or constants
            vocabulary = _with_constants(vocabulary, constants)
        term, used, route, how = _search(vocabulary, examples, request, max(0, budget - spent),
                                         switches.get("F"), entropy)
        if term is not None:
            record.update(term=term_to_dict(term), route=route, to_solution=spent + used, used=how["used"])
        spent += used
    record["candidates"] = spent
    record["seconds"] = round(time.perf_counter() - started, 2)
    return record


# ---- the driver -----------------------------------------------------------------------------------
class Harness:
    def __init__(self, workers: int, partition_names):
        guard.install()
        if guard.loader_modules():
            raise RuntimeError("fork the workers before any loader is imported")
        self.pool = ProcessPoolExecutor(workers, mp_context=multiprocessing.get_context("fork"),
                                        initializer=_init_worker)
        list(self.pool.map(_ready, range(workers)))          # the executor forks on first use
        from rsi5.verifier import FrozenVerifier
        self.tasks = {name: partitions.load(name) for name in partition_names}
        self.verifiers = {name: FrozenVerifier(tasks, step_budget=STEPS) for name, tasks in self.tasks.items()}
        self.public = {name: [partitions.public_view(t) for t in tasks] for name, tasks in self.tasks.items()}
        self.default = tuple(self.tasks)                 # a partition added later runs only when named
        self.runs = 0

    def add_partition(self, name: str, tasks, public) -> None:
        """Tasks made by the driver after the workers were forked (they need ``name``, ``examples``
        and ``hidden``) with their public views. They are run only when ``run`` names the partition."""
        from rsi5.verifier import FrozenVerifier
        if name in self.tasks:
            raise ValueError(f"partition {name!r} exists")
        self.tasks[name] = list(tasks)
        self.verifiers[name] = FrozenVerifier(self.tasks[name], step_budget=STEPS)
        self.public[name] = list(public)

    def close(self):
        self.pool.shutdown(wait=False, cancel_futures=True)

    def run(self, spec, partition_names=None, dreams=(), only=None) -> dict:
        """One generation: every task of the named partitions at spec['budget']; verdicts from the
        frozen verifier (one query per task per run). ``dreams`` are (public task, check examples)
        pairs made by the driver; their verdict is the check examples, and they come back under
        the key 'dream'. ``only`` (a set of 'partition/task name' keys) restricts the run to those
        tasks of the named partitions; the others are not run and have no row."""
        self.runs += 1
        spec = dict(spec, id=f"{spec.get('label', 'run')}#{self.runs}")
        names = list(partition_names if partition_names is not None else self.default)
        chosen = {name: [task for task in self.public[name] if only is None or f"{name}/{task.name}" in only]
                  for name in names}
        jobs = [(task, spec) for name in names for task in chosen[name]]
        jobs += [(task, spec) for task, _ in dreams]
        records = list(self.pool.map(solve, jobs, chunksize=1))
        out, cursor = {}, 0
        if dreams:
            rows = records[len(records) - len(dreams):]
            for row, (_, check) in zip(rows, dreams):
                term = term_from_dict(row["term"]) if row["term"] is not None else None
                row["solved"] = term is not None and _matches(term, check)
                row["program"] = str(term) if term is not None else None
            out["dream"] = rows
        for name in names:
            rows = records[cursor:cursor + len(chosen[name])]
            cursor += len(rows)
            for row in rows:
                term = term_from_dict(row["term"]) if row["term"] is not None else None
                row["solved"] = bool(self.verifiers[name].verify(row["name"], term, generation=self.runs).verdict)
                row["program"] = str(term) if term is not None else None
            out[name] = rows
        return out


def summary(result: dict) -> dict:
    return {name: sum(r["solved"] for r in rows) for name, rows in result.items() if name != "dream"}


def registered(vocabulary: str, budget: int, partition_names) -> dict:
    """Solved counts of the registered engine at ``budget``, read off its 10^6 run."""
    out = {}
    for name in partition_names:
        data = json.load(open(f"rsi5/results_p1/{vocabulary}_{name}.json"))
        if budget > data["plan"]["budget"]:
            raise ValueError(f"the registered run stopped at {data['plan']['budget']} candidates per task; "
                             f"nothing is known at {budget}")
        records = data["records"]
        out[name] = sum(1 for r in records if r["solved"] and r["candidates_to_solution"] <= budget)
    return out


ALL = ("train", "near", "validation", "far", "far2", "fresh1", "fresh2", "compose24")
LEARN = ("train", "near")
HELD_OUT = ("validation", "far", "far2", "fresh1", "fresh2", "compose24")


def spec_of(label, budget, components="", abstractions=(), constants=(), vocabulary="restored",
            keep=None, seed=0) -> dict:
    return {"label": label, "budget": budget, "vocabulary": vocabulary,
            "components": {c: True for c in components},
            "abstractions": list(abstractions), "constants": list(constants), "keep": keep, "seed": seed}


if __name__ == "__main__":
    budget = int(sys.argv[1])
    variants = sys.argv[2].split(",")              # e.g. "-,S,SC,SF,SCF"
    out_path = sys.argv[3]
    workers = int(sys.argv[4]) if len(sys.argv) > 4 else 3
    harness = Harness(workers, ALL)
    report = {"budget": budget, "registered": registered("restored", budget, ALL), "variants": {}}
    print("registered restored at", budget, report["registered"], "total", sum(report["registered"].values()), flush=True)
    for variant in variants:
        components = "" if variant == "-" else variant
        started = time.perf_counter()
        result = harness.run(spec_of(variant, budget, components))
        counts = summary(result)
        routes = {}
        for rows in result.values():
            for r in rows:
                if r["solved"]:
                    routes[r["route"]] = routes.get(r["route"], 0) + 1
        rejected = sum(1 for rows in result.values() for r in rows if r["term"] is not None and not r["solved"])
        report["variants"][variant] = {"counts": counts, "routes": routes, "rejected": rejected, "records": result}
        print(f"{variant:5s}", counts, "total", sum(counts.values()), "| held-out", sum(counts[n] for n in HELD_OUT),
              "| learn", sum(counts[n] for n in LEARN), "| routes", routes, "| rejected", rejected,
              "|", round(time.perf_counter() - started), "s", flush=True)
    harness.close()
    json.dump(report, open(out_path, "w"), indent=1)
