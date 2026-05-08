#!/usr/bin/env python3
"""
Proposed replacement for /root/.hermes/scripts/agent-interview-collector.py.

This file is stored in the writable workspace because the real target path is
read-only in the current session. It implements the requested behavior:
- 8 sources
- compact structured JSON
- writes to /person/agent-interview-archive/.last_collected.json and stdout
- marks fetch_failed sources for Agent-side web_extract follow-up
"""

import json
import re
import urllib.request
from datetime import date
from pathlib import Path

OUTPUT_PATH = Path("/person/agent-interview-archive/.last_collected.json")
MAX_SOURCE_CHARS = 800

SOURCES = [
    {
        "name": "coprep",
        "url": "https://www.coprep.ai/blog/top-agentic-ai-interview-questions-for-2026-beyond-the-models",
        "topic": "Agentic AI fundamentals, planning, tool use",
    },
    {
        "name": "datacamp_rag",
        "url": "https://www.datacamp.com/blog/rag-interview-questions",
        "topic": "RAG architecture, retrieval quality, chunking, evaluation",
    },
    {
        "name": "novelvista",
        "url": "https://www.novelvista.com/blogs/ai-and-ml/agentic-ai-interview-questions-answers",
        "topic": "Agent architecture, memory, safety, orchestration",
    },
    {
        "name": "galileo_eval",
        "url": "https://galileo.ai/blog/agent-evaluation-framework-metrics-rubrics-benchmarks",
        "topic": "Agent evaluation metrics, rubrics, benchmarks",
    },
    {
        "name": "thinking_co",
        "url": "https://thinking.inc/en/blue-ocean/agentic/ai-agent-evaluation-production/",
        "topic": "Production agent evaluation, failure analysis, observability",
    },
    {
        "name": "callsphere",
        "url": "https://callsphere.ai/blog/agentic-ai-multi-agent-interview-questions-2026",
        "topic": "Multi-agent design, coordination, routing, failure handling",
    },
    {
        "name": "anthropic",
        "url": "https://www.anthropic.com/research/building-effective-agents",
        "topic": "Effective agent design patterns and production practices",
    },
    {
        "name": "langchain_multi_agent",
        "url": "https://docs.langchain.com/oss/python/langchain/multi-agent/index",
        "topic": "LangChain multi-agent patterns, handoffs, supervisors",
    },
]


def fetch_url(url: str, timeout: int = 15) -> str | None:
    try:
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
                "Accept": "text/html,application/xhtml+xml",
                "Accept-Language": "en-US,en;q=0.9,zh-CN;q=0.8",
            },
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except Exception:
        return None


def clean_text(html: str) -> str:
    html = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r"<style[^>]*>.*?</style>", "", html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r"</?(?:div|p|br|h[1-6]|li|tr|section|article|blockquote|pre|code)[^>]*>", "\n", html, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", html)
    text = text.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">").replace("&nbsp;", " ")
    text = re.sub(r"&#(\d+);", lambda m: chr(int(m.group(1))), text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    text = re.sub(r"\n{2,}", "\n", text)
    return text.strip()


def extract_title(html: str) -> str:
    match = re.search(r"<title[^>]*>([^<]+)</title>", html, re.IGNORECASE)
    return match.group(1).strip() if match else ""


def split_sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?。！？])\s+|\n+", text)
    return [p.strip() for p in parts if len(p.strip()) >= 30]


def summarize_points(text: str, limit: int = 5) -> list[str]:
    points = []
    seen = set()
    for sentence in split_sentences(text):
        normalized = sentence.lower()
        if normalized in seen:
            continue
        seen.add(normalized)
        points.append(sentence[:140])
        if len(points) == limit:
            break
    while len(points) < limit:
        points.append("Content extraction was partial; agent should infer one interview angle from the source title/topic.")
    return points


def infer_question_topics(source: dict, text: str) -> list[str]:
    lowered = f"{source['topic']} {text}".lower()
    topics = []
    candidates = [
        ("rag", "RAG pipeline design and retrieval quality"),
        ("multi-agent", "Multi-agent coordination and routing"),
        ("tool", "Tool use reliability and function invocation"),
        ("evalu", "Evaluation metrics, rubrics, and offline or online testing"),
        ("safety", "Safety guardrails and failure containment"),
        ("memory", "Memory strategy and context management"),
        ("plan", "Planning and task decomposition"),
        ("observ", "Observability, tracing, and debugging"),
    ]
    for keyword, label in candidates:
        if keyword in lowered and label not in topics:
            topics.append(label)
    if not topics:
        topics = [
            "System design tradeoffs",
            "Production failure handling",
            "Interview scenario adaptation",
        ]
    return topics[:5]


def compact_source_record(record: dict) -> dict:
    raw = json.dumps(record, ensure_ascii=False)
    if len(raw) <= MAX_SOURCE_CHARS:
        return record

    compact = dict(record)
    compact["key_points"] = [point[:100] for point in compact.get("key_points", [])][:5]
    compact["question_topics"] = [topic[:70] for topic in compact.get("question_topics", [])][:5]
    compact["title"] = compact.get("title", "")[:120]
    return compact


def build_source_record(source: dict) -> dict:
    html = fetch_url(source["url"])
    if not html:
        return {
            "name": source["name"],
            "url": source["url"],
            "title": "",
            "topic": source["topic"],
            "key_points": [],
            "question_topics": [],
            "fetch_failed": True,
            "note": "Fetch failed; Agent should use web_extract to补充该来源。",
        }

    title = extract_title(html)
    text = clean_text(html)
    record = {
        "name": source["name"],
        "url": source["url"],
        "title": title,
        "topic": source["topic"],
        "key_points": summarize_points(text, limit=5),
        "question_topics": infer_question_topics(source, text),
    }
    return compact_source_record(record)


def main() -> None:
    payload = {
        "date": date.today().isoformat(),
        "sources": [build_source_record(source) for source in SOURCES],
    }
    OUTPUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
