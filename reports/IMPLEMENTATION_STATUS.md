# 구현 상태 — InvoiceGuard-PO (package v4 기반 구현 진행 기록)

마지막 갱신: 2026-11-14 / 세션 1 (Claude Code desktop, Opus 5.5)

## 요약 표
| 구분 | 상태 | 근거 또는 다음 조치 |
|---|---|---|
| v3 기술 설계와 감사 | inherited_design_only | docs/14_FINAL_AUDIT.md |
| Claude Code 지침·폴더·프롬프트 전환 | completed_package_only | docs/18_PACKAGE_MIGRATION.md |
| T00 환경 확인 + 패키지 검사(G0 일부) | passed_with_evidence (package_contract_tests only) | 아래 T00 로그 |
| Claude Code CLI 실행 | n/a — desktop app(Code 탭)에서 실행 중 | CLI 단독 검증 아님 |
| 전체 공개 데이터 적재·이미지/정답 감사 (T01/G1) | passed_with_evidence | T01 로그, reports/data/ |
| 공개 데이터 누수 없는 분할 (T02) | passed_with_evidence (application_cpu_test) | T02-a 로그, manifests/ |
| 자체 Invoice–PO 합성·렌더러·대사 규칙·평가기 (T02/G2) | passed_with_evidence (application_cpu_test) | T02-b 로그 |
| 관리자 대시보드(읽기 전용 현황판) | implemented_local | `python -m invoiceguard.dashboard --run-tests` |
| Git / GitHub | private repo `TaeyanG4/invoiceguard-po` (사용자 요청으로 생성·push) | 데이터·venv 제외 |
| 실제 RunPod 잔액·견적·Pod 접속 | not_run — 승인 요청 초안만 | reports/RUNPOD_APPROVAL.md |
| 실제 QLoRA·추론·GPU API·측정 | not_run | T03–T08 (GPU 러너 코드 미작성) |
| 제품 API/UI·검수·승인·동시성 테스트 | not_implemented | T06 |

## 환경 (T00, 2026-11-14 확인)
- OS: Windows 10 Pro 10.0.19045, PowerShell 5.1 + Git Bash (MINGW). WSL 사용 안 함.
- 작업 폴더: `H:\dev\invoiceguard-po` (Git 저장소 아님; 상위 폴더에도 저장소 없음 — 새 저장소 초기화는 하지 않음).
- Python: 시스템 3.12.6 / 3.11.9 존재. 프로젝트 로컬 `.venv` = CPython 3.11.9 (`uv venv --python 3.11 .venv`). uv 0.11.29.
- Git 2.45.1. 디스크 여유: H: 652.8GB, C: 742.1GB.
- 로컬 GPU: NVIDIA GeForce RTX 4070 Ti SUPER, 16376 MiB, driver 561.17 (`nvidia-smi`). 로컬 GPU는 이번 단계에서 모델 실행에 사용하지 않음.

## 실행 로그

### T00 — 환경·문서·패키지 검사 (로컬, 2026-11-14)
| 명령 | 결과 |
|---|---|
| `py -3.11 scripts/verify_checksums.py` (수정 전) | exit 0, `PASS: 59 listed files; archive integrity only` |
| `uv venv --python 3.11 .venv` + `uv pip install -r requirements-pack.txt` | jsonschema 4.26.0, PyYAML 6.0.3 설치 |
| `.venv/Scripts/python.exe scripts/verify_pack.py` | exit 0, `pass: 72 package checks` |
| `.venv/Scripts/python.exe scripts/verify_contracts.py` | exit 0, `pass: 63 technical contract/fixture checks` |
| `.venv/Scripts/python.exe scripts/verify_claude_pack.py` | exit 0, `pass: 258 static Claude Code package checks` |

- 검사 스크립트가 `reports/PACK_VALIDATION.json`, `CONTRACT_VALIDATION.json`, `CLAUDE_PACK_VALIDATION.json`을 재작성함. 원본은 실행 전 세션 scratchpad에 백업(저장소 밖).
- 성격: **package_contract_tests**. 앱/모델/GPU 검증 아님.
- 변경 파일: `.venv/`(git 제외), 위 3개 report JSON, 본 보고서 3종.
- 비용: 클라우드 작업 없음, $0.

