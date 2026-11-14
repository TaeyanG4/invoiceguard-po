# 세션 인계 — 최종 상태 (2026-11-14, 세션 2: RunPod 재현 후)

- project_root: `H:\dev\invoiceguard-po` (Windows 10, PowerShell 5.1 + Git Bash), git `main`, remote `origin` = github.com/TaeyanG4/invoiceguard-po (**public**, 2026-11-14 작성자 이메일을 noreply로 재작성한 이력으로 새로 만듦 — `reports/HISTORY_REWRITE.md`)
- push: 사용자 지시에 따라 프로젝트 완료 시 1회 push (이 문서 커밋 직후)
- python_env: 제품/CPU `.venv` (3.11.9, `pip install -e ".[dev,app]"`), 모델 `.venv-ml` (정확한 버전 `requirements-ml.lock.txt`) — 둘 다 Git 제외
- decision record: `docs/19_DECISIONS_V5.md` (방향·검토 Fable, 구현 Opus)
- completed: T00–T02, T03(로컬 + RunPod), T04, T05(개선 시도는 음성 결과), T06(최소 검수 API; 검수 UI 미구현), T07(HF+PEFT 로컬 · vLLM RunPod), T08(final 1회), T09(로컬 백업 + RunPod 백업·삭제)
- blocked / not_run:
  - vLLM 서빙: 로컬은 **blocked**(드라이버 561.17 = CUDA 12.6). RunPod A40에서 **측정 완료**(reports/serving/vllm_bf16_a40.json). 미해결: vLLM에서 M1 정확도 0.849 vs HF 0.960, 문서마다 합계 4필드 손실로 추정 — 원인 미확정(NF4 학습 기본 vs bf16 서빙 기본 불일치 유력). 다음 확인: 원문 저장(수정 완료) 상태로 재측정, vLLM bitsandbytes 기본 모델 또는 병합 어댑터 비교.
  - RunPod: **완료** — Pod `jwvf173fyus06x`(A40, CA-MTL-1) 17:59:55–18:43:19 KST, 약 $0.43. 삭제 후 list-pods 0 · network volume 0 · 지출률 $0/hr 확인. 활성 승인 없음(`reports/RUNPOD_APPROVAL.md` approved: false로 복귀).
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
- active_paid_resources_from_this_project: none — RunPod Pod 1대를 만들고 삭제까지 확인(2026-11-14 18:43 KST). 콘솔 잔액 $9.56(18:44, 반영 지연 가능)
- runpod_access: Runpod MCP(OAuth, `/mcp`에서 로그인 유지). API 키 없음. 등록 SSH 키는 로컬 `~/.ssh/id_ed25519_runpod_rsna_c_20261008`과 짝

## 사용자 결정 (2026-11-14)
처음에는 RunPod과 드라이버 업데이트를 하지 않기로 했다가, 포트폴리오 검토 후 **RunPod 사용으로 변경**("모델 성능보다 학습이 제대로 되었는지가 중요"). 드라이버는 그대로 둔다. RunPod 실행 1회 완료(reports/runpod/RUNPOD_RUN.md). 다음 유료 실행은 새 견적·새 승인이 필요하다.

## 재개 시
1. `prompts/CLAUDE_RESUME.md`로 시작하고 이 파일·`reports/IMPLEMENTATION_STATUS.md`를 대조한다.
2. 남은 선택지: (a) vLLM LoRA 정확도 저하 원인 확인(새 승인 필요, 원문 저장 벤치 재실행 · bnb 기본 모델 · 병합 어댑터), (b) 검수 화면 UI, (c) seed 반복으로 학습 분산 확인.
3. final은 이미 1회 실행됨 — 이후 어떤 변경으로 다시 돌린 평가는 exploratory로 표기한다.
