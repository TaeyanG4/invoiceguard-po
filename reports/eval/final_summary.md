# FINAL results — evaluated ONCE after the freeze (configs/frozen_v1.json + frozen_v1_appendix.json @ 622c22c7)

Local RTX 4070 Ti SUPER, HF transformers NF4 (vision unquantised, patch-embed fp32), greedy, batch 1. SYNTHETIC data only.
Cell = strict field accuracy [95% bootstrap CI by base/family] / document exact / strict JSON validity (lenient fence-strip accuracy when JSON validity < 1).

| set | n | B0 OCR v1.2 | M0 2B NF4 | M1 2B NF4+LoRA |
|---|---:|---|---|---|
| trade:test | 40 | **0.210** [0.19–0.23] / 0.00 / 1.00 | **0.897** [0.85–0.94] / 0.62 / 1.00 | **0.921** [0.87–0.96] / 0.62 / 1.00 |
| public:iid_final\|clean | 20 | **0.731** [0.46–0.99] / 0.80 / 1.00 | **0.000** [0.00–0.00] / 0.00 / 0.00 (len 0.817) | **0.880** [0.78–0.96] / 0.65 / 1.00 |
| public:iid_final\|faded | 20 | **0.721** [0.45–0.98] / 0.80 / 1.00 | **0.000** [0.00–0.00] / 0.00 / 0.00 (len 0.529) | **0.851** [0.69–0.95] / 0.60 / 1.00 |
| public:iid_final\|bad_scan | 20 | **0.346** [0.15–0.56] / 0.10 / 1.00 | **0.000** [0.00–0.00] / 0.00 / 0.00 (len 0.466) | **0.798** [0.63–0.92] / 0.55 / 1.00 |
| public:ood_final\|clean | 20 | **0.000** [0.00–0.00] / 0.00 / 1.00 | **0.000** [0.00–0.00] / 0.00 / 0.00 (len 0.555) | **0.973** [0.94–0.99] / 0.75 / 1.00 |
| public:ood_final\|faded | 20 | **0.000** [0.00–0.00] / 0.00 / 1.00 | **0.000** [0.00–0.00] / 0.00 / 0.00 (len 0.000) | **0.905** [0.83–0.96] / 0.50 / 1.00 |
| public:ood_final\|bad_scan | 20 | **0.000** [0.00–0.00] / 0.00 / 1.00 | **0.000** [0.00–0.00] / 0.00 / 0.00 (len 0.058) | **0.756** [0.62–0.88] / 0.40 / 1.00 |

Own test by layout (field acc / doc exact): B0 T05 0.260/0.00, T06 0.153/0.00 · M0 T05 0.958/0.75, T06 0.828/0.50 · M1 T05 0.965/0.75, T06 0.870/0.50.

## Paired differences (A − B, identical documents, cluster bootstrap 95% CI)

| set | M1 − M0 | M1 − B0 |
|---|---|---|
| trade:test | +0.024 [-0.0008, 0.0502] | +0.711 [0.6682, 0.75] |
| public:iid_final\|clean | +0.880 [0.7841, 0.9595] | +0.149 [-0.1491, 0.4219] |
| public:iid_final\|faded | +0.851 [0.6859, 0.9548] | +0.130 [-0.2136, 0.418] |
| public:iid_final\|bad_scan | +0.798 [0.6309, 0.9217] | +0.452 [0.2093, 0.6887] |
| public:ood_final\|clean | +0.973 [0.9429, 0.9925] | +0.973 [0.9429, 0.9925] |
| public:ood_final\|faded | +0.905 [0.8333, 0.9567] | +0.905 [0.8333, 0.9567] |
| public:ood_final\|bad_scan | +0.756 [0.6192, 0.877] | +0.756 [0.6192, 0.877] |

## E3 findings on own test (40 docs; live findings from each arm's own extraction vs oracle findings on gold)

| arm | review rate | per code TP/FP/FN |
|---|---|---|
| B0 OCR v1.2 | 1.0 | AMBIGUOUS_QUANTITY 0/85/2, DUPLICATE_SKU 0/0/4, MISSING_CRITICAL_FIELD 0/255/0, PO_LINE_NOT_FOUND 2/166/0, QTY_DIFF 0/0/6, TOTAL_ARITHMETIC_MISMATCH 0/10/0, TOTAL_CHECK_NOT_EVALUABLE 0/23/0, UNIT_PRICE_DIFF 0/0/10, UNKNOWN_SKU 0/0/2, UNSUPPORTED_ROW_COUNT 0/22/0 |
| M0 2B NF4 | 0.65 | AMBIGUOUS_QUANTITY 1/0/1, DUPLICATE_SKU 4/0/0, LINE_ARITHMETIC_MISMATCH 0/18/0, PO_LINE_NOT_FOUND 2/3/0, QTY_DIFF 5/1/1, TOTAL_ARITHMETIC_MISMATCH 0/3/0, UNIT_MISMATCH 0/1/0, UNIT_PRICE_DIFF 10/13/0, UNKNOWN_SKU 2/2/0 |
| M1 2B NF4+LoRA | 0.675 | AMBIGUOUS_NUMBER 0/1/0, AMBIGUOUS_QUANTITY 0/0/2, DUPLICATE_SKU 4/0/0, LINE_ARITHMETIC_MISMATCH 0/19/0, PO_LINE_NOT_FOUND 2/6/0, QTY_DIFF 5/2/1, TOTAL_ARITHMETIC_MISMATCH 0/5/0, UNIT_MISMATCH 0/1/0, UNIT_PRICE_DIFF 10/15/0, UNKNOWN_SKU 2/4/0 |

## What the final supports (and what it does not)
- Unseen own layouts (T05/T06): the rule-based OCR baseline collapses (0.21) because its header vocabulary only knows train/dev layouts; M0 and M1 generalise (0.90/0.92). M1−M0 = +0.024 [−0.001, 0.050] — **not significant** on 40 documents.
- Public IID clean/faded: M1 vs B0 not significant; bad_scan +0.45 (significant). Public OOD (freelancer): M1 0.97/0.91/0.76 vs B0 0 and M0 0 (strict; M0 fences everything on public).
- M0's public failures are format (```json fences, 0% strict validity); lenient scores show partial reading ability (0.82 IID clean, 0.55 OOD clean). M1's public gain is format + reading together; conditional/lenient columns separate them.
- Risk that remains: M1 turned ambiguous quantities into numbers on test too (AMBIGUOUS_QUANTITY recall 0/2) and extraction errors create many false warnings (UNIT_PRICE_DIFF FP 15, LINE_ARITHMETIC FP 19). The product therefore keeps every document in human review; arithmetic warnings are the safety net.
- Small n (20 bases per public set, 40 own families, per-code counts 1–10) → case evidence; synthetic data → no claim about real customs documents.
- Not measured here: serving-framework throughput (S6), cloud cost (S9).
