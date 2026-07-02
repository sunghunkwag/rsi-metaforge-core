# Phase H — Ordering Specification (H3, frozen before Phase I)

Stratified offer schedule replacing the single global MDL-greedy pass.
Frozen and hashed at Phase H commit time; Phase I implements it exactly
(the hash is asserted by test; a defect discovered during implementation
triggers stop-and-report, not a silent patch).

## GR-O key inventory (every key, with its source)

| Key | Source | GR-O status |
|---|---|---|
| type signature of a body (`_sim_types` static typing from empty stack) | pool-internal computation | legal |
| subterm in-degree (number of distinct archive elites whose expansion contains the body as a contiguous window) | archive-internal statistic | legal |
| MDL net saving | Track 2 anchor report (frozen artifact) | legal |
| E3 characterized membership (body is the expansion of a characterized elite) | Track 2 anchor report | legal |
| program cost (surface length, steps), expanded length, lexicographic tokens | pool/archive-internal | legal |

Excluded by construction: designer-task scores, gate outcomes, holdout
results, adoption history. Phase I adds a GR-F-style isolation test:
the ordering computation's reachable inputs are exactly the two frozen
Track 2 artifacts and the archive document.

## Eligibility (two sources)

1. **Whole-elite bodies** — unchanged from G2: halt-bucket-8 elites,
   fully expanded, expanded length 2–12, deduplicated. (All are
   int-terminal by the h8 construction.)
2. **List-valued subterm fragments** — new: every contiguous window of
   length 2–8 of an elite expansion whose static type from the empty
   stack is exactly one list (`('l',)`), occurring in ≥ 2 distinct
   elites. Census on the frozen Phase G archive: 132 fragment types.
   Justification: H2 Mechanism 1 — the staircase's rungs exist in the
   archive only as subterms; a type-blind pool cannot offer them.

## Strata

- **S1 — list-valued fragments** (132 bodies). Order: subterm in-degree
  desc, then MDL net saving desc, then expanded length asc, then lex.
  Justification: in-degree measures how much of the archive is built
  from the fragment — the direct, GR-O-legal signal of composability.
- **S2 — characterized int-terminal bodies** (195). Order: MDL net
  saving desc, then frozen elite cost, then lex. Justification:
  E3-verified structure ranks a terminal above an uncharacterized one at
  equal compression; within the stratum, compression is the only
  remaining Track 2 value signal.
- **S3 — remaining int-terminal bodies** (123). Order: as S2.
  Justification: terminals without external verification go last; H2
  shows terminals are the displacing class.

## Schedule

Per-wave offer bounds unchanged (14 batches × 3 bodies). Batches are
drawn **round-robin S1, S1, S2, S3** (ratio 2:1:1), repeating within the
wave; an exhausted stratum yields its slot to the next non-empty stratum
in the same rotation. Justification: composable material leads every
window (H2 Mechanisms 1–2) while terminal compressors still flow every
wave — the schedule interleaves rather than banning.

## Re-offer policy (bounded)

A body whose batch was **rejected**, or that was **installed-and-dropped
as an unused rider**, re-enters the tail of its stratum's queue after a
cooldown of 2 waves, at most **2 re-offers per body**. Every re-offer is
logged: wave, body sha16, stratum, and the prior rejection/drop record.
Justification: H2 Mechanism 3 — one-shot consumption froze a dead state
for six waves; a 2-wave cooldown re-judges a body under the vocabulary
that later installs create, and the 2-re-offer cap bounds total offer
work at ≤ 3× pool size. An offer consumed by *installation and use* does
not re-enter.

## Worked dry-run on the H2 trace (schedule mechanics only — GR-O: no designer evaluations consulted)

Wave-0 offer windows, old schedule vs this spec (real data from the
frozen artifacts):

| Batch | Old (global MDL-greedy) | New (stratified) |
|---|---|---|
| 0 | `[INPUT,INPUT,ZMUL,INPUT,INPUT,ZMUL,ZMUL,RED_ADD]` (terminal sum-x⁴, pool[1]) + 2 more terminals | S1: `[INPUT,INPUT,ZMUL]` (x², in-deg 231, MDL 834), `[INPUT,INPUT,ZMUL,INPUT,INPUT,ZMUL,ZMUL]` (x⁴, in-deg 122, MDL 874), `[INPUT,TAIL]` (in-deg 43) |
| 1 | terminals (MDL rank 4–6) | S1: next three fragments (`[INPUT,INPUT,ZMUL,INPUT,INPUT,ZMUL,ZMUL,TAIL]`, `[INPUT,REVL]`, `[INPUT,SCAN_MAX]`) |
| 2 | terminals (7–9) | S2 head: terminal sum-x⁴ body + next two characterized terminals |
| 3 | terminals (10–12); T15 enabler arrives batch 7 | S3 head: uncharacterized terminals |
| 4… | … | rotation repeats S1,S1,S2,S3 |

Under the old schedule the terminal compressor is the **first** offer
and the x²/x⁴ fragments **never appear** (type-excluded). Under this
spec both staircase rungs (x² and x⁴) are offered in wave 0's first
batch, two batches **before** the first terminal; if either is dropped
as a rider at wave 0, the re-offer policy returns it in wave 2 — the
wave at which the G3-only genealogy consumed its x⁴ rung. The displaced
stepping stone survives to its wave under this schedule. No claim is
made here about gate outcomes (GR-O); this is offer mechanics only.

## Serialization

Per-stratum queues, cooldown ledger, and re-offer counts persist in the
runstate (deterministic; two-run byte-identity required as everywhere).
