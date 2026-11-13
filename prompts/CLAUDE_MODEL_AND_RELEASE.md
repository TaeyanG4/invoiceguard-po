데이터 계약과 RunPod 승인이 실제로 통과한 범위에서 모델·릴리스를 진행해줘.
먼저 CLAUDE.md, docs/05_MODEL_PLAN.md, docs/06_EVALUATION.md, docs/15_LABEL_AND_METRIC_CONTRACT.md, docs/16_RUNTIME_RELEASE_GATES.md, reports/RUNPOD_APPROVAL.md를 확인해줘.

실제 image-expanded assistant loss mask, 의도한 LoRA 모듈, gradient와 파라미터 업데이트, 저장·재로드를 10스텝 검사에서 확인해줘. 검사 후 base·seed·optimizer를 초기화해 본학습을 시작해줘.
PUBLIC_CANONICAL과 TRADE_RAW의 입력·출력·지표를 분리하고, training-only 파일럿 뒤 standard/mini와 manifest를 평가 전에 고정해줘. M0/M1은 같은 NF4 정밀도·프롬프트·전처리·최종 분할에서 둘 다 측정해줘.
dev의 실제 실패 최대 10건을 분석하고 개선 한 가지의 효과와 회귀를 남겨줘. final은 개선에 쓰지 마. 실패가 적으면 실제 개수를 적어줘.
실제 GPU API, timeout 취소/격리, 늦은 응답 CAS, 버전별 사람 승인·내보내기를 검증해줘. live/fixture/replay와 측정하지 못한 항목을 명확히 나눠줘.
완료 전에 결과·어댑터를 로컬로 백업하고 해시/복원을 확인해줘. 승인된 종료 절차만 실행하고 Pod·남은 볼륨 과금 상태를 실제로 확인해줘. 확인 불가능하면 비용 위험을 즉시 알려줘.
세션 인계·작업표·구현 상태에 증거와 비용을 갱신해줘.
