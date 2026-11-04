# Procedure induction: a development-only result, not registered

**The idea.** The search skeletons (`map h`, `filter h`, `fold h init`,
...) and the conjugation move are designer-given procedures. Procedure
induction lets the system write new ones from its own verified
solutions:

- **Anti-unification.** Every pair of same-typed solutions is compared,
  and the smallest subterm containing all their differences becomes a
  typed hole. The bound variables the hole uses are lambda-lifted.
- **Ranking.** The resulting templates are ranked by support, the number
  of solutions that are instances of them.
- **Offering.** The top 8 templates are offered as skeletons to every
  unsolved task of their type.
- **Adoption.** A template is adopted, and kept across generations, only
  when a program found through it is verified on an unsolved task.
  Adopted templates were to count a depth, one more than the deepest
  procedure behind their source solutions. That depth was meant to
  measure recursion in procedure growth.

**Where the code lives.** It is not on this branch:

| Variant | Branch | Commit | Code |
| --- | --- | --- | --- |
| v1: each template is its own meta-RL action | `rsi3/induce` | 1f33c8d | `rsi3/induce.py`, `rsi3/tests/test_induce.py` |
| v2: all templates form one `induced` action family | `rsi3/induce-family` | d689576 | the same |

**Development runs.** Both used seed 44 and `--skip-validation`, so no
held-out set was loaded. TRAIN is seed-independent for these arms.

| Arm | TRAIN g1–g16 | TRAIN g16 | Templates proposed (g16) | Adopted |
| --- | --- | --- | --- | --- |
| RSI3_META_HONEST (registered) | 10 14 17 22 24 25 25 25 25 25 25 26 28 28 29 29 | 29 | — | — |
| INDUCE v1 | 10 14 17 18 19 22 22 24 25 25 25 25 25 25 25 25 | 25 | 7 (182 task slots) | **0** |
| INDUCE v2 (family) | 10 14 17 19 23 24 25 25 25 25 25 25 25 25 26 28 | 28 | 6 | **0** |

**What happened.**

- **The templates are real generalizations of the system's own
  programs.** Examples:
  - `lambda l. cons □ l` and `lambda l. cons (□ l) l`, from the prepend
    family;
  - `map (lambda x. mod x □)`, from modulo-k;
  - `lambda l. learned_g8_0 l □`, from the slices.
- **No template was adopted.** The tasks left unsolved on TRAIN (dup,
  has-head-in-tail, index-head, kth-largest ×2, kth-smallest, rotate-k)
  are not instances of anything the solved families share. A procedure
  can be adopted only by solving an unsolved task, so no adoption was
  possible on this TRAIN set.
- **Exploration cost TRAIN.** In v1, each template was its own action and
  took 60–96 chunks of wake budget in generations 3–4. The reverse cascade
  arrived late or not at all, so TRAIN ended at 25. In v2, one family
  action spent a single chunk at generation 3 and TRAIN ended at 28.
  Episodes on the `induced` action: 950, rewarded 88; nearly all were
  practice on imagined tasks.

**Decision.** Neither variant is registered, because the gate this design
needs cannot open on this TRAIN set. One observation carried forward:
the templates are edits of single verified programs. Analogical repair
(`analogy.py`) applies that idea directly. There a candidate is one
verified program with one subterm changed, and the measure is held-out
tasks, where related unsolved tasks exist.
