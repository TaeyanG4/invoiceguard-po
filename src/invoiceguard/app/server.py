"""Run the review API on 127.0.0.1.

  python -m invoiceguard.app.server --mode unavailable
  python -m invoiceguard.app.server --mode replay --replay-run m1_dev_v1     # REPLAY_OF_SAVED_RUN, never LIVE
  python -m invoiceguard.app.server --mode live --model-url http://127.0.0.1:8001 --model m1
"""
from __future__ import annotations

import argparse
from pathlib import Path

import uvicorn

from .api import REPO, create_app
from .extractors import LiveHTTPExtractor, ReplayExtractor, UnavailableExtractor, image_sha_index


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["unavailable", "replay", "live"], default="unavailable")
    parser.add_argument("--replay-run")
    parser.add_argument("--model-url", default="http://127.0.0.1:8001")
    parser.add_argument("--model", default="m1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    if args.mode == "replay":
        from ..vlm.records import trade_records

        records = trade_records("standard_role", "dev") + trade_records("standard_role", "train")
        extractor = ReplayExtractor(REPO / "artifacts" / "predictions" / args.replay_run, image_sha_index(records))
    elif args.mode == "live":
        extractor = LiveHTTPExtractor(args.model_url, args.model)
    else:
        extractor = UnavailableExtractor()
    app = create_app(REPO / "artifacts" / "app" / "invoiceguard.sqlite", REPO / "artifacts" / "app" / "uploads", extractor)
    uvicorn.run(app, host="127.0.0.1", port=args.port, log_level="info")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
