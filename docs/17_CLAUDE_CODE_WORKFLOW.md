# 17. Claude Code 작업 방식 · v4

## 목적과 적용 범위
2026-11-14에 Claude Code 공식 문서를 확인하여 패키지의 시작·권한·진행 기록을 정리했다. 제품 설계는 v3 기술 감사를 유지한다. 모델/데이터/RunPod 가격의 새 검증을 수행했다는 의미가 아니다.

이 패키지는 루트 `CLAUDE.md`를 프로젝트 지침으로 둔다. 공식 문서에 따르면 Claude Code는 프로젝트 지침을 세션 문맥으로 읽으며, 이는 강제 보안 설정과는 다르다. 설정은 `.claude/settings.json`에 분리한다. [C01, C02]

## 1. 실행 폴더
ZIP을 작업 상위 폴더에 풀면 `invoiceguard-po/`가 생성된다. 그 안의 `CLAUDE.md`와 `.claude/settings.json`을 확인하고 거기서 시작한다.
CLI가 설치되어 있으면 아래 명령으로 실행한다. 설치/인증은 사용자의 로컬 환경에서 수행하며 패키지가 자동 설치하거나 로그인하지 않는다. [C04]
```text
cd invoiceguard-po
claude
```
VS Code 등에서 사용하면 동일한 폴더를 workspace로 연다. 설치 버전별 인터페이스 차이는 공식 문서를 확인한다. OS는 사용자가 확정하지 않았으므로 Windows/WSL/Linux를 먼저 확인한다. 네이티브 Windows에서도 Python 검사 파일을 UTF-8로 읽도록 이 패키지를 정리했다.

## 2. 처음 전달할 내용
[prompts/CLAUDE_START.md](../prompts/CLAUDE_START.md)를 전달한다. 이미 이 파일의 내용과 `CLAUDE.md`가 있으므로 새 초기 지침을 자동 생성해 기존 파일을 대체할 필요가 없다.
읽기 우선순위:
1. `CLAUDE.md`, `README.md`, 이 문서, `reports/SESSION_HANDOFF.md`.
2. `docs/00_PROJECT_BRIEF.md`, `configs/project.yaml`, `docs/08_48H_EXECUTION.md`.
3. `docs/14_FINAL_AUDIT.md`, `docs/15_LABEL_AND_METRIC_CONTRACT.md`, `docs/16_RUNTIME_RELEASE_GATES.md`.
4. 해당 단계에 필요한 01/03/04/05/06/07/09/12/13 문서.

짧은 실행 계획 후 허용된 로컬 구현을 진행한다. 기본 권한 모드는 `default`이며 명령/편집 권한 프롬프트가 나올 수 있다. 이것과 유료 지출의 업무상 승인은 별개다. Plan Mode를 사용자가 선택했다면 읽기·계획 후 구현 가능한 모드로 전환해야 실제 파일을 만들 수 있다. [C02]

## 3. 로컬과 RunPod 역할
| 위치 | 역할 | 하지 않는 일 |
|---|---|---|
| 로컬 개발 PC | Claude Code 세션, 소스/데이터 준비, 평가기, 규칙/API/UI, 백업 | 클라우드 실행을 로컬 mock으로 대체하고 live라고 표시 |
| 승인한 RunPod 1대 | 실제 모델 파일럿, QLoRA, 평가, GPU 추론 측정 | Claude 계정 로그인 복제, 불필요한 agent 설치, 다중 Pod |
| Git 저장소 | 코드·문서·작은 가상 테스트·재현 명령 | API 키, private key, 대용량 원본·가중치·폰트 배포 |

Claude Code 자체 사용 요금과 RunPod GPU/스토리지 요금은 별도다. Claude 요금제·잔액은 확인하지 않았으며, 약 $10은 사용자가 알려준 RunPod 크레딧만 의미한다. 작업 툴의 모델 선택을 프로젝트 추론 모델 Qwen과 혼동하지 않는다.

## 4. 권한과 비밀정보
`.claude/settings.json`에는 default 모드, 일부 비밀 경로의 Read 차단, 주요 원격/게시 명령의 ask만 둔다. 광범위한 allow 목록, 자동 실행 hook, 자동 배포, 권한 우회 모드는 넣지 않는다. 공식 문서의 Read/Bash 패턴과 범위에 따른 설정이다. [C02, C03]