### T01 — 공개 데이터 적재·프로파일·시각 감사 (로컬, 2026-11-14)
| 명령 | 결과 |
|---|---|
| HF API `api/datasets/alamgirqazi/invoice-ocr-synthetic` | revision `673ff85be462eb7f3715ec188a295dd17ca11115`, license tag cc-by-4.0, gated=false |
| `curl .../resolve/<rev>/data/train-0000{0,1}-of-00002.parquet` → `data/raw/...` | 594,209,287 B / 2,635,217,711 B. SHA256 `62b0432e…85b3`, `7e48694c…d968b` = HF LFS oid 일치 |
| `.venv/Scripts/python.exe -m invoiceguard.public_profile` (1m28s) | exit 0. rows 2814 / base 938 (게시자 주장과 동일), 3품질×938, 이미지 2814개 실제 디코드(PNG), parquet↔`ground_truth_released.json`(Decimal) canonical 품목 938/938 일치, excluded 62건 미포함, locale en 938 |
| 렌더러 템플릿 소스 확인 (commit `91082ede…`) + 12장 육안 감사 | `reports/data/public_visual_audit.md` |

- 프로파일: `reports/data/public_profile.json`. 템플릿 base 수 formal_corporate 189 / pos_thermal 187 / utility_bill 177 / event_ticket 132 / modern_minimal 130 / freelancer_invoice 123. 통화 EUR 408 / GBP 231 / USD 202 / CAD 51 / AUD 45 / `$` 1. 품목 수 1–10. 라벨 숫자형은 모두 double, q×p=amount Decimal 정확 일치(불일치 0), 음수 단가/금액 24, 비정수 수량 15.
- 중복: 같은 이미지 SHA 0, 같은 업무내용 해시 0, 같은 추출대상(품목) 해시 1쌍(둘 다 freelancer_invoice).
- 가시성 판정(렌더러 소스): event_ticket 단가 미인쇄·품명 대문자, pos_thermal 단가 조건부 인쇄·품명 28자 절단, 단가/금액 `%.2f` 인쇄로 소수 3자리 이상 라벨 4개 반올림. 해당 필드는 마스크하고 정답을 새로 만들지 않음.
- 성격: **G1 actual data evidence** (모델 결과 아님). 비용 $0.
- 변경 파일: `pyproject.toml`, `src/invoiceguard/{__init__,canonical,public_data,public_profile,public_visibility}.py`, `tests/test_canonical.py`, `tests/test_public_visibility.py`, `reports/data/public_profile.json`, `reports/data/public_visual_audit.md`. 데이터는 `data/raw`, `data/processed`(Git 제외).

### T02-a — 공개 데이터 누수 없는 분할 (로컬, 2026-11-14)
| 명령 | 결과 |
|---|---|
| `.venv/Scripts/python.exe -m invoiceguard.public_manifest` | exit 0, `manifests/public_canonical_v1.jsonl` 2814행, sha256 `53ad6fe993564c32a27d2b1fe78f611ac476e8e7e2ab1728f8c7f85605cce1a2`, checks pass |
| `.venv/Scripts/python.exe -m pytest tests/` | 36 passed (canonical 24 + visibility 7 + split 5) |

- 그룹: file_name + 업무내용 해시 + 추출대상 해시 + 3품질 이미지 SHA를 union-find로 연결 → 937 그룹(다문서 1). freelancer_invoice 포함 그룹 전체 → OOD pool(123 base). 나머지 seed 20261113 해시 순서로 train/dev/iid = 611/102/102 base.
- 사전 등록 선택(모델 출력과 무관): standard train 200(clean, 학습적격만) / dev 20 + stress 8 / IID final 20×3품질 / OOD final 20×3품질; mini 120/10/4/8/8, mini ⊂ standard 검사 통과.
- 학습 적격: formal 189/189, modern 130/130, utility 174/177, pos_thermal 24/187, event_ticket 0/132 (사유는 manifest summary).
- 누수 검사: base_id·group_id·content_hash·target_hash·image_sha256 모두 pool 간/역할 간 교집합 0. manifest에 라벨 값·PO·이미지 없음.
- 프로필(standard/mini)은 **아직 선택·동결하지 않음** (T03 훈련 전용 파일럿 후 1회 선택).

