# 세션 인계 — 최종 상태 (2026-11-14)

- project_root: `H:\dev\invoiceguard-po` (Windows 10, PowerShell 5.1 + Git Bash), git `main`, remote `origin` = github.com/TaeyanG4/invoiceguard-po (**private**)
- push: 사용자 지시에 따라 프로젝트 완료 시 1회 push (이 문서 커밋 직후)
- python_env: 제품/CPU `.venv` (3.11.9, `pip install -e ".[dev,app]"`), 모델 `.venv-ml` (정확한 버전 `requirements-ml.lock.txt`) — 둘 다 Git 제외
- decision record: `docs/19_DECISIONS_V5.md` (방향·검토 Fable, 구현 Opus)
- completed: T00–T02, T03(로컬), T04, T05(개선 시도는 음성 결과), T06(최소 검수 API; 검수 UI 미구현), T07(HF+PEFT 서빙), T08(final 1회), T09(로컬 백업)
- blocked / not_run:
  - vLLM 서빙: **blocked** — `vllm/vllm-openai:v0.11.2`는 CUDA ≥ 12.9 필요, 로컬 드라이버 561.17 = CUDA 12.6. 해제: 사용자가 NVIDIA 드라이버 ≥ 575 업데이트(시스템 변경, 사용자 작업) 또는 RunPod 승인. 스크립트 `src/invoiceguard/serving/vllm_bench.py` 준비됨.
  - RunPod: **not_run** — 로그인·실견적 승인 없음. 비용 $0. 생성한 Pod/스토리지 없음.
  - FSDP/DeepSpeed·DPO: 기각(docs/19).
- profile: standard (동결 `configs/frozen_v1.json`)
- dataset_revision: alamgirqazi/invoice-ocr-synthetic@673ff85be462eb7f3715ec188a295dd17ca11115
- manifest_hash: public_canonical_v1 1495b06a… / trade_raw_v1 f818ae30… / stress_v1 677167cf… / trade_raw_aug1 35e6acba… (M1 v2 전용, 미채택)
- model: Qwen/Qwen3-VL-2B-Instruct@89644892e4d85e24eaac8bacfd4f463576704203 (weights 7de1838c…77a0)
- M1 adapter (final에 사용): `artifacts/adapters/m1_standard_v1/adapter_model.safetensors` eb08674120d6489fb9f2ae4cf72038588794e09b3d337a5239d8a6078aff2868
- freeze appendix: `configs/frozen_v1_appendix.json` @ git 622c22c7 (final 실행 전 커밋 7c5b7f8)
- final: `reports/eval/final_summary.md` (B0/M0/M1, 160/160, 1회)
- backup: `H:\dev\invoiceguard-po-backup` (어댑터·예측 41파일, 해시 검증 `reports/backup_inventory.json`)
- running_processes: 없음 (HF 모델 서버·검수 API는 시연 후 종료, 포트 8000/8001 닫힘 확인). 대시보드 미리보기 서버(127.0.0.1:8765)는 Claude 앱 Browser 패널에서 열려 있을 수 있음 — 과금 없음.
- active_paid_resources_from_this_project: none (RunPod 미사용)

## 사용자 결정 (2026-11-14, 프로젝트 종료 후)
RunPod 사용과 NVIDIA 드라이버 업데이트를 **하지 않기로 결정**. vLLM 서빙 측정은 blocked, 클라우드 GPU 운영·비용 증거는 not_run으로 유지한다. 재개 시 사용자가 다시 요청하지 않으면 이 두 항목을 제안하지 않는다.

## 재개 시
1. `prompts/CLAUDE_RESUME.md`로 시작하고 이 파일·`reports/IMPLEMENTATION_STATUS.md`를 대조한다.
2. 남은 선택지: (a) 드라이버 업데이트 후 vLLM 벤치(`vllm_bench up` → `run --label vllm_bf16`), (b) RunPod 승인 시 S9(1-GPU, 견적·FullSSH·백업·종료 확인), (c) 검수 화면 UI.
3. final은 이미 1회 실행됨 — 이후 어떤 변경으로 다시 돌린 평가는 exploratory로 표기한다.
