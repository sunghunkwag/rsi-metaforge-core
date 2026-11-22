"""Running a verifier on a candidate answer, with limits.

A verifier is external code. It is compiled once per instance and called with a candidate and
the instance's parameters. Three things can go wrong and each is a verdict, not a crash: the
candidate does not satisfy the verifier (``False``), the call raises (``error``), or the call
does not return within the time limit (``timeout``). Only ``True`` is a solve.

Limits. A candidate is refused before the call when it is larger than the caps below (a search
can otherwise ask a verifier to scan a list of a billion items). The time limit is a safety
net, not a budget: budgets are counted in verifier calls by the caller. A run is reproducible
as long as no call is near the limit, so the limit is generous and every timeout is counted.
"""
from __future__ import annotations

import signal
import typing

MAX_INT_BITS = 20_000            # an integer answer with more bits is refused
MAX_ITEMS = 200_000              # total number of leaves of an answer (characters, numbers)
LIMIT = 2.0                      # seconds per verifier call

TRUE, FALSE, ERROR, TIMEOUT, REFUSED = "true", "false", "error", "timeout", "refused"


class _Timeout(BaseException):
    """Not an Exception: a verifier's own ``except Exception`` must not swallow it."""


def _raise_timeout(signum, frame):
    raise _Timeout()


def size_of(value, budget: int = MAX_ITEMS) -> int:
    """Leaves of a nested answer, or ``budget + 1`` as soon as it is exceeded."""
    if isinstance(value, bool) or value is None:
        return 1
    if isinstance(value, int):
        return 1 if value.bit_length() <= MAX_INT_BITS else budget + 1
    if isinstance(value, float):
        return 1
    if isinstance(value, (str, bytes)):
        return max(1, len(value))
    if isinstance(value, (list, tuple, set, frozenset)):
        total = 1
        for item in value:
            total += size_of(item, budget - total)
            if total > budget:
                return budget + 1
        return total
    if isinstance(value, dict):
        return size_of(list(value.items()), budget)
    return budget + 1            # an object of another kind is not an answer


NAMESPACE = {name: getattr(typing, name) for name in ("List", "Dict", "Tuple", "Set", "Optional", "Any", "Union")}


def compile_verifier(source: str):
    """The function ``sat`` of a verifier's source."""
    namespace = dict(NAMESPACE)
    exec(compile(source, "<verifier>", "exec"), namespace)      # external task code, by design
    return namespace["sat"]


def call(function, *args, limit: float = LIMIT, **kwargs):
    """``(status, value)`` of ``function(*args, **kwargs)`` under the time limit."""
    previous = signal.signal(signal.SIGALRM, _raise_timeout)
    signal.setitimer(signal.ITIMER_REAL, limit)
    try:
        return "ok", function(*args, **kwargs)
    except _Timeout:
        return TIMEOUT, None
    except RecursionError:
        return ERROR, None
    except MemoryError:
        return ERROR, None
    except Exception:
        return ERROR, None
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)


class Verifier:
    """One instance's verifier, with a count of the calls made to it."""

    def __init__(self, instance):
        self.instance = instance
        self.function = compile_verifier(instance.source)
        self.calls = 0
        self.timeouts = 0

    def verdict(self, answer, limit: float = LIMIT) -> str:
        self.calls += 1
        if size_of(answer) > MAX_ITEMS:
            return REFUSED
        status, value = call(self.function, answer, limit=limit)
        if status == TIMEOUT:
            self.timeouts += 1
            return TIMEOUT
        if status != "ok":
            return ERROR
        return TRUE if value is True else FALSE

    def __call__(self, answer) -> bool:
        return self.verdict(answer) == TRUE
