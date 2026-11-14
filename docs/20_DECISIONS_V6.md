---
type: decision
title: 계약 개정 v6 — 실사진 영수증 CORD v2 추가와 사전 고정 판정 기준
description: 합성 데이터만으로는 난이도가 낮아(M0·M1 차이가 유의하지 않음) 라벨이 있는 실사진 영수증 CORD v2를 별도 태스크 CORD_RAW로 추가한다. 학습·평가 전에 지표와 통과 기준을 고정한다.
tags: [decision, cord-v2, real-documents, metric, pre-registration]
status: active
generated: {by: claude-opus-5.5, at: 2026-11-14T22:33+09:00}
sources:
  - {id: cord-v2, resource: "https://huggingface.co/datasets/naver-clova-ix/cord-v2", note: "revision 7f0115a4b758a71d6473b8d085751692da2fef98, CC BY 4.0"}
  - {id: fetch, resource: reports/realdocs/cord_fetch.json}
  - {id: plan, resource: plan.md}
---

# 20. 계약 개정 v6 — CORD v2 실사진 영수증 (2026-11-14)

## 왜
- 합성 데이터 dev 44건에서 M1(LoRA)과 M0(기본 모델)의 차이가 유의하지 않았다. 데이터가 너무 쉽다(plan.md P14).
- Kaggle 인도 세금계산서 169장은 라벨이 없다. 교사 모델 초안은 검산 통과율이 낮아(185행 중 40행) 정답으로 쓸 수 없다. 사용자도 "결국 사람이 라벨링해야 한다"고 지적했다 → 정량 평가에서 제외한다.
- CORD v2는 실제로 찍은 영수증 사진에 사람이 단 라벨이 있고, 공식 분할(800/100/100)이 있으며 CC BY 4.0이다. 사용자가 내려받기를 승인했다(2026-11-14).

## 무엇이 바뀌나
| 항목 | 결정 |
|---|---|
| 새 태스크 | `CORD_RAW` — 영수증 사진에서 품목(name, count, unit_price, price, sub_items)과 subtotal·tax·total을 **인쇄된 그대로** 옮긴다. 프롬프트 `prompts/EXTRACT_CORD_RAW.txt`, 스키마 `schemas/cord_extraction.schema.json` |
| 기존 계약과의 관계 | TRADE_RAW·PUBLIC_CANONICAL과 그 frozen_v1 final은 바꾸지 않는다. 제품 API 태스크는 여전히 TRADE_RAW. CORD는 영어 전용 문서가 아니다(인도네시아 영수증, 품목명 혼용) — 이 점을 결과에 명시한다 |
| 라벨 | CORD `gt_parse`의 menu.nm/cnt/unitprice/price, menu.sub, sub_total.subtotal_price, sub_total.tax_price, total.total_price만 사용. 값은 원문 문자열 그대로(변환·정규화 없음). 그 밖의 키(num, discountprice, cash·change 등)는 요청하지 않는다 |
| 여러 상자로 나뉜 값 | 원 라벨이 리스트인 필드(약 20개 문서)는 이어 붙이지 않는다. 평가에서는 그 필드만 채점 제외(masked)로 세고, 학습에서는 그런 문서를 뺀다 |
| 분할 | CORD 공식 분할을 그대로: train 800 → 학습, validation 100 → dev(조정·디버깅), test 100 → 한 번만 쓰는 최종 평가 |
| 내용 중복 | 공식 분할에서 사진은 다르지만 정답이 완전히 같은 문서가 있다(test 15건, dev 20건이 train과 같은 정답). 정답 암기를 막기 위해 **dev·test와 정답이 같은 train 40건은 학습에서 뺀다**(학습 가능 742건 = 800 − 리스트 라벨 18 − 내용 중복 40). test는 공식 100건 그대로 평가하고, train과 내용이 겹치지 않는 85건 결과도 따로 보고한다 |
| 입력 경계 | 모델 입력은 이미지와 고정 프롬프트뿐. 파일명·image_id·정답은 넣지 않는다 |
| 전처리·생성 | 기존과 동일: max_pixels 786,432, greedy, max_new_tokens 1,536. M0·M1 모두 같은 설정 |

## 비교 설계
- **주 비교:** M0(기본 모델) 대 M1-cord(기존 학습 데이터 + CORD train으로 학습한 QLoRA). 둘 다 **로컬 RTX 4070 Ti SUPER, NF4**로 평가한다. M1-cord는 NF4에서 학습했으므로 NF4 기본 모델에 붙여 평가한다(어댑터-정밀도 짝 검사 P15).
- **보조 비교:** 기존 M1(CORD 없이 학습한 어댑터)도 같은 CORD test에 돌려 "CORD를 더한 효과"를 분리한다.
- **회귀 확인:** M1-cord를 기존 dev(trade dev, public dev clean)에도 돌려 기존 M1 대비 하락을 본다.
- **GPU 원칙:** 학습한 GPU·정밀도와 평가하는 GPU·정밀도를 섞지 않는다. RunPod를 쓰면 그 Pod 안에서 학습과 평가를 함께 하고, 로컬 결과와 같은 표에 섞지 않는다.

