# 의뢰: 채용 포트폴리오 독립 평가 + 계획 자문 (1차)

## 대상
저장소 `H:/dev/invoiceguard-po` (공개: github.com/TaeyanG4/invoiceguard-po). 영어 인보이스 이미지 → Qwen3-VL-2B + QLoRA 추출 → 독립 발주서(PO) 대사 → 사람 검수 API → 승인본만 내보내기. 데이터는 모두 합성이다.

## 채용공고 (JobKorea 50342762, ㈜로그인네트웍, "AI 모델 개발자(LLM/VLM) – 오픈소스 파인튜닝·서빙")
회사는 수출입 서류(인보이스, 패킹리스트, B/L)를 통관 신고 데이터로 바꾸며, 외부 모델 API와 자체 학습 모델을 더 정확·빠르·싸게 만들려 한다.
- 업무: 공개 VLM/LLM LoRA/SFT(데이터·학습·평가), 품목·수량·단가·품번 추출 정확도, LLM 서빙 프레임워크 배포(양자화·추론 가속·배치 튜닝)와 GPU 서버 운영, 정답 대비 자동 채점·회귀 테스트, 실패 분석과 프롬프트·후처리·데이터 개선.
- 필수: HF transformers/peft/trl 실무 코드, 서빙 프레임워크 배포와 성능 실측, Linux/SSH, 수치 평가.
- 우대: OCR/문서 AI, 양자화, 멀티 GPU(DeepSpeed/FSDP), 클라우드 GPU 비용 최적화, 한영 혼합·표 문서, 무역·통관 도메인, Java/Spring Boot/React.

## 읽을 것 (한 묶음씩, 데이터셋은 열지 않음)
1. `README.md`(영어; `README.ko.md`는 한국어판) — 포트폴리오 첫 화면.
2. `plan.md`(앞으로의 계획), `handoff.md`(작업 내역), `reports/IMPLEMENTATION_STATUS.md`, `reports/TASK_BOARD.md`.
3. `reports/eval/final_summary.md`와 `reports/eval/` — 평가 결과.
4. `reports/runpod/RUNPOD_RUN.md`, `reports/RUNPOD_APPROVAL.md`, `reports/runpod/train_compare.json`, `reports/serving/vllm_bf16_a40.json`.
5. `src/invoiceguard/`(vlm/, serving/, app/, evaluation.py, reconciliation.py)와 `tests/` — 코드 품질과 README 주장의 근거.

참고: 지금 로컬 GPU에서 plan.md P3 실험(기본 모델 정밀도별 HF 추론, `scripts/quant/run_precision_dev20.sh`)이 돌고 있어 결과 파일이 아직 없다. 이 평가는 현재 상태 기준이다.

## 답할 것 (한국어, 약 900단어 이내)
1. **100점 만점 점수**와 가중치 표: 공고 항목마다 가중치·점수·근거 파일. 우리 결론을 모르는 상태에서 독립적으로 매긴다.
2. **치명적 공백**이 남아 있는지(이 회사 서류 검토자가 떨어뜨릴 수준인지) 분명히.
3. **90점 이상으로 가려면** 무엇이 필요한지: 항목별 예상 가산점, 노력, 유료 GPU 필요 여부. plan.md의 P1–P10에 대해 빠진 것·순서·과한 것을 자문해 달라.
4. vLLM에서 M1 정확도가 0.849(HF NF4 경로 0.960)로 떨어진 원인에 대한 너의 판단과, plan.md P3 실험 설계(E1–E5)가 원인을 가를 수 있는지. A40·리눅스·dtype(bf16/fp16/fp32) 차이 가능성도 따져 달라.
5. README에서 기록으로 뒷받침되지 않는 주장이나 과장(문장 인용 + 반박 파일). 없으면 "없음".
