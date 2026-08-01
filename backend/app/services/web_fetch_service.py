"""Safe HTML retrieval, redirect handling, and main-content extraction."""

import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import cast
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup
from readability import Document  # type: ignore[import-untyped]

from app.core.security import (
    HostResolver,
    UrlNotAllowedError,
    require_public_ip_address,
    validate_public_http_url,
)

REDIRECT_STATUSES = {301, 302, 303, 307, 308}
HTML_CONTENT_TYPES = {"text/html", "application/xhtml+xml"}
WHITESPACE = re.compile(r"[\t\f\v ]+")


@dataclass(frozen=True, slots=True)
class FetchedPage:
    """Normalized page content returned to the agent."""

    title: str
    url: str
    content: str
    truncated: bool


class WebFetchServiceError(RuntimeError):
    """Safe fetch failure with a stable public category."""

    def __init__(self, message: str, *, retryable: bool) -> None:
        super().__init__(message)
        self.retryable = retryable


class WebFetchService:
    """Fetch public HTML with bounded redirects, bytes, and extracted text."""

    def __init__(
        self,
        *,
        timeout_seconds: float,
        max_bytes: int,
        transport: httpx.AsyncBaseTransport | None = None,
        resolver: HostResolver | None = None,
        max_redirects: int = 5,
    ) -> None:
        self._timeout_seconds = timeout_seconds
        self._max_bytes = max_bytes
        self._transport = transport
        self._resolver = resolver
        self._max_redirects = max_redirects

    async def fetch(self, *, url: str, max_chars: int) -> FetchedPage:
        """Validate and fetch one HTML page, rechecking every redirect target."""
        current_url = url
        try:
            async with httpx.AsyncClient(
                timeout=self._timeout_seconds,
                transport=self._transport,
                follow_redirects=False,
                trust_env=False,
            ) as client:
                for redirect_count in range(self._max_redirects + 1):
                    safe_url = await self._validate(current_url)
                    async with client.stream(
                        "GET",
                        safe_url,
                        headers={
                            "Accept": "text/html,application/xhtml+xml",
                            "User-Agent": "AgentFlow/0.1",
                        },
                    ) as response:
                        self._validate_connected_peer(response)
                        if response.status_code in REDIRECT_STATUSES:
                            location = response.headers.get("location")
                            if location is None or redirect_count >= self._max_redirects:
                                raise WebFetchServiceError(
                                    "网页重定向无效或次数过多", retryable=False
                                )
                            current_url = urljoin(safe_url, location)
                            continue
                        response.raise_for_status()
                        media_type = response.headers.get("content-type", "").split(";", 1)[0]
                        if media_type and media_type.lower() not in HTML_CONTENT_TYPES:
                            raise WebFetchServiceError("目标地址不是 HTML 网页", retryable=False)
                        body = await self._read_bounded(response)
                        encoding = response.encoding or "utf-8"
                    return self._extract(
                        body.decode(encoding, errors="replace"), safe_url, max_chars
                    )
        except UrlNotAllowedError:
            raise
        except WebFetchServiceError:
            raise
        except httpx.TimeoutException as exc:
            raise WebFetchServiceError("网页读取超时", retryable=True) from exc
        except (httpx.NetworkError, httpx.HTTPStatusError, LookupError) as exc:
            raise WebFetchServiceError("网页读取失败", retryable=True) from exc
        raise WebFetchServiceError("网页读取失败", retryable=True)

    def _validate_connected_peer(self, response: httpx.Response) -> None:
        """Recheck the actual socket peer to close DNS-rebinding races."""
        stream = response.extensions.get("network_stream")
        if stream is None:
            if self._transport is None:
                raise WebFetchServiceError("网页连接安全校验失败", retryable=True)
            return
        getter = getattr(stream, "get_extra_info", None)
        if getter is None:
            if self._transport is None:
                raise WebFetchServiceError("网页连接安全校验失败", retryable=True)
            return
        peer = cast(Callable[[str], object], getter)("server_addr")
        if not isinstance(peer, tuple) or not peer or not isinstance(peer[0], str):
            if self._transport is None:
                raise WebFetchServiceError("网页连接安全校验失败", retryable=True)
            return
        require_public_ip_address(peer[0])

    async def _validate(self, url: str) -> str:
        if self._resolver is None:
            return await validate_public_http_url(url)
        return await validate_public_http_url(url, resolver=self._resolver)

    async def _read_bounded(self, response: httpx.Response) -> bytes:
        chunks: list[bytes] = []
        size = 0
        async for chunk in response.aiter_bytes():
            size += len(chunk)
            if size > self._max_bytes:
                raise WebFetchServiceError("网页内容超过读取限制", retryable=False)
            chunks.append(chunk)
        return b"".join(chunks)

    @staticmethod
    def _extract(html: str, url: str, max_chars: int) -> FetchedPage:
        try:
            document = Document(html)
            title = document.short_title().strip()
            main_html = document.summary(html_partial=True)
        except Exception as exc:
            raise WebFetchServiceError("网页正文提取失败", retryable=False) from exc

        soup = BeautifulSoup(main_html, "html.parser")
        for element in soup.select("script, style, nav, header, footer, aside, noscript"):
            element.decompose()
        content = WebFetchService._normalize_text(soup.get_text("\n"))
        if not content:
            fallback = BeautifulSoup(html, "html.parser")
            for element in fallback.select("script, style, nav, header, footer, aside, noscript"):
                element.decompose()
            content = WebFetchService._normalize_text(fallback.get_text("\n"))
        if not content:
            raise WebFetchServiceError("网页未提取到有效正文", retryable=False)

        truncated = len(content) > max_chars
        normalized_title = WHITESPACE.sub(" ", title).strip()[:500] or url
        return FetchedPage(
            title=normalized_title,
            url=url,
            content=content[:max_chars],
            truncated=truncated,
        )

    @staticmethod
    def _normalize_text(value: str) -> str:
        lines = (WHITESPACE.sub(" ", line).strip() for line in value.splitlines())
        return "\n\n".join(line for line in lines if line)
