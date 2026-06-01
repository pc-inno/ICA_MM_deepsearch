import json
import os
import time
import traceback

import requests


def _contains_chinese(text: str) -> bool:
    return any("一" <= ch <= "鿿" for ch in text)


class SerperSearch:
    """Web search via google.serper.dev with retry and language detection."""

    ENDPOINT = "https://google.serper.dev/search"

    def __init__(self, api_key: str | None = None):
        self._api_key = api_key or os.getenv(
            "SERPER_API_KEY", "EMPTY"
        )

    def search(self, query: str, total: int = 10) -> list[dict]:
        """
        Search and return a list of ``{title, snippet, link}`` dicts.

        Retries up to 8 times with 2 s backoff. Returns ``[]`` on total failure.
        """
        if not self._api_key or self._api_key == "EMPTY":
            return []

        if _contains_chinese(query):
            payload = {"q": query, "num": total, "location": "China", "gl": "cn", "hl": "zh-cn"}
        else:
            payload = {"q": query, "num": total, "location": "United States", "gl": "us", "hl": "en"}

        headers = {
            "X-API-KEY": self._api_key,
            "Content-Type": "application/json",
        }

        max_retries = 8
        for attempt in range(1, max_retries + 1):
            try:
                resp = requests.post(
                    self.ENDPOINT,
                    headers=headers,
                    data=json.dumps(payload),
                    timeout=30,
                )
                resp.raise_for_status()
                data = resp.json()

                if "error" in data:
                    print(f"[SerperSearch] API error: {data['error']}")
                    return []

                organic = data.get("organic")
                if organic is None:
                    print(f"[SerperSearch] No 'organic' key in response")
                    return []

                return [
                    {
                        "title": item.get("title", ""),
                        "snippet": item.get("snippet", ""),
                        "link": item.get("link", ""),
                    }
                    for item in organic[:total]
                ]

            except requests.exceptions.Timeout:
                print(f"[SerperSearch] Timeout (attempt {attempt}/{max_retries})")
            except requests.exceptions.HTTPError as e:
                body = getattr(e.response, "text", "")[:200]
                print(f"[SerperSearch] HTTP {e.response.status_code} (attempt {attempt}): {body}")
            except requests.exceptions.RequestException as e:
                print(f"[SerperSearch] Request error (attempt {attempt}): {e}")
            except json.JSONDecodeError as e:
                print(f"[SerperSearch] JSON decode error (attempt {attempt}): {e}")
            except Exception as e:
                print(f"[SerperSearch] Unexpected error (attempt {attempt}): {e}")
                traceback.print_exc()

            if attempt < max_retries:
                time.sleep(2)

        return []


# ---------------------------------------------------------------------------
# Module-level convenience function (matches the old tools.py interface)
# ---------------------------------------------------------------------------

_default_searcher: SerperSearch | None = None


def web_search(query: str, start_idx: int = 0, total: int = 10) -> list[dict]:
    """
    Search via Serper API.

    Returns list of ``{title, snippet, link, rank}`` dicts.
    """
    global _default_searcher
    if _default_searcher is None:
        _default_searcher = SerperSearch()

    results = _default_searcher.search(query, total=total)
    for i, r in enumerate(results):
        r["rank"] = start_idx + i + 1
    return results


# ---------------------------------------------------------------------------
# OpenAI function-calling schema (used by inference.py to declare tools)
# ---------------------------------------------------------------------------

web_search_tool = {
    "type": "function",
    "function": {
        "name": "web_search",
        "description": (
            "This function acts as a search engine to retrieve a wide range of "
            "information from the web. It is capable of processing queries "
            "related to various topics and returning relevant results."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "array",
                    "items": {
                        "type": "string",
                        "description": (
                            "The search query used to retrieve information from "
                            "the internet. Rewrite and optimize the query based "
                            "on conversation history for best search quality."
                        ),
                    },
                    "minItems": 1,
                    "description": "The list of search queries.",
                }
            },
            "required": ["query"],
        },
    },
}
