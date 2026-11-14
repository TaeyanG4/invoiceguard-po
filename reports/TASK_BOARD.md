# T00–T09 작업표

이 표는 구현 진행용이다. 배포 문서를 만들었다는 이유로 T00/G0 전체를 통과 처리하지 않는다.
상태: `not_started`, `in_progress`, `blocked`, `failed`, `passed_with_evidence`.

| 단계 | 작업 | 실행 위치 | 상태 | 증거/차단 사유 |
|---|---|---|---|---|
| T00 | 기존 코드·환경·문서·패키지 검사 | 로컬 | passed_with_evidence | checksums 59 PASS(수정 전), verify_pack 72 / contracts 63 / claude_pack 258 pass (2026-11-14). package_contract_tests만 해당 |
| T01 | 데이터 다운로드·프로파일·12장 이미지/라벨 감사 | 로컬 | passed_with_evidence | rev 673ff85b, shard SHA=LFS oid, 2814행 디코드, 938 base, 12장 육안+렌더러 소스 가시성 (reports/data/) |
| T02 | 누수 없는 분할·합성 렌더러·채점기·대사 규칙 | 로컬 | passed_with_evidence | 공개 manifest 1495b06a… 누수 0 / 자체 224건 manifest f818ae30… 렌더=정답·family 누수 0 / 대사 B01–B12·평가기 E01–E05 / pytest 106 pass (CPU only) |
| T03 | 실견적 승인·SSH/백업 검사·모델/10스텝 smoke | 로컬 GPU(승인) / RunPod | passed_with_evidence (local + RunPod) | 로컬: mask 360/360, 파일럿, 10-step QLoRA·재로드 pass. RunPod(2026-11-14, A40, 승인 $3.50): 실견적·호스트키·scp 왕복 SHA256·터널 pass, mask 360/360, 입력 해시 전부 일치, smoke pass, 80 step 재학습이 사전 고정 기준 5개 통과 (reports/runpod/RUNPOD_RUN.md) |
| T04 | 프로필 동결·M0 기준선·M1 학습/재로드 | 로컬 GPU | passed_with_evidence | standard 동결(configs/frozen_v1.json), TRL M1 80 step·어댑터 eb086741…, 디스크 재로드 추론, M0/M1/B0 dev |
| T05 | dev 실패 분석·개선 한 가지 | 로컬 | passed_with_evidence (negative) | 실패 분류(reports/eval/failures_m1_dev_v1.md), 개선=train 보강 32건 → 효과 없음, M1 v1 유지(dev_summary.md) |
| T06 | 검수 UI/API·버전·승인·export | 로컬 | passed_with_evidence (minimal API) | FastAPI+SQLite 검수 API, CAS·스냅샷·429/503/504·재시작 복구, 테스트 12개. 검수 화면 UI는 관리자 대시보드만(검수용 UI 미구현) |
| T07 | 실제 GPU API·지연/메모리/실패 측정 | 로컬 GPU / RunPod | passed_with_evidence (HF+PEFT local · vLLM RunPod) | HF 서버: 실제 타임아웃 취소·bounded queue·동시성 측정(reports/serving/). vLLM 0.11.2: 로컬은 드라이버로 blocked, RunPod A40에서 동시성 1–8 측정(실패 0). 단 vLLM에서 M1 정확도 0.849 vs HF 0.960 — 원인 미확정(reports/serving/vllm_bf16_a40.json) |
| T08 | M0/M1 동일 frozen final 평가 | 로컬 GPU | passed_with_evidence | 동결 부록 7c5b7f8 후 1회: B0/M0/M1 160/160, reports/eval/final_summary.md |
| T09 | 결과/어댑터 백업·복원·승인된 과금 리소스 정리 | 로컬 / RunPod | passed_with_evidence (local + RunPod) | 로컬: 41파일 저장소 밖 백업·해시 일치(reports/backup_inventory.json). RunPod: 백업 32파일 SHA256 일치·로컬 복원 확인 후 Pod 삭제, list-pods 0·지출률 $0/hr (약 $0.43 추정, reports/runpod/RUNPOD_RUN.md) |

## Gate 상태 (docs/16)
| Gate | 상태 |
|---|---|
| G0 문서/schema/config/fixture | pass (package_contract_tests 범위) |
| G1 실제 데이터/라벨 | pass (reports/data/public_visual_audit.md) |
| G2 분할·evaluator·PO 경계 | pass (application_cpu_test; manifests/*.summary.json, tests/) |
| G3 견적·FullSSH·파일럿·mask | pass: local mask·pilot·10-step; RunPod 실견적·승인·FullSSH·scp 왕복·터널 (reports/RUNPOD_APPROVAL.md) |
| G4 학습/재로드·M0/M1 dev | pass (local GPU; reports/model, reports/eval/dev_summary.md) |
| G5 검수 API/경쟁조건 | pass (application_cpu_test 12 + live HF cancel/queue probe) |
| G6 final·서빙 | pass with caveat: final pass (once, frozen); HF serving measured; vLLM measured on RunPod (speed), LoRA accuracy under vLLM open |
| G7 백업·과금 정리 | pass: local hash-verified backup; RunPod 백업 32파일 SHA256 일치·로컬 복원 확인 후 Pod 삭제, list-pods 0·지출률 $0/hr 확인 (약 $0.43) |

T03 승인을 기다리는 동안 독립적인 로컬 작업은 진행할 수 있다. GPU 결과 없는 기능 시연은 fixture/replay라고 명시한다.
