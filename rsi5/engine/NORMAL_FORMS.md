# Normal forms the engine enumerates

The bottom-up engine builds only terms in **β-normal, η-long form** and refuses, before
evaluation, every left-hand side below. A refused term is never evaluated and never
counted against the candidate budget. `same(a, b)` means the two argument programs
are the same pool entry; since the pool keeps one program per behaviour on the
evaluation points, that is "a and b have one behaviour there".

## By construction

- **No β-redex.** A lambda is only ever built as the function argument of a
  higher-order primitive (`map`, `filter`, `fold`, `unfold`, `fix1`); it is never
  applied to an argument.
- **η-long.** Every function-typed argument is a lambda of the full arity the
  primitive expects (`map (λx. neg x) xs`, never `map neg xs`); every primitive is
  fully applied; pools hold only ground-typed programs. The only application of a
  non-primitive head is `rec e` inside a `fix1` body, where `rec` is the recursive
  function variable.
- **Commutative arguments in canonical order.** For `add`, `mul`, `eq`, `and`, `or`,
  the left argument precedes the right one in pool order (`add b a -> add a b`). For
  `and` and `or` this is not behaviour-preserving in the reference interpreter, which
  evaluates them left to right and skips the right side when the left decides: see
  "Where a rule loses programs" below.

## What "replacement" means

The engine keys a program by its outputs on the evaluation points, failures included, so
two programs are interchangeable only if they fail on the same points. The rules below do
not all preserve that. The middle column is the rule's **replacement**: it equals the
refused form wherever the refused form is defined, and it is defined at least as often
(`mul e 0 -> 0` is `0` where `e` fails; `if c a a -> a` is `a` where `c` fails;
`sub e e`, `eq e e`, `cons (head e) (tail e)` and `head (cons a b)` likewise). The
language has no construct that observes a failure, so every context is monotone in
definedness: putting the replacement where the refused form stood never turns a program
that answers into one that fails. Such a rule can therefore drop a behaviour class from
the pools but not a program that solves a task. The three exceptions are listed after the
table.

## Rewrite rules (left-hand side refused)

| Refused | Replacement | Why |
| --- | --- | --- |
| `if true a b`, `if false a b` | `a`, `b` | literal condition |
| `if (not c) a b` | `if c b a` | negated condition |
| `if c a a` | `a` | same branches |
| `if c (if c a b) d`, `if c d (if c a b)` | `if c a d`, `if c d b` | repeated condition |
| `not (not e)`, `not true`, `not false` | `e`, literal | double negation, literal |
| `neg (neg e)`, `neg k` | `e`, the literal `-k` where the vocabulary has one (`k` in −1, 0, 1) | double negation, literal |
| `abs (abs e)`, `abs (neg e)`, `abs k` | `abs e`, `abs e`, literal | idempotence, literal |
| `add e 0`, `add 0 e` | `e` | identity |
| `sub e 0`, `sub e e` | `e`, `0` | identity, annihilation |
| `mul e 1`, `mul 1 e`, `mul e 0`, `mul 0 e` | `e`, `0` | identity, absorption |
| `div e 1`, `div e 0`, `div e e` | `e`, error, `1` or error | identity, constant failure, constant |
| `mod e 1`, `mod e 0`, `mod e e` | `0`, error, `0` or error | constant, constant failure, constant |
| `eq e e`, `le e e`, `ge e e`, `lt e e`, `gt e e` | `true`, `true`, `true`, `false`, `false` | reflexivity |
| `and e e`, `or e e`, `and b e`, `or b e` (literal `b`) | `e`, `e`, `e` or literal | idempotence, literal |
| `cons (head e) (tail e)` | `e` | list eta |
| `head (cons a b)`, `tail (cons a b)` | `a`, `b` | constructor elimination |
| `is_empty (cons a b)`, `is_empty nil` | `false`, `true` | literal |
| `length (cons a b)`, `length nil` | `add 1 (length b)`, `0` | constructor elimination |
| `head nil`, `tail nil` | error | constant failure |
| `map f nil`, `filter f nil`, `fold f z nil` | `nil`, `nil`, `z` | empty traversal |
| `filter (λx. true) xs`, `filter (λx. false) xs` | `xs`, `nil` | literal predicate |
| `fold (λacc. λe. acc) z xs` | `z` | constant step |
| `zip nil e`, `zip e nil` | `nil` | empty traversal |
| `index i nil` | error | constant failure |
| `unfold (λs. true) h n x`, `unfold (λs. false) h n x` | `nil`, error | literal predicate |
| `fix1 x (λrec. λy. body)` with `rec` unused in `body` | `body[y := x]` | a β-redex in disguise (a let-binding: see below) |
| `fst (pair a b)`, `snd (pair a b)` | `a`, `b` | constructor elimination |
| `pair (fst p) (snd p)` | `p` | pair eta |

The filter is intentionally shallow: it refuses what a one-step rewrite would
remove. Deeper equivalences are left to observational equivalence, which prunes
them after one evaluation.

## Where a rule loses programs

Found by the adversarial review of the Phase 1 pull request and pinned in
[`tests/test_review_findings.py`](../tests/test_review_findings.py). The rules are those
of the registered run; repairing them changes what the engine enumerates and is deferred
to a new registration ([`RESULTS_P1.md`](../RESULTS_P1.md), "Adversarial review").

- **`and`, `or` are not commutative in the reference interpreter.** With
  `p = eq (head xs) 0` and `q = eq (length xs) 1`, `and p q` fails on `[]` and `and q p`
  is `false`. The canonical order can keep the failing one. The vectorised `and` and `or`
  are also strict (a failure on either side fails the result), so in the engine a guard
  written with `and` or `or` never protects its right side: a guarded conjunction is
  reachable only as `if g e false`, one symbol longer. Both registered vocabularies have
  `if`.
- **`neg k` has no literal replacement for `k` = 2 (both vocabularies) or 3, 4, 5
  (restored).** The values −2 to −5 are built from three symbols (`add -1 -1`, `mul -1 2`,
  `sub 0 2`) where `neg k` would be two, so every program that needs one is one symbol
  longer than the language allows.
- **`fix1` without recursion is a let-binding.** `fix1 x (λrec. λy. body)` shares the
  value of `x` among the occurrences of `y`. Its replacement `body[y := x]` repeats `x`:
  it is longer when `y` occurs twice or more and `x` is not small, and it may not be
  buildable at all (`body` lives in a two-binder context, where the engine builds no
  lambda). Refusing the form removes sharing from the language.
