# 세션 인계 — 최종 상태 (2026-11-15, 세션 3: RunPod 실행 2 · CORD v2 실사진 트랙 후)

작업 내역은 최신순으로 `handoff.md`, 단계 계획은 `plan.md`에 있다. 이 파일은 환경 · 해시 · 리소스 상태의 스냅샷이다.

- project_root: `H:\dev\invoiceguard-po` (Windows 10, PowerShell 5.1 + Git Bash), git `main`, remote `origin` = github.com/TaeyanG4/invoiceguard-po (**public**, 작성자 이메일 noreply로 재작성한 이력 — `reports/HISTORY_REWRITE.md`)
- push: 사용자 승인(11-15 "전부 승인")으로 사전 등록 커밋을 실행 전에 push — e247246(09:50, 수정 4–6) · 5a6b0b6(11:4x, 수정 7), GitHub CI 통과. 최종 push는 6차 평가 후 README 정리와 함께
- python_env: 제품/CPU `.venv` (3.11.9, `pip install -e ".[dev,app]"`), 모델 `.venv-ml` (정확한 버전 `requirements-ml.lock.txt`) — 둘 다 Git 제외
- decision record: `docs/19_DECISIONS_V5.md`, `docs/20_DECISIONS_V6.md`(CORD v2 실사진 트랙, 지표·통과 기준 사전 고정) — 방향·검토 Fable, 구현 Opus
- completed: T00–T09 (T05 개선 시도는 음성 결과, T06 검수 API + 검수 화면(한국어 한 페이지, 11-15)). 추가: 정밀도 비교(P3), NF4 역양자화 병합(P8a), 어댑터–정밀도 짝 검사(P15), 서빙 회귀 테스트(P12), RunPod 실행 2(L40S: vLLM 정확도 회복 · FP8 · bf16 LoRA), CORD v2 트랙(dev · 학습 · 동결 · test 1회, 사전 기준 충족)
- vLLM 서빙: 로컬은 **blocked**(드라이버 561.17 = CUDA 12.6 < vLLM 0.11.2 요구 12.9). RunPod에서 측정 — 실행 1 A40 속도, 실행 2 L40S에서 원인(어댑터·기본 모델 정밀도 불일치)을 확인하고 NF4 역양자화 병합본으로 **0.960 회복**(HF 경로와 같음), FP8 처리량 +23–33 % (`reports/runpod2/vllm_run2_*.json`)
- blocked / not_run:
  - RunPod: 실행 1 A40 43분($0.437) · 실행 2 L40S 1시간 33분($1.725), 둘 다 백업 해시 확인 후 삭제 · list-pods 0 확인. 합계 **$2.162(청구 기록, `reports/runpod2/billing.json`)**. 활성 승인 없음(`reports/RUNPOD_APPROVAL.md` approved: false). 다음 유료 실행은 새 견적 · 새 승인 필요
  - CORD RunPod 재현(C7): not_run (선택, 승인 필요)
  - seed 반복: CORD dev에서 seed 3개 완료(M1-cord − M0 평균 +0.051, 모두 > 0). 합성 트랙과 CORD test는 seed 1개 · 1회
  - 어려운 합성 데이터 렌더러 v2(Q1–Q3): not_run — CORD 실데이터로 방향 변경
  - 검수 화면: 구현(로컬 한 사용자용, 로그인 · 권한 없음)
  - FSDP/DeepSpeed·DPO: 기각(docs/19) · 하드웨어 한계로 평가 제외(`reports/reviews/briefs/review_constraints.md`)
- profile: standard (동결 `configs/frozen_v1.json`)
- dataset_revision: alamgirqazi/invoice-ocr-synthetic@673ff85be462eb7f3715ec188a295dd17ca11115 · naver-clova-ix/cord-v2@7f0115a4b758a71d6473b8d085751692da2fef98 (CC BY 4.0)
- manifest_hash: public_canonical_v1 1495b06a… / trade_raw_v1 f818ae30… / stress_v1 677167cf… / trade_raw_aug1 35e6acba… (미채택) / cord_v2 42a8371d…
- model: Qwen/Qwen3-VL-2B-Instruct@89644892e4d85e24eaac8bacfd4f463576704203 (weights 7de1838c…77a0)
- adapters: M1 v1 (합성 FINAL) `artifacts/adapters/m1_standard_v1` eb08674120d6489f… · M1-cord `artifacts/adapters/m1_cord_v1` 630d3dd1251f4bad… (둘 다 NF4 위 QLoRA, NF4 기본 모델에만 붙인다)
- freeze: 합성 `configs/frozen_v1_appendix.json` @ 622c22c7 (final 실행 전 커밋 7c5b7f8, 과거 결과로 보존) · CORD `configs/frozen_cord_v1.json` @ 92892c5 (fa750bb에 커밋, code_dirty false)
- final: 합성 `reports/eval/final_summary.md` (B0/M0/M1, 160/160, 1회) · CORD test `reports/eval/cord_test_*.json` (M0 0.689 · M1 v1 0.215 · M1-cord 0.754, M1-cord−M0 +0.065 [+0.027, +0.107], 1회)
- backup: `H:\dev\invoiceguard-po-backup` — 합성 트랙 41파일(`reports/backup_inventory.json`) + CORD 트랙 18파일(어댑터 · 예측 원문, `reports/backup_inventory_cord.json`, 복원 해시 일치)
- serving_local: 한 서버에 어댑터 2개(M1 v1 `m1` · M1-cord `cord`), dev 전체 자체 24/24 · CORD 100/100 원문이 오프라인과 동일, 서버 보고 어댑터 해시 = 오프라인 해시(`reports/serving/hf_multi_lora_*.json`). M1-cord vLLM 서빙은 not_run(RunPod 필요)
- running_processes: HF 모델 서버(127.0.0.1:8001)는 측정 후 매번 종료(11-15 08:56 M1-cord 측정 후 포트 닫힘 · 고아 0 확인). 대시보드 미리보기 서버(127.0.0.1:8765)는 Claude 앱 Browser 패널에서 열려 있을 수 있음 — 과금 없음
- active_paid_resources_from_this_project: none — RunPod Pod 2대 모두 삭제 확인(실행 1 2026-11-14 18:43, 실행 2 22:22:58 KST, list-pods 0)
- runpod_access: Runpod MCP(OAuth). API 키 없음. 등록 SSH 키는 로컬 키와 짝

## 사용자 결정 (2026-11-14 ~ 11-15)
RunPod를 쓰되 유료 리소스마다 실제 견적을 승인받는다. 2B 모델로 끝내고 큰 모델(32B 등)은 돌리지 않는다. 라벨이 없는 실문서(인도 세금계산서)는 정량 평가에서 빼고, 사람 라벨이 있는 CORD v2를 쓴다. PC · 시간 한계로 불가능한 작업은 Fable · astra 평가에서 감점 · 제안 대상에서 뺀다.

## 재개 시
1. `handoff.md`(최신순) → `plan.md` → 이 파일 순서로 읽는다.
2. 남은 일: Fable · astra 재평가(P9, 목표 각 90 이상) → 지적 반영 → 재평가, RunPod 청구 확정값 반영, 사용자 승인 시 push.
3. 합성 final과 CORD test는 각각 1회 실행됐다 — 이후 변경으로 다시 돌린 평가는 exploratory로 표기한다.
