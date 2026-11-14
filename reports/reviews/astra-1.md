**76/100점입니다. 서류에서 면접으로 넘길 만한 포트폴리오지만, “학습한 모델을 품질 손실 없이 서빙한다”는 증거가 부족합니다.** 현재 코드와 기존 실행 기록 기준이며, 진행 중인 P3는 제외했습니다. 지정 문서에 이전 평가점수가 포함돼 있어 완전한 블라인드는 아니지만, 아래 가중치는 공고 기준으로 별도 산정했습니다.

| 공고 항목 | 가중치 | 획득점 | 판단·근거 |
|---|---:|---:|---|
| LoRA/SFT, transformers·peft·trl | 20 | 17 | 실제 학습·마스크 검증·재현성 우수. seed·ablation 부족. [train.py](H:/dev/invoiceguard-po/src/invoiceguard/vlm/train.py:96), [학습 비교](H:/dev/invoiceguard-po/reports/runpod/train_compare.json:40) |
| 품명·수량·단가·품번 정확도 | 15 | 11 | 자체 test 0.921이나 M1−M0 비유의, 단가 0.824. [FINAL](H:/dev/invoiceguard-po/reports/eval/final_summary.md:22), [필드별 결과](H:/dev/invoiceguard-po/README.md:378) |
| 서빙 프레임워크·가속·배치 | 20 | 14 | vLLM 배포·동시성 실측 인정. M1 품질 저하 미해결. [RunPod](H:/dev/invoiceguard-po/reports/runpod/RUNPOD_RUN.md:74) |
| 자동 채점·회귀 테스트 | 15 | 14 | 실패 분모 유지, bootstrap, 엄격/보조 지표, CI가 강점. [평가기](H:/dev/invoiceguard-po/src/invoiceguard/evaluation.py:44), [CI](H:/dev/invoiceguard-po/.github/workflows/ci.yml:17) |
| 실패 분석·프롬프트·데이터 개선 | 10 | 7 | 구체적 분석과 부정적 결과 공개. 위험 오류 개선 성공은 없음. [dev 분석](H:/dev/invoiceguard-po/reports/eval/dev_summary.md:42) |
| Linux·SSH·GPU 운영 | 8 | 7 | 설치·터널·백업·복원·삭제 실증. 운영 경험은 단기 1회. [실행 기록](H:/dev/invoiceguard-po/reports/runpod/RUNPOD_RUN.md:24) |
| OCR·표 문서·무역 도메인 | 5 | 4 | 독립 PO·Decimal 대사·승인본 export 우수. 통관 서류 전반은 미검증. [대사](H:/dev/invoiceguard-po/src/invoiceguard/reconciliation.py:77), [승인](H:/dev/invoiceguard-po/src/invoiceguard/app/api.py:335) |
| 양자화·클라우드 비용 최적화 | 4 | 2 | NF4·비용 기록 있음. 품질/속도/비용 비교 부족. [한계](H:/dev/invoiceguard-po/README.md:560) |
| 멀티 GPU·한영 혼합 | 2 | 0 | 현재 실증 없음. [범위](H:/dev/invoiceguard-po/README.md:564) |
| Java/Spring Boot/React | 1 | 0 | Python·vanilla JS 구현. [구현 현황](H:/dev/invoiceguard-po/reports/IMPLEMENTATION_STATUS.md:118) |
| **합계** | **100** | **76** | |

**필수역량이 통째로 빠진 치명적 공백은 없습니다.** 제가 서류 검토자라면 면접 대상으로 봅니다. 다만 즉시 서빙 업무를 맡길 사람을 찾는다면, **vLLM에서 11.1%p 하락하고 원문도 남기지 않은 점**은 실제 탈락 사유가 될 수 있습니다. 합성 데이터 한계와 모호수량 recall 0/2도 중요하지만, 이를 명시하고 사람 승인을 강제한 설계는 타당합니다([FINAL:42](H:/dev/invoiceguard-po/reports/eval/final_summary.md:42)).

90점에는 약 **14점의 실질적 보강**이 필요합니다. 아래 가산점은 결과가 확인될 때의 추정치입니다.

| 보강 작업 | 예상 가산 | 노력 | 유료 GPU |
|---|---:|---|---|
| P3→P8: 원인 분리·수정 후 vLLM 정확도 회복, 동시성별 품질·p95 검증 | +4–5 | 1–2일 | 현재 환경에서는 짧은 재측정 필요 |
| P5: M0/M1 BF16·INT8·NF4 정확도/지연/VRAM 비교 | +2 | 반나절–1일 | 불필요 |
| P6: 추가 seed 2개·데이터 구성 ablation | +2 | 약 1일 | 불필요 |
| 모호수량·누락행 대상 개선, 새로 고정한 검증셋에서 효과 확인 | +3 | 1–3일 | 대체로 불필요 |
| 서빙 취소·포화·실패 회귀 테스트, 한영 혼합·다페이지 합성 검증 | +2–3 | 1–2일 | 불필요 |

