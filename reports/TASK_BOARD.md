# T00–T09 작업표

이 표는 구현 진행용이다. 배포 문서를 만들었다는 이유로 T00/G0 전체를 통과 처리하지 않는다.
상태: `not_started`, `in_progress`, `blocked`, `failed`, `passed_with_evidence`.

| 단계 | 작업 | 실행 위치 | 상태 | 증거/차단 사유 |
|---|---|---|---|---|
| T00 | 기존 코드·환경·문서·패키지 검사 | 로컬 | passed_with_evidence | checksums 59 PASS(수정 전), verify_pack 72 / contracts 63 / claude_pack 258 pass (2026-11-14). package_contract_tests만 해당 |
| T01 | 데이터 다운로드·프로파일·12장 이미지/라벨 감사 | 로컬 | passed_with_evidence | rev 673ff85b, shard SHA=LFS oid, 2814행 디코드, 938 base, 12장 육안+렌더러 소스 가시성 (reports/data/) |
| T02 | 누수 없는 분할·합성 렌더러·채점기·대사 규칙 | 로컬 | passed_with_evidence | 공개 manifest 53ad6fe9… 누수 0 / 자체 224건 manifest 6a2d089e… 렌더=정답·family 누수 0 / 대사 B01–B12·평가기 E01–E05 / pytest 102 pass (CPU only) |
| T03 | 실견적 승인·SSH/백업 검사·모델/10스텝 smoke | RunPod 승인 후 | blocked | 콘솔 견적·Full SSH 확인과 사용자 승인 필요(초안: RUNPOD_APPROVAL.md). GPU 러너 코드 미작성 |
| T04 | 프로필 동결·M0 기준선·M1 학습/재로드 | RunPod | not_started | 실제 모델 미실행 |
| T05 | dev 실패 분석·개선 한 가지 | 로컬/승인된 Pod | not_started | 예측 없음 |
| T06 | 검수 UI/API·버전·승인·export | 로컬 | not_started | 제품 코드 미구현 |
| T07 | 실제 GPU API·지연/메모리/실패 측정 | 승인된 Pod | not_started | 실측 없음 |
| T08 | M0/M1 동일 frozen final 평가 | 승인된 Pod | not_started | final 미실행 |
| T09 | 결과/어댑터 백업·복원·승인된 과금 리소스 정리 | 로컬/RunPod | not_started | 아직 자원 생성 안 함 |

## Gate 상태 (docs/16)
| Gate | 상태 |
|---|---|
| G0 문서/schema/config/fixture | pass (package_contract_tests 범위) |
| G1 실제 데이터/라벨 | pass (reports/data/public_visual_audit.md) |
| G2 분할·evaluator·PO 경계 | pass (application_cpu_test; manifests/*.summary.json, tests/) |
| G3 견적·FullSSH·파일럿·mask | not_run |
| G4 학습/재로드·M0/M1 dev | not_run |
| G5 검수 API/경쟁조건 | not_run |
| G6 final·서빙 | not_run |
| G7 백업·과금 정리 | not_run |

T03 승인을 기다리는 동안 독립적인 로컬 작업은 진행할 수 있다. GPU 결과 없는 기능 시연은 fixture/replay라고 명시한다.
