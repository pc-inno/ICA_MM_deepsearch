#!/usr/bin/env python3
"""LLM-as-a-judge scorer for ICA/MM deepsearch JSONL results.

The input JSONL is expected to contain at least:
  - question
  - answer (gold answer)
  - prediction (model output)

Each output line preserves the input fields and appends:
  - judge_model
  - judge_score: 1 for correct/equivalent, 0 for incorrect, null on judge error
  - judge_verdict: "correct" / "incorrect" / "error"
  - judge_reason
  - judge_raw
  - judge_error

Example:
  HERMES_API_KEY=... HERMES_BASE_URL=https://tokenhub.sensetime.com/v1 \
  python llm_judge.py --input outputs/bc_zh_results.jsonl --output outputs/bc_zh_judged.jsonl
"""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from threading import Lock
from typing import Any

from openai import OpenAI
from tqdm import tqdm


DEFAULT_BASE_URL = "https://tokenhub.sensetime.com/v1"
DEFAULT_MODEL = "bailian/deepseek-v4-flash"

SYSTEM_PROMPT = """你是一个严格但公平的问答评测裁判。你的任务是判断模型预测是否回答了题目，并且是否与标准答案语义等价。

评分规则：
- 只给 1 或 0。
- 若预测最终答案与标准答案语义等价、同名别称等价、或包含标准答案且没有互相矛盾的最终答案，给 1。
- 若预测最终答案错误、缺失、拒答、多个互斥答案无法确定、或关键实体/数值不匹配，给 0。
- 只评判最终答案，不因为推理过程冗长而扣分；但若推理过程和最终答案冲突，以明确的最终答案为准。
- 不要使用外部搜索；只能依据题目、标准答案、预测内容和常识判断等价性。

必须只输出一个 JSON 对象，不要输出 Markdown：
{"score": 0 或 1, "verdict": "correct" 或 "incorrect", "reason": "一句中文理由"}
"""


def read_jsonl(path: Path, limit: int = 0) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for i, line in enumerate(f, 1):
            if limit and len(items) >= limit:
                break
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON at {path}:{i}: {exc}") from exc
            obj.setdefault("id", i - 1)
            items.append(obj)
    return items


def load_done_ids(path: Path) -> set[str]:
    done: set[str] = set()
    if not path.exists():
        return done
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            done.add(str(obj.get("id")))
    return done


def strip_think(text: str) -> str:
    # Some rollouts include leaked thinking tags. Keep the final answer while removing
    # complete <think> blocks to reduce judge prompt size.
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = text.replace("</think>", "")
    return text.strip()


def tail_text(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return text[-max_chars:]


def make_user_prompt(item: dict[str, Any], max_prediction_chars: int) -> str:
    question = str(item.get("question") or item.get("prompt") or "")
    answer = str(item.get("answer") or "")
    prediction = str(item.get("prediction") or "")
    prediction = tail_text(strip_think(prediction), max_prediction_chars)
    return (
        "请判断下面预测答案是否等价于标准答案。\n\n"
        f"[题目]\n{question}\n\n"
        f"[标准答案]\n{answer}\n\n"
        f"[预测答案]\n{prediction}\n"
    )


def parse_judge_json(text: str) -> dict[str, Any]:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        obj = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if not match:
            raise
        obj = json.loads(match.group(0))

    score = obj.get("score")
    if isinstance(score, str):
        score = score.strip()
        if score in {"1", "正确", "correct", "true", "True"}:
            score = 1
        elif score in {"0", "错误", "incorrect", "false", "False"}:
            score = 0
    score = 1 if score == 1 else 0
    verdict = obj.get("verdict") or ("correct" if score else "incorrect")
    if verdict not in {"correct", "incorrect"}:
        verdict = "correct" if score else "incorrect"
    return {
        "score": score,
        "verdict": verdict,
        "reason": str(obj.get("reason") or obj.get("explanation") or "").strip(),
    }


def judge_one(
    client: OpenAI,
    item: dict[str, Any],
    model: str,
    max_prediction_chars: int,
    max_retries: int,
) -> dict[str, Any]:
    last_error = ""
    for attempt in range(1, max_retries + 1):
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": make_user_prompt(item, max_prediction_chars)},
                ],
                temperature=0,
                response_format={"type": "json_object"},
            )
            raw = resp.choices[0].message.content or ""
            parsed = parse_judge_json(raw)
            return {
                **item,
                "judge_model": model,
                "judge_score": parsed["score"],
                "judge_verdict": parsed["verdict"],
                "judge_reason": parsed["reason"],
                "judge_raw": raw,
                "judge_error": None,
            }
        except Exception as exc:  # noqa: BLE001 - CLI should record per-item failures.
            last_error = f"{type(exc).__name__}: {exc}"
            if attempt < max_retries:
                time.sleep(min(2 ** attempt, 8))
    return {
        **item,
        "judge_model": model,
        "judge_score": None,
        "judge_verdict": "error",
        "judge_reason": "",
        "judge_raw": "",
        "judge_error": last_error,
    }


