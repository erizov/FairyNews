#!/usr/bin/env python3
"""Download Nukadeti.ru texts into local RAG corpus (.txt).

Targets:
- https://nukadeti.ru/skazki/evgeniy-shvarc
- https://nukadeti.ru/basni/tolstoj
- https://nukadeti.ru/basni/mikhalkov

Saves UTF-8 .txt files under:
    data/raw/local_tales/soviet/nukadeti/<author_slug>/

Stops early if downloads appear blocked or parsing yields no links/text.
Prints progress at least every 10 minutes (time-based).
"""

from __future__ import annotations

import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent.parent
OUT_BASE = ROOT / "data" / "raw" / "local_tales" / "soviet" / "nukadeti"

UA = (
    "FairyNewsRAGDownloader/1.0 "
    "(https://github.com/erizov/FairyNews; educational use)"
)


@dataclass(frozen=True)
class Catalog:
    url: str
    author_slug: str
    author_ru: str
    kind_ru: str


CATALOGS: tuple[Catalog, ...] = (
    Catalog(
        url="https://nukadeti.ru/skazki/evgeniy-shvarc",
        author_slug="shvarc",
        author_ru="Евгений Шварц",
        kind_ru="сказки",
    ),
    Catalog(
        url="https://nukadeti.ru/basni/tolstoj",
        author_slug="tolstoy",
        author_ru="Лев Толстой",
        kind_ru="басни",
    ),
    Catalog(
        url="https://nukadeti.ru/basni/mikhalkov",
        author_slug="mikhalkov",
        author_ru="Сергей Михалков",
        kind_ru="басни",
    ),
)


_WS = re.compile(r"[ \t\r\f\v]+")
_NL3 = re.compile(r"\n{3,}")
_SAFE = re.compile(r"[^a-z0-9_.-]+")


def _norm_text(s: str) -> str:
    s = s.replace("\u00a0", " ")
    s = _WS.sub(" ", s)
    return s.strip()


def _clean_block_text(s: str) -> str:
    s = s.replace("\u00a0", " ")
    s = s.replace("\r\n", "\n").replace("\r", "\n")
    lines = [ln.strip() for ln in s.split("\n")]
    s2 = "\n".join([ln for ln in lines if ln])
    s2 = _NL3.sub("\n\n", s2)
    return s2.strip()


def _slugify(name: str) -> str:
    name = name.strip().lower()
    name = re.sub(r"^https?://", "", name)
    name = name.replace("/", "_")
    name = _SAFE.sub("_", name)
    name = re.sub(r"_+", "_", name).strip("_")
    return name[:120] or "item"


def _same_host(a: str, b: str) -> bool:
    try:
        return urlparse(a).netloc == urlparse(b).netloc
    except ValueError:
        return False


def _fetch(client: httpx.Client, url: str) -> str:
    r = client.get(url)
    r.raise_for_status()
    return r.text


