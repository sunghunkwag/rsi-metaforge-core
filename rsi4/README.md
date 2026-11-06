# RSI-4: a four-loop continual learner, judged by J

RSI-4 extends the latest scored RSI-3 arm (RSI3_META_HONEST, on
`rsi3/analogy` at 1e6868a) into a continual learner with four loops (instant
adaptation inside a task's budget, experience writing, sleep, rule
improvement), measured on new task streams by an external judge J that the
system cannot reach. The Owner's directive is
[OWNER_DIRECTIVE.md](OWNER_DIRECTIVE.md); the design is
[ARCHITECTURE.md](ARCHITECTURE.md).

| Phase | What | Status |
| --- | --- | --- |
| 0 | Harness before agent: stages and J pools, J, sealing audit, workflow, red-team R1–R3 | **Gate 0 passed** ([RESULTS_P0.md](RESULTS_P0.md)) |
| 1 | Reproduce the base arm; measure forgetting (B0, B1, B2) | next |
| 2 | Loops 1 and 2: compute controller C and fast store (L12, A1–A3) | — |
| 3 | Loop 3: J's sleep check (L123, A4, R4) | — |
| 4 | Loop 4: rule rounds, final test (R5–R7) | — |

## Quick start

```bash
python -m unittest discover -s rsi4/tests -t .          # J, sealing and red-team tests
python -m rsi4.judge.replay rsi4/ledger/judge_log.jsonl  # recompute every logged J decision
```

Rebuilding the pools from DreamCoder's source (fetched once, not committed):

```bash
curl -sSLo /tmp/list_tasks2.json https://raw.githubusercontent.com/ellisk42/ec/cb0e63f5c33cd2de360b791038b0f5272750270e/data/list_tasks2.json
python -m rsi4.judge.pools --source /tmp/list_tasks2.json --check
RSI4_LIST_TASKS2=/tmp/list_tasks2.json python -m unittest rsi4.tests.test_redteam_r2
```

Long runs go to GitHub Actions: push a branch `rsi4/run-<name>` holding the
plan `rsi4/runs/<name>.json` (`.github/workflows/rsi4-runs.yml`).

## Layout

```
rsi4/
  OWNER_DIRECTIVE.md, archive/OWNER_DIRECTIVE_v2.md
  README.md, ARCHITECTURE.md, RESULTS_P0.md
  client.py      the one door to J (spawned process)
  guard.py       run-time audit hook: the agent process cannot open, list or import J
  watchdog.py    RSS cap (3 GB) per worker; a breach stops the worker and is logged
  data/stage_train.json   3 x 36 stage-train tasks
  judge/         J: registry, pools, evaluate, sleep_check, adopt, metrics, ledger,
                 replay, audit, service; pools/, seed.json, MANIFEST.sha256
  tests/
```

All copyright and attribution: Intelligence Research Project.
