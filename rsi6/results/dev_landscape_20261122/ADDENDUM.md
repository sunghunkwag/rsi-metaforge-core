# Addendum: the scan on all nine categories, and reading 1

Written 2026-11-22, 22:10 UTC. **Provisional in one respect:** seventeen of the eighteen jobs
of `dev-landscape` are in; the job of set covering with seed 730001 was still running after
three hours. Set covering therefore has three of its four seeds below. The files are in
`provisional/`; the final ones replace them, under the names `README.md` gives, when that job
is in, and `artifacts/landscape.tar.gz` is added then.

## Reading 1 of `PREDICTION.md`

The first choice, `assess.holdback` 0.25 → 0.3, on the three categories it was made without, in
the scan itself (`provisional/reading_1_provisional.json`):

| | |
|---|---|
| m3 | −0.0602 |
| p3 | 0.918 (78 of the 85 changes are at or above it) |
| knapsack (8 seeds) | −0.0006 |
| partitioning (4) | −0.0030 |
| set covering (3 of 4) | −0.177 |

**It does not carry to the three.** Both readings that `PREDICTION.md` fixed for its choice are
negative; only its warning held. For the one job still missing to turn m3 above zero, set
covering would need about +0.54 on its fourth seed, more than the whole gain of generation 0
there (+0.46 to +0.48).

On those same three categories the change with the largest mean of all 85 is `model.batch` 2
(+0.053), which was on the list of comparisons, not the choice.

## The scan with every category in

For the record; nothing was fixed about this beforehand, and the new seeds of `README.md` are
the better evidence (`provisional/loco_nine_provisional.json`).

Leaving each of the nine categories out in turn, the statistic of amendment 2 on the other
eight chooses **`model.batch` 2 in all nine folds**:

| Left out | On the category left out | Place among the 85 changes there |
|---|---|---|
| set covering (3 seeds) | +0.147 | 1.00 |
| quadratic assignment | +0.049 | 0.88 |
| job shop | +0.034 | 0.89 |
| partitioning | +0.008 | 0.99 |
| p-median | +0.007 | 0.94 |
| knapsack | +0.004 | 0.96 |
| bin packing | −0.000 | 0.39 |
| forecasting, regression | 0 | |

Mean +0.0276; resampling seeds gives a 5 % point of −0.0097 (the three seeds of set covering
make it wide) and chooses `model.batch` 2 in 87.5 % of the folds; shuffling the changes within
every category and repeating the procedure reaches +0.0276 in 0.05 % of 2000 shuffles. So the
scan of eight seeds, once it had all nine categories, pointed at the change that 64 new seeds
per category (32 on the two heavy ones) had by then confirmed; with six categories it had
pointed at another.

Job shop and quadratic assignment in this table carry generation 0's bad luck on the scan's
seeds (`README.md`, section 3): on new seeds the same change is at −0.005 and +0.019 there.

## Picking by the training score, nine categories

`provisional/train_pick_provisional.json`, as section 4 of `README.md`: set covering +0.142 (3
seeds, all above), quadratic assignment +0.094, job shop +0.067, p-median +0.027, knapsack
+0.012, bin packing +0.002, partitioning −0.007 (2 seeds above, 2 below), forecasting −0.003,
regression −0.007. An upper reference at 86 times the compute, as said there.
