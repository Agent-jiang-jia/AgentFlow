"""SSRF URL validation tests."""

from collections.abc import Sequence

import pytest
from app.core.security import UrlNotAllowedError, validate_public_http_url


async def public_resolver(_host: str, _port: int) -> Sequence[str]:
    """Resolve test hostnames to a public example address."""
    return ("93.184.216.34",)


@pytest.mark.anyio
@pytest.mark.parametrize(
    "url",
    [
        "file:///etc/passwd",
        "ftp://example.com/file",
        "http://localhost/admin",
        "http://127.0.0.1/",
        "http://0.0.0.0/",
        "http://[::1]/",
        "http://169.254.169.254/latest/meta-data/",
        "http://10.0.0.1/",
        "http://172.16.0.1/",
        "http://192.168.1.1/",
        "http://user:password@example.com/",
    ],
)
async def test_rejects_non_public_and_credentialed_urls(url: str) -> None:
    """Schemes, loopback, private, link-local, metadata, and credentials are refused."""
    with pytest.raises(UrlNotAllowedError):
        await validate_public_http_url(url, resolver=public_resolver)


@pytest.mark.anyio
async def test_rejects_when_any_dns_answer_is_private() -> None:
    """Mixed DNS answers cannot bypass the public-address policy."""

    async def mixed_resolver(_host: str, _port: int) -> Sequence[str]:
        return ("93.184.216.34", "192.168.1.20")

    with pytest.raises(UrlNotAllowedError):
        await validate_public_http_url("https://public.example/path", resolver=mixed_resolver)


@pytest.mark.anyio
async def test_normalizes_public_http_url() -> None:
    """Safe URLs lose fragments and normalize host, scheme, and default ports."""
    result = await validate_public_http_url(
        "HTTPS://Public.Example:443/article?q=1#section",
        resolver=public_resolver,
    )

    assert result == "https://public.example/article?q=1"
