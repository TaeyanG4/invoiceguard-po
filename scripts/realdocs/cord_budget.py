"""Token budget and loss-mask check for every CORD_RAW record (CPU only), run before any CORD training.

Every record is encoded with the same processor settings as training/inference; the verified collator checks
(prompt/image tokens masked, trained span decodes to the gold answer) must pass, no record may exceed the sequence
budget, and no gold answer may be longer than max_new_tokens (otherwise the model could never finish it).
Writes reports/realdocs/cord_budget.json.

Usage (.venv-ml): python scripts/realdocs/cord_budget.py
"""
from __future__ import annotations

import json
import time
from pathlib import Path

from invoiceguard.vlm.records import cord_records
from invoiceguard.vlm.sft import MAX_NEW_TOKENS, SEQUENCE_BUDGET, encode, load_processor

REPO = Path(__file__).resolve().parents[2]


def main() -> int:
    proc = load_processor()
    t0, out = time.time(), {}
    for split in ("train", "dev", "test"):
        recs = cord_records(split, train_only_eligible=(split == "train"))
        tot, ans, img, errs = [], [], [], 0
        for r in recs:
            e = encode(proc, r.image(), r.prompt(), r.answer)
            tot.append(e.n_total); ans.append(e.n_answer); img.append(e.n_image_tokens); errs += bool(e.check_errors)
        out[split] = {"n": len(recs), "max_total": max(tot), "max_answer": max(ans), "mean_answer": round(sum(ans) / len(ans), 1),
                      "image_tokens_min_max": [min(img), max(img)], "over_budget": sum(t > SEQUENCE_BUDGET for t in tot),
                      "answer_over_max_new_tokens": sum(a > MAX_NEW_TOKENS for a in ans), "mask_check_errors": errs}
    out["sequence_budget"], out["max_new_tokens"], out["seconds"] = SEQUENCE_BUDGET, MAX_NEW_TOKENS, round(time.time() - t0, 1)
    path = REPO / "reports" / "realdocs" / "cord_budget.json"
    path.write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(out, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
