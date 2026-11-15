# InvoiceGuard-PO 6차 독립 평가 (Fable, 2026-11-15)

<sub>의뢰: `reports/reviews/briefs/review-6-brief.md`(+ review-3 brief의 질문 형식, `review_constraints.md`). Fable(하위 에이전트, 읽기 전용). 확인 대상: `git log ad2a69e..HEAD`(e247246 … 8f20a18, 12커밋)와 해당 파일, `gh run list`. 점수 **95.5/100** (1차 70, 2차 79, 3차 82.5, 4차 89, 5차 91).</sub>

**한 줄 판정:** 5차 감점 15건 중 9건이 파일과 원격 기록으로 확인되어 사라졌다(사전 등록의 원격 시각, LoRA ablation, 검증된 개선, 인보이스 번호 원인, 서빙 표본 · 어댑터 해시, 검수 화면, 한영 혼합). 남은 감점은 시험에 쓴 모델의 단가 하락, M1-cord의 vLLM 미측정, Pod 자동 정지, 우대 항목의 깊이에 있다.

| 공고 항목 | 가중치 | 5차 | 6차 |
|---|---:|---:|---:|
| LoRA/SFT 데이터·학습·평가 | 25 | 24 | 25 |
| 품목·수량·단가·품번 정확도 | 15 | 12.5 | 13 |
| 서빙·양자화·배치·GPU 운영 | 20 | 18.5 | 19.5 |
| 자동 채점·회귀 테스트 | 12 | 12 | 12 |
| 실패 분석·개선 | 10 | 9 | 9.5 |
| Linux/SSH·클라우드 비용 | 8 | 7.5 | 7.5 |
| 우대 | 5 | 2.5 | 4 |
| 정직성·재현성·문서 | 5 | 5 | 5 |

## 감점표 (합계 −4.5)

