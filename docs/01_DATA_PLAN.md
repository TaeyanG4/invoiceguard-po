# 01. 데이터 수집·라벨·분할 계획 v3

## 1. 공개 출처와 검증 범위
`alamgirqazi/invoice-ocr-synthetic` [S01]. 게시자 설명상 938개 base 문서와 3개 이미지 품질, 총 2,814개 이미지이며 영어 합성 자료다. 6개 템플릿, 인보이스 외 티켓·영수증·청구서도 섞인다. 게시자 라이선스 표기는 CC BY 4.0이다. 원문 이미지 전체와 레코드별 정합성을 이번 감사에서 내려받아 검증하지는 못했다.

Claude Code는 GPU 과금 전에 로컬에서 라이선스/출처/revision과 실제 전체 row 수, locale, template, quality, 품목 필드 null/타입, 중복을 집계한다. 캐시가 있는 파일도 SHA와 revision을 기록한다. 데이터 카드 수치는 assertion 가정이며 관측 결과가 우선한다. source renderer에서 각 목표 열이 실제 표시되는지 확인하고, 6개 템플릿에서 clean 표본 2개씩 최소 12개를 눈으로 확인한다. 열이 없는/값이 안 보이는 정답은 학습 타깃으로 만들지 않고 범위를 기록한다. 모델 출력이 나쁜 사례를 보고 사후 제외하는 방식은 금지한다.

## 2. 공개 라벨은 '문자 모양 정답'이 아님 — 중요
원본 `quantity`, `unit_price`, `amount`는 숫자형이다. 2.5라는 라벨만으로 문서가 `2.50`, `$2.50`, `2.5000` 중 무엇을 인쇄했는지 알 수 없다. 따라서 다음 두 태스크를 분리한다.

| 태스크 | 입력/출력 | 학습·평가 |
|---|---|---|
| PUBLIC_CANONICAL | 이미지 + 전용 프롬프트 → description와 3개 숫자의 canonical decimal string | 숫자값 EM, description 공백 정규화 EM, 행/문서 완전 일치 |
| TRADE_RAW | 자체 인보이스 + 전용 프롬프트 → 기존 raw 추출 계약 | 실제 renderer가 보존한 표시 문자열 EM와 숫자값 EM, SKU 보존 |

두 태스크는 하나의 Qwen3-VL 모델/어댑터에 섞어 학습하되 프롬프트·스키마·출처·지표를 분리한다. 공개 JSON의 숫자를 `str()`로 바꿔 raw 전사 정답이라고 부르지 않는다. PO는 두 태스크 모두 모델 입력에서 제외한다. 형식 차이를 없애는 수치 정규화는 비교용이며 모델 원문은 별도 보존한다. 자세한 계약은 [라벨·지표](15_LABEL_AND_METRIC_CONTRACT.md).

SKU·unit 등 공개 데이터에 제공되지 않은 대상 필드를 임의로 null 정답으로 확장하지 않는다. PUBLIC_CANONICAL 스키마에는 해당 필드가 없다. null은 게시자가 부재로 정의한 필드와 '주석하지 않은 필드'를 구분한다. renderer 확인이 불가능한 필드는 `visibility_unverified`로 기록한다.

## 3. 분할 누수 방지
1. 동일 full `file_name`의 clean/faded/bad_scan은 하나의 base family다.
2. 품질·파일명·폰트·레이아웃만 제외한 business-content의 canonical hash로 **다른 파일명에 들어간 동일 거래 레코드**도 같은 연결 그룹에 묶는다. 동일 이미지 SHA도 검사한다. 시각 유사도는 후보 검토용이며 다른 숫자를 가진 같은 템플릿을 무조건 중복으로 합치지는 않는다.
3. `freelancer_invoice`를 final layout holdout으로 둔다. 내용이 학습 후보와 중복되는 그룹은 전체를 holdout에 보내거나 규칙에 따라 격리한다. 단순히 파일명만 다른 버전이 학습으로 남아서는 안 된다.
4. 나머지 그룹에서 train/dev/IID test=75/12.5/12.5 비율을 기준으로 결정적 표본을 만든다. 실제 문서 수와 문서종류/템플릿 분포는 기록한다.
5. OOD 비교는 양식뿐 아니라 내용·업종 차이도 포함한다. 점수 차이를 '레이아웃만의 효과'로 해석하지 않는다.
6. 고정 manifest는 source, revision, base/family ID, content hash, template, quality, split, task, visibility/label status를 갖는다. 원본 파일명/라벨 JSON/PO는 model input에 넣지 않는다.

## 4. 두 실행 프로필
아래는 상한 계획이며 실제 확보 수를 결과에 함께 보고한다.

| 항목 | standard | mini |
|---|---:|---:|
| 공개 clean 학습 base | 200 | 120 |
| 공개 dev base | 20 | 10 |
| 공개 dev 중 품질3종 확인 base | 8 | 4 |
| 공개 IID final base | 20 | 8 |
| 공개 OOD final base | 20 | 8 |
| 자체 train/dev/test | 160/24/40 | 96/12/20 |
| 본학습 optimizer step 상한 | 80 | 40 |

final 공개 자료는 모든 선택 base의 세 품질을 평가한다. dev는 clean 전체 + 사전 고정 stress base의 faded/bad_scan만 평가한다. mini는 standard의 사전 선택된 하위집합이다. **훈련용 파일럿의 길이·속도·메모리만 보고 프로필을 한 번 선택**, dev/final 예측 전에 동결한다. 이후 비용 부족이면 완료된 결과와 not_run을 남기고 좋은 테스트만 골라 채우지 않는다.

## 5. 자체 영어 Invoice–PO 생성
standard 224개 거래 가족, 6개 layout family: train T01–03, dev T04, final T05–06. mini는 같은 가족/레이아웃 규칙의 고정 하위집합. 폰트·색만 바꾼 디자인을 독립 레이아웃으로 세지 않는다. 표 열 순서, header/footer 배치, 줄바꿈 방식 등이 다른 구조를 사용한다.

시나리오: normal, price_change, quantity_change, unknown_sku, ambiguous_quantity, missing_po_line, duplicate_sku. 유형별 계획 수는 config에 있다. 유형과 템플릿·색·파일명·SKU prefix가 일대일로 대응하지 않게 한다. PO를 먼저 만들고 문서값을 유지/변경하여 이미지를 렌더한다. PO는 모델 예측에서 생성하거나 수정하지 않는다. 같은 원거래의 정상/변경/열화 버전은 `scenario_family_id`로 묶어 한 split에만 둔다.

`2 cartons / 100 pcs` 같은 모호한 원문은 숫자 100으로 강제 라벨링하지 않는다. renderer가 실제 그린 문자열을 별도 보존하며 숫자 판단은 검수 상태로 둔다. 세금/할인은 명시적으로 0, 통화는 USD, 단위는 EA라고 인쇄한다. invoice crop 밖 정답, 글자 잘림, 렌더 전후 값 변경을 검사한다. 생성기는 데이터 파일만 만들고 학습 라벨을 추론 서비스로 전달하지 않는다.

## 6. 공개·배포
데이터/기본모델을 ZIP 또는 Git에 재배포하지 않는다. 출처·라이선스·revision·다운로드 절차·manifest를 제공한다. 외부 데이터/렌더러/폰트/기본모델 라이선스를 각각 확인한다. 폰트 파일을 패키지에 포함하지 않는다. 생성 코드·가상 데모 공개와 어댑터 업로드도 사용자의 별도 승인을 받는다.
