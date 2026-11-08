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
  the left argument precedes the right one in pool order (`add b a -> add a b`).

## Rewrite rules (left-hand side refused)

| Refused | Equivalent | Why |
| --- | --- | --- |
| `if true a b`, `if false a b` | `a`, `b` | literal condition |
| `if (not c) a b` | `if c b a` | negated condition |
| `if c a a` | `a` | same branches |
| `if c (if c a b) d`, `if c d (if c a b)` | `if c a d`, `if c d b` | repeated condition |
| `not (not e)`, `not true`, `not false` | `e`, literal | double negation, literal |
| `neg (neg e)`, `neg k` | `e`, literal | double negation, literal |
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
| `fix1 x (λrec. λy. body)` with `rec` unused in `body` | `body[y := x]` | a β-redex in disguise |
| `fst (pair a b)`, `snd (pair a b)` | `a`, `b` | constructor elimination |
| `pair (fst p) (snd p)` | `p` | pair eta |

The filter is intentionally shallow: it refuses what a one-step rewrite would
remove. Deeper equivalences are left to observational equivalence, which prunes
them after one evaluation.
