# 세션 인계

- package: v4.0 / technical baseline: audited v3
- project_root: `H:\dev\invoiceguard-po` (Windows 10, PowerShell 5.1 + Git Bash)
- git: `main`, remote `origin` = github.com/TaeyanG4/invoiceguard-po (**private**, 사용자 요청으로 생성)
- python_env: 제품/CPU `.venv` (CPython 3.11.9) · 모델 `.venv-ml` (torch 2.9.1+cu126, transformers 4.57.6, peft 0.17.1, bitsandbytes 0.48.2, torchvision 0.24.1) — 둘 다 Git 제외
- last_completed_implementation_task: T02 (CPU) + T03 로컬 GPU smoke 부분 (2026-11-14)
- current_task: T03 — 로컬 smoke pass, RunPod 부분은 콘솔 로그인·견적·사용자 승인 대기
- pending_user_decision: 포트폴리오를 공고(JobKorea 50342762) 기준 "OCR 기준선 + 비교표 + vLLM 서빙" 중심으로 조정할지 (Fable 독립 검토 반영, 미결정)
- current_profile: not_selected (standard/mini는 훈련 전용 파일럿 후 1회 선택)
- user_constraints: 영어 / 2일 MVP / RTX 4070 Ti SUPER 16GB(사용자가 로컬 시험 승인) / RunPod 잔액 약 $10(미검증)
- billing_approval: none_for_this_execution (RUNPOD_APPROVAL.md approved: false)
- active_pods_from_this_package: none_created
- actual_account_active_resources: unknown_not_queried
- actual_spend_from_this_package: $0 (클라우드 작업 없음; 로컬 GPU 전기만 사용)
- cloud_credentials: not_provided; do not paste secrets. RunPod 로그인이 필요해지면 사용자에게 먼저 알린다.
- dataset_revision: alamgirqazi/invoice-ocr-synthetic@673ff85be462eb7f3715ec188a295dd17ca11115
- manifest_hash: public_canonical_v1 1495b06a45881dbfe8e911ff8f1ee6498786743a5cae989ff33bb584834320d7 / trade_raw_v1 f818ae30cc855521b2a758942fc979263e9cdedf7b42d2743171678dd7fef0ae (둘 다 미동결)
- model_revision: Qwen/Qwen3-VL-2B-Instruct@89644892e4d85e24eaac8bacfd4f463576704203 (weights SHA256 7de1838c…77a0, `models/`)
- adapter_hash: smoke 전용 `artifacts/adapters/local_smoke_10step/adapter_model.safetensors` ffadbcd4…cec4 (M1 아님). M1 not_run
- running_local_processes: 대시보드 미리보기 서버(127.0.0.1:8765, 과금 없음)가 Browser 패널에서 시작됐을 수 있음. GPU 작업 없음
- next_prompt: prompts/CLAUDE_RESUME.md

## 재현 명령 (로컬)
```text
uv venv --python 3.11 .venv && uv pip install --python .venv/Scripts/python.exe -e ".[dev]"
.venv/Scripts/python.exe -m invoiceguard.public_profile      # data/raw에 parquet 필요 (약 1.5분)
.venv/Scripts/python.exe -m invoiceguard.public_manifest
.venv/Scripts/python.exe -m invoiceguard.synth.build
.venv/Scripts/python.exe -m pytest tests/
# 모델 (GPU): .venv-ml 생성 후
.venv-ml/Scripts/python.exe -m invoiceguard.vlm.smoke masks|pilot|train
```

## 다음 작업
1. (사용자 결정) 포트폴리오 방향: 비교 실험(B0 OCR / M0 / M1 [/ 외부 API]) + vLLM 서빙 중심으로 조정할지.
2. (로컬 GPU 가능) M1 본학습(깨끗한 base에서 재시작) 전에 프로필 동결; 공개 프롬프트의 코드펜스 문제는 dev에서만 다루고 바꾸면 M0/M1 모두 재평가.
3. (사용자) RunPod 콘솔 로그인 → 잔액·기존 리소스·GPU 1대 tier/region/단가·스토리지·Full SSH 확인 → 승인 범위 결정.
4. T06 검수 API는 최소 범위로 GPU 없이 진행 가능(모델 결과처럼 표시 금지).

## 다음 세션에 남길 항목
실제로 끝낸 단계, 통과/실패 검사, 마지막 명령, 실행 중인 프로세스/Pod, 승인된 최대 시간/금액, 백업 경로·검사, 명확한 다음 명령을 간결하게 기록한다. 채팅 기록만 참조하지 않는다.
