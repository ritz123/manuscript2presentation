"""pyttsx3-backed TTS engine (uses espeak-ng on Linux)."""

from __future__ import annotations

import threading
from pathlib import Path

import pyttsx3

from text2speech.tts_base import TTSEngineBase, Voice


class Pyttsx3Engine(TTSEngineBase):
    """Offline TTS via pyttsx3 / espeak-ng — zero internet, 100+ languages."""

    def __init__(self) -> None:
        self._engine: pyttsx3.Engine | None = None
        self._lock = threading.Lock()

    def _get_engine(self) -> pyttsx3.Engine:
        if self._engine is None:
            self._engine = pyttsx3.init()
        return self._engine

    # ── TTSEngineBase interface ──────────────────────────────────────────────

    def list_voices(self) -> list[Voice]:
        voices = []
        for v in self._get_engine().getProperty("voices"):
            langs = getattr(v, "languages", []) or []
            langs = [lang.decode() if isinstance(lang, bytes) else lang for lang in langs]
            voices.append(
                Voice(
                    id=v.id,
                    name=v.name,
                    languages=langs,
                    gender=getattr(v, "gender", "unknown") or "unknown",
                )
            )
        return voices

    def set_voice(self, voice_id: str) -> None:
        self._get_engine().setProperty("voice", voice_id)

    def set_rate(self, rate: int) -> None:
        self._get_engine().setProperty("rate", rate)

    def set_volume(self, volume: float) -> None:
        self._get_engine().setProperty("volume", max(0.0, min(1.0, volume)))

    def speak(self, text: str) -> None:
        with self._lock:
            engine = self._get_engine()
            engine.say(text)
            engine.runAndWait()

    def save_to_file(self, text: str, output_path: Path) -> None:
        with self._lock:
            engine = self._get_engine()
            engine.save_to_file(text, str(output_path))
            engine.runAndWait()

    # ── extras ──────────────────────────────────────────────────────────────

    def get_properties(self) -> dict:
        engine = self._get_engine()
        return {
            "rate": engine.getProperty("rate"),
            "volume": engine.getProperty("volume"),
            "voice": engine.getProperty("voice"),
        }

    def stop(self) -> None:
        if self._engine is not None:
            try:
                self._engine.stop()
            except Exception:
                pass

    def __del__(self) -> None:
        self.stop()


# Legacy alias so existing imports keep working
TTSEngine = Pyttsx3Engine
