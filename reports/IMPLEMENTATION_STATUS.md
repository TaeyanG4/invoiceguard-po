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
| 관리자 대시보드(사이드바·데이터 직접 보기·평가/서빙 차트, 읽기 전용, 기본 다크) | implemented_local | `.venv/Scripts/python.exe -m invoiceguard.dashboard_server --port 8765` (127.0.0.1) |
| Git / GitHub | **public** repo `TaeyanG4/invoiceguard-po` (사용자 요청으로 생성 → 공개 전 작성자 이메일 noreply 재작성 후 재생성) | 데이터·venv 제외, `reports/HISTORY_REWRITE.md` |
| 실제 RunPod 잔액·견적·Pod 접속 | not_run — 승인 요청 초안만 | reports/RUNPOD_APPROVAL.md |
| 로컬 GPU smoke (RTX 4070 Ti SUPER, 사용자 승인) | M01 mask pass / 파일럿 8장 실행 / 10-step 학습 — 아래 로그 | reports/model/local_smoke_*.json |
| RunPod(클라우드) 실행·비용 | not_run — 사용자 로그인·견적 승인 없음, 비용 $0 | reports/RUNPOD_APPROVAL.md (초안만) |
| 검수 API·버전·승인·동시성 / 검수 화면 UI | API implemented + tested (12) · LIVE 종단 시연 / **UI not_implemented** (읽기 전용 관리자 대시보드만) | src/invoiceguard/app/, reports/serving/live_e2e_demo.json |
| 로컬 GPU 본학습·dev·final 평가 | passed_with_evidence (HF NF4, final 1회) | reports/model/, reports/eval/dev_summary.md, reports/eval/final_summary.md |
| 서빙 | HF+PEFT 서버 실측 passed_with_evidence · **vLLM blocked**(이미지 CUDA≥12.9, 드라이버 561.17=12.6) | reports/serving/ |

## 환경 (T00, 2026-11-14 확인)
- OS: Windows 10 Pro 10.0.19045, PowerShell 5.1 + Git Bash (MINGW). WSL 사용 안 함.
- 작업 폴더: `H:\dev\invoiceguard-po`. T00 시점에는 Git 저장소가 아니었고, 이후 사용자 요청으로 `git init` + private GitHub 저장소를 만들었다(아래 Git 절).
- Python: 시스템 3.12.6 / 3.11.9 존재. 프로젝트 로컬 `.venv` = CPython 3.11.9 (`uv venv --python 3.11 .venv`). uv 0.11.29.
- Git 2.45.1. 디스크 여유: H: 652.8GB, C: 742.1GB.
- 로컬 GPU: NVIDIA GeForce RTX 4070 Ti SUPER, 16376 MiB, driver 561.17 (`nvidia-smi`). T00 단계에서는 사용하지 않았고, 이후 사용자 승인("4070 Ti SUPER로 먼저 시험")으로 학습·평가·서빙의 주 실행 위치가 되었다.

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
| `.venv/Scripts/python.exe -m invoiceguard.public_manifest` | exit 0, `manifests/public_canonical_v1.jsonl` 2814행, sha256 `1495b06a45881dbfe8e911ff8f1ee6498786743a5cae989ff33bb584834320d7`, checks pass |
| `.venv/Scripts/python.exe -m pytest tests/` | 36 passed (canonical 24 + visibility 7 + split 5) |

- 그룹: file_name + 업무내용 해시 + 추출대상 해시 + 3품질 이미지 SHA를 union-find로 연결 → 937 그룹(다문서 1). freelancer_invoice 포함 그룹 전체 → OOD pool(123 base). 나머지 seed 20261113 해시 순서로 train/dev/iid = 611/102/102 base.
- 사전 등록 선택(모델 출력과 무관): standard train 200(clean, 학습적격만) / dev 20 + stress 8 / IID final 20×3품질 / OOD final 20×3품질; mini 120/10/4/8/8, mini ⊂ standard 검사 통과.
- 학습 적격: formal 189/189, modern 130/130, utility 174/177, pos_thermal 24/187, event_ticket 0/132 (사유는 manifest summary).
- 누수 검사: base_id·group_id·content_hash·target_hash·image_sha256 모두 pool 간/역할 간 교집합 0. manifest에 라벨 값·PO·이미지 없음.
- 프로필(standard/mini)은 **아직 선택·동결하지 않음** (T03 훈련 전용 파일럿 후 1회 선택).

