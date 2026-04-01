"""GigaChat REST API через ``requests``: OAuth и chat completions."""

from __future__ import annotations

import logging
import os
import time
import uuid
from typing import Any

import requests
import urllib3

from app.llm_utils import _parse_json_loose

logger = logging.getLogger(__name__)

_DEFAULT_OAUTH = "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"
_DEFAULT_CHAT = (
    "https://gigachat.devices.sberbank.ru/api/v1/chat/completions"
)


class GigaChatRequestsProvider:
    """LLMProvider на GigaChat (официальный REST)."""

    def __init__(
        self,
        auth_key: str,
        *,
        scope: str | None = None,
        model: str | None = None,
        oauth_url: str | None = None,
        chat_url: str | None = None,
        timeout: float = 120.0,
    ) -> None:
        self._auth_key = auth_key.strip()
        self._scope = (
            (scope or os.environ.get("GIGACHAT_SCOPE", "")).strip()
            or "GIGACHAT_API_PERS"
        )
        self._model = (
            (model or os.environ.get("GIGACHAT_MODEL", "")).strip()
            or "GigaChat"
        )
        self._oauth_url = (oauth_url or _DEFAULT_OAUTH).strip()
        self._chat_url = (chat_url or _DEFAULT_CHAT).strip()
        self._timeout = timeout
        self._verify = (
            os.environ.get("GIGACHAT_SSL_VERIFY", "1").strip().lower()
            not in ("0", "false", "no")
        )
        self._access_token: str | None = None
        self._token_deadline: float = 0.0

    @property
    def model_label(self) -> str:
        return self._model

    @property
    def provider_name(self) -> str:
        return "gigachat"

    def _token_valid(self) -> bool:
        if not self._access_token:
            return False
        return time.time() < self._token_deadline - 45.0

    def _fetch_token(self) -> None:
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
            "RqUID": str(uuid.uuid4()),
            "Authorization": f"Basic {self._auth_key}",
        }
        try:
            resp = requests.post(
                self._oauth_url,
                headers=headers,
                data={"scope": self._scope},
                timeout=self._timeout,
                verify=self._verify,
            )
            if not resp.ok:
                logger.warning("GigaChat OAuth failed: %s", resp.text[:800])
            resp.raise_for_status()
        except requests.HTTPError as exc:
            code = getattr(exc.response, "status_code", "?")
            logger.error(
                "GigaChat OAuth HTTP error: status=%s body=%s",
                code,
                (exc.response.text[:800] if exc.response else ""),
            )
            raise RuntimeError(
                "GigaChat: ошибка OAuth (ключ, scope или сертификат). "
                "Проверьте GIGACHAT_API_KEY и GIGACHAT_SCOPE; при наличии "
                "OPENAI_API_KEY он используется по умолчанию раньше GigaChat. "
                "Для принудительного OpenAI: FAIRYNEWS_LLM_BACKEND=openai."
            ) from None
        data = resp.json()
        token = str(data.get("access_token", "")).strip()
        if not token:
            raise RuntimeError("GigaChat OAuth: нет access_token в ответе")
        self._access_token = token
        exp_raw = data.get("expires_at")
        if exp_raw is None:
            self._token_deadline = time.time() + 25 * 60
            return
        exp = float(exp_raw)
        if exp > 1e12:
            exp = exp / 1000.0
        self._token_deadline = exp

    def _ensure_token(self) -> None:
        if self._token_valid():
            return
        self._fetch_token()

    def _post_chat(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float,
        max_tokens: int,
    ) -> str:
        self._ensure_token()
        headers = {
            "Authorization": f"Bearer {self._access_token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        body: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
        }
        resp = requests.post(
            self._chat_url,
            headers=headers,
            json=body,
            timeout=self._timeout,
            verify=self._verify,
        )
        if not resp.ok:
            logger.warning("GigaChat chat failed: %s", resp.text[:500])
        resp.raise_for_status()
        out = resp.json()
        choices = out.get("choices") or []
        if not choices:
            return ""
        msg = choices[0].get("message") or {}
        return str(msg.get("content", "")).strip()

    def chat_text(
        self,
        system: str,
        user: str,
        *,
        temperature: float = 0.5,
        max_tokens: int = 2000,
    ) -> str:
        messages: list[dict[str, str]] = []
        if system.strip():
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": user})
        return self._post_chat(
            messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    def chat_json_object(
        self,
        system: str,
        user: str,
        *,
        temperature: float = 0.3,
        max_tokens: int = 1200,
    ) -> dict[str, Any]:
        sys2 = (
            system.strip()
            + "\n\nОтветь одним JSON-объектом без пояснений и без "
            "markdown."
        )
        raw = self.chat_text(
            sys2,
            user,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return _parse_json_loose(raw)
