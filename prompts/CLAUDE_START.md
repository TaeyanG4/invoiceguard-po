현재 폴더의 InvoiceGuard-PO를 구현해줘. 먼저 CLAUDE.md, README.md, docs/17_CLAUDE_CODE_WORKFLOW.md와 reports/SESSION_HANDOFF.md를 읽고, docs/08_48H_EXECUTION.md의 T00부터 진행해줘.

목표는 영어 인보이스 이미지에서 품번·수량·단가를 실제 VLM으로 추출하고, 독립 발주서와 비교해 사람이 수정·승인한 버전만 내보내는 2일 MVP야. 일반 챗봇이나 자동 통관 서비스로 범위를 넓히지 마.

내 PC는 RTX 4070 Ti SUPER 16GB이고 RunPod 잔액은 약 $10이야. 모델 추론·QLoRA·GPU 측정은 가급적 RunPod에서, 데이터 준비·평가기·API/UI 개발은 로컬에서 진행해줘. 현재 OS와 Python/개발환경은 직접 확인하고 기존 코드나 설정이 있으면 보존해줘.

기술 계약은 docs/14_FINAL_AUDIT.md, docs/15_LABEL_AND_METRIC_CONTRACT.md, docs/16_RUNTIME_RELEASE_GATES.md와 configs/project.yaml을 기준으로 해줘. 공개 데이터는 영어 합성 자료이고 SKU 정답이 없어. PUBLIC_CANONICAL과 자체 인보이스용 TRADE_RAW를 구분하고, 발주서나 정답을 추출 모델에 넣지 마. 학습 전후는 같은 데이터·정밀도·프롬프트·전처리로 비교해줘.

우선 간단한 실행 계획을 제시한 뒤, 현재 환경에서 가능한 로컬 파일 작성·검사·구현을 진행해줘. 별도 결제나 기존 작업 덮어쓰기가 없는 단계마다 재승인을 반복해서 묻지 말고, 필요한 도구 권한 요청에는 따르도록 해줘. UI부터 만들지 말고 문서 검사→데이터·정답 확인→분할·평가기·규칙 테스트를 먼저 해줘.

RunPod 유료 Pod·스토리지 생성/재시작 전에는 실제 콘솔 가격, GPU 한 대, 저장공간, 최대 비용·시간, 백업과 종료 절차를 보여주고 내 승인을 받아줘. GPU $7 + 기타 $1 이내를 계획으로 삼고 $2를 남겨줘. RunPod 잔액이나 접근 권한을 이미 확인했다고 가정하지 마. 키·비밀번호·SSH 개인키는 채팅에 요구하거나 출력하지 마. Claude Code 로그인은 로컬에 두고 원격에는 승인된 모델 작업만 실행해줘.

미실행 작업은 not_run/blocked로 기록하고, 가상 예제나 mock을 실제 학습·API 결과로 표시하지 마. 각 단계 후 reports/IMPLEMENTATION_STATUS.md, reports/TASK_BOARD.md, reports/SESSION_HANDOFF.md에 실제 명령·결과·증거·비용·다음 작업을 갱신해줘. 유료 승인이나 사용자 입력이 필요한 부분만 중단하고, 독립적으로 가능한 로컬 작업은 계속해줘.
