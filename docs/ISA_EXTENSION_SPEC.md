# ISA Extension Specification — Phase J2 (PROPOSED; frozen upon approval)

Status: PROPOSED at the Phase J2 checkpoint. Per DIRECTIVE v5 §3, nothing in
this specification is implemented until the user explicitly approves it. Upon
approval this file is frozen read-only; its SHA-256 is recorded in the Phase J
report and pinned by a test added in J3 (R5/R12). A defect discovered after
freezing triggers stop-and-report and a re-hashed revision, never a silent
patch.

## 1. Proposal summary

Two primitives, and only two, are proposed for the extended ISA:

| name  | ext id | type (ins, rightmost-first -> outs) | semantics |
|-------|--------|--------------------------------------|-----------|
| BCAST | 60     | (int, list) -> list                  | pop int `s` (top), pop list `xs`, push `(s,) * len(xs)` |
| ZGT   | 61     | (list, list) -> list                 | pop list `y` (top), pop list `x`, push `tuple(1 if x[i] > y[i] else 0 for i in range(min(len(x), len(y))))` |

Exact operational rules, shared with every existing op:

- Both crash with `VMCrash` on type or arity violation (same `_pop_int` /
  `_pop_list` discipline as base ops); crashes score 0 and are never hidden.
- `ZGT` truncates to the shorter operand exactly as the existing zip family
  (`ZADD`, `ZSUB`, `ZMUL`, `ZMAX`) does, and is specified as the same
  combinator: `_zip2(lambda a, b: 1 if a > b else 0)`; on two empty lists it
  pushes the empty list, like every zip.
- `BCAST` is byte-identical to the existing dormant catalog entry
  (`DORMANT_CAPABILITY_CATALOG["BCAST"]`, runtime line 5874): this proposal
  does not modify it, it proposes granting it.
- Output values pass through the existing `_push` guards (`INT_CAP`,
  `MAX_LIST_LEN`, active stack bound); no new capacity or budget constant is
  introduced or changed.

Id assignment: 60 and 61 lie in the reserved extended range
`[EXT_ID_BASE, EXT_ID_MAX] = [60, 99]` — above every base op (< 34) and below
every macro (>= 100) — so all existing "is a macro" predicates and base
tables are untouched by construction. Disclosed id-space interaction: the
Section-16 self-forge battery transiently registers forged ops from
`FORGE_ID_BASE = 61` upward inside its own battery scope (granted and revoked
within one run, never persisted, never concurrent with a live searcher);
any extended id >= 61 shares that range, and 60 is BCAST's committed id, so
overlap with transient forge registrations is unavoidable within [60, 99].
J3 must add a guard test that a live searcher never holds a Section-16
registration concurrently with a granted Phase J primitive.

## 2. Derivation from the J1 gap analysis (requirement i)

The primitive set is derived from docs/ISA_GAP_J.md, which is derived from
the committed proofs — not from any reference oracle implementation:

- **BCAST** closes the absolute, lemma-certified gap: the executed
  constructor lemma (`no_int_to_list_constructor_lemma`, >= 2000 transitions,
  test-pinned) proves no base op except `INPUT` creates a list, so a
  program-supplied constant list is inexpressible at any depth. The dormant
  catalog already names this gap with this exact signature `(i, l) -> (l)`,
  and the existing oracle-free mechanical locator
  (`propose_capability_requests`) already derives a BCAST request from the
  system's own residues (test-pinned:
  `test_capability_request_is_mechanical_and_oracle_free`).
- **ZGT** closes the tier gap documented in ISA_GAP_J.md §2: the ISA has
  order-selection at every tier (`MAX2`/`MIN2`, `ZMAX`, `SCAN_MAX`,
  `RED_MAX`, `SORTL`) and a compositional scalar order-test
  (`SUB PUSH0 MAX2 PUSH1 MIN2`), but no elementwise order-test — the
  elementwise capping constants are exactly the constant lists the lemma
  proves unconstructible. ZGT restores tier parity with what the scalar
  closure already contains rather than importing semantics foreign to the
  ISA; it is the minimal comparison completion of the existing zip family.