| 공고 항목 | 감점 | 사유 | 근거 | 5차 대비 | 되돌리는 방법 (시간 · 비용) |
|---|---:|---|---|---|---|
| LoRA/SFT | 0 | 대상 모듈(q·k·v·o)과 rank(16) 대조를 하나씩 바꿔 학습하고 사전 기준으로 판정. 비교 JSON과 학습 보고서 수치가 README와 일치(+0.0199 [0.0048, 0.0363], 단가 40/50, 학습 파라미터 3,211,264) | `docs/20_DECISIONS_V6.md:92-101`, `reports/eval/compare_cord_dev_m1cordqkvo_nf4__vs__cord_dev_m1cord_nf4.json`, `reports/model/train_m1_cord_qkvo.json`, `README.md:587-595` | **고쳐짐** (−0.5 → 0) | — |
| LoRA/SFT | 0 | 사전 등록의 원격 시각 증명. e247246(수정 4–6)의 CI 실행 2026-11-15T00:50:45Z, 5a6b0b6(수정 7) 02:43:18Z를 `gh run list`로 확인. 결과 커밋은 그 뒤(19019e8 11:07, 6a31ce9 11:39, dec9b75 12:54, 8f20a18 13:42 KST). 로컬 = origin/main. 과거 건(원안 · 게이트 규칙)은 되돌릴 수 없고 기록 정정 절에 정직하게 적혀 있음 | `gh run list`, `git branch -vv`, `docs/20_DECISIONS_V6.md:66-69` | **고쳐짐** (−0.5 → 0) | — |
| 추출 정확도 | −1 | 시험에 쓰고 서빙하는 모델(M1-cord)의 단가 하락(test 0.82 → 0.72)은 그대로. 수정 4(프롬프트)는 부작용(0.68 → 0.46). 수정 5의 A1이 dev에서 0.80까지 되돌렸지만 seed 1개 · dev 전용이고 서빙 어댑터가 아님(README도 "후보"로 적음) | `README.md:558,582-584,591,595`, `configs/regression_gate.json`(prompt 쌍 accepted 34→23) | **일부** (−1.5 → −1) | A1을 seed 2개 더 학습해 dev 반복(로컬 약 1.2시간, $0). 세 seed 모두 단가 ≥ 0.76이고 전체가 M1-cord seed 범위 위면 −0.5 |
| 추출 정확도 | −0.5 | 품번 · 단가 · 수량의 M1 − M0이 유의하지 않음(합성 FINAL). 서술은 정직 | `reports/eval/final_field_ci.md:14-18` | 남음 | 범위 안에서 되돌릴 방법 없음 |
| 추출 정확도 | −0.5 | 모호 수량: 합성 FINAL 0/2 미해결. T07에서 2–3/3으로 "레이아웃 의존"이라는 새 관찰은 있으나 고친 것은 아님 | `README.md:774`, `reports/eval/t07_stress.md` | 남음 | T05/T06 dev를 고해상도(수정 7 방식)로 다시 추론해 모호 수량이 해상도 문제인지 확인(로컬 15–20분, $0, 사전 등록 필요) |
| 서빙 | −0.5 | M1-cord의 vLLM 측정 없음(한계 정직 기재). 5차의 나머지 절반(어댑터 해시)은 해결: 서버 `/health` 해시 630d3dd1… = 오프라인 run 해시, `same_adapter_as_offline_m1: true` | `README.md:780`, `reports/serving/hf_multi_lora_cord.json`(adapter 블록) | **일부** (−1 → −0.5) | A40 Pod에서 M1-cord 병합본 vLLM(CORD dev 100장, HF 일치, 동시 1–16, 지속 부하) 약 1시간, $0.6–1.4(견적 승인) |
| 서빙 | 0 | 표본 확대: 자체 dev 24/24, CORD dev 100/100 원문 동일(0.9682 = 0.9682, 0.7617 = 0.7617), 동시 1 · 2 실패 0, CORD 5분 지속 44/44, 429 재시도 클라이언트(4에서 99/100, 8에서 96/100 · p95 189 s). 한 서버 두 어댑터의 요청별 선택은 코드와 테스트로 확인. 반복 1회 · 무배치 · 꼬리 지연은 README가 그대로 적음 | `reports/serving/hf_multi_lora_*.json`, `src/invoiceguard/serving/hf_server.py:83`, `tests/test_serving_core.py:146`, `README.md:658,779-780` | **고쳐짐** (−0.5 → 0) | — |
| 회귀 테스트 | 0 | 게이트 직접 실행: 0 failing · 8 accepted, exit 0. accepted가 정확한 칸 수에 고정, 필드 · 세트 누락도 실패. `cord_eval` CLI는 `cord_score`로 위임, 동결 원본 해시 + AST 동일성 검사. pytest 227 통과 · 1 skip(torch 없음) | `src/invoiceguard/regression_gate.py:33-66`, `src/invoiceguard/cord_guard.py:31-52`, `tests/test_regression_gate.py:32,44`, `tests/test_cord_freeze.py:149,177` | 유지 (0) | — |
| 실패 분석 | 0 | dev에서 검증된 개선이 생김: A1(사전 기준 "낫다"), 해상도(M0 품명 0.641 → 0.812, 대사 18 → 29/30, 사전 기준 충족). 실패한 시도 2건도 그대로 보고 | `docs/20_DECISIONS_V6.md:90,98-101,114`, `reports/eval/t07_stress.md` | **고쳐짐** (−0.5 → 0) | — |
| 실패 분석 | 0 | 인보이스 번호 하락 3건의 문서별 · 형식별 원인표(모두 `YYYY/NNNNN`, 키 누락 2 · 연도 누락 1), 원인은 가설이라고 명시, 대응(문서 종류별 어댑터)은 서빙에서 측정 | `reports/eval/invoice_number_drop_dev.md`, `README.md:562` | **고쳐짐** (−0.5 → 0) | — |
| 실패 분석 | −0.5 | **신규.** 수정 7이 "동결 해상도 786,432가 낮다"는 것을 밝혔지만 T07 30장에서만 확인. CORD dev와 자체 dev에서의 효과는 확인하지 않았고("not checked"), 검증된 두 개선(A1, 해상도)을 합친 다음 레시피의 dev 검증이 없음 | `README.md:641`, `docs/20_DECISIONS_V6.md:114` | 신규 | M1-cord를 CORD dev 100장 + 자체 dev 24장에 고해상도로 추론(사전 등록 후 로컬 30–40분, $0) |
| 운영·비용 | −0.5 | Pod 자동 정지 미실증(정직 기재) | `README.md:782` | 남음 | 다음 승인 Pod에서 함께(추가 비용 거의 없음) |
| 우대 | −0.5 | 한영 혼합은 측정됨(T07 30장, 사전 등록, 세 arm + 고해상도 arm, "M1이 더 잘 읽는다고 쓰지 않음"까지 정직). 남은 것: 합성 레이아웃 1종 · 30장, 고해상도에서도 품명 0.79–0.81, 패킹리스트 · B/L 없음 | `README.md:614-641`, `reports/eval/t07_stress.md` | **일부** (−1.5 → −0.5) | 패킹리스트형 레이아웃(중량 · 포장 수 열) 30장 stress set을 같은 방식으로(로컬 2–3시간, $0) |
| 우대 | −0.5 | 검수 화면 구현됨(한국어 단일 페이지, CSP self-only, 행 추가 · 삭제 · 사유 · 승인 · 내보내기, 서버 측 테스트 2건 + 스크린샷). 남은 것: 화면 동작(JS)은 자동 테스트가 없고 브라우저 수동 확인 1회, 공고의 React/Spring은 아님 | `src/invoiceguard/app/static/review.js`, `tests/test_app.py:264,281`, `README.md:712,784` | **일부** (−1 → −0.5) | 화면 흐름 1개를 헤드리스 브라우저 테스트로(CPU 1–2시간) |

