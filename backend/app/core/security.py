"""Network security helpers for public HTTP(S) access."""

import asyncio
import ipaddress
import socket
from collections.abc import Awaitable, Callable, Sequence
from urllib.parse import SplitResult, urlsplit, urlunsplit

type HostResolver = Callable[[str, int], Awaitable[Sequence[str]]]


class UrlNotAllowedError(ValueError):
    """Raised when a URL can reach a non-public or unsupported destination."""


async def resolve_host_addresses(host: str, port: int) -> Sequence[str]:
    """Resolve all TCP addresses for a host without blocking the event loop."""
    loop = asyncio.get_running_loop()
    records = await loop.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    return tuple(dict.fromkeys(str(record[4][0]) for record in records))


async def validate_public_http_url(
    value: str,
    *,
    resolver: HostResolver = resolve_host_addresses,
) -> str:
    """Normalize an HTTP(S) URL and reject every non-public resolved address."""
    parsed = _parse_http_url(value)
    host = parsed.hostname
    if host is None:
        raise UrlNotAllowedError("URL 缺少主机名")
    normalized_host = _normalize_host(host)
    port = _port(parsed)

    literal = _ip_literal(normalized_host)
    if literal is not None:
        _require_public_address(literal)
    else:
        if normalized_host == "localhost" or normalized_host.endswith(".localhost"):
            raise UrlNotAllowedError("URL 指向受限地址")
        try:
            addresses = await resolver(normalized_host, port)
        except (OSError, UnicodeError) as exc:
            raise UrlNotAllowedError("URL 主机无法安全解析") from exc
        if not addresses:
            raise UrlNotAllowedError("URL 主机无法安全解析")
        for address in addresses:
            try:
                parsed_address = ipaddress.ip_address(address.split("%", 1)[0])
            except ValueError as exc:
                raise UrlNotAllowedError("URL 主机解析结果无效") from exc
            _require_public_address(parsed_address)

    return _rebuild_url(parsed, normalized_host, port)


def normalize_search_result_url(value: str) -> str | None:
    """Normalize a search-result URL while rejecting unsafe literal hosts."""
    try:
        parsed = _parse_http_url(value)
        host = parsed.hostname
        if host is None:
            return None
        normalized_host = _normalize_host(host)
        if normalized_host == "localhost" or normalized_host.endswith(".localhost"):
            return None
        literal = _ip_literal(normalized_host)
        if literal is not None:
            _require_public_address(literal)
        return _rebuild_url(parsed, normalized_host, _port(parsed))
    except (UrlNotAllowedError, UnicodeError):
        return None


def _parse_http_url(value: str) -> SplitResult:
    normalized = value.strip()
    if not normalized or len(normalized) > 2048:
        raise UrlNotAllowedError("URL 无效")
    parsed = urlsplit(normalized)
    if parsed.scheme.lower() not in {"http", "https"}:
        raise UrlNotAllowedError("仅允许 HTTP 或 HTTPS URL")
    if parsed.username is not None or parsed.password is not None:
        raise UrlNotAllowedError("URL 不允许包含身份凭据")
    if parsed.hostname is None:
        raise UrlNotAllowedError("URL 缺少主机名")
    return parsed


def _normalize_host(host: str) -> str:
    if "%" in host:
        raise UrlNotAllowedError("URL 主机名无效")
    try:
        return host.rstrip(".").encode("idna").decode("ascii").lower()
    except UnicodeError as exc:
        raise UrlNotAllowedError("URL 主机名无效") from exc


def _port(parsed: SplitResult) -> int:
    try:
        explicit_port = parsed.port
    except ValueError as exc:
        raise UrlNotAllowedError("URL 端口无效") from exc
    return explicit_port or (443 if parsed.scheme.lower() == "https" else 80)


def _ip_literal(host: str) -> ipaddress.IPv4Address | ipaddress.IPv6Address | None:
    try:
        return ipaddress.ip_address(host)
    except ValueError:
        return None


def _require_public_address(address: ipaddress.IPv4Address | ipaddress.IPv6Address) -> None:
    candidate = address.ipv4_mapped if isinstance(address, ipaddress.IPv6Address) else None
    checked = candidate or address
    if not checked.is_global:
        raise UrlNotAllowedError("URL 指向受限地址")


def _rebuild_url(parsed: SplitResult, host: str, port: int) -> str:
    default_port = 443 if parsed.scheme.lower() == "https" else 80
    display_host = f"[{host}]" if ":" in host else host
    netloc = display_host if port == default_port else f"{display_host}:{port}"
    return urlunsplit((parsed.scheme.lower(), netloc, parsed.path or "/", parsed.query, ""))
