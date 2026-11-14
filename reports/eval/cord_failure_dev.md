---
type: report
title: CORD dev 실패 유형 (arm별)
description: 정답에 값이 있는 칸을 일치·형식만 다름·틀림·빠뜨림으로, 정답에 없는 칸을 지어냄으로 나눈 표. dev만 사용.
generated: {by: scripts/realdocs/cord_failure_report.py}
---

# CORD dev 실패 유형

칸 = 개수 (일치 / 형식만 다름 / 틀림 / 빠뜨림). 채점 정규화는 사전 고정 채점기(`cord_eval.py`)와 같습니다. test는 보지 않았습니다.

| 필드 | M0 | M1 v1 | M1-cord |
|---|---|---|---|
| item.name | 159 / 4 / 55 / 2 | 87 / 3 / 24 / 106 | 164 / 7 / 38 / 11 |
| item.count | 168 / 27 / 11 / 4 | 40 / 63 / 7 / 100 | 189 / 4 / 8 / 9 |
| item.unit_price | 41 / 3 / 4 / 2 | 23 / 2 / 4 / 21 | 34 / 4 / 2 / 10 |
| item.price | 189 / 15 / 14 / 2 | 93 / 13 / 7 / 107 | 177 / 20 / 11 / 12 |
| sub.name | 10 / 0 / 0 / 39 | 21 / 0 / 6 / 22 | 14 / 0 / 7 / 28 |
| sub.count | 1 / 0 / 0 / 31 | 15 / 3 / 0 / 14 | 8 / 0 / 0 / 24 |
| sub.price | 4 / 0 / 0 / 10 | 8 / 0 / 0 / 6 | 3 / 0 / 0 / 11 |
| doc.subtotal | 49 / 6 / 2 / 10 | 6 / 2 / 0 / 59 | 56 / 5 / 2 / 4 |
| doc.tax | 23 / 3 / 13 / 8 | 2 / 1 / 1 / 43 | 34 / 2 / 10 / 1 |
| doc.total | 73 / 7 / 6 / 12 | 11 / 3 / 1 / 83 | 88 / 9 / 1 / 0 |

**정답에 없는 칸을 채운 수 (지어냄)**

| 필드 | M0 | M1 v1 | M1-cord |
|---|---|---|---|
| doc.subtotal | 31 | 7 | 0 |
| doc.tax | 44 | 11 | 1 |
| doc.total | 2 | 0 | 2 |
| item.count | 6 | 4 | 0 |
| item.price | 1 | 1 | 1 |
| item.unit_price | 160 | 85 | 20 |
| sub.count | 9 | 9 | 0 |
| sub.name | 0 | 0 | 0 |
| sub.price | 6 | 19 | 0 |
| sub.unit_price | 10 | 27 | 0 |

**행 구조**

| | M0 | M1 v1 | M1-cord |
|---|---|---|---|
| 정답 품목 행 | 221 | 221 | 221 |
| 예측 품목 행 | 300 | 123 | 237 |
| 행을 덜 낸 문서 | 2 | 53 | 6 |
| 행을 더 낸 문서 | 27 | 5 | 6 |
| 정답 하위 품목 | 50 | 50 | 50 |
| 예측 하위 품목 | 10 | 62 | 27 |

**인쇄된 단가를 행은 냈는데 null로 둔 경우 (유형별)**

| 유형 | M0 | M1 v1 | M1-cord |
|---|---|---|---|
| other | 0 | 0 | 1 |
| unit price equals the line total (printed twice) | 1 | 0 | 5 |
| unit price put in the price field ('@…') | 0 | 0 | 2 |
