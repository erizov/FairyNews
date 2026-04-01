"""Shared OpenAI client and JSON helpers for multi-agent calls.

Один контур с ``python -m app.llm_connect_try``: корневой ``.env``,
``OPENAI_API_BASE`` / ``OPENAI_BASE_URL``, нормализация ``/v1``, модель
для прокси (AITunnel / OpenRouter / Azure).
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from openai import OpenAI

_REPO_ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = _REPO_ROOT


def load_llm_env(*, override: bool = True) -> None:
    """Подгружает корневой ``.env`` репозитория (как ``llm_connect_try``)."""
    load_dotenv(_REPO_ROOT / ".env", override=override)


load_llm_env()


def normalize_openai_base(url: str) -> str:
    u = url.strip().rstrip("/")
    return u if u.endswith("/v1") else f"{u}/v1"


def _normalize_openai_base_url(url: str | None) -> str | None:
    if not url or not url.strip():
        return None
    return normalize_openai_base(url)


def openai_base_url_from_env() -> str | None:
    """``OPENAI_API_BASE`` first, then legacy ``OPENAI_BASE_URL``."""
    raw = os.environ.get("OPENAI_API_BASE", "").strip()
    if not raw:
        raw = os.environ.get("OPENAI_BASE_URL", "").strip()
    return _normalize_openai_base_url(raw if raw else None)


def _proxy_host_needs_openrouter_model_id(base: str | None) -> bool:
    """OpenRouter / AITunnel ожидают ``provider/model``, не сырой id OpenAI."""
    if not base:
        return False
    host = base.lower().split("//", 1)[-1].split("/", 1)[0]
    markers = (
        "aitunnel",
        "openrouter",
        "openai.azure.com",
    )
    return any(m in host for m in markers)


def _openai_official_base(base_url: str | None) -> bool:
    """Нет прокси: SDK по умолчанию ходит на api.openai.com."""
    if base_url is None or not str(base_url).strip():
        return True
    host = (
        str(base_url)
        .lower()
        .split("//", 1)[-1]
        .split("/", 1)[0]
        .split(":", 1)[0]
    )
    return host == "api.openai.com"


def resolve_openai_chat_model_id(
    *,
    explicit: str | None,
    base_url: str | None,
) -> str:
    """Идентификатор модели: explicit → env → дефолт (как ``llm_connect_try``).

    Для официального ``api.openai.com`` и ``base_url=None`` дефолт
    ``gpt-4o-mini``; для прокси — ``openai/gpt-5`` (каталог AITunnel).
    """
    parts: list[str] = []
    if explicit and explicit.strip():
        parts.append(explicit.strip())
    for var in ("LLM_CONNECT_TRY_MODEL", "OPENAI_MODEL"):
        v = os.environ.get(var, "").strip()
        if v:
            parts.append(v)
    if parts:
        m = parts[0]
    else:
        m = (
            "gpt-4o-mini"
            if _openai_official_base(base_url)
            else "openai/gpt-5"
        )

    if "/" not in m and _proxy_host_needs_openrouter_model_id(base_url):
        return f"openai/{m}"
    return m


def create_openai_client(
    api_key: str,
    *,
    base_url: str | None = None,
    timeout: float | None = None,
) -> OpenAI:
    """``OpenAI()`` с нормализованным ``base_url`` (как ``llm_connect_try``).

    Не вызывает ``load_dotenv``: окружение уже подгружено при импорте
    ``llm_utils`` или явным ``load_llm_env()`` (иначе тесты с ``delenv``
    ломались бы из-за повторного override из файла).
    """
    kwargs: dict[str, Any] = {"api_key": api_key}
    if base_url is not None and str(base_url).strip():
        kwargs["base_url"] = normalize_openai_base(str(base_url))
    if timeout is not None:
        kwargs["timeout"] = timeout
    return OpenAI(**kwargs)


def get_openai_client() -> OpenAI:
    load_llm_env()
    key = os.getenv("OPENAI_API_KEY", "").strip()
    if not key:
        raise RuntimeError("Задайте переменную окружения OPENAI_API_KEY.")
    base = openai_base_url_from_env()
    return create_openai_client(key, base_url=base)


def verify_openai_env_chat(
    *,
    model: str | None = None,
    max_tokens: int = 24,
) -> tuple[bool, str]:
    """Один короткий completion: ключ + base (AITunnel / OpenRouter proxy).

    Подхватывает корневой ``.env`` репозитория даже при другом CWD.
    """
    load_llm_env()

    key = os.getenv("OPENAI_API_KEY", "").strip()
    if not key:
        return False, "Нет OPENAI_API_KEY в .env"

    base = openai_base_url_from_env()
    if not base:
        return (
            False,
            "Нет OPENAI_API_BASE / OPENAI_BASE_URL (для AITunnel задайте "
            "URL, напр. https://api.aitunnel.ru/v1).",
        )

    m = resolve_openai_chat_model_id(explicit=model, base_url=base)

    try:
        client = get_openai_client()
    except RuntimeError as exc:
        return False, str(exc)

    try:
        response = client.chat.completions.create(
            model=m,
            messages=[{"role": "user", "content": "Say OK in one word."}],
            max_tokens=max_tokens,
        )
    except Exception as exc:
        return False, f"{type(exc).__name__}: {exc}"

    chunk = (response.choices[0].message.content or "").strip()
    preview = chunk[:120] + ("…" if len(chunk) > 120 else "")
    return True, f"OK base={base} model={m} reply={preview!r}"


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
