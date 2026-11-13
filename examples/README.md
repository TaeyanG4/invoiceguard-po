# 가상 계약 예제

이 폴더의 모든 기업·품목·가격은 테스트용 가상 값이다. JSON은 **정답/계약 fixture**이며 VLM의 실제 예측 결과가 아니다. 이미지도 아직 생성되지 않았다.

`purchase_order.json`: 000125 센서 100개 × USD 2.50 = 250.00, CAB-002 케이블 20개 × USD 5.00 = 100.00. 기준 총액 350.00.

`invoice_oracle.json`: 센서 단가가 USD 2.75로 바뀌어 275.00, 케이블은 100.00. 문서 총액 375.00. 예상 차이는 첫 행의 UNIT_PRICE_DIFF이며 문서 자체 산술은 맞다. 금액 차이 25.00은 참고 정보다.

`expected_findings.json`: 위 정답 JSON을 넣었을 때 규칙 엔진에서 나와야 할 결과. 모델이 이 JSON을 출력했다는 뜻이 아니다.

`test_cases.json`: 추가 CPU 회귀 테스트 specification. 각 항목은 original fixture에 적용할 변경과 검사할 결과다. 테스트 수행 결과는 별도 보고서에 기록한다.

V3: public 숫자는 canonical 값 평가, 자체데이터만 raw 문자열/SKU 평가. 실제 모델/과금/데이터 전체 검증과 fixture를 구분한다.
