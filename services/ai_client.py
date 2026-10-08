"""Shared provider client defaults for bounded AI requests."""
from __future__ import annotations

import os

AI_REQUEST_TIMEOUT_SECONDS = 90.0
LOW_BANDWIDTH_AI_TIMEOUT_SECONDS = 300.0
AI_MAX_RETRIES = 1
LOW_BANDWIDTH_MAX_TOKENS = 256
GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"

# Backward-compatible names used by existing Groq client tests and callers.
GROQ_REQUEST_TIMEOUT_SECONDS = AI_REQUEST_TIMEOUT_SECONDS
GROQ_MAX_RETRIES = AI_MAX_RETRIES


def create_groq_client(api_key: str | None = None):
    from groq import Groq

    key = (
        api_key
        or os.environ.get("JARVIS_GROQ_API_KEY")
        or os.environ.get("GROQ_API_KEY")
        or ""
    ).strip()
    if not key:
        raise RuntimeError("Groq API anahtarı ayarlanmamış.")
    return Groq(
        api_key=key,
        timeout=AI_REQUEST_TIMEOUT_SECONDS,
        max_retries=AI_MAX_RETRIES,
    )


def create_gemini_client(api_key: str | None = None):
    """Create an OpenAI-compatible client for Google's Gemini API."""
    key = (
        api_key
        or os.environ.get("JARVIS_GEMINI_API_KEY")
        or os.environ.get("GEMINI_API_KEY")
        or ""
    ).strip()
    if not key:
        raise RuntimeError("Gemini API anahtarı ayarlanmamış.")
    from openai import OpenAI

    return OpenAI(
        api_key=key,
        base_url=GEMINI_BASE_URL,
        timeout=AI_REQUEST_TIMEOUT_SECONDS,
        max_retries=AI_MAX_RETRIES,
    )


def gemini_grounded_search(
    prompt: str,
    model: str,
    api_key: str | None = None,
    cancel_event=None,
    response_callback=None,
    timeout: float = AI_REQUEST_TIMEOUT_SECONDS,
) -> str:
    """Answer through Gemini Interactions API with Google Search grounding."""
    key = (
        api_key
        or os.environ.get("JARVIS_GEMINI_API_KEY")
        or os.environ.get("GEMINI_API_KEY")
        or ""
    ).strip()
    if not key:
        raise RuntimeError("Web araması için JARVIS_GEMINI_API_KEY ayarlanmamış.")

    import requests

    response = None
    try:
        response = requests.post(
            "https://generativelanguage.googleapis.com/v1beta/interactions",
            headers={"x-goog-api-key": key},
            json={
                "model": model,
                "input": prompt,
                "tools": [{"type": "google_search"}],
            },
            timeout=timeout,
            stream=True,
        )
        if response_callback is not None:
            response_callback(response)
        if cancel_event is not None and cancel_event.is_set():
            return ""
        response.raise_for_status()
        payload = response.json()
    finally:
        if response_callback is not None and response is not None:
            response_callback(None)
        if response is not None:
            response.close()
    interaction = payload.get("interaction", payload)
    answer = interaction.get("output_text", "")
    citations = []

    for step in interaction.get("steps", []):
        if step.get("type") != "model_output":
            continue
        for block in step.get("content", []):
            if block.get("type") != "text":
                continue
            if not answer:
                answer += block.get("text", "")
            for annotation in block.get("annotations", []):
                if annotation.get("type") != "url_citation":
                    continue
                url = annotation.get("url", "").strip()
                title = annotation.get("title", "").strip() or url
                if url and url not in {item[1] for item in citations}:
                    citations.append((title, url))

    if not answer:
        raise RuntimeError("Gemini web araması metin yanıtı döndürmedi.")
    if citations:
        answer += "\n\nKaynaklar:\n" + "\n".join(
            f"• {title}: {url}" for title, url in citations
        )
    return answer
