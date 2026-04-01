"""Smoke-test OpenAI-клиента (AITunnel и т.д.).

Делегирует в ``app.llm_utils`` — тот же контур, что у пайплайна и API.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from app.llm_utils import (
    create_openai_client,
    load_llm_env,
    openai_base_url_from_env,
    resolve_openai_chat_model_id,
)


def _utf8_stdout() -> None:
    so = sys.stdout
    reconf = getattr(so, "reconfigure", None)
    if callable(reconf):
        try:
            reconf(encoding="utf-8")
        except OSError:
            pass


def main() -> None:
    _utf8_stdout()
    load_llm_env(override=True)

    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        print(
            "В .env задайте OPENAI_API_KEY (файл: "
            f"{_ROOT / '.env'}).",
            file=sys.stderr,
        )
        raise SystemExit(1)

    base = openai_base_url_from_env()
    if not base:
        print(
            "В .env задайте OPENAI_API_BASE (или OPENAI_BASE_URL), "
            "напр. https://api.aitunnel.ru/v1",
            file=sys.stderr,
        )
        raise SystemExit(1)

    client = create_openai_client(api_key, base_url=base)
    model = resolve_openai_chat_model_id(explicit=None, base_url=base)

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "user",
                    "content": (
                        "Привет! Расскажи о себе в двух предложениях."
                    ),
                },
            ],
            max_tokens=1000,
        )
    except Exception as exc:
        print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
        raise SystemExit(1) from None

    content = response.choices[0].message.content
    print(content if content else "")


if __name__ == "__main__":
    main()