def summarize(path: Path) -> dict[str, Any]:
    total = correct = incorrect = errors = skipped_malformed = 0
    by_type: dict[str, dict[str, int]] = {}
    with path.open("r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, 1):
            if not line.strip():
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError as exc:
                skipped_malformed += 1
                print(f"Warning: skipping malformed JSONL record at {path}:{line_no}: {exc}", file=sys.stderr)
                continue
            total += 1
            typ = str(obj.get("type", ""))
            bucket = by_type.setdefault(typ, {"total": 0, "correct": 0, "incorrect": 0, "errors": 0})
            bucket["total"] += 1
            if obj.get("judge_score") == 1:
                correct += 1
                bucket["correct"] += 1
            elif obj.get("judge_score") == 0:
                incorrect += 1
                bucket["incorrect"] += 1
            else:
                errors += 1
                bucket["errors"] += 1
    return {
        "total": total,
        "correct": correct,
        "incorrect": incorrect,
        "errors": errors,
        "skipped_malformed": skipped_malformed,
        "accuracy": (correct / (total - errors)) if total > errors else None,
        "by_type": by_type,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Score JSONL QA predictions with an OpenAI-compatible LLM judge.")
    parser.add_argument("--input", required=True, help="Input JSONL with question/answer/prediction fields")
    parser.add_argument("--output", required=True, help="Output judged JSONL")
    parser.add_argument("--model", default=DEFAULT_MODEL, help=f"Judge model (default: {DEFAULT_MODEL})")
    parser.add_argument("--api-base", default=os.getenv("HERMES_BASE_URL") or os.getenv("OPENAI_BASE_URL") or DEFAULT_BASE_URL)
    parser.add_argument("--api-key", default="sk-2f8nSdpTYtOEvTOraocJ3dY4jDinlHRqRgxp3974pwgbbvkp")
    parser.add_argument("--concurrency", type=int, default=8)
    parser.add_argument("--limit", type=int, default=0, help="Only judge first N input rows")
    parser.add_argument("--resume", action="store_true", help="Skip ids already present in output")
    parser.add_argument("--max-prediction-chars", type=int, default=12000)
    parser.add_argument("--max-retries", type=int, default=3)
    args = parser.parse_args()

    if not args.api_key:
        print("Missing API key: set HERMES_API_KEY or OPENAI_API_KEY, or pass --api-key", file=sys.stderr)
        return 2

    input_path = Path(args.input)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    items = read_jsonl(input_path, limit=args.limit)
    if args.resume:
        done = load_done_ids(output_path)
        items = [item for item in items if str(item.get("id")) not in done]

    print(f"Loaded {len(items)} items from {input_path}")
    print(f"Judge model: {args.model}")
    print(f"Output: {output_path}")
    if not items:
        if output_path.exists():
            print(json.dumps(summarize(output_path), ensure_ascii=False, indent=2))
        return 0

    client = OpenAI(base_url=args.api_base, api_key=args.api_key)
    lock = Lock()

    # A shared JSONL output must never be written by two judge processes at
    # once: separate file descriptors can otherwise create zero-filled holes
    # and corrupt the line-oriented output.
    with output_path.open("a+", encoding="utf-8") as fout:
        try:
            fcntl.flock(fout.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print(f"Judge output is already being written: {output_path}", file=sys.stderr)
            return 2
        if not args.resume:
            fout.seek(0)
            fout.truncate()
        with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
            futures = [
                pool.submit(judge_one, client, item, args.model, args.max_prediction_chars, args.max_retries)
                for item in items
            ]
            for future in tqdm(as_completed(futures), total=len(futures), desc="judging"):
                result = future.result()
                with lock:
                    fout.write(json.dumps(result, ensure_ascii=False) + "\n")
                    fout.flush()

    summary = summarize(output_path)
    summary_path = output_path.with_suffix(output_path.suffix + ".summary.json")
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"Summary written to {summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
