# RunPod 실행 승인 기록

파일 존재나 프롬프트 전달은 결제 승인이 아니다. 승인은 사용자 채팅의 명시적 승인으로만, 실행 1회에만 유효하다.
아래 필드는 **현재 유효한 승인**이다. 2026-11-14 실행은 끝났고 Pod를 삭제했으므로 다시 미승인 상태다. 다음 실행은 새 견적과 새 승인이 필요하다.
- approved: false
- user_approved_at: null
- quote_observed_at: null
- actual_balance_usd: 9.56 (콘솔 Billing, 2026-11-14 18:44 KST — 직전 실행 반영이 최대 1시간 늦을 수 있음)
- existing_billable_resources_checked: true (2026-11-14 18:43 KST: Pod 0 · network volume 0 · 지출률 $0.000/hr)
- provider: RunPod
- pod_id: null
- gpu_model / gpu_count / tier / region: null
- gpu_rate_usd_per_hour: null
- container_disk_gb / volume_disk_gb: null
- running_storage_rate / stopped_storage_rate: null
- full_ssh_file_roundtrip_verified: false
- model_api_tunnel_verified: false
- maximum_approved_spend_usd: null
- maximum_approved_elapsed_time: null
- cutoff_time_and_timezone: null
- approved_stop_method: null
- terminate_authorized: false
- volume_deletion_authorized: false
- backup_destination: null
- backup_sha256_and_restore_verified: false
- approved_budget_change: false
- extra_pod_authorized: false
- auto_top_up_authorized: false
- shutdown_observed_at: null
- remaining_billable_storage_status: none (2026-11-14 18:43 KST 확인)

## 실행 1 — 2026-11-14 A40 (승인 → 실행 → 삭제 확인)
상세 기록: [`runpod/RUNPOD_RUN.md`](runpod/RUNPOD_RUN.md).

| 항목 | 값 |
|---|---|
| 승인 | 사용자 채팅 "A40로 승인" (약 17:55 KST). 범위: GPU 1 · SECURE · EU-SE-1/CA-MTL-1 · container 80GB + volume 20GB · 최대 5h / 총 $3.50 · 컷오프 자동 정지 · 백업 확인 후 terminate |
| 견적 관측 | 17:50 KST — MCP list-gpu-types + 콘솔 Deploy 페이지. 잔액 $9.81, 기존 유료 리소스 0 |
| Pod | `jwvf173fyus06x` · A40 48GB ×1 · SECURE · CA-MTL-1 · host CUDA 13.2 · 생성 17:59:55 KST |
| 단가 | 콘솔 Pod 상세: GPU $0.59 + container 80GB $0.011 + volume 20GB $0.003 = $0.60/hr |
| 직접 SSH · 파일 왕복 | 호스트 키 지문(부팅 로그) = `ssh-keyscan`, 1 MiB scp 왕복 SHA256 일치 |
| 모델 API 터널 | `ssh -L 127.0.0.1:8001 → Pod 127.0.0.1:18001` (이미지의 nginx가 8001 점유), 응답 SHA256 일치, 공인 IP에서 접근 불가, vLLM 요청 1건 터널 경유 성공 |
| 상한 · 컷오프 | $3.50 · 5h · 22:59 KST |
| 정지 방법 | Pod 안 `runpodctl`이 Pod 키로 Unauthorized라 자동 정지를 걸 수 없었음 → 세션 알림(22:47) + 상시 감시, 종료 후 알림 삭제 |
| 백업 | 로컬 `artifacts/runpod/backup.tgz` (SHA256 `1afa8544…1b0c`), 매니페스트 32개 파일 일치, JSON 17개 파싱 |
| 복원 확인 | Pod 어댑터를 로컬 4070 Ti SUPER에서 로드 → dev 2건 출력이 Pod와 동일 |
| 종료 | 18:43:19 KST delete-pod(204) → list-pods 0 · network volume 0 · 콘솔 지출률 $0.000/hr |
| 시간 · 비용 | 43분 24초 × $0.60/hr ≈ **$0.43** (계산값). 콘솔 잔액 $9.81 → $9.56 (18:44, 반영 지연 가능) |
| 추가 Pod · 예산 변경 · 자동충전 | 없음 |

