# RunPod 실행 기록 — 2026-11-14 (세션 2)

목적: **학습이 제대로 되었는지** 다른 머신에서 증명하고, 실제 서빙 프레임워크(vLLM)를 측정한다. 성능 향상은 목표가 아니다.
대상: 동결된 M1 학습(`m1_standard_v1`, 로컬 RTX 4070 Ti SUPER)을 같은 설정으로 다시 학습한다.
승인과 비용 상한: [`../RUNPOD_APPROVAL.md`](../RUNPOD_APPROVAL.md).

## 대여한 서버

| 항목 | 값 | 근거 |
|---|---|---|
| Pod | `jwvf173fyus06x` · invoiceguard-a40-repro | create-pod / get-pod |
| GPU | NVIDIA A40 48GB × 1 (Ampere, sm_86) · 드라이버 595.91.07 · host CUDA 13.2 | [`pod_nvidia_smi.txt`](pod_nvidia_smi.txt), [`pod_env.json`](pod_env.json) |
| 위치 | Secure Cloud · CA-MTL-1 | get-pod, 콘솔 |
| CPU · RAM | 9 vCPU (Xeon Gold 6342, cgroup 한도 7.65코어) · 50GB | 콘솔, `/sys/fs/cgroup/cpu.max` |
| 이미지 | `runpod/pytorch:1.0.2-cu1281-torch280-ubuntu2404` (공식 템플릿 runpod-torch-v280) — 이미지의 torch는 쓰지 않음 | list-public-templates |
| 디스크 | container 80GB(로컬 overlay) + volume 20GB `/workspace`(NFS) | 콘솔, `findmnt` |
| 접속 | `22/tcp`만 공개(직접 SSH · scp). HTTP 포트·Jupyter 없음 | create-pod body |
| 요금 | GPU $0.59 + container $0.011 + volume $0.003 = **$0.60/hr** | 콘솔 Pod 상세 |
| 사용 시간 | 17:59:55 → 18:43:19 KST (**43분 24초**) | create-pod `createdAt`, delete-pod 시각 |
| 비용 | 약 **$0.43** (43.4분 × $0.60/hr, 계산값). 콘솔 잔액 $9.81 → $9.56 (18:44 기준, 과금 반영 지연 최대 1시간) | 콘솔 Billing |

콘솔 캡처: [`../../docs/images/runpod/`](../../docs/images/runpod) (계정 잔액·프로필 영역은 가림).

## 진행 순서와 결과

