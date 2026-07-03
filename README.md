# manuscript2presentation

Convert any document into a **narrated video presentation** — entirely offline.

Give it a PDF, PowerPoint, YAML, or TSX slide deck and get back an MP4 with
synchronized voice-over, rendered slides, and embedded figures.

---

## Quick start

```bash
# ── Existing slide deck (PPTX / YAML / TSX) → narrated MP4 ──────────────────
./run.sh slides.pptx --slide
./run.sh slides.pptx --slide --engine kokoro --voice bm_george
./run.sh slides.pptx --slide --slides 1-5
./run.sh slides.pptx --slide --output ~/Desktop/talk.mp4

# --slide is the default for .pptx / .yaml / .tsx (can be omitted)
./run.sh slides.pptx --engine kokoro

# ── PDF manuscript → LLM → styled slides → narrated MP4 ─────────────────────
./run.sh paper.pdf --paper
./run.sh paper.pdf --paper --model llama3.2 --n-slides 10
./run.sh paper.pdf --paper --engine kokoro --voice bm_george
./run.sh paper.pdf --paper --video        # also renders MP4 in one shot
```

> **PDF requires an explicit flag** — `--paper` for prose documents, `--slide`
> for slide-per-page PDFs — so the right pipeline is always chosen.

Output goes to `output/<timestamp>_<name>.mp4` by default.

---

## PDF manuscript → narrated video (automated)

The `--paper` flag runs the full pipeline end-to-end with one command:

```
paper.pdf ──► extract text ──► Ollama LLM ──► slide plan
           ──► styled PPTX (bullets + figures + narration in Notes)
           ──► narrated MP4
```

```bash
# Minimum — uses llama3.2, 12 slides, kokoro voice
./run.sh paper.pdf --paper

# Customise the LLM model and slide count
./run.sh paper.pdf --paper --model mistral --n-slides 14

# Produce both PPTX and MP4 in one shot
./run.sh paper.pdf --paper --video --engine kokoro --voice bm_george
```

Ollama must be running locally (`ollama serve`) with a model pulled
(`ollama pull llama3.2`).  The PPTX is saved next to the PDF; the MP4
goes to `output/`.

### What the LLM produces per slide

| Field | On-slide | In video |
|---|---|---|
| `title` | Slide header | — |
| `bullets` | Concise key points | Visible on screen |
| `narration` | Stored in Notes | Spoken as voice-over |
| `image_page` | Figure from that PDF page | Visible on screen |

---

## How slides are rendered

When you pass any supported file to `./run.sh`, the pipeline:

1. **Parses** the file into a list of `SlideSpec` objects:
   - `.pptx` — title from shape named `slide_title`; bullets from body text boxes;
     narration from presenter Notes; figures from picture shapes
   - `.pdf` — title from first line per page; body from remaining text;
     figures from embedded images
   - `.yaml` — structured `title`, `bullets`, `narration`, `right_bullets` fields
   - `.tsx` — parses `SlideSpec(...)` call arguments with regex

2. **Renders** each slide to a 1280×720 PNG (Pillow):
   - Light background, dark navy accent, blue progress bar
   - Auto-scaling title and body fonts
   - Two-column bullet layout for dense slides
   - Images composited into the right panel

3. **Generates narration audio** per slide (Kokoro or pyttsx3)

4. **Assembles** images + audio into an MP4 via ffmpeg (`imageio-ffmpeg`)

---

## Voices

```bash
# List all available voices
./run.sh list-voices --engine kokoro
```

**Male voices (Kokoro):**

| ID | Name | Accent |
|---|---|---|
| `am_adam` | Adam | American |
| `am_michael` | Michael | American |
| `am_onyx` | Onyx | American |
| `bm_george` | George | British |
| `bm_daniel` | Daniel | British |

**Female voices (Kokoro):**

| ID | Name | Accent |
|---|---|---|
| `af_heart` | Heart | American |
| `af_sarah` | Sarah | American |
| `bf_emma` | Emma | British |

Preview any voice:

```bash
./run.sh speak "Well-written papers are read, remembered, cited." \
    --engine kokoro --voice bm_george
```

---

## Other commands

