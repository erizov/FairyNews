"""Bridge from RAG to the story-generation agent (orchestration stubs).

Multi-agent chain (planned under FastAPI):

1. **News agent** — актуальная повестка без RAG по сказкам.
2. **Story-generation agent** — промпт + `retrieve_plot_context` + сводка новостей.
3. **Audit agent** — отдельный вызов GPT с инструкцией проверки.
4. **Q&A agent** — вопрос по тексту сказки + эталонный ответ; отдельный промпт.

Веб — только оболочка; внутри — **мультиагентная оркестрация** и **многократные
вызовы GPT** (минимум по одному разу на роль, промпты различаются).
"""

from __future__ import annotations

from rag.retrieve import retrieve_plot_context


def context_for_story_agent(
    plot_query: str,
    *,
    k: int = 8,
    domains: tuple[str, ...] | None = None,
) -> str:
    """Retrieve tale-plot passages to inject into the story agent prompt."""
    return retrieve_plot_context(
        plot_query,
        k=k,
        domains=domains,
    )