## 승인 요청 초안 (2026-11-14, 세션 1) — 승인 아님, 견적 미관측
- 콘솔/CLI 접근: 없음 (`runpodctl` 미설치, API 키 요청하지 않음). 아래 단가는 **가정값**이며 실제 견적이 아니다.
- 제안 구성: GPU 1대 RTX 4090 24GB (대안 A6000/A40은 재승인), container 20GB + volume 60GB(`/workspace` 보존 여부 확인), Full SSH(공인 IP + TCP 포트) 필수.
- 작업량 기반 GPU 시간 추정(합 약 6.5h, 추정치): 설치·모델 다운로드·데이터 업로드 0.7h / SSH·파일 왕복·터널 검사 0.1h / 파일럿 8장+10스텝 smoke+mask 검사 0.5h / M0 dev 0.3h / QLoRA 80 step(=640 micro-step) 0.5–1h / M1 재로드+dev 0.3h / T05 개선 재평가 0.4h / final 2모델×160장 0.7h / 서빙 측정 0.3h / 백업·유휴 0.5h + 여유.
- `scripts/budget_plan.py --remaining-gpu-hours 6.5` (margin 1.3, 기타 $1) 가정 단가별 출력:

| 가정 단가 | GPU 예상 | 총 예상 | 계획 상한 내 |
|---|---:|---:|---|
| $0.34/h | $2.87 | $3.87 | 예 |
| $0.59/h | $4.99 | $5.99 | 예 |
| $0.69/h | $5.83 | $6.83 | 예 (여유 $1.17) |
| $0.89/h | $7.52 | $8.52 | **아니오** — 이 단가면 mini 프로필 또는 범위 축소 재승인 필요 |

- 스토리지 참고(공식 안내 기준, 미검증): volume 60GB 실행 중 약 $0.008/h, 중지 중 약 $0.016/h(하루 약 $0.39).
- 정지 계획(제안): 승인된 최대 경과시간 도달 또는 누적 $6.5 근접 시 새 작업 중단 → 백업·SHA 비교 → 콘솔에서 **stop 확인**. terminate·volume 삭제는 백업 복원 확인 후 별도 승인. 무인 야간 실행 없음.
- 사용자가 콘솔에서 확인할 항목(비밀값 제외): 실제 잔액, 기존 유료 리소스 유무, GPU 종류·tier(Secure/Community)·region·시간당 요금, container/volume 요금, Full SSH 지원 여부.

목표 배분: GPU 최대 $7 + 기타 최대 $1, 약 $10 중 $2 여유. 실제 잔액·요금·비용은 실행 시 확인한다.
설치·모델 다운로드·파일럿·실패·대기·백업도 예산에 포함한다. 계산기는 자원을 종료하지 않는다. 승인 후에도 실제 종료 상태를 확인해야 한다.
키/토큰/SSH 개인키/비밀번호는 여기에 적지 않는다. 실제 승인 내용과 시각을 남기되 민감한 계정 정보는 제외한다.

## 승인 요청 (2026-11-14 17:50 KST, 세션 2) — 실제 조회값, 아직 승인 아님

### 계정 조회 (모두 읽기 전용)
| 항목 | 값 | 출처 |
|---|---|---|
| 잔액 | $9.81, 지출률 $0.000/hr, 지출 한도 $80/hr, Auto-Pay **Disabled** | 콘솔 Billing 페이지 |
| 기존 유료 리소스 | Pod 0 · network volume 0 · serverless endpoint 0 | MCP list-pods / list-network-volumes / list-endpoints |
| 최근 30일 지출 | $0 (전 항목) | MCP list-billing (day, 30) |
| 등록 SSH 공개키 | ed25519 1개 — 로컬 `~/.ssh/id_ed25519_runpod_rsna_c_20261008`과 일치, 개인키 로컬에만 존재 | MCP get-ssh-keys + 로컬 대조(키 값 출력 없음) |
| 연결 방식 | Runpod MCP(OAuth). API 키 불필요 | — |

### GPU 후보 (24GB 이상, SECURE, host CUDA ≥ 12.8)
| GPU | VRAM | 시간당 | 재고 | 비고 |
|---|---:|---:|---|---|
| **RTX 4090 (제안)** | 24GB | **$0.89** | 전체 HIGH, EU-RO-1 HIGH | 로컬 4070 Ti SUPER와 같은 Ada(sm_89) → 학습 곡선 비교가 가장 깔끔 |
| A40 (대안) | 48GB | $0.59 | 전체 HIGH, EU-SE-1 MEDIUM · CA-MTL-1 LOW | Ampere(sm_86), 더 쌈 |
| RTX A6000 | 48GB | $0.69 | EU-SE-1 LOW | — |
| L4 | 24GB | $0.69 | LOW | 느림 |
가격·재고 출처: list-gpu-types(include=AVAILABILITY, product=POD, SECURE, minCudaVersion 12.8)와 콘솔 Deploy 페이지가 같은 값을 표시. COMMUNITY 4090($0.34)은 재고 LOW이고 공인 IP/직접 SSH가 보장되지 않아 제외.