```bash
# Speak text aloud
./run.sh speak "Hello world" --engine kokoro

# Speak a text file
./run.sh speak-file notes.txt --engine kokoro

# Generate per-slide MP3 narrations (no video)
./run.sh canvas-mp3 slides.pptx --engine kokoro --combined all.mp3

# List available Kokoro voices
./run.sh list-voices --engine kokoro
```

---

## Requirements

| Requirement | Notes |
|---|---|
| Python ≥ 3.10 | |
| [uv](https://docs.astral.sh/uv/) | Fast Python package manager |
| `espeak-ng` | Fallback TTS engine on Linux |
| [Ollama](https://ollama.ai) (optional) | Local LLM — only needed for `paper-to-slides` slide planning |

Install `espeak-ng` if needed:

```bash
sudo apt install espeak-ng        # Debian/Ubuntu
sudo dnf install espeak-ng        # Fedora/RHEL
sudo pacman -S espeak-ng          # Arch
```

The first run of `./run.sh` bootstraps the virtual environment automatically.
Kokoro model weights (~300 MB) are downloaded on first use and cached locally.

---

## Dependencies

All Python dependencies are managed by `uv` and declared in `pyproject.toml`.

### Always installed

| Package | Purpose | AI/ML? |
|---|---|---|
| `typer`, `click` | CLI framework | No |
| `rich` | Terminal output formatting | No |
| `pillow` | Renders each slide to a 1280×720 PNG | No |
| `imageio-ffmpeg` | Bundles ffmpeg; assembles PNGs + audio into MP4 | No |
| `python-pptx` | Reads and writes PPTX files | No |
| `pypdf` | Extracts text and embedded images from PDFs | No |
| `pyyaml` | Parses YAML slide decks | No |
| `soundfile`, `numpy` | WAV audio I/O | No |
| `pyttsx3` | Rule-based TTS via the system `espeak-ng` engine (fallback) | No |
| `ollama` | Python client for a locally running Ollama LLM server | **Yes** — local LLM |

### Optional — Kokoro neural TTS

Installed automatically on first use of `--engine kokoro`:

| Package | Purpose | AI/ML? |
|---|---|---|
| `kokoro-onnx` | Neural TTS model, runs fully offline via ONNX Runtime | **Yes** — neural TTS |
| `misaki[en]` | Grapheme-to-phoneme text normaliser for Kokoro | **Yes** — ML-based |

### AI/ML usage summary

Everything runs **100% on your machine** — no cloud APIs, no keys, no internet
required after the initial one-time model download.

| Component | When used | Model size |
|---|---|---|
| **Kokoro TTS** | `--engine kokoro` | ~300 MB (ONNX, cached after first run) |
| **Ollama LLM** | `paper-to-slides` slide planning; `--process` / `--summarize` flags | Depends on which model you pull locally |
| **pyttsx3 / espeak-ng** | Default TTS (no `--engine` flag) | None — rule-based |

---

## Project layout

```
text2speech/
├── run.sh                          # Main entry point
├── src/text2speech/
│   ├── cli.py                      # typer CLI (canvas-video, canvas-mp3, speak, …)
│   ├── canvas_video.py             # Slide renderer + video assembler
│   ├── slides.py                   # PPTX / PDF reader → Slide objects
│   └── tts.py                      # TTS engine abstraction
├── .cursor/skills/paper-to-slides/ # paper-to-slides Cursor skill
│   ├── SKILL.md
│   └── scripts/create_pptx.py      # Styled PPTX builder
└── ashby-how-to-write-paper.yaml   # Example slide deck (YAML format)
```

---

## YAML slide format

You can author slides in YAML and pass them directly to `./run.sh`:

```yaml
- index: 1
  title: "My Talk Title"
  tag: "OVERVIEW"
  bullets:
    - "Key point one"
    - "Key point two"
    - "  Sub-point (indent with 2 spaces)"
  narration: >
    This is the full spoken narration for the slide.
    It can be several sentences long.

- index: 2
  title: "Second Slide"
  tag: "SECTION 1"
  bullets:
    - "Another point"
  right_bullets:
    - "Right column point"
  narration: "Narration for slide two."
```

```bash
./run.sh my-talk.yaml --engine kokoro
```

---

## Development

```bash
uv sync --dev
uv run ruff check src/
uv run pytest
```
