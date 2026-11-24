# Development check D2 of design r (the relay), repeated on 2026-11-22

Development only: categories of the source pool, scratch ledgers, nothing here is evidence.
The check is D2 of `rsi6/audit/design_panel_20261116/synthesize.json` (`development_checks`).
Its outputs of 2026-11-16 were never committed, so it was run again as
`python -m rsi6.open.dev_d2` (the measurement of `results/dev_r_20261116/scripts/dev_r_d2.py`
with paths as arguments) on GitHub-hosted runners: plan `rsi6/runs/dev-d2.json`, workflow run
45029175395, commit `20d48b1`, Python 3.13.18 and NumPy 2.5.3, one job per left-out category,
every arm of a category on one machine (AMD EPYC 7763 or 9V74, 4 CPUs).

For each left-out category: 8 chains of 8 acquisitions over the other categories at training
budget 200, then on the left-out category the relay (the memory the chain left), the frozen
learner (no memory) and the shuffled placebo, 2 seeds per chain.

| left-out category | relay − frozen | se | shuffled − frozen | relay / frozen CPU |
|---|---|---|---|---|
| quadratic assignment | −0.0095 | 0.0071 | −0.0036 | 1.02 |
| job shop | −0.0120 | 0.0110 | −0.0087 | 0.98 |
| p-median | −0.0018 | 0.0093 | −0.0047 | 0.94 |
| **24 chains pooled** | **−0.0078** | 0.0052 | −0.0057 (se 0.0041) | |

The 80% interval of the pooled development effect is −0.0147 to −0.0010: on a category it has
not met, the learner that carries the relay's memory acquires less than the learner that
carries nothing, on all three left-out categories. The relay is no better than its shuffled
placebo (−0.0021, se 0.0041). The prior the memory builds does not point at what the next
acquisition will find useful (prospective Spearman +0.04 for the rule dplus and +0.05 for
dmean, 164 acquisitions) and stays close to uniform (median top-3 mass 0.19). The library holds
a median of 14 blocks. sigma-hat 0.0252, tau-hat 0.0192. No instance scored 0 in any arm.

The rules written before the check (`synthesize.json`), applied to these numbers
(`pooled.json`):

* (b) library median at least 2: holds; splicing stays.
* (c) dmean's prospective correlation is not more than 0.1 above dplus's: dplus stays.
* (d) the median top-3 mass is below 0.30: alpha would be raised to 2.0.
* (e) "do not register" needs both L2_dev below 0.003 and the upper 80% bound of the
  development effect below 0.003. The second holds (−0.0010); the first does not (L2_dev is
  +0.0125 in the repeated D1). By the letter of the rule the experiment is still to be
  registered.

What the rule does not say and the numbers do: the registered experiment's primary endpoint is
this same comparison, relay minus frozen, on four categories no process has used, and in
development it is negative. The design's own prediction for that endpoint was +0.002 with about
one chance in four of being met. Registering the experiment would spend the four held-out
categories, which can be used once, on a comparison whose development value is below zero.
Whether to register it is the Owner's decision; it was not registered here.

Files: the three summaries as the runners wrote them (`dev_r_d2n_*.json`), the pooled numbers
and rules (`pooled.json`), and every record the three scratch ledgers added to their copy of
the committed ledger (`records.jsonl.gz`, 558 records).
