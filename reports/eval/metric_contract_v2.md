# Metric contract v2 (docs/19 #5) — implemented 2026-11-14

| Metric | Definition | Denominator | Role |
|---|---|---|---|
| strict JSON validity | response is exactly one JSON object (whitespace allowed); no fence strip, no truncation repair; `finish_reason=length` = truncated | all attempted documents | **primary** |
| strict field accuracy (E1/E2) | per-field EM over all gold scored fields; failed/invalid documents score every field wrong | all scored gold fields of all attempted documents | **primary** |
| conditional_on_valid_json | the same field accuracy restricted to documents whose strict parse succeeded | scored fields of strictly valid documents (document count reported) | secondary — separates reading from format |
| lenient_fence_strip | identical scoring after removing exactly one surrounding ```json fence; truncation and syntax are NOT repaired | all attempted documents (`repaired_documents` reported) | secondary, never mixed into primary |

Implementation: `invoiceguard.evaluation.aggregate()` (`conditional_on_valid_json`) and `strict_and_lenient()`; test `tests/test_evaluation.py::test_metric_contract_v2_strict_vs_lenient_and_conditional`.
