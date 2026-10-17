"""Plain text from feed HTML, and URL normalisation for stable article ids."""

import hashlib
import html
import re
from html.parser import HTMLParser
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from app.models.news import SUMMARY_MAX

# query parameters that only track the click, never change the article
TRACKING_PARAMS = frozenset(
    {
        "fbclid",
        "gclid",
        "dclid",
        "msclkid",
        "mc_cid",
        "mc_eid",
        "ref",
        "ref_src",
        "cmpid",
        "ito",
        "_ga",
        "igshid",
        "yclid",
        "spm",
    }
)
_BLOCK_TAGS = {"p", "br", "div", "li", "ul", "ol", "h1", "h2", "h3", "h4", "tr", "table"}
_SKIP_TAGS = {"script", "style", "iframe", "noscript", "svg"}
_SPACES = re.compile(r"\s+")


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in _SKIP_TAGS:
            self.skip += 1
        elif tag in _BLOCK_TAGS:
            self.parts.append(" ")

    def handle_endtag(self, tag):
        if tag in _SKIP_TAGS and self.skip:
            self.skip -= 1
        elif tag in _BLOCK_TAGS:
            self.parts.append(" ")

    def handle_data(self, data):
        if not self.skip:
            self.parts.append(data)


def strip_html(value: str | None) -> str:
    """Text content only (scripts and styles dropped), entities decoded, whitespace collapsed."""
    if not value:
        return ""
    parser = _TextExtractor()
    try:
        parser.feed(value)
        parser.close()
        text = "".join(parser.parts)
    except Exception:  # noqa: BLE001 - broken markup: drop anything that looks like a tag
        text = re.sub(r"<[^>]*>", " ", value)
    return _SPACES.sub(" ", html.unescape(text)).strip()


def clip(text: str, limit: int = SUMMARY_MAX) -> str:
    """At most ``limit`` characters, cut at a word with an ellipsis."""
    if len(text) <= limit:
        return text
    cut = text[: limit - 1].rsplit(" ", 1)[0] or text[: limit - 1]
    return cut.rstrip(" ,.;:") + "…"


def normalize_url(url: str) -> str:
    """Lower-case scheme and host, no fragment, no tracking parameters (``utm_*`` and friends),
    remaining parameters sorted, no trailing slash on paths."""
    parts = urlsplit(url.strip())
    query = [
        (k, v)
        for k, v in parse_qsl(parts.query, keep_blank_values=True)
        if not k.lower().startswith("utm_") and k.lower() not in TRACKING_PARAMS
    ]
    path = parts.path.rstrip("/") if parts.path not in ("", "/") else ""
    host = (parts.hostname or "").lower()
    if parts.port and not (
        (parts.scheme == "http" and parts.port == 80)
        or (parts.scheme == "https" and parts.port == 443)
    ):
        host = f"{host}:{parts.port}"
    return urlunsplit((parts.scheme.lower(), host, path, urlencode(sorted(query)), ""))


def url_id(url: str) -> str:
    """``external_id`` of an article without a provider id: sha256 of the normalised URL."""
    return hashlib.sha256(normalize_url(url).encode()).hexdigest()[:40]


def is_http_url(value: str | None) -> bool:
    if not value:
        return False
    parts = urlsplit(value.strip())
    return parts.scheme in ("http", "https") and bool(parts.hostname)
