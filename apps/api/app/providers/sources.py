import hashlib
import ipaddress
import os
import socket
import time
from datetime import UTC, datetime
from urllib.parse import urljoin, urlsplit, urlunsplit

import feedparser
import httpx
from bs4 import BeautifulSoup, Tag

from app.domain.rules import valid_url
from app.schemas.models import Article, Journal

MAX_BODY = 1_000_000


def public_addresses(host: str) -> list[str]:
    addresses = list(
        dict.fromkeys(
            str(item[4][0]) for item in socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
        )
    )
    if not addresses or any(not ipaddress.ip_address(address).is_global for address in addresses):
        raise ValueError("DNS указывает на частный или зарезервированный адрес")
    return addresses


def fetch(url: str) -> tuple[str, str]:
    if not valid_url(url):
        raise ValueError("Недопустимый URL")
    parts = urlsplit(url)
    allowed = {
        h.strip().casefold()
        for h in os.getenv("SOURCE_ALLOWED_HOSTS", "cisa.gov,www.cisa.gov,nvd.nist.gov").split(",")
        if h.strip()
    }
    host = parts.hostname or ""
    if host.casefold() not in allowed:
        raise ValueError("Домен не входит в SOURCE_ALLOWED_HOSTS")
    address = public_addresses(host)[0]
    ip_host = f"[{address}]" if ":" in address else address
    port = parts.port or (443 if parts.scheme == "https" else 80)
    pinned_url = urlunsplit((parts.scheme, f"{ip_host}:{port}", parts.path or "/", parts.query, ""))
    # Connect to resolved IP, verify TLS for original host, and never resolve host again.
    started = time.monotonic()
    with (
        httpx.Client(
            timeout=httpx.Timeout(5, connect=3), follow_redirects=False, trust_env=False
        ) as client,
        client.stream(
            "GET",
            pinned_url,
            headers={"Host": host, "User-Agent": "CyberDigest/1.0"},
            extensions={"sni_hostname": host.encode()},
        ) as response,
    ):
        if response.is_redirect:
            raise ValueError("Перенаправления источников запрещены")
        response.raise_for_status()
        content_type = response.headers.get("content-type", "").lower()
        if not any(kind in content_type for kind in ["xml", "rss", "atom", "html", "text/plain"]):
            raise ValueError("Неподдерживаемый Content-Type")
        chunks: list[bytes] = []
        size = 0
        for chunk in response.iter_bytes():
            size += len(chunk)
            if size > MAX_BODY or time.monotonic() - started > 8:
                raise ValueError("Источник превысил лимит размера или времени")
            chunks.append(chunk)
        return b"".join(chunks).decode("utf-8", errors="replace"), content_type


def preview(urls: list[str]) -> dict[str, object]:
    articles: list[Article] = []
    warnings: list[str] = []
    journal: list[Journal] = []
    for url in urls:
        try:
            body, content_type = fetch(url)
            host = urlsplit(url).hostname
            if "xml" in content_type or "rss" in content_type or "atom" in content_type:
                parsed = feedparser.parse(body)
                for entry in parsed.entries[:20]:
                    content = entry.get("content", [])
                    raw_text = content[0].get("value", "") if content else entry.get("summary", "")
                    text = BeautifulSoup(raw_text, "html.parser").get_text(" ", strip=True)
                    # feed dates without explicit offset remain unknown rather than fabricated.
                    published = entry.get("published") or entry.get("updated")
                    if published:
                        from email.utils import parsedate_to_datetime

                        try:
                            published = parsedate_to_datetime(published).isoformat()
                        except (ValueError, TypeError):
                            pass
                    articles.append(
                        Article(
                            id="rss-"
                            + hashlib.sha256(
                                (url + str(entry.get("id", entry.get("link", "")))).encode()
                            ).hexdigest()[:16],
                            title=entry.get("title"),
                            text=text[:30000],
                            source=host,
                            source_type="unknown",
                            url=urljoin(url, entry.get("link", "")),
                            published_at=published,
                        )
                    )
            else:
                soup = BeautifulSoup(body, "html.parser")
                for element in soup(["script", "style", "nav", "footer", "form"]):
                    element.decompose()
                title = soup.find("h1") or soup.title
                date = soup.find("meta", property="article:published_time")
                main = soup.find("article") or soup.find("main")
                articles.append(
                    Article(
                        id="html-" + hashlib.sha256(url.encode()).hexdigest()[:16],
                        title=title.get_text(" ", strip=True)[:500] if title else None,
                        text=main.get_text(" ", strip=True)[:30000] if main else None,
                        source=host,
                        source_type="unknown",
                        url=url,
                        published_at=str(date.get("content"))
                        if isinstance(date, Tag) and date.get("content")
                        else None,
                    )
                )
        except (ValueError, OSError, httpx.HTTPError) as exc:
            # Do not expose response bodies, secrets, query strings, or exception request headers.
            reason = (
                str(exc)
                if isinstance(exc, ValueError)
                else "Источник недоступен или HTTP-запрос завершился ошибкой"
            )
            warnings.append(reason)
            journal.append(
                Journal(
                    id=None,
                    title=None,
                    source=None,
                    source_type=None,
                    url=url,
                    published_at=None,
                    status="source_unavailable",
                    exclusion_reason=reason,
                    errors=[reason],
                    processed_at=datetime.now(UTC).isoformat(),
                )
            )
    return {
        "articles": [a.model_dump() for a in articles],
        "warnings": warnings,
        "journal": [j.model_dump() for j in journal],
    }
