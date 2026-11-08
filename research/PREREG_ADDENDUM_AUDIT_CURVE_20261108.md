# Pre-run addendum: audit-family learning curve (no gate relaxation)

This addendum is committed **before any implementation execution or audit evaluation**. It extends, but does not relax, the preregistration in `research/PREREG_EXTERNAL_METACONTROL_20261108.md` (commit `a576be9cd4831f9ec9c29a70ba98b237dfec15af`).

After all support updates and development decisions have been frozen, evaluate the **same external audit tasks** with separately snapshotted controllers from generations 1, 2 and 3 in ONE audit run. Never allow any audit outcome to update weights or choose hyperparameters. Use the same paired seed-specific random proposal tape for each audit checkpoint so fixed baselines cannot appear to learn from random reseeding. Final audit task IDs remain fixed to manifest blob `c27b1c6431ab9d836c94f9ddc66269fd4216a1e0`.

**Additional mandatory gate:** the adaptive persistent controller's OOD success-rate margin over the strongest frozen baseline on the never-seen audit families must be nondecreasing at checkpoints 1, 2 and 3, and final minus initial margin >= **5 percentage points**. Also report per-checkpoint wins/losses/ties against every baseline, especially single-generation equal-total-compute and memory-wiped controls.

Training-input VM calls must be exactly matched for each candidate evaluation during audit. Every arm must receive the same task × trajectory × checkpoint schedule. Compute limitations and paired bootstrap intervals are unchanged.

If there is no growth, or if the negative control appears to satisfy the full success gate, the experiment fails regardless of the last checkpoint's absolute score.
