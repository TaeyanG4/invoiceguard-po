# 04. 데이터 계약·정규화·대사 규칙

JSON Schema 파일이 타입의 기준이고, 이 문서는 필드의 의미와 상태 전이의 기준이다. 모순이 발견되면 테스트와 함께 한 번에 수정한다.

## 1. 모델 출력 — 관측값만

`schemas/extraction.schema.json` 참조. 제품에서 쓰는 원문 필드는 다음과 같다.

```json
{
  "schema_version": "1.0",
  "document_type": "invoice",
  "invoice_number_raw": "DEMO-001",
  "currency_raw": "USD",
  "items": [
    {
      "row_index": 1,
      "sku_raw": "000125",
      "description_raw": "Sensor module",
      "quantity_raw": "100",
      "unit_raw": "EA",
      "unit_price_raw": "2.75",
      "line_total_raw": "275.00"
    }
  ],
  "subtotal_raw": "275.00",
  "tax_raw": "0.00",
  "discount_raw": "0.00",
  "total_raw": "275.00"
}
```

이 예시는 **가상 정답 계약 예제**이지 모델의 실제 출력이 아니다.

모델 출력에 confidence, 승인 여부, PO 값, 거래 차이 판정을 넣지 않는다. 숫자도 raw 단계에서는 string이다. 못 읽거나 의미가 모호한 값은 null 또는 원문 표기 전체로 남긴다. 없는 것을 계산해 채우지 않는다.

`row_index`는 1부터 시작하여 배열 순서와 같아야 한다. 중복/건너뜀은 계약 오류다. 모델이 행을 하나 빼먹은 사실은 이 규칙만으로 탐지할 수 없다. 모든 모델 출력이 문서 전체를 완전히 담았다고 가정하지 않는다.

최상위 필수는 schema_version, document_type, items이고 행 필수는 row_index다. 다른 필드는 nullable/optional이다. 이는 제품에서 못 읽은 값과 읽은 값을 구분하기 위한 계약이다. 공개 데이터의 canonical 태스크에는 별도 스키마를 사용한다. 런타임 parser는 누락된 필드를 null로 확장하고 `missing_in_response`를 기록한다. 합성 이미지에서는 보이는 모든 핵심값이 채워져야 정상 후보가 될 수 있다.

`schema_version`은 모델 메타데이터용이지 원문에서 읽을 값이 아니다. GPU 모델은 고정 버전 "1.0"을 출력한다.

## 2. 별도 정규화 구조

raw를 수정하지 않고 다음 정보를 만든다.

```text
field_result = {
  raw: string|null,
  normalized: string|null,
  status: parsed|missing|ambiguous|unsupported,
  reason: string|null
}
```

### 인보이스 P0 파싱

- SKU: 앞뒤 공백만 제거. 대소문자와 앞자리 0 보존. 정수 변환/유사 문자열 매칭 금지.
- 수량: 양의 정수 문자열만 지원. 0, 음수, 소수 수량, `2 cartons / 100 pcs`는 검수. `quantity=1`을 default로 넣지 않는다.
- 단위: 원문 EA만 지원(대소문자 무시). BOX/PCS/KG를 EA로 환산하지 않는다.
- 통화: 명시적 `USD` 또는 `US$`만 USD로 정규화. `$` 단독은 ambiguous. PO 통화를 추출값 대신 채우지 않는다.
- 숫자: 지정된 en-US 형식만 지원. 단가 최대 소수 4자리, 금액 최대 소수 2자리. 천 단위 구분은 `1,234.50`처럼 정확한 grouping이어야 한다. `1.234,50`은 unsupported. `1,234`는 영어 USD 인보이스 경로에서 1234로 해석한다. 공개 데이터의 다른 통화는 해당 통화와 원문 형태를 보존하고 별도 평가한다.
- 숫자의 출력/저장은 Decimal을 나타내는 string으로 유지한다. float를 거치지 않는다.
- 할인/세금: P0 정상 후보는 명시적인 0 또는 생성 계약상 검증된 없음만 지원한다. 문서에서 관측되지 않은 금액을 0으로 가정하지 않는다. nonzero/unknown은 검수 대상으로 남긴다.

문서 전체가 세금/할인 표현 없는 간단한 송장일 때도 이미지를 보고 확정하지 못했다면 `unknown`이다. 자체 생성한 학습/평가 문서는 `Tax 0.00 / Discount 0.00`을 명시하여 이 범위를 통제한다.

### 공개 영어 InvoiceOCR-Synth 평가 경로 — 별도 계약

이 절에는 raw 문자열 채점을 적용하지 않는다. 공개 숫자형 label은 원문 인쇄 표기를 보존하지 않는다. PUBLIC_CANONICAL의 별도 스키마/프롬프트/Decimal 값 평가를 사용한다. 자세한 규칙은 [라벨·지표 계약](15_LABEL_AND_METRIC_CONTRACT.md)을 따른다. SKU·unit·통화 등 제공되지 않은 값을 추측하지 않는다.

## 3. PO 계약

`schemas/purchase_order.schema.json` 참조. JSON import를 P0로 구현한다.

