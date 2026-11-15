# 의뢰: 채용 포트폴리오 독립 재평가 (5차) — 감점 사유 중심

대상·채용공고·읽을 것·답할 형식은 3차 의뢰(`reports/reviews/briefs/review-3-brief.md`)와 같다. 그 파일의 "채용공고"와 "답할 것"(특히 2번 감점표: 깎은 점수마다 공고 항목, 점수, 구체적 사유, 근거 파일:줄, 4차 이후 고쳐졌는지/남았는지, 되돌리는 방법·시간·비용)을 그대로 따른다. `reports/reviews/briefs/review_constraints.md`의 평가 제외 규칙(PC·시간 한계로 불가능한 작업은 감점·제안에서 제외, 한계를 정직하게 적었는지만 평가)도 그대로 적용한다.

## 4차 평가(Fable 89 · astra 92.5, `reports/reviews/fable-4.md`, `astra-4.md`) 이후 바뀐 것 — 사실 목록, 파일·git 이력(커밋 39b0dc2, 4e8de7f)으로 직접 확인할 것
- **필드별 회귀 게이트 (CI):** `src/invoiceguard/regression_gate.py` + `configs/regression_gate.json`(하락 > 0.05 이고 3칸 이상이면 실패, 이미 확정된 하락은 사유와 함께 accepted로 남김), `.github/workflows/ci.yml`에 단계 추가, `tests/test_regression_gate.py`. 현재 결과 0 failing · 5 accepted. 평균으로는 안 보이던 하락(CORD를 더한 뒤 자체 dev 인보이스 번호 0.958 → 0.833)을 README 6장에 기록.
- **FINAL 자체 test 필드별 paired CI:** `scripts/eval/final_field_ci.py` → `reports/eval/final_field_ci.md`(같은 40문서, family bootstrap 2,000회). M1 − M0은 행 금액만 유의하고 품번 · 단가 · 수량은 유의하지 않음 — README에 그대로 적음.
- **비용:** 추정치 대신 Runpod 청구 기록 `reports/runpod2/billing.json` $2.162(읽기 전용 billing API).
- **채점 의존 파일 고정:** `configs/frozen_cord_v1_deps.json`(evaluation.py · public_data.py · canonical.py 등 동결 시점 해시) — `cord_guard.py` · `cord_score.py`가 검사, `tests/test_cord_freeze.py`.
- **문구 정정:** "GPU memory flat" → 벤치는 최댓값만 기록한다고 정정.
- **실사진 모델(M1-cord) 서빙 측정 (astra 4 · Fable 4 지적):** 벤치에 `--task cord`(`src/invoiceguard/serving/vllm_bench.py`, CORD 채점기로 모든 답 채점, 테스트 `tests/test_bench_load.py`). 로컬 HF+PEFT 서버(어댑터 해시 = 동결 M1_cord)에서 CORD dev 10장: 원문이 오프라인 평가와 10/10 동일, 정확도 0.730 = 0.730, 동시 4는 429 × 7(설계대로), 5분 지속 부하 64건 모두 200(`reports/serving/hf_peft_nf4_local_cord.json`, `hf_peft_nf4_local_cord_sustained.json`). README 요약표 · 7장 · 11장, 대시보드 서빙 페이지 갱신.
- **패키지 검사:** `scripts/verify_claude_pack.py`가 git에서 제외된 로컬 폴더(.venv · artifacts 등)를 건너뛰도록 고치고 CI에 추가.
- **아직 하지 않은 것:** M1-cord의 vLLM 서빙(유료 Pod, 견적 승인 대기 — 로컬 vLLM은 드라이버 한계로 불가), 한영 혼합 레이아웃, 검수 화면 UI. 단가 하락 · 모호 수량 · 하위 품목 약점은 그대로이며 README에 한계로 적혀 있음.

## 답할 것 (요약)
1. 공고 기준 점수(100점 만점, 소수 0.5 단위)와 한 줄 판정.
2. 감점표 — 4차 감점 항목마다 "고쳐짐 / 일부 / 남음"과 근거 파일:줄, 새로 찾은 감점이 있으면 추가.
3. 90점 이상이면 남은 감점 중 가장 값싼 개선 2–3개, 90점 미만이면 90점까지 필요한 최소 작업.
