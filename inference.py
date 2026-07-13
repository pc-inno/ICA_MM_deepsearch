import json
import os
import re
import time
import traceback
from datetime import datetime

from openai.types.chat.chat_completion_message_tool_call import (
    ChatCompletionMessageToolCall,
    Function,
)
from mcp_tools.tools import (
    call_fetch_url_sync_img,
    fetch_page_tool_img,
    fetch_page_tool_dom,
    web_search,
    web_search_tool,
)

MAX_TOOL_CALLS = 250
MAX_DUPLICATE_QUERY_COUNT = 5
SUPPORTED_TOOLS = {"web_search", "fetch_url"}


def _build_safe_message(message) -> dict:
    """Extract only server-safe fields from a model message."""
    msg = message.model_dump(exclude_unset=True)
    safe = {"role": msg.get("role")}
    if msg.get("content") is not None:
        safe["content"] = msg["content"]
    if msg.get("tool_calls"):
        safe["tool_calls"] = msg["tool_calls"]
    return safe


def _extract_tool_calls_from_text(text):
    """
    Parse <tool_call>JSON</tool_call> blocks into OpenAI-compatible tool call objects.

    Returns (tool_calls_or_None, error_msg_or_None).
    """
    if not text:
        return None, None

    tool_calls = []
    for raw in re.findall(r"<tool_call>(.*?)</tool_call>", text, re.DOTALL):
        raw = raw.strip()
        try:
            obj = json.loads(raw)
        except json.JSONDecodeError as e:
            err = f"Tool JSON parse error: {e} | raw='{raw}'"
            print(f"[ERROR] {err}")
            return None, err

        tool_calls.append(
            ChatCompletionMessageToolCall(
                id=f"call_{len(tool_calls)}_{int(time.time())}",
                type="function",
                function=Function(
                    name=obj.get("name", ""),
                    arguments=json.dumps(obj.get("arguments", {}), ensure_ascii=False),
                ),
            )
        )

    return (tool_calls or None), None


VLLM_MODEL_NAME = os.environ.get("VLLM_MODEL_NAME", "Qwen3-VL-8B-A3B")
FETCH_STRATEGY = os.environ.get("FETCH_STRATEGY", "image")


def _generate(client, messages, *, think_mode=True):
    """Single model generation call."""
    fetch_tool_schema = fetch_page_tool_dom if FETCH_STRATEGY == "dom" else fetch_page_tool_img
    return client.chat.completions.create(
        max_tokens=8192,
        messages=messages,
        model=VLLM_MODEL_NAME,
        stream=False,
        temperature=1.0,
        tools=[web_search_tool, fetch_tool_schema],
        tool_choice="none",
        extra_body={
            "top_k": 20,
            "top_p": 0.95,
            "repetition_penalty": 1.05,
            "enable_thinking": think_mode,
        },
    )


def _handle_web_search(func_args, tool_call_id, search_ref_start_idx, recent_queries):
    """
    Execute web_search tool.

    Returns (tool_output_dict, updated_start_idx, error_or_None).
    On duplicate-query abort, error is non-None.
    """
    query_param = func_args.get("query", "")
    if isinstance(query_param, list):
        queries = query_param
    elif isinstance(query_param, str):
        queries = [query_param]
    else:
        queries = [str(query_param)]

    for q in queries:
        recent_queries.append(q)
        count = recent_queries.count(q)
        if count > MAX_DUPLICATE_QUERY_COUNT:
            err = f"Detected query '{q}' repeated {count} times. Aborting."
            print(f"[ERROR] {err}")
            return None, search_ref_start_idx, err

    call_start_idx = search_ref_start_idx
    all_results = []
    query_results_map = {}

    for qi, single_query in enumerate(queries):
        search_args = {k: v for k, v in func_args.items() if k != "query"}
        search_args["query"] = single_query
        search_args["start_idx"] = call_start_idx + len(all_results)
        try:
            result = web_search(**search_args)
            local_start = len(all_results)
            all_results.extend(result)
            query_results_map[qi] = {
                "query": single_query,
                "start_idx": call_start_idx + local_start,
                "end_idx": call_start_idx + len(all_results) - 1,
                "result_count": len(result),
            }
        except Exception as e:
            print(f"Error searching '{single_query}': {e}")
            query_results_map[qi] = {
                "query": single_query,
                "start_idx": call_start_idx + len(all_results),
                "end_idx": call_start_idx + len(all_results) - 1,
                "result_count": 0,
                "error": str(e),
            }

    response_dict = {}
    for i, part in enumerate(all_results):
        ref_idx = call_start_idx + i
        response_dict[f"<ref_{ref_idx}>"] = {
            "title": part.get("title", ""),
            "url": part.get("link", ""),
            "snippet": part.get("snippet", ""),
        }

    if len(queries) > 1:
        response_dict["_queries"] = queries
        response_dict["_query_results_map"] = query_results_map

    new_start_idx = search_ref_start_idx + len(all_results)
    output = {
        "role": "tool",
        "content": json.dumps(response_dict, ensure_ascii=False),
        "tool_call_id": tool_call_id,
    }
    return output, new_start_idx, None


