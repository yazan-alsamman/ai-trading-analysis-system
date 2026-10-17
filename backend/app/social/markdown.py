"""Input rules for user Markdown (posts, comments). The API stores Markdown as written and
never returns HTML; clients render it with raw HTML disabled. On top of that, input with raw
HTML tags or script links is refused, so a careless renderer cannot be turned against readers:

- HTML tags, comments, CDATA and processing instructions outside code spans/blocks -> 422;
- link targets (inline, reference and autolinks) must be relative or http, https, mailto;
- ``javascript:`` / ``vbscript:`` anywhere outside code, also when split by whitespace or
  control characters or written with HTML entities.
"""

import html
import re
from urllib.parse import urlsplit

_FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,}).*?(?:^ {0,3}\1[`~]*[ \t]*$|\Z)", re.S | re.M)
_INDENTED = re.compile(r"^(?: {4}|\t).*$", re.M)
_INLINE_CODE = re.compile(r"(`+)(?!`).+?(?<!`)\1(?!`)", re.S)
_HTML = re.compile(
    r"<\s*/?\s*[A-Za-z][A-Za-z0-9-]*(?:\s[^<>]*)?/?\s*>|<!--|<!\[CDATA\[|<\?[A-Za-z]"
)
_INLINE_LINK = re.compile(r"\]\(\s*<?([^)\s>]*)")
_REFERENCE = re.compile(r"^ {0,3}\[[^\]]+\]:\s*<?(\S+?)>?(?:\s|$)", re.M)
_AUTOLINK = re.compile(r"<([A-Za-z][A-Za-z0-9+.\-]*:[^<>\s]*)>")
_SCRIPT = re.compile(r"(?:java|vb|live)script:", re.I)
_CONTROL = re.compile(r"[\x00-\x20\x7f]+")
SAFE_SCHEMES = frozenset({"http", "https", "mailto"})


def _without_code(text: str) -> str:
    text = _FENCE.sub(" ", text)
    text = _INDENTED.sub(" ", text)
    return _INLINE_CODE.sub(" ", text)


def _normalized(value: str) -> str:
    return _CONTROL.sub("", html.unescape(value)).lower()


def check(text: str, *, single_line: bool = False) -> str:
    """The cleaned text (line endings normalised, trimmed), or ValueError with the reason."""
    text = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    if single_line:
        text = " ".join(text.split())
    if "\x00" in text:
        raise ValueError("must not contain NUL characters")
    prose = _without_code(text)
    if _HTML.search(prose):
        raise ValueError("raw HTML is not allowed (use Markdown)")
    if _SCRIPT.search(_normalized(prose)):
        raise ValueError("script links are not allowed")
    targets = [
        *_INLINE_LINK.findall(prose),
        *_REFERENCE.findall(prose),
        *_AUTOLINK.findall(prose),
    ]
    for target in targets:
        clean = _normalized(target)
        if ":" not in clean.split("/", 1)[0]:
            continue  # relative link or anchor
        scheme = urlsplit(clean).scheme
        if scheme not in SAFE_SCHEMES:
            raise ValueError("links must be http, https or mailto")
    return text
