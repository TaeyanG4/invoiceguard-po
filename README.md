# InvoiceGuard-PO
**영어 인보이스 이미지 → VLM 추출(Qwen3-VL-2B + QLoRA) → 독립 발주서(PO) 대조 → 사람 검수·승인 → 승인 버전만 export**

2일 MVP 포트폴리오입니다. 데이터는 **모두 합성**(공개 InvoiceOCR-Synth + 자체 생성 Invoice–PO)이며, 실제 기업·통관 문서 성능을 주장하지 않습니다. 모든 수치는 이 저장소의 스크립트로 재현되는 실측값이고, 실행하지 않은 항목은 `not_run`/`blocked`로 남겼습니다.

## 결과 한눈에 (final — 설정 동결 후 1회 평가)
로컬 RTX 4070 Ti SUPER, HF Transformers NF4(비전 비양자화), greedy, batch 1. 값 = strict 필드 정확도 [95% bootstrap CI, base/family 단위]. 전체 표: [`reports/eval/final_summary.md`](reports/eval/final_summary.md)

| 세트 (n) | B0 OCR+규칙 (Tesseract) | M0 Qwen3-VL-2B (기본) | **M1 QLoRA** |
|---|---|---|---|
| 자체 test, 처음 보는 레이아웃 T05/T06 (40) | 0.210 [0.19–0.23] | 0.897 [0.85–0.94] | **0.921** [0.87–0.96] |
| 공개 IID clean (20) | 0.731 [0.46–0.99] | 0.000 (펜스, lenient 0.817) | **0.880** [0.78–0.96] |
| 공개 IID bad_scan (20) | 0.346 [0.15–0.56] | 0.000 (lenient 0.466) | **0.798** [0.63–0.92] |
| 공개 OOD 양식 freelancer clean (20) | 0.000 | 0.000 (lenient 0.555) | **0.973** [0.94–0.99] |
| 공개 OOD bad_scan (20) | 0.000 | 0.000 (lenient 0.058) | **0.756** [0.62–0.88] |

**읽는 법 — 정직한 결론**
1. **깨끗한 문서는 OCR+규칙으로도 충분**: dev와 final 모두 clean에서 M1−B0 차이가 유의하지 않습니다(예: dev 공개 clean 0.000 [−0.06, 0.06]).
2. **OCR 규칙은 처음 보는 레이아웃·열화에서 무너지고, 파인튜닝한 VLM은 버팁니다**: 자체 test M1−B0 **+0.711 [0.67, 0.75]**, dev 열화 3종 +0.71~+0.81.
3. **파인튜닝 이득의 상당 부분은 "출력 형식"**: M0는 공개 문서에서 100% ```json 펜스를 붙여 strict 0점(펜스만 벗기면 0.82). 자체 test에서 M1−M0 = +0.024 [−0.001, 0.050]로 **유의하지 않음**.
4. **남은 위험**: M1도 좁은 열에 줄바꿈된 모호수량("2 cartons / 100 pcs")을 숫자로 바꿉니다(test AMBIGUOUS_QUANTITY 리콜 0/2). 그래서 제품은 모든 문서를 사람 검수로 보내고, 수량×단가≠금액 산술 경고가 안전망입니다. dev 기반 개선 시도(학습 데이터 보강)는 효과가 없었고 그대로 기록했습니다.

## 공고 직무 ↔ 증거
| 직무/자격 | 이 저장소의 증거 |
|---|---|
| LoRA/QLoRA/SFT, HF transformers·peft·**trl** | [`vlm/train.py`](src/invoiceguard/vlm/train.py) TRL `SFTTrainer` + 검증 collator, NF4 + LoRA r8 (언어 q/v만, 학습 파라미터 0.11%), [`reports/model/train_m1_standard_v1.json`](reports/model/train_m1_standard_v1.json) |
| 학습 정확성 검증 | 확장 이미지 토큰 기준 loss mask 감사 360/360, 10-step smoke(유한 gradient·112/112 텐서 변경·재로드 일치) [`reports/model/`](reports/model) |
| 추출 정확도·실패 분석·개선 | 세트별 평가기·paired bootstrap [`evaluation.py`](src/invoiceguard/evaluation.py), [`compare_runs.py`](src/invoiceguard/compare_runs.py), 실패 분류 [`reports/eval/failures_m1_dev_v1.md`](reports/eval/failures_m1_dev_v1.md), 개선 1건과 **음성 결과** [`reports/eval/dev_summary.md`](reports/eval/dev_summary.md) |
| 자동 채점·회귀 테스트 | pytest 150+개(규칙 B01–B12, 평가 E01–E05, API A01–A08), [GitHub Actions CI](.github/workflows/ci.yml), 동결·해시 가드 [`freeze.py`](src/invoiceguard/freeze.py) |
| 서빙·성능 측정 | Transformers+PEFT GPU 서버 [`serving/hf_server.py`](src/invoiceguard/serving/hf_server.py) — 실제 타임아웃 취소·bounded queue 실측 [`reports/serving/`](reports/serving). vLLM은 드라이버 제약으로 **blocked**(아래) |
| OCR/문서 AI(우대) | Tesseract 기준선 B0 (train/dev만 보고 만든 일반 규칙, Docker 격리) [`ocr_baseline.py`](src/invoiceguard/ocr_baseline.py) |
| 표 구조 문서·도메인 | 구조가 다른 6개 인보이스 레이아웃 렌더러, PO 대사 규칙(단가/수량 차이·미등록 품번·중복·모호수량) [`reconciliation.py`](src/invoiceguard/reconciliation.py) |
| 서비스 연동 | 검수 API(FastAPI+SQLite): 추출 CAS, 늦은 응답 덮어쓰기 방지, 승인 스냅샷 export [`app/api.py`](src/invoiceguard/app/api.py) |

## 구성
```
이미지 ─▶ [VLM 추출 TRADE_RAW] ─▶ 원문 응답 저장 ─▶ strict JSON 파싱 ─▶ 정규화(Decimal) ─▶ PO 대사 규칙 ─▶ 검수·수정 ─▶ 승인 스냅샷 ─▶ JSON/CSV
             ▲ 입력은 (고정 프롬프트, 이미지)뿐 — PO·정답·파일명은 모델에 들어가지 않음
