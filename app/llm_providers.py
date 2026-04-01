"""LLM backends: OpenAI-compatible API or stub when no key / forced."""

from __future__ import annotations

import os
import re
from typing import Any, Protocol, runtime_checkable

from app.gigachat_requests import GigaChatRequestsProvider
from app.llm_utils import (
    _parse_json_loose,
    create_openai_client,
    normalize_openai_base,
    openai_base_url_from_env,
    resolve_openai_chat_model_id,
)


@runtime_checkable
class LLMProvider(Protocol):
    """Chat completion contract for the four-agent pipeline."""

    @property
    def model_label(self) -> str:
        ...

    @property
    def provider_name(self) -> str:
        ...

    def chat_text(
        self,
        system: str,
        user: str,
        *,
        temperature: float = 0.5,
        max_tokens: int = 2000,
    ) -> str:
        ...

    def chat_json_object(
        self,
        system: str,
        user: str,
        *,
        temperature: float = 0.3,
        max_tokens: int = 1200,
    ) -> dict[str, Any]:
        ...


class OpenAILLMProvider:
    """OpenAI or compatible endpoint via ``OPENAI_API_BASE`` / ``OPENAI_BASE_URL``."""

    def __init__(
        self,
        api_key: str,
        model: str,
        *,
        base_url: str | None = None,
    ) -> None:
        self._model = model
        self._client = create_openai_client(api_key, base_url=base_url)

    @property
    def model_label(self) -> str:
        return self._model

    @property
    def provider_name(self) -> str:
        return "openai"

    def chat_text(
        self,
        system: str,
        user: str,
        *,
        temperature: float = 0.5,
        max_tokens: int = 2000,
    ) -> str:
        completion = self._client.chat.completions.create(
            model=self._model,
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
        self,
        system: str,
        user: str,
        *,
        temperature: float = 0.3,
        max_tokens: int = 1200,
    ) -> dict[str, Any]:
        completion = self._client.chat.completions.create(
            model=self._model,
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


def _offline_long_tale(snippet: str) -> str:
    """Deterministic multi-paragraph tale for captures and offline runs."""
    hook = snippet.strip()[:220].replace("\n", " ")
    if not hook:
        hook = "было царство, где люди учились договариваться без обмана."
    return (
        "Жил-был в тридевятом государстве царь Добронрав, и слава о нём "
        "шла далеко за морем-океаном: не златом клал он себе в казну "
        "гордости, а тишиной суда и ровностью сроков. Однажды на "
        "государев двор пришли мастера со всех концов: дровосеки, печники, "
        "печные трубы подводившие, няньки к малым детям и старцам — словом, "
        "всяк, кто ладил человеческое житьё-бытьё.\n\n"
        "И стало у царя забота великая. Ведь не всякий пришедший приносил "
        "с собою запись на пергаменте, откуда родом и по какому праву "
        "ремесло ведёт. Одни клялись на иконе, другие молчали, третьи "
        "торопились: «дай работу на вчера, да мзду наличной». А советники "
        "царские шептали: «Государь, государь, закон не спит: кто нанял "
        "без образу, тот за обиду ответит, хоть во дворе сидел, хоть на "
        "отшибе в терему».\n\n"
        "Собрал царь народ на площадь песчаную, где колодец да крытый со "
        "снедью ряд, и речь сказал не грозную, а размеренную, будто тётка "
        "сказку вечернюю ткёт. «Не в бровь вам, люди добрые, а в глаз, — "
        "говорит, — вся работа честна, коли честно сделана. Но смотрите: "
        "кто примет под стражу дом чужой без приглашу, тот сам станет "
        "сторожем вдвойне: за дом и за правду. Кто даст слово без печати "
        "на листе, тот расплатится не словом, а тяжёлою казною, и обида "
        "уйдёт по деревне быстрее доброй молвы».\n\n"
        "Старейшины качали головами, молодые слушали — кто зевал, кто "
        "крестил плечи. А царь приложил перст к пергаменту, что сам "
        "начертал: «Перво — спросить; второ — сверить; третье — записать; "
        "четвёрто — заплатить по сроку». И повелел немногим грамотеям "
        "ходить по окраинам да сверять, не врёт ли печать, не подменён ли "
        "устав, чтобы не вышло, что сказка хороша, а житьё — в суде "
        "кончается.\n\n"
        "Тут-то и вышла на площадь крылатая беда — спор двух соседей, "
        "давно друг друга терпевших. Один говорил: «Я работника приютил, "
        "хлеб дал, а отвечать за царский указ — не мой удел». Другой — "
        "что «хлеб-то общий, вина-то тоже общая, коли двор один». Царь "
        "не палкой рассек, а третьим словом: «Кто нанял, тот и ведёт "
        "дорогу. Кто платит ломом золотым, тот за лом отвечает. Учитесь "
        "вопрошать до сделки, а не после обиды».\n\n"
        "С тех пор в том государстве и повадились люди: прежде чем крышу "
        "чинить или забор поднимать, глядят в книгу уставную, звонят "
        "вестовому, клеймят срок на берёсте. И стало меньше криков через "
        "забор, больше смеху на завалинке. Бабки сказку помянут, а мужики "
        "— порядок в работе прозовут. А царь Добронрав сказал на прощанье "
        "короткое, но крепкое: «Сказка спасёт мир, коли в ней не врать "
        "ни другим, ни себе».\n\n"
        "И конец тому рассказу ровный: кто слова царевы в сердце унёс, "
        "тот и дома свой мирно водил; кто презрел — сам на себя горе "
        "натянул. Так в старых летописях и дожили до нас эти речи, а "
        "молодым наука — думать наперёд, прежде чем топор взять или няню "
        "в дом пустить.\n\n"
        f"Нить аллегории тянется к нашим дням: {hook}… "
        "И помните навсегда: в доброй сказке платят добродетелью, а в "
        "живой приходе — законом и совестью."
    )


class StubLLMProvider:
    """Offline demo: no API; deterministic fairy-tale-shaped output."""

    def __init__(self) -> None:
        self._json_phase = 0

    @property
    def model_label(self) -> str:
        return "offline-default"

    @property
    def provider_name(self) -> str:
        return "offline"

    def _news_body(self, user: str) -> str:
        m = re.search(r"Новость:\n(.*)", user, re.DOTALL)
        return (m.group(1).strip() if m else user.strip())[:800]

    def _story_hook(self, user: str) -> str:
        """Pulls the news summary slice from the story agent user prompt."""
        m = re.search(
            r"Новость \(структурировано\):\n(.*?)\nТемы:",
            user,
            re.DOTALL,
        )
        if m:
            return m.group(1).strip().replace("\n", " ")[:400]
        return self._news_body(user)[:400].replace("\n", " ")

    def chat_json_object(
        self,
        system: str,
        user: str,
        *,
        temperature: float = 0.3,
        max_tokens: int = 1200,
    ) -> dict[str, Any]:
        del system, temperature, max_tokens
        self._json_phase += 1
        if self._json_phase == 1:
            body = self._news_body(user)
            return {
                "summary": (
                    body[:400]
                    if body
                    else "Была новость в тридевятом царстве."
                ),
                "themes": ["народ", "справедливость", "терем"],
                "retrieval_keywords": "русская народная сказка царь",
            }
        if self._json_phase == 2:
            return {"approved": True, "notes": "замечаний нет", "tale": ""}
        return {
            "question": (
                "Почему царь Добронрав требует сверять документы до сделки, "
                "а не после спора?"
            ),
            "reference_answer": (
                "Потому что работодатель несёт ответственность за тех, кого "
                "нанимает: заранее сверить статус справедливее, чем платить "
                "штрафами после обиды."
            ),
        }

    def chat_text(
        self,
        system: str,
        user: str,
        *,
        temperature: float = 0.5,
        max_tokens: int = 2000,
    ) -> str:
        del system, temperature, max_tokens
        return _offline_long_tale(self._story_hook(user))


def _groq_key() -> str:
    return (
        os.environ.get("GROQ_KEY", "").strip()
        or os.environ.get("GROQ_API_KEY", "").strip()
    )


def _deepseek_key() -> str:
    s = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    if s.endswith("=") and s.count("=") == 1:
        s = s[:-1]
    return s


def _resolved_openai_proxy_model(explicit: str | None) -> str:
    """Как ``llm_connect_try``: AITunnel / OpenRouter — id вида provider/model."""
    base = openai_base_url_from_env()
    ex = (explicit or "").strip() or None
    return resolve_openai_chat_model_id(explicit=ex, base_url=base)


def _gemini_openai_compatible_provider(model: str | None) -> LLMProvider:
    """Gemini через OpenAI-совместимый endpoint (Google AI или прокси)."""
    key = (
        os.environ.get("GEMINI_API_KEY", "").strip()
        or os.environ.get("GOOGLE_API_KEY", "").strip()
    )
    if not key:
        raise RuntimeError("Нужен GEMINI_API_KEY или GOOGLE_API_KEY")
    m = (
        (model or "").strip()
        or os.environ.get("GEMINI_MODEL", "gemini-2.5-flash").strip()
    )
    raw = os.environ.get(
        "GEMINI_OPENAI_BASE",
        "https://generativelanguage.googleapis.com/v1beta/openai",
    ).strip()
    base = normalize_openai_base(raw)
    return OpenAILLMProvider(key, m, base_url=base)


def build_llm_from_backend(
    backend: str,
    *,
    model: str | None = None,
) -> LLMProvider:
    """Явный backend для режима разных моделей по этапам (TEST 1)."""
    b = backend.strip().lower()
    if not b:
        raise RuntimeError("Пустой backend")
    if b == "stub":
        if os.environ.get("FAIRYNEWS_LLM_MODE", "").strip().lower() != "stub":
            raise RuntimeError(
                "backend=stub в FAIRYNEWS_STAGE_* только при "
                "FAIRYNEWS_LLM_MODE=stub"
            )
        return get_llm_provider()
    if b == "gigachat":
        giga = os.environ.get("GIGACHAT_API_KEY", "").strip()
        if not giga:
            raise RuntimeError("Нужен GIGACHAT_API_KEY")
        m = (model or "").strip() or None
        return GigaChatRequestsProvider(giga, model=m)
    if b == "groq":
        k = _groq_key()
        if not k:
            raise RuntimeError("Нужен GROQ_KEY или GROQ_API_KEY")
        m = (
            (model or "").strip()
            or os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile").strip()
        )
        return OpenAILLMProvider(
            k,
            m,
            base_url="https://api.groq.com/openai/v1",
        )
    if b == "deepseek":
        k = _deepseek_key()
        if not k:
            raise RuntimeError("Нужен DEEPSEEK_API_KEY")
        m = (model or "").strip() or "deepseek-chat"
        return OpenAILLMProvider(
            k,
            m,
            base_url="https://api.deepseek.com/v1",
        )
    if b == "openai":
        key = os.environ.get("OPENAI_API_KEY", "").strip()
        if not key:
            raise RuntimeError("Нужен OPENAI_API_KEY")
        m = _resolved_openai_proxy_model((model or "").strip() or None)
        return OpenAILLMProvider(key, m, base_url=openai_base_url_from_env())
    if b == "gemini":
        return _gemini_openai_compatible_provider(model)
    raise RuntimeError(f"Неизвестный backend={backend!r}")


_PIPELINE_STAGE_KEYS: tuple[tuple[str, str], ...] = (
    ("news", "NEWS"),
    ("story", "STORY"),
    ("audit", "AUDIT"),
    ("qa", "QA"),
)


def _stage_backend_var(stage: str) -> str:
    for name, suffix in _PIPELINE_STAGE_KEYS:
        if name == stage:
            return f"FAIRYNEWS_STAGE_{suffix}_BACKEND"
    raise ValueError(f"Неизвестный этап: {stage!r}")


def _stage_model_var(stage: str) -> str:
    for name, suffix in _PIPELINE_STAGE_KEYS:
        if name == stage:
            return f"FAIRYNEWS_STAGE_{suffix}_MODEL"
    raise ValueError(f"Неизвестный этап: {stage!r}")


def resolve_pipeline_llm_providers(
    *,
    llm: LLMProvider | None = None,
) -> tuple[bool, dict[str, LLMProvider]]:
    """Один провайдер на все этапы либо четыре (FAIRYNEWS_LLM_PER_STAGE)."""
    if llm is not None:
        p = llm
        return False, {name: p for name, _ in _PIPELINE_STAGE_KEYS}

    per = os.environ.get("FAIRYNEWS_LLM_PER_STAGE", "").strip().lower()
    per_on = per in ("1", "true", "yes", "on")
    uni = os.environ.get("FAIRYNEWS_LLM_UNIFORM_STAGES", "").strip().lower()
    uniform_on = uni in ("1", "true", "yes", "on")
    if not per_on and not uniform_on:
        p = get_llm_provider()
        return False, {name: p for name, _ in _PIPELINE_STAGE_KEYS}

    if uniform_on:
        ub = os.environ.get("FAIRYNEWS_UNIFORM_BACKEND", "").strip()
        if not ub:
            raise RuntimeError(
                "FAIRYNEWS_LLM_UNIFORM_STAGES: задайте FAIRYNEWS_UNIFORM_BACKEND "
                "(TEST2: один backend+модель на все этапы)."
            )
        um = os.environ.get("FAIRYNEWS_UNIFORM_MODEL", "").strip()
        single = build_llm_from_backend(ub, model=um or None)
        return True, {name: single for name, _ in _PIPELINE_STAGE_KEYS}

    default_shared: LLMProvider | None = None
    out: dict[str, LLMProvider] = {}
    for name, _suf in _PIPELINE_STAGE_KEYS:
        b = os.environ.get(_stage_backend_var(name), "").strip()
        if b:
            m = os.environ.get(_stage_model_var(name), "").strip()
            out[name] = build_llm_from_backend(b, model=m or None)
        else:
            if default_shared is None:
                default_shared = get_llm_provider()
            out[name] = default_shared
    return True, out


def get_llm_provider() -> LLMProvider:
    """Выбор провайдера по env (в т.ч. ``FAIRYNEWS_LLM_BACKEND`` для опытов)."""
    mode = os.environ.get("FAIRYNEWS_LLM_MODE", "").strip().lower()
    if mode == "stub":
        return StubLLMProvider()

    forced = os.environ.get("FAIRYNEWS_LLM_BACKEND", "").strip().lower()
    if forced:
        if forced == "gemini":
            return build_llm_from_backend("gemini", model=None)
        if forced in (
            "gigachat",
            "groq",
            "deepseek",
            "openai",
        ):
            return build_llm_from_backend(forced, model=None)
        raise RuntimeError(
            f"Неизвестный FAIRYNEWS_LLM_BACKEND={forced!r}"
        )

    skip_giga = os.environ.get("FAIRYNEWS_SKIP_GIGACHAT", "").strip().lower()
    skip_giga_on = skip_giga in ("1", "true", "yes", "on")
    prefer_giga = os.environ.get("FAIRYNEWS_PREFER_GIGACHAT", "").strip().lower()
    prefer_giga_on = prefer_giga in ("1", "true", "yes", "on")

    giga = os.environ.get("GIGACHAT_API_KEY", "").strip()
    key = os.environ.get("OPENAI_API_KEY", "").strip()

    if giga and not skip_giga_on and (not key or prefer_giga_on):
        return GigaChatRequestsProvider(giga)
    if key:
        m = _resolved_openai_proxy_model(None)
        return OpenAILLMProvider(key, m, base_url=openai_base_url_from_env())
    if giga and not skip_giga_on:
        return GigaChatRequestsProvider(giga)
    return StubLLMProvider()