| 시각 (KST) | 단계 | 결과 |
|---|---|---|
| 17:50 | 계정 조회(MCP, 읽기 전용) | Pod·volume·endpoint 0개, 30일 지출 $0, 잔액 $9.81, 등록 SSH 키 = 로컬 키 |
| 17:55 | 사용자 승인 "A40로 승인" | 상한 5h · $3.50, 컷오프 22:59 |
| 17:59:55 | create-pod → read-back | A40 · CA-MTL-1 · $0.59/h · `ssh.direct`(공인 IP + 매핑 포트) 할당 확인 |
| 18:01 | 호스트 키 지문 대조 | ED25519 `SHA256:ma/Bi1pY…JpYg` — 부팅 로그와 `ssh-keyscan` 일치 |
| 18:02 | 1 MiB scp 왕복 | SHA256 3개(로컬·Pod·회수본) 일치 |
| 18:03 | 자동 정지 감시 시도 | Pod 안 `runpodctl`(1.14.15)이 Pod 키로 Unauthorized → 세션 알림(22:47)으로 대체 |
| 18:05 | SSH 터널 | Pod 8001은 이미지의 nginx가 점유 → 18001 사용. 응답 SHA256 일치, 공인 IP에서 접근 불가 |
| 18:06 | 번들 업로드 | 코드·manifest·자체 데이터·동결 어댑터 745개 파일, tgz SHA256 일치 |
| 18:07 | 환경 설치 (`uv`) | Python 3.11.9 venv에 `requirements-ml.lock.txt` 그대로. lockfile 대비 차이는 리눅스 전용 CUDA 런타임 휠·triton·hf-xet 추가뿐 |
| 18:07 | 고정 다운로드 + 해시 | 모델 `model.safetensors` = 동결 SHA256, 공개 샤드 2개 = 동결 SHA256 ([`pod_fetch.json`](pod_fetch.json)) |
| 18:07 | 마스크 감사 | 360/360 통과 (공개 200 · 자체 160, 확장 이미지 토큰 포함) |
| 18:08 | 입력 해시 대조 | 모델 11/11 · manifest 4/4 · 자체 이미지·정답 256/256 · 샤드 2/2 · Pod에서 새로 추출한 공개 학습 이미지 200/200 · 동결 어댑터 3/3 모두 일치 ([`inventory_pod.json`](inventory_pod.json)) |
| 18:08 | smoke 10 step | 통과: gradient 유한, LoRA 텐서 112/112 변경, 저장→재로드 텐서 일치, 재로드 추론 schema 유효. 7.53 s/step (로컬 7.97). 로컬 smoke와 step별 loss 차이 최대 0.0021 |
| 18:10–18:20 | 본 학습 80 step | 620초 (로컬 1,308초), peak VRAM 6.52GB(로컬과 같음). 아래 기준 전부 통과 |
| 18:21–18:24 | 추론 parity (dev 8건) | 아래 표 |
| 18:25–18:28 | vLLM 0.11.2 기동 | `base` + LoRA `m1`(로컬 동결) + `m1pod`(Pod 학습), 127.0.0.1:18001 |
| 18:28 | 터널 경유 API 요청 | 로컬 → `m1pod` 1건 성공 (10.6초, 첫 요청) |
| 18:29–18:40 | vLLM 벤치 | 아래 표 |
| 18:41 | 백업 | 12MB tgz SHA256 일치, 매니페스트 32개 파일 전부 일치, JSON 17개 파싱 |
| 18:42 | 복원 확인 | Pod 어댑터를 로컬 4070 Ti SUPER에 로드 → dev 2건 출력이 Pod와 글자 단위로 동일 |
| 18:43:19 | delete-pod → 확인 | list-pods 0개, network volume 0개, 콘솔 지출률 $0.000/hr |

## 학습 비교 — 기준은 Pod 결과가 나오기 전에 고정

| 기준 | 로컬 (4070 Ti SUPER · Windows) | Pod (A40 · Linux) | 판정 |
|---|---:|---:|---|
| (a) step 1 loss 상대 차이 ≤ 2 % | 0.3643 | 0.3641 | 통과 (0.05 %) |
| (b) 80 step 평균 loss 상대 차이 ≤ 10 % | 0.048715 | 0.048569 | 통과 (0.3 %) |
| (c) 마지막 10 step 평균 절대 차이 ≤ 0.01 | 0.00884 | 0.00882 | 통과 (0.00002) |
| (d) 학습됨: 마지막 10 ≤ step 1의 10 % | — | 2.4 % | 통과 |
| (e) 구조: micro-step 641 mask 재검사, 학습 파라미터 1,605,632 (텐서 112, 언어 q/v LoRA만, vision 0), smoke 재로드 일치 | 같음 | 같음 | 통과 |

step별 최대 |Δ| = 0.0020. 원본: [`train_compare.json`](train_compare.json), [`train_m1_pod_a40.json`](train_m1_pod_a40.json).
Pod 어댑터 `adapter_model.safetensors` SHA256 `d8103a22…6337d4d` (로컬 동결 어댑터 `eb086741…ff2868`과는 다름 — GPU가 달라 비트 단위 동일은 기대하지 않음).

## 추론 parity — 자체 dev 앞 8건, HF NF4 기준 경로, batch 1, greedy

