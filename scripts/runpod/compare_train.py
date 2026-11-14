"""Compare a RunPod training report with the local frozen M1 run using the criteria fixed in
reports/RUNPOD_APPROVAL.md ("합격 기준 수정") BEFORE the Pod run produced any output.

Usage: python scripts/runpod/compare_train.py reports/runpod/train_m1_pod_a40.json
       [--local reports/model/train_m1_standard_v1.json] [--smoke reports/runpod/smoke_train_pod.json]
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def losses(report: dict) -> list[float]:
    return [row["loss"] for row in sorted(report["loss_log"], key=lambda r: r["step"])]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("pod")
    parser.add_argument("--local", default="reports/model/train_m1_standard_v1.json")
    parser.add_argument("--smoke")
    parser.add_argument("--out", default="reports/runpod/train_compare.json")
    args = parser.parse_args()
    pod = json.loads((REPO / args.pod).read_text(encoding="utf-8"))
    loc = json.loads((REPO / args.local).read_text(encoding="utf-8"))
    lp, ll = losses(pod), losses(loc)
    if len(lp) != len(ll):
        raise SystemExit(f"step count differs: pod {len(lp)} vs local {len(ll)}")
    m_p, m_l = statistics.mean(lp), statistics.mean(ll)
    t_p, t_l = statistics.mean(lp[-10:]), statistics.mean(ll[-10:])
    per_step = [{"step": i + 1, "local": a, "pod": b, "abs_diff": round(abs(a - b), 5)} for i, (a, b) in enumerate(zip(ll, lp))]
    tr = pod["trainable"]
    criteria = {
        "a_step1_rel_diff_le_2pct": {"local": ll[0], "pod": lp[0], "rel_diff": round(abs(lp[0] - ll[0]) / ll[0], 5),
                                     "pass": abs(lp[0] - ll[0]) / ll[0] <= 0.02},
        "b_mean80_rel_diff_le_10pct": {"local": round(m_l, 6), "pod": round(m_p, 6), "rel_diff": round(abs(m_p - m_l) / m_l, 5),
                                       "pass": abs(m_p - m_l) / m_l <= 0.10},
        "c_last10_abs_diff_le_0.01": {"local": round(t_l, 6), "pod": round(t_p, 6), "abs_diff": round(abs(t_p - t_l), 6),
                                      "pass": abs(t_p - t_l) <= 0.01},
        "d_learned_last10_le_10pct_of_step1": {"pod_step1": lp[0], "pod_last10": round(t_p, 6), "ratio": round(t_p / lp[0], 5),
                                               "pass": t_p <= 0.10 * lp[0]},
        "e_structure": {"micro_steps_checked": pod["micro_steps_checked"], "trainable_params": tr["trainable_params"],
                        "trainable_tensors": tr["trainable_tensors"], "unexpected_trainable": tr["unexpected_trainable"],
                        "visual_trainable": tr["visual_trainable"],
                        "pass": (pod["micro_steps_checked"] == loc["micro_steps_checked"]
                                 and tr["trainable_params"] == loc["trainable"]["trainable_params"]
                                 and tr["trainable_tensors"] == loc["trainable"]["trainable_tensors"]
                                 and not tr["unexpected_trainable"] and not tr["visual_trainable"])},
    }
    if args.smoke:
        smoke = json.loads((REPO / args.smoke).read_text(encoding="utf-8"))
        criteria["e_structure"]["smoke_pass"] = smoke.get("pass")
        criteria["e_structure"]["smoke_reload_tensor_equal"] = smoke.get("reload_tensor_equal")
        criteria["e_structure"]["pass"] = criteria["e_structure"]["pass"] and bool(smoke.get("pass"))
    result = {"pod_report": args.pod, "local_report": args.local, "pod_env": pod.get("env"), "local_env": loc.get("env"),
              "train_seconds": {"pod": pod["train_seconds"], "local": loc["train_seconds"]},
              "peak_vram_gb": {"pod": pod["peak_vram_gb"], "local": loc["peak_vram_gb"]},
              "criteria": criteria, "all_pass": all(c["pass"] for c in criteria.values()),
              "max_abs_step_diff": max(p["abs_diff"] for p in per_step), "per_step": per_step}
    out = REPO / args.out
    out.write_text(json.dumps(result, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({k: v for k, v in result.items() if k != "per_step"}, ensure_ascii=False, indent=1))
    return 0 if result["all_pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