Derivation discipline, disclosed: ZGT's type signature `(l, l) -> (l)`
already exists in the zip family, so the current signature-gap locator
cannot fire for it; its justification is the J1 certificate analysis, i.e. a
designer act, stated as such — precisely the disclosure discipline the
dormant catalog already uses ("designer-stocked, stated, not hidden").
Neither primitive encodes a task constant (the threshold 3 of T29 remains a
program-supplied `PUSH3`), a task-specific control structure, or any
oracle-derived behavior; both are single generic ops, in contrast to the
Section-16 forge, which synthesizes whole task-shaped fold programs and is
excluded from the mainline ledger for exactly that reason.

Minimality, now measured (§8): neither primitive alone makes any wall
reachable within the certified <= 6 horizon (untruncated enumeration); only
the joint set does, and only for T29. BCAST alone leaves T29 expressible
only at depth 19 (committed witness) — the committed admission trial at
maximal declared budget (12 x 1500) found nothing. ZGT alone cannot express
T29/T30 (no constant comparand / no broadcast of the maximum; the §7
witnesses for those tasks require BCAST). No third primitive is included
because every remaining sub-capability (positional arithmetic, first-index
extraction, segment accumulation) is already inside the base closure once
indicators exist, as the §7 witnesses demonstrate constructively.

## 3. Generality and MDL accounting (requirement ii)

Requirement (ii) asks each primitive to be MDL-positive on a re-encoding of
the existing Track 2 archive, independent of T29–T32. Two accountings are
reported; both instruments are declared here, before any Phase J search runs
(R5), and both results are honest nulls.

**(a) Under the frozen Phase E accounting (docs/mdl_spec_phaseE.md,
SHA-pinned): delta = 0 by construction, for both primitives.** The frozen
spec defines re-encoding only for candidate macros whose bodies are base-op
subsequences (length 2–8); a genuinely new primitive has no base-op body, so
greedy longest-match can never fire. This is a structural property of any
closure-extending primitive, not a defect of these two.

**(b) Under the extended-ISA re-encoding instrument declared for Phase J
(new; measured; deterministic).** Definition: for every elite of the frozen,
SHA-verified Phase G archive, expand with the archive's own vocabulary
macros and execute on the 20 frozen train inputs (crashing or non-scalar
elites excluded and counted); `behavior(e)` is the resulting 20-vector;
shortest-program lengths are taken from the runtime's own untruncated
observational-equivalence enumeration at surface length <= 6 under four
vocabularies (base; base+BCAST; base+ZGT; base+BCAST+ZGT);
`saving_P(e) = len_base(e) - len_P(e)` with each term flooring the elite's
own expanded length; `MDL(P) = sum(saving_P) - defcost(P)`,
`defcost = 2 per primitive` (declared convention: one naming token plus one
catalog entry; the frozen macro convention `len(body)+1` is undefined for a
body-less primitive).

Measured result (reproduction: `docs/measure_mdl_extension_J.py`; output
committed as `docs/mdl_extension_J.json`; no randomness; archive load
SHA-verified; every table untruncated at class cap 2,500,000):

| quantity | value |
|---|---|
| Phase G elites total / excluded (crash or non-int on train inputs) / scored | 404 / 6 / 398 |
| total saving, base+BCAST | 0 tokens (0 elites improved) |
| total saving, base+ZGT | 0 tokens (0 elites improved) |
| total saving, base+BCAST+ZGT | 0 tokens (0 elites improved) |
| net after defcost (2 per primitive) | -2 / -2 / -4 |
| MDL-positive per requirement (ii) | **No — for both primitives, under both accountings** |

