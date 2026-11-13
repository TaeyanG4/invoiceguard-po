# 15. 라벨·출력·평가 계약 — v3의 최우선 변경

## A. PUBLIC_CANONICAL
전용 스키마 `schemas/public_extraction.schema.json`, 프롬프트 `prompts/EXTRACT_PUBLIC_CANONICAL.txt`.
```json
{"schema_version":"public-1.0","items":[{"row_index":1,"description":"Sensor module","quantity":"100","unit_price":"2.5","amount":"250"}]}
```
위 값은 가상 계약 예제다. 이 태스크는 표시 문자열을 그대로 베끼는 태스크가 아니다. 문서에서 관측한 숫자를 부호·소수점의 canonical decimal string으로 반환한다. `100.00`과 `100`은 수치상 같다. 모델 출력 원문은 그대로 따로 보관한다.

**GT 변환:** JSON은 가능하면 `parse_float=Decimal`; parquet 숫자는 원본 라이브러리 값의 안전한 10진 직렬화→Decimal. float 산술로 새로운 값을 계산하지 않는다. 금액/단가를 소수2자리로 재반올림하여 오답을 숨기지 않는다. non-finite/부적절한 타입은 데이터 오류로 격리·집계한다.

**출력 파싱:** canonical 값은 `^-?[0-9]+(\.[0-9]+)?$`만 허용. 문자열의 천단위/통화기호는 이 태스크의 출력 규약 위반이므로 strict canonical pass를 통과하지 못한다. 별도 관대한 파싱 점수를 낼 때는 이름·분모·변환규칙을 사전 동결하고 primary와 혼합하지 않는다. JSON 숫자(float)를 내보냈다면 계약 위반이며 서버가 문자열로 조용히 고쳐 canonical 성공으로 집계하지 않는다.

**원문이 숫자를 표시하지 않는 필드:** source에 라벨이 있어도 renderer에서 인쇄하지 않는 경우 학습·주지표 대상에서 빼고 `not_visible`로 보고한다. 보이는지 알 수 없으면 `visibility_unverified`. 누락 라벨을 amount/quantity로 생성하지 않는다. 제공되지 않은 SKU는 출력 계약에 넣지 않는다. source-defined null과 미주석의 차이를 별도 메타데이터로 보존한다.

**숫자 채점 예제**
| GT / prediction | 판정 |
|---|---|
| 2.5 / "2.50" | 값 정답 |
| 2.5 / "25.00" | 오답 |
| 1200 / "1,200.00" | strict canonical 형식 오류; 선택적인 lenient score만 별도 |
| 2.5 / null | 관측 라벨 기준 오답·abstention count |
| 라벨 미제공 SKU | 점수 계산하지 않음 |

## B. TRADE_RAW
기존 `schemas/extraction.schema.json` + `prompts/EXTRACT_V1.txt`. 우리가 렌더러에서 보존한 표시 문자열만 raw 정답이다. SKU와 단위·통화는 여기서 학습/평가한다. `000125`와 `125`는 다른 품번이다. `2 cartons / 100 pcs`는 그대로 보존하거나 unreadable null; 어느 수량인지 임의 확정하지 않는다.

두 태스크는 프롬프트 해시를 다르게 기록한다. task selector는 서버가 고정한 값이며 문서/PO가 바꾸지 못한다. PUBLIC_CANONICAL 결과를 제품 raw로 간주하지 않는다. 제품 API는 TRADE_RAW만 호출한다.

## C. 학습 mask 검사
assistant-only loss라는 옵션명만 확인하지 않는다. 실제 이미지 토큰 확장 후의 batch에서 user/system/image/padding 위치가 -100인지, JSON answer 토큰이 0개가 아닌지 decode와 인덱스로 검사한다. 현재 TRL의 vision assistant-only 경로는 버전·chat template 조건이 있으므로 공식 문서를 확인하고 성공한 환경을 잠근다. 기본 기능이 지원되지 않으면 검증한 completion-only collator를 쓰며 prompt만 따로 토큰화한 길이로 단순 자르지 않는다. [S06]

## D. 계약 검사와 모델 평가는 다름
스키마·예제·Decimal fixture 테스트를 통과했다고 모델이 문서를 잘 읽는 것은 아니다. README/최종보고서에서 package_contract_test, application_cpu_test, actual_gpu_test를 반드시 분리한다.
