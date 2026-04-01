#!/usr/bin/env python3
"""Один прогон пайплайна для опытов этапа 4; итог — одна строка JSON в stdout."""

from __future__ import annotations

import json
import os
import sys
import traceback
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def main() -> None:
    if len(sys.argv) < 3:
        print(
            json.dumps(
                {"ok": False, "error": "usage: etap4_run_one.py NEWS_PATH PRESET_ID"},
            ),
        )
        raise SystemExit(2)
    news_path = Path(sys.argv[1])
    preset_id = sys.argv[2]
    os.chdir(_ROOT)
    try:
        from app.agents_pipeline import run_four_agent_pipeline
        from app.presets import get_preset

        news = news_path.read_text(encoding="utf-8").strip()
        preset = get_preset(preset_id)
        hint = str(preset["retrieval_hint"])
        domains = preset.get("domains")
        backend = os.environ.get("FAIRYNEWS_RAG_BACKEND", "snapshot").strip()
        out = run_four_agent_pipeline(
            news,
            hint,
            domains,
            preset_id=preset_id,
            news_id=None,
            rag_backend=backend,
        )
        rep = out.get("report") or {}
        rag = rep.get("rag") or {}
        llm = rep.get("llm") or {}
        tale = str(out.get("tale", ""))
        timing = rep.get("timing") or {}
        summary = {
            "ok": True,
            "tale_chars": len(tale),
            "tale_preview": tale[:280].replace("\n", " ") + ("…" if len(tale) > 280 else ""),
            "chosen_tale_source": out.get("chosen_tale_source"),
            "rag_k": rag.get("k_retrieve"),
            "llm_provider": llm.get("provider"),
            "llm_model": llm.get("model"),
            "audit_ok": (out.get("audit") or {}).get("approved"),
            "qa_question_len": len(str((out.get("qa") or {}).get("question", ""))),
            "timing": timing,
            "test_profile": rep.get("test_profile"),
        }
        print(json.dumps(summary, ensure_ascii=False))
    except Exception as exc:
        print(
            json.dumps(
                {
                    "ok": False,
                    "error": f"{type(exc).__name__}: {exc}"[:800],
                    "trace": traceback.format_exc()[-1500:],
                },
                ensure_ascii=False,
            ),
        )
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
