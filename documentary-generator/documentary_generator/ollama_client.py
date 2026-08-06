from __future__ import annotations

import json
from typing import Any

import requests

from .models import DocumentaryPlan


PLAN_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "youtube_description": {"type": "string"},
        "scenes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "narration": {"type": "string"},
                    "visual_query": {"type": "string"},
                    "on_screen_text": {"type": "string"},
                },
                "required": ["narration", "visual_query", "on_screen_text"],
            },
        },
    },
    "required": ["title", "youtube_description", "scenes"],
}


def ollama_is_running(host: str, timeout: float = 2.0) -> bool:
    try:
        response = requests.get(f"{host.rstrip('/')}/api/tags", timeout=timeout)
        return response.ok
    except requests.RequestException:
        return False


def generate_plan(
    *,
    topic: str,
    source_notes: str,
    target_minutes: int,
    model: str,
    host: str,
) -> DocumentaryPlan:
    scene_count = min(36, max(4, target_minutes * 4))
    notes = source_notes.strip() or "No verified source notes were supplied. Avoid precise claims that cannot be supported."
    prompt = f"""
Create a factual YouTube documentary plan about: {topic}
Target duration: approximately {target_minutes} minute(s).
Target scene count: {scene_count}.

Verified source notes supplied by the creator:
---
{notes}
---

Rules:
- Use only the supplied notes for specific factual claims, dates, quotations, and statistics.
- When notes are incomplete, use cautious general wording rather than inventing facts.
- Begin with a strong hook, build a clear narrative, and end with a meaningful conclusion.
- Each scene needs 25 to 55 spoken words.
- visual_query must be a concise English stock-footage search phrase, not an image-generation prompt.
- on_screen_text must be brief, preferably under 8 words, and may be empty.
- Do not include markdown.
- Return only JSON matching this schema:
{json.dumps(PLAN_SCHEMA)}
""".strip()

    try:
        response = requests.post(
            f"{host.rstrip('/')}/api/chat",
            json={
                "model": model,
                "messages": [
                    {
                        "role": "system",
                        "content": "You are a careful documentary writer. Accuracy is more important than drama.",
                    },
                    {"role": "user", "content": prompt},
                ],
                "stream": False,
                "format": PLAN_SCHEMA,
                "options": {"temperature": 0.2},
            },
            timeout=600,
        )
        response.raise_for_status()
        content = response.json()["message"]["content"]
        return DocumentaryPlan.model_validate_json(content)
    except requests.RequestException as exc:
        raise RuntimeError(f"Ollama request failed: {exc}") from exc
    except (KeyError, ValueError) as exc:
        raise RuntimeError("Ollama returned an invalid documentary plan.") from exc
