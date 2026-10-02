# Legacy boundary audit

Read `docs/P_RESULT.md` before implementation. It reports coupling trajectory
`[0,3,3,3,3,3,3]`, no admitted extensions and an empty final ISA. Its positive
controls are explicitly designer-supplied extension-requiring tasks.

Verified against the current 49,316-line `rsi_levels_metaforge_unified.py`:

| Boundary | Runtime evidence |
| --- | --- |
| Archived source | Five AST string constants span lines 17174–37514; explicit subsystem loading is required to execute them. They are not K–P loop implementations. |
| Straight-line ascent VM | `OP_NAMES` at 151 contains 34 ops; `ak_run_tokens` at 42077 iterates base tokens and dispatches `OP_IMPL`. No general branching, user functions or recursion. |
| Solver subset | `SC_SOLVER_VOCAB` at 38484 has 21 ops; expanded length cap is 200 at 38436. |
| Fold forge | 7991–8113 fixes three integer state slots, one pass, six tree operators and depth 4. These terms do not become base ascent tokens. |
| Dormant catalog | 6010–6029 stocks BCAST and ZGT; Phase P freezes catalog behavior at 47792. |
| Setter closure | `AKSetterLineage.propose` at 42540 builds tasks and witnesses from SC unit grammars and adopted archive bodies. Base executor rejects extension tokens. |
| Phase O | Channel A at 47174 supplies three prewritten candidates, including MOD and MOD+SELECT. Channel B at 47034 supplies two predefined pruning schemas. Six MOD tasks are predefined at 46915. |
| Self-edit | 13125–13147 declares three capabilities; frontier examples are designer-written at 13150. |
| Feature bank | Section 24 at 14190 supplies six handwritten features. Candidate selection consults sealed/counterfactual gates at 14374. |

These support the Owner's stated closure concerns. RSI-2 imports none of this
runtime and changes no existing source or documents. The existing filtered
`no_dynamic` test passed; its runner prints the aggregate 286-test banner even
for a filter, so this is one selected test, not a full-suite reproduction.
