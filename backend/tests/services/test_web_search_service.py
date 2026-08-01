"""Configured web-search provider behavior tests."""

import json

import httpx
import pytest
from app.services.web_search_service import WebSearchService, WebSearchServiceError
from pydantic import SecretStr


@pytest.mark.anyio
@pytest.mark.parametrize("query", ["Agent frameworks", "智能体框架"])
async def test_search_supports_queries_filters_deduplicates_and_limits(query: str) -> None:
    """Provider results are normalized without generating a summary."""
    received: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        assert isinstance(payload, dict)
        received.update(payload)
        return httpx.Response(
            200,
            json={
                "results": [
                    {"title": "One", "url": "https://Example.com/a#top", "content": "A"},
                    {"title": "Duplicate", "url": "https://example.com/a", "content": "B"},
                    {"title": "No URL", "content": "ignored"},
                    {"title": "Unsafe", "url": "http://127.0.0.1/", "content": "ignored"},
                    {"title": "Two", "url": "https://example.org/b", "content": "C"},
                ]
            },
        )

    service = WebSearchService(
        provider="tavily",
        api_base="https://search.example/api",
        api_key=SecretStr("test-secret"),
        timeout_seconds=2,
        transport=httpx.MockTransport(handler),
    )

    results = await service.search(query=query, max_results=2)

    assert received["query"] == query
    assert received["max_results"] == 2
    assert [result.url for result in results] == [
        "https://example.com/a",
        "https://example.org/b",
    ]
    assert [result.snippet for result in results] == ["A", "C"]


@pytest.mark.anyio
async def test_search_requires_configuration_and_hides_provider_failure() -> None:
    """Missing credentials and provider errors become safe service failures."""
    unconfigured = WebSearchService(
        provider="tavily",
        api_base="https://search.example/api",
        api_key=None,
        timeout_seconds=2,
    )
    with pytest.raises(WebSearchServiceError, match="尚未配置") as missing:
        await unconfigured.search(query="test", max_results=5)
    assert missing.value.retryable is False

    failing = WebSearchService(
        provider="tavily",
        api_base="https://search.example/api",
        api_key=SecretStr("test-secret"),
        timeout_seconds=2,
        transport=httpx.MockTransport(lambda _request: httpx.Response(503, text="internal")),
    )
    with pytest.raises(WebSearchServiceError, match="无效响应") as failure:
        await failing.search(query="test", max_results=5)
    assert failure.value.retryable is True
    assert "internal" not in str(failure.value)
