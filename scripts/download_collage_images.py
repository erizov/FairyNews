#!/usr/bin/env python3
"""Скачивает растровые кадры коллажа в ``frontend/collage/tile-*.jpg``.

Файлы с **Wikimedia Commons**; URL строится как
``/commons/{md5[0]}/{md5[:2]}/{имя_файла}`` (тот же алгоритм, что у CDN).
Лицензии и авторы — на страницах File: на Commons.

Перед первым запуском сгенерируйте SVG (fallback в браузере)::

    python scripts/generate_collage_assets.py

Затем::

    python scripts/download_collage_images.py

При HTTP 429 подождите и повторите; между запросами — пауза.
"""

from __future__ import annotations

import hashlib
import sys
import time
from pathlib import Path

import httpx

_ROOT = Path(__file__).resolve().parent.parent
_MAX_SIDE = 960
_MAX_BYTES_BEFORE_SHRINK = 450_000
_OUT = _ROOT / "frontend" / "collage"
_UA = (
    "FairyNewsCollage/1.0 "
    "(https://github.com/erizov/FairyNews; student diploma; collage decor)"
)

# (stem, точное имя файла на upload.wikimedia.org)
# Атрибуция: см. страницы File:… на commons.wikimedia.org
_SOURCES: tuple[tuple[str, str], ...] = (
    ("tile-00", "Newspaper_stack.jpg"),
    ("tile-01", "Old_paper.jpg"),
    ("tile-02", "London_from_a_hot_air_balloon.jpg"),
    ("tile-03", "Pleiades_large.jpg"),
    ("tile-04", "Open_book.jpg"),
    (
        "tile-05",
        "Two_bookshelves_full_of_books_belonging_to_Unitedmissionary_"
        "(2010).jpg",
    ),
    ("tile-06", "Forest_path.jpg"),
    ("tile-07", "Wood_texture.jpg"),
)


def _commons_url(filename: str) -> str:
    digest = hashlib.md5(filename.encode("utf-8")).hexdigest()
    return (
        "https://upload.wikimedia.org/wikipedia/commons/"
        f"{digest[0]}/{digest[0:2]}/{filename}"
    )


def _maybe_downscale_jpeg(path: Path) -> None:
    """Сжимает очень большие JPEG для быстрой отдачи с ``/static``."""
    try:
        from PIL import Image
    except ImportError:
        return
    try:
        if path.stat().st_size <= _MAX_BYTES_BEFORE_SHRINK:
            return
    except OSError:
        return
    with Image.open(path) as im:
        im.thumbnail(
            (_MAX_SIDE, _MAX_SIDE),
            Image.Resampling.LANCZOS,
        )
        rgb = im.convert("RGB") if im.mode in ("RGBA", "P") else im
        rgb.save(path, "JPEG", quality=85, optimize=True)


def main() -> None:
    _OUT.mkdir(parents=True, exist_ok=True)
    headers = {"User-Agent": _UA, "Accept": "image/*,*/*;q=0.8"}
    delay = 1.8
    with httpx.Client(
        headers=headers,
        timeout=60.0,
        follow_redirects=True,
    ) as client:
        for i, (stem, filename) in enumerate(_SOURCES):
            if i:
                time.sleep(delay)
            url = _commons_url(filename)
            dest = _OUT / f"{stem}.jpg"
            try:
                r = client.get(url)
                r.raise_for_status()
            except Exception as exc:
                print(f"FAIL {stem} ({filename}): {exc}", file=sys.stderr)
                continue
            ct = (r.headers.get("content-type") or "").lower()
            if "image" not in ct:
                print(
                    f"WARN {stem}: content-type {ct!r}",
                    file=sys.stderr,
                )
            dest.write_bytes(r.content)
            _maybe_downscale_jpeg(dest)
            rel = dest.relative_to(_ROOT)
            print("wrote", rel, dest.stat().st_size, "bytes")


if __name__ == "__main__":
    main()
