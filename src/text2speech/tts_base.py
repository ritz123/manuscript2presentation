"""Abstract base class for TTS engines."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Voice:
    id: str
    name: str
    languages: list[str] = field(default_factory=list)
    gender: str = "unknown"

    def display_name(self) -> str:
        langs = ", ".join(self.languages) if self.languages else "unknown"
        return f"{self.name}  [{langs}]  ({self.gender})"


class TTSEngineBase(ABC):
    """Common interface for all TTS backends."""

    @abstractmethod
    def list_voices(self) -> list[Voice]:
        """Return all voices supported by this engine."""

    @abstractmethod
    def set_voice(self, voice_id: str) -> None:
        """Select a voice by its ID."""

    @abstractmethod
    def set_rate(self, rate: int) -> None:
        """Set speech rate (words per minute or engine-specific scale)."""

    @abstractmethod
    def set_volume(self, volume: float) -> None:
        """Set volume in range [0.0, 1.0]."""

    @abstractmethod
    def speak(self, text: str) -> None:
        """Speak text aloud, blocking until done."""

    @abstractmethod
    def save_to_file(self, text: str, output_path: Path) -> None:
        """Render speech to a WAV file without playing it."""

    def get_properties(self) -> dict:
        return {}
