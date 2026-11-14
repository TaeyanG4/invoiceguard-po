# InvoiceGuard-PO 3차 독립 평가 (Fable, 2026-11-15)

<sub>의뢰: `reports/reviews/briefs/review-3-brief.md` + `review_constraints.md`. Fable(하위 에이전트, 읽기 전용, 135초)의 답을 그대로 옮김.</sub>

## 1. 점수: **82.5 / 100** (1차 70, 2차 79)

| 공고 항목 | 가중치 | 2차 | 3차 |
|---|---:|---:|---:|
| LoRA/SFT 데이터·학습·평가 | 25 | 21 | 21.5 |
| 품목·수량·단가·품번 정확도 | 15 | 11 | 11.5 |
| 서빙·양자화·배치·GPU 운영 | 20 | 16.5 | 17 |
| 자동 채점·회귀 테스트 | 12 | 10 | 11 |
| 실패 분석·개선 | 10 | 7 | 8 |
| Linux/SSH·클라우드 비용 | 8 | 6.5 | 6.5 |
| 우대 | 5 | 2.5 | 2.5 |
| 정직성·재현성·문서 | 5 | 4.5 | 4.5 |

직접 확인한 수정은 다음과 같습니다.
- **R1–R4 커밋:** `3daa2a6` 한 커밋에 10개 파일로 들어 있습니다.
- **test 가드:** `src/invoiceguard/cord_guard.py` L50–58이 같은 arm의 두 번째 test를 막고, `src/invoiceguard/vlm/infer.py` L154–157, L184가 이를 호출합니다.
- **CI 검사:** `tests/test_cord_freeze.py` L22–43이 동결 해시와 arm당 보고서 1개를 검사합니다.
- **vLLM 짝 검사:** `src/invoiceguard/serving/vllm_bench.py` L35–46.
- **행 추가·삭제:** `src/invoiceguard/app/api.py` L79, L345와 `tests/test_app.py` L226.
- **기록 정정:** `docs/20_DECISIONS_V6.md` L62–65.
- **테스트 수:** CPU 환경에서 수집만 해 보니 208개였고, torch가 필요한 `tests/test_vlm_masks.py`는 건너뜁니다. 테스트를 실행하지는 않았습니다.
- **수정 2·3:** `artifacts/adapters/`에 seed·단가 실험 어댑터가 없어 not_run으로 채점했습니다.

## 2. 감점표 (합계 −17.5)

| 항목 | 감점 | 사유 | 근거 | 2차 이후 | 되돌리는 방법 (시간·비용) |
|---|---:|---|---|---|---|
| LoRA/SFT | −2 | CORD 효과의 근거가 학습 1회·seed 1개. 수정 2는 사전 고정만 됨 | `README.md` L545, `docs/20_DECISIONS_V6.md` L67–71, `plan.md` L86 | 남음 (not_run) | 수정 2 실행: 로컬 약 75분, 무료 |
| LoRA/SFT | −1 | CORD 레시피(r8, q·v, 240 step)에 ablation이 없고, dev는 +0.0497로 기준 미달 | `handoff.md` L81, `docs/20_DECISIONS_V6.md` L51 | 남음 | 수정 3을 데이터 구성 ablation으로 보고: 로컬 약 40분 |
| LoRA/SFT | −0.5 | 원안과 수정 1이 한 커밋이고 동결 전 원격 시각이 없음 | `docs/20_DECISIONS_V6.md` L63–65 | 공개로 절반 회복, 되돌릴 수 없음 | 수정 2·3을 실행 전에 push하면 이후분은 증명됨: 5분 |
| 추출 정확도 | −1.5 | CORD test 단가 0.82→0.72, 품목 금액 0.84→0.82 하락 | `README.md` L27, L547 | 원인 분석만 추가, 수치는 남음 | 수정 3 실행. 실패하면 "단가 null이고 금액과 같은 숫자면 채움" 후처리를 dev에서 검증: CPU 1시간 |
| 추출 정확도 | −0.5 | 하위 품목 0.00–0.30, 분석 없음 | `README.md` L547 | 남음 | dev 오류 유형표: CPU 1시간 |
| 추출 정확도 | −1 | 품번은 합성 데이터에만 있고, 합성 FINAL에서 M1 0.921 대 M0 0.897은 유의하지 않음 | `README.md` L24, L682 | 남음 | 일부만 회복 가능: 품번·단가 필드별 paired CI 표, CPU 30분 |
| 추출 정확도 | −0.5 | 모호 수량 미해결 | `README.md` L686 | 남음 | 후처리 규칙 1건을 dev에서 검증: CPU 1–2시간 |
| 서빙 | −1.5 | M1-cord 어댑터는 vLLM 서빙 측정이 없음 (R7 견적 대기) | `plan.md` L88 | 남음 | A40 Pod 1대 45–60분, $0.6–1.2 (견적 승인 후) |
| 서빙 | −1 | 측정이 10–20문서·반복 1회 | `README.md` L689, L815 | 남음 | 위 Pod에서 2회 반복과 100문서: 추가 약 $0.2 |
| 서빙 | −0.5 | 자체 HF 서버는 배치가 없고 지속 부하 미측정 | `README.md` L688–689 | 남음 | 로컬 10분 지속 부하 1회: 20분 |
| 회귀 테스트 | −0.5 | 저장된 예측의 필드별 하락 한도를 거는 CI 게이트가 없음 | `.github/workflows/ci.yml`, `tests/` | 남음 | CPU 1–2시간 |
| 회귀 테스트 | −0.5 | 채점기 자체는 동결 해시를 검사하지 않고(CI만 검사), 같은 실행 ID는 폴더가 있으면 재개 가능 | `src/invoiceguard/cord_guard.py` L57, `src/invoiceguard/cord_eval.py`, `plan.md` L82 | 대부분 고침, 잔여 | 채점 시 `frozen_file_problems` 호출, 완료된 run 재개 거부: CPU 30분 |
| 실패 분석 | −1.5 | 단가 원인은 찾았으나 개선 검증(수정 3)이 not_run | `docs/20_DECISIONS_V6.md` L73–79 | 분석 +1, 검증 남음 | 로컬 약 40분 |
| 실패 분석 | −0.5 | CORD 분석이 `handoff.md`와 docs/20에만 있고 재현 스크립트·보고서·README 반영이 없음 | `handoff.md` L42, `reports/eval/` | 남음 | `failure_analysis`를 CORD에 적용: CPU 1시간 |
| 운영·비용 | −0.5 | 비용이 정산이 아닌 추정치 | `README.md` L678 | 남음 | 콘솔 청구 내역을 사용자가 확인해 기록: 10분 |
| 운영·비용 | −1 | Pod 자동 정지 미설정, 로컬 실행기가 결함으로 20회 재시작 | `README.md` L692, `handoff.md` L22–23 | 실행기는 `d0d8c2d`로 수정, 실증 전 | 실행기 1회 완주 로그. 다음 Pod에서 `sleep N; runpodctl` 정지 확인 |
| 우대 | −1.5 | 한영 혼합·패킹리스트 등 무역 서류 종류가 없음 | `README.md` L682 | 남음 | 한영 혼합 헤더 레이아웃 1종 + dev 측정: 로컬 3–4시간 |
| 우대 | −1 | 검수 UI 미구현 | `README.md` L694 | 남음 | 단일 HTML 검수 화면: CPU 3–4시간 |
| 정직성 | −0.5 | 낡은 상태 표기 (4번 참조) | `plan.md` L86, `README.md` L27 | 새로 생김 | 15분 |

