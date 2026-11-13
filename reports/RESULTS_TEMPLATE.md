# InvoiceGuard-PO v3 — 결과 보고서 템플릿

이 템플릿은 `not_run`으로 시작한다. 실행 후 증거 위치/모수/지표/비용을 채운다.

## 환경 및 데이터
- Pod GPU/VRAM/시간당 GPU·storage 표시 가격, 시작/종료, 실제 총 사용액: `not_run`
- local GPU: RTX 4070 Ti SUPER 16GB (사용자 제공 사양; 실제 검증하지 않음)
- Qwen model revision, dataset revision, training config hash: `not_run`
- public English unique IDs / quality 3 variants / grouped split hash / final subset: `not_run`
- synthetic trade train/dev/test 수 및 template holdout: `not_run`

## 모델 결과
| 평가/단위 | M0 base | M1 QLoRA | 평가모수 |
|---|---|---|---|
| English public clean: row exact / field EM | not_run | not_run | n observed fields, docs |
| English public faded: row exact | not_run | not_run | n same base docs |
| English public bad_scan: row exact | not_run | not_run | n same base docs |
| English unseen-layout freelancer_invoice | not_run | not_run | n heldout IDs |
| English synthetic trade SKU/quantity/price EM | not_run | not_run | n trade docs |
| PO business discrepancy precision/recall | not_run | not_run | n known changes |
| PO candidate false-pass / review volume | not_run | not_run | n candidates |
| Serving p50/p95, docs/sec, VRAM | not_run | not_run | n attempts & GPU |

## 에러 개선과 정직한 한계
- 실제 오류 분석 최대10건(적으면 전수·개수 공개); 수정, 회귀 테스트, dev 성능 변화: `not_run`
- 사용자 가치 시간/정확도 실측: **실제 기업에서는 미측정**
- actual customs invoice / Korean / Japanese language performance: **미검증**
- cost guard: 실제 청구/stop/delete 확인 `not_run`

V3: public 숫자는 canonical 값 평가, 자체데이터만 raw 문자열/SKU 평가. 실제 모델/과금/데이터 전체 검증과 fixture를 구분한다.
