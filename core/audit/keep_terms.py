"""Words a translation keeps in English, so they do not count as "untranslated text" (SK, 2026-11-12; rules of the
blog translation agent: product and brand names, file formats and abbreviations, platforms, code, URLs and paths
stay as they are).

`translatable_words(text, host, extra)` returns the Latin words left after removing those; the untranslated checks
(crawl title/description_untranslated, repo post_text_untranslated) flag a value only when at least MIN_WORDS remain.
Brand names are recognised by shape (Brand.Product, optionally "for <platform>" / "via <platform>"), never by name,
so this module stays tenant-neutral; a tenant can add its own terms (`audit.translation.keep_terms`, regexes).
"""

from __future__ import annotations

import re

MIN_WORDS = 3
# Brand.Product[.Sub] with an optional "for .NET", "for Python via .NET", "for Node.js via Java" tail
PRODUCT = re.compile(r"\b[A-Z][A-Za-z0-9]*\.[A-Z][A-Za-z0-9]*(?:\.[A-Za-z0-9]+)*"
                     r"(?:\s+for\s+[.\w#+-]+(?:\s+via\s+[.\w#+-]+)?)?")
URL_OR_PATH = re.compile(r"https?://\S+|\S*/\S*|\S+\.(?:md|html?|xml|json|ya?ml)\b")
CODE = re.compile(r"`[^`]*`")
ABBREVIATION = re.compile(r"\b[A-Z0-9][A-Z0-9#+.-]*[A-Z0-9#+]\b")  # PDF, REST, API, XLSX, C#, C++, HTML5
PLATFORMS = {"net", "java", "python", "node", "js", "javascript", "typescript", "php", "go", "golang", "ruby",
             "swift", "kotlin", "android", "ios", "linux", "windows", "macos", "docker", "excel", "word",
             "powerpoint", "outlook", "visio", "markdown", "cloud", "sdk", "sdks", "api", "apis", "rest"}
WORD = re.compile(r"[A-Za-z]{2,}")


def translatable_words(text: str, host: str = "", extra: list[str] | None = None) -> list[str]:
    for rx in [CODE, URL_OR_PATH, PRODUCT, *(re.compile(x) for x in extra or [])]:
        text = rx.sub(" ", text)
    text = ABBREVIATION.sub(" ", text)
    skip = PLATFORMS | {w.lower() for w in host.split(".") if w}
    return [w for w in WORD.findall(text) if w.lower() not in skip]


def looks_untranslated(value: str, host: str = "", extra: list[str] | None = None) -> bool:
    """True when the value has at least MIN_WORDS words a translation should have translated."""
    return len(translatable_words(value, host, extra)) >= MIN_WORDS