### T02-b — 대사 규칙·평가기·자체 합성 Invoice–PO (로컬, 2026-11-14)
| 명령 | 결과 |
|---|---|
| `.venv/Scripts/python.exe -m invoiceguard.synth.build` (약 30초) | exit 0. 224건(train 160 T01–T03 / dev 24 T04 / test 40 T05–T06), manifest `manifests/trade_raw_v1.jsonl` sha256 `f818ae30cc855521b2a758942fc979263e9cdedf7b42d2743171678dd7fef0ae`, render_errors 0 |
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

### 정정 — manifest 해시 기준 바이트 (2026-11-14)
- 발견: Windows `Path.write_text`가 CRLF로 저장해 manifest SHA가 CRLF 바이트 기준이었음. Git(`.gitattributes eol=lf`)은 LF로 저장하므로 clone 후 SHA가 달라지는 문제.
- 조치: 모든 기록기를 `newline="
"`로 고정, manifest 재생성. 내용은 이전과 동일(줄바꿈만 차이, diff 확인). 새 기준 해시: public `1495b06a45881dbfe8e911ff8f1ee6498786743a5cae989ff33bb584834320d7`, trade `f818ae30cc855521b2a758942fc979263e9cdedf7b42d2743171678dd7fef0ae` (= 커밋된 LF blob SHA와 일치 확인). 재발 방지 테스트 `test_manifests_are_lf_only_so_hashes_survive_git_checkout` 추가 → pytest 106 passed.
- 이전 해시(53ad6fe9…, 6a2d089e…)는 폐기. 어떤 평가에도 사용되지 않았음.

### T03 준비 (로컬, 2026-11-14)
- RunPod 콘솔·CLI 접근 없음 → 실제 견적 미관측. `reports/RUNPOD_APPROVAL.md`에 작업량 추정(약 6.5 GPU-h)과 가정 단가별 `budget_plan.py` 출력만 기록, `approved: false` 유지. 비용 $0.

### T03-local — 로컬 GPU smoke (사용자 지시: "4070 Ti SUPER로 먼저 시험", 2026-11-14)
- 사전 점검: `nvidia-smi` 사용 1.25GB / 여유 14.8GB, 전력 19W(유휴), SM 약 35%는 데스크톱 부하 → 사용 가능 판단. 다른 python.exe(3.12) 1개가 GPU 컨텍스트 보유(소량).
- 모델: `Qwen/Qwen3-VL-2B-Instruct` revision `89644892e4d85e24eaac8bacfd4f463576704203` (Apache-2.0), `model.safetensors` 4,255,140,312 B, SHA256 `7de1838c87a5349b016c26a1c3f7d2bc400a3d485f95ef39a7059ffd734977a0` = HF LFS oid. `models/`(Git 제외).
- ML 환경 `.venv-ml`(Git 제외): torch 2.9.1+cu126, torchvision 0.24.1+cu126, transformers 4.57.6, peft 0.17.1, bitsandbytes 0.48.2, accelerate 1.10.1. (transformers 5.x는 일부러 쓰지 않음 — 검증된 4.57 계열 고정.)
- 로딩 조건(M0/M1 공통): NF4 + double quant, bf16 compute, **vision tower·lm_head는 양자화하지 않음**(읽기 품질 보존), sdpa, max_pixels 786,432 → 이미지 토큰 690–736.

