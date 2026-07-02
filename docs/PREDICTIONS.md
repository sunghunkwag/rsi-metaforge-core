# Phase I Predictions (registered before the final evaluation)

Committed before any Phase I final-evaluation run exists (GR-P). No
Phase I live run has been executed at prediction time — every claim
below derives from Phase H committed evidence plus feedback-free offer
mechanics (the fresh-offer order is fully determined by the frozen
strata and rotation; simulating it consults no designer evaluations,
GR-O). Scored in `docs/SEQUENCING_RESULT.md`.

Offer-mechanics facts used (deterministic, from the frozen strata):
294 of 450 stratified bodies are offered fresh within one run (S1
132/132, S2 81/195, S3 81/123 — the S2/S3 truncation is stated, bounded,
and mitigated by re-offers); the x² and x⁴ fragments are both in wave
0's **first batch** (S1 head, per the H3 dry-run); the T15 enabler
`[INPUT,EVENIDX,RED_ADD]` is offered at **wave 1** (S2); the terminal
sum-x⁴ compressor arrives wave 0 in an S2 slot (batch 3), **after** the
staircase fragments.

## The three union-critical tasks

| Task | Prediction | H-phase evidence | Path / contingency |
|---|---|---|---|
| **T27 sum_x16** | **SOLVED** (wave 0–1) | The G3-only genealogy proves the x⁴ macro gates T27 (`M100 M100 ZMUL` → w1 `SCREEN_INSTALL gained=['T27']`); sum x¹⁶ = 6 surface tokens over an x⁴ macro, within `ENUM_SURFACE_MAX`. Under the spec, the x⁴ fragment is offered in wave 0's first batch — as a **pool offer**, not mined, so Mechanism 2 (mining-score inversion) is bypassed for this rung. | Inference from H evidence, not an observation — no Phase I run exists. |
| **T28 sum_x32** | **SOLVED** (wave 1–3) | **Expected acquisition path: fresh mining, not pool offer.** No list-valued fragment of length ≤ 8 can express x⁸ or deeper (x⁸ needs ≥ 15 ops), so the pool cannot offer the x¹⁶ rung; T28 requires the G3-only genealogy to resume — mine T27's adopted program to obtain the x¹⁶ macro (in G3-only this gram ranked in top-3 and gated T28 at w2). **Mechanism-2 contingency, stated in advance:** if wave-0 terminal installs shorten the corpus so the x¹⁶ gram ranks below `top_k = 3` again, the chain stalls; that outcome is an attributable null pointing at mining policy (v5 scope), and the report must exhibit the skip-digest evidence exactly as H2 did (`751d1479…`-style re-derivation). | Known-at-prediction-time: only the G3-only w2 observation (digest `93338b61e81fe6e1`); the Phase I corpus differs and the risk is real. |
| **T15 alternating_sum** | **SOLVED** (wave 1–2) | Enabler offered at wave 1 (S2 mechanics above); the same body was gate-accepted in both prior configurations that offered it (v2 final w6; G combined w0) with `gained=['T15']`. | Pool offer; if rider-dropped, re-offer returns it by wave 3. |

## The remaining OPEN tasks (attribution unchanged from Phase F/H)

| Task | Prediction | Basis |
|---|---|---|
| T18, T21, T22, T23, T26 | OPEN | SEARCH/VOCAB attribution; no stratified body or fragment supplies the missing vocabulary (conditionals, index arithmetic, order statistics, shifted-difference); unchanged from Phase G outcomes. |
| T29–T32 | OPEN | Certified ISA walls. |

**Predicted final designer count: 24/33 with {T15, T27, T28}
simultaneously SOLVED — the threshold exactly met.** Disclosed risks:
(i) the T28 mining contingency above (null → 23/33, attributable to
mining policy with skip-digest evidence); (ii) wave-0 batch interactions
between fragment installs and terminal installs are novel territory —
any additional displacement will be traced per deliverable point 5.
