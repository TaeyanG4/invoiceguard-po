---
type: log
title: InvoiceGuard-PO — 작업 내역 (handoff)
description: 지금까지 한 작업, 결과, 결정, 남은 일을 최신순으로 쌓는 기록. 이어서 작업할 때 먼저 읽는다. 계획은 plan.md.
tags: [portfolio, handoff, log]
generated: {by: claude-opus-5.5, at: 2026-11-14T19:10+09:00}
sources:
  - id: implementation-status
    resource: reports/IMPLEMENTATION_STATUS.md
  - id: runpod-run
    resource: reports/runpod/RUNPOD_RUN.md
  - id: session-snapshot
    resource: reports/SESSION_HANDOFF.md
---

# 작업 내역

이어서 작업할 때: 이 파일 → `plan.md` → `reports/SESSION_HANDOFF.md`(환경·해시·리소스 상태) 순서로 읽는다.
기록 규칙: 항목마다 시각(KST) · 한 일 · 실제 결과(수치와 근거 파일) · 결정 · 다음 할 일. 실행하지 않은 것은 not_run, 실패는 failed. 비밀값은 적지 않는다.

## 2026-11-15 08:20 — 수정 3 결과: 효과 없음, 로컬 서빙 지속 부하 측정 중
- **수정 3 (단가 인쇄 영수증 2배, 1,374건, 22.1분, loss 0.0671):** dev 품목 단가 0.68 → 0.70, strict 0.762 → 0.758(−0.004 [−0.032, +0.021]), M0 대비 +0.046 [+0.002, +0.089]. 사전 기준(단가 +0.10 이상) 미충족 → **효과 없음**. "두 번 인쇄된 단가" 누락 5칸·"@" 2칸 그대로(`reports/eval/cord_failure_dev.md`). 단가 null을 금액으로 채우는 후처리는 지어냄(M0 160칸)을 되살려 쓰지 않음. README 6장에 기록.
- GPU 실행기 6개 작업 모두 완료(ALL DONE 08:14, 메모리 상한 뒤 경합 0회).
- **서빙 측정 (astra 3 지적):** 로컬 HF+PEFT 서버(M1 v1)에 `vllm_bench run --conc 1,2,4 --docs 10`(모든 답 채점) + `--duration 300 --conc 2`(5분 지속 부하) 실행 중.

## 2026-11-15 07:40 — 3차 지적 CPU 수정, 메모리 상한으로 GPU 학습 정상화, seed 반복 결과
- **CPU 수정 (커밋 4beb38f · 062b108 · 9f6143c):** `cord_score.py`(test 채점·비교에 동결 검사, test 보고서 한 번만 쓰기 — 커밋된 test 보고서를 다시 채점하니 바이트 단위로 같음), `cord_guard.py`(끝났거나 채점된 test run 재개 금지), findings 스키마에 `key` + API 응답 스키마 검증, `TRAIN_DATA_SOURCES`(모든 --data가 읽는 manifest 해시 기록), `reports/eval/cord_failure_dev.md`(단가 맞바꿈: M0 지어냄 160칸 → M1-cord 20칸, 대신 인쇄된 단가 10칸 비움 / 하위 품목 정답 50 중 M0 10 · M1-cord 27), 벤치가 모든 동시성에서 답을 채점·잘림·상태 코드·`--duration` 지속 부하. 테스트 214개.
- **GPU 원인 확정:** osu! 종료 후에도 학습이 step 1에서 멈춤(15.9 GB, 80 W) → 학습 프로세스의 메모리 풀이 실제 사용(약 7 GB)보다 훨씬 커져 데스크톱 0.8 GB만 더해져도 공유 메모리로 넘침. `set_per_process_memory_fraction(0.75)`(12 GB, `INVOICEGUARD_CUDA_MEM_FRACTION`, 보고서 env에 기록) 후 06:12부터 6.7–7 s/step, 7.4–8.8 GB, 220 W로 정상. docs/20에 결과 전 기록.
- **seed 반복 (수정 2):** seed 20261114 학습 27.7분(loss 0.0616), dev 0.756, M0 대비 +0.044 [0.000, +0.087] / seed 20261115 dev 0.772, +0.060 [+0.017, +0.103]. seed 20261113 +0.050. 평균 **+0.051**, 모두 > 0 → 사전 기준 충족. 단가는 세 seed 모두 0.64–0.68(M0 0.82). README 6장에 표, 요약·한계 문장 갱신.
- **수정 3 (단가 가중) 학습 07:38 시작**, 이어서 dev 평가.

## 2026-11-15 05:05 — 3차 평가: Fable 82.5 · astra 89, GPU 작업 일시 정지
- 사용자: "그럼 당분간 멈춰봐 osu 끝나면 알려줄게" → GPU 실행기 정지(작업은 시작 전, 남은 프로세스 없음, GPU 741 MiB). osu! 종료 알림 후 `gpu_free_runner.py cord_r5_r6` 재시작.
- **Fable 3 = 82.5** (`reports/reviews/fable-3.md`, 감점 −17.5): seed 1개(−2), 단가 하락·개선 검증 없음(−3), CORD 모델 vLLM 서빙·작은 표본(−3), 무역 서류 종류(−1.5), 검수 UI(−1), 품번·모호수량·하위 품목(−2), 비용 추정·Pod 자동 정지·실행기 결함(−1.5), 회귀 게이트·채점 시 동결 검사·낡은 상태 표기·레시피 ablation(−3.5). 상승분은 무결성·문서·가드.
- **astra 3 = 89** (`reports/reviews/astra-3.md`, 감점 −11): seed(−1), 단가(−2), 모호수량(−1), 하위 품목(−1), 고동시성 응답 미채점·지속 부하 없음(−2), `cord_eval score/compare`에 동결 검사 없음(−1), 같은 run 폴더만 있으면 유실 예측 재생성 가능(−1), `all_plus_cord_up` manifest 해시 미기록(−0.5), 문구 2곳(−0.5), 경고 `key`가 findings 스키마에 없음(−1). 단가 "분석 없음" 감점은 철회. "추가 GPU 없이 CPU 보완 2–3시간으로 90 가능"이라고 평가.

## 2026-11-15 04:58 — 로컬 GPU 경합으로 R5·R6 대기, 3차 평가 의뢰
- 사용자 결정: GPU 실험은 "Local, when PC is free"(03:10경). `scripts/realdocs/gpu_free_runner.py`로 PC가 빌 때만 실행.
- 02:12 재시작한 seed 학습도 02:23부터 다시 느려짐(10 → 354 s/step) — osu!·NVIDIA Overlay가 함께 실행 중. 03:08 중단.
- 실행기 1차(03:13–04:53): osu!가 계속 실행되어 20번 재시작 후 중단. 실행기 결함도 있었다 — 이전 시도의 느린 속도 줄을 새 시도에 그대로 읽어 정상 시작을 30초 만에 멈춤. 학습 프로세스는 시작 1분 안에 GPU를 약 15.9 GB까지 잡는다(정상 동작). 로그 `artifacts/logs/gpu_runner_attempt1.log`.
- 수정(d0d8c2d): osu! 등 게임 프로세스가 떠 있으면 대기, 속도는 이번 시도 출력만으로 판단, 메모리만 꽉 찼다고 멈추지 않음. 04:5x 재시작 — osu!가 꺼질 때까지 대기 중.
- 3차 평가: `reports/reviews/briefs/review-3-brief.md`(감점표 요청, R5·R6은 not_run으로 명시) + `review_constraints.md`(하드웨어·시간 한계, README 길이는 사용자 결정)로 Fable·astra 동시 의뢰.

