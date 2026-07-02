# Phase H — Displacement Trace (H2)

Wave-by-wave reconstruction of how the G-combined schedule destroyed the
T27→T28 staircase. Every claim below is recomputed from committed
artifacts (`docs/final_live_phaseG.json`,
`docs/adaptive_g3only_phaseH.json`, `docs/exploration_archive_phaseG.json`,
`docs/anchor_report_phaseG.json`) via the hash-pinned pool functions and
deterministic re-derivation; the decisive re-derivation reproduces the
run's own skip digest exactly (`751d1479e8586590`).

## The successful staircase (G3-only, digest `93338b61e81fe6e1`)

A genealogy of **list-valued** macros, each mined from programs built
with the previous one; zero meta-gate rejections during the climb:

| Wave | Mined macro (TCCI record) | Type | Gate outcome |
|---|---|---|---|
| 0 | mid100 `INPUT INPUT ZMUL` (x²) — from T05/T08/T10 | list | accepted, gained T11, T12 |
| 1 | mid103 `M100 M100 ZMUL` (x⁴) — from T11/T12 programs | list | accepted, gained T27 |
| 2 | mid106 `M103 M103 ZMUL DUP ZMUL` (x¹⁶) — from T27's program | list | accepted, gained T28 |

## The collapse (G combined, digest `47324408543b7365`)

Three compounding mechanisms, each verified:

**Mechanism 1 — type-blind pool selection.** Offer eligibility required
halt-bucket-8 elites; a program whose terminal state is a list can never
complete to a single int, so h8 admits only int-terminal programs.
Measured: **0 of 318** pool bodies are list-valued, while the x²
fragment `INPUT INPUT ZMUL` appears as a subterm inside **231 of 404**
archive elites (the x⁴ fragment: 122). The archive's most-reused
composable fragments were structurally invisible to the offer stream;
MDL-gain ordering then decided which *terminals* arrived first
(`pool[1]` = the terminal sum-x⁴ body, wave 0 batch 0).

**Mechanism 2 — mining score inversion after a terminal install.**
Wave 0 installed exploration terminal macro 101 (sum-x⁴, 8 base ops,
gained T11 → adopted as `M101 M101 MUL`) alongside the mined x² macro
103 (gained T12 → adopted as `M103 M103 ZMUL DUP ZMUL RED_ADD`). The
wave-1 mining corpus therefore contained the x⁴ rung `(103,103,25)` —
but `mine_macros` ranks grams by `n_tasks × len(expansion) (+ bonus)`,
and grams of the 16–17-op terminal macro outscore the 7-op x⁴ fragment.
Re-derived exactly from the artifact (normalization included):
top-3 = `[M101,M101,MUL]` (score 34), `[M101,M101]` (32),
`[M103,LEN,M103,RED_ADD]` (16); the x⁴ rung `[M103,M103,ZMUL]` scores 14
— **ranked 4th, below top_k = 3, never proposed**.

**Mechanism 3 — one-shot digests freeze the dead state.** The top-3
bundle gained nothing and was rejected at wave 1. No adoption occurred
afterward, so the corpus never changed; the identical proposal
re-derived at every later wave and was skipped as a duplicate
(`SKIP_DUPLICATE_PROPOSAL 751d1479e8586590` at waves 2–6 — digest
reproduced exactly by the re-derivation). The mining channel was dead
from wave 1 on. Exploration offers continued (14 batches/wave, all
int-terminal) and were all rejected: 25–30 META_REJECTs per wave,
195 total, no install after wave 0.

| Wave | Adoptions | Installs | Ordinary-proposal fate | META_REJECTs |
|---|---|---|---|---|
| 0 | 19 | 4 macros (2 exploration incl. the terminal; x² mined; even-idx) | accepted ×3 | 25 |
| 1 | 5 (T11, T12, T15 among them) | none | rejected (x⁴ rung ranked 4th, excluded) | 30 |
| 2–6 | 0 | none | `SKIP_DUPLICATE_PROPOSAL 751d1479e8586590` | 28 each |
| 7 | 0 | — | final-wave guard | 0 |

**Net effect:** T27 (needs the x⁴ rung) and T28 (needs T27's genealogy)
both stay OPEN; the run holds T15 alone of the three union-critical
tasks.

## Implications carried into the H3 spec

1. Selection must be type-aware: list-valued composable fragments exist
   only as subterms of int-terminal elites; the offer pool must extract
   and offer them directly (composition-graph statistics are GR-O-legal).
2. Ordering must not let compression-greedy terminals monopolize early
   windows: stratify by type/composability and interleave.
3. One-shot consumption must end: rider-dropped and rejected bodies need
   a bounded re-offer path.
4. **Documented residual risk (outside v4 scope):** Mechanism 2 lives in
   `mine_macros`' scoring, which is not part of the offer schedule;
   Phase I may not change it ("no other mechanism changes"). The H3
   spec mitigates it from the offer side — the x⁴ fragment is offered
   directly (stratum 1, in-degree 122), so the staircase no longer
   depends on wave-1 mining — but the scoring inversion remains latent
   and is recorded for a future directive.
