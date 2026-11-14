# 커밋 이력 재작성 기록 (2026-11-14)

저장소를 공개하기 전에, 사용자 요청에 따라 모든 커밋의 작성자·커미터 이메일을 GitHub noreply 주소로 바꿨습니다.
바뀐 것은 커밋의 이메일 필드뿐이며, 25개 커밋 모두 파일 트리(tree 해시)가 재작성 전과 같습니다.
재작성 전 저장소는 삭제했고, 같은 이름의 공개 저장소에 재작성된 이력만 올렸습니다.

이 시점 이전에 쓰인 기록(`reports/`, `configs/frozen_v1.json`, `configs/frozen_v1_appendix.json`의 `git_commit`)에 나오는
커밋 해시는 재작성 **전** 값입니다. 동결 파일은 해시 가드 대상이라 고치지 않았고, 아래 대응표로 새 해시를 찾을 수 있습니다.
동결 검사(`python -m invoiceguard.freeze verify`)는 파일 해시만 비교하므로 이 재작성의 영향을 받지 않습니다.

| 재작성 전 | 재작성 후 | 날짜 | 커밋 |
|---|---|---|---|
| `9ba61fd8` | `112de44f` | 2026-11-14 | Initial import: package v4 + T00-T02a local implementation |
| `9cdb428f` | `fb18bd0e` | 2026-11-14 | Pin LF line endings so manifest and checksum hashes stay reproducible |
| `7749915d` | `4155f6b6` | 2026-11-14 | T02 complete: synthetic Invoice-PO renderer, evaluator, admin dashboard |
| `d3213494` | `b234487e` | 2026-11-14 | Write manifests and reports with LF so SHA-256 matches a clean checkout |
| `2c280ea1` | `f6a94224` | 2026-11-14 | Local GPU QLoRA smoke, sidebar admin dashboard with data views |
| `0a1cd6e5` | `7f7d3075` | 2026-11-14 | S1: v5 contract (docs/19), metric contract v2, GitHub Actions CI |
| `4a7cec19` | `ddfdda36` | 2026-11-14 | S2: freeze profile/manifests/prompts/generation (configs/frozen_v1.json) |
| `c7f3e960` | `9d060c2d` | 2026-11-14 | S3: freeze B0 OCR baseline v1.1 (Tesseract in Docker + generic layout heuristics) |
| `ceb52130` | `661ae1cb` | 2026-11-14 | Fix B0 OCR cache collision: key preprocess/TSV files by record_id |
| `41d60e91` | `c76ec43e` | 2026-11-14 | S5 prep: failure-analysis tool for dev runs; S3 results recorded |
| `4d79c755` | `fea467bc` | 2026-11-14 | S8 (partial): minimal review API (FastAPI + SQLite, loopback) with CAS and snapshot export |
| `5fa0793d` | `3af49890` | 2026-11-14 | Address Fable mid-course review blockers before any final run |
| `6b64305b` | `31e74a9b` | 2026-11-14 | S5: dev results for B0/M0/M1 (per set, paired CIs), failure analysis, train-only augmentation for M1 v2 |
| `dc352f2a` | `87746920` | 2026-11-14 | Freeze: reports/ outputs excluded from the clean-tree rule; dev summary table fix |
| `65719427` | `37ca1357` | 2026-11-14 | S5 outcome: M1 v2 augmentation had no dev effect; keep M1 v1 (pre-registered rule) |
| `622c22c7` | `414eaa6e` | 2026-11-14 | freeze: ASCII console message |
| `7c5b7f8a` | `65ebb039` | 2026-11-14 | S7 freeze appendix: code/adapter/OCR image/manifest hashes before any final run |
| `a9c8cb08` | `14607202` | 2026-11-14 | Dashboard: show recorded dev/final evaluations (per set) and paired differences |
| `ccc1f412` | `50f19ceb` | 2026-11-14 | S7: final results (B0/M0/M1, once, frozen) with paired CIs and E3 |
| `25a4f85a` | `1b5ad03b` | 2026-11-14 | S6/S8: HF+PEFT serving server with real timeout cancellation, live E2E demo, README, backup |
| `05581308` | `cdf94fa1` | 2026-11-14 | Final review fixes (Fable): honest README claims, final handoff and status |
| `f23df966` | `08f46223` | 2026-11-14 | Record user decision: no RunPod and no driver update (vLLM stays blocked, cloud not_run) |
| `cff82c0c` | `421a97e9` | 2026-11-14 | Dashboard: light/dark theme toggle (remembered per browser, follows OS by default) |
| `4f2a81b2` | `1bb0cf61` | 2026-11-14 | Dashboard: dark by default, favicon, redesigned layout and record-driven charts |
| `beb3c4a8` | `eff4d85e` | 2026-11-14 | README: portfolio rewrite with dashboard screenshots, data by type, charts and diagrams |
