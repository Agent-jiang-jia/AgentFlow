"""Webpage fetch, extraction, bounding, and redirect safety tests."""

from collections.abc import Sequence

import httpx
import pytest
from app.core.security import UrlNotAllowedError
from app.services.web_fetch_service import WebFetchService, WebFetchServiceError


async def public_resolver(_host: str, _port: int) -> Sequence[str]:
    """Resolve test hostnames to a public example address."""
    return ("93.184.216.34",)


@pytest.mark.anyio
async def test_fetch_extracts_main_text_and_truncates() -> None:
    """Scripts and navigation are removed while main content is bounded."""
    article = "正文段落。" * 300
    html = f"""
    <html><head><title>Example Page</title><style>.x{{}}</style></head>
    <body><nav>Navigation secret</nav><article><h1>Article</h1><p>{article}</p></article>
    <script>script secret</script></body></html>
    """
    service = WebFetchService(
        timeout_seconds=2,
        max_bytes=100_000,
        resolver=public_resolver,
        transport=httpx.MockTransport(
            lambda _request: httpx.Response(
                200,
                headers={"content-type": "text/html; charset=utf-8"},
                content=html.encode(),
            )
        ),
    )

    page = await service.fetch(url="https://public.example/article", max_chars=1000)

    assert page.title == "Example Page"
    assert page.url == "https://public.example/article"
    assert len(page.content) == 1000
    assert page.truncated is True
    assert "Navigation secret" not in page.content
    assert "script secret" not in page.content


@pytest.mark.anyio
async def test_redirect_target_is_revalidated_before_second_request() -> None:
    """A public page cannot redirect the fetcher into a private address."""
    requests: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(str(request.url))
        return httpx.Response(302, headers={"location": "http://127.0.0.1/admin"})

    service = WebFetchService(
        timeout_seconds=2,
        max_bytes=10_000,
        resolver=public_resolver,
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(UrlNotAllowedError):
        await service.fetch(url="https://public.example/start", max_chars=1000)
    assert requests == ["https://public.example/start"]


@pytest.mark.anyio
async def test_fetch_rejects_oversized_and_non_html_responses() -> None:
    """The download byte cap and HTML media-type boundary are enforced."""
    oversized = WebFetchService(
        timeout_seconds=2,
        max_bytes=1024,
        resolver=public_resolver,
        transport=httpx.MockTransport(lambda _request: httpx.Response(200, content=b"x" * 1025)),
    )
    with pytest.raises(WebFetchServiceError, match="超过读取限制"):
        await oversized.fetch(url="https://public.example/large", max_chars=1000)

    non_html = WebFetchService(
        timeout_seconds=2,
        max_bytes=2048,
        resolver=public_resolver,
        transport=httpx.MockTransport(
            lambda _request: httpx.Response(
                200,
                headers={"content-type": "application/pdf"},
                content=b"pdf",
            )
        ),
    )
    with pytest.raises(WebFetchServiceError, match="不是 HTML"):
        await non_html.fetch(url="https://public.example/file", max_chars=1000)