**Interpretation, stated plainly:** requirement (ii) is not met, and the
measurement explains why it cannot be met by any closure-extending primitive
on this corpus: the Track 2 archive lives strictly inside the old closure
(404 elites dominated by elementwise-power motifs; the committed anchor
reports show the same), so it contains no behavior that new out-of-closure
semantics could shorten at the certified horizon. An MDL-positive-on-the-old-
archive primitive would, by the same token, be macro-expressible and close no
gap. This null is reported as a primary finding of Phase J2 and is one of the
decision points of the checkpoint below. The general-purpose case for the set
therefore rests on the measured breadth evidence (§7: two generic ops give
sealed-gate-passing expressibility across all four walls, with three distinct
downstream idiom families reusing the same indicator data) and on tier parity
(§2), with the archive-MDL numbers reported as measured.

## 4. Non-degeneracy (requirement iii)

Measured over the extended vocabulary (34 base + BCAST + ZGT = 36 tokens),
all 36 + 36^2 = 1332 programs of expanded length <= 2, executed on all 20
train inputs: **zero OPEN-task train vectors are reachable at length <= 2**
(checked for T18, T21, T22, T29, T30, T31, T32; reproduction:
`docs/measure_witnesses_J.py`, output `docs/witnesses_J.json`). The
untruncated <= 6 enumeration (§8) sharpens this: the shortest extended-ISA
wall crossing anywhere below length 7 is T29 at exactly 6 tokens
(`INPUT INPUT PUSH3 BCAST ZGT RED_ADD`, found by the enumerator itself),
a composition of an input read, a program-chosen constant, both new
primitives, and a reduction — a capability change exercised through
composition, not a definition change. No other OPEN task is reachable at
<= 6 under any of the four vocabularies.

## 5. Backward compatibility (requirement iv)

- Existing programs cannot contain tokens 60/61: ungranted extended ids crash
  (`test_extension_registry_dormant_inertness`, pinned) and no committed
  artifact contains them (the Phase G archive alphabet is base ops + macros
  100/103).
- Granting adds dispatch entries; it modifies no base-op implementation, no
  constant, no gate, no seed, no budget.
- J3 obligations (add-only tests): byte-identical re-evaluation of all 26
  adopted designer programs and every Phase G archive elite under the
  extended VM; two-run byte-identity for every new computation; dormant
  inertness preserved for all non-granted ids.
- The second subsystem's same-named constants (`MAX_STACK = 64`,
  `MAX_PROGRAM_LEN = 60`) are untouched; the existing literal-check test
  stays green.

## 6. Adoption path (design constraints binding J3–J5)

1. **Catalog, not hack:** ZGT enters `DORMANT_CAPABILITY_CATALOG` as a
   `CapabilitySpec` (dormant by default; all inertness tests keep passing).
2. **Gate-arbitered grant:** a grant becomes permanent only as a
   searcher-state change through the existing discipline — A/B versus the
   incumbent at identical budgets and seeds, sealed-holdout arbitration,
   through the single `_permanent_install` call site (R3). No second install
   site; no unconditional activation in any live path.
3. **Freeze-before-run (J4):** the extended-ISA holdout instrument for
   T29–T32 is created and SHA-256-hashed before any extended search runs.
4. **Re-certification (J3):** closure certificates re-derived for the
   extended ISA for T29–T32 and the previously certified set, committed with
   determinism tests; where a task stays unreachable, the new certificate
   says so.
5. **Ledger discipline:** designer witnesses (§7) are never counted as
   solved; only search-found, dual-gate-passing programs enter
   `adopted_tokens` (existing pins stay).
6. **Expected pin conflicts, declared now (R1/R2):** a successful T29-class
   crossing will trip `test_expected_isa_blocked_walls_stay_open` and the
   witness test's "wall not adopted" assertion, and re-derived certificates
   change `certified_blocked_le` reporting for the extended vocabulary.
   Each conflict will be presented per-assertion at a STOP for explicit
   authorization before any amendment, in a separate labeled commit. No test
   is weakened silently.

## 7. Expressibility witnesses (designer-supplied; never counted as solved)

Measured with in-memory grants of §1 semantics, verified against train,
sealed holdout, and counterfactual gates (all three pass, for all four
tasks; reproduction: `docs/measure_witnesses_J.py`):

