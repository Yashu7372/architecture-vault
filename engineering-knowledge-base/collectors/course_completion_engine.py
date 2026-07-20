from __future__ import annotations

from dataclasses import dataclass
from typing import Any
import os

import requests

from collectors.course_learning_builder import build_course_study_guide


@dataclass(frozen=True)
class CompletionResult:
    content: str
    mode: str
    model: str | None = None
    error: str | None = None


@dataclass(frozen=True)
class CompletionConfig:
    base_url: str
    api_key: str
    model: str
    timeout_seconds: int
    max_tokens: int
    temperature: float
    strict: bool

    @classmethod
    def from_environment(cls) -> CompletionConfig | None:
        base_url = os.getenv("COURSE_LLM_BASE_URL", "").strip()
        model = os.getenv("COURSE_LLM_MODEL", "").strip()
        if not base_url or not model:
            return None
        return cls(
            base_url=base_url.rstrip("/"),
            api_key=os.getenv("COURSE_LLM_API_KEY", "").strip(),
            model=model,
            timeout_seconds=int(os.getenv("COURSE_LLM_TIMEOUT_SECONDS", "180")),
            max_tokens=int(os.getenv("COURSE_LLM_MAX_TOKENS", "6500")),
            temperature=float(os.getenv("COURSE_LLM_TEMPERATURE", "0.25")),
            strict=os.getenv("COURSE_LLM_STRICT", "false").lower() in {"1", "true", "yes"},
        )


def build_completion_prompt(
    *,
    lesson,
    previous_lesson,
    next_lesson,
    public_content: str,
    access_level: str,
    course_track: str,
) -> str:
    previous_text = (
        f"Day {previous_lesson.day}: {previous_lesson.title}"
        if previous_lesson
        else "No previous lesson; establish the required foundation."
    )
    next_text = (
        f"Day {next_lesson.day}: {next_lesson.title}"
        if next_lesson
        else "No next lesson; connect this topic to the completed platform."
    )
    public_excerpt = public_content.strip()
    if len(public_excerpt) > 14000:
        public_excerpt = public_excerpt[:14000] + "\n\n[Public excerpt truncated by the local pipeline.]"
    if not public_excerpt:
        public_excerpt = "No article body is publicly visible. Use only the curriculum title and expected output."

    return f"""You are writing an original, standalone distributed-systems lesson for an engineer.

Copyright and access rules:
- Do not guess, reconstruct, paraphrase, or imitate subscriber-only course text.
- Use only the public curriculum metadata and the public excerpt supplied below.
- Do not claim that your explanation is the missing paid article.
- Do not quote the source beyond short phrases that are necessary to identify the topic.
- Create a fresh technical explanation from general engineering knowledge.

Course track: {course_track}
Current lesson: Day {lesson.day}: {lesson.title}
Module: {lesson.module}
Week: {lesson.week}
Expected implementation output: {lesson.expected_output or 'Create a demonstrable implementation of the topic.'}
Previous lesson: {previous_text}
Next lesson: {next_text}
Public access classification: {access_level}

Publicly visible source material:
--- BEGIN PUBLIC SOURCE ---
{public_excerpt}
--- END PUBLIC SOURCE ---

Write a detailed Markdown lesson, normally 2,500-4,000 words when the topic warrants it. It must be useful even when the public source is only an introduction or architecture image. Use this exact high-level structure:

## Part 2 — Original Completed Lesson
### What You Will Learn
### Where This Fits in the Course
### Problem and Requirements
### First-Principles Explanation
### Architecture Breakdown
### Components and Responsibilities
### End-to-End Data Flow
### Data Model and Contracts
### Detailed Implementation Plan
### Technology-Specific Notes for {course_track}
### Concurrency, Ordering, and Consistency
### Failure Scenarios and Recovery
### Scaling and Performance
### Observability
### Security and Governance
### Design Alternatives and Trade-offs
### Hands-On Exercise
### Validation and Test Plan
### Mermaid Architecture Diagram
### Key Takeaways
### Questions to Check Your Understanding

Requirements:
- Explain every important term before using it deeply.
- Distinguish correctness guarantees from performance optimizations.
- Include concrete request/event examples, invariants, acknowledgement boundaries, retry behavior, idempotency, and backpressure where relevant.
- Provide implementation steps and pseudocode or small code/config examples when useful, but do not invent source-specific proprietary code.
- Connect the previous lesson to this one and explain what interface must remain stable for the next lesson.
- Include realistic production failure cases and the exact evidence an operator should inspect.
- The Mermaid diagram must be syntactically simple and directly related to this lesson.
- End with an explicit statement that the lesson is original explanatory material based on public curriculum signals and general engineering knowledge.
"""


def _chat_completions_url(base_url: str) -> str:
    if base_url.endswith("/chat/completions"):
        return base_url
    if base_url.endswith("/v1"):
        return f"{base_url}/chat/completions"
    return f"{base_url}/v1/chat/completions"


def _extract_content(payload: dict[str, Any]) -> str:
    choices = payload.get("choices") or []
    if not choices:
        raise ValueError("LLM response did not contain choices")
    message = choices[0].get("message") or {}
    content = message.get("content")
    if isinstance(content, str) and content.strip():
        return content.strip()
    if isinstance(content, list):
        text = "\n".join(
            part.get("text", "") for part in content if isinstance(part, dict) and part.get("type") == "text"
        ).strip()
        if text:
            return text
    raise ValueError("LLM response did not contain message content")


def complete_course_lesson(
    *,
    lesson,
    previous_lesson,
    next_lesson,
    public_content: str,
    access_level: str,
    course_track: str,
    session: requests.Session | None = None,
) -> CompletionResult:
    fallback = build_course_study_guide(
        lesson=lesson,
        previous_lesson=previous_lesson,
        next_lesson=next_lesson,
        public_content=public_content,
        access_level=access_level,
    ).replace("## Original Stitched Study Guide", "## Part 2 — Original Completed Lesson", 1)

    config = CompletionConfig.from_environment()
    if config is None:
        return CompletionResult(content=fallback, mode="deterministic-template")

    client = session or requests.Session()
    headers = {"Content-Type": "application/json"}
    if config.api_key:
        headers["Authorization"] = f"Bearer {config.api_key}"
    prompt = build_completion_prompt(
        lesson=lesson,
        previous_lesson=previous_lesson,
        next_lesson=next_lesson,
        public_content=public_content,
        access_level=access_level,
        course_track=course_track,
    )
    payload = {
        "model": config.model,
        "messages": [
            {
                "role": "system",
                "content": (
                    "Create original engineering education content. Respect access boundaries and never reconstruct "
                    "subscriber-only source material."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        "temperature": config.temperature,
        "max_tokens": config.max_tokens,
    }

    try:
        response = client.post(
            _chat_completions_url(config.base_url),
            headers=headers,
            json=payload,
            timeout=config.timeout_seconds,
        )
        response.raise_for_status()
        content = _extract_content(response.json())
        if not content.startswith("## Part 2"):
            content = f"## Part 2 — Original Completed Lesson\n\n{content}"
        return CompletionResult(content=content, mode="llm", model=config.model)
    except Exception as exc:
        if config.strict:
            raise
        return CompletionResult(
            content=fallback,
            mode="deterministic-fallback",
            model=config.model,
            error=str(exc),
        )
