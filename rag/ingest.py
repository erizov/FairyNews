"""Build chunk records + content hashes from seeds (shared by full & incremental)."""

from __future__ import annotations

import hashlib
from typing import Any

from rag.chunking import chunk_text
from rag.config import CHUNK_OVERLAP_CHARS, CHUNK_TARGET_CHARS, ROOT


def content_sha256(text: str) -> str:
    """SHA-256 of normalized UTF-8 text."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _heroes_en_ru(item: dict[str, Any]) -> tuple[str, str]:
    """Pair (heroes_en, heroes_ru); legacy key ``heroes`` counts as English."""
    en = str(item.get("heroes_en") or item.get("heroes", ""))[:500]
    ru = str(item.get("heroes_ru", ""))[:500]
    return en, ru


def _content_lang_gutenberg(item: dict[str, Any]) -> str:
    """Language of chunk *text*: Gutenberg defaults to English."""
    raw = item.get("content_lang")
    if raw is not None and str(raw).strip():
        return str(raw).strip().lower()[:8]
    return "en"


def _content_lang_local(loc: dict[str, Any]) -> str:
    """Language of local file text; default Russian for ``local_tales``."""
    raw = loc.get("content_lang")
    if raw is not None and str(raw).strip():
        return str(raw).strip().lower()[:8]
    return "ru"


def records_from_gutenberg(
    item: dict[str, Any],
    full_text: str,
) -> tuple[str, str, list[tuple[str, str, dict[str, Any]]]]:
    """Return (source_key, sha256, [(chunk_id, text, metadata), ...])."""
    gid = int(item["id"])
    source_key = f"gutenberg:{gid}"
    digest = content_sha256(full_text)
    domain = str(item["domain"])
    note = str(item.get("note", ""))[:500]
    author = str(item.get("author", ""))[:300]
    country = str(item.get("country", ""))[:80]
    heroes_en, heroes_ru = _heroes_en_ru(item)
    content_lang = _content_lang_gutenberg(item)

    chunks = chunk_text(full_text, CHUNK_TARGET_CHARS, CHUNK_OVERLAP_CHARS)
    records: list[tuple[str, str, dict[str, Any]]] = []
    for i, ch in enumerate(chunks):
        cid = f"gutenberg-{gid}-c{i:05d}"
        meta = {
            "domain": domain,
            "source": source_key,
            "work_note": note,
            "author": author,
            "country": country,
            "heroes": heroes_en,
            "heroes_en": heroes_en,
            "heroes_ru": heroes_ru,
            "content_lang": content_lang,
            "content_sha256": digest,
            "chunk_index": int(i),
        }
        records.append((cid, ch, meta))
    return source_key, digest, records


def records_from_local_file(
    rel_posix: str,
    text: str,
    domain: str,
    *,
    author: str = "",
    country: str = "",
    heroes_en: str = "",
    heroes_ru: str = "",
    content_lang: str = "ru",
) -> tuple[str, str, list[tuple[str, str, dict[str, Any]]]]:
    """Index one local UTF-8 tale file."""
    source_key = f"file:{rel_posix}"
    digest = content_sha256(text)
    note = f"local:{rel_posix}"[:500]
    he = str(heroes_en)[:500]
    hr = str(heroes_ru)[:500]
    clang = str(content_lang).strip().lower()[:8] or "ru"

    chunks = chunk_text(text, CHUNK_TARGET_CHARS, CHUNK_OVERLAP_CHARS)
    records: list[tuple[str, str, dict[str, Any]]] = []
    safe = rel_posix.replace("/", "_")
    for i, ch in enumerate(chunks):
        cid = f"local-{safe}-c{i:05d}"
        meta = {
            "domain": domain,
            "source": source_key,
            "work_note": note,
            "author": author[:300],
            "country": country[:80],
            "heroes": he,
            "heroes_en": he,
            "heroes_ru": hr,
            "content_lang": clang,
            "content_sha256": digest,
            "chunk_index": int(i),
        }
        records.append((cid, ch, meta))
    return source_key, digest, records


def iter_local_txts(pattern: str, default_domain: str) -> list[tuple[str, str, str]]:
    """Return (relative posix path, text, domain) for each matched file."""
    found: list[tuple[str, str, str]] = []
    for p in sorted(ROOT.glob(pattern)):
        if not p.is_file():
            continue
        text = p.read_text(encoding="utf-8", errors="replace")
        rel = p.relative_to(ROOT).as_posix()
        found.append((rel, text, default_domain))
    return found


def iter_local_globs_dedup(
    local_globs: list[dict[str, Any]],
) -> list[tuple[str, str, str, str, str, str, str, str]]:
    """Apply globs in order; each *rel_path* only once (first match wins).

    Returns (rel_path, text, domain, author, country, heroes_en, heroes_ru,
    content_lang).
    """
    seen: set[str] = set()
    rows: list[tuple[str, str, str, str, str, str, str, str]] = []
    for loc in local_globs:
        pattern = str(loc["pattern"])
        dd = str(loc.get("default_domain", "russian"))
        auth = str(loc.get("author", ""))
        ctry = str(loc.get("country", ""))
        he = str(loc.get("heroes_en") or loc.get("heroes", ""))
        hr = str(loc.get("heroes_ru", ""))
        clang = _content_lang_local(loc)
        for rel_path, text, dom in iter_local_txts(pattern, dd):
            if rel_path in seen:
                continue
            seen.add(rel_path)
            rows.append((rel_path, text, dom, auth, ctry, he, hr, clang))
    return rows