| 비교 | 필드 정확도 | 원문 동일률 |
|---|---:|---:|
| 로컬 동결 어댑터 · 로컬 (기존 `m1_dev_v1`) | 200/204 = 0.980 | 기준 |
| 로컬 동결 어댑터 · Pod | 200/204 = 0.980 | 7/8 — 다른 1건은 값이 모두 같고 JSON 키 순서만 다름(`items` 위치) |
| Pod 학습 어댑터 · Pod | 200/204 = 0.980 | 8/8 |
| Pod 학습 어댑터 · 로컬 (복원 확인) | — | 2/2 (Pod 출력과 비교) |

원본: [`parity_dev8.json`](parity_dev8.json), [`restore_local_load.json`](restore_local_load.json), [`predictions/`](predictions).

## vLLM 0.11.2 서빙 — 자체 dev 20건, max_tokens 1536, warmup 3, 반복 2

| 모델 | 동시성 | 문서/분 | p50 | p95 | 실패 |
|---|---:|---:|---:|---:|---:|
| M0 base (bf16) | 1 | 18.2 | 3.08 s | 5.25 s | 0/40 |
| | 2 | 34.0 | 3.25 s | 5.48 s | 0/40 |
| | 4 | 62.7 | 3.46 s | 5.84 s | 0/40 |
| | 8 | 104.8 | 3.89 s | 6.50 s | 0/40 |
| M1 LoRA `m1` (bf16 base) | 1 | 24.3 | 2.24 s | 4.17 s | 0/40 |
| | 2 | 47.1 | 2.26 s | 4.23 s | 0/40 |
| | 4 | 87.7 | 2.40 s | 4.39 s | 0/40 |
| | 8 | 149.3 | 2.62 s | 4.90 s | 0/40 |

비교: 로컬 자체 Transformers+PEFT 서버(NF4, 직렬 워커)는 M1 동시성 1에서 4.0 문서/분, p50 16.1 s였다 (다른 GPU·다른 정밀도라 속도 비교는 참고용).
GPU 메모리 36.1GB는 `--gpu-memory-utilization 0.82`로 KV 캐시를 미리 잡은 값이다 (모델 4.27GiB, KV 캐시 28.09GiB).

**정확도 차이 (같은 20건, strict 필드)**
- M0: vLLM bf16 **0.969** vs HF NF4 0.941
- M1: vLLM bf16 **0.849** vs HF NF4 0.960, 원문 동일률 5 %
- M1은 vLLM에서 **20건 모두 정확히 4필드씩** 틀렸다. vLLM 출력이 HF 출력보다 문서마다 37–53토큰 짧고, 이는 문서 합계 블록(`subtotal_raw` · `tax_raw` · `discount_raw` · `total_raw`, 약 43토큰) 길이와 같다. 그래서 합계 4필드가 빠진 것으로 보인다.
- 다만 이번 벤치는 원문 응답을 저장하지 않아 확정하지 못했다(스크립트는 이후 원문을 저장하도록 수정함).
- 원인도 확정하지 못했다. 가장 유력한 후보는 정밀도 불일치다: 어댑터는 NF4로 양자화된 기본 모델 위에서 학습했지만 vLLM은 bf16 기본 모델에 붙였다. vLLM의 packed qkv LoRA 처리도 후보다.
- 따라서 이 vLLM 수치는 **속도 측정**으로만 쓰고, LoRA 서빙 품질은 미해결로 둔다.

원본: [`../serving/vllm_bf16_a40.json`](../serving/vllm_bf16_a40.json), 로그 [`logs/`](logs).

## 한계
- seed 1개, 학습 1회. dev parity는 8건, 복원 확인은 2건.
- Pod 안 자동 정지는 권한 문제로 걸지 못했다. 이번에는 사람이 지켜보는 동안 43분 만에 끝났다.
- vLLM에서 LoRA 정확도 저하(위)는 원인 미확정. NF4 기본 모델로 vLLM을 띄우거나 어댑터를 병합한 비교는 하지 않았다(not_run).
- final 테스트 세트는 Pod에서 쓰지 않았다(dev만).
