"""Tale-style presets for retrieval query shaping (MVP step 2)."""

from __future__ import annotations

from typing import Any

# ``domains`` passed to Chroma filter; ``None`` = all domains.
TALE_PRESETS: list[dict[str, Any]] = [
    {
        "id": "default",
        "label": "По умолчанию",
        "description": "Народный каркас без привязки к одному произведению",
        "retrieval_hint": (
            "русская народная сказка царство тридевятое царевна мороз "
            "иванушка-дурачок"
        ),
        "domains": None,
    },
    {
        "id": "russian_folk",
        "label": "Русский фольклор",
        "description": "Опоры из домена russian в индексе",
        "retrieval_hint": (
            "баба-яга жар-птица василиса мороз иван богатырь русская сказка"
        ),
        "domains": ("russian",),
    },
    {
        "id": "european",
        "label": "Европейские мотивы",
        "description": "Гримм, Перро, Андерсен и сборники (european*)",
        "retrieval_hint": (
            "сказка король принцесса волшебник лес европейская традиция"
        ),
        "domains": ("european", "european_compilation"),
    },
    {
        "id": "oriental",
        "label": "Восточные мотивы",
        "description": "Домен oriental (в т.ч. арабские сказки в сборниках)",
        "retrieval_hint": (
            "сказка визирь пустыня сокровище мудрец восточный фольклор"
        ),
        "domains": ("oriental",),
    },
]

_PRESET_BY_ID = {p["id"]: p for p in TALE_PRESETS}


def get_preset(preset_id: str) -> dict[str, Any]:
    """Return preset dict or raise KeyError."""
    return dict(_PRESET_BY_ID[preset_id])


def list_preset_ids() -> tuple[str, ...]:
    return tuple(_PRESET_BY_ID.keys())