감점하지 않은 항목(평가 범위 규칙): 멀티 GPU, 로컬 vLLM(드라이버 한계), fp32 · 로컬 bf16 LoRA, 2B 초과 모델, 32B 교사, 사람 라벨 실문서 구축, 대규모 seed · 탐색, README 길이. A1을 CORD test에 돌리지 않은 것은 test 1회 원칙 준수라 감점 없음.

## 확인한 것
- `gh run list`: e247246 → 00:50:45Z success, 5a6b0b6 → 02:43:18Z success. 최신 8f20a18은 조회 시점에 in_progress.
- `python -m invoiceguard.regression_gate`: 0 failing, 8 accepted. `pytest tests/`: 227 passed, 1 skipped. 실행 뒤 작업 트리 변경 없음.
- 수정 4 · 5 비교 JSON, 학습 보고서, T07 표, 서빙 JSON 6개의 수치가 README · docs/20과 일치.
- 서빙 JSON: 서버가 보고한 어댑터 해시 2개(m1 eb086741…, cord 630d3dd1…)와 오프라인 run 해시 일치.

## 치명적 공백
없음.

## 뒷받침되지 않는 주장 · 과장
감점 수준은 없음. 낡은 문구 네 곳.
1. "on the four comparison pairs registered there"(`README.md:561`, `README.ko.md:559` "비교 쌍 4개") — `configs/regression_gate.json`의 쌍은 지금 7개.
2. "A one-line prompt instruction (amendment 4) then had a side effect (below)"(`README.md:598`) — 해당 문단은 위(582행)에 있음.
3. "228 pytest tests"(`README.md:28`) — 수집 228건 중 1건은 torch가 없는 환경(CI 포함)에서 skip. "228 collected, 1 GPU-only skip"이 정확.
4. 수정 7 머리글 시각 "11:50, 실행 전"(`docs/20_DECISIONS_V6.md:110`) — 커밋 5a6b0b6은 11:43:15 KST. 순서(push 뒤 실행)는 맞고 표기만 어긋남.

## 95점 이상 — 남은 감점 중 가장 값싼 개선
| 제안 | 가산 | 시간 · 비용 |
|---|---:|---|
| A. 사전 등록 후 로컬 dev 실험 한 묶음: A1 seed 2개 반복 + M1-cord 고해상도 추론(CORD dev 100, 자체 dev 24, T05/T06의 모호 수량 포함) | +1~1.5 | 로컬 약 2시간, $0 |
| B. M1-cord(또는 A1) 병합본 vLLM 서빙 + Pod 안 자동 정지 시도 | +0.5~1 | A40 약 1시간, $0.6–1.4(견적 승인) |
| C. 낡은 문구 4곳 정정 + 검수 화면 헤드리스 흐름 테스트 1개 | +0~0.5 | CPU 1–2시간, $0 |

우선순위 A, B, C. A와 B를 하면 97점 안팎이고, 그 위는 범위 밖 항목(실문서 라벨, 품번 실라벨)이 막고 있다.
