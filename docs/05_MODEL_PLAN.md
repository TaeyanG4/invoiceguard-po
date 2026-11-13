# 05. 모델·학습·서빙 v3

## 장비와 프로세스
사용자 PC RTX 4070 Ti SUPER 16GB는 데이터 감사·CPU/화면 구현·선택적 작은 추론에 사용한다. 본학습과 live GPU 측정은 **RunPod 단일 Pod**를 우선한다. 기본 후보 4090 24GB, 메모리/가격/재고 문제 시 재승인된 A6000/A40 48GB. 어느 GPU가 항상 빠르다거나 24GB에서 반드시 학습된다고 보장하지 않는다.

## 실행 전에
1. 로컬 데이터 프로파일, renderer 검사, schema/evaluator/예산 계산을 먼저 완료한다.
2. 콘솔 가격·cloud tier·GPU 1개·스토리지·SSH 종류·$8 총지출 상한·최대 실행시간·종료 방식에 대해 사용자 승인을 받는다.
3. Full SSH port forwarding과 작은 파일 전송·해시를 먼저 확인한다. 공개 포트에 인증 없이 API를 켜는 대안은 금지한다.
4. 실제 선택한 GPU/container에서 Python·CUDA·torch·transformers·PEFT·bitsandbytes·TRL를 확인하고 검증된 버전을 기록한다. attention backend는 설치 위험이 낮은 지원 backend부터 사용한다. FlashAttention 재컴파일에 무제한 시간을 쓰지 않는다.

## 모델과 두 task
후보 `Qwen/Qwen3-VL-2B-Instruct`, 실제 revision 다운로드 후 pin. [S05]
- 공개 자료: PUBLIC_CANONICAL, 숫자값 라벨 기반 최소 출력.
- 자체 인보이스: TRADE_RAW, renderer가 보존한 원문 문자열 출력.
- 한 어댑터에 두 종류의 (고정 prompt, image, answer) record를 섞는다. 태스크별 데이터 수와 샘플 가중치는 기록하며 제품은 TRADE_RAW만 호출한다.

## 유료 파일럿 게이트
훈련 후보 이미지 8개(여러 행 수/형태)로 실제 생성 token 수, 이미지 리사이즈 후 가독성, 지연·VRAM 측정. final은 보지 않는다. 실제 target token 분포를 구해 출력/sequence 제한보다 긴 label을 알아낸다. image token이나 정답 뒤쪽을 조용히 자르지 않는다. 학습 record가 길면 해상도·출력 스키마·행 지원범위를 검토한 후 기록하고 **본학습 전** 확정한다. final의 긴 문서는 실패/unsupported로 분모에 남긴다.

10 optimizer-step smoke를 수행한다. 어시스턴트 정답에 nonzero target token이 있으며, prompt/system/image/pad는 -100인지 실제 decode로 확인한다. vision과 projector가 frozen인지 실제 파라미터 이름으로 검사한다. LoRA target을 `q_proj/v_proj` 이름만으로 전역 탐색해 vision까지 학습시키지 않는다. 최소 하나의 LoRA gradient가 유한하고 업데이트 후 adapter 파라미터가 변경돼야 한다. 초기화 특성상 모든 LoRA 파라미터에 매 step nonzero gradient를 강제하지 않는다.

현행 TRL 문서는 VLM assistant-only loss에 버전/chat template 조건을 둔다. 자동 mask가 되는지 검사하고 성공한 환경만 lock한다. 미지원 환경은 검증한 completion-only collator로 대체할 수 있지만 prompt-only 토큰 길이 추정으로 대충 masking하지 않는다. [S06]

## 본학습
파일럿의 비용/속도만 보고 standard/mini를 정하고 manifest/config를 동결한다. smoke로 바뀐 모델을 이어 학습하지 않고 base/seed/optimizer를 초기화해 M1을 시작한다. NF4 4-bit + double quant, rank8/alpha16, language adapter, microbatch1, grad_accum8, checkpointing. standard 최대80 optimizer step, mini40; 숫자는 상한이며 실제 step·보인 example 수를 기록한다. optimizer step과 micro-step을 구분한다.

M0와 M1 비교는 같은 base/4-bit 로딩, 같은 prompt와 generation, 같은 입력 해상도다. 본학습 중 dev loss 선택은 가능하지만 final로 checkpoint를 선택하지 않는다. NaN/OOM이면 실패를 기록한다. OOM 대응은 unneeded process 종료→batch/activation 점검→읽을 수 있는 해상도 축소→길이 검사→필요 시 재승인된48GB 순서. 정답/image 토큰 절단으로 통과시키지 않는다.

## 어댑터 검증
base revision, adapter config/hash, processor/tokenizer revision을 저장한다. 모델을 완전히 내린 후 base+adapter를 재로드하여 훈련/개발 고정 이미지 추론이 실제로 수행되는지 검사한다. API 응답에 active adapter hash가 없으면 M1이라고 표시하지 않는다. 한 GPU에서 학습기와 서버를 동시에 띄우지 않는다.

## 서빙 P0
Transformers+PEFT GPU inference server가 기본이다. vLLM은 optional이며 연결이 없다고 P0가 막히지 않는다. 로컬 FastAPI→Full SSH tunnel→127.0.0.1 GPU API. semaphore1, bounded queue, request_id. 120초 timeout 이후 GPU 작업이 계속 돌지 않는지 확인한다. 취소 불가 worker는 신규 요청을 차단하고 종료·재기동 후 ready로 바꾼다. HTTP 타임아웃만 내고 orphan inference를 쌓지 않는다. 모델 unavailable은 503이며 oracle로 자동 대체하지 않는다.

## 서빙 실험
동시성1/2는 먼저 직렬 GPU+queue의 실제 행동을 측정한다. CPU 전처리 캐시 또는 지원되는 배치 같은 최적화는 동일 문서·모델·정밀도·정확도 조건에서 비교한다. 결과 캐시는 GPU 처리량 측정에서 비활성화한다. GPU memory, server process 상태, 요청 실패, wall/inference 시간을 남긴다. QLoRA 학습을 했다는 사실만으로 4-bit 서빙의 정확도/속도를 증명하지 않는다.
