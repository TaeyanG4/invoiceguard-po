# 의뢰: 6차 평가 후속 확인 (astra) — 신규 감점 2건의 수정 여부만

6차 평가(`reports/reviews/astra-6.md`, 96.0)에서 새로 깎은 두 항목을 커밋 e9e0ca2에서 고쳤다고 한다. 파일과 `git show e9e0ca2`로 직접 확인하고, 다른 항목은 다시 평가하지 말 것. `reports/reviews/briefs/review_constraints.md`의 제외 규칙은 그대로 적용한다.

1. **서비스 연계: PO 일치 (−0.5):** 같은 발주서 ID · 버전에 내용이 다른 JSON을 올리면 기존 발주서에 인보이스가 연결되던 문제.
   주장: API가 내용이 같으면 `PO_VERSION_EXISTS`, 다르면 `PO_VERSION_CONFLICT`(409)를 돌려주고, 검수 화면은 `PO_VERSION_EXISTS`일 때만 계속한다(`src/invoiceguard/app/api.py`, `src/invoiceguard/app/static/review.js`, `tests/test_app.py`의 `test_po_validation`). 예시 불러오기 경로도 `PO_VERSION_CONFLICT`를 쓴다.
2. **결과 보고 정확성 (−0.5):** README의 "No field dropped" 과장.
   주장: 한영 README 모두 "게이트 기준(0.05 넘게 · 3칸 이상)을 넘는 하락은 없지만 작은 하락은 있음(r16 수량 189 → 188, 행 금액 177 → 175)"으로 고쳤다(`README.md`, `README.ko.md`의 LoRA ablation 문단).

## 답할 것
- 두 항목 각각 "고쳐짐 / 일부 / 남음"과 근거 파일:줄.
- 수정이 새 문제를 만들었는지(예: 정상 재업로드 경로가 막혔는지).
- 고친 결과를 반영한 최종 점수(0.5 단위)와 한 줄 판정.
