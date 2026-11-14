# 의뢰: 채용 포트폴리오 독립 재평가 (2차)

## 대상
저장소 `H:/dev/invoiceguard-po` (공개: github.com/TaeyanG4/invoiceguard-po). 영어 인보이스 이미지 → Qwen3-VL-2B + QLoRA 추출 → 독립 발주서(PO) 대사 → 사람 검수 API → 승인본만 내보내기. 합성 데이터에 더해, 학습 효과를 가리기 위해 사람이 라벨을 단 실사진 영수증 CORD v2를 별도 태스크로 추가했다.

## 채용공고 (JobKorea 50342762, ㈜로그인네트웍, "AI 모델 개발자(LLM/VLM) – 오픈소스 파인튜닝·서빙")
회사는 수출입 서류(인보이스, 패킹리스트, B/L)를 통관 신고 데이터로 바꾸며, 외부 모델 API와 자체 학습 모델을 더 정확·빠르·싸게 만들려 한다.
- 업무: 공개 VLM/LLM LoRA/SFT(데이터·학습·평가), 품목·수량·단가·품번 추출 정확도, LLM 서빙 프레임워크 배포(양자화·추론 가속·배치 튜닝)와 GPU 서버 운영, 정답 대비 자동 채점·회귀 테스트, 실패 분석과 프롬프트·후처리·데이터 개선.
- 필수: HF transformers/peft/trl 실무 코드, 서빙 프레임워크 배포와 성능 실측, Linux/SSH, 수치 평가.
- 우대: OCR/문서 AI, 양자화, 멀티 GPU(DeepSpeed/FSDP), 클라우드 GPU 비용 최적화, 한영 혼합·표 문서, 무역·통관 도메인, Java/Spring Boot/React.

## 1차 평가 이후 바뀐 것 (사실 목록 — 평가는 직접 파일을 보고 독립적으로)
- vLLM 정확도 저하(0.849)의 원인을 로컬 정밀도 실험으로 규명하고(`reports/quant/precision_dev20.md`), RunPod L40S에서 NF4 역양자화 병합본으로 0.960 회복, FP8 측정(`reports/runpod2/`).
- 어댑터–기본 모델 정밀도 짝 검사(`src/invoiceguard/vlm/pairing.py`), 서빙 큐·데드라인 회귀 테스트(`tests/test_serving_core.py`).
- bf16 일반 LoRA를 L40S에서 학습·비교(P14).
- CORD v2 트랙: 지표·통과 기준을 학습 전에 고정(`docs/20_DECISIONS_V6.md`), dev 3 arm, M1-cord 학습, 기존 dev 회귀 확인, `configs/frozen_cord_v1.json` 동결 후 test 1회(`reports/eval/cord_test_*.json`).
- 관리자 대시보드에 CORD 페이지, README(영·한) 갱신, README의 CORD 표는 결과 파일에서 생성(`src/invoiceguard/readme_cord.py`).

## 읽을 것 (한 묶음씩, 데이터셋·이미지는 열지 않음)
1. `README.md`(영어; `README.ko.md`는 한국어판) — 포트폴리오 첫 화면.
2. `plan.md`, `handoff.md`(최신순 작업 내역), `reports/SESSION_HANDOFF.md`, `reports/IMPLEMENTATION_STATUS.md`, `reports/TASK_BOARD.md`.
3. `docs/20_DECISIONS_V6.md`, `reports/eval/`(특히 `final_summary.md`, `cord_*.json`, `compare_cord_*.json`), `reports/quant/`, `reports/runpod/`, `reports/runpod2/`, `reports/serving/`.
4. `src/invoiceguard/`(vlm/, serving/, app/, evaluation.py, cord.py, cord_eval.py, reconciliation.py)와 `tests/` — 코드 품질과 README 주장의 근거.

## 답할 것 (한국어, 약 900단어 이내)
1. **100점 만점 점수**와 가중치 표: 공고 항목마다 가중치·점수·근거 파일. 우리 결론을 그대로 믿지 말고 파일로 확인해 독립적으로 매긴다.
2. **치명적 공백**이 남아 있는지(서류 검토자가 떨어뜨릴 수준인지).
3. **CORD 사전 등록의 무결성**: 기준·수정 1의 시점, test 1회 강제, 내용 중복 처리, 비교 조건(같은 GPU·정밀도·프롬프트)에 허점이 있는지.
4. README에서 기록으로 뒷받침되지 않는 주장이나 과장(문장 인용 + 반박 파일). 없으면 "없음".
5. **90점 이상으로 가려면** 무엇이 필요한지: 항목별 예상 가산점, 노력, 비용. 아래 "평가 범위"의 조건을 지킨 제안만.