### 제안 구성
- GPU 1대 RTX 4090, SECURE, `dataCenterIds: [EU-RO-1]`, `gpu.minCudaVersion: "12.8"`
- 이미지 `runpod/pytorch:1.0.2-cu1281-torch280-ubuntu2404`(공식 템플릿 runpod-torch-v280). 학습은 그 위 별도 venv에 `requirements-ml.lock.txt`(torch 2.9.1+cu126 · transformers 4.57.6 · trl 0.25.1 · peft 0.17.1 · bitsandbytes 0.48.2)를 설치해 로컬과 같은 버전으로 맞춘다. vLLM은 다른 venv.
- 포트 `22/tcp`만(직접 SSH · scp). HTTP 포트·Jupyter 없음. 모델 API는 Pod 안 127.0.0.1에만 바인딩하고 SSH 터널(로컬 127.0.0.1:8001)로만 접근.
- container disk 80GB(venv·모델·데이터, 정지 시 삭제) + volume disk 20GB `/workspace`(어댑터·로그·결과 보존)

### 할 일과 합격 기준(학습이 제대로 됐는지 증명이 목적, 성능은 부차)
1. 접속: `ssh.direct` 확인 → 작은 파일 scp 왕복 SHA256 일치 → 터널 확인. 실패 시 학습 전 중단.
2. 환경: 설치 버전·`nvidia-smi`·pip freeze 기록. 모델 revision 89644892, 데이터셋 revision과 split manifest SHA256이 로컬 frozen 값과 같음을 확인.
3. 마스크 감사: 확장된 이미지 토큰 포함 assistant-only loss 360/360 재현.
4. Smoke 10 step: 유한 gradient, 의도한 LoRA 모듈(q_proj/v_proj)만 가중치 변화, 어댑터 저장→재로드 일치.
5. 본 학습 80 step: 로컬 `train_m1_standard_v2`와 같은 config·seed. 허용오차를 미리 고정한다 — step 1 loss 차이 ≤ 2 %, 마지막 10 step 평균 loss 차이 ≤ 10 %. 벗어나면 그대로 failed로 기록.
6. 추론 parity: 로컬 어댑터와 Pod 어댑터를 Pod에서 같은 dev 이미지 8장에 돌려 비교. final test는 쓰지 않는다.
7. vLLM 서빙: 기본 모델 + Pod 어댑터(LoRA)를 127.0.0.1:8001에 띄우고 dev 이미지로 동시성 1/4/8의 지연(p50/p95)·처리량 측정, Transformers 경로 출력과 비교. vLLM이 이 모델의 LoRA를 못 올리면 blocked로 기록하고 기본 모델만 측정.
8. 백업: 어댑터·로그·원시 예측·환경 기록을 로컬로 복사, SHA256 대조, 로컬 4070 Ti SUPER에서 Pod 어댑터 실제 로드 확인.

### 시간·비용
| 항목 | 값 |
|---|---|
| 예상 실행 시간 | 약 3.5시간(설치·다운로드 0.5h · 접속검사 0.25h · 감사+smoke 0.2h · 80 step 약 0.3–0.4h · parity 0.25h · vLLM 0.75h · 백업 0.25h · 실패 여유 약 1h) |
| 예상 비용 | GPU 3.5h × $0.89 = $3.12 + 디스크 약 $0.05 → **약 $3.2** |
| **최대 승인 요청** | **경과 5시간 / 총 $5.00**(GPU 5h $4.45 + 디스크 · 여유). 잔액 $9.81 기준 최악에도 $4.81 남음(> $2 보존) |
| 하드 컷오프 | Pod 생성 후 5시간 또는 **2026-11-14 23:30 KST** 중 이른 시각. Pod 안에 `sleep …; runpodctl pod stop $RUNPOD_POD_ID` 감시 프로세스를 걸어 컷오프에 자동 **정지**(무인 야간 실행 방지) |

### 정지·종료 계획(승인 요청 항목)
- 정상 종료: 8번 백업의 SHA256 일치와 로컬 어댑터 로드를 확인한 뒤 Pod **terminate**(volume disk도 함께 삭제, 되돌릴 수 없음) → list-pods/콘솔 지출률 $0.000/hr로 확인.
- 비정상: 접속 검사 실패·예상 밖 과금·누적 $4.5 도달·컷오프 → 새 작업을 멈추고 백업 → stop. stop 상태는 volume 20GB에 대해 약 $0.0055/h(하루 약 $0.13)만 과금. terminate 여부는 다시 묻는다.
- 추가 Pod·네트워크 볼륨·자동충전·예산 증액은 하지 않는다.

