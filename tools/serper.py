import json
from datetime import datetime
from typing import Any
import datetime as dt
import requests

from .protocol import (
    SearchEngineProtocol,
    SearchResponse,
    SearchResultItem,
    validate_top_value,
)


class SerperSearch(SearchEngineProtocol):
    """Search implementation using serper.dev API."""

    def __init__(self, api_key: str, default_top: int = 10):
        self.api_key = api_key
        validated_default = validate_top_value(default_top)
        if validated_default is None:
            raise ValueError("default_top must be one of the supported search sizes (3, 5, 10)")
        self._default_top = validated_default

    @property
    def source(self) -> str:
        return "Google"

    def _call_api(self, query: str, num: int = 4) -> dict[str, Any]:
        url = "https://google.serper.dev/search"
        payload = json.dumps({"q": query, "num": num})
        headers = {"X-API-KEY": self.api_key, "Content-Type": "application/json"}
        resp = requests.post(url, headers=headers, data=payload, timeout=10)
        resp.raise_for_status()
        return resp.json()

    def search(self, text: str, top: int | None = None) -> SearchResponse:
        desired = validate_top_value(top) or self._default_top
        data = self._call_api(text, num=desired)
        organic = data.get("organic", [])

        results: list[SearchResultItem] = []
        for idx, item in enumerate(organic[:desired], start=1):
            snippet = item.get("snippet") or item.get("description") or ""
            results.append(
                SearchResultItem(
                    title=item.get("title", ""),
                    link=item.get("link", ""),
                    summary=snippet,
                    rank=idx,
                )
            )

        response = SearchResponse(query=text, source=self.source)
        response.set_bucket(desired, results, recorded_at=dt.datetime.now(dt.UTC))
        return response
