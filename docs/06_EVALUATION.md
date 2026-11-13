# 06. 평가·실패 분석 v3

## 비교 트랙
- E1 공개 영어 합성 문서의 canonical 품목 추출. SKU·원문 숫자 표기 점수는 없음.
- E2 자체 영어 인보이스의 raw 전사 + 수치/품번 정확도. 합성 시나리오 점수임을 명시.
- E3 독립 PO 차이 검수. oracle 입력의 규칙 단위시험과 live VLM의 end-to-end 결과를 따로 계산.

## 실험 동결
M0=동일 base revision, 동일 NF4 4-bit 로딩, 어댑터 없음. M1=같은 base/정밀도 + 실제 학습 어댑터. prompt/task, 이미지 전처리, token 한도, seed, generation, 평가 manifest가 같아야 '어댑터 효과' 비교가 된다. BF16 M0와 4-bit M1을 직접 비교해 학습 효과로 해석하지 않는다. 다른 정밀도 서빙은 별도의 S1 실험이다.

모든 final subset에 **M0와 M1 모두** 실행한다. M0를 IID에서만, M1을 OOD에서만 실행하면 비교가 아니다. 오류 개선은 dev에서만 하며, 프롬프트를 바꾸면 M0/M1 양쪽을 동일하게 다시 평가한다. final을 본 뒤 수정하면 해당 평가를 exploratory로 내려놓는다.

## 추출 지표
- 시도 수/JSON 형식 유효율/스키마 유효율/timeout/OOM/truncated/non-finite/지원 밖 건수.
- description: NFKC+공백 정리 후 문자열 EM; 대소문자 유지. 이를 한글/일본어 성능으로 확대하지 않음.
- public quantity/unit_price/amount: Decimal 값의 정확 일치. `2.5 == 2.50`이며 float 상대오차 비교나 원문 문자열 EM이 아님. 파싱 불가·null 예측은 관측 정답에 대해 오답. 세부 내용은 [라벨·지표 계약](15_LABEL_AND_METRIC_CONTRACT.md).
- E2는 renderer의 정확한 표시 문자열 EM와 수치 EM를 구분. leading-zero SKU는 문자열 그대로 비교.
- field EM의 행 대응은 P0에서 읽기 순서 고정. 누락 행으로 뒤 행이 어긋나도 조용히 재정렬하지 않음. row count, row exact, document exact를 함께 보여 한 방식의 한계를 설명.
- 모델이 추가한 행은 별도 오류이며 document exact 실패. API 실패는 모든 해당 관측 필드 및 문서 점수에서 실패; 성공한 요청만 남겨 정확도를 높이지 않음.
- base별 품질3종 paired 결과를 기록. 20 base×3이미지를 독립 문서 60건으로 세지 않음. 요약 불확실성/bootstrapping은 base/family를 묶어서 계산.

## PO 지표와 코드
기계 판정 이유 코드는 `schemas/findings.schema.json`이 기준이다. `QTY_DIFF`, `AMBIGUOUS_QUANTITY`, `PO_LINE_NOT_FOUND`, `UNKNOWN_SKU`, `DUPLICATE_SKU`를 사용한다. 별칭 QUANTITY_DIFF/AMBIGUOUS_QTY/MISSING_ITEM/EXTRA_ITEM을 혼용하지 않는다.

1. `QTY_DIFF`, `UNIT_PRICE_DIFF`, `UNKNOWN_SKU`, `PO_LINE_NOT_FOUND` 등 실제 시나리오별 TP/FP/FN.
2. `AMBIGUOUS_QUANTITY`, `DUPLICATE_SKU` 등 지원/검수 blocker를 거래차이와 별도 집계.
3. 검수 대상 비율, 차이 없는 후보 비율, 후보 중 실제 거래차이 비율, 후보 중 추출오류 비율.
4. 모든 문서를 검수로 보내는 정책이 우수하다고 보이지 않게 검수율과 정확도를 같이 표시.
5. 작은 final에서 유형별 표본이 1–2개면 사례 검증으로만 해석. 0/n 오류도 모집단 0% 보장이 아니며 n=0인 precision/recall은 null이다.
6. warning의 원문 확인은 사람에게 맡긴다. 모델만으로 실제 공급업체의 잘못을 확정하지 않는다.

## 오류 개선
dev의 실제 실패를 최대 10건, 적으면 전수 점검하고 수량을 공개한다. 정답을 일부러 바꾸어 실패 10건을 채우지 않는다. 원인별로 JSON/파싱, 행 누락, 숫자 혼동, SKU 앞자리 손실, 흐린 인쇄, 출력 잘림을 구분한다. 한 가지 변경을 적용하고 전체 고정 dev 또는 해당 지표 계약에 맞는 dev 결과를 재검증한다. 규칙 개선은 저장한 원문 예측을 재사용할 수 있지만 모델 정확도가 개선됐다고 부르지 않는다. 실패가 없으면 별도의 사전 정의 stress test로 개발하며 final은 사용하지 않는다.

## 서빙
20개 서로 다른 dev/benchmark 이미지에 warmup3, 동시성1/2, 각 조건 2회. p50/p95는 소표본 탐색 지표로 표시하고 요청 수/실패율을 함께 기록한다. API concurrency2가 GPU 병렬추론이라는 뜻은 아니다: semaphore1이면 직렬 처리+대기시간 실험이다. 429/timeout도 workload 결과에 포함한다. 실제 batching이 없으면 batch speedup을 주장하지 않는다. 인터넷 왕복 포함 wall latency와 모델 내부 inference 시간을 구분한다.

## 최종 상태
모든 실측 전 필드는 null/not_run이다. 기능 fixture, 기록 재생, 실제 원격 추론의 모드를 표시한다. 품질/모델 성능이 나빠도 정직한 실험 기록은 유효하며, 제품으로 성공했다고 과장하지 않는다.
