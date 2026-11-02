# SWARM report

Crossing curves of self-posed task archives under the frozen kernel. Not a benchmark result.

## Crossing curves X(g)

| Arm | Seed | G | X(G) | ΔX by generation | last-half second differences | peak ΔX (gen) | Builder candidates |
| --- | --- | --- | --- | --- | --- | --- | --- |
| SWARM_FULL | 11 | 9 | 0 | 0 0 0 0 0 0 0 0 0 | 0 0 0 0 | 0 (g1) | 24000 |
| SWARM_RECORDS | 11 | 9 | 0 | 0 0 0 0 0 0 0 0 0 | 0 0 0 0 | 0 (g1) | 24000 |
| SWARM_NO_MAPPER | 11 | 9 | 0 | 0 0 0 0 0 0 0 0 0 | 0 0 0 0 | 0 (g1) | 24000 |
| SWARM_NO_SELFEDIT | 11 | 11 | 0 | 0 0 0 0 0 0 0 0 0 0 0 | 0 0 0 0 0 | 0 (g1) | 32000 |
| SWARM_NO_BREAKER_REGRET | 11 | 9 | 2 | 0 0 0 0 2 0 0 0 0 | -2 0 0 0 | 2 (g5) | 26574 |
| SWARM_SHUFFLED_FIELD | 11 | 8 | 1 | 0 0 0 0 0 0 0 1 | 0 0 0 1 | 1 (g8) | 23937 |

## Frontier motion

| Arm | Seed | archive | crossed | open | markers | fraction crossed | never crossed | mean gens-to-crossing | mean Kb margin |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| SWARM_FULL | 11 | 43 | 0 | 38 | 5 | 0.000 | 1.000 | - | 0.384 |
| SWARM_RECORDS | 11 | 43 | 0 | 38 | 5 | 0.000 | 1.000 | - | 0.384 |
| SWARM_NO_MAPPER | 11 | 43 | 0 | 38 | 5 | 0.000 | 1.000 | - | 0.384 |
| SWARM_NO_SELFEDIT | 11 | 52 | 0 | 36 | 16 | 0.000 | 1.000 | - | 0.416 |
| SWARM_NO_BREAKER_REGRET | 11 | 31 | 2 | 24 | 5 | 0.065 | 0.935 | 2.00 | 0.427 |
| SWARM_SHUFFLED_FIELD | 11 | 38 | 1 | 37 | 0 | 0.026 | 0.974 | 2.00 | 0.406 |

## Substrate growth

| Arm | Seed | primitives forged | library entries | learned entries | self-edits adopted / proposed | regressions caught | adopted edits (gen: kind, solves) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| SWARM_FULL | 11 | 1 | 0 | 0 | 1 / 9 | 0 | g9: forge 0->1 |
| SWARM_RECORDS | 11 | 1 | 0 | 0 | 1 / 9 | 0 | g9: forge 0->1 |
| SWARM_NO_MAPPER | 11 | 1 | 0 | 0 | 1 / 9 | 0 | g9: forge 0->1 |
| SWARM_NO_SELFEDIT | 11 | 0 | 0 | 0 | 0 / 0 | 0 | - |
| SWARM_NO_BREAKER_REGRET | 11 | 1 | 1 | 1 | 1 / 9 | 0 | g4: forge 0->2 |
| SWARM_SHUFFLED_FIELD | 11 | 1 | 0 | 0 | 1 / 8 | 0 | g7: forge 0->1 |

## Channel and collapse detectors

| Arm | Seed | retrieval hit rate | breaker norm | builder norm | mapper pairs | mapper residual | proposals | admitted | rejections | Kb rejection rate | wake failures |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| SWARM_FULL | 11 | - | 0.086 | 0.037 | 0 | - | 49 | 43 | Kb:5 Kc:1 | 0.102 | 3 |
| SWARM_RECORDS | 11 | - | 0.000 | 0.000 | - | - | 49 | 43 | Kb:5 Kc:1 | 0.102 | 3 |
| SWARM_NO_MAPPER | 11 | - | 0.086 | 0.037 | - | - | 49 | 43 | Kb:5 Kc:1 | 0.102 | 3 |
| SWARM_NO_SELFEDIT | 11 | - | 0.084 | 0.038 | 0 | - | 60 | 52 | K0:1 Kb:5 Kc:2 | 0.083 | 3 |
| SWARM_NO_BREAKER_REGRET | 11 | 1.000 | 0.053 | 0.079 | 2 | 0.478 | 50 | 31 | Kb:7 Kc:12 | 0.140 | 2 |
| SWARM_SHUFFLED_FIELD | 11 | 1.000 | 0.087 | 0.042 | 1 | 0.500 | 43 | 38 | Kb:4 Kc:1 | 0.093 | 2 |

## Logical budget (cumulative candidate evaluations / interpreter steps)

| Arm | Seed | Breaker steps | Builder candidates | Builder steps | Kernel candidates | Kernel steps | wall seconds |
| --- | --- | --- | --- | --- | --- | --- | --- |
| SWARM_FULL | 11 | 42855 | 24000 | 9012949 | 62056 | 14281305 | 2126 |
| SWARM_RECORDS | 11 | 42855 | 24000 | 9012949 | 62056 | 14281305 | 2127 |
| SWARM_NO_MAPPER | 11 | 42855 | 24000 | 9012949 | 62056 | 14281305 | 2126 |
| SWARM_NO_SELFEDIT | 11 | 53432 | 32000 | 8342321 | 20936 | 4909340 | 1938 |
| SWARM_NO_BREAKER_REGRET | 11 | 116792 | 26574 | 10657163 | 42245 | 9953320 | 1867 |
| SWARM_SHUFFLED_FIELD | 11 | 35113 | 23937 | 8494971 | 58663 | 13645107 | 1859 |

## Decisive comparisons

| # | Comparison | Rule | Per seed | Passes |
| --- | --- | --- | --- | --- |
| K1 | SWARM_FULL vs SWARM_NO_SELFEDIT | X_S0(G) > X_other(G) on every seed: substrate change produces crossings | seed 11: [0, 0] | no |
| K2 | SWARM_FULL vs SWARM_RECORDS | X_S0(G) > X_other(G) on every seed: the latent channel beats records | seed 11: [0, 0] | no |
| K3 | SWARM_FULL vs SWARM_NO_MAPPER | X_S0(G) > X_other(G) on every seed: the mapper matters | seed 11: [0, 0] | no |
| K4 | SWARM_FULL vs SWARM_SHUFFLED_FIELD | X_S0(G) > X_other(G) on every seed: the channel carries information | seed 11: [0, 1] | no |
| K5 | SWARM_FULL vs SWARM_NO_BREAKER_REGRET | mean generations-to-crossing lower and never-crossed fraction lower in S0, every seed | seed 11: {"mean_generations_to_crossing": [null, 2.0], "never_crossed_fraction": [1.0, 0.9354838709677419]} | no |
| K6 | SWARM_FULL compounding | second difference of X(g) >= 0 over the last half of the run on every seed | seed 11: {"passes": true, "last_half_second_differences": [0, 0, 0, 0], "sum_last_half": 0, "peak_increment_generation": 1, "peak_increment": 0} | yes |
