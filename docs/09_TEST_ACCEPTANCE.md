# 09. 테스트·인수 기준 v3
아래는 Claude Code가 구현 후 실행해야 하는 카탈로그다. 문서/fixture 검사만 실행된 상태와 앱/GPU 결과를 혼동하지 않는다.

## 데이터/학습
| ID | 검사 | 통과 기준 |
|---|---|---|
| D01 | 실제 source 다운로드/12개 시각검사/전체프로필 | 증거·revision·표본/전체 수 분리 |
| D02 | source 숫자→canonical label | 원문표기 정답으로 가정하지 않음 |
| D03 | SKU·미관측·비가시·null 라벨 | 무근거 필드/0/기본수량 생성 금지 |
| D04 | 같은 file_name·content·품질·scenario family | split 교집합0 |
| D05 | 합성 6 layout/표시문자열/이미지크기 | 구조 차이, 렌더값 일치, 잘린 행 없음 |
| D06 | PO/정답/filename 입력 경계 | 모델 요청에 이미지+고정task prompt만 |
| D07 | 고정profile/test manifest | 예측 전에 freeze, 후선택 없음 |
| M01 | expanded-token loss mask | prompt/image/pad -100, answer nonzero |
| M02 | module/gradient/update | 언어 LoRA만, 실제 변경·finite |
| M03 | 10step와 본학습 구분 | smoke 후base reset, 실제 optimizer step 기록 |
| M04 | 동일 M0/M1 정밀도·모든 final split | 비교조건 동일, 실제 두 예측 존재 |
| M05 | adapter 재로드/live API | 올바른base revision/adapter hash, 실제추론 |
| M06 | 출력잘림·OOM·timeout | 실패 분모와 원본응답 보존 |

## 규칙·평가
| ID | 사례 | 기대 |
|---|---|---|
| B01 | SKU000125 vs125 | 다름, leading zero 보존 |
| B02 | public 숫자2.5 vs"2.50" | numeric 정답, raw EM 아님 |
| B03 | PO2.50 / invoice2.75 / qty100 / amount275 | UNIT_PRICE_DIFF만, 산술오류 아님 |
| B04 | quantity100 vs90 | QTY_DIFF |
| B05 | 다른SKU / PO행미등장 | UNKNOWN_SKU / PO_LINE_NOT_FOUND |
| B06 | 같은SKU두행 | DUPLICATE_SKU, 자동합치기 금지 |
| B07 | 2 cartons /100 pcs | AMBIGUOUS_QUANTITY, 강제100금지 |
| B08 | 제품 유럽숫자1.234,50 | AMBIGUOUS_NUMBER/지원밖 |
| B09 | USD아닌통화 또는$단독 | UNSUPPORTED_CURRENCY 등, 추측금지 |
| B10 | BOX와EA | UNIT_MISMATCH |
| B11 | 잘못된라인/총액 | 산술 warning; 원문값 자동수정 금지 |
| B12 | 필수값null | MISSING_CRITICAL_FIELD |
| E01 | 전체 실패 응답 | 분모 유지·null/실패 코드 표시 |
| E02 | oracle vs live | 다른source, score표 분리 |
| E03 | 없는reason enum | 스키마·지표 검사 실패 |
| E04 | 품질3종 반복 | 독립문서 n은base 수 |
| E05 | precision 분모0 /0건오류 | null/표본수 표시, 안전보장 금지 |

## 앱·운영
| ID | 검사 | 기대 |
|---|---|---|
| A01 | 미승인export | 409 |
| A02 | 미해결warning/blocker 승인 | 422 |
| A03 | 승인후수정/PO재연결 | 이전승인 무효 |
| A04 | stale approval/늦은추론 | 덮어쓰기 없음, 409/이력보관 |
| A05 | extracting 중 중복request | 동시GPU실행 방지 |
| A06 | 강제timeout 후 | worker 정리확인 전신규추론 차단 |
| A07 | 모델없음/네트워크단절 | 503/명시적실패, fixture자동대체 없음 |
| A08 | 이미지/path/HTML/CSV/문서지시문 공격 | 제한/escape, 명령실행없음 |
| O01 | FullSSH+scp roundtrip | 파일해시 일치 |
| O02 | actual quote/profile 계산 | 승인상한 안, 계산기는실제정지장치가아님 |
| O03 | adapter·raw·manifest백업복구 | 해시+파싱·가능시실제로드 |
| O04 | stop/terminate 뒤 리소스 | GPU상태와잔여volume과금확인 |

## 최종 인수
G0–G7은 [런타임 게이트](16_RUNTIME_RELEASE_GATES.md)의 증거로만 pass 처리한다. CPU CI의 GPU skip은 정직한 상태이나 release GPU gate를 통과시켜주지 않는다. 미측정 수치는 null/not_run이다.