## 2026-11-15 02:15 — seed 학습 중단·재시작 (WDDM 메모리 밀림), README 1분 요약
- **사고:** seed 20261114 학습이 step 55(01:58)부터 5.9 s/step → 110 s/step으로 느려짐(GPU 15.6/16 GB, 98 % 사용률에 84 W). 01:58에 학습 중인데 `.venv-ml` Python으로 `import invoiceguard.vlm.train` 확인을 돌린 직후다. Windows WDDM이 새 CUDA 컨텍스트 때문에 학습 프로세스 메모리를 공유 메모리로 밀어낸 것으로 판단(남은 예상 5시간 이상). 두 백그라운드 작업을 TaskStop하고 남은 bash·python 4개를 PID로 종료, GPU 282 MiB 확인. 학습 결과물(어댑터·예측)은 생기기 전이라 지울 것 없음. 로그는 `artifacts/logs/cord_seeds_chain_aborted_wddm.log`로 보존.
- **재시작:** 02:14경 seed 반복 → 단가 실험을 한 체인으로 다시 시작(같은 run id, 수정 2·3 그대로). 재발 방지: 학습이 도는 동안 torch를 여는 Python은 실행하지 않는다(메모리에 기록).
- **README:** 영·한 맨 위에 "1분 요약" 표(실사진 효과, 서빙 회복, 재현, 대사, 무결성, 비용, 한계) — Fable 지적("README 961줄").

## 2026-11-15 02:00 — 2차 평가 반영 R1–R4 완료, seed 반복·단가 개선 실험 실행 중
- **R1 test 가드** (`src/invoiceguard/cord_guard.py`, infer.py가 사용): 같은 arm의 두 번째 test(예측 폴더를 지워도 커밋된 `reports/eval/cord_*.json`으로 막음), 끝난 실행 ID의 세트 변경, 동결 뒤 바뀐 채점기(cord_eval·cord·model_output 해시)를 거부. `tests/test_cord_freeze.py` 7개가 CI에서 채점기·프롬프트·manifest = 동결 해시, test 보고서는 arm마다 1개·동결 설정을 검사. 실제 상태로 확인: 새 실행 ID의 M1-cord test → `cord_test_already_run`·`cord_test_already_scored` 거부.
- **R2 문장:** README L97(회귀 기준은 두 세트, 나머지 중 최대 하락 faded −0.067), L498(수정 1은 M0 dev 18건 본 뒤), L514(지어낸 필드가 "훨씬 적게"), L676(서버 자동 테스트 6개 + 실제 요청 6/6), L818(GPU 결론은 20문서 범위, 문서 1건 차이는 배제 못 함). docs/20에 기록 정정 절.
- **R3:** `vllm_bench up()`이 컨테이너 전에 짝 검사 → NF4 어댑터를 bf16 원본에 붙이면 거부(`--allow-precision-mismatch`로만), 테스트 1개.
- **R4:** 검수 API `add_row`·`delete_row`(행 번호 재부여, 경고 재계산), 모든 경고에 `key`, 빠진 PO 행 경고는 SKU별 키. 테스트 1개, README 8장.
- 테스트 209개 실패 0, verify_pack 306 · contracts 63 pass. 커밋 3daa2a6.
- **R5 seed:** `run_cord_seeds.sh` 01:52:39 시작(seed 20261114 → 20261115, 각 학습 약 24분 + dev 약 14분).
- **R6 분석 (dev만):** M1-cord 단가 누락 10칸 중 8칸은 행은 냈는데 단가만 null(단가 = 금액으로 두 번 인쇄, 또는 "@" 단가를 금액 칸에). train에서 단가 인쇄 품목 29 %. → **수정 3**(단가 인쇄 영수증 272장 2배, dev만, 판정 사전 고정) 커밋 4b0e6de 후 `run_cord_up.sh`를 seed 체인 뒤에 자동 실행하도록 대기.

## 2026-11-15 01:52 — 2차 평가: Fable 79 · astra 88, 반영 계획(단계 4), seed 사전 고정
- **Fable 2 = 79/100** (1차 70, `reports/reviews/fable-2.md`, 165초): 치명적 공백 없음. 약점 — 단일 seed, CORD 단가 하락 분석 없음, 서빙과 실데이터 분리. 사전 등록 허점 4개(원안·수정 1이 한 커밋, 시각 정정 기록 없음, test 1회 가드 약함, 동결 전 원격 시각 없음). README 수치 과장 없음, 문장 3곳 수정 요청. 90 경로: CORD 실패 분석·개선(+2.5), CORD vLLM 서빙(+2.5, 유료), seed 2개(+2), 회귀 게이트·가드(+1.5), 한영 혼합 레이아웃(+1.5), 문서 정정(+1).
- **astra 2 = 88/100** (1차 76, `reports/reviews/astra-2.md`): 치명적 공백 없음, vLLM 해결·정밀도 원인 분리를 높게 평가. 약점 — test 1회 강제의 구현 결함(완료된 test 실행 ID를 cord:dev로 재사용하면 통과, 평가기 해시 미검사), 단가·모호수량, 검수 API에 행 추가·삭제 없음, 구형 `vllm_bench up()`이 bf16 기본 모델에 NF4 어댑터를 붙임. README 3곳 한정 필요(L818 GPU 결론, L97 회귀 문장, L514 "지어낸 필드 없이").
- **결정:** 두 평가 공통 지적부터(plan.md 단계 4, R1–R7). docs/20에 기록 정정 + **수정 2(seed 20261114·20261115, dev만, 보고 기준 사전 고정)**를 seed 학습 전에 커밋. R7(유료)은 견적·승인 후.

## 2026-11-15 01:50 — 재평가 준비: 상태 문서 갱신, P12 실제 요청 확인, CORD 백업, 평가 의뢰
- **P12:** 리팩터링한 HF+PEFT 서버(127.0.0.1:8001, M1 v1 어댑터)에 `vllm_bench run --docs 3 --conc 1` → M0·M1 각 3건 원문이 오프라인 dev 출력과 **6/6 동일**, 실패 0, M1 p50 17.7초(`reports/serving/hf_server_refactor_smoke.json`). 서버는 TaskStop 후 포트 8001 닫힘·고아 프로세스 없음 확인.
- **백업:** CORD 어댑터·예측 원문 18파일을 `H:/dev/invoiceguard-po-backup`에 복사, 해시 일치(`reports/backup_inventory_cord.json`).
- **상태 문서:** `reports/SESSION_HANDOFF.md` 다시 씀(실행 2·CORD 반영, vLLM 해결, not_run 목록), `IMPLEMENTATION_STATUS.md`·`TASK_BOARD.md`에 실행 2·CORD·P12 반영(G6·G7 갱신, 추가 트랙 표).
- **평가 의뢰:** `reports/reviews/briefs/review-2-brief.md` + `review_constraints.md`(하드웨어·시간 한계 항목 제외)로 Fable(하위 에이전트)·astra(`consult_astra.py`) 동시 의뢰.

