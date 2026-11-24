"""The gate of process d, generation 1 (amendment 6): what must hold before it runs. No learner runs here.

    OPENBLAS_NUM_THREADS=1 python -m rsi6.tests.test_gate_d
"""
from __future__ import annotations

import hashlib
import json
import os
import sys

os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")

from rsi6.environments import fresh
from rsi6.experiments import gate_d, guard
from rsi6.kernel import ledger as ledgers
from rsi6.learner import designs
from rsi6.meta import rounds


def test_the_amendment_and_the_driver_state_the_same_test():
    amendment = json.load(open(gate_d.AMENDMENT))
    reg = json.load(open(gate_d.REGISTRATION))
    stated = amendment["registered"]
    v0 = designs.default(reg["design"])
    nominee = designs.validate(dict(v0, **gate_d.NOMINEE))
    assert stated["incumbent"] == designs.digest(v0) and stated["nominee"] == designs.digest(nominee)
    assert designs.differences(v0, nominee) == {"model.batch": {"from": 4, "to": 2, "function": "model"}}
    assert stated["categories"] == sorted(gate_d.ENVIRONMENTS) and stated["role"] == gate_d.ROLE
    assert stated["gate_seeds"] == [gate_d.GATE_SEEDS[0], gate_d.GATE_SEEDS[-1]] and len(gate_d.GATE_SEEDS) == 32
    assert stated["confirm_seeds"] == [gate_d.CONFIRM_SEEDS[0], gate_d.CONFIRM_SEEDS[-1]] and len(gate_d.CONFIRM_SEEDS) == 32
    assert not set(gate_d.GATE_SEEDS) & set(gate_d.CONFIRM_SEEDS)
    assert stated["budget"] == reg["budgets"]["run"]


def test_the_rules_are_the_registered_ones():
    amendment = json.load(open(gate_d.AMENDMENT))
    reg = json.load(open(gate_d.REGISTRATION))
    assert amendment["registered"]["rules"] == {"margin": 0.005, "cpu_ratio": 1.15, "bootstrap": 2000, "level": 0.9}
    assert all(reg["rules"][k] == v for k, v in amendment["registered"]["rules"].items())
    assert all(rounds.RULES[k] == v for k, v in amendment["registered"]["rules"].items())


def test_the_adapters_are_the_audited_files():
    table = fresh.table()["categories"]
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    for name in gate_d.ENVIRONMENTS:
        path = os.path.join(here, "environments", name + ".py")
        assert table[name]["admitted"] and hashlib.sha256(open(path, "rb").read()).hexdigest() == table[name]["sha256"], name


def test_no_run_before_the_unlock_and_no_seed_used_twice():
    ledger = ledgers.Ledger(guard.MAIN)
    unlock = [r["idx"] for r in ledger.records if r.get("type") == "unlock" and r.get("role") == gate_d.ROLE]
    for record in ledger.records:
        if record.get("type") != "run":
            continue
        if record["env"] in gate_d.ENVIRONMENTS:
            assert unlock and record["idx"] > unlock[0], "a learner ran on a category of this gate before it was unlocked"
            assert record["seed"] in gate_d.GATE_SEEDS + gate_d.CONFIRM_SEEDS and record["purpose"].split(":")[1] == "d", record["purpose"]
        else:
            assert record["seed"] not in gate_d.GATE_SEEDS + gate_d.CONFIRM_SEEDS, "a seed of this gate was used elsewhere"


def test_an_amendment_record_carries_the_hash_of_the_file():
    ledger = ledgers.Ledger(guard.MAIN)
    recorded = ledger.select(type="amendment", amendment=6)
    if recorded:
        assert recorded[-1]["record_sha256"] == hashlib.sha256(open(gate_d.AMENDMENT, "rb").read()).hexdigest()


def main() -> int:
    failed = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print("PASS", name)
            except Exception as error:                   # noqa: BLE001
                failed += 1
                print("FAIL", name, repr(error))
    print(f"RESULT: {len([n for n in globals() if n.startswith('test_')]) - failed} passed, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
