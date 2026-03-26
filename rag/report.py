"""Aggregate statistics from the fairy-tale RAG index."""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from collections import Counter
from typing import Any, Literal

from rag.store import get_collection

_HERO_SPLIT = re.compile(r"[;,]\s*")

Lang = Literal["ru", "en", "bi"]

_LABELS_RU: dict[str, str] = {
    "title": "Отчёт RAG (корпус сказок)",
    "summary": "Краткая сводка",
    "total_chunks": "Всего чанков",
    "unique_works": "Уникальных произведений",
    "by_domain": "По домену",
    "by_country": "По стране / региону",
    "by_author": "По автору",
    "by_content_lang": "По языку текста чанков",
    "chunks_per_work": "Чанков на произведение",
    "works": "Произведения (снимок метаданных)",
    "heroes_col": "Подсказки по образам героев",
    "hero_hints": "Частота слов в подсказках героев",
    "note": "Примечание",
}

# Short English for parentheses after Russian labels.
_LABELS_EN: dict[str, str] = {
    "title": "Fairy-tale RAG corpus report",
    "summary": "Brief summary",
    "total_chunks": "total chunks",
    "unique_works": "unique works",
    "by_domain": "by domain",
    "by_country": "by country / region",
    "by_author": "by author",
    "by_content_lang": "by chunk text language",
    "chunks_per_work": "chunks per work",
    "works": "works (metadata snapshot)",
    "heroes_col": "hero figure hints",
    "hero_hints": "hero hint token frequency",
    "note": "Note",
}


def _norm(s: str | None) -> str:
    if not s:
        return ""
    return str(s).strip()


def _report_notes_empty() -> dict[str, str]:
    return {
        "ru": "Индекс пуст — выполните: python -m rag --reset",
        "en": "Index empty — run: python -m rag --reset",
    }


def _report_notes_full() -> dict[str, str]:
    return {
        "ru": (
            "«Произведение» = один уникальный source (книга Gutenberg по id или "
            "локальный .txt). Чанк не равен отдельной сказке без разметки по "
            "заголовкам. Язык текста чанка — поле content_lang (en/ru)."
        ),
        "en": (
            "One «work» = one unique source (Gutenberg book id or local .txt). "
            "A chunk is not one tale without heading-level segmentation. "
            "Chunk text language: content_lang (en/ru)."
        ),
    }


def _label(key: str, *, lang: Lang) -> str:
    if lang == "en":
        return _LABELS_EN[key]
    return f"{_LABELS_RU[key]} ({_LABELS_EN[key]})"


def _heading(key: str, *, lang: Lang) -> str:
    if lang == "en":
        return f"-- {_LABELS_EN[key]} --"
    return f"-- {_LABELS_RU[key]} ({_LABELS_EN[key]}) --"


