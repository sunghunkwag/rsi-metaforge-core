"""The continual-learning score matrix and its metrics (OWNER_DIRECTIVE.md §6).

R[i][j] = stage-eval tasks of stage j (of 100) solved by the learned solver at
B_eval = 64 after training through stage i; i = 0 is the checkpoint after
TRAIN only. A task counts when solved on at least 2 of 3 seeds.

    ACC = mean_j R[3][j]                                      (j = 1, 2, 3)
    BWT = mean_{j in 1,2} R[3][j] - R[j][j]
    FGT = mean_{j in 1,2} max(0, max_{i in [j, 2]} R[i][j] - R[3][j])
    FWT = mean_{j in 2,3} R[j-1][j] - R[0][j]

Each carries a 95% percentile bootstrap interval over tasks: 10,000
resamples, the 100 tasks of each stage resampled with replacement and the
same resample applied to every R[i][j] of that stage (the tasks are paired
across checkpoints). The resampling seed is fixed here.
"""
from __future__ import annotations

import numpy as np

BOOTSTRAP_RESAMPLES = 10_000
BOOTSTRAP_SEED = 20261106
STAGES = (1, 2, 3)
CHECKPOINTS = (0, 1, 2, 3)


def _metrics(counts) -> dict:
    """counts[i][j] (arrays over resamples, or scalars) -> the four metrics."""
    acc = sum(counts[3][j] for j in STAGES) / 3.0
    bwt = sum(counts[3][j] - counts[j][j] for j in (1, 2)) / 2.0
    fgt = sum(np.maximum(0.0, np.max(np.stack([np.asarray(counts[i][j], dtype=float)
                                               for i in range(j, 3)]), axis=0)
                         - counts[3][j]) for j in (1, 2)) / 2.0
    fwt = sum(counts[j - 1][j] - counts[0][j] for j in (2, 3)) / 2.0
    return {"ACC": acc, "BWT": bwt, "FGT": fgt, "FWT": fwt}


def score_matrix(outcomes: dict) -> dict:
    """outcomes[(i, j)] = {task: solved} -> R[i][j] counts, checking the task sets agree."""
    for j in STAGES:
        names = {frozenset(outcomes[(i, j)]) for i in CHECKPOINTS}
        if len(names) != 1:
            raise ValueError(f"stage {j}: checkpoints were evaluated on different tasks")
    return {i: {j: int(sum(outcomes[(i, j)].values())) for j in STAGES} for i in CHECKPOINTS}


def compute(outcomes: dict) -> dict:
    R = score_matrix(outcomes)
    point = {k: float(v) for k, v in _metrics(R).items()}
    rng = np.random.default_rng(BOOTSTRAP_SEED)
    sampled = {i: {} for i in CHECKPOINTS}
    for j in STAGES:
        names = sorted(outcomes[(0, j)])
        index = rng.integers(0, len(names), size=(BOOTSTRAP_RESAMPLES, len(names)))
        for i in CHECKPOINTS:
            solved = np.asarray([1.0 if outcomes[(i, j)][n] else 0.0 for n in names])
            sampled[i][j] = solved[index].sum(axis=1)
    boot = _metrics(sampled)
    intervals = {k: [float(np.percentile(v, 2.5)), float(np.percentile(v, 97.5))]
                 for k, v in boot.items()}
    return {"R": {str(i): {str(j): R[i][j] for j in STAGES} for i in CHECKPOINTS},
            "point": point, "ci95": intervals, "resamples": BOOTSTRAP_RESAMPLES,
            "seed": BOOTSTRAP_SEED}
