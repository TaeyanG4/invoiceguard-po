"""Batched, resumable HF inference that SAVES RAW RESPONSES FIRST (scoring happens later, separately).

Usage (.venv-ml):
  python -m invoiceguard.vlm.infer --arm m0 --set public:dev --set trade:dev [--run-id ...]
  python -m invoiceguard.vlm.infer --arm m1 --adapter artifacts/adapters/<run> --set ...
  python -m invoiceguard.vlm.infer --arm m0 --ids-file ids.txt          # explicit train-only diagnostics

Sets: public:<standard_role> (train|dev|dev_stress|iid_final|ood_final), trade:<split> (train|dev|test),
stress:<name> (dev-only stress images). Final sets require --allow-final and a matching frozen config.
Every attempted item stays in predictions.jsonl with generation_status (ok|oom|error) so denominators
never shrink. Re-running with the same run-id resumes and skips completed ids under the same config.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path

import torch

from ..extraction_request import load_prompt
from . import MODEL_REVISION, REPO
from .records import Record, cord_records, public_records, trade_records
from .sft import MAX_NEW_TOKENS, MAX_PIXELS, load_processor, user_messages

FROZEN = REPO / "configs" / "frozen_v1.json"
FINAL_SETS = {"public:iid_final", "public:ood_final", "trade:test"}


def resolve_set(spec: str) -> list[Record]:
    kind, name = spec.split(":", 1)
    if kind == "public":
        return public_records("standard_role", name)
    if kind == "trade" and name == "t07":  # docs/20 amendment 6: Korean-English mixed layout, dev-only stress set
        return trade_records("standard_role", "stress", manifest="trade_raw_t07.jsonl")
    if kind == "trade":
        return trade_records("standard_role", {"test": "test", "dev": "dev", "train": "train"}[name])
    if kind == "stress":
        from .stress import stress_records
        return stress_records(name)
    if kind == "cord":  # docs/20: dev = CORD validation, test = frozen once (configs/frozen_cord_v1.json)
        return cord_records({"train": "train", "dev": "dev", "test": "test"}[name], train_only_eligible=False)
    raise ValueError(spec)


NF4_PRECISION = "nf4_double_quant_bf16_compute_vision_unquantised_patch_embed_fp32"


def precision_label(precision: str) -> str:
    return NF4_PRECISION if precision == "nf4" else f"{precision}_base_vision_lm_head_unquantised_patch_embed_fp32"


def config_fingerprint(arm: str, adapter_sha: str | None, batch_size: int, precision: str = "nf4") -> dict:
    return {"arm": arm, "model_revision": MODEL_REVISION, "adapter_sha256": adapter_sha,
            "prompt_sha256": {t: load_prompt(t)[1] for t in ("PUBLIC_CANONICAL", "TRADE_RAW")},
            "max_pixels": MAX_PIXELS, "max_new_tokens": MAX_NEW_TOKENS, "do_sample": False,
            "precision": precision_label(precision), "batch_size": batch_size,
            "padding_side": "left"}


def check_frozen(fp: dict) -> list[str]:
    if not FROZEN.exists():
        return ["frozen_config_missing"]
    frozen = json.loads(FROZEN.read_text(encoding="utf-8"))
    errors = []
    for key in ("model_revision", "prompt_sha256", "max_pixels", "max_new_tokens", "do_sample", "precision",
                "batch_size", "padding_side"):
        if frozen["generation"].get(key) != fp.get(key):
            errors.append(f"frozen_mismatch:{key}")
    for name, digest in frozen["manifests_sha256"].items():
        if hashlib.sha256((REPO / "manifests" / name).read_bytes()).hexdigest() != digest:
            errors.append(f"manifest_changed:{name}")
    return errors


from ..cord_guard import FROZEN_CORD, check_cord_frozen, check_run_sets  # noqa: E402,F401 - torch-free, CPU-tested


class VariantPromptRecord(Record):
    """A record whose prompt is replaced (docs/20 amendment 4, CORD dev only); everything else is unchanged."""

    def __init__(self, record_id, task, image_path, answer, role, prompt_text: str):
        super().__init__(record_id, task, image_path, answer, role)
        self._prompt_text = prompt_text

    def prompt(self) -> str:
        return self._prompt_text


@torch.inference_mode()
def generate_batch(model, processor, records: list[Record]) -> list[dict]:
    texts = [processor.apply_chat_template(user_messages(r.prompt()), tokenize=False, add_generation_prompt=True)
             for r in records]
    images = [r.image() for r in records]
    inputs = processor(text=texts, images=images, return_tensors="pt", padding=True).to(model.device)
    torch.cuda.synchronize()
    start = time.perf_counter()
    out = model.generate(**inputs, max_new_tokens=MAX_NEW_TOKENS, do_sample=False, temperature=None, top_p=None, top_k=None)
    torch.cuda.synchronize()
    elapsed = time.perf_counter() - start
    eos = model.generation_config.eos_token_id
    eos = set(eos if isinstance(eos, list) else [eos])
    pad = processor.tokenizer.pad_token_id
    width = inputs["input_ids"].shape[1]
    results = []
    for i, rec in enumerate(records):
        new = out[i, width:]
        tokens = [int(t) for t in new]
        while tokens and tokens[-1] == pad and pad not in eos:
            tokens.pop()
        n_eff = len(tokens)
        stopped = any(t in eos for t in tokens)
        if stopped:
            tokens = tokens[: next(k for k, t in enumerate(tokens) if t in eos)]
        results.append({"id": rec.record_id, "task": rec.task, "generation_status": "ok",
                        "raw_response": processor.tokenizer.decode(tokens, skip_special_tokens=True),
                        "finish_reason": "stop" if stopped else ("length" if n_eff >= MAX_NEW_TOKENS else "unknown"),
                        "generated_tokens": len(tokens), "batch_size": len(records),
                        "batch_latency_s": round(elapsed, 3)})
    return results


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--arm", choices=["m0", "m1", "m1merged"], required=True,
                        help="m1merged = an adapter already merged into a saved base (--model-dir); exploratory dev only")
    parser.add_argument("--model-dir", help="load the base model from this folder instead of the pinned revision (m1merged)")
    parser.add_argument("--adapter")
    parser.add_argument("--set", action="append", default=[])
    parser.add_argument("--ids-file")
    parser.add_argument("--batch-size", type=int, default=None)
    parser.add_argument("--run-id")
    parser.add_argument("--allow-final", action="store_true")
    parser.add_argument("--limit", type=int, help="keep only the first N resolved records (parity spot checks)")
    parser.add_argument("--allow-precision-mismatch", action="store_true",
                        help="exploratory only (P3): load an adapter on a base precision it was not trained on; recorded in the run")
    parser.add_argument("--max-pixels", type=int, help="docs/20 amendment 7 (exploratory): image resize limit instead of the "
                                                    "frozen 786,432; dev/stress sets only, recorded in the run fingerprint")
    parser.add_argument("--prompt-file", help="docs/20 amendment 4 (exploratory): replace the CORD_RAW prompt with this file; "
                                                "cord:dev only, recorded in the run fingerprint")
    parser.add_argument("--precision", default="nf4", choices=["nf4", "int8", "bf16", "fp16", "fp32"],
                        help="base-model precision; anything but nf4 is an exploratory dev comparison and cannot run final sets")
    args = parser.parse_args()

    if (args.arm == "m1") != bool(args.adapter):
        raise SystemExit("m1 requires --adapter; m0 must not have one")
    if args.arm == "m1merged" and (not args.model_dir or args.adapter):
        raise SystemExit("m1merged requires --model-dir and no --adapter (the adapter is already merged)")
    if args.model_dir and args.arm == "m0":
        raise SystemExit("--model-dir is for m1merged or m1 on a dequantised base, not m0")
    adapter_sha = None
    if args.adapter:
        adapter_sha = hashlib.sha256((REPO / args.adapter / "adapter_model.safetensors").read_bytes()).hexdigest()
    frozen = json.loads(FROZEN.read_text(encoding="utf-8")) if FROZEN.exists() else None
    batch_size = args.batch_size or (frozen["generation"]["batch_size"] if frozen else 4)
    fp = config_fingerprint(args.arm, adapter_sha, batch_size, args.precision)
    if args.adapter:  # P15: the adapter must sit on the base precision it was trained on
        from .pairing import check as check_pairing

        pairing = check_pairing(REPO / args.adapter, args.precision, MODEL_REVISION,
                                REPO / args.model_dir if args.model_dir else None, args.allow_precision_mismatch)
        if pairing["mismatch_allowed"]:
            fp["adapter_pairing_mismatch_allowed"] = pairing["problems"]
    if args.model_dir:
        fp["model_dir"] = args.model_dir
    if args.max_pixels:
        if any(s in FINAL_SETS or s == "cord:test" for s in args.set):
            raise SystemExit("--max-pixels is exploratory: not for final sets or cord:test")
        fp["max_pixels"] = args.max_pixels
    prompt_override = None
    if args.prompt_file:
        if args.set != ["cord:dev"] or args.ids_file:
            raise SystemExit("--prompt-file is an exploratory CORD dev variant: use exactly --set cord:dev")
        raw = (REPO / args.prompt_file).read_bytes()
        prompt_override = raw.decode("utf-8")
        fp["prompt_variant"] = {"file": args.prompt_file, "sha256": hashlib.sha256(raw).hexdigest()}
    if any(s.startswith("cord:") for s in args.set):  # docs/20: CORD runs also pin the CORD prompt and manifest
        fp["cord_prompt_sha256"] = fp["prompt_variant"]["sha256"] if prompt_override else load_prompt("CORD_RAW")[1]
        fp["cord_manifest_sha256"] = hashlib.sha256((REPO / "manifests" / "cord_v2.jsonl").read_bytes()).hexdigest()
    if "cord:test" in args.set:
        problems = check_cord_frozen(fp, args.run_id)
        if problems or not args.allow_final:
            raise SystemExit(f"cord:test needs --allow-final and a matching configs/frozen_cord_v1.json: {problems}")
    if any(s in FINAL_SETS for s in args.set) and (args.arm == "m1merged" or args.precision != "nf4"):
        raise SystemExit("final sets run only the frozen reference (m0/m1, nf4); merged or other precisions are dev-only")
    if any(s in FINAL_SETS for s in args.set):
        from ..freeze import verify_final_ready

        problems = check_frozen(fp) + verify_final_ready({"fingerprint": fp})
        if problems or not args.allow_final:
            raise SystemExit(f"final sets need --allow-final and a matching frozen config: {problems}")

    records: list[Record] = []
    for spec in args.set:
        records += resolve_set(spec)
    if args.ids_file:
        wanted = set(Path(args.ids_file).read_text(encoding="utf-8").split())
        pool = public_records("standard_role", "train") + trade_records("standard_role", "train")
        records += [r for r in pool if r.record_id in wanted]
    if args.limit is not None:
        records = records[: args.limit]
    if prompt_override is not None:
        records = [VariantPromptRecord(r.record_id, r.task, r.image_path, r.answer, r.role, prompt_override) for r in records]
    run_id = args.run_id or f"{args.arm}_{time.strftime('%Y%m%d_%H%M%S')}"
    out_dir = REPO / "artifacts" / "predictions" / run_id
    out_dir.mkdir(parents=True, exist_ok=True)
    meta_path, pred_path = out_dir / "run_metadata.json", out_dir / "predictions.jsonl"
    if meta_path.exists():
        old = json.loads(meta_path.read_text(encoding="utf-8"))
        if old["fingerprint"] != fp:
            raise SystemExit("run-id exists with a different config; use a new run-id")
        sets_problem = check_run_sets(meta_path, args.set)
        if sets_problem:
            raise SystemExit(sets_problem)
    done = set()
    if pred_path.exists():
        done = {json.loads(l)["id"] for l in pred_path.read_text(encoding="utf-8").splitlines() if l.strip()}
    todo = [r for r in records if r.record_id not in done]

    from peft import PeftModel

    from .model import load_base
    from .smoke import _env

    processor = load_processor()
    processor.tokenizer.padding_side = "left"
    if args.max_pixels:
        processor.image_processor.size = {**processor.image_processor.size, "longest_edge": args.max_pixels}
    model = load_base(REPO / args.model_dir, precision=args.precision) if args.model_dir else load_base(precision=args.precision)
    if args.adapter:
        model = PeftModel.from_pretrained(model, str(REPO / args.adapter))
        model.eval()
    previous_attempts = json.loads(meta_path.read_text(encoding="utf-8")).get("attempt_ids", []) if meta_path.exists() else []
    meta = {"run_id": run_id, "fingerprint": fp, "sets": args.set, "ids_file": args.ids_file,
            "attempt_ids": sorted(set(previous_attempts) | {r.record_id for r in records}), "env": _env(),
            "started": time.strftime("%Y-%m-%dT%H:%M:%S"), "adapter": args.adapter}
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    torch.cuda.reset_peak_memory_stats()
    t0 = time.perf_counter()
    with pred_path.open("a", encoding="utf-8", newline="\n") as handle:
        for start in range(0, len(todo), batch_size):
            chunk = todo[start:start + batch_size]
            try:
                rows = generate_batch(model, processor, chunk)
            except Exception as batch_exc:  # noqa: BLE001 - every failure is recorded, never dropped
                torch.cuda.empty_cache()
                rows = []
                for rec in chunk:  # retry one by one
                    try:
                        rows += generate_batch(model, processor, [rec])
                    except Exception as exc:  # noqa: BLE001
                        torch.cuda.empty_cache()
                        status = "oom" if isinstance(exc, torch.cuda.OutOfMemoryError) else "error"
                        rows.append({"id": rec.record_id, "task": rec.task, "generation_status": status,
                                     "raw_response": None, "finish_reason": None, "generated_tokens": 0,
                                     "error": repr(exc)[:200], "batch_error": repr(batch_exc)[:200]})
            for row in rows:
                handle.write(json.dumps(row, ensure_ascii=False) + "\n")
            handle.flush()
            print(f"{start + len(chunk)}/{len(todo)} done, elapsed {time.perf_counter() - t0:.0f}s", flush=True)
    meta.update({"finished": time.strftime("%Y-%m-%dT%H:%M:%S"), "wall_seconds": round(time.perf_counter() - t0, 1),
                 "peak_vram_gb": round(torch.cuda.max_memory_allocated() / 2**30, 3), "newly_generated": len(todo)})
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"run_id": run_id, "items": len(records), "new": len(todo), "wall_s": meta["wall_seconds"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
