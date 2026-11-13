# 세션 인계

- package: v4.0 / technical baseline: audited v3
- project_root: `H:\dev\invoiceguard-po` (Windows 10, PowerShell 5.1 + Git Bash)
- git: `main`, remote `origin` = github.com/TaeyanG4/invoiceguard-po (**private**, 사용자 요청으로 생성)
- python_env: `.venv` (CPython 3.11.9, uv). 실행: `.venv/Scripts/python.exe`
- last_completed_implementation_task: T02 (2026-11-14, passed_with_evidence, CPU only)
- current_task: T03 — blocked on RunPod console quote + user approval
- current_profile: not_selected (standard/mini는 훈련 전용 파일럿 후 1회 선택)
- user_constraints: 영어 / 2일 MVP / RTX 4070 Ti SUPER 16GB / RunPod 우선 / 잔액 약 $10(사용자 제공, 미검증)
- billing_approval: none_for_this_execution (RUNPOD_APPROVAL.md approved: false)
- active_pods_from_this_package: none_created
- actual_account_active_resources: unknown_not_queried
- actual_spend_from_this_package: $0 (클라우드 작업 없음)
- cloud_credentials: not_provided; do not paste secrets
- dataset_revision: alamgirqazi/invoice-ocr-synthetic@673ff85be462eb7f3715ec188a295dd17ca11115
- manifest_hash: public_canonical_v1 53ad6fe993564c32a27d2b1fe78f611ac476e8e7e2ab1728f8c7f85605cce1a2 / trade_raw_v1 6a2d089e05756cc0565a90f7150c8dbcf65e0873da717302096fcebbe88a552b (둘 다 미동결)
- model_revision / adapter_hash: not_run
- running_local_processes: 대시보드 미리보기 http.server(127.0.0.1:8765, 과금 없음) — Claude 앱 Browser 패널에서 시작, 필요 없으면 중지
- next_prompt: prompts/CLAUDE_RESUME.md

## 재현 명령 (로컬)
```text
uv venv --python 3.11 .venv && uv pip install --python .venv/Scripts/python.exe -e ".[dev]"
.venv/Scripts/python.exe -m invoiceguard.public_profile      # data/raw에 parquet 필요 (약 1.5분)
.venv/Scripts/python.exe -m invoiceguard.public_manifest
.venv/Scripts/python.exe -m invoiceguard.synth.build
.venv/Scripts/python.exe -m pytest tests/
.venv/Scripts/python.exe -m invoiceguard.dashboard --run-tests
```

## 다음 작업
1. (사용자) RunPod 콘솔에서 실제 잔액·기존 리소스·GPU 1대 tier/region/단가·스토리지 요금·Full SSH 가능 여부 확인 → 승인 범위 결정.
2. (로컬, 승인 대기 중 가능) GPU 러너 코드: 원문 응답 저장형 추론 러너, QLoRA 학습(확장 이미지 토큰 loss mask 검사·LoRA 대상 모듈·gradient·재로드), 백업 inventory. 실행 전에는 not_run.
3. 선택지: 로컬 RTX 4070 Ti SUPER로 mask/gradient smoke를 무료로 먼저 검증할지 사용자 결정 필요(현재 지침은 RunPod 우선).
4. T06 검수 API/UI(FastAPI+SQLite, CAS·immutable snapshot)는 GPU 없이 진행 가능하나 모델 결과처럼 표시 금지.

## 다음 세션에 남길 항목
실제로 끝낸 단계, 통과/실패 검사, 마지막 명령, 실행 중인 프로세스/Pod, 승인된 최대 시간/금액, 백업 경로·검사, 명확한 다음 명령을 간결하게 기록한다. 채팅 기록만 참조하지 않는다.
