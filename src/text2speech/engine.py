"""Engine factory — selects and configures a TTS backend."""

from __future__ import annotations

from enum import Enum

from text2speech.tts_base import TTSEngineBase


class EngineChoice(str, Enum):
    auto = "auto"
    kokoro = "kokoro"
    pyttsx3 = "pyttsx3"


def get_engine(choice: EngineChoice = EngineChoice.auto) -> TTSEngineBase:
    """
    Return a ready-to-use TTS engine.

    auto   → tries Kokoro first; falls back to pyttsx3 if kokoro-onnx is not installed
    kokoro → Kokoro neural TTS (requires `pip install kokoro-onnx`)
    pyttsx3→ pyttsx3 / espeak-ng
    """
    if choice == EngineChoice.pyttsx3:
        from text2speech.tts import Pyttsx3Engine
        return Pyttsx3Engine()

    if choice == EngineChoice.kokoro:
        from text2speech.tts_kokoro import KokoroEngine
        return KokoroEngine()

    # auto: prefer Kokoro if installed
    try:
        import kokoro_onnx  # noqa: F401
        from text2speech.tts_kokoro import KokoroEngine
        return KokoroEngine()
    except ImportError:
        from text2speech.tts import Pyttsx3Engine
        return Pyttsx3Engine()