### 합격 기준 수정 (2026-11-14 18:20 KST, Pod 학습 결과가 나오기 전)
5번의 "마지막 10 step 평균 loss 차이 ≤ 10 %"는 로컬 값이 0.0014–0.0367(평균 0.00884)로 매우 작아 상대 10 %가 잡음 수준이라, 정상 학습도 실패로 판정될 수 있는 기준이었다. Pod 학습 출력이 생기기 전에 다음으로 바꾼다(재현 대상: 로컬 `m1_standard_v1`, 동결 M1).
- (a) step 1 loss 상대 차이 ≤ 2 % (로컬 0.3643)
- (b) 80 step 평균 loss 상대 차이 ≤ 10 % (로컬 0.048717)
- (c) 마지막 10 step 평균 loss **절대** 차이 ≤ 0.01 (로컬 0.00884)
- (d) 실제로 학습됨: Pod 마지막 10 step 평균 ≤ Pod step 1 loss의 10 %
- (e) 구조: micro-step 641개 전부 mask 재검사 통과, 학습 파라미터 1,605,632개(텐서 112개, 언어 q/v LoRA만, vision 0), smoke의 어댑터 저장→재로드 텐서 일치
- 하나라도 벗어나면 failed로 기록한다. 다른 GPU(A40 Ampere vs 로컬 Ada)라 비트 단위 동일은 기대하지 않는다.

### 저가 변경안 (2026-11-14 18:00 KST 재조회)
| GPU (SECURE) | 시간당 | 재고(get-gpu-type) | 예상 시간 | 예상 비용 | 판단 |
|---|---:|---|---:|---:|---|
| RTX 4090 | $0.89 | HIGH | 약 3.5h | 약 $3.2 | 원안 |
| **A40 48GB** | **$0.59** | 전체 HIGH · EU-SE-1 MEDIUM · CA-MTL-1 LOW | 약 3.6h | **약 $2.2** | 약 $1 절약. 상한 5h/$3.50로 낮춤 |
| RTX 2000 Ada 16GB | $0.24 | **NONE**(재고 없음) | — | — | 생성 불가 |
| RTX A4000/A4500/A5000 | $0.25–0.27 | NONE | — | — | 생성 불가 |
| COMMUNITY RTX 4090 | $0.34 | LOW | 약 3.5h | 약 $1.3 | 제외: 직접 SSH(공인 IP) 보장 없음. Pod는 1대만 허용이라 실패 시 다른 Pod로 재시도 불가 |
예상 시간은 추정이다. A40 메모리 대역폭(696 GB/s)이 로컬 4070 Ti SUPER(672 GB/s)와 비슷해 80 step을 로컬 실측 1,449초와 비슷하게 본다. 시간 대부분은 설치·다운로드·vLLM 준비라 GPU 속도와 무관하다.
3090·4000번대 재조회 (2026-11-14 18:05 KST, get-gpu-type). 로컬 학습 peak VRAM은 6.52 GB라 12 GB 이상이면 메모리는 충분하다.
| GPU | 클라우드 | 시간당 | 재고 | 판단 |
|---|---|---:|---|---|
| RTX 3090 24GB | SECURE | $0.50 | NONE | 생성 불가 |
| RTX 3090 24GB | COMMUNITY | $0.22 | LOW (host CUDA 12.9 · 13.0 가능) | 가장 쌈(약 3.7h ≈ $0.8). 직접 SSH 보장 없음 → 실패 시 즉시 terminate 후 A40로 넘어가는 예외 승인이 필요 |
| RTX 4000 Ada 20GB | SECURE | $0.28 | NONE | 생성 불가 |
| RTX 4080 SUPER 16GB | COMMUNITY만 | $0.28 | NONE | 생성 불가 |
| RTX 4070 Ti · 4080 | COMMUNITY만 | $0.19 · $0.27 | NONE(17:55 조회) | 생성 불가 |
| RTX PRO 4000 · 5080 (Blackwell) | — | $0.57 · $0.39 | LOW | 제외: lockfile의 torch 2.9.1+cu126은 Blackwell(sm_120)을 지원하지 않아 로컬과 같은 버전으로 학습할 수 없음 |

A40 변경 시: `gpu.id: NVIDIA A40`, `dataCenterIds: [EU-SE-1, CA-MTL-1]`, 나머지(이미지·포트·디스크·컷오프 23:30 KST·종료 계획) 동일, 최대 승인 요청 경과 5h / 총 $3.50.
