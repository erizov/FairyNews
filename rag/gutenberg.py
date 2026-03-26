"""Download plain text from Project Gutenberg by ebook id."""

from __future__ import annotations

import logging
import re

import httpx

logger = logging.getLogger(__name__)


def strip_gutenberg_boilerplate(raw: str) -> str:
    """Remove common PG header/footer blocks heuristically."""
    lines = raw.splitlines()
    body_start = 0
    body_end = len(lines)
    for i, line in enumerate(lines):
        if "*** START OF" in line.upper() or "***START OF" in line.upper():
            body_start = i + 1
            break
    for j in range(len(lines) - 1, -1, -1):
        if "*** END OF" in lines[j].upper():
            body_end = j
            break
    body = "\n".join(lines[body_start:body_end])
    body = re.sub(r"\s+\n", "\n", body)
    return body.strip()


def fetch_gutenberg_text(epub_id: int, timeout: float) -> str:
    """Fetch UTF-8 text for Gutenberg ebook *epub_id*."""
    url = (
        f"https://www.gutenberg.org/cache/epub/{epub_id}/pg{epub_id}.txt"
    )
    logger.info("Fetching %s", url)
    with httpx.Client(timeout=timeout, follow_redirects=True) as client:
        resp = client.get(url)
        resp.raise_for_status()
    raw = resp.content.decode("utf-8", errors="replace")
    return strip_gutenberg_boilerplate(raw)
