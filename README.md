# text2speech

A fully **offline** text-to-speech CLI powered by:

- **[Ollama](https://ollama.ai)** — local LLM models for optional text preprocessing / summarization
- **[pyttsx3](https://pyttsx3.readthedocs.io)** — offline TTS using the system speech engine (`espeak-ng` on Linux)

---

## Requirements

| Requirement | Notes |
|---|---|
| Python ≥ 3.10 | |
| [uv](https://docs.astral.sh/uv/) | Fast Python package manager |
| [Ollama](https://ollama.ai) running locally | `ollama serve` |
| `espeak-ng` | System TTS engine on Linux |

Install `espeak-ng` if not already present:

```bash
# Debian / Ubuntu
sudo apt install espeak-ng

# Fedora / RHEL
sudo dnf install espeak-ng

# Arch
sudo pacman -S espeak-ng
```

---

## Installation

```bash
# Clone / enter the project directory
cd text2speech

# Install with uv (creates .venv and installs all deps)
uv sync

# Run directly
uv run t2s --help

# Or install into the uv-managed venv and use the script
uv pip install -e .
t2s --help
```

---

## Usage

### List locally available Ollama models

```bash
uv run t2s list-models
```

### List available TTS voices

```bash
uv run t2s list-voices
```

### Speak text directly

```bash
# Simple speech
uv run t2s speak "Hello, this is a text to speech demo."

# Adjust speed and volume
uv run t2s speak "Faster speech example." --rate 220 --volume 0.9

# Use a specific TTS voice (by index from list-voices)
uv run t2s speak "Hello!" --voice 2

# Save audio to a WAV file instead of playing
uv run t2s speak "Save me to disk." --save output.wav
```

### Pre-process text with Ollama before speaking

Ollama cleans up abbreviations, markdown, symbols, and awkward phrasing for natural speech:

```bash
# Auto-selects model interactively
uv run t2s speak "The CEO earned $2.5M in FY24." --process

# Specify a model
uv run t2s speak "Dr. Smith's report: ~40% increase YoY." --process --model llama3.2
```

### Summarize long text with Ollama before speaking

```bash
echo "Very long article text..." | uv run t2s speak --summarize --model mistral
```

### Speak a file

```bash
# Read a file aloud
uv run t2s speak-file document.txt

# Summarize with Ollama first, then speak
uv run t2s speak-file article.txt --summarize --model llama3.2

# Save the audio
uv run t2s speak-file notes.md --process --model llama3.2 --save notes.wav
```

### Interactive chat mode (AI responses spoken aloud)

Chat with any Ollama model and hear every response:

```bash
uv run t2s interactive --model llama3.2

# Save each reply as a WAV file
uv run t2s interactive --model mistral --save-dir ./session_audio
```

### Show TTS engine config

```bash
uv run t2s config
```

---

## Stdin / pipe support

```bash
cat README.md | uv run t2s speak --summarize --model llama3.2
curl -s https://example.com | uv run t2s speak
```

---

## How it works

```
Text Input
    │
    ▼
[Optional] Ollama LLM
    ├── --process   → clean up abbreviations, markdown, symbols
    └── --summarize → condense to a natural spoken summary
    │
    ▼
pyttsx3 TTS Engine (espeak-ng backend)
    ├── Play audio directly
    └── Save to WAV file
```

---

## Development

```bash
uv sync --dev
uv run ruff check src/
uv run pytest
```
