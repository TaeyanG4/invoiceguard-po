# InvoiceGuard-PO 5차 독립 평가 (Fable, 2026-11-15)

<sub>의뢰: `reports/reviews/briefs/review-5-brief.md`(+ review-3 brief의 질문 형식, `review_constraints.md`). Fable(하위 에이전트, 읽기 전용). 확인 대상: 커밋 39b0dc2, 4e8de7f와 해당 파일. 점수 **91/100** (1차 70, 2차 79, 3차 82.5, 4차 89).</sub>

**한 줄 판정:** 4차에서 값싸다고 한 항목(필드별 회귀 게이트, 필드별 paired CI, 청구 기록, 문구)이 실제로 들어갔고 실사진 모델의 서빙 일치도 로컬에서 확인되어 90점을 넘는다. 남은 감점은 단가 하락 미해결, M1-cord의 vLLM 측정 없음, 우대 항목(한영 혼합 · 검수 UI)에 몰려 있다.

| 공고 항목 | 가중치 | 4차 | 5차 |
|---|---:|---:|---:|
| LoRA/SFT 데이터·학습·평가 | 25 | 23.5 | 24 |
| 품목·수량·단가·품번 정확도 | 15 | 12 | 12.5 |
| 서빙·양자화·배치·GPU 운영 | 20 | 18 | 18.5 |
| 자동 채점·회귀 테스트 | 12 | 11.5 | 12 |
| 실패 분석·개선 | 10 | 9.5 | 9 |
| Linux/SSH·클라우드 비용 | 8 | 7 | 7.5 |
| 우대 | 5 | 2.5 | 2.5 |
| 정직성·재현성·문서 | 5 | 5 | 5 |

## 감점표 (합계 −9)

| 공고 항목 | 감점 | 사유 | 근거 | 4차 대비 | 되돌리는 방법 (시간 · 비용) |
|---|---:|---|---|---|---|
| LoRA/SFT | 0 | seed 기준이 점 추정 규칙이며 seed 20261114의 CI 하한이 0.000임을 명시 | `README.md:564` | **고쳐짐** (−0.5 → 0) | — |
| LoRA/SFT | −0.5 | 데이터 구성 ablation 1건뿐, r · 대상 모듈 · step 대조 없음 | `README.md:343` | 남음 | r16 또는 q·k·v·o 1회 dev 비교 (로컬 40분, $0) |
| LoRA/SFT | −0.5 | 사전 고정의 원격 시각 증명 없음. 로컬이 origin보다 24커밋 앞서 있어, 회귀 게이트 규칙이 "수치를 보기 전에 고정됐다"는 문장(`configs/regression_gate.json:2`)도 규칙과 accepted 5건이 같은 커밋 39b0dc2에 들어가 확인할 수 없음 | `git branch -vv` (ahead 24), `configs/regression_gate.json:2,50` | 남음 | 실행 전 push (사용자 결정 사항, 0분) |
| 추출 정확도 | −1.5 | CORD 단가 하락이 세 seed에서 재현되고 수정 3도 효과 없음. 이번 회차에 새 시도 없음 | `README.md` 6장, `configs/regression_gate.json:22-31` | 남음 | 단가 프롬프트 한 줄 dev 검증 (로컬 15–20분, $0) |
| 추출 정확도 | −0.5 | 품번 · 단가 · 수량의 M1 − M0이 유의하지 않음(품번 +0.024 [−0.024, +0.068], 단가 +0.018 [−0.034, +0.066]). 표와 문장은 정직하게 추가됐으나 결과 자체는 그대로이고 품번은 합성 데이터뿐 | `reports/eval/final_field_ci.md:14-18`, `README.md:461-463` | **일부** (−1 → −0.5) | 범위 안에서 되돌릴 방법 없음(품번 실라벨 부재). 현재 서술 유지 |
| 추출 정확도 | −0.5 | 모호 수량 미해결 | `README.md` 11장 "ambiguous-quantity failure is not solved" | 남음 | 조건부 후처리 dev 검증 (CPU 1–2시간) |
| 서빙 | −1 | M1-cord를 로컬 HF+PEFT 서버로 측정(원문 10/10 일치, 0.730 = 0.730, 429 × 7, 지속 부하 64/64) — 파일로 확인됨. 그러나 공고의 "서빙 프레임워크"인 vLLM으로는 M1-cord 미측정. 또 서빙 보고서 JSON에 어댑터 해시가 없어 "어댑터 = 동결 M1_cord"는 `handoff.md:23` 서술로만 뒷받침됨 | `reports/serving/hf_peft_nf4_local_cord.json`(arms.m1.bench), `hf_peft_nf4_local_cord_sustained.json`, `README.md:605,717-719` | **일부** (−1.5 → −1) | A40 Pod 45–60분, $0.6–1.2(견적 승인 필요). 해시는 벤치가 `/health`의 adapter_sha256을 보고서에 기록 (CPU 15분) |
| 서빙 | −0.5 | CORD 측정도 10문서 · 1회 · 지속 부하 1회. 동시 4의 정확도는 성공 3건 기준 | `hf_peft_nf4_local_cord.json` (repetitions 1, bench.4 fields 18/21), `README.md:719` | 남음 | 30–50문서 × 2회 (로컬 20–30분, $0) |
| 회귀 테스트 | 0 | 필드별 한도 게이트가 CI 단계로 들어갔고, 규칙 단위 테스트와 "accepted가 실제 위반과 정확히 일치" 검사가 있음. 직접 실행 결과 0 failing · 5 accepted, exit 0. 채점 의존 파일 해시 고정과 테스트도 확인 | `src/invoiceguard/regression_gate.py:33-48`, `.github/workflows/ci.yml:24-25`, `tests/test_regression_gate.py:10-16`, `src/invoiceguard/cord_guard.py:31-41` | **고쳐짐** (−0.5 → 0) | — |
| 실패 분석 | −0.5 | dev에서 검증된 개선 0건 | `README.md` 6장 수정 3 "no effect" | 남음 | 조건부 규칙의 dev 정밀도 · 재현율 (CPU 1시간) |
| 실패 분석 | −0.5 | **신규.** 게이트가 찾아낸 자체 dev 인보이스 번호 하락(0.958 → 0.833, 24건 중 3건)은 기록만 되고 원인 분석이 없음(어느 3문서인지, 어떤 오류인지 보고서 없음). 하락을 가진 M1-cord가 그대로 서빙 대상 | `configs/regression_gate.json:14-16`, `README.md:554`; `handoff.md:32`는 수치만 | 신규 | 3문서의 예측 · 정답 대조표를 실패 보고서에 추가 (CPU 30분) |
| 운영·비용 | 0 | 청구 API 기록으로 교체, Pod별 GPU · 디스크 분리, 조회 시점 활성 Pod 0 | `reports/runpod2/billing.json:6-31`, `README.md:707` | **고쳐짐** (−0.5 → 0) | — |
| 운영·비용 | −0.5 | Pod 자동 정지 미실증(한계는 정직하게 기재) | `README.md` 11장 "automatic stop … could not be set" | 남음 | 다음 승인 Pod에서 함께 (추가 비용 거의 없음) |
| 우대 | −1.5 | 한영 혼합 · 패킹리스트 없음 | brief "아직 하지 않은 것" | 남음 | 한영 혼합 레이아웃 dev 측정 (로컬 3–4시간, $0) |
| 우대 | −1 | 검수 UI 미구현 | `README.md:656,723` | 남음 | 최소 검수 화면 (CPU 3–4시간) |