def build_report() -> dict[str, Any]:
    """Scan Chroma metadatas and return a structured report dict."""
    collection = get_collection(reset=False)
    n_docs = collection.count()
    if n_docs == 0:
        notes = _report_notes_empty()
        empty_summary = {
            "chunks_by_language": {},
            "top_countries": [],
            "top_authors": [],
            "top_hero_tokens": [],
        }
        return {
            "total_chunks": 0,
            "unique_works": 0,
            "by_domain": {},
            "by_country": {},
            "by_author": {},
            "by_content_lang": {},
            "works": [],
            "hero_mentions_top": [],
            "summary": empty_summary,
            "notes": notes,
            "note": notes["en"],
        }

    batch = collection.get(
        include=["metadatas"],
        limit=max(n_docs, 1) + 10,
    )
    metas_raw = batch.get("metadatas") or []

    by_domain: Counter[str] = Counter()
    by_country: Counter[str] = Counter()
    by_author: Counter[str] = Counter()
    by_content_lang: Counter[str] = Counter()
    chunks_per_source: Counter[str] = Counter()
    work_meta: dict[str, dict[str, str]] = {}
    hero_tokens: Counter[str] = Counter()

    for m in metas_raw:
        if not m:
            continue
        src = _norm(m.get("source"))
        dom = _norm(m.get("domain")) or "unknown"
        ctry = _norm(m.get("country")) or "unknown"
        auth = _norm(m.get("author")) or "unknown"
        clang = _norm(m.get("content_lang")) or "unknown"
        by_domain[dom] += 1
        by_country[ctry] += 1
        by_author[auth] += 1
        by_content_lang[clang] += 1
        if src:
            chunks_per_source[src] += 1
            if src not in work_meta:
                hen = _norm(m.get("heroes_en")) or _norm(m.get("heroes"))
                hru = _norm(m.get("heroes_ru"))
                work_meta[src] = {
                    "source": src,
                    "domain": dom,
                    "country": ctry,
                    "author": auth,
                    "work_note": _norm(m.get("work_note"))[:200],
                    "heroes_hint_en": hen[:300],
                    "heroes_hint_ru": hru[:300],
                    "content_lang": clang,
                }

        _add_hero_tokens(hero_tokens, m)

    works = sorted(work_meta.values(), key=lambda w: w["source"])
    hero_list = hero_tokens.most_common(30)
    notes = _report_notes_full()
    by_c = dict(sorted(by_country.items(), key=lambda x: -x[1]))
    by_a = dict(sorted(by_author.items(), key=lambda x: -x[1]))
    by_l = dict(sorted(by_content_lang.items(), key=lambda x: -x[1]))
    summary = {
        "chunks_by_language": by_l,
        "top_countries": list(by_c.items())[:5],
        "top_authors": list(by_a.items())[:5],
        "top_hero_tokens": hero_list[:5],
    }
    return {
        "total_chunks": n_docs,
        "unique_works": len(chunks_per_source),
        "by_domain": dict(sorted(by_domain.items(), key=lambda x: -x[1])),
        "by_country": by_c,
        "by_author": by_a,
        "by_content_lang": by_l,
        "chunks_per_work": dict(
            sorted(chunks_per_source.items(), key=lambda x: -x[1]),
        ),
        "works": works,
        "hero_mentions_top": hero_list,
        "summary": summary,
        "notes": notes,
        "note": notes["en"],
    }


def _add_hero_tokens(store: Counter[str], m: dict[str, Any]) -> None:
    """Count tokens from heroes_en, heroes_ru, legacy heroes (each once)."""
    seen_text: set[str] = set()
    for key in ("heroes_en", "heroes_ru", "heroes"):
        s = _norm(m.get(key))
        if not s or s in seen_text:
            continue
        seen_text.add(s)
        parts = [p.strip() for p in _HERO_SPLIT.split(s) if p.strip()]
        if len(parts) > 1:
            for tok in parts:
                if len(tok) >= 2:
                    store[tok.lower()] += 1
        elif len(parts) == 1 and len(parts[0]) <= 48:
            store[parts[0].lower()] += 1


def _print_summary(report: dict[str, Any], *, lang: Lang) -> None:
    summ = report.get("summary") or {}
    print(_heading("summary", lang=lang))
    if lang == "en":
        print(
            f"  {_LABELS_EN['total_chunks']}: {report['total_chunks']}; "
            f"{_LABELS_EN['unique_works']}: {report['unique_works']}"
        )
    else:
        print(
            f"  {_label('total_chunks', lang=lang)}: {report['total_chunks']}; "
            f"{_label('unique_works', lang=lang)}: {report['unique_works']}"
        )
    langs = summ.get("chunks_by_language") or {}
    if lang == "en":
        print(f"  {_LABELS_EN['by_content_lang']}: {langs}")
    else:
        print(f"  {_label('by_content_lang', lang=lang)}: {langs}")
    tc = summ.get("top_countries") or []
    ta = summ.get("top_authors") or []
    th = summ.get("top_hero_tokens") or []
    if lang == "en":
        print(f"  Top countries: {tc}")
        print(f"  Top authors: {ta}")
        print(f"  Top hero tokens: {th}")
    else:
        print(f"  Чаще всего по странам (top countries): {tc}")
        print(f"  Чаще всего по авторам (top authors): {ta}")
        print(f"  Чаще всего в подсказках героев (top hero tokens): {th}")
    print()