| task | name | expanded tokens | len | uses |
|------|------|-----------------|-----|------|
| T29 | count_above_threshold | `INPUT DUP PUSH3 BCAST ZGT RED_ADD` | 6 | BCAST, ZGT |
| T30 | argmax_index | `INPUT DUP RED_MAX BCAST INPUT SCAN_MAX ZGT RED_ADD` | 8 | BCAST, ZGT |
| T31 | first_greater_than_previous | `INPUT TAIL INPUT ZGT DUP SCAN_MAX RED_ADD INPUT LEN SWAP SUB SWAP PUSH0 PUSH1 SUB SWAP RED_ADD SELECT` | 18 | ZGT |
| T32 | longest_increasing_run | `INPUT TAIL INPUT ZGT DUP DUP PUSH1 BCAST SWAP ZSUB SWAP SCAN_ADD SWAP OVER ZMUL SCAN_MAX ZSUB RED_MAX PUSH1 ADD` | 20 | BCAST, ZGT |

Token ids: T29 `(4,5,3,60,61,29)`; T30 `(4,5,30,60,4,27,61,29)`;
T31 `(4,20,4,61,5,27,29,4,16,6,10,6,0,1,10,6,29,33)`;
T32 `(4,20,4,61,5,5,1,60,6,24,6,28,6,8,25,27,24,30,1,9)`.

Roles, exactly as the committed BCAST witness precedent: they bound each wall
from above (expressible-at depth), while re-derived certificates bound from
below; they are labeled designer-supplied, never enter any solved count, and
J3 pins both properties by test. The three downstream idiom families — count
(`RED_ADD` on a mask), first-position (`SCAN_MAX` step + counting or length
arithmetic), segment measure (`SCAN_ADD`/`SCAN_MAX`/`ZMUL` algebra) — reuse
the same indicator data, which is the §2 minimality claim made constructive.

## 8. Search-reachability analysis (feeds docs/PREDICTIONS_J.md)

Measured, untruncated observational-equivalence enumeration to expanded
length 6 (class cap 2,500,000; reproduction `docs/measure_mdl_extension_J.py`,
output `docs/mdl_extension_J.json`):

| vocabulary | classes per length 1..6 | wall vectors found <= 6 |
|---|---|---|
| base (34 ops) | 5, 38, 365, 3097, 33012, 332509 | none (cross-validates the committed certificates; L6 count matches the pinned 332509) |
| base+BCAST | 5, 38, 368, 3145, 33705, 341320 | none |
| base+ZGT | 5, 38, 365, 3109, 33375, 339123 | none |
| base+BCAST+ZGT | 5, 38, 368, 3157, 34073, 348070 | **T29 at length 6**: `(4,4,3,60,61,29)` |

Consequences for J5 planning (known-at-spec-time; PREDICTIONS_J must mark
them as such): T29's train vector lies inside the live search's own
enumeration horizon (`ENUM_SURFACE_MAX = 6`) under the joint grant, so the
deterministic enumeration channel is expected to reach it without stochastic
luck; T30 (witness at 8) sits beyond the horizon and depends on the
stochastic channel (`MAX_PROGRAM_LEN = 14`, `RESTARTS_PER_TASK = 6`,
`ITERS_PER_RESTART = 550`) or macro compression; T31 (18) and T32 (20) are
expected honest nulls at current budgets. The committed BCAST admission-trial
null (12 x 1500 found nothing at witness depth 19) is the cautionary
precedent: expressibility does not imply reachability. The class-count
growth (+4.7% at length 6 for the joint vocabulary) quantifies the added
enumeration load; every certificate in this table is untruncated, so J3
re-certification at these depths is feasible on this hardware.

## 9. Freeze protocol

On explicit user approval of this exact text: the file is committed
read-only; its SHA-256 is recorded in the Phase J report and pinned by a J3
test; the two measurement scripts and their outputs are committed beside it
(`docs/measure_witnesses_J.py` + `docs/witnesses_J.json`,
`docs/measure_mdl_extension_J.py` + `docs/mdl_extension_J.json`); any
subsequent change follows R12 (stop, report, re-hash, justify).
