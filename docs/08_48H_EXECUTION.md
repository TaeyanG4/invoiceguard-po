# 08. 2일 실행 순서와 중단 게이트 v3

개발 시간 배분을 위한 계획이다. 자동 실행 완료 약속이나 GPU 소요시간 보장이 아니다. 스스로 실행하지 않은 명령/테스트는 not_run으로 기록한다.

## Day 1: 돈을 쓰기 전에 검증 → 실제 학습
| 순서 | 실행 장소 | 작업 | 다음 단계 통과 조건 |
|---|---|---|---|
| T00 | 로컬 | v3 문서·설정·schema 확인, 환경 계획 | 문서 계약 검사 통과 |
| T01 | 로컬 | 공개 source/revision/download/프로필, 12개 clean 이미지·renderer 확인 | 영어/라벨 가시성/분할 가능 여부 확인 |
| T02 | 로컬 | content group split, 자체 인보이스 renderer, evaluator·규칙 fixture | 누수 없음, raw/canonical 구분, 생성값/이미지 대응 |
| T03 | RunPod 승인 후 | quote 입력, fullSSH·백업시험, 모델8장·10-step smoke | mask/gradient/VRAM·시간·복원·예산 예상 통과 |
| T04 | RunPod | standard/mini 사전 동결, M0 dev → base 재초기화 → M1 | 실제 baseline, adapter/log, 재로드 dev |

로컬 준비 동안 GPU는 켜두지 않는다. 데이터가 막히면 source 자체를 임의 변경하지 말고 blocked를 기록한다. 자체 합성 수직 기능은 별도로 계속 구현할 수 있으나 공개 데이터 검증을 완료했다고 쓰지 않는다.

## Day 2: 실패 개선 → 실제 시연 → 최종 검증
| 순서 | 작업 | 통과 조건 |
|---|---|---|
| T05 | dev 실제 실패 최대10건 분석, 개선1개 | 수정 영향/회귀 결과; 프롬프트 수정 시 양 모델 재비교 |
| T06 | 한 화면 API/UI, 수정·차이 확인·승인·export | CPU 기능/버전경쟁/보안 테스트 |
| T07 | RunPod live 연결·서빙 측정 | request ID/adapter/실측 지연/실패/비용 증거 |
| T08 | frozen final을 M0와 M1 모두 평가 | E1 IID/OOD 3품질, E2/E3 동일 manifest와 분모 |
| T09 | 결과·adapter 백업, 해시 및 로컬 복원, 리소스 정리 | 실제 백업 확인, GPU+volume 과금 상태 확인 |

## 비용이 부족하면
우선순위는 데이터/평가기 → 실제 baseline → 학습 → 동일 조건 비교 → 최소 검수·승인 → 실제 API 측정이다. 디자인·vLLM·새 모델·세 번째 학습·다중 PDF는 후순위다. 어느 하나를 하지 못했으면 직무대응 전체완료가 아니라 일부완료로 표시한다. 비용 절약을 위해 비교 대상 하나의 final만 실행하거나 좋게 나온 사례만 표에 넣지 않는다.

## final 명령의 필수 모양
아래는 Claude Code가 구현할 목표 인터페이스이며 아직 앱 명령이 아니다.
```bash
for model in base adapter; do
  for split in public_iid_final public_ood_final trade_final; do
    uv run python -m invoiceguard.evaluate \
      --model "$model" --split "$split" --frozen
  done
done
```
원본 응답을 먼저 저장한 뒤 채점한다. 중단된 실행은 완료된 IDs/실패 IDs/미시도 IDs를 나누며, 재개하더라도 같은 설정/manifest를 유지한다.

## 실제 준비된 도구 vs 목표 앱
준비됨: `scripts/verify_pack.py`, `scripts/verify_contracts.py`, `scripts/budget_plan.py`는 문서/계약/계산 도구이다.
미구현: `invoiceguard.*`, UI, 모델학습 및 실측 API. 문서에서 코드로 자동 전환돼 있다고 가정하지 않는다.


## Claude Code v4 실행·인계
현재 배포의 루트 지침은 `CLAUDE.md`다. T00에서는 `scripts/verify_claude_pack.py`도 실행한다. 각 단계 후 `reports/TASK_BOARD.md`, `reports/IMPLEMENTATION_STATUS.md`, `reports/SESSION_HANDOFF.md`를 함께 갱신한다. 로컬 검사 단계에는 GPU를 생성하지 않는다. 유료 단계는 `reports/RUNPOD_APPROVAL.md`의 이번 실행 승인이 필요하다.
