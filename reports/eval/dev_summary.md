# S5 dev summary (frozen config v1, HF NF4, batch 1) — DEV ONLY, not final

Cell = strict field accuracy / document exact / strict JSON validity (lenient fence-strip field accuracy). Each set is scored separately; stress sets are dev-only and never pooled.

| set | n | B0 OCR v1.2 | M0 base NF4 | M1 QLoRA v1 |
|---|---:|---|---|---|
| trade:dev | 24 | 0.911 / 0.54 / 1.00 (len 0.911) | 0.921 / 0.58 / 1.00 (len 0.921) | 0.968 / 0.71 / 1.00 (len 0.968) |
| stress:blur_jpeg | 24 | 0.124 / 0.00 / 1.00 (len 0.124) | 0.000 / 0.00 / 0.00 (len 0.885) | 0.932 / 0.67 / 1.00 (len 0.932) |
| stress:fade_noise | 24 | 0.217 / 0.00 / 1.00 (len 0.217) | 0.064 / 0.08 / 0.08 (len 0.895) | 0.930 / 0.67 / 1.00 (len 0.930) |
| stress:skew_lowres | 24 | 0.180 / 0.00 / 1.00 (len 0.180) | 0.167 / 0.08 / 0.17 (len 0.908) | 0.932 / 0.62 / 1.00 (len 0.932) |
| public:dev|clean | 20 | 0.967 / 0.85 / 1.00 (len 0.967) | 0.000 / 0.00 / 0.00 (len 0.841) | 0.967 / 0.80 / 1.00 (len 0.967) |
| public:dev_stress|faded | 8 | 0.933 / 0.50 / 1.00 (len 0.933) | 0.000 / 0.00 / 0.00 (len 0.629) | 1.000 / 1.00 / 1.00 (len 1.000) |
| public:dev_stress|bad_scan | 8 | 0.562 / 0.00 / 1.00 (len 0.562) | 0.000 / 0.00 / 0.00 (len 0.448) | 0.705 / 0.50 / 1.00 (len 0.705) |

## Paired differences (cluster bootstrap 95% CI; clusters = public base / trade family)

| set | M1−M0 field acc | M1−B0 field acc | M1−B0 doc exact |
|---|---|---|---|
| trade:dev | +0.047 [0.0016, 0.1121] | +0.058 [-0.0242, 0.1544] | +0.167 [-0.125, 0.4167] |
| stress:blur_jpeg | +0.932 [0.8629, 0.9907] | +0.808 [0.7277, 0.8836] | +0.667 [0.4583, 0.8333] |
| stress:fade_noise | +0.867 [0.7619, 0.9579] | +0.714 [0.5994, 0.8129] | +0.667 [0.4583, 0.8333] |
| stress:skew_lowres | +0.765 [0.6082, 0.9078] | +0.751 [0.6865, 0.8091] | +0.625 [0.4167, 0.8333] |
| public:dev|clean | +0.968 [0.9217, 0.9961] | +0.000 [-0.0631, 0.0563] | -0.050 [-0.3, 0.2] |
| public:dev_stress|faded | +1.000 [1.0, 1.0] | +0.067 [0.0187, 0.1724] | +0.500 [0.125, 0.875] |
| public:dev_stress|bad_scan | +0.705 [0.4, 0.9649] | +0.143 [-0.0223, 0.5769] | +0.500 [0.125, 0.875] |

## E3 on trade:dev (24 docs; oracle review rate 14/24 = 0.583)

| arm | review rate | failed rate | per-code TP/FP/FN |
|---|---|---|---|
| B0 OCR v1.2 | 0.625 | 0.0 | AMBIGUOUS_NUMBER 0/3/0, AMBIGUOUS_QUANTITY 1/1/0, DUPLICATE_SKU 2/0/0, LINE_ARITHMETIC_MISMATCH 0/3/0, PO_LINE_NOT_FOUND 1/9/0, QTY_DIFF 3/1/1, TOTAL_CHECK_NOT_EVALUABLE 0/6/0, UNIT_PRICE_DIFF 5/2/1, UNKNOWN_SKU 1/5/0, UNSUPPORTED_ROW_COUNT 0/1/0 |
| M0 base NF4 | 0.166667 | 0.708333 | AMBIGUOUS_QUANTITY 0/0/1, DUPLICATE_SKU 0/0/2, MISSING_CRITICAL_FIELD 0/3/0, PO_LINE_NOT_FOUND 0/0/1, QTY_DIFF 1/0/3, UNIT_PRICE_DIFF 1/0/5, UNKNOWN_SKU 0/0/1 |
| M1 QLoRA v1 | 0.666667 | 0.0 | AMBIGUOUS_QUANTITY 0/0/1, DUPLICATE_SKU 2/0/0, LINE_ARITHMETIC_MISMATCH 0/4/0, PO_LINE_NOT_FOUND 1/1/0, QTY_DIFF 4/3/0, TOTAL_ARITHMETIC_MISMATCH 0/2/0, UNIT_PRICE_DIFF 6/1/0, UNKNOWN_SKU 1/0/0 |

## Reading

- Clean documents: M1 and B0 are statistically indistinguishable (public clean 0.0 [−0.063, 0.056]; own clean +0.058 [−0.024, 0.154]). OCR + rules is enough for clean renders.
- Degraded documents: M1 beats B0 by +0.71 to +0.81 field accuracy on every own stress variant; B0 collapses (0.12–0.22).
- M0's low strict scores are largely FORMAT: it wraps JSON in ```json fences (public and stressed docs) and is schema-invalid on 71% of clean own docs; lenient scores (0.84–0.91) show it can read. M1's gain therefore mixes format and reading; the conditional and lenient columns separate them.
- Small n: 20 public bases, 24 own families per set; per-code E3 counts are 1–7 → case evidence only.

## Failure analysis (M1 v1, `failures_m1_dev_v1.md`) and the ONE fix
- ambiguous quantity in a narrow, wrapped quantity cell (T04 `tr_7d3690b30c40`, '100 cartons / 2000 pcs') turned into a number ('500'/'100') in all 4 variants, with a dropped row in 3 — the most dangerous error (contract: never force a quantity). The line-arithmetic check still sends it to review.
- last row dropped on a 7-row document under all three stress variants (`tr_f2882769a6fc`); train had only 3 seven-row documents.
- thousands separator dropped in totals ('1,230.84' -> '1230.84'): raw EM error, value correct, no effect on findings.
- Fix chosen (one change): train-only augmentation `manifests/trade_raw_aug1.jsonl` (32 families on T01–T03: 16 ambiguous_quantity, 16 normal with 6–7 rows), same training config → M1 v2. Adopt only if dev improves; final/test untouched.
