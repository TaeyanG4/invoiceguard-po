# 의뢰: 채용 포트폴리오 독립 재평가 (4차) — 감점 사유 중심

대상·채용공고·읽을 것·답할 형식은 3차 의뢰(`reports/reviews/briefs/review-3-brief.md`)와 같다. 그 파일의 "채용공고"와 "답할 것"(특히 2번 감점표: 깎은 점수마다 공고 항목, 점수, 구체적 사유, 근거 파일:줄, 3차 이후 고쳐졌는지/남았는지, 되돌리는 방법·시간·비용)을 그대로 따른다.

## 3차 평가(Fable 82.5 · astra 89, `reports/reviews/fable-3.md`, `astra-3.md`) 이후 바뀐 것 — 사실 목록, 파일·git 이력으로 직접 확인할 것
- **seed 반복 (docs/20 수정 2, 실행 완료):** M1-cord seed 20261114·20261115를 학습해 CORD dev로만 평가. 세 seed의 M1-cord − M0 = +0.050 · +0.044 · +0.060, 평균 +0.051 → 사전 기준 충족(`reports/eval/compare_cord_dev_m1cord_s2026111*_nf4__vs__cord_dev_m0_nf4.json`, `reports/model/train_m1_cord_s2026111*.json`). 추가 seed는 test를 돌리지 않음.
- **단가 개선 시도 (수정 3, 실행 완료) — 효과 없음:** 단가 인쇄 영수증 가중 학습, dev 단가 0.68 → 0.70, 전체 −0.004(`reports/eval/compare_cord_dev_m1cordup_nf4__vs__cord_dev_m1cord_nf4.json`). 사전 기준 미충족을 그대로 보고.
- **CORD 실패 유형 보고서:** `reports/eval/cord_failure_dev.md` (+ 재현 스크립트 `scripts/realdocs/cord_failure_report.py`).
- **채점 통제:** `src/invoiceguard/cord_score.py`(test 채점·비교에 동결 검사, test 보고서 한 번만 쓰기), `cord_guard.py`(끝났거나 채점된 test run 재개 금지), `tests/test_cord_freeze.py`.
- **스키마·재현성:** findings 스키마에 `key`(API 응답 스키마 검증 테스트), `records.TRAIN_DATA_SOURCES`(모든 학습 데이터 옵션이 읽는 manifest 해시 기록).
- **서빙:** 벤치가 모든 동시성에서 답을 채점·잘림·HTTP 상태 코드 기록, `--duration` 지속 부하. 로컬 HF 서버 재측정(`reports/serving/hf_peft_nf4_local_v2.json`, `hf_peft_nf4_local_sustained.json`).
- **GPU 운영:** 학습 메모리 풀이 커져 공유 메모리로 넘친 문제를 `set_per_process_memory_fraction(0.75)`로 해결, PC가 빌 때만 도는 실행기(`scripts/realdocs/gpu_free_runner.py`). 경위는 `handoff.md`.
- **문서:** README 1분 요약·seed 표·수정 3 결과·서빙 재측정, plan·handoff 갱신.
- **아직 하지 않은 것:** CORD 모델의 vLLM 서빙(유료 Pod, 승인 대기), 한영 혼합 레이아웃, 검수 UI.
