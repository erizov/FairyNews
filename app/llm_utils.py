"""Shared OpenAI client and JSON helpers for multi-agent calls."""

from __future__ import annotations

import json
import os
import re
from typing import Any

from openai import OpenAI


def get_openai_client() -> OpenAI:
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        raise RuntimeError("Задайте переменную окружения OPENAI_API_KEY.")
    return OpenAI(api_key=key)


def get_model_name() -> str:
    return os.environ.get("OPENAI_MODEL", "gpt-4o-mini")


def chat_text(
    client: OpenAI,
    model: str,
    system: str,
    user: str,
    *,
    temperature: float = 0.5,
    max_tokens: int = 2000,
) -> str:
    completion = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=temperature,
        max_tokens=max_tokens,
    )
    content = completion.choices[0].message.content
    return (content or "").strip()


def chat_json_object(
    client: OpenAI,
    model: str,
    system: str,
    user: str,
    *,
    temperature: float = 0.3,
    max_tokens: int = 1200,
) -> dict[str, Any]:
    """Ask model for a JSON object (API json_schema / json_object)."""
    completion = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=temperature,
        max_tokens=max_tokens,
        response_format={"type": "json_object"},
    )
    raw = completion.choices[0].message.content or "{}"
    return _parse_json_loose(raw)


def _parse_json_loose(raw: str) -> dict[str, Any]:
    raw = raw.strip()
    fence = re.search(r"\{[\s\S]*\}", raw)
    if fence:
        raw = fence.group(0)
    try:
        out = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return out if isinstance(out, dict) else {}
