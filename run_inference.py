#!/usr/bin/env python3
"""
Batch inference runner for predict_qwen_search.

Usage:
    python run_inference.py \
        --input data/test.jsonl \
        --output outputs/results.jsonl \
        --api-base http://127.0.0.1:8000/v1 \
        --concurrency 4
"""

import argparse
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from threading import Lock

from openai import OpenAI

from inference import predict_qwen_search


def read_input(path: str, limit: int = 0) -> list[dict]:
    items = []
    with open(path, "r", encoding="utf-8") as f:
        for i, line in enumerate(f):
            if limit and i >= limit:
                break
            line = line.strip()
            if not line:
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            if "question" not in item and "prompt" not in item:
                continue
            item.setdefault("id", i)
            items.append(item)
    return items


def process_one(client: OpenAI, item: dict, think_mode: bool) -> dict:
    prompt = item.get("question") or item.get("prompt", "")
    item_id = item.get("id", "?")

    t0 = time.time()
    try:
        prediction, messages, should_retry, error = predict_qwen_search(
            client, prompt, think_mode=think_mode,
        )
        elapsed = time.time() - t0

        if should_retry and error:
            print(f"  [WARN] id={item_id} retry-flag set: {error} ({elapsed:.1f}s)")

        return {
            **item,
            "prediction": prediction,
            "trajectory": messages,
            "error": error,
            "should_retry": should_retry,
            "elapsed_s": round(elapsed, 2),
            "num_messages": len(messages) if messages else 0,
        }
    except Exception as e:
        elapsed = time.time() - t0
        print(f"  [ERROR] id={item_id}: {e} ({elapsed:.1f}s)")
        return {
            **item,
            "prediction": None,
            "error": str(e),
            "should_retry": True,
            "elapsed_s": round(elapsed, 2),
            "num_messages": 0,
        }


def main():
    parser = argparse.ArgumentParser(description="Batch inference with predict_qwen_search")
    parser.add_argument("--input", required=True, help="Input JSONL file (needs 'question' or 'prompt' field)")
    parser.add_argument("--output", required=True, help="Output JSONL file")
    parser.add_argument("--api-base", default="http://127.0.0.1:8000/v1", help="vLLM OpenAI-compatible API base URL")
    parser.add_argument("--api-key", default="dummy", help="API key (default: dummy for local vLLM)")
    parser.add_argument("--concurrency", type=int, default=4, help="Max concurrent requests")
    parser.add_argument("--limit", type=int, default=0, help="Only process first N items (0 = all)")
    parser.add_argument("--no-think", action="store_true", help="Disable thinking mode")
    args = parser.parse_args()

    if not os.path.exists(args.input):
        print(f"Error: input file not found: {args.input}")
        sys.exit(1)

    items = read_input(args.input, limit=args.limit)
    print(f"Loaded {len(items)} items from {args.input}")

    if not items:
        print("No items to process.")
        return

    client = OpenAI(base_url=args.api_base, api_key=args.api_key)
    think_mode = not args.no_think

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    write_lock = Lock()
    done = 0
    total = len(items)

    with open(output_path, "w", encoding="utf-8") as fout:
        with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
            futures = {
                pool.submit(process_one, client, item, think_mode): item
                for item in items
            }
            for future in as_completed(futures):
                result = future.result()
                with write_lock:
                    fout.write(json.dumps(result, ensure_ascii=False) + "\n")
                    fout.flush()
                    done += 1
                pred_preview = (result.get("prediction") or "")[:80]
                print(f"  [{done}/{total}] id={result.get('id')} elapsed={result.get('elapsed_s')}s | {pred_preview}...")

    print(f"\nDone: {done}/{total} items written to {args.output}")


if __name__ == "__main__":
    main()