def _extract_links(catalog_url: str, html: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    anchors = soup.select("a.img[href]") or soup.select("a[href]")
    out: list[str] = []
    want_basni = "/basni/" in catalog_url
    want_skazki = "/skazki/" in catalog_url
    for a in anchors:
        href = str(a.get("href") or "").strip()
        if not href:
            continue
        abs_url = urljoin(catalog_url, href)
        if not _same_host(abs_url, catalog_url):
            continue
        # Keep only item pages in same section; skip category roots.
        if abs_url.rstrip("/") == catalog_url.rstrip("/"):
            continue
        if not ("/skazki/" in abs_url or "/basni/" in abs_url):
            continue
        if want_basni and "/basni/" not in abs_url:
            continue
        if want_skazki and "/skazki/" not in abs_url:
            continue
        # Hard filter: exclude obvious taxonomy pages on the tales catalog.
        path = urlparse(abs_url).path.rstrip("/")
        if "/skazki/" in abs_url:
            bad = (
                path.endswith("/skazki/avtorskie")
                or path.endswith("/skazki/skazki-po-vozrastam")
                or path.endswith("/skazki/pro-detej")
                or path.endswith("/skazki/pouchitelnye")
                or path.endswith("/skazki/skazki-dlya-shkolnikov")
                or path.startswith("/skazki/dlya_")
                or path.startswith("/skazki/dlya-")
                or path.startswith("/skazki/skazki-dlya-")
                or path.startswith("/skazki/pro_")
                or path.startswith("/skazki/o_")
            )
            if bad:
                continue
        out.append(abs_url)
    # De-dup while preserving order.
    seen: set[str] = set()
    uniq: list[str] = []
    for u in out:
        if u in seen:
            continue
        seen.add(u)
        uniq.append(u)
    return uniq


def _extract_title_and_text(url: str, html: str) -> tuple[str, str]:
    soup = BeautifulSoup(html, "html.parser")
    h1 = soup.find("h1")
    title = _norm_text(h1.get_text(" ", strip=True)) if h1 else ""
    block = soup.select_one(".tale-text")
    if block is None:
        # Fallback for other layouts.
        block = soup.select_one("article") or soup.select_one("main")
    text = ""
    if block is not None:
        text = _clean_block_text(block.get_text("\n", strip=True))
    return title, text


def _write_text(
    *,
    dest: Path,
    title: str,
    text: str,
    source_url: str,
    author_ru: str,
    kind_ru: str,
) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    header = (
        f"Источник: {source_url}\n"
        f"Автор: {author_ru}\n"
        f"Раздел: {kind_ru}\n"
        f"Заголовок: {title}\n"
        "\n"
    )
    dest.write_text(header + text.strip() + "\n", encoding="utf-8")


def main() -> None:
    started = time.monotonic()
    last_progress = started
    total_saved = 0

    with httpx.Client(
        headers={"User-Agent": UA, "Accept": "text/html,*/*;q=0.8"},
        follow_redirects=True,
        timeout=60.0,
    ) as client:
        for cat in CATALOGS:
            print(f"[catalog] {cat.url}", flush=True)
            try:
                html = _fetch(client, cat.url)
            except Exception as exc:
                print(f"ERROR: cannot load catalog: {cat.url}: {exc}", file=sys.stderr)
                raise SystemExit(2) from None

            links = _extract_links(cat.url, html)
            if not links:
                print(
                    f"ERROR: no item links extracted from {cat.url}; "
                    "download/parsing likely blocked.",
                    file=sys.stderr,
                )
                raise SystemExit(3) from None

            out_dir = OUT_BASE / cat.author_slug
            saved_here = 0
            consecutive_fail = 0

            for idx, item_url in enumerate(links, start=1):
                now = time.monotonic()
                if now - last_progress >= 600:
                    elapsed_min = int((now - started) // 60)
                    print(
                        f"[progress] {elapsed_min} min; saved {total_saved} files so far",
                        flush=True,
                    )
                    last_progress = now

                try:
                    item_html = _fetch(client, item_url)
                    title, text = _extract_title_and_text(item_url, item_html)
                except httpx.HTTPStatusError as exc:
                    code = exc.response.status_code
                    print(
                        f"ERROR: HTTP {code} on {item_url} — stopping.",
                        file=sys.stderr,
                    )
                    raise SystemExit(4) from None
                except Exception as exc:
                    consecutive_fail += 1
                    print(
                        f"WARN: failed {item_url}: {exc} "
                        f"(consecutive_fail={consecutive_fail})",
                        file=sys.stderr,
                    )
                    if consecutive_fail >= 3:
                        print("ERROR: too many failures — stopping.", file=sys.stderr)
                        raise SystemExit(5) from None
                    continue

                consecutive_fail = 0
                if not title or len(text) < 60:
                    print(
                        f"ERROR: empty/short text on {item_url} — stopping.",
                        file=sys.stderr,
                    )
                    raise SystemExit(6) from None

                slug = _slugify(Path(urlparse(item_url).path).name or item_url)
                dest = out_dir / f"nukadeti_{slug}.txt"
                _write_text(
                    dest=dest,
                    title=title,
                    text=text,
                    source_url=item_url,
                    author_ru=cat.author_ru,
                    kind_ru=cat.kind_ru,
                )
                saved_here += 1
                total_saved += 1

                if idx == 1 or idx % 10 == 0:
                    print(
                        f"  saved {saved_here}/{len(links)}: {dest.relative_to(ROOT)}",
                        flush=True,
                    )

                time.sleep(1.1)

            print(
                f"[done] {cat.author_ru}: saved {saved_here} files into "
                f"{out_dir.relative_to(ROOT)}",
                flush=True,
            )

    elapsed = int((time.monotonic() - started) // 60)
    print(f"Done. Saved {total_saved} files. Elapsed ~{elapsed} min.", flush=True)


if __name__ == "__main__":
    main()

