# 19. 계약 개정 v5 — 공고 맞춤 방향 결정 (2026-11-14)

결정 주체: 사용자가 "전체 판단·검토는 Fable, 구현은 Opus"로 위임 → Fable(Claude Fable 5.2) 결정서를 Opus가 구현한다. 유료 RunPod 실행·로그인은 여전히 사용자의 명시 승인 대상이다.
배경: 대상 공고(JobKorea 50342762, LLM/VLM 파인튜닝·서빙)는 LoRA/SFT, HF transformers/peft/**trl**, **서빙 프레임워크 실측(양자화·추론 가속·배치)**, 자동 채점·회귀, 실패 분석을 요구한다. 로컬 실측(10-step QLoRA pass, HF+NF4 생성 약 10 tok/s)과 "OCR로 대체되지 않나"라는 질문이 계기다.

## 채택/기각
| 항목 | 결정 | 근거 |
|---|---|---|
| A. OCR 기준선 B0 | 지금 채택 | VLM 필요성의 대조군, 우대사항(OCR/문서AI) |
| B. stress 변형 | 지금 채택 — **dev/benchmark 전용** | final과 분리, docs/06의 stress 허용 범위 |
| C. 지표 분리 | 지금 채택 | 형식(코드펜스) 실패와 읽기 실패 분리 |
| D. TRL SFTTrainer | 지금 채택 (마스크 감사 재통과 조건) | 공고 필수 trl |
| E. vLLM 서빙 | **P1 → P0** (로컬 Docker/WSL2, 127.0.0.1) | 공고 필수 서빙 실측 |
| F. RunPod 1회 | 시간 되면 + 사용자 승인 | 클라우드 운영·비용 증거 |
| G. 8B vs 2B | 시간 되면, **추론 전용** arm, 유료 승인 시에만 | 8B 학습 없음 |
| H. FSDP/DeepSpeed | 기각 | $7로 2-GPU 학습 위험, 근거 약함 |
| I. DPO | 기각 | 소표본·근거 약함 |
| J. 한영 혼합 레이아웃 | 시간 되면, stress 전용(미학습 OOD) | 우대사항 |
| K. GitHub Actions CI | 지금 채택 | 회귀 테스트 |
| L. 검수 API | 최소 범위(replay + CAS 테스트), 후순위 | 공고 가중치 낮음 |

## 개정된 계약
1. **서빙**: Transformers+PEFT(HF)는 주 비교표의 기준 평가 경로로 유지한다. vLLM은 별도 서빙 arm이며 HF NF4 결과와 같은 dev 표본의 필드 일치율로만 "정확도 유지"를 말한다. 속도 비교는 같은 문서·같은 토큰 한도일 때만 한다. continuous batching이 실제로 켜진 경우만 batch 효과라 부른다.
2. **로컬 GPU**: 사용자 승인에 따라 2B QLoRA 본학습과 평가는 로컬 RTX 4070 Ti SUPER 16GB가 주 실행 위치다. RunPod는 재현·비용 증거용이며 유료 승인 규칙은 그대로다. 학습기와 서빙/평가를 한 GPU에 동시에 띄우지 않는다.
3. **B0 arm**: 입력은 M0/M1과 같은 이미지뿐이다(PO·정답·파일명 접근 금지). 규칙 조정은 train/dev만 보고 하며 final 전에 커밋 해시로 동결한다. held-out 레이아웃(T05–T06, freelancer_invoice)에 맞춘 규칙 금지. 조정 시간·규칙 수를 공개한다.
4. **stress set**: 사전 정의 변형(blur/JPEG/기울기/저해상도 등)과 seed를 고정하고 dev 문서에만 적용한다. final 표에 합산하지 않는다.
5. **지표**: strict JSON(펜스·잘림 복구 없음)이 주 지표다. lenient(코드펜스 제거만) 점수와 "strict 유효 출력 조건부 필드 정확도"를 보조로 병기하며 각 분모를 명시한다.
6. **동결(S2)**: 프로필(standard), manifest 해시, 태스크 프롬프트 해시, 이미지 전처리(max_pixels), generation 설정, 로딩 정밀도, LoRA 설정을 `configs/frozen_v1.json`에 기록한다. 이후 프롬프트 변경은 모든 arm 재평가. final 열람 후 수정한 평가는 exploratory로 강등. final은 1회.
7. **두 번째 모델**: "second large model 금지"를 "8B는 추론 전용 탐색 arm, 유료 승인 시에만"으로 완화한다.

## 실행 순서 (S1–S8 로컬·무승인, S9 승인 필요)
S1 계약 개정+지표 분리+CI → S2 dev 전용 프롬프트 확정·동결 → S3 B0 → S4 TRL M1 본학습·재로드 → S5 dev 평가·실패 분석·수정 1건(전 arm 재평가, stress는 dev만) → S6 vLLM 로컬 서빙 벤치(2시간 내 기동 실패 시 blocked 기록) → S7 final 1회(M0/M1/B0 같은 subset, 주 표는 HF NF4) → S8 README·결과표·최소 검수 API → S9 [사용자 승인+RunPod 로그인] 1-GPU Pod 재현·$/1k docs·백업·종료 확인.

## 피해야 할 함정
B0 허수아비/과적합, final 조기 열람, lenient를 주 지표로 사용, 다른 정밀도 결과를 "양자화해도 동일"로 주장, 품질 변형을 독립 표본으로 계산(base 단위 bootstrap 사용), 유형별 n=1–2를 일반화, 합성 점수를 실제 통관 성능으로 확대, smoke 어댑터 이어 학습, M1 열위 결과 숨기기.