**감점하지 않은 항목:** 멀티 GPU, 로컬 vLLM, fp32·로컬 bf16 LoRA, 2B 초과 모델, 32B 교사, 사람 라벨 실문서, 대규모 seed·탐색, README 길이는 제외했습니다. 이 한계들은 `README.md` L680–693과 `reports/SESSION_HANDOFF.md` L11–15에 적혀 있습니다.

## 3. 치명적 공백

없습니다. 다만 2차의 세 약점(단일 seed, 단가 하락, 서빙과 실데이터 분리)은 결과 기준으로 그대로입니다. 이번 상승분은 무결성·문서·가드에서 나왔고, 새 실험 증거는 0건입니다.

## 4. 뒷받침되지 않는 주장

수치 과장은 없습니다. CORD 비교값을 `reports/eval/compare_cord_test_m1cord_nf4__vs__cord_test_m0_nf4.json`과 대조했고 일치했습니다. 고칠 곳은 세 가지입니다.

1. `README.md` L27 "training seeds in section 6" — 6장에는 "one seed, one training run"(L545)뿐이라 seed 결과가 있는 것처럼 읽힙니다. "single seed; repeats pre-registered, not run"으로 바꿔야 합니다.
2. `plan.md` L86 R5 "실행 중 (01:52 시작)" — `handoff.md` L20–24에 따르면 중단 후 대기 중입니다. README에는 수정 2·3이 대기 중이라는 언급도 없습니다.
3. `plan.md` L82 "해시 검사(실행·채점 모두)" — 채점 코드 `cord_eval.py`에는 동결 검사가 없고, 채점 쪽은 CI 테스트만 검사합니다.

## 5. 90점까지 (+8.5~10)

| 제안 | 가산 | 시간·비용 |
|---|---:|---|
| A. 수정 2 실행(seed 2개, dev). 결과가 음성이어도 그대로 보고 | +2 (음성 +1) | 로컬 75분 |
| B. 수정 3 실행 + CORD 실패 유형 보고서. 실패하면 후처리 1건을 dev에서 검증 | +2 | 로컬 40분 + CPU 1시간 |
| C. M1-cord 병합본을 vLLM으로 CORD 100장 서빙: HF 경로와 일치, 동시 1–16, 2회 반복 | +2.5 | A40 약 1시간, $0.6–1.2 (승인 필요) |
| D. 필드별 회귀 게이트 CI + 채점 시 동결 검사 | +1 | CPU 2시간 |
| E. 한영 혼합 레이아웃 1종 dev 측정 | +1.5 | 로컬 3–4시간 |
| F. 4번의 세 문장 정정, 청구 내역 기록 | +1 | 30분 |

A, B, C가 모두 실행되면 약 90–92점입니다. A와 B가 모두 음성이면 88점 안팎에 머뭅니다. 우선순위는 A, B(대기 중인 실행기 완주), C, F, D 순입니다.
