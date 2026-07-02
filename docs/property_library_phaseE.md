# Phase E Property Library (frozen instrument)

Mathematical ground-truth anchor for Track 2 discoveries. Every property
is an executable predicate over the function computed by a program
(`f : List[int] -> int` on this VM — properties over list-valued outputs
such as sortedness or permutation-of-input do not type-check here and are
therefore not part of this library). Properties hold or fail by
execution against their mathematical definitions; the space of such facts
is unbounded and entirely external to the system. The reference
implementation is `property_check` / `characterize_elites` in
`rsi_levels_metaforge_unified.py`; the SHA-256 of the exact source text is
pinned by `test_anchor_frozen_instruments_intact`.

## Verification domains

- **Exhaustive domain (k = 3):** every input list with length ≤ 3 and
  values in 0..3 — 85 inputs (the file's existing small-domain proof
  convention). A property must hold on every applicable input.
- **Seeded extension:** 50 vectors from `random.Random(515151)` with
  lengths 4..21 and values 0..15, fixed at freeze time. A property must
  also hold on every applicable seeded input (and derived pairs where a
  property quantifies over two inputs; pairs are formed deterministically
  as consecutive seeded vectors).
- Execution uses the frozen exploration executor (default stack bound,
  `EXPLORE_STEP_BUDGET` expanded ops). A crash on any applicable input
  fails the property being tested (except where the property itself is
  about totality).

## Properties

1. `total_on_domain` — completes (single-int terminal state) on every
   exhaustive-domain and seeded input.
2. `permutation_invariant` — for every exhaustive-domain input, all
   permutations of it yield equal outputs; for every seeded input, 5
   seeded shuffles yield equal outputs. Requires `total_on_domain`.
3. `value_monotone` — incrementing any single element by 1 never
   decreases the output (exhaustive domain; seeded inputs with one seeded
   position incremented). Requires `total_on_domain`.
4. `append_monotone` — appending any single value v in 0..3 never
   decreases the output (exhaustive domain over all v; seeded inputs with
   5 seeded appends). Requires `total_on_domain`.
5. `concat_additive` — `f(xs ++ ys) = f(xs) + f(ys)` for every ordered
   pair of exhaustive-domain inputs with `len(xs ++ ys) ≤ 6`, and for
   consecutive seeded pairs with combined length ≤ 21. Requires
   `total_on_domain`.
6. `concat_max` — `f(xs ++ ys) = max(f(xs), f(ys))` on the same pair
   domains as property 5. Requires `total_on_domain`.
7. `output_bounded_by_input` — for every nonempty applicable input,
   `min(xs) ≤ f(xs) ≤ max(xs)`. Requires `total_on_domain`.

## Triviality exclusion list

An elite is excluded from characterization (recorded as mapped coverage,
unclaimed) if any of the following holds:

- its expansion has fewer than 2 base ops;
- it is **constant on the exhaustive domain** (all 85 outputs equal,
  including crash-free) — constant programs satisfy properties 2, 3, 4
  vacuously;
- it computes `f(xs) = len(xs)` or `f(xs) = 0` on the entire exhaustive
  domain (the two degenerate aggregates reachable with one effective op).

## Characterized discovery

An elite is a **characterized discovery** iff it passes the triviality
exclusions and at least one property from this library holds on its full
verification domain (exhaustive k = 3 plus seeded extension). Reports
list, per discovery: elite cell, tokens, expansion, the properties that
held, and the exact domain sizes verified. Elites failing all properties
remain in the archive as mapped coverage — recorded, unclaimed.