## 2026-11-15 01:30 — CORD test 판정: 파인튜닝 효과 사전 기준 충족, CI 실패 1회 수정, push
- **test 실행** (`run_cord_test.sh`, 로컬 4070 NF4, 동결 `configs/frozen_cord_v1.json`, arm마다 1회): M0 00:32–00:53(1,217.7초) · M1-cord 00:53–01:05(669.2초) · M1 v1 01:05–01:22(1,060.4초). 전체 50분.
- **결과** (`reports/eval/cord_test_*.json`, 펜스 하나만 벗긴 출력): strict M0 **0.689**(729/1,058) · M1 v1 0.215 · M1-cord **0.754**(798/1,058). 형식 무시 0.737 / 0.278 / 0.792. F1 0.640 / 0.363 / 0.822. 미중복 85건 0.671 / 0.200 / 0.734. 펜스 없는 JSON 0/100 · 75/100 · 100/100. 지어낸 필드 264 · 116 · 42.
- **사전 기준 판정 (docs/20):** M1-cord − M0 strict **+0.0652 [+0.0272, +0.1073]** → "파인튜닝 효과 있음" 충족. 형식 무시 **+0.0548 [+0.0193, +0.0953]** → "형식만이 아니라 읽기도 좋아짐" 충족. 미중복 85건도 +0.0635 [+0.021, +0.109]. 기존 성능 유지는 dev 회귀로 이미 충족. dev(+0.0497)와 같은 방향, dev를 보고 바꾼 설정 없음.
- M1 v1 − M0 −0.4735 [−0.543, −0.400] (JSON 읽히지 않음 25/100, 합계 0.12) — 합성 인보이스 어댑터는 영수증으로 전이되지 않음.
- 필드별(test): 소계 0.64→0.91, 합계 0.59→0.91, 세금 0.43→0.67 상승 / 단가 0.82→0.72, 품목 금액 0.84→0.82 하락(dev와 같은 방향). 하위 품목은 모두 약함.
- **README:** `readme_cord.py`로 CORD 표 3개를 결과 파일에서 생성(빈칸 없어짐), 1장·6장 결론 문장을 test 기준으로 수정. 대시보드는 결과 파일을 읽어 자동 반영.
- **CI:** 첫 push(63569f9)에서 "Package contract checks" 실패 — astra 평가 문서의 로컬 절대경로 링크(H:/dev/…) 31개, handoff의 `](CI …)` 오인 링크 2개. 상대경로·#L 링크로 바꾸고 띄어 써서 1270441에서 통과. consult_astra.py가 앞으로 링크를 자동 변환, verify_pack.py는 로컬 전용 폴더(.venv 등)를 건너뛰어 로컬에서도 CI와 같은 결과(264 pass). 앞으로 push 전에 verify_pack·verify_contracts·pytest를 모두 돌린다.
- **push:** 사용자 요청("깃에 올려봐 확인해보게")으로 main에 push(c003a03..1270441). 그 뒤 커밋은 로컬.

## 2026-11-15 00:45 — CORD dev 3 arm·학습·회귀 완료, 동결, test 1회 실행 중, 대시보드·README 반영
- **체인 시간** (`artifacts/logs/cord_local_chain.log`, UTC 스탬프 → KST): M1 v1 dev 22:57:13–23:18:55 · M1-cord 학습 23:18:55–23:42:26(train_seconds 1,354) · M1-cord dev 23:42:26–23:56:51 · 기존 dev 회귀 23:56:51–00:26:56(1,780.8초). 체인 전체 약 1시간 30분.
- **M1-cord 학습** (`reports/model/train_m1_cord_v1.json`): 1,102건(공개 200 + 자체 160 + CORD 742), 240 step ≈1.74 epoch, 22.6분, loss 0.370 → 0.030(평균 0.063), VRAM 7.02GB, 1,919 micro-step 마스크 재검사, 어댑터 sha256 630d3dd1….
- **CORD dev 결과** (`reports/eval/cord_dev_*.json`, 펜스 하나만 벗긴 출력):

| arm | strict | 형식 무시 | F1 | 미중복 80 | 펜스 없는 JSON | 지어낸 필드 | 시간 |
|---|---:|---:|---:|---:|---:|---:|---:|
| M0 | 0.712 | 0.777 | 0.654 | 0.706 | 0/100 | 269 | 20.7분 |
| M1 v1 (CORD 없음) | 0.304 | 0.393 | 0.425 | 0.272 | 79/100 | 163 | 20.9분 |
| M1-cord | **0.762** | **0.812** | **0.845** | **0.744** | 100/100 | 24 | 13.6분 |

- **짝지은 차이(dev, 참고):** M1-cord − M0 strict **+0.0497 [+0.005, +0.093]**(기준 +0.05에 점추정 0.0003 모자람), 형식 무시 +0.036 [−0.001, +0.073] (CI 0 포함), F1 +0.191 [+0.152, +0.231], 문서 일치 +0.32. M1 v1 − M0 −0.408 [−0.503, −0.307] — 합성 인보이스 어댑터는 영수증으로 전이되지 않음(합계 0.11).
- **필드별(dev):** M1-cord가 tax 0.49→0.72, total 0.74→0.90, item.count 0.80→0.90 상승, item.unit_price 0.82→0.68, item.price 0.86→0.80 하락. 하위 품목은 모든 arm 약함.
- **회귀(기존 dev, m1_dev_v1과 같은 세트):** `compare_m1cord_dev_v1__vs__m1_dev_v1.json` — trade dev −0.003 [−0.032, +0.021], public dev clean +0.033 [+0.004, +0.077] (M1-cord 1.000) → 기준(−0.03 이내) 충족. 나머지 5개 −0.067 ~ +0.162.
- **동결:** 커밋 92892c5(결과·대시보드) 뒤 `freeze_cord.py` → `configs/frozen_cord_v1.json`(code_dirty false) 커밋 fa750bb. dev 결과를 보고 바꾼 설정 없음(학습 설정·프롬프트는 docs/20 그대로).
- **test 실행 중:** `scripts/realdocs/run_cord_test.sh` 00:32:32 시작(M0 → M1-cord → M1 v1, 약 55분), 로그 `artifacts/logs/cord_test_chain.log`. 동결 검사 통과 확인. GPU 작업은 이것 하나, RunPod 리소스 없음.
- **대시보드:** 새 페이지 2개 — "CORD 영수증"(필터 목록 → 사진 + 정답 + 기록된 실행별 예측을 칸마다 ✓/≈/✗/∅/+ 비교, 원문 출력) · "CORD 평가"(사전 기준 표, dev/test 막대, paired 차이 포레스트, 세부 지표·필드별 표, 학습 loss, 걸린 시간, 데이터 카드). test 칸은 결과 파일이 생기기 전까지 빈칸(—). 개요·분할 페이지에도 CORD 카드. API `/api/cord/rows|doc|image`(ID 정규식 + manifest, 이미지 해시 검사). 4번째 arm 색 #c98500/#eda100 팔레트 검사 통과. 테스트 9개 추가(대시보드 테스트 전체 통과).
- **README(영·한):** 배지·머리말, 1장 요약에 CORD 표(test 빈칸), 3.5 CORD 데이터(샘플 `docs/images/data/cord-dev-sample.jpg`), 4장 M1-cord 학습, 6장 CORD 결과·사전 기준·한 장 예시, 7장 vLLM 회복, 9장 대시보드 페이지, 11장 비용 약 $2.16·한계, 12장 실행 2(L40S) 표, 13장 재현, 14장 출처.
- **다음:** test 3 arm 채점 → compare(M1-cord−M0, M1-cord−M1 v1, M1 v1−M0) → 사전 기준 판정 → README·대시보드 test 칸 채움 → 커밋. 이후 Fable·astra 재평가.

