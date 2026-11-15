`99f1282` 기준으로 확인했습니다. **핵심 성능·서빙·청구 수치는 대체로 근거와 맞지만, seed 차이 수치 한 곳과 재현 절의 연결 오류는 수정이 필요합니다.** 아래 제안은 모두 문서 수정이며 비용은 $0입니다.

1. **오류 — A1 세 번째 seed의 차이 수치**
   
   위치: [README.md:604](../../README.md#L604), [README.ko.md:602](../../README.ko.md#L602).
   
   M0 대비 마지막 값 `+0.050`은 원보고서의 **0.0546**과 다릅니다. 근거: [비교 JSON:13](../../reports/eval/compare_cord_dev_m1cordqkvo_s20261115_nf4__vs__cord_dev_m0_nf4.json#L13).
   
   **교체:** “M0 대비는 세 seed 모두 유의합니다(+0.070 · +0.064 · **+0.055**).” 약 5분.

2. **오류 — 생성하는 예측과 replay·벤치가 읽는 이름 불일치**
   
   위치: [README.md:1018](../../README.md#L1018), [README.ko.md:1016](../../README.ko.md#L1016).
   
   4단계는 `m1_dev`를 만들지만 6단계 replay와 자체 문서 벤치는 `m1_dev_v1`을 읽습니다. 기존 로컬 산출물이 없는 환경에서는 연결되지 않습니다. 근거: [extractors.py:54](../../src/invoiceguard/app/extractors.py#L54), [vllm_bench.py:164](../../src/invoiceguard/serving/vllm_bench.py#L164).
   
   **수정:** 4단계 추론·채점·비교의 run 이름을 모두 `m1_dev_v1`로 통일. 약 5분.

3. **오류 — 서빙 명령을 순서대로 실행할 수 없음**
   
   위치: [README.md:1030](../../README.md#L1030), [README.ko.md:1028](../../README.ko.md#L1028).
   
   첫 서버 명령은 종료될 때까지 터미널을 점유합니다. 벤치 스크립트도 서버를 자체 기동·종료하므로 수동 서버와 함께 실행하면 충돌하고, 벤치 종료 후에는 LIVE API의 추론 서버가 없습니다. LIVE와 replay도 기본 포트가 같습니다. 근거: [run_multi_lora_bench.sh:11](../../scripts/serving/run_multi_lora_bench.sh#L11), [동일 파일:23](../../scripts/serving/run_multi_lora_bench.sh#L23), [server.py:39](../../src/invoiceguard/app/server.py#L39).
   
   **추가 문장:** “아래는 선택 실행 경로입니다. 벤치 스크립트는 수동 서버 없이 실행합니다. LIVE 체험은 별도 터미널에 HF 서버를 유지하고 API를 실행하며, replay는 LIVE 대신 선택합니다. 두 어댑터 서빙에는 8단계의 CORD 어댑터·dev 예측이 먼저 필요합니다.” 약 15분.

4. **오류 — CORD 최초 실행 기록을 현재 재현 절차로 제시**
   
   위치: [README.md:1049](../../README.md#L1049), [README.ko.md:1047](../../README.ko.md#L1047).
   
   현재 checkout에는 동결 파일과 test 보고서가 있어 `freeze_cord.py`와 test 재실행이 의도적으로 거부됩니다. 또한 앞의 스크립트는 뒤에서 요구하는 `cord_dev_m0_nf4`를 생성하지 않습니다. 근거: [freeze_cord.py:31](../../scripts/realdocs/freeze_cord.py#L31), [cord_guard.py:89](../../src/invoiceguard/cord_guard.py#L89), [run_cord_local.sh:14](../../scripts/realdocs/run_cord_local.sh#L14).
   
   **교체:** “동결·test 명령은 최초 실행 당시 기록입니다. 현재 checkout에서는 재실행을 거부합니다. dev 재현에는 M0 baseline 생성도 포함해야 합니다. 기존 test 원예측을 복원한 경우에만 저장된 보고서와 동일한 재채점을 검증할 수 있습니다.” dev 절에 M0 명령도 추가. 약 15–20분.

5. **오래됨 — ‘남은 방법은 사람 라벨 추가’라는 결론**
   
   위치: [README.md:591](../../README.md#L591), [README.ko.md:589](../../README.ko.md#L589).
   
   바로 뒤의 q·k·v·o 실험은 같은 데이터로 단가를 회복했습니다. 따라서 사람 라벨 추가만 남았다는 결론은 후속 결과와 맞지 않습니다. 근거: [docs/20:93](../../docs/20_DECISIONS_V6.md#L93), [동일 문서:119](../../docs/20_DECISIONS_V6.md#L119).
   
   **교체:** “학습 가중과 프롬프트 변경은 실패했습니다. 이후 q·k·v·o 변형은 추가 라벨 없이 dev 단가를 회복했으며, test에서는 확인하지 않았습니다.” 약 5분.

6. **오래됨 — 한글 오독을 기본 모델의 한계로 단정**
   
   위치: [README.md:635](../../README.md#L635), [README.ko.md:633](../../README.ko.md#L633).
   
   뒤의 실험에서는 같은 모델의 해상도만 바꿔 품명이 크게 개선됩니다. 기존 문장은 현재 결과를 충분히 반영하지 못합니다. 근거: [t07_stress.md:36](../../reports/eval/t07_stress.md#L36).
   
   **교체:** “동결 해상도에서는 세 arm 모두 한글 오독을 보였습니다. 후속 실험에서 입력 축소가 이 T07 조건의 주요 원인 중 하나임을 확인했습니다.” 요약의 ‘해상도가 원인’도 같은 범위로 한정하면 정확합니다. 약 5–10분.

7. **보완 — ‘숫자 필드는 모두 1.000’의 범위**
   
   위치: [README.md:649](../../README.md#L649), [README.ko.md:647](../../README.ko.md#L647).
   
   표 각주는 품번·단가·행 금액·합계로 한정하므로 표 자체는 맞습니다. 다만 앞 문단에서는 수량도 숫자 필드에 포함하며, 고해상도 수량은 **0.9915**입니다. 근거: [t07_stress.json:188](../../reports/eval/t07_stress.json#L188).
   
   **교체:** “품번·단가·행 금액·합계는 모두 1.000이 됐고, 수량은 0.992였습니다.” 약 5분.

8. **보완 — 해상도 일반화 결과의 세트 명칭·판정**
   
   위치: [README.md:651](../../README.md#L651), [README.ko.md:649](../../README.ko.md#L649).
   
   CORD까지 “영어 dev 세트”로 묶지만 CORD는 인도네시아 혼합언어 영수증입니다. 또한 원보고서의 판정은 개선 실패뿐 아니라 **안전성도 입증하지 못함**입니다. 근거: [README.md:339](../../README.md#L339), [resolution_dev.md:17](../../reports/eval/resolution_dev.md#L17).
   
   **교체:** “기존 자체 인보이스·CORD dev에서는 개선과 사전 정의한 안전성을 입증하지 못했습니다. 해상도 상향의 효과는 이번 T07 조건에서 확인됐습니다.” 1장 결론의 같은 표현도 맞추면 됩니다. 약 5분.

9. **보완 — 펜스 제거가 제외된 ‘동결 계약’의 범위**
   
   위치: [README.md:785](../../README.md#L785), [README.ko.md:783](../../README.ko.md#L783).
   
   합성 FINAL에는 맞지만 CORD의 동결 평가에는 펜스 제거가 포함됩니다. 근거: [README.md:528](../../README.md#L528).
   
   **교체:** “합성 FINAL의 strict 계약에는 펜스 제거를 포함하지 않습니다. CORD는 수정 1에 따라 펜스를 제거한 필드 점수와 원본 JSON 형식 지표를 분리합니다.” 약 5분.

10. **보완 — ‘검수 대상 비율’과 사람 승인 대상의 혼동**
    
    위치: [README.md:519](../../README.md#L519), [README.ko.md:517](../../README.ko.md#L517).
    
    0.675는 `needs_review` 상태 비율입니다. 실제 제품에서는 경고 없는 문서도 승인해야 내보낼 수 있으므로 “share sent to review”는 다르게 읽힐 수 있습니다. 근거: [evaluation.py:261](../../src/invoiceguard/evaluation.py#L261), [api.py:478](../../src/invoiceguard/app/api.py#L478).
    
    **교체:** “대사 결과 `needs_review` 비율 — 내보내기 전 사람 승인은 모든 문서에 필요.” 약 5분.

11. **보완 — 서빙 표의 공통 측정 조건이 낡음**
    
    위치: [README.md:662](../../README.md#L662), [README.ko.md:660](../../README.ko.md#L660).
    
    표 머리의 “자체 dev 10장, warmup 3”은 뒤의 전체 dev 24·100장 측정에 적용되지 않습니다. 전체 dev 벤치는 warmup 2입니다. 근거: [run_multi_lora_bench.sh:17](../../scripts/serving/run_multi_lora_bench.sh#L17).
    
    **교체:** “측정 항목 — 문서 수·warmup·동시성은 측정별로 다름.” 기존 조건은 최초 측정 행으로 이동. 약 5분.

12. **보완 — 모델 환경 설치 선행 단계 누락**
    
    위치: [README.md:1001](../../README.md#L1001), [README.ko.md:999](../../README.ko.md#L999).
    
    `.venv-ml` 생성·의존성 설치·프로젝트 설치 없이 바로 해당 Python을 실행합니다. lockfile은 버전 목록이며 프로젝트 설치를 대신하지 않습니다. 근거: [requirements-ml.lock.txt:1](../../requirements-ml.lock.txt#L1), [pyproject.toml:27](../../pyproject.toml#L27).
    
    **추가 문장:** “먼저 Python 3.11로 `.venv-ml`을 만들고, CUDA 12.6용 PyTorch와 lockfile 의존성, 이 프로젝트를 설치합니다.” 이어 실제 설치 명령을 제시하면 됩니다. 약 10분.

한영 README의 **핵심 수치 차이나 주요 내용 누락은 발견하지 못했습니다.** 위 문제들은 대부분 양쪽에 공통입니다. 영어의 `3+ fields`([603줄](../../README.md#L603))는 한국어 “3칸”에 맞춰 `at least three fewer correct field values`로 쓰면 필드 종류 수라는 오해를 줄일 수 있습니다.

로컬 링크 대상 140개와 내부 앵커에서는 깨진 연결을 찾지 못했습니다. 외부 URL의 접속 상태는 검증하지 않았습니다. 검수 화면의 구현·검증 설명에서도 추가 오류를 찾지 못했습니다. 채용 독자에게 필요한 순서 보완은 **재현 절의 선행 조건과 실행 경로 구분**이 우선입니다.

파일 수정, 테스트·모델·서버 실행은 하지 않았습니다.