"""Shared fixtures for the swarm tests: a working copy of the generation-0 tree and planted triples."""
import json
import random
import shutil
from pathlib import Path

from swarm.kernel import checker_lang
from swarm.kernel.runtime import KernelRuntime

ROOT = Path(__file__).resolve().parents[2]
TREE = ROOT / "swarm" / "builder" / "mutable"


def copy_tree(destination: Path) -> Path:
    shutil.copytree(TREE, destination, ignore=shutil.ignore_patterns("__pycache__", "*.pkl"))
    return destination


def distinct_inputs(seed: int, count: int, length=(1, 6), values=(0, 9)) -> list:
    rng = random.Random(seed)
    found, seen = [], set()
    while len(found) < count:
        value = [rng.randint(*values) for _ in range(rng.randint(*length))]
        if tuple(value) not in seen:
            seen.add(tuple(value))
            found.append(value)
    return found


def triple(lineage, witness, checker, inputs, public=8):
    outputs = [checker_lang.run(witness, [x]).value for x in inputs]
    instances = [{"inputs": [x], "output": o} for x, o in zip(inputs, outputs)]
    return {"lineage": lineage, "witness": witness, "checker": checker,
            "examples": instances[:public], "hidden": instances[public:]}


def equality_checker(witness):
    return ["lambda", ["x", "y"], ["=", "y", [witness, "x"]]]


MAP_PLUS_ONE = ["lambda", ["x"], ["map", ["lambda", ["v"], ["+", "v", 1]], "x"]]
SORT = ["lambda", ["x"], ["sort", "x"]]


class Kernel:
    """Every kernel object wired over a working directory (through the kernel runtime)."""

    def __init__(self, workdir: Path, b_inst: int = 100, horizon: int = 5):
        self.workdir = Path(workdir)
        self.live = self.workdir / "live"
        self.tree = copy_tree(self.live / "mutable")
        self.runtime = KernelRuntime(self.workdir, b_inst=b_inst, probe_seed=11, horizon=horizon)
        for name in ("meter", "executor", "ledger", "vault", "archive", "snapshots", "admission",
                     "crossings", "judge"):
            setattr(self, name, getattr(self.runtime, name))

    def snapshot(self) -> str:
        return self.snapshots.take(self.tree)

    def forge(self, name: str, type_text: str, body, sources: list) -> None:
        path = self.tree / "forged.json"
        forged = json.loads(path.read_text(encoding="utf-8"))
        forged[name] = {"type": type_text, "body": body, "sources": sources}
        path.write_text(json.dumps(forged, indent=1), encoding="utf-8")

    def runner(self, program, inputs):
        return self.runtime.breaker_runner(program, inputs)

    def batch_runner(self, programs, inputs):
        return self.runtime.builder_runner(programs, inputs)

    def solver(self, function, payload):
        return self.runtime.live_call(self.tree, function, payload)