## 2026-11-14 22:58 — CORD dev M0 기준선 결과
- **실행:** `infer --arm m0 --set cord:dev` 로컬 4070 NF4, batch 1, 22:36:24–22:57:05 (1,240.6초, 문서당 12.4초, 최대 VRAM 2.35GB). 체인(`run_cord_local.sh`)은 22:57:13에 이어서 시작.
- **결과** (`reports/eval/cord_dev_m0_nf4.json`, 펜스 벗긴 출력 기준): 필드 정확도 **0.712**(717/1,007), 형식 무시 0.777, 순서 무관 F1 0.654(정밀도 0.559 · 재현율 0.788), 내용 미중복 80건 0.706. strict JSON 0/100(전부 펜스). 문서 완전 일치 1/100, 행 수 일치 0.67.
- **약한 곳:** 하위 품목(count 0.03, name 0.20, price 0.29), tax 0.49, 정답에 없는 값 채움 269개(예: 인쇄되지 않은 unit_price를 price로 채움, 거스름돈을 tax로).
- **판단:** 합성 데이터와 달리 0.55–0.80 난이도 범위 안 → 학습 효과를 볼 여지가 있음.

## 2026-11-14 22:43 — CORD v2 준비 완료, 로컬 M0 기준선 실행 중
- **승인:** 사용자 "내려받기 승인"(22:27경). `scripts/realdocs/fetch_cord.py` → 6개 parquet 2,307,284,272 bytes, 51.9초, Hub LFS 해시 6/6 일치(`reports/realdocs/cord_fetch.json`). 원본은 `data/raw/cord-v2/<rev>/`(git 제외).
- **변환:** `python -I -m invoiceguard.cord build` → `manifests/cord_v2.jsonl`(sha256 42a8371d…), gold 1,000건 모두 `schemas/cord_extraction.schema.json` 통과. 리스트 라벨 masked: train 18 / dev 1 / test 2 문서.
- **발견 — 내용 중복:** 공식 분할에서 사진은 다르지만 정답이 같은 문서가 test 15건, dev 20건(train과 동일). 정답 암기를 막기 위해 dev·test와 같은 정답인 train 40건을 학습 제외 → 학습 가능 742건. test는 100건 그대로 + 미중복 85건 따로 보고.
- **판정 기준 사전 고정:** `docs/20_DECISIONS_V6.md`(OKF). 주 지표 필드 정확도, 보조 형식 무시 정확도·순서 무관 F1, 통과 기준 M1-cord − M0 ≥ +0.05이고 CI 하한 > 0.
- **수정 1(dev 관찰, 학습·test 전):** M0가 dev 첫 18건 모두 ```json 펜스로 감쌈 → 필드 점수는 펜스 하나만 벗긴 출력으로, strict JSON 비율은 형식 지표로 따로.
- **토큰 예산:** 742/100/100건 모두 마스크 검사 통과, 최대 1,820토큰(예산 6,144), 정답 최대 855토큰(<1,536) (`reports/realdocs/cord_budget.json`).
- **코드:** `cord.py`, `cord_eval.py`, 프롬프트 `EXTRACT_CORD_RAW.txt`, `records.cord_records`, `infer --set cord:*`(test는 `configs/frozen_cord_v1.json` + `--allow-final` + 1회), `train --data all_plus_cord`. 테스트 8개 추가, 전체 통과.
- **실행 중:** M0 NF4 CORD dev(로컬, 문서당 약 12.6초). 다음: `scripts/realdocs/run_cord_local.sh`(M1 v1 dev → M1-cord 학습 240 step → M1-cord dev → 기존 dev 회귀).
- **주의:** CORD 관련 코드 변경으로 frozen_v1 appendix의 코드 해시는 현재 코드와 다르다. v1 final은 이미 1회 실행된 과거 결과이고 다시 돌리지 않는다.

## 2026-11-14 22:25 — 실행 2 종료, 실데이터 방향 정정 (인도 세금계산서 → CORD v2)
- **8B 교사 초안:** 169장 914초(12 동시, 약 280 tok/s). 그러나 검산 21장 기준 185행 중 40행만 "수량×단가=금액" 통과. 32B 초안 2장과 비교하니 HSN·품명·단가·금액은 대체로 같고, 열 해석(Qty CT/UN 등)과 행 밀림이 다름. GST 계산서마다 열 구성이 달라 단순 산술 검산도 맞지 않음 → **초안을 정답으로 쓸 수 없음.**
- **사용자 지적:** "라벨이 없는 인도 데이터는 결국 사람이 라벨링해야 하지 않나, 그러면 진행할 수 없지 않나" — 맞음. 인도 세금계산서는 정량 평가에서 제외하고, 8B·32B 초안은 내부 참고로만 보관(`artifacts/private_realdocs/`, 저장소 밖 — 실제 상호·계산서 번호 포함. 저장소에는 개수·시간 요약 `reports/runpod2/teacher_drafts_summary.json`만).
- **새 실데이터 트랙: CORD v2**(naver-clova-ix/cord-v2 @7f0115a4, CC BY 4.0, 실사진 영수증 1,000장 = 800/100/100, menu nm·cnt·unitprice·price·subtotal·tax·total 라벨 있음, SKU 없음). 내려받기 약 2.31GB → 사용자 승인 대기.
- **백업·종료:** backup2.tgz SHA256 c3e785bc…, 62개 파일 일치, Pod bf16 LoRA 어댑터 로컬 로드 2/2 동일 → 22:22:58 delete-pod, list-pods 0.
- **소요 시간**(`reports/runpod2/timeline.md`, 총 1시간 33분 20초):

| 구간 | 시간 |
|---|---:|
| 설치·검사 | 5분 |
| vLLM 5회 | 18분 |
| 32B 시도 | 약 15분 (실패 2회 + 2장) |
| P14 학습 + dev44 평가 3종 | 35분 (학습 253초, 평가 583·545·약 330초) |
| 8B 초안 | 17.5분 |
| 백업·삭제 | 2.7분 |

- **비용:** 약 $1.73 추정(1:33:20 × $1.09 + 디스크). 실행 1과 합하면 약 $2.16.
- **사용자 질문 "왜 A40을 안 썼나":** FP8 측정 때문에 Ada(L40S)를 골랐음. A40(Ampere)은 FP8 하드웨어 연산이 없음. 결과적으로 32B는 쓰지 못했고, FP8 외 작업은 A40($0.59)으로도 가능했으므로 약 $0.7을 더 썼다고 보고함.

## 2026-11-14 22:03 — 실행 2: P14 결과, 교사 모델 8B로 변경 (소요 시간 포함)
- 사용자: "걸리는 시간도 잘 기록하도록해" → `scripts/runpod/timeline.py`로 Pod 로그의 단계 타임스탬프에서 시작·종료·소요 시간 표를 만든다(종료 후 `reports/runpod2/timeline.md`).
- **P14 (모두 같은 L40S, HF 기준 경로, batch 1):**
  - 학습: bf16 기본 + 일반 LoRA, 80 step **253.2초**(3.2 s/step), loss 0.278 → 마지막 10 평균 0.0083, peak VRAM 6.98 GB, 641 micro-step 마스크 재검사.
  - 비교: 로컬 4070에서는 같은 학습이 15.8 GB까지 차며 358 s/step이어서 중단. 원인은 조사하지 않음.
  - dev44 평가 소요 시간: M0 bf16 583.4초 · M1 NF4 544.6초 · M1 bf16 LoRA 약 330초.
  - 결과 (공개 dev clean 20 / 자체 trade dev 24):

| 모델 | 공개 dev clean | 자체 trade dev |
|---|---:|---:|
| M0 bf16 | 0.000 (lenient 0.736) | 0.976 |
| M1 NF4 | 0.963 | 0.970 |
| M1 bf16 LoRA | 0.931 | 0.986 |

  - 짝지은 차이(문서 bootstrap 95% CI):
    - bf16 LoRA − QLoRA: 공개 −0.033 [−0.087, 0.017], trade +0.017 [−0.016, 0.057] — 둘 다 유의하지 않음.
    - bf16 LoRA − M0: trade +0.011 [−0.027, 0.059] — 유의하지 않음.
  - 결론: 쉬운 데이터에서는 학습 방식 간 차이를 가를 수 없다(seed 1). 근거 `reports/eval/dev44_l40s_*.json`, `compare_dev44_*.json`.
- **교사 모델:**
  - 32B FP8은 세 번째 시도(경로 수정)에 정상 기동했다(12:57:53 UTC). 그러나 KV 1.35 GiB 때문에 동시 1건, 15 tok/s로 4분에 2장만 처리했다. 169장이면 약 5.6시간이라 컷오프를 넘는다.
  - 13:02:50 UTC에 중단하고 **Qwen3-VL-8B-Instruct bf16**(동시 12건)으로 교체했다.
  - 32B 초안 2장은 `teacher32b_raw_partial.jsonl`로 보관해 8B 품질의 기준으로 쓴다.

## 2026-11-14 21:27 — 실행 2: vLLM 정확도 회복·FP8 결과, 교사 모델 재시도, P14 L40S 학습 중
- **vLLM (L40S, 같은 자체 dev 20건, max_tokens 1536, 원문 저장)** — `reports/runpod2/vllm_run2_*.json`:

| 모델 | 정밀도 | 정확도 | 문서/분 c1 · c4 · c8 · c16 | p50 c1 |
|---|---|---:|---|---:|
| M0 | bf16 | 0.998 | 22.8 · 76.8 · 118.9 · 168.3 | 2.43 s |
| M0 | FP8 | 0.996 | 30.3 · 100.2 · 153.0 · 207.0 | 1.85 s |
| M1 병합(역양자화) | bf16 | **0.960** (HF 0.960과 같음, 합계 20/20) | 32.6 · 107.3 · 168.8 · 238.4 | 1.75 s |
| M1 병합 | FP8 | 0.950 | 42.3 · 140.7 · 219.0 · 295.6 | 1.33 s |

  실행 1의 0.849 → **0.960 회복**(서빙 문제 해결 확인). FP8: 처리량 +23–33 %, 정확도 −0.2 %p(M0) / −1.0 %p(M1). M0 bf16(0.998)이 M1(0.960)보다 높음 → 자체 데이터가 쉬움 + bf16 위 재학습(P14) 필요성 재확인. max-num-seqs 4 결과도 저장됨(배치 제한 비교).
- **교사(Qwen3-VL-32B-Instruct-FP8 @4bf2c2f3) 시작 실패 2회:** ① 가중치 33.5 GiB + 3.2 MP 이미지 프로파일링 후 KV 0.47 GiB, ② FP8 KV 캐시 JIT에 필요한 `ninja`가 PATH에 없음. 수정(이미지 2.36 MP, max-model-len 8192, KV fp8, util 0.97, PATH에 venv bin) 후 P14 뒤에 재시도 대기.
- 원격 정리 명령 `pkill -f "vllm serve"`가 자기 SSH 세션까지 끝내는 실수 2회 → `[v]llm` 패턴으로 수정.
- **P14 (L40S):** 공개 학습 이미지 200장을 샤드에서 새로 추출하느라 시작이 늦었고(약 5분), bf16 LoRA 학습은 3.2 s/step(로컬 4070은 358 s/step). 이어서 같은 L40S에서 dev44 평가 3종.

## 2026-11-14 21:02 — RunPod 실행 2 진행 중 (L40S), GPU 간 병합본 차이 측정, P14를 Pod로 이동
- 사용자 "승인"(20:45). Pod `t5c8go2mwmeh8u` L40S 48GB · Secure EUR-IS-2 · $1.09/h · 20:49:38 생성 · 컷오프 23:19(알림 23:07). 호스트 키 일치, 1 MiB 왕복·번들 203MB SHA256 일치, 터널 OK(공인 IP 차단). 설치 4분, 2B 모델 해시 일치.
- 실행 순서(`scripts/runpod/pod_run2.sh`): Pod에서 병합 → vLLM 5회(M0 bf16, M1 병합 bf16, M1 병합 FP8, M0 FP8, M1 bf16 max-num-seqs 4) → 32B FP8 교사 라벨 초안. 이어서 `pod_p14.sh`.
- **GPU 간 병합본 차이:** Pod(L40S)에서 같은 스크립트로 만든 병합본 SHA256 e227b3f7… ≠ 로컬(4070) 46cfdc9f…. 텐서 625개 중 59개 다름(LoRA 대상 q/v뿐 아니라 down/gate/k/o/up도 → bitsandbytes NF4 양자화 단계부터 GPU마다 비트가 다름). 직접 비교: layer0 v_proj 2,097,152개 중 13개, down_proj 12,582,912개 중 2개, 최대 차이 bf16 1칸(4.9e-4 / 1.2e-4). 원칙: 모델 파일은 한 곳에서 한 번 만들고 해시로 옮긴다. 근거 `reports/runpod2/merge_tensor_diff.json`, `*_merged_tensors.json`.
- **P8a 비병합도 0.960(501/522)** — 병합과 같음(17.5 s/문서, 병합 11.3).
- **P14 로컬 중단:** 4070 16GB에서 bf16 LoRA가 15.8GB를 써서 공유 메모리로 넘쳐 358 s/step(80 step ≈ 8시간). 프로세스 6개 PID로 종료. P14는 같은 L40S에서 학습 + dev44 평가 3종(M0 bf16, M1 NF4, M1 bf16 LoRA)으로 옮김 — 비교가 한 GPU 안에서 끝남. 승인 상한(2.5h·$3.00) 안.

## 2026-11-14 20:40 — 사용자 지시 반영: 2B로 완수, 수집한 것부터, RunPod 병행, 정밀도·어댑터 짝 주의
- 사용자: "굳이 많은 데이터를 공수 할 필요 없어 게다가 2로 완수 하고 싶어, 지금 수집한것 부터 먼저 더해서 시도해볼수 있도록해 runpod도 같이 활용할수 있도록해 4070과 a40의 정밀도 차이 조심하도록해", "어댑터 유무와 정밀도마다 같은 어댑터 쓰면 성능 낮아지는것도 주의하도록해". 해석: Qwen3-VL-2B 유지, 조사한 공개 데이터부터 추가, RunPod 병행(견적 승인은 유지), 비교는 같은 GPU·같은 정밀도, 어댑터는 학습한 기본 모델 정밀도와 짝.
- **P8a 성공:** NF4 역양자화 bf16 + 병합 LoRA = **0.960 (501/522)**, 합계 20/20, 평균 토큰 267.6 — NF4 경로와 동일, 11.3 s/문서(NF4 13.5). vLLM에 LoRA 없이 올릴 수 있는 bf16 체크포인트(`models/merged/m1_v1_nf4deq_bf16`, git 제외).
- **P15 완료:** `vlm/pairing.py` + `tests/test_pairing.py`(7개). `infer.py`는 짝이 안 맞으면 거부(`--allow-precision-mismatch`로만 허용, 지문에 기록), `hf_server.py`는 NF4 기본 모델과 짝 검사. 실제로 m1_standard_v1 + bf16은 거부, + 역양자화 기본 모델은 통과 확인.
- **Kaggle 내려받기:** `data/raw/kaggle_indian_grocery_invoices/` (zip 669,947,762 B, SHA256 d8a8522…7e3e → d9a85225…267e3e). 사진 169장(3060×4080), CSV는 file_name·label·country·document_type뿐(품목 라벨 없음). 내용: 인도 도매 GST 세금계산서, 15–36행 표(HSN 코드·수량·단위·단가·세율·금액), 구김·손글씨·여러 쪽. **실제 상호·주소·GSTIN·서명 포함 → 이미지·개인정보는 저장소에 넣지 않음.**
- **RunPod 실행 2 제안** (`reports/RUNPOD_APPROVAL.md`): L40S 48GB $1.09/h(Low), 상한 2.5h·$3.00 — vLLM 병합본 정확도 회복, FP8 대 bf16, 32B FP8 교사로 실문서 라벨 초안. 승인 대기.

## 2026-11-14 20:50 — 두 방향 자문 합의, 계획 단계 2 추가, P6 중단 사고 정리
- **Fable 방향 자문** (`reports/reviews/fable-direction-1.md`): 어려운 합성 데이터(B) 주축 + CORD·실문서 40장 평가 보강, C·AI Hub 제외, DocILE 신청만. P14 주력 승격, 쉬운 데이터 P6 보류. 난이도 게이트(M0 bf16 0.55–0.80), 판정 +0.05 · CI 하한 > 0 · seed 3 동일 방향.
- **astra 방향 자문** (`reports/reviews/astra-direction-1.md`, 같은 세션 재사용, 117초): B를 좁게(7–12행, 여러 줄 품명, 포장 단위 수량, 한영 혼합 헤더, 읽을 수 있는 촬영 왜곡) + 실문서는 Kaggle 인도 세금계산서(개발 20, 봉인 60–100). 15–40행·다페이지·유럽식 숫자·3자 대사는 다음 단계(대사 최대 12행, 출력 1,536토큰 한계). 판정 +3%p · CI 하한 > 0, seed 3. P8a·P14 유지, P6은 새 데이터로 이동.
- **결정:** 두 의견의 공통안으로 `plan.md` 단계 2(Q1–Q7) 작성. 쉬운 데이터 P6 중단.
- **사고:** 백그라운드 큐를 TaskStop으로 멈췄지만 Git Bash 자식 프로세스가 살아남아, 19:18에 띄웠던 첫 P6 대기 스크립트와 두 번째 큐가 둘 다 20:24에 `m1_seed_20261114` 학습을 **같은 출력 폴더로 동시에** 시작했음. 20:40 발견, PID로 bash·python 10개 종료, nvidia-smi로 GPU 비었음 확인. 어댑터는 저장 전이라 없음, trainer 폴더는 `artifacts/aborted/`로 이동. P3(20:23 완료)와 P8a 1차 시도에는 영향 없음. 메모리에 재발 방지 절차 기록.
- **재시작:** `scripts/quant/run_p8a_p14.sh`(대기 없이 P8a → P14 → dev44 평가) 20:4x 시작.
- **사용자 결정 필요:** Q4 Kaggle 데이터 내려받기(약 670MB, CC BY 4.0) 승인과 라벨 검수 방식.

## 2026-11-14 20:35 — P3 완료, P8a 실패·수정, 데이터셋 조사, 방향 자문 의뢰
- **P3 완료** (`reports/quant/precision_dev20.{json,md}`, 같은 자체 dev 20건, HF 기준 경로):
  - M1: nf4 0.960 · int8 0.847 · bf16 0.847 · fp16 0.849 · fp32 0.849 (NF4 외 모두 합계 필드 1/20) — 원인 = 학습 기본 모델 불일치.
  - M0: nf4 0.941 · int8 0.992 · bf16 0.994 · fp16 0.966 · fp32 0.969 (n=20, fp16/fp32가 bf16보다 낮은 것은 그리디 출력 차이로 보이며 표본이 작음). int8은 문서당 43–69초로 느림.
- **P8a 1차 실패**: 저장 시 "Object of type dtype is not JSON serializable"(bitsandbytes가 남긴 `_pre_quantization_dtype`). `merge_dequantized.clean_config` 추가, GPU 없이 재현→해결 확인. GPU가 P6 학습 중이라 `scripts/quant/run_after_p6.sh`로 P6 뒤에 P8a 재시도 → P14(bf16 일반 LoRA, `train.py --base-precision bf16`, `attach_lora(quantized=False)`) → dev44 평가(m1_bf16lora, m0 bf16).
- **P6 진행**: 20:24 seed 20261114 학습 시작.
- **데이터셋 조사**(웹 하위 에이전트 + Kaggle API): `reports/research/datasets-2026-11-14.md`. 후보: DocILE(실제 B2B 인보이스, 라인아이템, 요청·연구용), CORD v2(실사진 영수증, CC BY 4.0), Kaggle 인도 식료품 세금계산서 169장(실사진, CC BY 4.0, 라벨 없음), AI Hub 71301(상업송장·포장명세서·B/L, 라벨 없음, 내국인·공유 금지).
- **방향 자문 의뢰**: `reports/reviews/briefs/direction-1-brief.md`를 Fable(하위 에이전트)과 astra(같은 세션 재사용)에게 독립 의뢰.

## 2026-11-14 20:00 — 방향 전환 논의: 난이도 상향
- 사용자 질문 "각 어댑터에 맞게 만들어야 하나" → 예: 어댑터는 학습한 기본 모델과 짝. plan P15(어댑터-기본 모델 짝 검사) 추가.
- "한 단계 낮은 Qwen" → Hugging Face 조회 결과 Qwen3-VL-2B가 Qwen3-VL 중 최소(2B·4B·8B·30B-A3B·32B·235B), 공식 `Qwen3-VL-2B-Instruct-FP8` 존재(P8b에 활용 가능). 사용자: 이전 세대 비교는 불필요.
- 사용자: "어려운 난이도의 데이터를 만들거나 다른 데이터셋을 찾거나 프로젝트를 바꿔서 난이도를 올리는 방향성이 맞는것같아". 진행: 웹 데이터셋 조사(하위 에이전트, 실제 스캔·품목 행 라벨·라이선스 확인) → Fable·astra 방향 자문 → 선택지 정리 → 사용자 결정. 로컬 GPU 실험(P3→P8a→P6)은 계속.

## 2026-11-14 19:51 — P3 중간 표 (6/8 완료)
- 같은 자체 dev 20건, HF 기준 경로: m1 nf4 0.960 · bf16 0.847 · fp16 0.849 · fp32 0.849 · int8 0.847(42.9 s/문서로 느림) → **양자화하지 않았든 int8이든 NF4가 아닌 기본 모델이면 모두 같은 저하.**
- **m0 bf16 0.994 (519/522)** — 같은 문서에서 m0 nf4 0.941보다 높음. 기본 모델 자체는 4비트 양자화로 약 5포인트를 잃고 있었다는 뜻(자체 dev, exploratory). P14(bf16 위 일반 LoRA)의 근거가 강해짐.
- 남은 P3: m0 int8 · fp16 · fp32 (약 25분) → 이어서 P8a → P6 → P14.
- 사용자 질문 "bf16으로 낮추면 성능이 떨어지지 않나 / GPU를 바꾸는 게 맞지 않나 / fp32가 가장 정밀한데 왜 NF4가 높나"에 답함: NF4가 가장 낮은 정밀도이고, 원인은 학습 기준 가중치 불일치라 GPU·dtype을 바꿔도 해결되지 않음. GPU는 속도와 FP8 지원(Ada/Hopper) 때문에 고른다.

## 2026-11-14 19:45 — P12 서빙 회귀 테스트, P3 fp32 결과
- P3: m1 fp32 기본 모델 0.849(443/522), 합계 필드 1/20, 토큰 20/20 vLLM과 일치 — bf16(0.847)과 같음. **dtype(bf16·fp32)은 원인이 아니고 "양자화된 가중치에서 학습한 어댑터를 양자화하지 않은 가중치에 붙인 것"이 원인.** 사용자가 제기한 A40·dtype 가설은 기각.
- P12: `serving/core.py`(torch 없는 대기열·데드라인·HTTP)로 분리, `hf_server.py`는 GPU 생성만. `tests/test_serving_core.py` 6개(정상 응답, 데드라인 취소 후 워커 해제·생성 중단, 대기열 포화 429와 회복, 대기열 안 만료 504, 백엔드 오류 500 후 회복, 입력 검증) 통과, 전체 테스트 통과. 테스트용 생성기는 테스트 파일 안에만 있음. **남은 확인:** 리팩터링한 실제 GPU 서버를 한 번 띄워 요청 1건(GPU가 빌 때).
- P11은 이전 시도(aug1, 음성 결과)가 있어 설계를 Fable·astra에게 자문한 뒤 진행. P13(T07 한영 혼합)은 로컬 한글 글꼴(맑은 고딕·Noto Sans KR, 저장소에 넣지 않음)로 렌더러에 추가 예정.

## 2026-11-14 19:40 — astra 평가 1: 76점
- `reports/reviews/astra-1.md` (Codex gpt-6-astra, 같은 세션 재의뢰, 376초). 시도 1은 파일을 못 읽어 무효(`astra-1-attempt1-noread.md`).
- 점수 76/100: LoRA/SFT 17/20, 추출 정확도 11/15, 서빙 14/20, 자동 채점·회귀 14/15, 실패 분석 7/10, Linux·GPU 운영 7/8, OCR·표·무역 4/5, 양자화·비용 2/4, 멀티 GPU·한영 0/2, Java 0/1.
- 치명 공백 없음(면접 대상). 다만 vLLM 품질 저하와 원문 미보존은 서빙 담당 채용이면 탈락 사유가 될 수 있음.
- README 부정확 3곳(기록·코드로 직접 확인 후 수정함): ① vLLM에서 "모든 문서가 정확히 4필드" → 실제 17/20이 4필드, 나머지 6·5·0 ② 검수 API "(version, run_id, state) 재확인" → 코드는 시작 때 버전, 완료 때 state·active_run_id(`app/api.py:246`) ③ "배칭 없음"은 직접 만든 HF 서버에 한정. RUNPOD_RUN.md도 같이 바로잡음.
- 90점까지 약 +14: P3→P8 서빙 품질 회복(+4–5), 양자화 비교(+2), seed·ablation(+2), **모호수량·누락 행 개선을 새로 고정한 검증셋에서 확인(+3)**, **서빙 취소·포화·실패 회귀 테스트, 한영 혼합·다페이지 합성(+2–3)**.
- 계획 자문: P8은 조건부가 아니라 최종 서빙 경로 확인에 필요. P9는 점수 반복보다 사전 완료 기준으로 재평가. 기존 FINAL은 유지하고 새 검증셋을 따로 고정. E2는 vision·lm_head dtype도 함께 바뀜(순수 언어부 비교 아님), Conv3d는 모든 조건에서 fp32라는 점을 결과에 명시할 것. "단순 bf16 병합도 보장 없음 — W_bf16+Δ ≠ dequant(W_nf4)+Δ" → P8a가 바로 dequant(W_nf4)+Δ 방식.

## 2026-11-14 19:25 — P3 핵심 결론: 원인은 정밀도 불일치 (A40·vLLM 아님)
- 로컬 RTX 4070 Ti SUPER, HF 기준 경로, 기본 모델만 bf16(양자화 없음) + 같은 어댑터 v1, vLLM 벤치와 같은 자체 dev 20건: **필드 정확도 0.847 (442/522)** — A40 vLLM 0.849와 거의 같음. 문서별 생성 토큰이 vLLM과 20/20 ±1 일치, 합계 4필드가 남은 문서 1/20. NF4 경로는 0.960(501/522), 20/20.
- 결론: H1 확정 — NF4 기본 모델에서 학습한 QLoRA 어댑터를 bf16 기본 모델에 붙이면 생기는 문제이며, 하드웨어(A40)·OS·vLLM과 무관. 근거 `reports/quant/precision_dev20.json`(전체 표는 P3 완료 후 갱신).
- 사용자: "성능문제 때문에 필요시 a40아닌 다른것 대여해도 괜찮아" → plan P8을 P8a(로컬: 역양자화 bf16 + 병합/비병합 LoRA로 정확도 회복 확인)와 P8b(유료: vLLM에서 회복 확인 + FP8 양자화 + 배치 튜닝, Ada/Hopper GPU 후보, 견적·승인 필요)로 나눔.
- 대기열 재구성: P3 → P8a(`scripts/quant/run_p8a_then_p6.sh`) → P6. `infer.py`에 `--model-dir`, `--arm m1merged` 추가, final 세트는 nf4 m0/m1만 허용하도록 막음. `scripts/quant/merge_dequantized.py`(병합 / `--no-merge`).

## 2026-11-14 19:20 — P2 완료, P3·P4·P6 진행 중
- P2 완료: README(영·한) — 선형 증가 표현을 실측 배율(6.1×·5.8×, p50 +17–26 %)로, parity 7/8(로컬 어댑터를 Pod에서) 추가, TRL `SFTTrainer` 사용 범위를 정확히 기술(학습 루프만, 데이터 준비·assistant-only loss는 우회), 비용을 "추정 $0.43"으로 표기. TASK_BOARD T09 행을 RunPod 정리 결과로 수정. 청구 기록은 아직 일부만 반영(billing API $0.135, 콘솔 잔액 차감 $0.25) → P10에서 확정값으로 교체.
- P7 완료(앞당김): `src/invoiceguard/readme_tables.py`가 final JSON에서 필드별 정확도 표를 만들어 README 두 판의 표시 사이에 넣음, 테스트로 일치 확인. B0의 자체 test 품목 필드 0/170은 열 병합 때문(예측 1건 대조로 확인)이라 주석에 적음.
- P3 진행: `infer.py --precision {nf4,int8,bf16,fp16,fp32}`와 `model.load_base(precision=)` 추가(nf4 지문은 동결값과 같음). `scripts/quant/run_precision_dev20.sh`가 8회 실행 중(19:14 시작). **중간 관찰:** HF bf16 기본 모델 + 어댑터 v1의 문서별 생성 토큰이 A40 vLLM과 ±1로 같음(269/270, 213/214 …), NF4 경로는 312·255 … → 정밀도 불일치(H1)가 유력. 20건 완료 후 확정.
- P4: `scripts/review/consult_astra.py` 작성(Codex `gpt-6-astra`, 읽기 전용 샌드박스, 웹·네트워크 끔). 1차 시도는 `code_mode_host`를 꺼서 파일을 못 읽음 → 해당 기능만 켜고 같은 세션으로 재의뢰(`reports/reviews/astra-1-attempt1-noread.md` 보존). 시도 1에서도 아스트라는 "HF 안 정밀도 비교 → 같은 정밀도 HF↔vLLM → 원문 보존" 순서를 권함.
- P6 대기열: `train.py --seed --data {all,public_only}` 추가(기본값은 동결 설정 그대로). `scripts/train_variance/run_p6.sh`가 P3 종료를 기다렸다가 seed 20261114·20261115, public_only 학습과 dev 44문서 평가를 이어서 실행.

## 2026-11-14 19:10 — 90점 계획 시작
- 사용자 지시: "고칠곳 고치고 아스트라한테도 자문 및 평가 받고 단계별로 차근차근 plan을 세워서 모든 작업을 끝낼수 있도록해", "a40 특성상 … bf16 fp16 fp32 혹은 환경이 다름으로써 생기는걸수도 있으니 확인하고 우선 fable과 astra한테 반복적으로 평가받고 각각 90점 이상".
- 한 일: `plan.md`(P1–P10)와 이 파일을 OKF 형식(YAML 머리말 `type`·`title`·`description`·`tags`·`generated`·`sources`)으로 만듦.
- 아스트라 = Codex CLI 0.154.0의 `gpt-6-astra` 모델(enveda 프로젝트의 `consult_astra.py` 방식). 이 저장소에서는 읽기 전용 샌드박스로 호출한다.
- 다음: P2(불일치 5곳) → P3(로컬 정밀도 실험) → P4(astra 평가 1).

## 2026-11-14 19:00 — Fable 평가 1: 70점
- 방법: Fable 하위 에이전트에 저장소와 공고만 주고 독립 채점(이전 66점은 클라우드 제외라 참고만).
- 점수 69.2 ≈ 70. 큰 감점: 서빙(13/20, vLLM에서 M1 정확도 저하 원인 미확정), 양자화 우대(1.2/4, 비교 없음), LoRA/SFT(16/20, 80 step·seed 1개·ablation 없음), 추출 정확도(8.4/12, 자체 test M1−M0 유의하지 않음).
- 치명 공백: 없음. 단 "파인튜닝 어댑터를 서빙 프레임워크에 올리면 품질이 깨짐, 원인 모름"은 면접 첫 질문 수준.
- README 지적 5곳(직접 확인함): "almost linearly"(실제 8배 동시성에 6.1·5.8배), parity 7/8 누락, TRL `SFTTrainer` 표현 과장, 비용 배지가 확정값처럼 보임, TASK_BOARD T09 행 모순.
- 권고: vLLM 원인 규명(+4–5), 양자화 비교(+3), seed·ablation(+3), 필드별 표(+1–2), 한영 혼합·서빙 테스트(+2).

## 2026-11-14 17:50–18:58 — RunPod 재현 (세션 2)
- 승인: 사용자 "A40로 승인" (상한 5h · $3.50). Pod `jwvf173fyus06x`, A40 Secure CA-MTL-1, 17:59:55–18:43:19, 시간당 $0.60, 약 $0.43(계산값; 콘솔 반영 $0.25).
- 결과: 마스크 360/360, 입력 해시 전부 일치, smoke pass, 80 step 재학습이 사전 고정 기준 5개 통과(step별 최대 |Δ| 0.002), dev parity(Pod 학습 어댑터 원문 8/8 동일, 로컬 어댑터 Pod 실행 7/8 — 키 순서), 백업 32파일 SHA256, 로컬 복원 2/2 동일, Pod 삭제 확인.
- vLLM 0.11.2: M1 분당 24.3(동시성 1)–149.3(동시성 8), 실패 0. M1 정확도 0.849 vs HF 0.960 — 원인 미확정. 벤치가 원문을 저장하지 않았음(이후 수정).
- 기록: `reports/runpod/RUNPOD_RUN.md`, `reports/RUNPOD_APPROVAL.md`, README 12장. 커밋 c003a03, push 완료, CI 통과.
- 문제와 처리: Pod 안 runpodctl Unauthorized → 자동 정지 불가(감시로 대체). 프로젝트 설정의 ssh/scp ask 규칙이 확인창을 띄움 → 사용자 지시로 삭제. README 5장 다이어그램을 정규식 실수로 덮어씀 → git 원본으로 복원.

## 2026-11-14 (세션 1 후반) — 공개·README·대시보드
- 대시보드 UI 개편(기본 다크, favicon), README 영어 기본 + 한국어판, 데이터 종류별 샘플, 평가 세트 7개 설명, 차트 라이트/다크 대응.
- 커밋 작성자 이메일을 noreply로 재작성 후 저장소를 공개로 다시 만듦(`reports/HISTORY_REWRITE.md`). 프로필 README에 프로젝트 추가.
- Fable 완성도 검토(클라우드 제외) 약 66%. README의 M0 원인 설명 오류를 고쳐 기록.

## 2026-11-13–14 (세션 1) — 구현 T00–T09
- 데이터: 공개 InvoiceOCR-Synth(PUBLIC_CANONICAL, rev 673ff85b) 누수 없는 분할, 자체 Invoice–PO 합성(TRADE_RAW, 레이아웃 6종, 시나리오 7종), stress(dev 전용).
- 모델: Qwen3-VL-2B @89644892 NF4 + LoRA r8 q/v, TRL SFTTrainer 하위 클래스 + 검증 collator, 80 step. B0(Tesseract + 규칙), M0, M1을 같은 문서로 비교, final 1회(동결 후).
- 서빙: 직접 만든 HF+PEFT 서버(타임아웃 취소, bounded queue). vLLM은 로컬 드라이버(CUDA 12.6)로 blocked.
- 검수 API: 버전 CAS, 승인 스냅샷, 늦은 응답 차단. 검수 화면 UI는 미구현.
- 상세: `reports/IMPLEMENTATION_STATUS.md`.
