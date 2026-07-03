"""Kokoro neural TTS engine — high-quality offline speech via ONNX.

Model files (~300 MB) are auto-downloaded on first use to:
  ~/.local/share/text2speech/models/
"""

from __future__ import annotations

import shutil
import ssl
import subprocess
import tempfile
import urllib.request
from pathlib import Path

import numpy as np
import soundfile as sf

from text2speech.tts_base import TTSEngineBase, Voice

# Model file download URLs (v1.0 release)
_MODEL_URL = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.onnx"
_VOICES_URL = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin"

_MODELS_DIR = Path.home() / ".local" / "share" / "text2speech" / "models"
_MODEL_PATH = _MODELS_DIR / "kokoro-v1.0.onnx"
_VOICES_PATH = _MODELS_DIR / "voices-v1.0.bin"

# All available voices with metadata
# Source: https://huggingface.co/hexgrad/Kokoro-82M/blob/main/VOICES.md
KOKORO_VOICES: list[Voice] = [
    # American English — Female
    Voice("af_heart",   "Heart",   ["en-us"], "Female"),
    Voice("af_bella",   "Bella",   ["en-us"], "Female"),
    Voice("af_sarah",   "Sarah",   ["en-us"], "Female"),
    Voice("af_nicole",  "Nicole",  ["en-us"], "Female"),
    Voice("af_sky",     "Sky",     ["en-us"], "Female"),
    Voice("af_alloy",   "Alloy",   ["en-us"], "Female"),
    Voice("af_aoede",   "Aoede",   ["en-us"], "Female"),
    Voice("af_jessica", "Jessica", ["en-us"], "Female"),
    Voice("af_kore",    "Kore",    ["en-us"], "Female"),
    Voice("af_nova",    "Nova",    ["en-us"], "Female"),
    Voice("af_river",   "River",   ["en-us"], "Female"),
    # American English — Male
    Voice("am_adam",    "Adam",    ["en-us"], "Male"),
    Voice("am_michael", "Michael", ["en-us"], "Male"),
    Voice("am_echo",    "Echo",    ["en-us"], "Male"),
    Voice("am_eric",    "Eric",    ["en-us"], "Male"),
    Voice("am_fenrir",  "Fenrir",  ["en-us"], "Male"),
    Voice("am_liam",    "Liam",    ["en-us"], "Male"),
    Voice("am_onyx",    "Onyx",    ["en-us"], "Male"),
    Voice("am_puck",    "Puck",    ["en-us"], "Male"),
    # British English — Female
    Voice("bf_emma",    "Emma",    ["en-gb"], "Female"),
    Voice("bf_alice",   "Alice",   ["en-gb"], "Female"),
    Voice("bf_isabella","Isabella",["en-gb"], "Female"),
    Voice("bf_lily",    "Lily",    ["en-gb"], "Female"),
    # British English — Male
    Voice("bm_george",  "George",  ["en-gb"], "Male"),
    Voice("bm_lewis",   "Lewis",   ["en-gb"], "Male"),
    Voice("bm_daniel",  "Daniel",  ["en-gb"], "Male"),
    Voice("bm_fable",   "Fable",   ["en-gb"], "Male"),
    # Japanese
    Voice("jf_alpha",   "Alpha",   ["ja"], "Female"),
    Voice("jf_gongitsune", "Gongitsune", ["ja"], "Female"),
    Voice("jf_nezumi",  "Nezumi",  ["ja"], "Female"),
    Voice("jm_kumo",    "Kumo",    ["ja"], "Male"),
    # Mandarin Chinese
    Voice("zf_xiaobei", "Xiaobei", ["cmn"], "Female"),
    Voice("zm_yunxi",   "Yunxi",   ["cmn"], "Male"),
    # Spanish
    Voice("ef_dora",    "Dora",    ["es"], "Female"),
    Voice("em_alex",    "Alex",    ["es"], "Male"),
    Voice("em_santa",   "Santa",   ["es"], "Male"),
    # French
    Voice("ff_siwis",   "Siwis",   ["fr-fr"], "Female"),
    # Hindi
    Voice("hf_alpha",   "Alpha",   ["hi"], "Female"),
    Voice("hm_omega",   "Omega",   ["hi"], "Male"),
    # Italian
    Voice("if_sara",    "Sara",    ["it"], "Female"),
    Voice("im_nicola",  "Nicola",  ["it"], "Male"),
    # Brazilian Portuguese
    Voice("pf_dora",    "Dora",    ["pt-br"], "Female"),
    Voice("pm_alex",    "Alex",    ["pt-br"], "Male"),
    Voice("pm_santa",   "Santa",   ["pt-br"], "Male"),
]

