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

목표 배분: GPU 최대 $7 + 기타 최대 $1, 약 $10 중 $2 여유. 실제 잔액·요금·비용은 실행 시 확인한다.
설치·모델 다운로드·파일럿·실패·대기·백업도 예산에 포함한다. 계산기는 자원을 종료하지 않는다. 승인 후에도 실제 종료 상태를 확인해야 한다.
키/토큰/SSH 개인키/비밀번호는 여기에 적지 않는다. 실제 승인 내용과 시각을 남기되 민감한 계정 정보는 제외한다.