감점하지 않은 항목(평가 범위 규칙): 멀티 GPU, 로컬 vLLM(드라이버 한계, `README.md:611`), fp32 · 로컬 bf16 LoRA, 2B 초과 모델, 32B 교사, 사람 라벨 구축, 대규모 seed · 탐색, README 길이. 추가 seed의 test 미실행은 사전 고정 원칙 준수라 감점 없음.

## 확인한 것
- `python -m invoiceguard.regression_gate`를 읽기 전용으로 실행: 0 failing, 5 accepted, exit 0 — brief와 일치.
- `final_field_ci.md`: M1 − M0은 행 금액만 유의(+0.076 [+0.019, +0.139]) — README 문장과 일치.
- `billing.json` 합계 $2.1623 = $0.4373 + $1.7250 — README · 배지와 일치.
- CORD 서빙: c1 54/74 = 0.7297, 오프라인 동일, identical_raw_rate 1.0, 동시 4에서 429 × 7 · 200 × 3, 지속 부하 64/64 · 12.55 docs/min · p50 9.33 s / p95 11.33 s — README 605행과 일치.
- 4차 문구 2곳(test 칸 문구, seed 점 추정)과 `cord_eval.py` 직접 실행 안내(`README.md:982`) 모두 반영됨.

## 치명적 공백
없음.

## 뒷받침되지 않는 주장 · 과장
감점 수준은 없음. 두 가지만 적는다.
1. "field-level regression gate … run in CI"(`README.md:554`): 워크플로 파일에는 있으나 로컬이 원격보다 24커밋 앞서 있어 GitHub에서 실행된 기록은 아직 없다. push 뒤에 참이 된다.
2. "Fixed 2026-11-15 before the per-field numbers were inspected"(`configs/regression_gate.json:2`): 반박 증거는 없지만 같은 커밋에 accepted가 함께 들어가 제3자가 확인할 수 없다.

## 90점 이상 — 남은 감점 중 가장 값싼 개선
| 제안 | 가산 | 시간 · 비용 |
|---|---:|---|
| A. 인보이스 번호 하락 3건의 원인표(예측 · 정답 대조) + 서빙 보고서에 어댑터 해시 기록 | +0.5~1 | CPU 45분, $0 |
| B. 단가 프롬프트 한 줄 또는 조건부 후처리의 dev 검증(음성이어도 기록, 양성이면 단가 · 실패 분석 감점 회복) | +0.5~2 | 로컬 15–20분 + CPU 1시간, $0 |
| C. M1-cord 병합본 vLLM 서빙(CORD dev 50–100장, HF 일치, 동시 1–16, 2회, 지속 부하, 자동 정지 시도) | +1.5~2 | A40 약 1시간, $0.6–1.4(견적 승인) |

A와 B는 무료로 92–93점대, C까지 하면 94점 안팎. 우선순위 A, B, C.
