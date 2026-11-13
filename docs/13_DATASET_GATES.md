# 13. 착수 전 데이터 게이트 v3

## 채택 판정
영어 단일 언어는 유지한다. 공개 데이터는 InvoiceOCR-Synth, 제품시연은 별도 자체 영어 Invoice–PO. DocILE 승인·CORD 인도네시아어·추가 대형 데이터 수집은 이번 P0 의존성이 아니다.

## 순서대로 검사
1. 저장소 revision, 라이선스, 파일 존재와 **실제 이미지 bytes 다운로드**. 목록을 보았다는 것과 다운로드 완료는 다르다.
2. 938 base/2,814 row/3품질/6레이아웃은 source claim과 actual count를 구분해 비교한다.
3. locale=en, line_items 타입·결측, SKU 미제공, 렌더러에 나타나는 핵심 열을 확인한다.
4. 공개 숫자 GT는 canonical 계약으로 변환한다. `2.5`를 `2.50`의 raw 정답으로 둔갑시키지 않는다.
5. 템플릿별 clean 2건씩+일부 품질변형을 수동 점검한다. 확인 실패/불가도 기록한다.
6. file_name + 동일 content family + 같은 품질변형 + 자체 scenario family가 split을 넘지 않음을 검사한다.
7. 6개 자체 layout의 구조 차이, 유형/레이아웃 상관, 잘린행/비가시 label, PO가 모델에 새지 않는지 검사한다.
8. 훈련용 파일럿 뒤 standard/mini 중 하나를 동결하고 test 예측 전에 manifest hash를 만든다.

## 누락 라벨과 학습 eligibility
PUBLIC_CANONICAL 학습에는 네 핵심 필드의 뜻/가시성이 확인된 문서만 넣는다. source-defined null이 실제 부재로 검증된 경우만 null 타깃을 사용한다. 필드가 unannotated/visibility_unverified이면 억지 null을 채우지 말고 그 학습 레코드를 제외하고 수와 사유를 보고한다. final에서는 마스크·known-field denominator를 기록하고 unknown은 평가하지 않는다. 모델 실패를 보고 사후 제외하지 않는다.

## 실패시
인터넷/DNS/원본 파일 문제로 실제 다운로드를 못하면 `public_data=blocked`다. 자체 합성 시연은 가능하지만 공개 데이터 연구완료라 쓰지 않는다. 사전 제한 때문에 표본이 적으면 그 수와 제외 사유를 공개한다. 다른 데이터로 바꾸는 것은 별도 설계변경이며 사용자와 합의한다.

## 이번 감사의 확인 한계
공식 카드·공개 표·모델/가격/TRL/SSH 문서는 웹으로 확인했다. 감사 컨테이너의 외부 DNS 연결 실패와 이미지 signed URL 접근 실패 때문에 전체 데이터 적재 및 12개 이미지 직접검사는 하지 못했다. 이를 Claude Code 착수 gate로 남겨 두었다. GPU 실행·계정 잔액도 확인하지 않았다.