def _handle_fetch_url(func_args, tool_call_id):
    """Fetch URL(s) and return tool output based on FETCH_STRATEGY."""
    url_arg = func_args.get("url", "")
    urls = url_arg if isinstance(url_arg, list) else ([url_arg] if url_arg else [])
    urls = [u for u in urls if u]

    if not urls:
        return {
            "role": "tool",
            "content": json.dumps({"error": "No valid URLs provided"}, ensure_ascii=False),
            "tool_call_id": tool_call_id,
        }

    result = call_fetch_url_sync_img({"url": urls})
    if result is None or isinstance(result, str):
        return {
            "role": "tool",
            "content": json.dumps({"error": "Failed to fetch URLs"}, ensure_ascii=False),
            "tool_call_id": tool_call_id,
        }

    raw_text = getattr(result.content[0], "text", "") if result.content else ""
    if not raw_text:
        return {
            "role": "tool",
            "content": json.dumps({"error": "MCP returned empty content"}, ensure_ascii=False),
            "tool_call_id": tool_call_id,
        }

    try:
        res_dict = json.loads(raw_text)
    except json.JSONDecodeError:
        print(f"[DEBUG fetch_url] raw_text type={type(raw_text).__name__}, len={len(raw_text)}, repr={repr(raw_text[:200])}")
        return {
            "role": "tool",
            "content": json.dumps({"error": "MCP returned invalid JSON"}, ensure_ascii=False),
            "tool_call_id": tool_call_id,
        }

    # ---- DOM strategy: return pure text, no images ----
    if FETCH_STRATEGY == "dom":
        text_parts = res_dict.get("text", [])
        dom_content = []
        for part in text_parts:
            link = part.get("link", "")
            snapshot = part.get("dom_snapshot", "")
            error = part.get("error", "")
            if error:
                dom_content.append(f"[{link}] Error: {error}")
            else:
                dom_content.append(f"[{link}]\n{snapshot}")
        return {
            "role": "tool",
            "tool_call_id": tool_call_id,
            "content": "\n\n".join(dom_content),
        }

    # ---- Image strategy: multimodal content (text + image_url) ----
    text_content = res_dict.get("text", "")

    image_list = []
    for slices in (res_dict.get("image") or []):
        for img_item in slices:
            image_list.append(img_item.get("image"))

    text_segments = json.dumps(text_content).split("<image>")
    content_parts = []
    for i, segment in enumerate(text_segments):
        if segment.strip():
            content_parts.append({"type": "text", "text": segment})
        if i < len(image_list):
            content_parts.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{image_list[i]}"},
            })

    return {
        "role": "tool",
        "tool_call_id": tool_call_id,
        "content": content_parts,
    }


class _ToolError(Exception):
    """Internal error during tool processing."""

    def __init__(self, message, *, should_retry=False):
        super().__init__(message)
        self.should_retry = should_retry


