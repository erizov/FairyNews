"""Fairy-tale plot RAG for the «Нейро-сказочник» pipeline.

This package indexes **only** fairy-tale / folklore narrative texts. It does **not**
index political news (news are handled outside RAG, e.g. by the news agent).

Intended consumer: **Agent story generation** inside multi-agent orchestration:
news agent → story agent (uses this RAG + prompts) → audit agent → Q&A agent.

Volume planning: see ``VOLUME_ESTIMATES.md`` in this package.
"""
