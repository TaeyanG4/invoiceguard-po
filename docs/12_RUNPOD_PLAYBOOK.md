# 12. RunPod 비용·접속·백업 v3

## 1. 가격 판정
2026-11-13 공식 gpu-models 페이지는 4090 $0.34/h, A6000 $0.33/h, A40 $0.35/h를 표시했고, pricing 페이지는 4090 $0.89/h 등 다른 구성을 표시했다. [S02,S03] 이는 콘솔에서 원하는 tier/재고를 그 가격에 잡을 수 있다는 보장이 아니다. 공식 문서도 배포 시 콘솔의 실제 가격을 확인하도록 한다. [S04]

과거 $6.08/18GPU-hour 계산은 특정 단가 가정의 예시일 뿐, 이번 실행의 고정 견적으로 재사용하지 않는다. config의 actual rate는 null이며 사용자 콘솔 견적 입력 전에는 유료 시작 불가다. GPU 수 1, cloud tier, region, hourly quote, 디스크 구분, 시작 잔액, 다른 활성 유료 리소스를 기록한다.

## 2. $10 예산 구조 — 사용자 보고값이며 실시간 잔액 아님
| 용도 | 계획 상한 |
|---|---:|
| GPU 실제 실행 | $7 |
| 보관/체크포인트/종료 여유 | $1 |
| 사용하지 않을 잔액 여유 | $2 |
| 프로젝트 총 지출 목표 상한 | $8 |

견적·실제 잔액이 다르면 사용자 승인 한도를 더 보수적으로 적용한다. 자동충전은 켜지 않는다. 잔액 소진으로 강제종료되기를 기다리지 않는다. 여러 Pod를 동시에 만들지 않는다.

$7 GPU만 나눈 이론값: $0.34/h라면20.59h, $0.69/h라면10.14h, $0.89/h라면7.87h. **학습시간 보장이 아니며** 설치·다운로드·유휴·실패 재시도·추론·백업 시간도 실행시간이다. 48시간 개발과 48시간 GPU 켜두기를 혼동하지 않는다.

## 3. 시작 전 비용 계산
`scripts/budget_plan.py`는 콘솔에서 직접 확인한 요금과 예상 작업시간으로 예산을 계산하는 로컬 도구다. 실제 RunPod 계정/잔액을 읽거나 Pod를 정지시키지는 않는다.

예상 GPU 시간 = 설치/다운로드 + 남은 optimizer step×파일럿 step time + 남은 모든 모델별 이미지수×파일럿 문서시간 + benchmark + backup.
여기에 안전계수1.3과 storage/기타 비용을 반영하여 `이미 쓴 금액 + 남은 예상 비용 <= 승인 상한`인지 확인한다. optimizer step time에 grad accumulation이 포함됐는지 검사한다. eval의 품질3종과 모델2개를 빼먹지 않는다.

콘솔 요금이 $0.89/h일 때 18시간을 돌리면 GPU만 $16.02다. 저가 가정으로 승인한 슬롯을 높은 단가 인스턴스에 그대로 적용하지 않는다. 동급내 가격이 더 싸더라도 throughput·환경 실패 위험을 비교해야 한다.

## 4. 정지 규칙은 실제 리소스 제어
$8 근접 시에는 더 큰 job을 시작하지 않고 체크포인트/로그를 백업한다. Python 프로세스 kill, `torch` exit, 터미널 종료는 Pod 종료가 아니다. RunPod console/API의 **실제 stopped 상태**를 확인해야 GPU 요금이 멈춘다.

Claude Code가 비용 제어를 구현한다면 사용자 승인받은 최대 elapsed time/종료 시점을 사용한 감시와 console 확인을 둔다. 예산 계산 스크립트가 정지까지 보장한다고 표시하지 않는다. 계정 전체 다른 리소스의 비용도 확인한다. unattended overnight 실행은 금지한다.

## 5. 연결/백업 사전 검사
기본 proxy SSH는 SCP/SFTP를 지원하지 않는다고 공식 문서가 설명한다. 본 설계는 **공인IP·노출TCP SSH port를 지원하는 Full SSH**가 필요하다. [S07] 선택 Pod에 이 연결이 있는지 비용 승인 단계에서 확인한다. 공개 모델API 포트를 여는 것은 대체책이 아니다.

콘솔에서 확인한 IP/매핑 SSH port를 사용한다. 아래 값은 사용자가 채우는 자리표시자다.
```bash
ssh -i "$KEY" -p "$SSH_PORT" \
  -N -o ExitOnForwardFailure=yes \
  -L 127.0.0.1:8001:127.0.0.1:8001 root@"$POD_IP"
# 별도 로컬 터미널: 작은 파일 round-trip과 SHA256 일치부터 검사
scp -i "$KEY" -P "$SSH_PORT" probe.txt root@"$POD_IP":/workspace/probe.txt
scp -i "$KEY" -P "$SSH_PORT" root@"$POD_IP":/workspace/probe.txt probe.returned.txt
```
SSH host key를 확인하고 검증을 끄지 않는다. 공유되는 문서에 사설키/API token을 넣지 않는다. SSH 명령/터널은 실제 환경에서 검증 전 not_run이다. 연결 불가 시 승인 범위 안에서 적합한 Pod로 바꾸거나 변경 계획을 요청한다.

## 6. 저장 계층
공식 요금 안내: container disk 실행중 $0.10/GB/월, 중지 후 삭제; volume disk 실행중 $0.10/GB/월·중지중 $0.20/GB/월; network volume 별도 비용. [S04] 선택한 템플릿의 실제 mount를 확인하고 `/workspace`가 보존 volume인지 검사한다. 모든 Pod가 같은 mount라는 가정은 금지한다.

초기 제안은 container20GB + volume60GB이며 데이터/model/cache/adapter 크기를 실측하여 조정한다. 별도 network volume은 P0에서 기본 생성하지 않는다. 디스크를 끝없이 늘리지 않는다. 원본 base weights는 다시 받을 수 있지만 adapter·raw predictions·split manifest·환경기록은 우선 백업한다.

## 7. 종료·복구
각 블록이 끝나면 adapter/config/processor reference/manifest/raw prediction/metric/log를 로컬로 복사하고 SHA256 inventory를 비교한다. backup 1개를 실제 열고 adapter config/평가 JSON이 파싱되는지 검사한다. 가능하면 로컬 또는 재시작된 환경에서 adapter를 실제 로드한 증거도 남긴다. GPU가 없는 환경의 config 파싱은 모델 복원검사와 구분한다.

백업 확인 후 승인된 절차에 따라 Pod stop/terminate, 남아 있는 volume/network volume 점검, billing 상태를 확인한다. terminate 후 pod volume을 복구할 수 있다고 가정하지 않는다. GPU/volume이 남으면 구현 완료 여부와 별개로 운영 종료는 미완료다.