def _process_tool_calls(tool_calls, search_ref_start_idx, recent_queries, call_count):
    """
    Execute a batch of tool calls.

    Returns (tool_outputs, updated_search_ref_start_idx, updated_call_count, stop_flag).
    Raises _ToolError on fatal errors.
    """
    tool_outputs = []
    stop_flag = False

    for tool_call in tool_calls:
        func_name = tool_call.function.name

        try:
            func_args = json.loads(tool_call.function.arguments)
        except json.JSONDecodeError as e:
            raise _ToolError(
                f"Tool JSON parse error for '{func_name}': {e}",
                should_retry=False,
            )

        if func_name not in SUPPORTED_TOOLS:
            print(f"Warning: Unknown tool: {func_name}")
            tool_outputs.append({
                "role": "tool",
                "content": json.dumps(
                    {"error": f"Unknown tool: {func_name}. Available: {sorted(SUPPORTED_TOOLS)}"},
                    ensure_ascii=False,
                ),
                "tool_call_id": tool_call.id,
            })
            continue

        if call_count >= MAX_TOOL_CALLS:
            print(f"Maximum tool calls ({MAX_TOOL_CALLS}) reached.")
            tool_outputs.append({
                "role": "tool",
                "content": json.dumps(
                    {"error": f"Maximum tool calls ({MAX_TOOL_CALLS}) reached. Please answer now."},
                    ensure_ascii=False,
                ),
                "tool_call_id": tool_call.id,
            })
            stop_flag = True
            break

        call_count += 1

        if func_name == "web_search":
            output, search_ref_start_idx, err = _handle_web_search(
                func_args, tool_call.id, search_ref_start_idx, recent_queries,
            )
            if err:
                raise _ToolError(err, should_retry=True)
            tool_outputs.append(output)

        elif func_name == "fetch_url":
            try:
                tool_outputs.append(_handle_fetch_url(func_args, tool_call.id))
            except Exception as e:
                traceback.print_exc()
                tool_outputs.append({
                    "role": "tool",
                    "content": json.dumps({"error": str(e)}, ensure_ascii=False),
                    "tool_call_id": tool_call.id,
                })

    return tool_outputs, search_ref_start_idx, call_count, stop_flag


def predict_qwen_search(client, prompt, think_mode=True):
    """
    Multi-turn tool-augmented inference with web search and page fetch.

    Returns (prediction, messages, should_retry, error_msg).
    """
    today = datetime.now().strftime("%Y-%m-%d")
    system_prompt = (
        f"today is:{today} 。\n"
        "   Reason step by step and place the thought process within the "
        "<think></think> tags, and provide the final conclusion at the end."
        "\n\n# Tools\n\nYou may call one or more functions to assist with "
        "the user query.\n\nYou are provided with function signatures within "
        "<tools></tools> XML tags:\n"
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": prompt},
    ]

    # --- Initial generation ---
    try:
        response = _generate(client, messages, think_mode=think_mode)
    except Exception as e:
        err = f"Initial generation failed: {e}"
        print(f"[ERROR] {err}")
        return None, None, True, err

    message = response.choices[0].message
    tool_calls, parse_err = _extract_tool_calls_from_text(message.content or "")
    if parse_err:
        return parse_err, messages, False, parse_err

    # --- Tool-call loop ---
    call_count = 0
    recent_queries = []
    search_ref_start_idx = 0

    while tool_calls:
        try:
            outputs, search_ref_start_idx, call_count, stop_flag = _process_tool_calls(
                tool_calls, search_ref_start_idx, recent_queries, call_count,
            )
        except _ToolError as e:
            err = str(e)
            if e.should_retry:
                return None, None, True, err
            return err, messages, False, err

        messages.append(_build_safe_message(message))
        if outputs:
            messages.extend(outputs)

        if stop_flag:
            break

        try:
            response = _generate(client, messages, think_mode=think_mode)
        except Exception as e:
            err = f"Generation in loop failed: {e}"
            print(f"[ERROR] {err}")
            return None, None, True, err

        message = response.choices[0].message
        tool_calls, parse_err = _extract_tool_calls_from_text(message.content or "")
        if parse_err:
            return parse_err, messages, False, parse_err

        if call_count >= MAX_TOOL_CALLS:
            tool_calls = None

    # --- Final answer ---
    if call_count >= MAX_TOOL_CALLS:
        if message and (message.content or getattr(message, "tool_calls", None)):
            messages.append(_build_safe_message(message))
        messages.append({
            "role": "user",
            "content": (
                "You have reached the maximum number of tool calls. "
                "Please provide your final answer based on the information gathered so far."
            ),
        })
        try:
            response = _generate(client, messages, think_mode=think_mode)
        except Exception as e:
            err = f"Final summary generation failed: {e}"
            print(f"[ERROR] {err}")
            return None, None, True, err
        message = response.choices[0].message
        messages.append(_build_safe_message(message))
        return (message.content or ""), messages, False, None

    messages.append(_build_safe_message(message))
    prediction = response.choices[0].message.content or ""
    return prediction, messages, False, None