## 지표 (학습 전에 고정, 이후 변경 금지)
1. **주 지표 — strict 필드 정확도:** 정답에 값이 있는 필드(품목 4개 필드, 하위 품목 4개 필드, subtotal·tax·total)만 센다. 품목은 순서대로(위치) 맞춘다. 비교는 NFKC 정규화 + 공백 하나로 압축 후 완전 일치. JSON 실패·누락 행은 틀린 것으로 센다.
2. **보조 A — 형식 무시 정확도:** 숫자 필드(count, unit_price, price, subtotal, tax, total)는 숫자만 남겨 비교("@16.500" = "16500"), 이름은 대소문자·공백 무시. "형식만 배운 것인지, 실제로 더 잘 읽는지"를 가르는 지표.
3. **보조 B — 순서 무관 필드 F1:** (필드 이름, strict 정규화 값) 쌍의 다중집합으로 정밀도·재현율·F1. 행 하나를 빠뜨려 뒤가 모두 밀리는 위치 채점의 약점을 보완하고, 정답에 없는 값을 지어낸 것도 정밀도로 잡는다.
4. JSON 파싱 성공률, 스키마 유효율, 정답에 없는데 값을 낸 필드 수를 함께 보고한다.
5. 모든 지표를 test 전체 100건과 내용 미중복 85건으로 나눠 보고한다(판정은 전체 100건 기준).
6. 신뢰구간: 문서 단위 paired bootstrap 2,000회(seed 20261113), 95% 백분위 구간.

## 통과 기준
- **"CORD에서 파인튜닝 효과 있음"**: CORD test에서 M1-cord − M0의 strict 필드 정확도 차이가 **+0.05 이상이고 95% CI 하한 > 0**.
- **"형식이 아니라 읽기도 좋아졌음"**: 위에 더해 보조 A(형식 무시)의 차이도 CI 하한 > 0. 아니면 "주로 출력 형식을 맞춘 효과"라고 쓴다.
- **"기존 성능 유지"**: 기존 dev(trade dev, public dev clean)에서 M1-cord가 기존 M1보다 0.03 넘게 떨어지지 않음. 넘게 떨어지면 그대로 보고한다.
- 결과가 기준에 못 미쳐도 그대로 보고한다. test 결과를 본 뒤 프롬프트·학습을 바꾼 평가는 exploratory로 표시한다.

## 학습 설정 (학습 전에 고정)
- M1-cord: 기존 학습 데이터(public 200 + trade 160) + CORD train 742 = 1,102건, QLoRA NF4, LoRA r8/α16 q_proj·v_proj, lr 1e-4 cosine, 유효 배치 8, **240 step**(약 1.74 epoch — 기존 M1 레시피의 1.78 epoch에 맞춤), seed 20261113, 로컬 RTX 4070 Ti SUPER.
- 실행 순서와 시각 기록: `scripts/realdocs/run_cord_local.sh`.

## 수정 1 — 코드 펜스 (2026-11-14 22:40, CORD 학습·test 실행 전, dev 관찰 근거)
- **관찰:** M0 dev 실행 첫 18건이 전부 답을 ```json 펜스로 감쌌다. strict JSON 파싱으로는 M0의 모든 필드가 0점이 되어, 비교가 읽기 능력이 아니라 펜스 유무를 재게 된다(합성 데이터 P14에서도 M0 strict 0.000 / lenient 0.736으로 같은 현상).
- **변경:** 위 지표 1–3과 통과 기준의 필드 점수는 **펜스 하나만 벗긴 출력**으로 계산한다. 이 경로는 기존 lenient와 같다: 맨 앞뒤의 ```json 펜스 한 쌍만 제거하고, 잘림·문법 오류·키 누락은 고치지 않는다.
- **형식 지표는 따로:** 펜스 없이 바로 파싱되는 JSON 비율(strict JSON 비율)과 그 기준의 필드 정확도를 별도 줄로 보고한다. "M1이 형식을 배웠다"는 이 줄로만 말한다.
- 이 수정은 dev만 보고 정했고, CORD test는 아직 열지 않았다.

## 동결
dev에서 학습 설정을 정한 뒤, test를 돌리기 전에 `configs/frozen_cord_v1.json`에 manifest 해시, 프롬프트 해시, 생성 설정, 정밀도, 어댑터 해시를 기록한다. `cord:test`는 `--allow-final`과 이 동결 파일이 맞을 때만 실행된다.

