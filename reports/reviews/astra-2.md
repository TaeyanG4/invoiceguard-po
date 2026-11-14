**88/100점입니다. 서류 통과 후 면접에서 검증할 가치가 충분합니다.** 학습·서빙·수치 평가의 필수 역량은 확인됐습니다. 남은 약점은 CORD 실행 통제, 단가·모호수량 오류, 일부 README 표현입니다.

파일과 Git 이력을 읽기 전용으로 검토했습니다. 테스트·모델은 실행하지 않았으며, 지정하신 자원상 불가능한 작업은 감점과 제안에서 제외했습니다.

**1. 가중 평가**

점수는 각 가중치 안에서 획득한 점수입니다.

| 공고 항목 | 가중치 | 점수 | 확인 근거·평가 |
|---|---:|---:|---|
| LoRA/SFT·Transformers/PEFT/TRL | 20 | 19 | 실제 학습 경로, completion 마스크 검증, 저장·재로드 확인. [train.py](../../src/invoiceguard/vlm/train.py#L38), [smoke 기록](../../reports/model/local_smoke_train.json#L120) |
| 품목·수량·단가·품번 추출·문서 AI | 20 | 16 | 필드별 평가와 CORD 효과 확인. 단가·모호수량은 약점. [FINAL](../../reports/eval/final_summary.md#L30), [CORD](../../reports/eval/cord_test_m1cord_nf4.json#L52) |
| 서빙 프레임워크·양자화·배치 실측 | 20 | 18 | vLLM 정확도 회복·FP8 실측 인정. 지속 부하와 동시성별 품질 검증은 부족. [L40S 결과](../../reports/runpod2/vllm_run2_m1merged_bf16.json#L455), [벤치 코드](../../src/invoiceguard/serving/vllm_bench.py#L114) |
| 자동 채점·회귀·평가 무결성 | 20 | 17 | 실패 분모 유지·paired CI·회귀 테스트는 강함. CORD 동결 강제에 허점. [평가기](../../src/invoiceguard/evaluation.py#L44), [CORD 가드](../../src/invoiceguard/vlm/infer.py#L79) |
| 실패 분석·프롬프트·후처리·데이터 개선 | 10 | 9 | 정밀도 원인 분리와 해결이 특히 좋음. 실패한 데이터 보강도 보존. [정밀도 실험](../../reports/quant/precision_dev20.md#L1), [dev 분석](../../reports/eval/dev_summary.md#L42) |
| Linux/SSH·GPU 운영·비용 관리 | 5 | 5 | 실제 Pod 학습·서빙, 터널, 백업·복원·종료 기록. [RunPod 기록](../../reports/runpod/RUNPOD_RUN.md#L31) |
| 무역 문서 업무·서비스 연계 | 5 | 4 | 독립 PO 대사, 버전 충돌 방지, 승인 스냅샷 export 구현. 행 추가·삭제 검수는 빠짐. [API](../../src/invoiceguard/app/api.py#L301) |
| **합계** | **100** | **88** | |

**2. 치명적 공백**

**필수 요건 부재로 즉시 탈락시킬 공백은 없습니다.** 특히 vLLM 배포·측정과 정밀도 문제 해결은 공고와 직접 연결됩니다.

다만 실무 정확도는 아직 개선 대상입니다. 합성 test 단가 정확도는 **0.824**, 모호수량 탐지는 **0/2**입니다. CORD에서도 단가는 **0.821→0.716**으로 하락했습니다. 전체 정확도 상승을 품목 필드 전반의 개선으로 해석하면 안 됩니다. 이 한계는 이미 공개돼 있습니다. [필드별 결과](../../README.md#L422), [CORD 해석](../../README.md#L535)

또한 사람 검수가 안전장치인데, 현재 API는 기존 행의 값만 수정합니다. **누락행 추가·허위행 삭제가 불가능한 점**은 제품 흐름의 실제 공백입니다. [api.py](../../src/invoiceguard/app/api.py#L314)

**3. CORD 사전 등록 무결성**

- **시점은 대체로 인정합니다.** 기준과 수정1은 `6823ad0` 커밋인 **11월 14일 22:43**에 존재하며, 학습 시작 **23:18:55**보다 빠릅니다. 문서의 시각 표기는 이후 정정됐지만 기준 내용은 먼저 존재했습니다. 수정1은 dev 18건을 관찰한 뒤 변경했으므로, 정확한 표현은 **“dev 관찰 후, 학습·test 전 고정”**입니다. [결정문](../../docs/20_DECISIONS_V6.md#L57), [학습 시각](../../handoff.md#L38)
- **판정 수치는 유효합니다.** strict 차이 **+0.0652 [0.0272, 0.1073]**, 형식 무시 **+0.0548 [0.0193, 0.0953]**로 정한 기준을 충족합니다. [비교 결과](../../reports/eval/compare_cord_test_m1cord_nf4__vs__cord_test_m0_nf4.json#L9)
- **test 1회 강제는 불완전합니다.** 완료된 test 실행 ID를 `cord:dev`에 재사용하면 fingerprint 검사를 통과하고 metadata의 세트가 덮입니다. 이후 새 test 실행이 허용될 수 있습니다. 평가기 해시도 동결 파일에 기록만 하고 검사하지 않습니다. **실제 악용·재실행 증거와는 별개인 구현 결함**입니다. [실행 가드](../../src/invoiceguard/vlm/infer.py#L93), [덮어쓰기](../../src/invoiceguard/vlm/infer.py#L203), [채점 경로](../../src/invoiceguard/cord_eval.py#L179)
- **중복 처리는 합리적입니다.** held-out과 동일 gold인 train 40건을 제외하고, 동일 gold를 CI 재표집 단위로 묶었습니다. 미중복 85건에서도 효과가 유지됩니다. 다만 완전 동일 정답 검사이며 부분·유사 중복까지 보장하지는 않습니다. [제외 로직](../../src/invoiceguard/cord.py#L123), [클러스터링](../../src/invoiceguard/cord_eval.py#L194)
- **실제 비교 조건은 일치합니다.** 6개 dev/test 결과의 GPU·NF4·모델 revision·프롬프트·전처리·생성 설정이 같습니다. GPU 일치는 코드상 강제 사항은 아닙니다. [대표 fingerprint/env](../../reports/eval/cord_test_m1cord_nf4.json#L4)

**4. README의 과장·불일치**

| 인용 | 반박·필요한 한정 |
|---|---|
| “With matching precision the three GPUs reached the same accuracy” ([818줄](../../README.md#L818)) | M0 bf16은 **0.994/0.969/0.998**입니다. 큰 하락의 주원인을 정밀도 불일치로 설명할 수 있지만 GPU·런타임 영향을 배제할 수는 없습니다. [비교표](../../README.md#L844) |
| “On the existing synthetic dev sets M1-cord did not fall below M1 v1” ([97줄](../../README.md#L97)) | 자체 dev **−0.003**, 공개 faded **−0.0667**. “지정한 두 dev 세트에서 허용하락 기준 충족”이 정확합니다. [회귀 결과](../../reports/eval/compare_m1cord_dev_v1__vs__m1_dev_v1.json#L20) |
| “M1-cord is faster because it answers without a fence and without invented fields, so it generates fewer tokens.” ([514줄](../../README.md#L514)) | 지어낸 필드가 test **42개**입니다. “fewer invented fields”로 수정해야 합니다. [결과](../../reports/eval/cord_test_m1cord_nf4.json#L116) |

추가로 “서버 자동 테스트 없음”은 과장이 아닌 **오래된 과소서술**입니다. [README:676](../../README.md#L676)과 [서빙 회귀 테스트](../../tests/test_serving_core.py#L76)가 불일치합니다.

**5. 90점 이상으로 가는 현실적인 작업**

예상 가산점은 구현·검증 결과에 따른 제 평가이며 자동 합산을 보장하지 않습니다. 비용은 추가 GPU 이용료입니다.

| 개선 | 예상 가산 | 노력·시간·비용 |
|---|---:|---|
| CORD 실행 ID의 세트 변경 금지, 이력 보존, 평가 의존 파일 해시 검증·CPU 회귀 | **+2** | 중간, 로컬 CPU 2–4시간, **$0** |
| README 표현 정정과 구형 vLLM 실행 경로의 정밀도 불일치 차단—현재 `up()`은 원본 bf16에 NF4 어댑터를 붙임 | **+1** | 작음, CPU 1–2시간, **$0**. [해당 경로](../../src/invoiceguard/serving/vllm_bench.py#L35) |
| 검수 행 추가·삭제, 누락 PO 경고별 고유 식별자·회귀 테스트 | **+1** | 중간, CPU 2–4시간, **$0**. [경고 승인](../../src/invoiceguard/app/api.py#L352) |
| 단가·누락행 dev 실패에 한정한 개선 1회와 학습·dev 비교 | **성공 시 +1~2** | 중간, 로컬 GPU 1–3시간, **$0** |
| 선택: 동시성별 원문 채점·짧은 반복·5–10분 지속 부하 측정 | **+1~2** | 준비 1–2시간, Pod 1대 0.5–1시간, **약 $0.6–1.2**, 실제 견적 승인 후 |

우선순위는 **CORD 가드 보완과 README·서빙 경로 정합성 수정**입니다. 기존 test 결과는 보존하고 추가 모델 개선은 dev에서 평가하면 됩니다.