```
- 모델: `Qwen/Qwen3-VL-2B-Instruct` @ `89644892`, M1 어댑터 SHA256 `eb086741…`.
- LLM은 VLM 내부 언어모델뿐이며, 대사·승인은 결정적 규칙입니다(챗봇·RAG 없음).

## 데이터와 누수 방지
- 공개 [InvoiceOCR-Synth](https://huggingface.co/datasets/alamgirqazi/invoice-ocr-synthetic) rev `673ff85b`(CC BY 4.0, 합성 영어): 2,814장 전수 디코드, 렌더러 소스로 필드 가시성 판정(미인쇄 단가·대문자 변환·28자 절단은 채점 제외), SKU 정답 없음 → 공개는 숫자값 canonical 평가만. [`reports/data/`](reports/data)
- 분할: 파일명·업무내용·추출대상·이미지 해시를 union-find로 묶은 그룹 단위, freelancer 양식은 OOD 전용. [`manifests/`](manifests)
- 자체 Invoice–PO: PO를 먼저 만들고 시나리오별로 값을 유지/변경해 렌더, 정답 문자열만 그림(렌더=정답·겹침·열 침범 검사). train T01–T03 / dev T04 / test T05–T06 레이아웃 holdout. dev 전용 열화 stress 72장.

## 실험 설계 (공정성)
- M0/M1/B0는 같은 문서·분모·채점기. M0/M1은 같은 NF4 로딩·프롬프트·전처리·generation·batch 1([`configs/frozen_v1.json`](configs/frozen_v1.json)).
- final은 코드·어댑터·OCR 이미지·manifest 해시를 동결한 뒤 1회만 실행([`configs/frozen_v1_appendix.json`](configs/frozen_v1_appendix.json)); 누락은 실패로 분모에 포함.
- 의사결정 기록: 방향·검토는 Fable, 구현은 Opus([`docs/19_DECISIONS_V5.md`](docs/19_DECISIONS_V5.md)). 중간 검토가 찾은 B0의 held-out 어휘 오염 등은 수정·공개했습니다([`reports/IMPLEMENTATION_STATUS.md`](reports/IMPLEMENTATION_STATUS.md)).

## 서빙 실측 (로컬 GPU)
**Transformers+PEFT GPU 서버** ([`serving/hf_server.py`](src/invoiceguard/serving/hf_server.py), OpenAI 호환 subset, 127.0.0.1 전용, 작업자 1 + 대기열 2)

| 측정 | 결과 (자체 dev 10장, warmup 3) |
|---|---|
| 서버 출력 = 오프라인 평가 출력 | M0·M1 모두 원문 100% 동일, 같은 프롬프트 토큰(1045) |
| 처리량 (M1) | 동시성 1: 4.0 docs/min, p50 16.1s / p95 18.4s · 동시성 2: 4.2 docs/min, p50 26.6s / p95 36.3s (직렬 작업자 → 대기 시간 증가, 배치 효과 아님) |
| 동시성 4 | 10건 중 7건 **429** (bounded queue 설계대로) |
| 실제 타임아웃 취소 | 3초 제한 요청 → 3.1초에 504, 직후 작업자 `busy:false` (StoppingCriteria로 생성 중단, 고아 추론 없음) |
| GPU 메모리 | 약 3.1GB (nvidia-smi, 다른 프로세스 포함) |
| LIVE 종단 시연 | 검수 API(LIVE_MODEL) → 추출 15.2s, `UNIT_PRICE_DIFF` 검출, 정답 행과 일치 → 승인 → 스냅샷 export ([`reports/serving/live_e2e_demo.json`](reports/serving/live_e2e_demo.json)) |

**vLLM: blocked** — `vllm/vllm-openai:v0.11.2`(Qwen3-VL 지원 버전)는 CUDA ≥ 12.9를 요구하고, 로컬 드라이버 561.17은 CUDA 12.6까지입니다. 요구 조건 검사를 끄고 시도해도 컨테이너 안 PyTorch가 "No CUDA GPUs are available"로 실패했습니다. 드라이버 업데이트(사용자 작업) 또는 RunPod(승인 필요)에서 측정 예정이며, 측정 전에는 vLLM 속도·양자화 정확도를 주장하지 않습니다. 벤치 스크립트: [`serving/vllm_bench.py`](src/invoiceguard/serving/vllm_bench.py).

추가 발견: 이 Windows 스택에서 비전 patch-embedding Conv3d(bf16)가 문서당 18.4초를 차지해, 그 층만 fp32로 계산하도록 바꿔 추론이 2.5–3배 빨라졌습니다(전 arm 동일 적용).

## 비용
클라우드 지출 **$0** (RunPod 미사용, 승인 대기 — [`reports/RUNPOD_APPROVAL.md`](reports/RUNPOD_APPROVAL.md)). 학습 1회 약 22분, final 3-arm 추론 약 50분(로컬 GPU).

## 한계
합성 데이터만 사용 / 표본이 작음(공개 세트당 20 base, 자체 test 40) / 열화 stress는 dev 전용 / M0의 낮은 strict 점수는 형식 효과가 큼 / vLLM·클라우드 비용·멀티 GPU는 미실행 / 모호수량 실패는 해결되지 않음.

## 재현
```bash
uv venv --python 3.11 .venv && uv pip install --python .venv/Scripts/python.exe -e ".[dev,app]"
.venv/Scripts/python.exe -m pytest tests/
.venv/Scripts/python.exe -m invoiceguard.public_profile && .venv/Scripts/python.exe -m invoiceguard.public_manifest
.venv/Scripts/python.exe -m invoiceguard.synth.build
# 모델 환경(.venv-ml: torch 2.9.1+cu126, transformers 4.57.6, peft 0.17.1, trl 0.25.1, bitsandbytes 0.48.2)
.venv-ml/Scripts/python.exe -m invoiceguard.vlm.train --profile standard --run-id m1_standard_v1
.venv-ml/Scripts/python.exe -m invoiceguard.vlm.infer --arm m1 --adapter artifacts/adapters/m1_standard_v1 --set trade:dev --run-id m1_dev
.venv/Scripts/python.exe -m invoiceguard.score_run artifacts/predictions/m1_dev
.venv/Scripts/python.exe -m invoiceguard.dashboard_server --port 8765   # 관리자 대시보드 (127.0.0.1)
```
원래 패키지 안내(Claude Code 시작 방법·설계 문서 목록)는 [`docs/PACKAGE_README_v4.md`](docs/PACKAGE_README_v4.md)에 있습니다.
