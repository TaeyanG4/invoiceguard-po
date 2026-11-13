# RunPod 이번 실행 승인 기록

이 파일은 빈 양식이다. 파일 존재나 프롬프트 전달은 결제 승인이 아니다.
- approved: false
- user_approved_at: null
- quote_observed_at: null
- actual_balance_usd: null
- existing_billable_resources_checked: false
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
- remaining_billable_storage_status: unknown

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
