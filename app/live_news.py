"""Подбор свежих заголовков из RSS (английские и русские источники)."""

from __future__ import annotations

import logging
import re
import threading
import time
import xml.etree.ElementTree as ET
from typing import Any

import httpx

logger = logging.getLogger(__name__)

_LOCK = threading.Lock()
_CACHE: dict[str, Any] = {"ts": 0.0, "items": []}
_TTL_SEC = 900.0
# Медленный TLS / обрыв (WinError 10054 у BBC с части сетей) — запас и retry.
_TIMEOUT = 20.0
_RSS_RETRIES = 2

_USER_AGENT = (
    "FairyNews/1.0 (+student research; respectful RSS polling)"
)

# Сначала ленты, которые реже рвут соединение, чем BBC (10054 и т.п.).
_FEEDS_EN: tuple[tuple[str, str], ...] = (
    ("The Guardian (World)", "https://www.theguardian.com/world/rss"),
    ("NPR", "https://feeds.npr.org/1001/rss.xml"),
    ("BBC (UK/US wire)", "https://feeds.bbci.co.uk/news/world/rss.xml"),
)

_FEEDS_RU: tuple[tuple[str, str], ...] = (
    ("ТАСС", "https://tass.ru/rss/v2.xml"),
    # /world/index.xml отдаёт 404; общая лента — стабильный endpoint.
    ("РИА Новости", "https://ria.ru/export/rss2/index.xml"),
    ("Lenta.ru", "https://lenta.ru/rss/news"),
)


def _local(tag: str) -> str:
    if "}" in tag:
        return tag.rsplit("}", 1)[-1]
    return tag


def _strip_html(raw: str) -> str:
    t = re.sub(r"<[^>]+>", " ", raw)
    t = re.sub(r"\s+", " ", t)
    return t.strip()


def _longer_plain(a: str, b: str) -> str:
    """Берём более полный текст (RSS description vs content:encoded)."""
    aa = (a or "").strip()
    bb = (b or "").strip()
    if len(bb) > len(aa):
        return bb
    return aa


def _first_item_summary(channel: ET.Element) -> tuple[str, str, str, str]:
    """title, link, description, pub_date from first <item>."""
    title = ""
    link = ""
    desc = ""
    pub = ""
    for child in channel:
        tag = _local(child.tag)
        if tag == "item":
            for ic in child:
                tg = _local(ic.tag)
                txt = (ic.text or "").strip()
                if tg == "title" and txt:
                    title = txt
                elif tg == "link" and txt:
                    link = txt
                elif tg in ("description", "summary") and ic.text:
                    desc = _longer_plain(desc, _strip_html(ic.text))
                elif tg == "encoded" and ic.text:
                    # content:encoded (namespace → local name «encoded»)
                    desc = _longer_plain(desc, _strip_html(ic.text))
                elif tg == "pubDate" and txt:
                    pub = txt
            break
    return title, link, desc, pub


def _fetch_feed(client: httpx.Client, url: str) -> ET.Element | None:
    root: ET.Element | None = None
    for attempt in range(_RSS_RETRIES):
        try:
            r = client.get(url, follow_redirects=True)
            r.raise_for_status()
            root = ET.fromstring(r.content)
            break
        except Exception as exc:
            if attempt + 1 < _RSS_RETRIES:
                time.sleep(0.4)
                continue
            logger.warning("RSS fetch failed %s: %s", url, exc)
            return None
    if root is None:
        return None
    ch = root
    if _local(root.tag) == "rss":
        for c in root:
            if _local(c.tag) == "channel":
                ch = c
                break
    elif _local(root.tag) == "feed":  # Atom
        return root
    return ch


