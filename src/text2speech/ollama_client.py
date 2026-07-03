"""Ollama client helpers for model listing and text processing."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Generator

import ollama
from rich.console import Console

console = Console()

_SPEECH_PREP_SYSTEM = """\
You are a text preparation assistant for text-to-speech conversion.
Your job is to clean and reformat text so it sounds natural when spoken aloud.

Rules:
- Expand abbreviations (e.g. "Dr." → "Doctor", "e.g." → "for example")
- Spell out numbers and symbols (e.g. "$5" → "5 dollars", "50%" → "50 percent")
- Remove markdown formatting, URLs, and code blocks — replace with plain descriptions
- Break long run-on sentences into shorter, natural-sounding ones
- Preserve the original meaning exactly — do NOT summarize or add content
- Return ONLY the processed text, no explanations or commentary
"""

_SUMMARIZE_SYSTEM = """\
You are a summarization assistant preparing content for text-to-speech playback.
Create a clear, concise spoken summary of the provided text.
Write in natural spoken language — short sentences, no lists or bullet points.
Return ONLY the summary, no preamble.
"""


@dataclass
class ModelInfo:
    name: str
    size_gb: float
    family: str
    parameter_count: str

    def display(self) -> str:
        return f"{self.name}  ({self.parameter_count}, {self.size_gb:.1f} GB, {self.family})"


def list_models() -> list[ModelInfo]:
    """Fetch all locally available Ollama models."""
    try:
        response = ollama.list()
        models = []
        for m in response.models:
            size_bytes = getattr(m, "size", 0) or 0
            details = getattr(m, "details", None)
            family = getattr(details, "family", "unknown") if details else "unknown"
            param_size = getattr(details, "parameter_size", "?") if details else "?"
            models.append(
                ModelInfo(
                    name=m.model,
                    size_gb=size_bytes / 1e9,
                    family=family or "unknown",
                    parameter_count=param_size or "?",
                )
            )
        return models
    except Exception as exc:
        raise RuntimeError(
            f"Cannot connect to Ollama. Is it running? (ollama serve)\n{exc}"
        ) from exc


def prepare_for_speech(text: str, model: str) -> str:
    """Use an Ollama model to clean up text for natural TTS output."""
    try:
        response = ollama.chat(
            model=model,
            messages=[
                {"role": "system", "content": _SPEECH_PREP_SYSTEM},
                {"role": "user", "content": text},
            ],
        )
        return response.message.content.strip()
    except Exception as exc:
        raise RuntimeError(f"Ollama processing failed: {exc}") from exc


def summarize_for_speech(text: str, model: str) -> str:
    """Use an Ollama model to summarize text for TTS playback."""
    try:
        response = ollama.chat(
            model=model,
            messages=[
                {"role": "system", "content": _SUMMARIZE_SYSTEM},
                {"role": "user", "content": text},
            ],
        )
        return response.message.content.strip()
    except Exception as exc:
        raise RuntimeError(f"Ollama summarization failed: {exc}") from exc


def stream_generate(prompt: str, model: str, system: str = "") -> Generator[str, None, None]:
    """Stream text generation from an Ollama model, yielding token chunks."""
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    try:
        stream = ollama.chat(model=model, messages=messages, stream=True)
        for chunk in stream:
            token = chunk.message.content
            if token:
                yield token
    except Exception as exc:
        raise RuntimeError(f"Ollama streaming failed: {exc}") from exc


def chat_turn(
    messages: list[dict],
    model: str,
) -> str:
    """Send a full conversation history and return the assistant reply."""
    try:
        response = ollama.chat(model=model, messages=messages)
        return response.message.content.strip()
    except Exception as exc:
        raise RuntimeError(f"Ollama chat failed: {exc}") from exc
