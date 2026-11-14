# InvoiceGuard-PO

[English](README.md) · **한국어**

**영어 인보이스 이미지에서 품목을 VLM으로 추출하고, 독립 발주서(PO)와 대사한 뒤, 사람이 승인한 버전만 내보내는 시스템**

[![ci](https://github.com/TaeyanG4/invoiceguard-po/actions/workflows/ci.yml/badge.svg)](https://github.com/TaeyanG4/invoiceguard-po/actions/workflows/ci.yml)
![data](https://img.shields.io/badge/data-synthetic%20only-lightgrey)
![gpu](https://img.shields.io/badge/GPU-local%20RTX%204070%20Ti%20SUPER-informational)
![cloud](https://img.shields.io/badge/cloud%20spend-%240-success)

- **모델:** Qwen3-VL-2B-Instruct(NF4) + QLoRA 어댑터 — 로컬 GPU 1장에서 학습·평가·서빙
- **데이터:** 모두 합성입니다. 공개 InvoiceOCR-Synth와 자체 생성 Invoice–PO를 쓰며, 실제 기업·통관 문서 성능은 주장하지 않습니다.
- **재현성:** 평가 수치(학습 · dev · final · paired CI)는 이 저장소의 스크립트로 재현됩니다.
- **정직성:** 실행하지 않은 항목은 `not_run` / `blocked`로 남겼습니다.

![관리자 대시보드 — 개요](docs/images/dashboard-overview.png)

<sub>로컬 관리자 대시보드(읽기 전용, 127.0.0.1)의 개요 화면입니다. 모든 값은 `reports/` · `manifests/`의 기록을 그대로 읽은 것입니다.<br>
"10/10"은 증거가 있는 단계 수이며, T03 · T07은 로컬 부분만 통과했습니다(RunPod · vLLM은 blocked).</sub>

## 목차

| | | |
|---|---|---|
| 1. [한눈에 보기](#1-한눈에-보기) | 6. [결과](#6-결과) | 11. [비용과 한계](#11-비용과-한계) |
| 2. [시스템 구성](#2-시스템-구성) | 7. [서빙](#7-서빙) | 12. [재현](#12-재현) |
| 3. [데이터](#3-데이터) | 8. [검수 API](#8-검수-api) | 13. [출처](#13-출처) |
| 4. [모델과 학습](#4-모델과-학습) | 9. [관리자 대시보드](#9-관리자-대시보드) | |
| 5. [평가 설계](#5-평가-설계) | 10. [직무 역량 ↔ 증거](#10-직무-역량--증거) | |

---

## 1. 한눈에 보기

세 방식을 같은 문서 · 같은 채점기로 비교했습니다.

- **B0** — OCR + 규칙 기반 추출. Tesseract 4.1.1은 **학습시키지 않고** 그대로 쓰고, 품목 표를 찾는 규칙은 train/dev 양식만 보고 직접 작성했습니다.
- **M0** — Qwen3-VL-2B 기본 모델 (학습 없음)
- **M1** — M0 + QLoRA 파인튜닝

세트마다 무엇이 다른지는 [6. 결과 › 평가 세트 구성](#평가-세트-구성)에 정리했습니다.

| 평가 세트 | B0<br><sub>OCR + 규칙</sub> | M0<br><sub>기본 모델</sub> | M1<br><sub>QLoRA</sub> |
|---|---:|---:|---:|
| 자체 test<br><sub>학습에 없던 레이아웃 · 40문서</sub> | 0.210 | 0.897 | **0.921** ³ |
| 공개 IID clean<br><sub>20문서</sub> | 0.731 | 0.000 ¹ | **0.880** ⁴ |
| 공개 IID bad_scan<br><sub>20문서</sub> | 0.346 | 0.000 ¹ | **0.798** |
| 공개 OOD clean<br><sub>freelancer 양식 · 20문서</sub> | 0.000 ² | 0.000 ¹ | **0.973** |

<sub>값: strict 필드 정확도, FINAL(설정 동결 후 1회 평가).<br>
¹ M0는 공개 세트 출력 120건을 모두 ```` ```json ```` 코드펜스로 감싸 strict JSON 파싱에 실패했습니다. 펜스를 벗기고 채점하면(lenient) 0.00–0.82입니다. 공개용 프롬프트에 "Markdown 없이" 문구가 빠진 것이 가장 유력한 원인입니다(아래 6장).<br>
² B0는 freelancer 양식의 표 헤더 단어를 규칙에 넣지 않아(v1.2) 60건 모두 품목 행을 하나도 찾지 못했습니다.<br>
³ M1−M0 = +0.024 [−0.001, 0.050], 유의하지 않음. ⁴ M1−B0 = +0.149 [−0.15, 0.42], 유의하지 않음.</sub>

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/images/final-accuracy-ko-dark.svg">
  <img alt="FINAL strict 필드 정확도 — 세트별 B0·M0·M1 막대와 95% CI" src="docs/images/final-accuracy-ko-light.svg">
</picture>

### 읽는 법 — 정직한 결론

**1. B0가 이미 본 레이아웃의 깨끗한 문서는 OCR + 규칙으로도 충분합니다.**
- 공개 IID clean/faded와 dev clean에서 M1−B0 차이가 유의하지 않습니다(final IID clean +0.149 [−0.15, 0.42]).
- 같은 세트의 문서 완전일치는 오히려 **B0가 높습니다**(IID clean 0.80 vs M1 0.65).

**2. OCR 규칙은 처음 보는 레이아웃 · 열화에서 무너지고, 파인튜닝한 VLM은 버팁니다.**
- 자체 test(미학습 레이아웃) M1−B0 **+0.711** [0.67, 0.75]
- dev 열화 3종 +0.71 ~ +0.81, final IID bad_scan +0.452 [0.21, 0.69]

**3. 파인튜닝 이득의 상당 부분은 "출력 형식"입니다.**
- 코드펜스만 벗긴 M0 lenient 점수는 IID clean 0.817, 나머지 0.00–0.56입니다.
- 자체 test에서 M1−M0 = +0.024 [−0.001, 0.050]로 **유의하지 않습니다**.

**4. 남은 위험**
- M1은 모호수량 문서 2건 모두에서 수량을 숫자로 바꿨습니다(AMBIGUOUS_QUANTITY 리콜 **0/2**, M0는 1/2).
- 추출 오류로 인한 오경보가 많습니다(UNIT_PRICE_DIFF FP 15, LINE_ARITHMETIC_MISMATCH FP 19).
- 그래서 제품은 모든 문서를 사람 검수로 보냅니다.
- dev 기반 개선 시도(학습 데이터 보강)는 효과가 없었고, 그 결과도 그대로 기록했습니다.

---

## 2. 시스템 구성

```mermaid
flowchart LR
  IMG["인보이스 이미지<br/>(영어 · 합성)"] --> VLM
  PROMPT["고정 프롬프트"] --> VLM
  VLM["VLM 추출<br/>Qwen3-VL-2B NF4<br/>+ LoRA 어댑터 (M1)"] --> RAW["원문 응답 저장"]
  RAW --> PARSE["strict JSON 파싱<br/>Decimal 정규화"]
  PARSE --> REC["발주서 대사 규칙<br/>UNIT_PRICE_DIFF · QTY_DIFF<br/>PO_LINE_NOT_FOUND …"]
  PO[("독립 발주서 PO")] --> REC
  REC --> REVIEW["사람 검수·수정<br/>버전 CAS"]
  REVIEW --> APPROVE["승인<br/>불변 스냅샷"]
  APPROVE --> EXPORT["JSON/CSV export<br/>승인본만"]
```

- **모델 입력은 고정 프롬프트와 이미지뿐입니다.** 발주서 · 정답 · 파일명 · 시나리오 ID는 모델에 들어가지 않습니다.
- LLM은 VLM 안의 언어모델뿐입니다. 대사와 승인은 결정적 규칙이며, 챗봇 · RAG는 없습니다.
- 모델: [`Qwen/Qwen3-VL-2B-Instruct`](https://huggingface.co/Qwen/Qwen3-VL-2B-Instruct) @ `89644892`<br>
  M1 어댑터 SHA256 `eb086741…`

| 구성 요소 | 코드 |
|---|---|
| 데이터 · 분할 · 합성 렌더러 | [`public_manifest.py`](src/invoiceguard/public_manifest.py) · [`splits.py`](src/invoiceguard/splits.py) · [`synth/`](src/invoiceguard/synth) |
| 학습 · 추론<br><sub>Transformers + PEFT + TRL</sub> | [`vlm/train.py`](src/invoiceguard/vlm/train.py) · [`vlm/infer.py`](src/invoiceguard/vlm/infer.py) |
| OCR 기준선 B0<br><sub>Tesseract, Docker</sub> | [`ocr_baseline.py`](src/invoiceguard/ocr_baseline.py) |
| 채점 · 비교 · 동결 | [`evaluation.py`](src/invoiceguard/evaluation.py) · [`score_run.py`](src/invoiceguard/score_run.py) · [`compare_runs.py`](src/invoiceguard/compare_runs.py) · [`freeze.py`](src/invoiceguard/freeze.py) |
| 대사 규칙 | [`reconciliation.py`](src/invoiceguard/reconciliation.py) |
| GPU 서빙 서버 | [`serving/hf_server.py`](src/invoiceguard/serving/hf_server.py) |
| 검수 API | [`app/api.py`](src/invoiceguard/app/api.py) |
| 관리자 대시보드 | [`dashboard_server.py`](src/invoiceguard/dashboard_server.py) · [`dashboard_static/`](src/invoiceguard/dashboard_static) |

---

## 3. 데이터

데이터는 세 종류이며, 모두 합성입니다.

### PUBLIC_CANONICAL — 공개 데이터
- **출처:** [InvoiceOCR-Synth](https://huggingface.co/datasets/alamgirqazi/invoice-ocr-synthetic) rev `673ff85b` (CC BY 4.0, 합성 영어)
- **규모:** 2,814장 = 938 base × 3 품질(clean · faded · bad_scan), 템플릿 6종
- **정답:** 품목 설명 · 수량 · 단가 · 금액(숫자 canonical). **SKU 정답은 없습니다.**
- **용도:** 학습 · dev · final(IID / OOD)

### TRADE_RAW — 자체 Invoice–PO
- **출처:** 이 저장소의 렌더러로 만든 가상 회사 문서
- **규모:** 224문서, 레이아웃 6종(T01–T06), 시나리오 7종
- **정답:** 렌더러가 그린 원문 문자열 그대로(SKU · 단위 포함) + 독립 발주서
- **시나리오:** `normal` · `price_change` · `quantity_change` · `unknown_sku` · `ambiguous_quantity` · `missing_po_line` · `duplicate_sku`

### stress — dev 전용 열화 세트
- 자체 dev 24장 × 열화 3종(blur + JPEG · fade + noise · skew + 저해상도) = 72장
- 견고성 확인에만 쓰고, final에는 넣지 않습니다.

### IID와 OOD
- **IID**(in-distribution): 학습과 **같은 종류의 양식**에서 뽑은, 학습에 쓰지 않은 새 문서
- **OOD**(out-of-distribution): 학습에서 **통째로 뺀 양식**(freelancer_invoice)의 문서 — 처음 보는 양식에 일반화되는지 봅니다.
- 여기의 OOD는 같은 합성 생성기의 다른 양식 1종입니다. 분포가 완전히 다른 실제 문서가 아닙니다.
- 자체 데이터에서는 학습에서 뺀 레이아웃 T05 · T06으로 만든 test가 같은 역할을 합니다.

```mermaid
flowchart TB
  subgraph PUB["PUBLIC_CANONICAL (공개)"]
    P0["2,814장 = 938 base × 3 품질"] --> P1["누수 그룹 937개<br/>파일명 · 업무 내용 · 추출 대상 · 이미지 해시<br/>union-find"]
    P1 --> PT["train 611 base"]
    P1 --> PD["dev 102 base"]
    P1 --> PI["iid_test 102 base"]
    P1 --> PO["ood_test 123 base<br/>freelancer 양식 전용"]
  end
  subgraph OWN["TRADE_RAW (자체)"]
    O0["224문서 · 시나리오 7종"] --> OT["train 160<br/>레이아웃 T01–T03"]
    O0 --> OD["dev 24<br/>T04"]
    O0 --> OX["test 40<br/>T05–T06 held-out"]
    OD --> OS["stress 72<br/>dev 전용"]
  end
```

**데이터 처리 원칙**
- **가시성 마스크:** 렌더러 소스로 필드가 이미지에 그대로 보이는지 판정했습니다. 인쇄되지 않은 단가 · 대문자 변환 · 28자 절단 · 반올림 인쇄는 채점과 학습에서 뺍니다([`reports/data/`](reports/data)).
- **standard 프로필:** 학습 전용 파일럿으로 고른 뒤 동결했습니다.
  - 학습 이미지 200장, dev 20 + dev_stress 16
  - final: IID 20 base × 3 품질, OOD 20 base × 3 품질
  - IID 풀에는 학습에 없는 `event_ticket` 템플릿도 들어 있습니다.
- **자체 데이터 생성:** 발주서를 먼저 만들고, 시나리오에 따라 값을 유지 · 변경해 인보이스를 렌더합니다.
  - 정답 문자열만 그리고, 렌더 = 정답 · 겹침 · 열 침범을 자동 검사합니다.
  - 프롬프트 주입 문구가 든 견고성 문서도 일부 포함합니다.

| 공개 데이터 상세 | 자체 Invoice–PO 상세 |
|---|---|
| ![공개 데이터 문서 상세](docs/images/dashboard-public-doc.png) | ![자체 Invoice–PO 문서 상세](docs/images/dashboard-trade-doc.png) |
| <sub>bad_scan 문서 · 반올림 인쇄된 단가는 채점에서 제외(빗금)</sub> | <sub>단가 변경 시나리오 → `UNIT_PRICE_DIFF` 검출</sub> |

<sub>왼쪽 문서 이미지는 InvoiceOCR-Synth의 합성 이미지(<a href="https://creativecommons.org/licenses/by/4.0/">CC BY 4.0</a>)를 대시보드 화면 안에 축소해 표시한 것입니다.<br>
오른쪽은 이 저장소의 렌더러가 만든 가상 회사 문서입니다.</sub>

---

## 4. 모델과 학습

| 항목 | 값 |
|---|---|
| 기본 모델 | Qwen3-VL-2B-Instruct<br><sub>NF4 double-quant · bf16 compute, 비전 인코더와 lm_head는 비양자화</sub> |
| 방법 | QLoRA SFT<br><sub>TRL `SFTTrainer` + 검증한 completion-only collator</sub> |
| LoRA | r 8 · α 16 · dropout 0.05 · **언어 모델 q_proj / v_proj만**<br><sub>학습 파라미터 1,605,632개 (전체의 0.11%)</sub> |
| 학습 데이터 | 360건 (PUBLIC_CANONICAL 200 + TRADE_RAW 160) |
| 최적화 | 80 optimizer step<br><sub>micro batch 1 × grad accum 8 (≈1.78 epoch), lr 1e-4 cosine, warmup 0.05</sub> |
| 자원 | 로컬 RTX 4070 Ti SUPER 16GB<br><sub>21.8분 · 최대 VRAM 6.52GB</sub> |
| 학습 전 검증 | loss mask 감사 360/360 (확장 이미지 토큰 기준)<br><sub>10-step smoke: 유한 gradient · 112/112 텐서 변경 · 저장 후 재로드 일치</sub> |

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/images/training-loss-ko-dark.svg">
  <img alt="M1 QLoRA 학습 loss (optimizer step별)" src="docs/images/training-loss-ko-light.svg">
</picture>

**추가 발견 — 추론 속도**
- 이 Windows 환경에서는 비전 patch-embedding Conv3d(bf16)가 문서당 18.4초를 차지했습니다.
- 그 층만 fp32로 계산하도록 바꿔 추론이 2.5–3배 빨라졌고, 모든 arm에 똑같이 적용했습니다.
- 기록: [`reports/model/`](reports/model)

---

## 5. 평가 설계

```mermaid
flowchart LR
  A["학습 전용 파일럿<br/>standard 프로필 선택"] --> B["설정 동결<br/>configs/frozen_v1.json"]
  B --> C["M1 학습<br/>80 step"]
  C --> D["dev 평가 · 실패 분석<br/>개선 시도 1회 (음성)"]
  D --> E["동결 부록<br/>코드 · 어댑터 · OCR 이미지 · manifest 해시"]
  E --> F["FINAL 1회<br/>B0 · M0 · M1 같은 160문서"]
  F --> G["세트별 채점<br/>paired cluster bootstrap"]
```

**공정성**
- M0와 M1은 같은 NF4 로딩 · 프롬프트 · 이미지 전처리 · 생성 설정(greedy, batch 1)을 씁니다.
- 세 방식 모두 같은 문서 · 같은 분모 · 같은 채점기로 평가합니다.

**FINAL은 한 번만**
- 코드 · 어댑터 · OCR 이미지 · manifest 해시를 동결한 뒤 실행했습니다.
- 해시가 다르거나 작업 트리에 커밋하지 않은 변경이 있으면 실행을 거부합니다.
- 누락 · 실패 문서도 분모에 남깁니다.

| 지표 | 정의 |
|---|---|
| strict 필드 정확도 | strict JSON 파싱 → 정규화 후 필드 단위 일치율<br><sub>파싱에 실패한 문서의 필드는 모두 오답</sub> |
| lenient 정확도 | strict JSON이 실패한 출력에서 코드펜스를 벗긴 뒤 채점<br><sub>형식 준수와 읽기 능력을 분리해서 봅니다</sub> |
| 문서 exact | 한 문서의 채점 필드가 모두 맞은 비율 |
| 95% CI | base(공개) / family(자체) 단위 cluster bootstrap |
| paired 차이 | 같은 문서 쌍의 A − B<br><sub>CI가 0을 포함하면 유의하지 않음</sub> |

전체 계약: [`reports/eval/metric_contract_v2.md`](reports/eval/metric_contract_v2.md)

---

## 6. 결과

### 평가 세트 구성

| 세트 | 양식 | 이미지 | 추출 형식 |
|---|---|---|---|
| **자체 test**<br><sub>자체 문서 40개</sub> | T05 · T06<br><sub>학습에서 뺀 레이아웃</sub> | clean | TRADE_RAW<br><sub>SKU · 단위 포함 원문</sub> |
| **공개 IID** ×3<br><sub>20문서 × 품질 3</sub> | 학습과 같은 종류<br><sub>+ event_ticket</sub> | clean<br>faded<br>bad_scan | PUBLIC_CANONICAL<br><sub>설명 · 수량 · 단가 · 금액</sub> |
| **공개 OOD** ×3<br><sub>20문서 × 품질 3</sub> | freelancer<br><sub>학습에서 뺀 양식</sub> | clean<br>faded<br>bad_scan | PUBLIC_CANONICAL |

- 공개 IID · OOD의 세 줄은 **같은 20문서를 세 가지 이미지 품질로** 평가한 것입니다. 아래로 갈수록 스캔 열화가 심해집니다.
- 자체 test와 공개 세트는 문서 출처 · 추출 형식 · 프롬프트가 모두 다릅니다. 그래서 두 묶음의 점수를 직접 비교하지는 않습니다.

### FINAL — 세트별 strict 필드 정확도

| 평가 세트 | B0<br><sub>OCR + 규칙</sub> | M0<br><sub>기본 모델</sub> | M1<br><sub>QLoRA</sub> |
|---|---:|---:|---:|
| 자체 test<br><sub>T05 / T06 · 40문서</sub> | 0.210<br><sub>[0.19–0.23]</sub> | 0.897<br><sub>[0.85–0.94]</sub> | **0.921**<br><sub>[0.87–0.96]</sub> |
| 공개 IID clean<br><sub>20문서</sub> | 0.731<br><sub>[0.46–0.99]</sub> | 0.000<br><sub>lenient 0.817</sub> | **0.880**<br><sub>[0.78–0.96]</sub> |
| 공개 IID faded<br><sub>20문서</sub> | 0.721<br><sub>[0.45–0.98]</sub> | 0.000<br><sub>lenient 0.529</sub> | **0.851**<br><sub>[0.69–0.95]</sub> |
| 공개 IID bad_scan<br><sub>20문서</sub> | 0.346<br><sub>[0.15–0.56]</sub> | 0.000<br><sub>lenient 0.466</sub> | **0.798**<br><sub>[0.63–0.92]</sub> |
| 공개 OOD clean<br><sub>freelancer · 20문서</sub> | 0.000 ² | 0.000<br><sub>lenient 0.555</sub> | **0.973**<br><sub>[0.94–0.99]</sub> |
| 공개 OOD faded<br><sub>freelancer · 20문서</sub> | 0.000 ² | 0.000<br><sub>lenient 0.000</sub> | **0.905**<br><sub>[0.83–0.96]</sub> |
| 공개 OOD bad_scan<br><sub>freelancer · 20문서</sub> | 0.000 ² | 0.000<br><sub>lenient 0.058</sub> | **0.756**<br><sub>[0.62–0.88]</sub> |

<sub>[ ] = 95% CI. ² B0의 0점은 freelancer 양식의 헤더 단어를 규칙에서 일부러 뺀(v1.2) 결과로, 60건 모두 품목 행을 찾지 못했습니다.<br>
M1이 OOD clean에서 IID clean보다 높은 것은 이 OOD가 같은 생성기의 양식 1종이기 때문입니다. 원본: [`reports/eval/final_summary.md`](reports/eval/final_summary.md)</sub>

### 0.000은 무엇을 뜻하나

| | 원인 | 확인한 사실 |
|---|---|---|
| **M0** | 형식 실패<br><sub>읽기는 함</sub> | 공개 세트 출력 120건이 모두 ```` ```json ````로 시작 → strict JSON 실패<br><sub>같은 M0가 자체 test 40건에서는 순수 JSON을 내서 0.897</sub> |
| **B0** | 인식 실패<br><sub>표를 못 찾음</sub> | OOD 60건 모두 추출한 품목 행 0개<br><sub>헤더 단어로 표를 찾는 규칙이라 처음 보는 양식에 약함 (자체 test도 40건 중 22건이 행 0개)</sub> |

**왜 M0는 자체 test만 맞추나**
- 두 묶음은 프롬프트가 다릅니다.
  - 자체용 [`EXTRACT_V1.txt`](prompts/EXTRACT_V1.txt): "Return only one JSON object, **without Markdown** or commentary."
  - 공개용 [`EXTRACT_PUBLIC_CANONICAL.txt`](prompts/EXTRACT_PUBLIC_CANONICAL.txt): "Return one JSON object only" — Markdown 금지 문구가 없습니다.
- 같은 M0가 앞의 프롬프트에서는 40/40 순수 JSON을, 뒤의 프롬프트에서는 120/120 코드펜스를 냈습니다. 문구 차이가 가장 유력한 원인입니다.
- 프롬프트는 동결 대상이라 final 이후 고치지 않았습니다. 그래서 공개 세트의 M0 strict 점수는 형식 탓에 낮게 나온 값이며, 읽기 능력은 lenient 열로 봐야 합니다.
- 펜스를 벗겨도 열화 문서(faded · bad_scan)에서는 점수가 낮습니다(OOD 0.000 · 0.058). 열화 문서에서는 읽기 자체도 약합니다.
- M1은 같은 프롬프트로 학습해서 코드펜스 없이 답하게 됐습니다. M1의 공개 세트 이득에는 이 형식 효과가 크게 섞여 있습니다.

### Paired 차이 (같은 문서, A − B)

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/images/paired-diff-ko-dark.svg">
  <img alt="M1−M0, M1−B0 paired 차이와 95% CI" src="docs/images/paired-diff-ko-light.svg">
</picture>

- 자체 test에서 **M1−M0 = +0.024 [−0.001, 0.050], 유의하지 않음.**
  - 미학습 레이아웃에서는 기본 VLM도 이미 강합니다.
- 공개 IID clean / faded에서 **M1−B0는 유의하지 않음.**
  - OCR + 규칙은 본 레이아웃의 깨끗한 문서에서 경쟁력이 있습니다.

### 대사 경고 품질

자체 test 40문서에서, 각 방식의 추출 결과로 돌린 대사 경고를 정답 기준 대사 결과와 비교했습니다.

| 경고 코드<br><sub>TP / FP / FN</sub> | B0 | M0 | M1 |
|---|:---:|:---:|:---:|
| `UNIT_PRICE_DIFF` | 0 / 0 / 10 | 10 / 13 / 0 | 10 / 15 / 0 |
| `QTY_DIFF` | 0 / 0 / 6 | 5 / 1 / 1 | 5 / 2 / 1 |
| `AMBIGUOUS_QUANTITY` | 0 / 85 / 2 | 1 / 0 / 1 | **0 / 0 / 2** |
| `LINE_ARITHMETIC_MISMATCH` | 0 / 0 / 0 | 0 / 18 / 0 | 0 / 19 / 0 |
| 검수 대상 비율 | 1.00 | 0.65 | 0.675 |

dev 단계 결과와 실패 분류: [`dev_summary.md`](reports/eval/dev_summary.md) · [`failures_m1_dev_v1.md`](reports/eval/failures_m1_dev_v1.md)

---

## 7. 서빙

**Transformers + PEFT GPU 서버** ([`serving/hf_server.py`](src/invoiceguard/serving/hf_server.py))
- OpenAI 호환 subset, 127.0.0.1 전용
- GPU 작업자 1개 + 대기열 2개

| 측정<br><sub>자체 dev 10장, warmup 3</sub> | 결과 |
|---|---|
| 출력 동일성<br><sub>서버 vs 오프라인</sub> | M0 · M1 모두 원문 100% 동일<br><sub>같은 프롬프트 토큰 1045개</sub> |
| 처리량 · 지연<br><sub>M1</sub> | 동시 1: 4.0 문서/분, p50 16.1s / p95 18.4s<br>동시 2: 4.2 문서/분, p50 26.6s / p95 36.3s<br><sub>직렬 작업자라 대기 시간이 늘어난 것이며, 배치 효과가 아님</sub> |
| 동시 4 | 10건 중 7건 실패 기록<br><sub>대기열 초과 429로 추정되지만 벤치가 상태 코드를 저장하지 않아 미확인. 별도 probe에서 동시 4건 → 200 · 200 · 200 · 429 확인</sub> |
| 타임아웃 취소 | 3초 제한 요청 → 3.1초에 504, 직후 작업자 `busy:false`<br><sub>StoppingCriteria로 생성을 중단해 남는 추론이 없음</sub> |
| GPU 메모리 | 약 3.1GB<br><sub>nvidia-smi, 다른 프로세스 포함</sub> |
| LIVE 시연 | 검수 API(LIVE_MODEL) → 추출 15.2s → `UNIT_PRICE_DIFF` 검출 → 승인 → 스냅샷 export<br><sub>추출 결과가 정답 행과 일치</sub> |

**vLLM: blocked**
- `vllm/vllm-openai:v0.11.2`(Qwen3-VL 지원 버전)는 CUDA ≥ 12.9가 필요하고, 로컬 드라이버 561.17은 CUDA 12.6까지입니다.
- 요구 조건 검사를 끄고 시도해도 컨테이너 안 PyTorch가 "No CUDA GPUs are available"로 실패했습니다.
- 드라이버 업데이트와 클라우드 GPU를 쓰지 않기로 결정했으므로, vLLM 속도 · 양자화 정확도는 주장하지 않습니다.
- 벤치 스크립트는 준비되어 있습니다: [`serving/vllm_bench.py`](src/invoiceguard/serving/vllm_bench.py)

![서빙 페이지](docs/images/dashboard-serving.png)

---

## 8. 검수 API

FastAPI + SQLite ([`app/api.py`](src/invoiceguard/app/api.py))
- 사람이 승인한 버전만 내보냅니다.
- 늦게 도착한 추론이 최신 수정 · 승인을 덮어쓰지 못하게 합니다.

```mermaid
stateDiagram-v2
  direction LR
  [*] --> uploaded: 이미지 업로드 + PO 연결
  uploaded --> extracting: extract
  extracting --> needs_review: 대사 경고 있음
  extracting --> matched_candidate: 경고 없음
  extracting --> failed: 타임아웃 504 / 모델 없음 503 / 형식 오류
  failed --> extracting: 명시적 재시도
  needs_review --> approved: approve
  matched_candidate --> approved: approve
  needs_review --> matched_candidate: review 수정 후 경고 없음
  approved --> needs_review: review 수정 → 새 버전, 승인 취소
  needs_review --> rejected: reject
  matched_candidate --> rejected: reject
  approved --> [*]: export (승인 스냅샷)
```

<sub>다이어그램은 주요 흐름만 그렸습니다.<br>
reject는 `extracting`을 뺀 모든 상태에서, 재추출은 `approved`를 뺀 상태에서 가능합니다. 수정 결과는 대사 경고 유무에 따라 `needs_review` 또는 `matched_candidate`가 됩니다.</sub>

**보장하는 것**
- **버전 CAS:** 추출 · 수정 · 승인은 모두 `expected_version`을 확인합니다.<br>
  추출이 끝나면 (버전, run_id, 상태)를 다시 확인하고, 그 사이 바뀐 케이스에는 결과를 기록만 하고 반영하지 않습니다.
- **추론은 하나씩:** 동시 추출 요청은 429, 추출 중 수정 · 승인은 409를 돌려줍니다.<br>
  타임아웃이 나면 백엔드를 격리(503)하고, health check가 통과하면 풉니다.
- **불변 스냅샷:** 승인 시 스냅샷과 SHA256을 저장하고, export는 현재 버전의 유효한 승인 스냅샷만 돌려줍니다.<br>
  재시작하면 `extracting`에 남은 케이스는 `failed/INTERRUPTED`로 바뀝니다.
- 검수용 **화면 UI는 아직 없습니다.** API, 테스트 12개, LIVE 종단 시연 기록만 있습니다.

---

## 9. 관리자 대시보드

로컬 전용 읽기 전용 대시보드입니다.
- 127.0.0.1에서만 열리고 GET만 허용하며, 외부 리소스 없이 엄격한 CSP를 씁니다.
- 기본은 다크 모드이며, 라이트 모드로 바꿀 수 있습니다.
- 화면의 수치는 모두 저장소 기록을 그대로 읽으며, 추정하지 않습니다.

```bash
.venv/Scripts/python.exe -m invoiceguard.dashboard_server --port 8765   # http://127.0.0.1:8765
```

| 페이지 | 보여 주는 것 |
|---|---|
| 개요 · 진행 단계·게이트 | 파이프라인 단계, KPI, FINAL 막대, 차단 항목<br><sub>T00–T09 작업, G0–G7 인수 게이트</sub> |
| 공개 데이터 · 자체 Invoice–PO | 필터 목록 → 문서 이미지 + 정답 + 가시성 마스크<br><sub>자체 데이터는 발주서와 대사 결과까지</sub> |
| 분할·manifest | 분할 통계, 누수 검사, 동결 상태 |
| 모델·평가 · 서빙 | B0 · M0 · M1 막대(95% CI · lenient), paired 차이, 학습 loss<br><sub>지연 · 처리량 · 취소 · 출력 동일성</sub> |
| 검수 API · 테스트 · 클라우드·비용 | T06 기록과 LIVE 시연, pytest 요약, 예산 계획과 승인 양식 |

| 모델·평가 | 진행 단계·게이트 |
|---|---|
| ![모델·평가 페이지](docs/images/dashboard-model.png) | ![진행 단계·게이트 페이지](docs/images/dashboard-progress.png) |

---

## 10. 직무 역량 ↔ 증거

| 역량 | 이 저장소의 증거 |
|---|---|
| LoRA / QLoRA / SFT<br><sub>transformers · peft · **trl**</sub> | TRL `SFTTrainer` + 검증 collator, NF4 + LoRA r8<br><sub>[`vlm/train.py`](src/invoiceguard/vlm/train.py) · [`train_m1_standard_v1.json`](reports/model/train_m1_standard_v1.json)</sub> |
| 학습 정확성 검증 | loss mask 감사 360/360, 10-step smoke, 재로드 일치<br><sub>[`reports/model/`](reports/model)</sub> |
| 추출 정확도 · 실패 분석 · 개선 | 세트별 평가기 · paired bootstrap, 실패 분류, 개선 1건과 **음성 결과**<br><sub>[`reports/eval/`](reports/eval)</sub> |
| 자동 채점 · 회귀 테스트 | pytest 160개 이상(규칙 B01–B12, 평가 E01–E05, API A01–A08, 대시보드)<br><sub>[GitHub Actions CI](.github/workflows/ci.yml) · 동결 · 해시 가드</sub> |
| 서빙 · 성능 측정 | Transformers + PEFT GPU 서버 — 실제 타임아웃 취소 · bounded queue 실측<br><sub>[`reports/serving/`](reports/serving) · vLLM은 blocked</sub> |
| OCR / 문서 AI | Tesseract 기준선 B0<br><sub>train/dev만 보고 만든 일반 규칙, Docker 격리</sub> |
| 표 구조 문서 · 도메인 규칙 | 구조가 다른 인보이스 레이아웃 6종 렌더러, PO 대사 규칙 |
| 서비스 연동 | 검수 API: 추출 CAS, 늦은 응답 덮어쓰기 방지, 승인 스냅샷 export |

---

## 11. 비용과 한계

**비용**
- 클라우드 지출 **$0** — RunPod은 쓰지 않았습니다(사용자 결정).
- 학습 1회 약 22분, final M0 · M1 추론 약 49분(B0 OCR 시간은 기록 없음), 모두 로컬 GPU

**한계**
- 합성 데이터만 썼고 표본이 작습니다.
  - 공개 세트당 20 base, 자체 test 40문서, 경고 코드별 사례 1–10건
  - 열화 stress는 dev 전용입니다.
- M0의 낮은 strict 점수는 형식 효과가 큽니다. 공개용 프롬프트에 "Markdown 없이" 문구가 빠져 있었고, 동결 후라 고치지 않았습니다.
- 모호수량 실패는 해결되지 않았습니다.
- 서빙
  - 서빙 프레임워크(vLLM)는 측정하지 못했습니다(blocked).
  - 양자화 비교 없음(NF4 단일), 배칭 없음(batch 1, 직렬 작업자)
  - 벤치는 문서 10장 · 반복 1회이고, 서빙 서버 자체의 자동 테스트 없이 수동 probe만 있습니다.
- 클라우드 GPU 운영 · 비용 증거는 not_run입니다.
- FSDP / DeepSpeed는 2B 모델 · 단일 GPU에서 필요가 없어 쓰지 않았습니다([`docs/19_DECISIONS_V5.md`](docs/19_DECISIONS_V5.md)).
- 검수 **화면 UI는 미구현**입니다(검수 API와 읽기 전용 관리자 대시보드만 있음).

**진행 방식**
- 방향 판단과 단계별 검토는 Fable, 구현은 Opus(Claude Code)로 진행했습니다.
- 중간 검토가 찾은 문제(B0의 held-out 어휘 오염 등)는 고치고 기록했습니다([`IMPLEMENTATION_STATUS.md`](reports/IMPLEMENTATION_STATUS.md)).

---

## 12. 재현

**0) 제품 · 평가 환경 (CPU)**
```bash
uv venv --python 3.11 .venv && uv pip install --python .venv/Scripts/python.exe -e ".[dev,app]"
.venv/Scripts/python.exe -m pytest tests/
```

**1) 데이터** — 공개 데이터는 HF에서 rev `673ff85b`의 parquet 2개를 `data/raw/invoice-ocr-synthetic/<rev>/data/`에 받은 뒤
```bash
.venv/Scripts/python.exe -m invoiceguard.public_profile && .venv/Scripts/python.exe -m invoiceguard.public_manifest
.venv/Scripts/python.exe -m invoiceguard.synth.build && .venv/Scripts/python.exe -m invoiceguard.vlm.stress build
```

**2) 모델 환경 (`.venv-ml`)** — 정확한 버전은 `requirements-ml.lock.txt`<br>
<sub>torch 2.9.1+cu126 · transformers 4.57.6 · peft 0.17.1 · trl 0.25.1 · bitsandbytes 0.48.2.
모델 `Qwen/Qwen3-VL-2B-Instruct @ 89644892`를 `models/qwen3-vl-2b-instruct/<rev>/`에 둡니다.</sub>
```bash
.venv-ml/Scripts/python.exe -m invoiceguard.vlm.smoke masks
.venv-ml/Scripts/python.exe -m invoiceguard.vlm.train --profile standard --run-id m1_standard_v1
```

**3) B0 OCR (Docker)** — 이미지를 빌드한 뒤 OCR → 예측
```bash
docker build -t invoiceguard-ocr:tesseract docker/ocr
.venv/Scripts/python.exe -m invoiceguard.ocr_baseline ocr --set trade:dev --set public:dev --psm 4
.venv/Scripts/python.exe -m invoiceguard.ocr_baseline predict --set trade:dev --set public:dev --psm 4 --run-id b0_dev
```

**4) 추론 → 채점 → paired 비교** — 원문 응답을 먼저 저장합니다.
```bash
.venv-ml/Scripts/python.exe -m invoiceguard.vlm.infer --arm m1 --adapter artifacts/adapters/m1_standard_v1 --set trade:dev --set public:dev --run-id m1_dev
.venv/Scripts/python.exe -m invoiceguard.score_run artifacts/predictions/m1_dev
.venv/Scripts/python.exe -m invoiceguard.compare_runs m1_dev b0_dev
```

**5) final** — 코드 커밋 → 동결 부록 기록 · 커밋 → `--allow-final`(해시가 다르거나 커밋하지 않은 변경이 있으면 거부)
```bash
.venv/Scripts/python.exe -m invoiceguard.freeze write
.venv-ml/Scripts/python.exe -m invoiceguard.vlm.infer --arm m1 --adapter artifacts/adapters/m1_standard_v1 --set public:iid_final --set public:ood_final --set trade:test --run-id m1_final --allow-final
.venv/Scripts/python.exe -m invoiceguard.score_run artifacts/predictions/m1_final --allow-final
```

**6) 서빙 · 검수 API · 대시보드 (127.0.0.1)**
```bash
.venv-ml/Scripts/python.exe -m invoiceguard.serving.hf_server --adapter artifacts/adapters/m1_standard_v1 --port 8001
.venv/Scripts/python.exe -m invoiceguard.serving.vllm_bench run --label hf_peft_nf4_local --port 8001 --conc 1,2,4 --docs 10 --reps 1
.venv/Scripts/python.exe -m invoiceguard.app.server --mode live --model-url http://127.0.0.1:8001 --model m1
.venv/Scripts/python.exe -m invoiceguard.dashboard_server --port 8765
```

**7) README 차트 다시 그리기** — `reports/`의 기록에서 생성합니다.
```bash
.venv/Scripts/python.exe -m invoiceguard.readme_figures
```

원래 패키지 안내(Claude Code 시작 방법 · 설계 문서 목록)는 [`docs/PACKAGE_README_v4.md`](docs/PACKAGE_README_v4.md)에 있습니다.

---

## 13. 출처

- **공개 데이터:** [alamgirqazi/invoice-ocr-synthetic](https://huggingface.co/datasets/alamgirqazi/invoice-ocr-synthetic), [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)
  - 공개 데이터 화면 캡처(`docs/images/dashboard-public-doc.png`)에 이 데이터셋의 합성 이미지 1장(`synth_0433_668d20e1.png`, bad_scan)이 대시보드 화면 안에 축소되어 들어 있습니다.
  - 데이터 자체는 저장소에 포함하지 않습니다.
- **기본 모델:** [Qwen/Qwen3-VL-2B-Instruct](https://huggingface.co/Qwen/Qwen3-VL-2B-Instruct) — 가중치는 저장소에 포함하지 않습니다.
- **OCR:** [Tesseract](https://github.com/tesseract-ocr/tesseract) 4.1.1 (Docker 이미지 안에서 실행)
