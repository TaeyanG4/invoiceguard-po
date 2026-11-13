# 07. API 및 화면 설계

## 1. 화면 세 개

### A. 시작/문서 등록

모드 배지: `LIVE_MODEL` / `FIXTURE_DEMO` / `MODEL_UNAVAILABLE`. 모델명/adapter/버전 표시. PO JSON 등록, PO 선택, PNG/JPEG 업로드. 공개 영어 InvoiceOCR-Synth 연구평가는 별도 CLI/보고서로 분리한다. 원격 RunPod 모델 서버는 인증된 SSH 터널 등으로만 연결하며 외부 무인증 공개를 금지한다.

### B. 원문·추출·차이 검수

왼쪽 50%에 원문 전체와 확대. 오른쪽에 행별 표: 품번, 설명, 문서 수량, PO 수량, 문서 단가, PO 단가, 문서 금액, 사유. 아래에 판정 설명과 수정 이력. 색상만으로 의미를 전달하지 않고 `확인 필요`, `비교 불가`, `일치 후보` 텍스트를 함께 표시한다.

원문 bbox 자동 하이라이트는 P1. 예측하지 않은 위치를 그럴듯하게 만들어 표시하지 않는다. 원문은 전체 확대/스크롤로 확인한다.

읽기 오류를 수정하는 버튼과 실제 거래 차이를 확인하는 버튼을 구분한다. `2.75`가 원문 값이면 PO의 `2.50`으로 맞추지 않고 `거래 변경 확인` 사유를 남긴다.

### C. 승인·내보내기

현재 문서 버전, 기준 PO 버전, 미해결 이슈, 승인 체크를 보여 준다. 승인 전에는 JSON/CSV 내보내기 버튼이 비활성이고 서버도 차단한다. 수정하면 승인 배지가 즉시 사라진다.

## 2. API 계약

| Method/Path | 입력 | 출력/오류 |
|---|---|---|
| GET `/health` | 없음 | app/model readiness를 구분 |
| POST `/api/purchase-orders` | PO JSON | 201 id/version, 422 schema/duplicate SKU |
| GET `/api/purchase-orders` | 없음 | 선택 가능한 PO 요약 |
| POST `/api/cases` | multipart image + po_id + po_version | 201 case_id/version/state |
| POST `/api/cases/{id}/extract` | expected_version | 실제 추론 실행, 200 새 버전/결과; 409 stale, 429 busy, 503 model 없음, 504 timeout |
| GET `/api/cases/{id}` | 없음 | 현재 원문 참조/예측/대사/검수 상태 |
| GET `/api/cases/{id}/image` | 없음 | 검증된 로컬 이미지, path 입력 불가 |
| PUT `/api/cases/{id}/review` | expected_version, 수정 필드, reason | 200 새 버전, 이전 승인 무효; 409 stale |
| POST `/api/cases/{id}/approve` | expected_version, warning dispositions, reviewer_note | 200 승인; 409 version, 422 미해결 blocker/warning |
| POST `/api/cases/{id}/reject` | expected_version, reason | 200 rejected |
| GET `/api/cases/{id}/export?format=json|csv` | 없음 | 승인된 현재 버전만 200; 그 외 409 |

모든 ID는 서버 발급 UUID/검증된 PO ID다. 입력에서 임의 파일 경로/URL을 받지 않는다.

## 3. 오류 응답

```json
{
  "error": {
    "code": "APPROVAL_REQUIRED",
    "message": "현재 버전의 사람 승인이 필요합니다.",
    "request_id": "server-generated-uuid"
  }
}
```

서버 traceback, 사용자 파일 경로, API token, 전체 원문을 오류 응답에 노출하지 않는다.

## 4. 버전 및 동시 편집

모든 수정/승인/재추출 요청은 expected_version을 요구한다. SQLite transaction에서 현재 version과 비교 후 증가시킨다. 오래된 화면의 승인은 409. 이미 승인한 결과를 수정한 후 이전 export 링크를 새 데이터로 덮어쓰지 않는다. 각 파일은 승인 버전별로 보존한다.

## 5. 모델 호출

제품 API는 `Extractor.extract(image_bytes, document_hint)` 인터페이스를 사용한다. `document_hint`는 고정 지원 문서 유형일 뿐 PO 값/정답을 포함하지 않는다. `LiveExtractor`와 `FixtureExtractor`를 서로 다른 클래스/설정으로 분리한다. fixture는 명시적인 demo 모드에서만 사용하며 LIVE_MODEL 배지를 띄울 수 없다.

모델 API의 내부 형식이 OpenAI-compatible이어도 OpenAI 외부 서비스에 전송한다는 뜻은 아니다. SSH tunnel의 loopback 주소로 연결한 RunPod Transformers 서버만 P0에서 호출한다. 제품 태스크는 TRADE_RAW이며 PUBLIC_CANONICAL 연구출력을 제품 raw 결과로 바꾸지 않는다.

## 6. 기록

request_id, case_id, run_id, model revision, adapter hash, latency, status, error code는 기록한다. 원문 텍스트/이미지를 일반 console log에 쓰지 않는다. 모델 원문은 접근 제한된 artifact 파일로 보관한다.

## 7. 구현 전 추가 규약
[런타임 인수 게이트](16_RUNTIME_RELEASE_GATES.md)의 추출CAS, busy 상태, stale 응답, timeout cancellation, export snapshot 검사를 적용한다. 이 문서의 상태/HTTP 표만으로 구현을 완료했다고 판단하지 않는다.