def _parse_rss_channel(
    channel: ET.Element,
    source_label: str,
    lang: str,
    slot: int,
) -> dict[str, Any] | None:
    tag0 = _local(channel.tag)
    if tag0 == "feed":
        title = ""
        link = ""
        summary = ""
        updated = ""
        pub = ""
        for child in channel:
            tg = _local(child.tag)
            if tg == "title" and (child.text or "").strip():
                title = (child.text or "").strip()
            elif tg == "link":
                href = child.attrib.get("href", "")
                if href:
                    link = href
            elif tg in ("subtitle", "summary") and child.text:
                summary = _strip_html(child.text)
            elif tg == "updated" and (child.text or "").strip():
                updated = (child.text or "").strip()
        for child in channel:
            if _local(child.tag) != "entry":
                continue
            etitle = ""
            elink = ""
            edesc = ""
            edate = ""
            for ic in child:
                tg = _local(ic.tag)
                if tg == "title" and (ic.text or "").strip():
                    etitle = (ic.text or "").strip()
                elif tg == "link":
                    h = ic.attrib.get("href", "")
                    if h:
                        elink = h
                elif tg == "summary" and ic.text:
                    edesc = _longer_plain(edesc, _strip_html(ic.text))
                elif tg == "content" and ic.text:
                    edesc = _longer_plain(edesc, _strip_html(ic.text))
                elif tg == "updated" and (ic.text or "").strip():
                    edate = (ic.text or "").strip()
            if etitle:
                title = etitle
                link = elink or link
                summary = edesc or summary
                pub = edate or updated
                break
        if not title:
            return None
    else:
        title, link, desc, pub = _first_item_summary(channel)
        summary = desc
    if not title:
        return None
    if not summary:
        summary = (link or "")[:400]
    nid = f"{lang}-{slot}"
    return {
        "id": nid,
        "title": title,
        "date": pub[:32] if pub else "",
        "summary": summary,
        "source": source_label,
        "lang": lang,
        "link": link,
    }


def _gather_sample() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    with httpx.Client(
        headers={"User-Agent": _USER_AGENT},
        timeout=_TIMEOUT,
    ) as client:
        for i, (label, url) in enumerate(_FEEDS_EN):
            ch = _fetch_feed(client, url)
            if ch is None:
                continue
            row = _parse_rss_channel(ch, label, "en", i)
            if row:
                out.append(row)
        for i, (label, url) in enumerate(_FEEDS_RU):
            ch = _fetch_feed(client, url)
            if ch is None:
                continue
            row = _parse_rss_channel(ch, label, "ru", i)
            if row:
                out.append(row)
    return out


def get_cached_news_items(*, force_refresh: bool = False) -> list[dict[str, Any]]:
    """До шести статей: три en и три ru, если RSS доступны."""
    global _CACHE
    now = time.monotonic()
    with _LOCK:
        age = now - float(_CACHE["ts"])
        if not force_refresh and _CACHE["items"] and age < _TTL_SEC:
            return list(_CACHE["items"])
        try:
            items = _gather_sample()
        except Exception as exc:
            logger.warning("live news gather error: %s", exc)
            items = []
        _CACHE = {"ts": now, "items": items}
        return list(items)


def get_item_by_id(news_id: str) -> dict[str, Any] | None:
    """Актуальный объект новости по id слота (en-0 … ru-2)."""
    for row in get_cached_news_items():
        if row.get("id") == news_id:
            return dict(row)
    return None


def offline_fallback_items() -> list[dict[str, Any]]:
    """Шесть слотов-заглушек: офлайн-режим или подстановка при сбое RSS."""
    return [
        {
            "id": "en-0",
            "title": "Wire: regional talks continue",
            "date": "",
            "summary": "Officials met to align schedules.\nTeams reviewed "
            "documents.\nNo final communique yet.",
            "source": "wire-en",
            "lang": "en",
            "link": "",
        },
        {
            "id": "en-1",
            "title": "Markets digest overnight moves",
            "date": "",
            "summary": "Indexes closed mixed.\nBond yields edged lower.\n"
            "Focus shifts to labor data.",
            "source": "wire-en",
            "lang": "en",
            "link": "",
        },
        {
            "id": "en-2",
            "title": "Weather service issues early advisory",
            "date": "",
            "summary": "Coastal winds may strengthen.\nTravelers asked to "
            "monitor alerts.\nUpdates hourly.",
            "source": "wire-en",
            "lang": "en",
            "link": "",
        },
        {
            "id": "ru-0",
            "title": "Сводка: обсуждение графика работ",
            "date": "",
            "summary": "Участники согласовали черновик.\nДокументы переданы "
            "на проверку.\nИтоги позже.",
            "source": "wire-ru",
            "lang": "ru",
            "link": "",
        },
        {
            "id": "ru-1",
            "title": "Рынки: итоги вечерней сессии",
            "date": "",
            "summary": "Индексы закрылись разнонаправленно.\nДоходности "
            "снизились.\nВнимание к отчётам.",
            "source": "wire-ru",
            "lang": "ru",
            "link": "",
        },
        {
            "id": "ru-2",
            "title": "Служба оповещений: про погоду",
            "date": "",
            "summary": "Порывы усилятся у побережья.\nСледите за сообщениями."
            "\nОбновления по часам.",
            "source": "wire-ru",
            "lang": "ru",
            "link": "",
        },
    ]
