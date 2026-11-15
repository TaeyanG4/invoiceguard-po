# 의뢰: 채용 포트폴리오 독립 재평가 (6차, astra) — 감점 사유 중심

대상·채용공고·읽을 것·답할 형식은 3차 의뢰(`reports/reviews/briefs/review-3-brief.md`)와 같다. 그 파일의 "채용공고"와 "답할 것"(특히 2번 감점표: 깎은 점수마다 공고 항목, 점수, 구체적 사유, 근거 파일:줄, 5차 이후 고쳐졌는지/남았는지, 되돌리는 방법·시간·비용)을 그대로 따른다. `reports/reviews/briefs/review_constraints.md`의 평가 제외 규칙(PC·시간 한계로 불가능한 작업은 감점·제안에서 제외, 한계를 정직하게 적었는지만 평가)도 그대로 적용한다.

## 5차 평가(Fable 91 · astra 94, `reports/reviews/fable-5.md`, `astra-5.md`) 이후 바뀐 것 — 사실 목록, 파일·git 이력(`git log ad2a69e..HEAD`)으로 직접 확인할 것
- **사전 등록을 실행 전에 원격에 올림:** docs/20 수정 4 · 5 · 6을 커밋 e247246으로 push(GitHub CI 실행 시각 2026-11-15 00:50:45Z)한 뒤 GPU 실행을 시작했다(10:52 KST = 01:52Z, `artifacts/logs`는 로컬). 수정 7도 5a6b0b6으로 먼저 push했다. 원격 시각은 `gh run list` 또는 GitHub 커밋 페이지로 확인할 수 있다.
- **회귀 게이트:** 알려진 하락을 허용할 때의 정확한 칸 수에 고정, 필드 · 세트 누락도 실패(`src/invoiceguard/regression_gate.py`, `configs/regression_gate.json`, `tests/test_regression_gate.py`).
- **채점 CLI 우회 제거:** `cord_eval` CLI가 `cord_score`(동결 검사 · test 보고서 한 번만 쓰기)로 가고, 동결 원본 바이트를 보존해 해시 + AST 동일성을 실행 시 검사(`configs/frozen_cord_v1_amendments.json`, `configs/frozen_sources/`, `src/invoiceguard/cord_guard.py`, `tests/test_cord_freeze.py`).
- **인보이스 번호 하락 원인:** `reports/eval/invoice_number_drop_dev.md` (+ `scripts/eval/invoice_number_drop.py`).
- **서빙:** 한 서버에 NF4 기본 모델 1개 + 어댑터 2개(M1 v1, M1-cord), 요청마다 선택(`serving/hf_server.py --extra-adapter`, `serving/core.py`, 테스트). 벤치가 서버의 어댑터 해시를 기록하고 오프라인 실행 해시와 비교. dev 전체 측정: 자체 24/24 · CORD 100/100 원문 동일, CORD 5분 지속 부하(`reports/serving/hf_multi_lora_*.json`). 429를 재시도하는 클라이언트로 과부하 goodput 측정(`hf_multi_lora_*_retry.json`).
- **검수 화면:** `src/invoiceguard/app/static/`, `GET /`(CSP self-only), 케이스 목록 · 예시 불러오기 · 수정 · 경고 사유 · 승인 · 내보내기, `tests/test_app.py`, README 8장 스크린샷.
- **사전 등록 실험 결과 (모두 dev 전용, test 미사용):**
  - 수정 4 단가 프롬프트 한 줄 — 부작용(`reports/eval/compare_cord_dev_m1cordprompt_nf4__vs__cord_dev_m1cord_nf4.json`).
  - 수정 5 LoRA ablation(q·k·v·o, r16) — `reports/eval/compare_cord_dev_m1cordqkvo_nf4__vs__cord_dev_m1cord_nf4.json`, `..._m1cordr16_...`.
  - 수정 6 한영 혼합 레이아웃 T07 30장 — `reports/eval/t07_stress.md`.
  - 수정 7 한글 오독의 해상도 가설 — `reports/eval/t07_stress.md`(고해상도 arm).
  - 수정 8 (Fable 6차 지적 후 추가, 실행 전에 push 8c62534): A1 seed 2개 반복(`reports/eval/compare_cord_dev_m1cordqkvo_s2026111*_nf4__vs__*.json`) — 단가 회복은 세 seed 모두, 전체 향상은 seed에 견고하지 않음. 해상도의 일반화(`reports/eval/resolution_dev.md`) — 영어 dev 세트에서는 효과 없음.
- **Fable 6차(95.5, `reports/reviews/fable-6.md`) 이후 추가:** 검수 화면 헤드리스 Chrome 테스트(`tests/test_review_screen_browser.py`), 낡은 문구 정정, 대시보드 최신화(청구 기록 기반 클라우드 지출, 서빙 첫 지표 = dev 전체 원문 일치, 학습 표의 CORD test 어댑터 표시)와 스크린샷 교체, 회귀 게이트 쌍 10개.
- **문서:** README(요약 · 3.3 · 6 · 7 · 8 · 10 · 11장), 대시보드(서빙 표, T07 카드, 탐색 run 이름), plan.md 단계 6, handoff.md.
- **아직 하지 않은 것:** M1-cord의 vLLM 서빙(유료 Pod — 로컬 vLLM은 드라이버 한계로 불가), Pod 안 자동 정지 실증, 하위 품목 개선. CORD test의 단가 하락(M1-cord)은 그대로이며, 수정 3 · 4는 실패했고 q·k·v·o(수정 5 · 8)는 dev에서만 세 seed 모두 회복했다(test로는 확인하지 않음).

## 답할 것 (요약)
1. 공고 기준 점수(100점 만점, 소수 0.5 단위)와 한 줄 판정.
2. 감점표 — 5차 감점 항목마다 "고쳐짐 / 일부 / 남음"과 근거 파일:줄, 새로 찾은 감점이 있으면 추가.
3. 95점 이상이면 남은 감점 중 가장 값싼 개선 2–3개, 95점 미만이면 95점까지 필요한 최소 작업(유료 작업이면 비용).