필수: po_id, po_version, supplier_id, currency=`USD`, items[]. 필수 행: po_line_id, sku, description, quantity, unit=`EA`, unit_price. 수량/단가는 string이다. PO 내부 중복 SKU는 P0에서 422로 거부한다. 복수 동일 SKU를 line별로 처리하는 매칭 기능은 후속 범위다.

CSV import를 구현한다면 `po_id,po_line_id,sku,description,quantity,unit,unit_price,currency` 열을 받고 모든 값을 문자열로 읽는다. Excel의 자동 형변환으로 잃어버린 앞자리 0을 복구해 추측하지 않는다.

## 4. 대사 알고리즘

1. 지원 범위/필수값/문법 검사. blocker가 있으면 관련 숫자 비교는 not_evaluable.
2. 정규화된 SKU로만 정확하게 매칭한다. 품목 설명의 유사도로 자동 매칭하지 않는다.
3. PO에 없는 SKU는 UNKNOWN_SKU, PO에만 남은 행은 PO_LINE_NOT_FOUND. 전량 발주와 비교하는 P0 정책이며 부분선적일 수 있으므로 실제 오류로 단정하지 않는다.
4. 같은 SKU의 수량과 단가를 각각 비교한다. Decimal `2.5000`과 `2.50`은 동일하다.
5. 단위/통화가 다르거나 모호하면 환산하지 않는다. 관련 금액 차이는 not_evaluable.
6. 지원되는 행에 대해서만 `quantity × unit_price`를 cent 단위 ROUND_HALF_UP으로 계산한다. `abs(expected - printed_line_total) > 0.01`일 때 산술 차이.
7. 세금/할인 0이 확실하고 모든 행이 파싱되면 행 합계와 표시 총액을 비교한다. 일부 행이 모호하면 TOTAL_CHECK_NOT_EVALUABLE로 남긴다.
8. 포괄적인 모든 조합이 맞았다고 인증하지 않는다. 검사 결과가 없으면 matched_candidate다.

단가 변경 2.50→2.75에 맞춰 인보이스 금액도 250→275이면 `UNIT_PRICE_DIFF`만 발생하며 `LINE_ARITHMETIC_MISMATCH`는 발생하면 안 된다.

PO 총액과 인보이스 총액의 차이는 참고 값으로만 표시하고 추가 오류로 중복 카운트하지 않는다. 결제 초과손실 추정으로 부르지 않는다.

## 5. 이유 코드와 처리

| 코드 | 기본 심각도 | 처리 |
|---|---|---|
| MISSING_CRITICAL_FIELD | blocker | 읽기값 보완 후 재검증 |
| AMBIGUOUS_NUMBER / AMBIGUOUS_QUANTITY | blocker | 원문 확인·값/단위 명시 |
| UNSUPPORTED_CURRENCY / CURRENCY_MISMATCH | blocker | P0 밖, 자동 환산 금지 |
| UNIT_MISMATCH | blocker | 단위 확인, P0 밖이면 거절 |
| DUPLICATE_SKU | blocker | 자동 합치기 금지 |
| UNSUPPORTED_DOCUMENT / UNSUPPORTED_ROW_COUNT | blocker | 제품 지원 밖으로 표시 |
| NO_PO | blocker | 비교 PO 선택 |
| UNKNOWN_SKU | warning | 잘못된 PO/실제 추가품목 여부 확인 |
| PO_LINE_NOT_FOUND | warning | 누락/부분선적 여부 확인 |
| QTY_DIFF / UNIT_PRICE_DIFF | warning | 거래 변경 확인; 원문값 보존 |
| LINE_ARITHMETIC_MISMATCH / TOTAL_ARITHMETIC_MISMATCH | warning | 계산 조건을 사람이 확인 |
| TOTAL_CHECK_NOT_EVALUABLE | warning | 계산 못한 사실 표시, 사유 필요 |
| DUPLICATE_DOCUMENT | warning | 같은 sha256의 기존 case 안내 |

JSON 파싱 실패/출력 잘림은 case `failed`이며 정상 findings만 있는 결과로 바꾸지 않는다.

warning은 `confirmed_variance` 또는 수정을 통해 해결할 수 있다. 확인 사유를 쓰지 않은 warning은 승인할 수 없다. blocker는 텍스트 동의만으로 우회하지 않는다. `matched_candidate`라도 사람이 원문 전체를 확인한 뒤 승인한다.

## 6. export 계약

JSON은 schema_version, case_id, approved_version, model_run_id, reviewer, approved_at, final_raw, normalized_values, acknowledged_findings를 포함한다. 기준 PO id/version도 포함한다.

CSV는 `sku,description,quantity,unit,unit_price,line_total,currency,review_note`를 기본 열로 한다. UTF-8 BOM과 quoting을 사용하되 이것만으로 Excel의 앞자리 0 보존이 보장되는 것은 아니다. 사용 안내에 SKU 열을 텍스트로 가져오도록 명시하고 JSON을 원본 형식으로 제공한다. `=,+,-,@,tab,CR`로 시작하는 문자열은 수식 실행 방지용 이스케이프를 적용한다. export에만 적용하고 raw 데이터는 바꾸지 않는다.
