# 11. 확인 출처·설계 결정·한계 v3
확인일 2026-11-13. 요금·문서 지원 조건은 실행 때 재확인한다. 공식 공개 정보와 관측된 모델 성능은 다르다.

| ID | 출처 | 사용 근거 |
|---|---|---|
| S01 | https://huggingface.co/datasets/alamgirqazi/invoice-ocr-synthetic | 공개 데이터 카드/표, 합성·필드·품질/레이아웃·라이선스 표기 |
| S01a | https://huggingface.co/datasets/alamgirqazi/invoice-ocr-synthetic/blob/main/README.md | split 방법/명세의 출처, full download 검증 아님 |
| S02 | https://www.runpod.io/gpu-models | Community 모델별 표시 요금; console 재고와 별개 |
| S03 | https://www.runpod.io/pricing | 다른 tier/구성 가격도 존재함을 확인 |
| S04 | https://docs.runpod.io/pods/pricing | 최신 견적은 console, 저장계층 과금 |
| S05 | https://huggingface.co/Qwen/Qwen3-VL-2B-Instruct | 모델 후보·라이선스·공식 사용 예시 |
| S06 | https://huggingface.co/docs/trl/en/sft_trainer | VLM assistant mask/chat template/version 요건 |
| S07 | https://docs.runpod.io/pods/configuration/use-ssh | Basic SSH와 Full SSH의 파일전송 지원 차이 |

## 결정
D01 영어·합성임을 밝힌 제한된 문서/PO prototype. 실거래 성능을 주장하지 않음.
D02 public canonical / trade raw, 한 base+adapter의 두 고정 태스크. 숫자문자열 착오 제거.
D03 모델 비교 정밀도·manifest 통제. 테스트 사후 선택 금지.
D04 RunPod 한대·console quote·소비$8 목표·백업 후 종료. 사용자 승인 없이는 유료 리소스 생성 금지.
D05 단일사용자 FastAPI/Jinja2/SQLite, 별도GPU inference, vLLM P1.
D06 mask·취소·동시승인은 문서만 믿지 않고 runtime negative test로 검증.

## 이번 감사에서 못한 확인
컨테이너의 외부 DNS 연결 실패로 dataset row API 다운로드를 못했고, 공개 viewer image signed URL도403으로 열리지 않았다. 따라서 실제 full-data parsing, 샘플12장의 이미지-라벨 정합성, GPU 메모리·성능·학습·서빙·SSH 연결은 미검증이다. 사용자 PC와 RunPod 계정에 접속하지 않았다. 정확한 코드/데이터 revision은 아직 null이며 실제 다운로드 후 기록해야 한다.


## v4 작업 도구 전환
Claude Code 공식 문서 확인은 2026-11-14에 별도로 수행했다. [Claude Code 작업 방식](17_CLAUDE_CODE_WORKFLOW.md)의 C01–C04를 참조한다. 위 데이터·GPU·요금 출처를 이번 전환에서 재조회한 것으로 해석하지 않는다.
