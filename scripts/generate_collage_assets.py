"""Пишет 8 SVG-картинок коллажа в ``frontend/collage`` (без сети).

Запуск из корня::

    python scripts/generate_collage_assets.py

Чтобы использовать свои JPEG/PNG, положите файлы в ``frontend/collage`` и
обновите имена и расширения в ``_COLLAGE_FILES`` (``app.api_schemas``).
"""

from __future__ import annotations

from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_OUT = _ROOT / "frontend" / "collage"

# stop-color пары (светлый → тёмный) под мотивы печати / фольклора.
_SWATCHES: tuple[tuple[str, str], ...] = (
    ("#e2d8c8", "#a89478"),
    ("#ddd4c4", "#9a8a72"),
    ("#d4ccc0", "#8c7e68"),
    ("#1a2433", "#3d4a5c"),
    ("#e8dcc8", "#9c7b58"),
    ("#dcd0bc", "#87755e"),
    ("#c8d4be", "#5f6b52"),
    ("#ebe2d6", "#a89888"),
)


def _svg(grad_id: str, c0: str, c1: str) -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<svg xmlns="http://www.w3.org/2000/svg" '
        'width="400" height="400" viewBox="0 0 400 400">\n'
        "  <defs>\n"
        f'    <linearGradient id="{grad_id}" x1="0%" y1="0%" '
        'x2="100%" y2="100%">\n'
        f'      <stop offset="0%" style="stop-color:{c0}"/>\n'
        f'      <stop offset="100%" style="stop-color:{c1}"/>\n'
        "    </linearGradient>\n"
        "  </defs>\n"
        f'  <rect width="400" height="400" fill="url(#{grad_id})"/>\n'
        "</svg>\n"
    )


def main() -> None:
    _OUT.mkdir(parents=True, exist_ok=True)
    for i, (c0, c1) in enumerate(_SWATCHES):
        gid = f"g{i}"
        path = _OUT / f"tile-{i:02d}.svg"
        path.write_text(_svg(gid, c0, c1), encoding="utf-8")
        print("wrote", path.relative_to(_ROOT))


if __name__ == "__main__":
    main()
