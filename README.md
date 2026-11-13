# InvoiceGuard-PO
## Claude Code 시작 패키지 · v4.0

영어 인보이스의 품번·수량·단가를 실제 VLM으로 추출하고, 독립 발주서와 대조해 사람이 검수·승인한 결과만 내보내는 2일 MVP입니다.

**현재 제공물은 기획·설계·스키마·가상 예제·오프라인 검사 도구입니다.** 제품 코드, 학습 모델, 실제 데이터 전체 다운로드, GPU 실측 결과는 아직 없습니다.

## 시작 방법
1. ZIP을 작업할 **상위 폴더**에 압축 해제합니다. ZIP 안에 이미 `invoiceguard-po/`가 있으므로 같은 이름으로 폴더를 한 번 더 만들 필요가 없습니다.
2. `CLAUDE.md`와 `.claude/settings.json`이 보이는 `invoiceguard-po` 폴더를 Claude Code의 작업 폴더로 엽니다.
3. CLI를 이미 설치했다면 그 폴더의 터미널에서 `claude`를 실행하고, [시작 프롬프트](prompts/CLAUDE_START.md)를 그대로 전달합니다.
4. 기존 프로젝트가 있으면 새 빈 폴더에서 먼저 비교합니다. 덮어쓰지 않습니다. 새 GitHub 저장소 생성·원격 연결·push는 시작에 필수적이지 않습니다.

```text
<작업 상위 폴더>/
└── invoiceguard-po/       ← 여기에서 Claude Code 시작
    ├── CLAUDE.md
    ├── README.md
    ├── .claude/settings.json
    ├── prompts/CLAUDE_START.md
    ├── docs/
    └── reports/
```

## 그대로 유지한 조건
영어 단일 언어 / 공개 합성 InvoiceOCR-Synth + 자체 합성 Invoice–PO / Qwen3-VL-2B 후보 / 2일 MVP / RTX 4070 Ti SUPER 16GB / 모델 작업은 RunPod 우선.
RunPod 약 $10은 사용자 제공 정보이며 계정 잔액을 확인하지 않았습니다. GPU $7 + 스토리지·정리 $1, 여유 $2가 계획입니다. 실제 견적과 시간·지출 상한을 승인받기 전 유료 리소스를 만들지 않습니다. Claude Code 사용 요금은 이 RunPod 잔액과 별개이며 이 패키지에서 조회·추정하지 않습니다.

## 무엇이 바뀌었나
v4는 **작업 도구를 Claude Code로 전환한 배포 버전**입니다. v3의 데이터·평가·학습·예산·안전 계약은 유지합니다.
- 루트 [CLAUDE.md](CLAUDE.md): 시작 시 읽을 프로젝트 지침.
- [.claude/settings.json](.claude/settings.json): 기본 권한 확인, 일부 민감 파일 읽기 제한, 원격 명령 확인. 전체 결제 차단이나 강제 예산 집행 장치는 아닙니다.
- [Claude Code 작업 방식](docs/17_CLAUDE_CODE_WORKFLOW.md): 로컬 개발→RunPod→재개→종료.
- [세션 인계](reports/SESSION_HANDOFF.md)와 [작업표](reports/TASK_BOARD.md): 세션이 바뀌어도 진행 상황을 파일로 복원.
- [전환 기록](docs/18_PACKAGE_MIGRATION.md): 변경 범위와 검증 한계.

## 시작·재개 프롬프트
| 상황 | 전달할 파일 |
|---|---|
| 처음 시작 | [CLAUDE_START.md](prompts/CLAUDE_START.md) |
| 새 세션에서 이어가기 | [CLAUDE_RESUME.md](prompts/CLAUDE_RESUME.md) |
| RunPod 실행 전 승인 정보 정리 | [CLAUDE_RUNPOD_APPROVAL_CHECK.md](prompts/CLAUDE_RUNPOD_APPROVAL_CHECK.md) |
| 데이터·학습 게이트 이후 모델·릴리스 | [CLAUDE_MODEL_AND_RELEASE.md](prompts/CLAUDE_MODEL_AND_RELEASE.md) |

## 설계 문서 안내
| 목적 | 문서 |
|---|---|
| 목표·범위 | [00 기획](docs/00_PROJECT_BRIEF.md), [02 요구사항](docs/02_PRD.md) |
| 데이터·평가 | [01 데이터](docs/01_DATA_PLAN.md), [04 계약](docs/04_DATA_CONTRACTS.md), [06 평가](docs/06_EVALUATION.md), [15 라벨·지표](docs/15_LABEL_AND_METRIC_CONTRACT.md) |
| 구현 | [03 아키텍처](docs/03_ARCHITECTURE.md), [05 모델](docs/05_MODEL_PLAN.md), [07 API·UI](docs/07_API_UI.md) |
| 실행·운영 | [08 작업 순서](docs/08_48H_EXECUTION.md), [12 RunPod](docs/12_RUNPOD_PLAYBOOK.md), [16 런타임 게이트](docs/16_RUNTIME_RELEASE_GATES.md) |
| 품질·시연 | [09 테스트](docs/09_TEST_ACCEPTANCE.md), [10 시연](docs/10_DEMO_PORTFOLIO.md), [13 데이터 게이트](docs/13_DATASET_GATES.md) |
| 근거·검토 | [11 출처](docs/11_SOURCES_ADR.md), [14 기존 기술 감사](docs/14_FINAL_AUDIT.md) |

## 문서 패키지 검사
Python 3.11을 권장합니다. 아래 의존성은 **패키지 검사 전용**이며 GPU 학습 환경의 lockfile이 아닙니다.
```bash
python -m pip install -r requirements-pack.txt
python scripts/verify_checksums.py
python scripts/verify_pack.py
python scripts/verify_contracts.py
python scripts/verify_claude_pack.py
```
Windows에서 `python` 대신 `py -3.11` 또는 해당 가상환경의 Python을 사용할 수 있습니다. OS를 임의 변경하거나 전역 환경을 덮어쓰지 마세요.
`verify_checksums.py`는 받은 파일 그대로인지 확인하므로 **다른 검사나 구현으로 파일을 수정하기 전에** 실행하세요. 변경 후 해시가 달라지는 것은 정상입니다.

[패키지 검사 요약](reports/CLAUDE_MIGRATION_SUMMARY.json)은 문서/설정/예제 검사의 결과입니다. 실제 Claude Code CLI, RunPod, 모델학습, 제품 API를 실행한 증거가 아닙니다.

## 주의
API 키·개인 SSH 키는 채팅과 Git에 넣지 않습니다. Claude Code 로그인은 로컬에 두고, RunPod는 승인된 모델 작업에만 사용합니다. 모델 출력과 원문을 실제 고객 데이터처럼 포장하지 않습니다.
공식 Claude Code 사용법은 [워크플로 문서의 출처](docs/17_CLAUDE_CODE_WORKFLOW.md#공식-참고자료)를 참고합니다. 프로그램을 설치하는 스크립트, 자동 실행 hook, 광범위한 명령 허용 목록은 포함하지 않았습니다.
