# C1 vocabulary

The fast closure C1 searches with one of two vocabularies (`vocabulary.py`). The
language itself (`types.PRIMITIVE_TYPES`, `evaluator.py`) understands the union; a
vocabulary is the subset a search may build with. `tests/test_vocabulary.py` checks
that this file and `vocabulary.py` list the same symbols with the same types.

Reference for the restored set: DreamCoder's list domain,
`dreamcoder/domains/list/listPrimitives.py` in `ellisk42/ec` at commit
`cb0e63f5c33cd2de360b791038b0f5272750270e` (the commit FRESH and J's pools come
from). `bootstrapTarget_extra()` ∪ `basePrimitives()` there is: the integer
constants 0–5, `+ - * mod gt? eq? if empty cons car cdr empty? map unfold range
index fold length is-prime is-square`. RSI-2 already has every one of these
except `unfold`, `index`, `is-prime`, `is-square` and the constants 3, 4, 5.
`fix1` is DreamCoder's `primitiveRecursion1` (`McCarthyPrimitives()`); `zip` is
its `zip_primitive`, here with pairs instead of a combining function.

## ORIGINAL — RSI-2's grammar, unchanged (`rsi2/types.py`, `rsi2/grammar.py`)

| Symbol | Type |
| --- | --- |
| `add`, `sub`, `mul`, `div`, `mod` | `int -> int -> int` |
| `neg`, `abs` | `int -> int` |
| `eq`, `lt`, `le`, `gt`, `ge` | `int -> int -> bool` |
| `and`, `or` | `bool -> bool -> bool` |
| `not` | `bool -> bool` |
| `if` | `bool -> a -> a -> a` |
| `nil` | `list[a]` |
| `cons` | `a -> list[a] -> list[a]` |
| `head` | `list[a] -> a` |
| `tail` | `list[a] -> list[a]` |
| `is_empty` | `list[a] -> bool` |
| `length` | `list[a] -> int` |
| `range` | `int -> list[int]` |
| `map` | `(a -> b) -> list[a] -> list[b]` |
| `filter` | `(a -> bool) -> list[a] -> list[a]` |
| `fold` | `(b -> a -> b) -> b -> list[a] -> b` |
| integer constants | `-1 0 1 2` |
| boolean constants | `false true` |

## RESTORED — ORIGINAL plus the DreamCoder set RSI-2 lacked (OWNER_DIRECTIVE.md §3.1)

| Symbol | Type | Justification |
| --- | --- | --- |
| `unfold` | `(a -> bool) -> (a -> b) -> (a -> a) -> a -> list[b]` | DreamCoder `unfold` in `bootstrapTarget()`; its argument order there is seed first (`t0 -> (t0 -> bool) -> (t0 -> t1) -> (t0 -> t0) -> list t1`), here the directive's order, seed last. Stops when the predicate holds; one step per emitted element; recursion limit 50 there, the step budget here. |
| `index` | `int -> list[a] -> a` | DreamCoder `index` in `bootstrapTarget()` (`l[j]`). Out-of-range and negative positions fail here; Python's wrap-around is not reproduced. |
| `fix1` | `a -> ((a -> b) -> a -> b) -> b` | DreamCoder `primitiveRecursion1` (`fix1`), the only general recursion in its list sets. Bounded there by a depth limit of 20 recursive calls; here by the step budget only (one step per recursive call). |
| `is_prime` | `int -> bool` | DreamCoder `is-prime` in `basePrimitives()` and `bootstrapTarget_extra()`. There a table of the primes below 200; here trial division, so the two agree on every integer below 200 and this one is also correct above. `n < 2` is not prime. |
| `is_square` | `int -> bool` | DreamCoder `is-square` in `basePrimitives()` and `bootstrapTarget_extra()` (`int(sqrt(n))**2 == n`). Here `n >= 0 and isqrt(n)**2 == n`, so negative inputs are `false` instead of a host error. |
| `zip` | `list[a] -> list[b] -> list[(a, b)]` | DreamCoder `zip_primitive` takes a combining function `(a -> b -> c)`; the directive asks for pairs as a type, so `zip` returns pairs and the combination is written with `map`. Truncates to the shorter list, as DreamCoder's does. |
| `pair` | `a -> b -> (a, b)` | The pair type the directive's `zip` needs. Not in DreamCoder's list sets (it has no product type); `pair`, `fst` and `snd` are the smallest set that makes `zip` usable. |
| `fst` | `(a, b) -> a` | First projection of a pair (see `pair`). |
| `snd` | `(a, b) -> b` | Second projection of a pair (see `pair`). |
| integer constants | `-1 0 1 2 3 4 5` | DreamCoder's `basePrimitives()` and `bootstrapTarget_extra()` carry the constants 0–5; RSI-2 kept `-1`, which stays. |

Admitted primitives (Phase 2) are not listed here. They live in `admitted/<hash>.py`
with their type, C2 witness term, probe-set I/O table and admission record, and
are named by the first 12 hex characters of the SHA-256 of the witness term.