## 기록 정정 (2026-11-15 01:52, 외부 검토 지적 반영)
- 이 문서의 원안(지표·통과 기준)과 수정 1은 **같은 커밋 6823ad0(2026-11-14 22:43:31 KST)**에 처음 들어갔다. 그때 M0 dev 실행(22:36 시작)은 이미 돌고 있었으므로, 원안이 M0 dev 출력을 보기 전에 쓰였다는 git 증거는 없다. 정확한 표현은 "M0 dev 18건을 관찰한 뒤, CORD 학습(23:18 시작)과 test(00:32 시작) 전에 고정"이다.
- 커밋 92892c5에서 이 문서의 시각 표기를 바로잡았다: 생성 23:00 → 22:33, 수정 1 23:40 → 22:40. 처음 적은 값은 추측으로 쓴 오기였고, 고친 값은 파일 시각과 커밋 시각에서 다시 읽은 것이다. 내용(지표·기준·수정 1 본문)은 6823ad0 이후 바뀌지 않았다.
- test가 시작되기 전(00:32)에는 원격 저장소에 이 문서가 없었다. 첫 push는 test 도중(00:57)이었다. 제3자 시각 증명은 없고, 로컬 커밋 시각과 파일 시각이 근거다.

## 수정 2 — seed 반복 (2026-11-15 01:52, 추가 seed를 학습하기 전 — 커밋 1c6e04e)
- **목적:** test 판정(+0.065)이 학습 1회에서 나왔으므로, 같은 레시피를 다른 seed로 두 번 더 학습해 효과의 방향이 유지되는지 본다. **test 판정은 바꾸지 않는다.**
- **실행:** M1-cord와 같은 설정(1,102건, 240 step, LoRA r8/α16 q·v, lr 1e-4, NF4)에서 seed만 **20261114, 20261115**로 바꿔 학습하고, 로컬 4070 NF4로 **CORD dev 100장만** 평가한다. 추가 seed는 동결된 arm이 아니므로 CORD test는 돌리지 않는다.
- **보고 기준 (사전 고정):** seed 3개(20261113 · 20261114 · 20261115) 각각의 dev M1-cord − M0 strict 차이와 95% CI, 평균과 범위. "seed에 견고함"은 **세 seed 모두 차이가 0보다 크고**, 평균이 +0.03 이상일 때만 쓴다. 아니면 "seed에 따라 효과가 달라짐"이라고 그대로 쓴다.
- 실행 스크립트: `scripts/realdocs/run_cord_seeds.sh`.

## 수정 3 — 단가 누락 개선 시도 (2026-11-15 01:58, 학습 전, exploratory)
- **근거 (dev만 봄):** M1-cord는 CORD dev에서 정답에 단가가 있는 50칸 중 10칸을 비웠다(M0는 2칸). 그중 8칸은 행은 냈지만 단가만 null이었다. 대부분 단가와 행 금액이 같은 숫자로 두 번 인쇄된 경우이거나, "@"가 붙은 단가를 금액 칸에 넣은 경우다. CORD train에서 단가가 인쇄된 품목은 29 %다(1,987개 중 580개, 742문서 중 272문서).
- **변경 하나:** 단가가 인쇄된 train 영수증 272장을 한 번 더 넣는다(1,102 → 1,374건, `train --data all_plus_cord_up`). 나머지(240 step, seed 20261113, LoRA r8/α16 q·v, lr 1e-4, NF4)는 M1-cord와 같다. run id `m1_cord_up_v1`.
- **평가:** CORD dev 100장만(로컬 4070 NF4). test는 이미 1회 썼으므로 돌리지 않는다. 그래서 결과는 exploratory다.
- **판정 (사전 고정):** "개선"이라고 쓰는 조건은 두 가지다. dev 품목 단가 정확도가 M1-cord(0.68)보다 0.10 이상 오르고, dev 전체 strict 정확도가 M1-cord(0.762)보다 0.01 넘게 떨어지지 않아야 한다. 아니면 "효과 없음" 또는 "부작용"으로 그대로 보고한다. seed 차이(수정 2)도 함께 적는다.
- 실행 스크립트: `scripts/realdocs/run_cord_up.sh` (seed 반복이 끝난 뒤 같은 GPU에서).
- **실행 방식 변경 (2026-11-15 03:13, 커밋 4200c31, 결과 전):** 수정 2·3의 학습·평가는 `scripts/realdocs/gpu_free_runner.py cord_r5_r6`로 돌린다. 다른 프로그램이 GPU를 쓰지 않을 때만 작업을 시작하고, 도중에 GPU 경합이 생기면 그 작업을 멈췄다가 처음부터 다시 돌린다(학습은 0 step부터, 평가는 남은 문서부터). 학습 프로세스에는 `PYTORCH_CUDA_ALLOC_CONF=garbage_collection_threshold:0.6,max_split_size_mb:256`을 준다(메모리 재사용 방식만 바뀌고 계산은 같다). 이전 두 번의 시도는 GPU 메모리가 넘쳐 중단했다(handoff.md).
