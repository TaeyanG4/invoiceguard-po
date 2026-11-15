---
type: report
title: 해상도 2.2 MP — dev 세트에서의 효과 (수정 8 b)
description: T07에서 한글 오독을 고친 max_pixels 2,200,000이 자체 dev · CORD dev에서도 안전한지. 저장된 예측만 사용.
generated: {by: scripts/eval/resolution_dev.py}
---

# 해상도 2.2 MP — dev 세트

판정 규칙(사전 고정): safe = point estimate not more than 0.01 lower AND CI lower bound above -0.02 on both sets; helps = CI above 0

| 세트 | 786,432 | 2,200,000 | 차이 [95% CI] | 초/문서 (2.2 MP) |
|---|---:|---:|---|---:|
| trade:dev (24 own invoices, layout T04) | 0.9682 | 0.9576 | -0.0106 [-0.0520, +0.0138] | 12.1 |
| cord:dev (100 receipts) | 0.7617 | 0.7627 | +0.0010 [-0.0312, +0.0282] | 5.9 |

판정: **not shown to be safe; helps on neither**

CORD dev 100장 중 71장이 786,432에서 축소되고, 2,200,000에서도 15장은 축소됩니다.