def _print_text(
    report: dict[str, Any],
    lang: Lang,
    *,
    show_chunks_per_work: bool = False,
) -> None:
    notes = report.get("notes") or {}
    nr = notes.get("ru", "")
    ne = notes.get("en", report.get("note", ""))

    if lang == "en":
        print(f"=== {_LABELS_EN['title']} ===\n")
    else:
        print(f"=== {_label('title', lang=lang)} ===\n")

    _print_summary(report, lang=lang)

    hkey = "by_domain"
    print()
    print(_heading(hkey, lang=lang))
    for k, v in report.get("by_domain", {}).items():
        print(f"  {k}: {v}")

    hkey = "by_country"
    print()
    print(_heading(hkey, lang=lang))
    for k, v in report.get("by_country", {}).items():
        print(f"  {k}: {v}")

    hkey = "by_author"
    print()
    print(_heading(hkey, lang=lang))
    for k, v in report.get("by_author", {}).items():
        print(f"  {k}: {v}")

    hkey = "by_content_lang"
    print()
    print(_heading(hkey, lang=lang))
    for k, v in report.get("by_content_lang", {}).items():
        print(f"  {k}: {v}")

    if show_chunks_per_work:
        hkey = "chunks_per_work"
        print()
        print(_heading(hkey, lang=lang))
        for k, v in report.get("chunks_per_work", {}).items():
            print(f"  {k}: {v}")

    hkey = "works"
    print()
    print(_heading(hkey, lang=lang))
    for w in report.get("works", []):
        clang = w.get("content_lang", "")
        extra = f" | lang={clang}" if clang else ""
        print(
            f"  {w['source']} | {w['domain']} | {w['country']} | "
            f"{w['author']}{extra}"
        )
        hru = (w.get("heroes_hint_ru") or "")[:200]
        hen = (w.get("heroes_hint_en") or "")[:200]
        if not hru and not hen:
            continue
        if lang == "en":
            lab = _LABELS_EN["heroes_col"]
            if hen:
                print(f"    {lab} (EN): {hen}")
            if hru:
                print(f"    {lab} (RU): {hru}")
        else:
            lab = _label("heroes_col", lang=lang)
            if hru:
                print(f"    {lab} (RU): {hru}")
            if hen:
                print(f"    {lab} (EN): {hen}")

    hkey = "hero_hints"
    print()
    print(_heading(hkey, lang=lang))
    for token, cnt in report.get("hero_mentions_top", [])[:15]:
        print(f"  {token}: {cnt}")

    print()
    if lang == "en":
        print(f"{_LABELS_EN['note']}: {ne}")
    else:
        print(f"{_label('note', lang=lang)}: {nr}")


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass
    logging.basicConfig(level=logging.WARNING)
    p = argparse.ArgumentParser(
        description="RAG corpus statistics (default: Russian + English in parens).",
    )
    p.add_argument(
        "--json",
        action="store_true",
        help="Print machine-readable JSON (includes notes.ru and notes.en).",
    )
    p.add_argument(
        "--lang",
        choices=("ru", "en", "bi"),
        default="ru",
        help=(
            "Text output: ru — Russian with English in parentheses (default); "
            "en — English only; bi — same as ru."
        ),
    )
    p.add_argument(
        "--show-chunks-per-work",
        action="store_true",
        help=(
            "Include «Chunks per work» / «Чанков на произведение» "
            "(hidden by default)."
        ),
    )
    args = p.parse_args()
    rep = build_report()
    lang: Lang = "ru" if args.lang == "bi" else args.lang
    if args.json:
        print(json.dumps(rep, ensure_ascii=False, indent=2))
    else:
        _print_text(
            rep,
            lang,
            show_chunks_per_work=args.show_chunks_per_work,
        )


if __name__ == "__main__":
    main()
