# 14. 최종 단계별 감사 결과 — v2 → v3
기준일: 2026-11-13. 판정: **기획 보완 완료, 런타임 게이트를 통과하는 조건으로 착수 가능**. 제품/GPU 학습이 이미 검증됐다는 뜻은 아니다.

## 중요한 발견과 수정
| ID | 단계·문제 | 위험 | v3 조치 | 남은 확인 |
|---|---|---|---|---|
| A01 | 공개 숫자 라벨을 원문 문자열로 채점 | 2.5/2.50 정답을 오답 처리; 잘못된 SFT | canonical/raw task·schema 분리 | 실제 renderer·라벨 변환 |
| A02 | 공개 데이터 SKU/실거래 근거 없음 | 검증 안 된 품번/현장성능 주장 | E1/E2 분리·합성 명시 | 허가받은 실문서 검증 P1 |
| A03 | file_name만으로 그룹 | 같은 레코드 재렌더 누수 가능 | content component/scenario family 추가 | 전체 local 프로파일 |
| A04 | 원래 마지막 명령은 M0 IID / M1 OOD만 예시 | 서로 다른 데이터로 학습효과 비교 | 두 모델×모든 final split 행렬 | 실제 M0/M1 모두 실행 |
| A05 | 평가 이유코드와 schema 이름 다름 | 지표 FN/TP 잘못 집계 | QTY_DIFF/AMBIGUOUS_QUANTITY/PO_LINE_NOT_FOUND로 통일 | 앱 코드 동일 enum 사용 |
| A06 | 18 GPU시간 예산이 저가 요금 전제 | $10 초과 가능 | actual quote=null, $7/$1/$2 구조·시나리오계산 | 콘솔 tier/잔액/재고 |
| A07 | SSH 연결되면 scp도 된다고 가정 | 학습후 다운로드·터널 막힘 | FullSSH/roundtrip SHA gate | 실제 선택 Pod 접속 |
| A08 | 학습 mask/모듈/정밀도 불명확 | prompt학습·vision변경·비공정 비교 | batch mask/gradient 검사, 동일NF4 비교 | 실제10step·재로드 |
| A09 | timeout이 GPU 취소와 동치 아님 | orphan 추론·비용/동시성 누적 | worker cancel/quarantine + busy reject | 실제 강제timeout 시험 |
| A10 | 늦게 도착한 추론/동시승인 | 예전결과가 수정/승인 덮어씀 | extraction CAS/immutable version/export snapshot | CPU concurrency test |
| A11 | 8템플릿·440자체+350공개 등 범위 | 2일·$10에서 평가 누락 | 6템플릿·224자체+200공개와 mini 사전선택 | pilot시간·비용 |
| A12 | 실패10건 의무·p95 과신 | 실패조작/소표본 과장 | 최대10건·소표본·family분모 명시 | 실제 오류와 요청수 |

## 실행 순서
G0 문서계약 → G1 실제 데이터/라벨 → G2 leakage+evaluator → G3 비용/FullSSH+파일럿 → G4 학습/재로드 → G5 검수API/경쟁조건 → G6 두 모델 final/서빙 → G7 백업/비용정리.

각 gate의 상태는 `not_run`, `pass`, `failed`, `blocked` 중 하나다. `planned`와 `pass`를 혼용하지 않는다. 구성/fixture 검사 결과는 G0의 일부이지 다른 gate의 대체가 아니다.

## 최종 추천
프로젝트 목적·영어·RunPod·2B VLM은 유지한다. 추가 모델, 새로운 데이터셋, RAG, 자동 신고를 넣지 않는다. **데이터를 제대로 채점하고 실제 학습/추론·검수흐름을 같은 계약으로 연결하는 것**이 지금 가장 가치 있는 보완이다.
