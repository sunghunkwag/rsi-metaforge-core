"""The kernel's adapter checks that involve no learner, run with the fresh categories installed.

    OPENBLAS_NUM_THREADS=1 python -m rsi6.tests.test_fresh

The fresh adapters are not in the registry on disk (``environments/fresh.py``); this module
installs them before it imports the kernel's tests, so that every check written for every
adapter also covers them. No learner is run on them: the checks that run the learner use only
source categories, and the fresh categories' role is locked.
"""
from __future__ import annotations

import sys

from rsi6.environments import fresh

INSTALLED = fresh.install()

from rsi6.kernel import roles                       # noqa: E402
from rsi6.tests import test_kernel as K             # noqa: E402

CHECKS = [K.test_fast_evaluation_equals_the_specification, K.test_view_hides_the_adapter, K.test_layout_is_the_same_for_every_instance,
          K.test_malformed_answers_are_not_repaired, K.test_every_instance_has_its_own_relabelling, K.test_problem_carries_no_reference,
          K.test_split_keeps_groups_apart, K.test_role_lock_refuses_everything_but_source, K.test_draw_is_reproducible_and_complete]


def test_fresh_categories_are_installed_and_locked():
    assert set(INSTALLED) == {"tardiness", "quadratic", "projects", "clique"}, INSTALLED
    for name in INSTALLED:
        assert roles.role_of(name) == "fresh"
        assert name in K.ALL_ASSIGN and name not in K.ASSIGN_ENVIRONMENTS


def main() -> int:
    failed = 0
    for fn in [test_fresh_categories_are_installed_and_locked] + CHECKS:
        try:
            fn()
            print("PASS", fn.__name__)
        except Exception as error:                  # noqa: BLE001
            failed += 1
            print("FAIL", fn.__name__, "-", type(error).__name__, error)
    print(f"RESULT: {len(CHECKS) + 1 - failed} passed, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