### T02-b — 대사 규칙·평가기·자체 합성 Invoice–PO (로컬, 2026-11-14)
| 명령 | 결과 |
|---|---|
| `.venv/Scripts/python.exe -m invoiceguard.synth.build` (약 30초) | exit 0. 224건(train 160 T01–T03 / dev 24 T04 / test 40 T05–T06), manifest `manifests/trade_raw_v1.jsonl` sha256 `6a2d089e05756cc0565a90f7150c8dbcf65e0873da717302096fcebbe88a552b`, render_errors 0 |
| `.venv/Scripts/python.exe -m pytest tests/` | 105 passed, 0 failed, 0 skipped (1.9s) |

- 대사 규칙(`reconciliation.py`, `normalization.py`): docs/04 알고리즘, findings enum 그대로. `examples/expected_findings.json`과 결과 완전 일치(B03). B01–B12, E03(별칭 enum 스키마 실패), PO 중복 SKU 거부, 원문 불변 테스트.
- 평가기(`evaluation.py`, `model_output.py`): E1 canonical(Decimal 값 EM, JSON 숫자=type_error, 천단위=형식오류, 마스크 필드 별도 집계, casefold 보조지표 분리), E2 raw EM+수치 EM, E3 SKU 기준 finding 매칭·precision/recall 분모0=null, 실패 응답 분모 유지, 잘린 출력=truncated, fence 복구는 lenient 경로만, base 단위 cluster bootstrap.
- 자체 합성: PO 먼저 생성 → 시나리오별 값 유지/변경 → 정답 문자열만 렌더. 시나리오 7종 oracle 대사 = 기대 코드(15 seed×7 테스트 + 224건 빌드 검사). 유형별 템플릿 균등 순환 배정(유형→레이아웃 결정 없음), 6개 레이아웃 구조 상이(열 순서·2줄 목록·카드형·총액 위치·메타 위치). 렌더 검사: 그린 문자열=정답, 페이지 밖·필드 겹침·열 경계 침범·17px 미만 글자 0. 프롬프트 주입 문구 포함 문서 24건(유형과 무관).
- 수정한 결함: ① 무작위 배정으로 test unknown_sku가 한 레이아웃에 몰림 → 유형별 순환 배정 ② 좁은 열에서 모호수량 문구가 14px 축소·열 침범(겹침 검사가 놓침) → 17px 하한+열 내 줄바꿈+열 경계 검사 ③ 소수 수량에 `587 pcs (587 ctn)` 생성 → 포장 단위>1 보장(PO 단계에서 수량 조정).
- 육안 확인: T01·T03·T05·T06 각 1장 + 수정 후 T05 재확인. 폰트는 Windows 시스템 폰트 9종(파일 SHA만 manifest에 기록, 저장소에 포함 안 함).
- 모델 입력 경계(D06): `extraction_request.py`가 (task, 고정 프롬프트+SHA, 이미지)만 담음. PO·정답·파일명·시나리오 없음.

### 관리자 대시보드·Git (사용자 추가 요청, 2026-11-14)
- `python -m invoiceguard.dashboard --run-tests` → `artifacts/dashboard/index.html`(Git 제외). TASK_BOARD·RUNPOD_APPROVAL·SESSION_HANDOFF·manifest 요약·pytest junit만 읽어 표시. 외부 리소스 없음, 모든 값 HTML escape, 모델 결과는 not_run 고정 표시. 미리보기: `.claude/launch.json`의 `admin-dashboard`(127.0.0.1:8765).
- `git init -b main`, `.gitattributes`(LF 고정 — manifest SHA 재현성), GitHub `TaeyanG4/invoiceguard-po` **PRIVATE** 생성·push (visibility 확인). `data/`, `.venv/`, `artifacts/`, `*.egg-info/` 제외 확인.

### T03 준비 (로컬, 2026-11-14)
- RunPod 콘솔·CLI 접근 없음 → 실제 견적 미관측. `reports/RUNPOD_APPROVAL.md`에 작업량 추정(약 6.5 GPU-h)과 가정 단가별 `budget_plan.py` 출력만 기록, `approved: false` 유지. 비용 $0.

## 기록 방식
각 단계마다: 시각 / T단계 / 실행 환경 / 실행 명령 / 변경 파일 / 실제 exit code와 결과 / 증거 경로 / 데이터·모델 revision / manifest·adapter hash / 과금 승인 범위·실제 비용 / 미완료·실패·원인 / 다음 행동. 사용자 비밀값은 제외한다. 패키지 검사 결과를 앱이나 모델의 결과로 복사하지 않는다.
