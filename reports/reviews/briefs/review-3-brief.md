# 의뢰: 채용 포트폴리오 독립 재평가 (3차) — 감점 사유 중심

## 대상
저장소 `H:/dev/invoiceguard-po` (공개: github.com/TaeyanG4/invoiceguard-po). 영어 인보이스 이미지 → Qwen3-VL-2B + QLoRA 추출 → 독립 발주서(PO) 대사 → 사람 검수 API → 승인본만 내보내기. 합성 데이터와, 학습 효과를 가리기 위한 사람 라벨 실사진 영수증 CORD v2.

## 채용공고 (JobKorea 50342762, ㈜로그인네트웍, "AI 모델 개발자(LLM/VLM) – 오픈소스 파인튜닝·서빙")
회사는 수출입 서류(인보이스, 패킹리스트, B/L)를 통관 신고 데이터로 바꾸며, 외부 모델 API와 자체 학습 모델을 더 정확·빠르·싸게 만들려 한다.
- 업무: 공개 VLM/LLM LoRA/SFT(데이터·학습·평가), 품목·수량·단가·품번 추출 정확도, LLM 서빙 프레임워크 배포(양자화·추론 가속·배치 튜닝)와 GPU 서버 운영, 정답 대비 자동 채점·회귀 테스트, 실패 분석과 프롬프트·후처리·데이터 개선.
- 필수: HF transformers/peft/trl 실무 코드, 서빙 프레임워크 배포와 성능 실측, Linux/SSH, 수치 평가.
- 우대: OCR/문서 AI, 양자화, 멀티 GPU(DeepSpeed/FSDP), 클라우드 GPU 비용 최적화, 한영 혼합·표 문서, 무역·통관 도메인, Java/Spring Boot/React.

## 2차 평가(Fable 79 · astra 88, `reports/reviews/fable-2.md`, `astra-2.md`) 이후 바뀐 것 — 사실 목록, 파일로 직접 확인할 것
- **test 1회 가드** (`src/invoiceguard/cord_guard.py`, `tests/test_cord_freeze.py`): 같은 arm의 두 번째 test(예측 폴더를 지워도 커밋된 채점 보고서로 거부), 끝난 실행 ID의 세트 변경, 동결 뒤 바뀐 채점기를 거부. CI가 채점기·프롬프트·manifest = 동결 해시, test 보고서는 arm마다 1개인지 검사.
- **README 문장 정정**: GPU 결론의 범위 한정, 회귀 문장, "지어낸 필드", 수정 1 시점, 서빙 서버 자동 테스트. 맨 위 "1분 요약". `docs/20_DECISIONS_V6.md`에 기록 정정 절.
- **vLLM 짝 검사**: `vllm_bench up()`이 NF4 어댑터를 bf16 원본에 붙이면 거부(`tests/test_pairing.py`).
- **검수 API**: 행 추가·삭제(`add_row`/`delete_row`), 모든 경고에 `key`, 빠진 PO 행마다 고유 키(`tests/test_app.py`).
- **사전 고정만 하고 아직 실행하지 못한 것 (not_run)**: docs/20 수정 2(seed 2개 추가, dev만)와 수정 3(단가 인쇄 영수증 가중, dev만). 로컬 GPU를 사용자의 다른 프로그램(게임)과 함께 쓸 수 없어 PC가 빌 때 돌도록 대기 중이다(`scripts/realdocs/gpu_free_runner.py`, `handoff.md`). 결과 파일은 없다 — 있는 것처럼 평가하지 말 것.
- 2차 평가 때 지적된 CORD 단가 하락의 원인 분석은 `handoff.md`(2026-11-15 02:00 항목)와 docs/20 수정 3 근거에 있다.

## 읽을 것 (한 묶음씩, 데이터셋·이미지는 열지 않음)
1. `README.md`(영어; `README.ko.md` 한국어판).
2. `plan.md`, `handoff.md`(최신순), `reports/SESSION_HANDOFF.md`, `reports/IMPLEMENTATION_STATUS.md`, `reports/TASK_BOARD.md`.
3. `docs/20_DECISIONS_V6.md`, `reports/eval/`, `reports/quant/`, `reports/runpod/`, `reports/runpod2/`, `reports/serving/`.
4. `src/invoiceguard/`와 `tests/`, git 이력(읽기 전용 `git log`/`git show`).

## 답할 것 (한국어, 약 900단어 이내)
1. **100점 만점 점수**와 가중치 표.
2. **감점표 (가장 중요)**: 깎은 점수마다 한 줄씩 — 공고 항목, 깎은 점수, 구체적 사유, 근거 파일(줄 번호), 그리고 그 감점이 (a) 2차 평가 이후 고쳐졌는지/남았는지, (b) 무엇을 하면 되돌릴 수 있는지(시간·비용). 아래 "평가 범위" 규칙으로 감점하지 않은 항목은 따로 한 줄로 적는다.
3. 치명적 공백이 남아 있는지.
4. README·기록에서 뒷받침되지 않는 주장이나 과장(인용 + 반박 파일). 없으면 "없음".
5. 90점 이상까지 남은 것(평가 범위 조건 안의 제안만).