**이 설정은 완전한 비밀정보 샌드박스나 과금 차단기가 아니다.** 기존 사용자/조직/local 설정이 합쳐지며, 명령이 다른 wrapper/Python/API 경로로 실행될 수 있다. Claude Code에서 `/permissions`로 실제 적용 설정을 확인하고 승인할 명령을 검토한다. [C02, C03]

문서의 승인 규칙만으로 강제 지출 상한이 생기지 않는다. 사용자 승인 전에는 RunPod 계정 키를 새로 연결하지 않는다. 필요한 비밀정보는 로컬 안전한 환경변수/secret 파일에 사용자가 설정하며, 키 값 출력·로그·채팅 전달을 요구하지 않는다. 기존 SSH 키가 있으면 그대로 사용하고 새 키를 덮어쓰지 않는다.

## 5. RunPod 승인 경계
[승인 양식](../reports/RUNPOD_APPROVAL.md)의 현재 견적·최대 시간/지출·백업·종료 범위를 먼저 채운다. 콘솔 접근이 없으면 사용자가 비밀값 없는 정보만 확인하도록 안내한다. `approved`는 사용자가 이번 실행을 승인한 후에만 true로 갱신한다.

GPU/지역/단가/스토리지나 지출 한도가 달라지면 승인을 새로 받는다. 재개된 세션이 과거 승인만 보고 새 Pod를 만들지 않는다. Stop/terminate/volume 삭제는 승인 범위에 넣어 구분한다. 백업 전 destructive 정리는 금지한다. 기존에 승인한 시간 제한/종료 절차가 있으면 그 범위에서 수행하고 결과를 검증한다.

로컬에서 계속할 수 있는 작업은 승인 대기 중에도 진행할 수 있다. 다만 GPU 결과가 막혔다면 실제 모델 완료라고 표시하지 않는다.

## 6. 세션을 나누는 방법
T00–T02: 데이터·계약·평가기. T03–T05: 유료 승인·파일럿·학습·dev 개선. T06–T09: 제품 흐름·실측·final·백업과 정리.

각 단계 후 아래 세 파일을 함께 갱신한다.
- `reports/IMPLEMENTATION_STATUS.md`: 실행한 명령·결과·증거.
- `reports/TASK_BOARD.md`: T단계 상태와 다음 통과 조건.
- `reports/SESSION_HANDOFF.md`: 짧은 재개 요약, 활성 리소스와 다음 명령.

새 세션은 [재개 프롬프트](../prompts/CLAUDE_RESUME.md)로 시작한다. 과거 대화 자동 기억에만 의존하지 않고 파일과 실제 결과를 대조한다. Claude Code 공식 문서도 프로젝트 지침과 자동 기억을 구분한다. [C01]

컨텍스트가 부족해지거나 사용자가 종료할 때 활성 과금 리소스부터 확인한다. 확인하지 못했다면 사용자에게 위험을 명시한다. 진행 기록을 작성한다고 Pod가 꺼지지는 않는다.

## 7. 증거와 검사
문서 패키지 검사는 `scripts/verify_pack.py`, `scripts/verify_contracts.py`, `scripts/verify_claude_pack.py`다. 이들은 원본 배포 상태의 문서·계약 검사이며, 향후 앱 테스트를 대신하지 않는다. 구현 이후 null 메타데이터가 실제 값으로 바뀌면 고정된 배포 검사와 제품 검증을 구분하고 테스트 범위도 명확하게 갱신한다.

실제 Python 3.11/torch/CUDA/transformers/peft/trl 조합은 사용자 GPU 환경에서 smoke 테스트 후 lockfile로 기록한다. `requirements-pack.txt`는 jsonschema/PyYAML만 고정한 오프라인 문서 검사 환경이다.

모든 결과는 `not_run`, `blocked`, `failed`, `passed_with_evidence`를 구분한다. 패키지 JSON 검사 성공을 Claude Code CLI 검증, GPU 학습 성공 또는 보안 동작 검증으로 부르지 않는다.

## 공식 참고자료
- C01: https://code.claude.com/docs/en/memory — 루트 프로젝트 지침·기억·세션 문맥.
- C02: https://code.claude.com/docs/en/permissions — default 모드·권한 규칙·실제 적용 확인.
- C03: https://code.claude.com/docs/en/settings — 프로젝트 설정과 local/user/managed 계층.
- C04: https://code.claude.com/docs/en/quickstart — 프로젝트 폴더에서 `claude` 실행.
확인일: 2026-11-14. 이번 작업은 공식 문서 확인과 파일 제작이며, Claude Code CLI를 직접 실행한 검증은 아니다.