| 명령 (`.venv-ml/Scripts/python.exe -m invoiceguard.vlm.smoke …`) | 결과 |
|---|---|
| `masks` (50s, CPU processor) | **pass**. standard train 360건(공개 200 + 자체 160) 모두: prompt/이미지/비전 토큰 -100, 학습 구간 decode == 정답 JSON+`<|im_end|>`, 이미지 토큰 수 == grid 계산값, 잘림 없음. 최대 총 길이 1,557(예산 6,144), 정답 최대 511토큰(한도 1,536) |
| `pilot` (5m39s) | base NF4, **train 이미지 8장**(공개 4·자체 4, seed 고정). 자체 4/4 JSON·스키마 유효. 공개 4/4 `json_invalid` — 원인: 모델이 ```json 코드펜스로 감쌈(공개 프롬프트에 "Markdown 금지" 문구 없음). 생성 190–714토큰, **문서당 28–51초(약 10 tok/s)**, peak VRAM 2.33–2.37GB. 원문: `artifacts/runs/local_pilot_*/` |
| `pytest tests/test_vlm_masks.py` (.venv-ml) | 3 passed; 제품 `.venv`에서는 torch 없음으로 skip |
| `train` (10 optimizer step × grad accum 8 = 80 micro-step, lr 1e-4, seed 20261113) | **pass**. 학습 파라미터 1,605,632개(전체 1,424,494,592의 0.11%) = 언어모델 28층 q_proj/v_proj LoRA A/B 112 텐서만, vision 학습 0·예상 밖 학습 텐서 0. loss 0.431→0.101(step 9 0.054), 모든 step gradient 유한, 112/112 LoRA 텐서 실제 변경, mask 실패 0, non-finite loss 0. 학습 79.7s(7.97 s/optimizer step), peak VRAM 7.09GB. 어댑터 저장 `artifacts/adapters/local_smoke_10step/` (`adapter_model.safetensors` SHA256 `ffadbcd4704fc67a8669bfd4db3df88bb29e5c537e784c14a01e8f05fcbacec4`) → 모델 완전 해제 후 base+adapter 재로드, LoRA 텐서 동일 확인, 재로드 모델로 train 문서 1건 추론: JSON·스키마 유효, 534토큰 57.5s |

- smoke 어댑터는 검증용이며 M1이 아니다. M1 본학습은 계약대로 깨끗한 base·seed·optimizer로 다시 시작한다(training_after_smoke).
- 예상 비용 감각(로컬 실측 기반): 본학습 standard 80 step ≈ 11분. 병목은 생성 속도(HF generate + NF4 ≈ 9–10 tok/s, 문서당 30–57초) — final 2모델×160장 ≈ 3–4시간 → 서빙/추론 가속이 실제 필요.

- 해석 주의: 파일럿은 학습 이미지에 대한 진단이며 평가 결과가 아니다. 공개 태스크 실패는 형식(코드펜스) 문제로, primary strict 지표에서 실패로 집계되는 것이 계약대로다. 10 tok/s는 bitsandbytes NF4 + HF generate의 속도로, 서빙 단계에서 개선 대상(측정 근거).

### 대시보드 개편 (사용자 요청: 사이드바·데이터 직접 확인, 2026-11-14)
- `src/invoiceguard/dashboard_server.py` + `dashboard_static/`(vanilla JS, 외부 리소스 없음): 사이드바 9개 페이지(개요/진행 단계·게이트/공개 데이터/자체 Invoice–PO/분할·manifest/모델·학습/RunPod 비용·승인/테스트/검수 앱). 공개 데이터: 필터 목록 → 이미지(parquet에서 1회 추출·SHA 검증 후 캐시) + canonical 정답 + 필드별 가시성 마스크. 자체 데이터: 이미지 + 정답 + 발주서 + 기대/oracle findings.
- 안전: 127.0.0.1 전용(다른 host는 ValueError), GET/HEAD만, Host 헤더 검사(DNS rebinding), ID 정규식+manifest 등록 여부 이중 검사, CSP·nosniff, 프런트는 textContent만 사용. 정답·발주서는 "평가 데이터, 모델 입력 아님"으로 표시.
- 백그라운드 서브에이전트가 구현, 메인 세션이 검증: Browser 패널에서 좁은 화면(386px) 이미지·표 가로 넘침 결함 발견 → flex `min-width:auto`와 `1fr` 그리드 원인 수정(`minmax(0,1fr)`, 카드 내부 스크롤). 수정 후 문서 폭 386 ≤ 화면 401, 콘솔 오류 0.
- 테스트: `.venv` 134 passed / 1 skipped(torch 필요한 mask 테스트), `.venv-ml` mask 3 passed. `tests/test_repo_hygiene.py` 추가(git 추적 파일에 가중치·키·폰트·원본 데이터 없음).
- `scripts/verify_claude_pack.py`는 현재 작업 트리에서 `no_asset:.pem`, `no_asset:.safetensors` 2건 **failed**: 검사기가 Git 무시 폴더까지 rglob하여 `.venv-ml`의 certifi `cacert.pem`, `models/…/model.safetensors`, `artifacts/adapters/…/adapter_model.safetensors`를 잡음. `git ls-files` 기준 해당 파일 추적 0건 확인. 패키지 검사기는 수정하지 않고 결과(`reports/CLAUDE_PACK_VALIDATION.json`)를 그대로 둠.

### v5 실행 (Fable 결정서 docs/19, 구현 Opus) — 2026-11-14
**S1 계약 개정·지표 분리·CI (완료, 커밋 0a1cd6e)**: docs/19_DECISIONS_V5.md, CLAUDE.md 2개 조항 개정(로컬 GPU 주 실행, vLLM P0, 8B는 추론 전용·유료 승인 시). `evaluation.aggregate()`에 `conditional_on_valid_json`, `strict_and_lenient()` 추가, `reports/eval/metric_contract_v2.md`. `.github/workflows/ci.yml`(ubuntu, 패키지 검사+pytest).

**S2 프롬프트 확정·동결 (완료, 커밋 4a7cec1)**: `configs/frozen_v1.json` — profile standard, manifest 해시, 프롬프트 해시(공개 800bf7c9…, 자체 766c5596…), max_pixels 786,432, max_new_tokens 1,536, greedy, NF4, batch 1.
- 공개 프롬프트 A/B(train 4장, `reports/model/s2_prompt_ab_train.json`): "Markdown 펜스 금지" 문구 추가 시 strict 0/4→0/4, lenient 3/4→2/4 → **v1 유지**.
- **배치 불변성 문제**: batch 8 greedy 출력이 batch 1과 달라짐(train 진단 `diag_m0_prompt_v2_bs8`) → 평가 batch 1 고정.
- **속도 원인 규명**: cProfile 결과 문서당 시간의 대부분이 비전 patch-embedding `torch.conv3d`(bf16) 1회 18.4s. 텍스트 전용 디코드는 32 tok/s, NF4/bf16 동일 5.7 tok/s였던 이유. patch-embed만 fp32로 계산 → 문서당 12–21s(약 21 tok/s, 2.5–3배). 모든 arm 동일 적용·동결 설정에 기록. 학습 경로는 PEFT kbit 준비가 비전을 fp32로 올리므로 래퍼 미적용.

**S3 B0 OCR 기준선 (완료·동결, 커밋 c7f3e96 + 수정 ceb5213)**: Tesseract 4.1.1 Docker(ubuntu:22.04, `--network none`, `docker/ocr/`). 전처리 2종(①회색조·어두운 띠의 어두운 x범위만 반전·2배 확대·임계 165 이진화 ②이진화 없음)을 모두 OCR하고 **정답 없이 문서 내부 산술 일관성**(수량×단가≈금액, 행합≈총액)이 높은 쪽 선택. 헤더 키워드 열 탐지(긴 키워드 우선), 번호·세금 열 무시, 셀 간격 구문화, 텍스트=왼쪽/숫자=오른쪽 정렬, 2줄 목록·티켓 패턴.
- train 조정 이력(필드 정확도 자체/공개): 0.697/0.595 → 반전·확대 0.862/0.712 → 헤더 키워드 수정 0.884/0.820 → 이진화 0.925/0.864 → 변형 선택 **0.963/0.903** (v1.1 동결). 조정은 train만 사용. held-out 레이아웃에서 착안한 키워드("line") 1건은 발견 즉시 제거.
- **dev 결과(세트별, `reports/eval/b0_dev_v12.json`)**: 자체 dev clean(T04) 0.911 (doc exact 0.54, 검수율 0.625), 공개 dev clean 0.967, faded 0.933, **bad_scan 0.562**; 자체 dev stress **blur_jpeg 0.124 / fade_noise 0.217 / skew_lowres 0.180** (doc exact 0, 검수율 1.0).
- **정정**: 이전에 적었던 "E3 리콜 QTY_DIFF 0.75 / UNIT_PRICE_DIFF 0.83 / 검수율 0.625(96건)"은 OCR 캐시 충돌 버그 시점 수치이고 clean+stress를 합산한 값이라 폐기한다(Fable 중간 검토 blocker 4). 이제 E3·헤드라인·bootstrap은 세트별로만 낸다.
- **B0 v1.2 (계약 위반 시정, Fable 중간 검토 blocker 1)**: v1.1 어휘에 held-out 레이아웃 단어가 남아 있었다 — T05 전용 "item code / item description / rate / u/m / items total", 공개 OOD(freelancer) 전용 헤더 "hours / rate / description of work / total". 렌더러를 같은 세션이 작성해 그 지식이 섞였다. train/dev OCR 텍스트로 각 단어의 출처를 확인한 뒤 **train/dev에서 헤더로 관측된 단어만** 남겼다. train 자체 0.963→0.959, 공개 0.903 유지, dev 동일. 이 시정은 S5의 "수정 1건"에 포함하지 않는다.
- 공개: B0의 송장번호 정규식(`INVOICE_NO`)과 USD 탐지는 생성기 형식(모든 split에서 동일)을 train 문서에서 관찰해 쓴 것이다. 현실 문서 일반화 근거가 아니다.

- 버그 수정: stress 이미지가 clean과 같은 파일 stem을 써서 OCR 캐시를 재사용 → 세 변형 점수가 clean과 소수점까지 동일한 이상치로 발견, record_id 기준 이름으로 수정 + 회귀 테스트.

**S4 M1 본학습 (완료)**: `python -m invoiceguard.vlm.train --profile standard --run-id m1_standard_v1` — TRL 0.25.1 `SFTTrainer` 하위 클래스(LeanSFTTrainer) + 검증 collator. 80 optimizer step / 641 micro-step 전부 mask 재검사 통과 / 본 예제 640(≈1.78 epoch, 공개 200·자체 160) / loss 0.364→0.008(평균 0.0487) / 1,308s / peak 6.52GB / 학습 파라미터 1,605,632(언어 q/v LoRA만, vision 0). 어댑터 `artifacts/adapters/m1_standard_v1/adapter_model.safetensors` SHA256 `eb08674120d6489fb9f2ae4cf72038588794e09b3d337a5239d8a6078aff2868`. 기록 `reports/model/train_m1_standard_v1.json`.
- TRL 내장 assistant_only_loss는 Qwen3-VL chat template에 `{% generation %}` 표식이 없어 사용 불가 → 검증 collator 사용(문서화).
- 해결한 장애 2건: ① TRL 기본 compute_loss의 entropy/token-accuracy가 15만 어휘 logits fp32 복사본을 만들어 16GB에서 14.9GB→공유메모리 스필, GPU 유휴(19W)로 21분 정지 → 해당 메트릭만 생략(Trainer 기본 loss) ② `bf16=True` autocast가 비전 Conv3d를 bf16 느린 경로로 보내 micro-step 17s → autocast 끔(0.78s/micro-step, 2-step 시험 `reports/model/train_dryrun_trl_2step_nobf16.json`).
- 재로드 검증: S5 dev 추론(m1_dev_v1)과 final(m1_final_v1)이 디스크에서 base+adapter를 새로 로드해 수행 — 완료.

**Fable 중간 검토 (2026-11-14 03:59, 조건부 NO-GO) 반영**
- blocker 1 B0 held-out 어휘 → v1.2 (위).
- blocker 2 동결 장치 → `invoiceguard.freeze` + `configs/frozen_v1_appendix.json`(B0·평가기·추론 코드 해시, Tesseract 이미지 ID, M1 어댑터 SHA, stress manifest, git 커밋). B0 predict / HF infer / score_run 모두 final 세트는 `--allow-final` + 해시 일치 + clean git tree 아니면 거부(검증: appendix 없을 때 `trade:test` 거부 확인).
- blocker 3 분모 보전 → score_run이 run의 `sets`로 기대 ID를 재구성, 누락=missing 실패, 중복=채점 거부, `denominator_check` 기록. infer는 OOM 외 예외도 문서별 `error`로 기록, 재개 시 attempt_ids 병합. B0 메타에 attempt_ids. `compare_runs`는 두 arm의 ID·세트가 동일하지 않으면 거부.
- blocker 4 E3 정정·세트 분리 (위).
- should-fix: paired bootstrap(`invoiceguard.compare_runs`, base/family 군집) 추가; 조건부 지표를 `conditional_on_json_parse_ok`로 개명(스키마 유효 불요); 검수 API — 동기 추론을 async에서 제거(sync def→스레드풀), 예외 시 케이스가 extracting에 고착되던 문제 해결(BACKEND_ERROR 502), 격리 해제는 백엔드 /health 통과 시에만, dispositions 타입 오류 422. 테스트 12개.
- 공개(should-fix 7): M1 학습은 PEFT kbit 준비로 vision 전체 fp32·autocast 없음, 추론은 vision bf16 + patch-embed만 fp32. M1에 불리한 방향의 불일치이며 별도 train 이미지 sanity 검사는 **not_run**(dev·final 추론이 같은 추론 경로로 정상 동작한 것으로 대신 확인).
- 계획 변경: S5 → blocker 수정 → **S7(HF) → S6(vLLM, 2시간 타임박스)**. final 전 드라이버 변경 금지.

**S5 dev 평가·실패 분석·수정 1건 (완료)** — `reports/eval/dev_summary.md`
- dev(세트별 strict 필드 정확도) B0/M0/M1: 자체 clean 0.911/0.921/0.968, 자체 stress 3종 0.12–0.22 / 0.00–0.17(lenient 0.89–0.91) / 0.93, 공개 clean 0.967/0.000(lenient 0.84)/0.967, faded 0.933/0/1.000, bad_scan 0.562/0/0.705.
- paired: M1−B0 clean 차이 없음(0.0 [−0.06,0.06], +0.058 [−0.02,0.15]), 열화 +0.71~+0.81. M1−M0 전 세트 유의, 상당 부분 형식(M0 펜스·스키마 오류).
- 수정 1건 = train 전용 보강 32건(M1 v2) → **효과 없음**(±0.005, 출력 122/132 동일, 목표 실패 지속). 사전 규칙대로 **M1 v1 유지**. 원인 가설 기록.

**S5 준비 — dev 전용 stress set**: `invoiceguard.vlm.stress` 자체 dev 24장 × 3변형(blur_jpeg / skew_lowres / fade_noise) = 72장, `manifests/stress_v1.jsonl` sha256 677167cf…(2회 생성 동일). final 미포함.

**S6 vLLM (blocked)**: `vllm/vllm-openai:v0.11.2` 컨테이너가 `nvidia-container-cli: requirement error: cuda>=12.9`로 시작 거부. `NVIDIA_DISABLE_REQUIRE=1`로 재시도 시 엔진 초기화에서 `RuntimeError: No CUDA GPUs are available`. CUDA 12.6 빌드인 SGLang 최신 이미지(v0.5.3rc1-cu126, 2025-09-19)는 Qwen3-VL 공개 이전 버전. 해제 조건: 사용자가 NVIDIA 드라이버 ≥ 575로 업데이트하거나 RunPod 승인.

### S7 final (1회, 동결 후) — `reports/eval/final_summary.md`
- 동결: `configs/frozen_v1_appendix.json` (git 622c22c7, 커밋 7c5b7f8) — B0·평가기·추론 코드, M1 어댑터 eb086741…, OCR 이미지, manifest·stress 해시. `freeze verify` → final_ready true 후 B0(`--allow-final`), M0·M1(HF NF4, batch 1, 각 160장, 1,763s / 1,166s) 실행, `score_run --allow-final`, 누락 0.
- 결과(strict 필드 정확도): 자체 test B0 0.210 / M0 0.897 / M1 0.921 (M1−M0 +0.024 [−0.001, 0.050] 비유의, M1−B0 +0.711 [0.67, 0.75]); 공개 IID clean 0.731 / 0 / 0.880 (M1−B0 비유의), IID bad_scan 0.346 / 0 / 0.798; 미학습 템플릿(freelancer) clean 0 / 0 / 0.973. M0 공개 strict JSON 유효 0/120. M1 AMBIGUOUS_QUANTITY 리콜 0/2 (M0 1/2), 오경보 UNIT_PRICE_DIFF FP 15·LINE_ARITHMETIC FP 19.

### S8 서빙·시연·백업·문서
- `serving/hf_server.py` (Transformers+PEFT, 127.0.0.1:8001, 작업자 1 + 대기열 2): 서버 출력 = 오프라인 평가 출력 100%(M0·M1, dev 10장); M1 동시성1 4.0 docs/min p50 16.1s, 동시성2 p50 26.6s, 동시성4 실패 7/10; 3초 타임아웃 요청 → 3.1s 504, 직후 busy=false(실제 생성 중단); 동시 4건 → [200,200,200,429]. 기록: `reports/serving/hf_peft_nf4_local.json`(벤치 스크립트), `hf_cancel_probe.json`·`live_e2e_demo.json`(1회 수동 probe).
- LIVE 종단 시연: 검수 API(LIVE_MODEL) → 단가 변경 문서 추출 15.2s, UNIT_PRICE_DIFF, 정답 행 일치 → 승인 → 스냅샷 export. 이후 두 서버 종료(포트 8000/8001 닫힘 확인).
- 백업: `python -m invoiceguard.backup --dest H:/dev/invoiceguard-po-backup` → 41파일 22MB, 복사본 해시 전부 일치(`reports/backup_inventory.json`). 기본 모델 가중치는 고정 revision에서 재다운로드 가능하여 미복사.
- README를 포트폴리오 첫 화면으로 재작성(원래 패키지 안내는 docs/PACKAGE_README_v4.md). `requirements-ml.lock.txt` 추가.
- Fable 최종 검토(조건부 NO-GO) 반영: README의 과장 표현 정정(B0가 본 레이아웃 clean으로 한정·문서 exact는 B0 우위 명시, lenient 범위, 재현 범위, 미학습 템플릿 표기, 모호수량·오경보, 서빙 한계, UI 미구현), 인계 문서 갱신, 서빙 JSON의 vllm_* 키를 server_*로 개명(값 불변), CLAUDE_PACK_VALIDATION.json을 T00 실행본으로 복원(이후 작업 트리 실행은 Git 제외 자산(.venv-ml/models/artifacts) 때문에 no_asset 2건 실패 — 추적 파일 기준 0건, tests/test_repo_hygiene.py).

### 사용자 결정 (2026-11-14)
- RunPod·드라이버 업데이트를 하지 않기로 결정 → vLLM blocked, 클라우드 not_run을 최종 상태로 유지.

### 대시보드 UI/UX 개편 2차 (사용자 요청: 기본 다크·favicon·화면 구성, 2026-11-14)
- 기본 다크 모드(`theme.js`가 첫 페인트 전 적용, 라이트 선택만 브라우저에 기억), favicon(`dashboard_static/favicon.svg`, `/favicon.ico`도 같은 SVG), 상단 바(경로·새로고침·테마), 아이콘 사이드바·모바일 서랍 메뉴.
- 페이지 10개: 개요(파이프라인 단계·KPI·FINAL 막대·차단 항목) / 진행 단계·게이트 / 공개 데이터 / 자체 Invoice–PO / 분할·manifest / 모델·평가(B0·M0·M1 막대 + 95% CI + lenient 표시, paired 차이 forest plot, M1 학습 loss 곡선·설정) / 서빙(신규: HF+PEFT 벤치·취소·대기열·출력 동일성) / 검수 API(T06 기록·LIVE 시연 단계·엔드포인트) / 테스트 / 클라우드·비용.
- 모든 수치는 `reports/eval`, `reports/serving`, `reports/model`, TASK_BOARD, SESSION_HANDOFF 기록을 그대로 읽어 표시(추정 없음). 이전 화면의 오래된 표기(검수 앱 미구현·모델 결과 미실행·RESULTS_TEMPLATE 기반 상태) 제거. 게이트 상태 `partial:` 정규화.
- 차트 색: 검증된 범주 팔레트 앞 3칸(B0 파랑·M0 주황·M1 청록), 모드별 단계 사용, `validate_palette.js` 다크·라이트 all-pairs 통과(라이트 청록 대비 2.82:1 → 값 라벨·표로 보완).
- 정적 스냅샷(`python -m invoiceguard.dashboard`)도 final 채점 파일의 strict 정확도 표를 보여주도록 수정(파일 없으면 미실행).
- Fable 검토(MUST-FIX 4 · OPTIONAL 8) 반영: 공개 IID 설명 정정("학습과 같은 템플릿" → IID 풀, event_ticket은 학습에 없음 — manifest 확인), 본문 건너뛰기 링크가 라우팅을 바꾸던 문제, vLLM 문구에서 '해제' 제안을 빼고 SESSION_HANDOFF의 사용자 결정 문단(`handoff_decision`)을 함께 표시, 배너 글자색이 상태 클래스와 충돌하던 문제, 동시 4 실패 7건 설명을 "429로 추정·상태 코드 미기록"과 "성공 3건 기준 지표"로 정정, T05 (negative)·T06 (minimal API) 단서 표시, G7 상세 괄호 파싱, 409 라벨 범위, final 없을 때 문구, 비활성 페이지 링크·닫힌 모바일 서랍 키보드 접근, 기록 파일 삭제 중 500 방지.
- 검증: `pytest` 161 passed / 1 skipped (`tests/test_dashboard.py` 다크 기본·favicon·상태 기록·게이트 정규화·사용자 결정 파싱 테스트 추가), 브라우저에서 다크/라이트·데스크톱/모바일·콘솔 오류 0 확인.

### README 재구성·공개 준비 (사용자 요청, 2026-11-14)
- README를 13개 절로 재구성: 한눈에 보기 / 시스템 구성 / 데이터(종류별 표·분할 다이어그램·문서 상세 화면) / 모델과 학습 / 평가 설계 / 결과 / 서빙 / 검수 API(상태 다이어그램) / 관리자 대시보드 / 직무 역량 ↔ 증거 / 비용과 한계 / 재현 / 출처.
- 차트: `python -m invoiceguard.readme_figures` → `docs/images/{final-accuracy,paired-diff,training-loss}-{light,dark}.svg` (reports/eval·reports/model 기록에서 생성, 외부 라이브러리 없음, GitHub 라이트/다크 `<picture>`). 다이어그램: Mermaid 4개(시스템·데이터 분할·평가 절차·검수 API 상태), Mermaid 11에서 렌더 확인.
- 대시보드 화면 캡처 6장(`docs/images/dashboard-*.png`, 로컬 headless Chrome, 기본 다크). 공개 데이터 화면의 문서 이미지는 InvoiceOCR-Synth(CC BY 4.0) — README 출처 절에 표기.
- 공개 전 점검: 전체 git 이력에서 토큰·키·비밀번호 패턴 0건, 사용자 이름이 든 로컬 경로 0건, 1MB 넘는 추적 파일은 manifest 1개. 커밋 작성자 이메일은 공개 시 노출되므로 사용자 확인 대상.
- 검증: `pytest` 164 passed / 1 skipped (`tests/test_readme_figures.py`: 차트 값 = 기록, 커밋된 SVG = 새 생성본, README 로컬 링크 존재).

### 공개 전환 (사용자 요청, 2026-11-14)
- 사용자 선택: 커밋 작성자 이메일을 GitHub noreply로 바꾸고 공개. 로컬에서 25개 커밋의 작성자·커미터 이메일만 재작성(트리 해시 25개 모두 동일, 재작성 전 이력은 로컬 bundle 백업), 이 저장소의 커밋 이메일 설정도 noreply로 변경.
- GitHub는 force push 후에도 예전 커밋을 해시로 보여 주므로, 사용자 승인으로 기존 비공개 저장소를 삭제하고 같은 이름의 공개 저장소를 새로 만들어 재작성된 이력만 push. 예전 CI 실행 기록 6건은 함께 삭제됨.
- 이전 기록에 적힌 커밋 해시는 재작성 전 값 — 대응표 `reports/HISTORY_REWRITE.md`. 동결 파일(`configs/frozen_v1*.json`)은 해시 가드 대상이라 고치지 않음.

### README 영어 기본 + 한국어판 (사용자 요청, 2026-11-14)
- `README.md` = 영어(기본), `README.ko.md` = 한국어, 맨 위에 언어 전환 링크. 표는 짧은 제목·의도한 줄바꿈(`<br>`)·작은 글씨 보조 설명으로 단어가 끊기지 않게 정리(GitHub 렌더러로 미리보기 확인).
- 추가 설명: 평가 세트 구성(자체 test vs 공개 IID/OOD ×3 = 같은 20문서의 품질 3종), Tesseract는 학습 없이 사용, 0.000의 의미(M0 형식 실패 · B0 표 미검출 — 예측 원본으로 확인), M0가 자체 test만 맞추는 이유(공개용 프롬프트에 'without Markdown' 문구 없음; 동결 대상이라 미수정).
- 차트: `readme_figures`가 영어(기본 파일명)·한국어(`-ko-`) × 라이트·다크 = 12개 SVG 생성, 각 SVG는 자체 배경 카드를 가져 GitHub 테마와 OS 설정이 달라도 읽힘.

## 기록 방식
각 단계마다: 시각 / T단계 / 실행 환경 / 실행 명령 / 변경 파일 / 실제 exit code와 결과 / 증거 경로 / 데이터·모델 revision / manifest·adapter hash / 과금 승인 범위·실제 비용 / 미완료·실패·원인 / 다음 행동. 사용자 비밀값은 제외한다. 패키지 검사 결과를 앱이나 모델의 결과로 복사하지 않는다.
