# Phase E MDL Encoding Specification (frozen instrument)

Compression anchor for Track 2 discoveries: an algorithmic-information
channel that is computed, not judged. The reference implementation is
`mdl_archive_cost` / `mdl_positive_discoveries` in
`rsi_levels_metaforge_unified.py`; the SHA-256 of their exact source text
is pinned by `test_anchor_frozen_instruments_intact`. Spec and
implementation are read-only after the Phase E freeze.

## Encoding

- The corpus is the frozen exploration archive
  `docs/exploration_archive_phaseD.json` (SHA-256
  `e107d831ab2fc590b66974d6b0bbfea8d36e9be1d8ca43cfff14224b00bca96e`):
  every elite program, taken as its fully macro-expanded base-op
  sequence, in sorted cell-key order.
- Base cost under vocabulary `V0` (base ops only):
  `cost(archive | V0) = sum over elites of len(expanded_tokens)`.
- Re-encoding under `V0 ∪ {m}` for a candidate macro body `m` (a base-op
  sequence, `2 ≤ len(m) ≤ 8`): deterministic greedy longest-match — scan
  each elite expansion left to right; at each position, if the next
  `len(m)` tokens equal `m`, emit one macro token and advance `len(m)`;
  otherwise emit the base token and advance 1.
  `cost(archive | V0 ∪ {m})` is the total emitted token count.
- Definition cost: `defcost(m) = len(m) + 1` (the body plus one naming
  token).

## MDL-positive discovery

A candidate `m` is **MDL-positive** iff
`cost(archive | V0 ∪ {m}) + defcost(m) < cost(archive | V0)`.

Candidate enumeration (deterministic, exhaustive within bounds): every
contiguous base-op subsequence of length 2–8 occurring in at least two
distinct elite expansions. Every candidate's exact cost delta is
computed; all MDL-positive candidates are reported with their numbers
(occurrences, saved tokens, defcost, net saving), sorted by net saving
descending, then lexicographically by body. Single-macro judgments only
(no joint re-encoding of multiple candidates); this understates joint
compression and is stated as such in reports.
