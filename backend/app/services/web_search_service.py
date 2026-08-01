"""Configured Tavily search client with provider-neutral results."""

from dataclasses import dataclass
from typing import cast

import httpx
from pydantic import SecretStr

from app.core.security import normalize_search_result_url


@dataclass(frozen=True, slots=True)
class SearchResult:
    """One normalized search result returned to the agent."""

    title: str
    url: str
    snippet: str


class WebSearchServiceError(RuntimeError):
    """Safe search-provider failure."""

    def __init__(self, message: str, *, retryable: bool) -> None:
        super().__init__(message)
        self.retryable = retryable


class WebSearchService:
    """Call one configured search provider without exposing credentials."""

    def __init__(
        self,
        *,
        provider: str,
        api_base: str,
        api_key: SecretStr | None,
        timeout_seconds: float,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._provider = provider
        self._api_base = api_base
        self._api_key = api_key
        self._timeout_seconds = timeout_seconds
        self._transport = transport

    async def search(self, *, query: str, max_results: int) -> tuple[SearchResult, ...]:
        """Return de-duplicated HTTP(S) results up to the requested limit."""
        if self._provider != "tavily" or self._api_key is None:
            raise WebSearchServiceError("联网搜索尚未配置", retryable=False)
        try:
            async with httpx.AsyncClient(
                timeout=self._timeout_seconds,
                transport=self._transport,
                trust_env=False,
            ) as client:
                response = await client.post(
                    self._api_base,
                    json={
                        "api_key": self._api_key.get_secret_value(),
                        "query": query,
                        "max_results": max_results,
                        "search_depth": "basic",
                    },
                    headers={"Accept": "application/json"},
                )
                response.raise_for_status()
                payload = response.json()
        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            raise WebSearchServiceError("联网搜索请求失败", retryable=True) from exc
        except (httpx.HTTPStatusError, ValueError) as exc:
            raise WebSearchServiceError("联网搜索服务返回无效响应", retryable=True) from exc

        if not isinstance(payload, dict) or not isinstance(payload.get("results"), list):
            raise WebSearchServiceError("联网搜索服务返回无效响应", retryable=True)

        results: list[SearchResult] = []
        seen_urls: set[str] = set()
        for item in cast(list[object], payload["results"]):
            if not isinstance(item, dict):
                continue
            raw_url = item.get("url")
            if not isinstance(raw_url, str):
                continue
            url = normalize_search_result_url(raw_url)
            if url is None or url in seen_urls:
                continue
            raw_title = item.get("title")
            raw_snippet = item.get("content")
            title = raw_title.strip() if isinstance(raw_title, str) else ""
            snippet = raw_snippet.strip() if isinstance(raw_snippet, str) else ""
            results.append(
                SearchResult(
                    title=(title or url)[:500],
                    url=url,
                    snippet=snippet[:1000],
                )
            )
            seen_urls.add(url)
            if len(results) >= max_results:
                break
        return tuple(results)
