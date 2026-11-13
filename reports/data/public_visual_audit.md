# T01 공개 데이터 시각 감사 — InvoiceOCR-Synth (합성 영어 공개 자료)

- 감사일: 2026-11-14 / 감사자: Claude Code(Opus 5.5) 세션 1, 이미지 직접 열람
- 데이터: `alamgirqazi/invoice-ocr-synthetic` revision `673ff85be462eb7f3715ec188a295dd17ca11115` (CC BY 4.0, 게시자 표기)
- 렌더러 소스: `github.com/alamgirqazi/synthetic-invoice-gen` commit `91082ede48d2c0b2e32d9c489ea35f34e9922a99` 의 `templates/*.html`, `render_receipts.py` (로컬 `data/raw/renderer_src/`, 실행하지 않고 읽기만 함)
- 표본: 템플릿별 clean 2장(seed 20261113 해시 순서로 결정적 선택) = 12장 + 템플릿별 1개 base의 faded/bad_scan 12장 추출. 직접 열람한 것은 clean 12장 + 열화 2장(formal_corporate bad_scan, pos_thermal faded).
- 이미지 파일은 `data/processed/public/audit/`(Git 제외). 정답 비교표는 같은 폴더 `audit_gold.json`.

## 결과 요약
| 템플릿 | 표본(clean) | description | quantity | unit_price | amount | 근거 |
|---|---|---|---|---|---|---|
| formal_corporate | synth_0057_5072a4b2, synth_0548_c0f3e504 | 보임·일치 | `%.2f` 인쇄(1.00) | `%.2f` | `%.2f` | 템플릿 L96–99 + 이미지 |
| modern_minimal | synth_0732_08c24cd4, synth_0311_df57d68c | 보임·일치 | str(float)(1.0) | 통화기호+`%.2f` | 통화기호+`%.2f` | L116–120 + 이미지 |
| utility_bill | synth_0100_2874e6f0, synth_0096_2b8b7dfc | 보임·일치(Ω, µ 포함) | str(float) | `%.2f` | `%.2f` | L107–111 + 이미지 |
| freelancer_invoice (OOD) | synth_0717_de4c7f68, synth_0171_1bb2f804 | 보임·일치 | str(float) | 통화기호+`%.2f` | 통화기호+`%.2f` | L121–124 + 이미지 |
| event_ticket | synth_0267_bf4703cc, synth_0372_8fac2313 | **대문자 변환(`|upper`)** | `2.0 x` 형태 | **인쇄 안 함** | 통화기호+`%.2f` | L54–55 + 이미지 |
| pos_thermal | synth_0748_08f496bd, synth_0225_c0612bf3 | **28자 절단(`[:28]`)** | str(float) | **unit_price≠amount일 때만 `@ X each`** | `%.2f` | L70–76 + 이미지 |

12장 모두 관측 가능한 값은 canonical 정답(Decimal)과 일치했다. 불일치 사례는 없었다. 열화 2장도 표 영역이 잘리지 않고 판독 가능했다(전체 열화본 판독성은 미검사).

## 확인된 위험과 처리 (docs/15 A "원문이 숫자를 표시하지 않는 필드")
1. **event_ticket unit_price 미인쇄**: 889개 필드 중 event_ticket 전체. `not_printed`로 마스크. 학습 대상 제외, 주지표 분모에서 제외하고 수를 보고.
2. **pos_thermal unit_price 조건부 인쇄**: 수량 1 등 unit_price==amount인 행은 단가가 인쇄되지 않음 → `not_printed`. 산술로 채운 정답을 만들지 않음.
3. **`%.2f` 반올림**: 라벨이 소수 3자리 이상이면 인쇄값과 라벨이 다름. utility_bill unit_price 4필드 → `printed_rounded` 마스크. 금액을 재반올림해 정답을 바꾸지 않음.
4. **event_ticket 품명 대문자**: 원래 대소문자가 이미지에 없음 → 대소문자 보존 EM에서 `case_transformed` 마스크. casefold 보조지표는 별도 이름으로만 보고(주지표와 혼합 금지).
5. **pos_thermal 품명 28자 절단**: 83필드 `truncated_by_renderer` 마스크.
6. **freelancer_invoice 빈 행에 `0.00` 인쇄**: 모델이 빈 행을 품목으로 출력하면 excess row 오류로 집계(OOD 고유 함정, 라벨 변경 없음).
7. "None" 문자열: customer/supplier가 null이면 일부 템플릿이 `None`을 인쇄. 품목 필드와 무관.
8. SKU·단위·원문 숫자 표기 라벨 없음 → 공개 데이터에서 SKU/raw 평가 안 함.

## 판정
- G1(실제 데이터/라벨): **pass** — 실제 이미지 bytes 2,814개 디코드, revision·shard SHA 고정, 전체 프로파일(`reports/data/public_profile.json`), 12장 시각 점검, 렌더러 소스로 가시성 규칙 확정.
- 한계: 12장 + 열화 2장만 육안 확인. 나머지는 렌더러 소스 규칙에 근거한 자동 판정이다. 열화본의 개별 판독 가능성은 확인하지 않았다(품질별 점수로만 관찰).
