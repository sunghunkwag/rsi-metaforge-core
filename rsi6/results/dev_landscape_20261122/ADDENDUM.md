# Addendum: the scan on all nine categories, and reading 1

Final: all eighteen jobs of `dev-landscape` are in (the last one, set covering with seed 730001,
finished at 23:06 UTC after nearly four hours; a first version of this file, written at 22:10
UTC with three of the four seeds of set covering, said what was provisional). `artifacts/landscape.tar.gz`
has the eighteen artifacts.

## Reading 1 of `PREDICTION.md`

The first choice, `assess.holdback` 0.25 → 0.3, on the three categories it was made without, in
the scan itself (`reading_1.json`):

| | |
|---|---|
| m3 | −0.0450 |
| p3 | 0.894 (76 of the 85 changes are at or above it) |
| knapsack (8 seeds) | −0.0006 |
| partitioning (4) | −0.0030 |
| set covering (4) | −0.131 |

**It does not carry to the three.** Both readings that `PREDICTION.md` fixed for its choice are
negative; only its warning held.

On those same three categories `model.batch` 2, which was on the list of comparisons and not
the choice, has the second largest mean of all 85 changes (+0.071) and the largest of those
within the CPU limit (`shortlist` 1 is at +0.075 and costs 1.7 times the CPU).

## The scan with every category in

For the record; nothing was fixed about this beforehand, and the new seeds of `README.md` are
the better evidence (`loco_nine_categories.json`).

Leaving each of the nine categories out in turn, the statistic of amendment 2 on the other
eight chooses **`model.batch` 2 in all nine folds**:

| Left out | On the category left out | Place among the 85 changes there |
|---|---|---|
| set covering (4 seeds) | +0.201 | 0.99 |
| quadratic assignment | +0.049 | 0.88 |
| job shop | +0.034 | 0.89 |
| partitioning | +0.008 | 0.99 |
| p-median | +0.007 | 0.94 |
| knapsack | +0.004 | 0.96 |
| bin packing | −0.000 | 0.39 |
| forecasting, regression | 0 | |

Mean +0.0337; resampling seeds gives a 5 % point of −0.0007 (the four seeds of set covering
make it wide); shuffling the changes within every category and repeating the procedure reaches
+0.0337 in 0.1 % of 2000 shuffles. So the scan of eight seeds, once it had all nine categories,
pointed at the change that 64 new seeds per category (32 on the two heavy ones) had by then
confirmed; with six categories it had pointed at another.

Job shop and quadratic assignment in this table carry generation 0's bad luck on the scan's
seeds (`README.md`, section 3): on new seeds the same change is at −0.005 and +0.019 there.

## Picking by the training score, nine categories

`train_pick.json`, as section 4 of `README.md`: set covering +0.218 (4 seeds, all above),
quadratic assignment +0.094, job shop +0.067, p-median +0.027, knapsack +0.012, bin packing
+0.002, partitioning −0.007 (2 seeds above, 2 below), forecasting −0.003, regression −0.007. An
upper reference at 86 times the compute, as said there.