_DEFAULT_VOICE = "af_heart"
_SAMPLE_RATE = 24_000


def _make_ssl_context(verify: bool = True) -> ssl.SSLContext:
    if verify:
        ctx = ssl.create_default_context()
        # Try loading the system CA bundle (handles corporate proxies on most distros)
        try:
            import certifi  # type: ignore[import]
            ctx.load_verify_locations(certifi.where())
        except ImportError:
            pass
        return ctx
    # Disable verification — fallback for corporate SSL inspection
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


def _download_with_progress(url: str, dest: Path) -> None:
    """Download a file with progress, falling back to unverified SSL if needed."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(".tmp")

    def _fetch(ctx: ssl.SSLContext) -> None:
        req = urllib.request.Request(url, headers={"User-Agent": "text2speech/1.0"})
        with urllib.request.urlopen(req, context=ctx) as response:
            total = int(response.headers.get("Content-Length", 0))
            downloaded = 0
            chunk_size = 1024 * 256  # 256 KB
            with open(tmp, "wb") as f:
                while True:
                    chunk = response.read(chunk_size)
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total:
                        pct = downloaded * 100 // total
                        print(f"\r  Downloading {dest.name} ... {pct}%", end="", flush=True)

    try:
        print(f"  Downloading {dest.name} ...", end="", flush=True)
        try:
            _fetch(_make_ssl_context(verify=True))
        except ssl.SSLError:
            print(f"\r  SSL verification failed — retrying without cert check ...", flush=True)
            tmp.unlink(missing_ok=True)
            _fetch(_make_ssl_context(verify=False))
        tmp.rename(dest)
        print(f"\r  Downloaded  {dest.name} ✓           ")
    except Exception:
        tmp.unlink(missing_ok=True)
        raise


def ensure_models(progress: bool = True) -> tuple[Path, Path]:
    """Return (model_path, voices_path), downloading if necessary."""
    if not _MODEL_PATH.exists():
        if progress:
            print("Kokoro model files not found — downloading (~300 MB total)...")
        _download_with_progress(_MODEL_URL, _MODEL_PATH)
    if not _VOICES_PATH.exists():
        _download_with_progress(_VOICES_URL, _VOICES_PATH)
    return _MODEL_PATH, _VOICES_PATH


def models_available() -> bool:
    return _MODEL_PATH.exists() and _VOICES_PATH.exists()


def _play_wav(path: Path) -> None:
    """Play a WAV file using the best available Linux audio player."""
    for player in ("aplay", "paplay", "ffplay"):
        if shutil.which(player):
            extra = ["-nodisp", "-autoexit", "-loglevel", "quiet"] if player == "ffplay" else []
            subprocess.run([player, *extra, str(path)], check=True)
            return
    raise RuntimeError(
        "No audio player found. Install one of: aplay (alsa-utils), paplay (pulseaudio), ffplay (ffmpeg)"
    )


class KokoroEngine(TTSEngineBase):
    """
    High-quality neural TTS via kokoro-onnx.

    Pure Python / ONNX inference — no system TTS binary required for synthesis.
    Model files are auto-downloaded on first use (~300 MB to ~/.local/share/text2speech/models/).
    """

    def __init__(
        self,
        model_path: Path | None = None,
        voices_path: Path | None = None,
        voice: str = _DEFAULT_VOICE,
        speed: float = 1.0,
        lang: str = "en-us",
    ) -> None:
        self._model_path = model_path
        self._voices_path = voices_path
        self._voice = voice
        self._speed = speed
        self._lang = lang
        self._kokoro = None   # lazy init — triggers download on first use
        self._g2p = None      # lazy init — misaki grapheme-to-phoneme

    def _get_g2p(self):
        """Return a misaki G2P callable, or None if misaki is not installed."""
        if self._g2p is None:
            try:
                from misaki import en  # type: ignore[import]
                self._g2p = en.G2P(trf=False, british=False)
            except Exception:
                self._g2p = False  # mark as unavailable so we don't retry
        return self._g2p if self._g2p is not False else None

    def _phonemize(self, text: str) -> str:
        """Convert text to phonemes via misaki; return original text if unavailable."""
        g2p = self._get_g2p()
        if g2p is None:
            return text
        try:
            phonemes, _ = g2p(text)
            return phonemes
        except Exception:
            return text

    def _get_kokoro(self):
        if self._kokoro is None:
            try:
                from kokoro_onnx import Kokoro  # type: ignore[import]
            except ImportError:
                raise RuntimeError(
                    "kokoro-onnx is not installed.\n"
                    "Install it with:  uv pip install --default-index https://pypi.org/simple kokoro-onnx"
                )
            mp, vp = ensure_models()
            self._kokoro = Kokoro(str(self._model_path or mp), str(self._voices_path or vp))
        return self._kokoro

    # ── TTSEngineBase interface ──────────────────────────────────────────────

    def list_voices(self) -> list[Voice]:
        return list(KOKORO_VOICES)

    def set_voice(self, voice_id: str) -> None:
        self._voice = voice_id

    def set_rate(self, rate: int) -> None:
        # Map words-per-minute to Kokoro speed multiplier.
        # 175 wpm ≈ speed 1.0, scale linearly.
        self._speed = round(rate / 175.0, 2)
        self._speed = max(0.5, min(2.0, self._speed))

    def set_volume(self, volume: float) -> None:
        # Kokoro has no native volume control; handled at playback.
        self._volume = max(0.0, min(1.0, volume))

    def _synthesize(self, text: str) -> tuple:
        """Phonemize then synthesize, returning (samples, sample_rate)."""
        g2p = self._get_g2p()
        if g2p is not None:
            try:
                phonemes, _ = g2p(text)
                return self._get_kokoro().create(
                    phonemes,
                    voice=self._voice,
                    speed=self._speed,
                    lang=self._lang,
                    is_phonemes=True,
                )
            except Exception:
                pass
        # fallback: let Kokoro handle the raw text with its built-in phonemizer
        return self._get_kokoro().create(
            text,
            voice=self._voice,
            speed=self._speed,
            lang=self._lang,
        )

    def speak(self, text: str) -> None:
        samples, sr = self._synthesize(text)
        vol = getattr(self, "_volume", 1.0)
        if vol != 1.0:
            samples = (samples * vol).astype(np.float32)

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp_path = Path(tmp.name)
        try:
            sf.write(str(tmp_path), samples, sr)
            _play_wav(tmp_path)
        finally:
            tmp_path.unlink(missing_ok=True)

    def save_to_file(self, text: str, output_path: Path) -> None:
        samples, sr = self._synthesize(text)
        vol = getattr(self, "_volume", 1.0)
        if vol != 1.0:
            samples = (samples * vol).astype(np.float32)
        sf.write(str(output_path), samples, sr)

    def get_properties(self) -> dict:
        return {
            "voice": self._voice,
            "speed": self._speed,
            "lang": self._lang,
            "volume": getattr(self, "_volume", 1.0),
            "sample_rate": _SAMPLE_RATE,
        }