[계획](H:/dev/invoiceguard-po/plan.md:25)의 순서는 **P1 상태 정리 → P2/P7 완료 확인 → P3/P5 → P8 → 실패 개선 → P6 → P9 → P10**을 권합니다. P2는 상당 부분 반영됐고, P7 표는 이미 있습니다. P4는 이번 자문에 해당합니다. **P8은 H3일 때만 수행할 일이 아니라, 최종 서빙 경로의 품질 확인에 필요합니다.** P9는 점수가 나올 때까지 반복하기보다 사전 완료 기준으로 한 번 재평가하세요. 멀티 GPU 도입과 대규모 rank sweep은 현재 우선순위가 낮습니다. 기존 FINAL은 유지하고 새 검증셋을 별도로 고정해야 합니다.

vLLM 하락은 **일반적인 A40 문제보다 M1의 베이스 정밀도·LoRA 적용·출력 구조 사이의 상호작용**을 우선 의심합니다. M0는 오히려 개선됐고, A40 HF NF4에서는 동일 필드 정확도가 재현됐습니다. 다만 NF4→BF16 불일치와 vLLM 구현 중 어느 쪽인지는 아직 가를 수 없습니다([RunPod:63](H:/dev/invoiceguard-po/reports/runpod/RUNPOD_RUN.md:63)).

[P3 E1–E5](H:/dev/invoiceguard-po/plan.md:45)는 유용하지만 판정 문구를 수정해야 합니다.

- **E1/E3:** HF 안의 정밀도 효과를 확인합니다. E1 저하만으로 H1을 “확정”, 정상만으로 “기각”할 수는 없습니다.
- **E2:** dtype 민감도 검사입니다. 현재 코드는 vision·lm_head dtype도 함께 바꾸며 모든 HF 조건에서 Conv3d를 FP32로 실행합니다. 순수 언어부 정밀도 비교가 아닙니다([model.py:26](H:/dev/invoiceguard-po/src/invoiceguard/vlm/model.py:26)).
- **E4:** 8건 NF4 일치는 A40/Linux의 일반적 문제를 약화하지만, BF16 커널 차이를 배제하지 못합니다. A40은 BF16 지원 GPU이며 FP32가 추출 정확도를 반드시 높이지는 않습니다.
- **E5:** 지원 여부와 양자화 제외 모듈부터 확인해야 합니다. 먼저 **같은 A40에서 HF BF16↔vLLM BF16, M0/M1**을 비교하는 연결 실험이 필요합니다.

원문·필드별 오답·입력 토큰/이미지 전처리·종료 조건·실제 모듈 dtype을 함께 저장하세요. 단순 BF16 병합도 해결을 보장하지 않습니다. `W_bf16+Δ`는 학습 때의 `dequant(W_nf4)+Δ`와 다릅니다.

README에서 확인한 부정확한 주장은 다음입니다.

1. **“Every M1 document lost exactly 4 fields”**([README:663](H:/dev/invoiceguard-po/README.md:663))는 틀립니다. JSON을 집계하면 오답 4개인 문서는 **17/20**, 나머지는 6·5·0개입니다. 특히 [18/18 정답·원문 동일 사례](H:/dev/invoiceguard-po/reports/serving/vllm_bf16_a40.json:651)가 있습니다. “합계 4필드 누락”은 원문 없는 가설로 남겨야 합니다.
2. **“(version, run_id, state) is checked again”**([README:507](H:/dev/invoiceguard-po/README.md:507))과 달리 완료 검사는 [state와 active_run_id](H:/dev/invoiceguard-po/src/invoiceguard/app/api.py:246)입니다. 설명을 고칠 부분이며, 현재 단일 프로세스에서 지연 덮어쓰기 결함을 발견했다는 뜻은 아닙니다.
3. **“no batching”**([README:572](H:/dev/invoiceguard-po/README.md:572))은 HF 서버로 범위를 한정해야 합니다. [vLLM 동시성 실측](H:/dev/invoiceguard-po/reports/runpod/RUNPOD_RUN.md:74)과 현재 문구가 충돌합니다.

핵심 학습·FINAL 수치·승인본 export 주장은 정적 검토와 기존 기록으로 뒷받침됩니다. 이번 검토에서 테스트나 모델은 실행하지 않았습니다.