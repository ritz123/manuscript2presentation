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
./run.sh paper.pdf --paper --no-video     # PPTX only, skip video
```

> **PDF requires an explicit flag** — `--paper` for prose documents, `--slide`
> for slide-per-page PDFs — so the right pipeline is always chosen.

Output goes to `output/<timestamp>_<name>.mp4` by default.

---

## PDF manuscript → slides (recommended: Claude plans)

The highest-quality workflow has **Claude read the PDF and write the slide plan** directly.
No Ollama required — invoke the `/paper-to-slides` skill in Cursor:

```
paper.pdf ──► Claude reads & plans ──► JSON slide plan
           ──► pptx_builder → styled PPTX (bullets + figures + narration in Notes)
```

```bash
# Step 1: Claude generates the JSON plan (via /paper-to-slides skill)
# Step 2: Build the PPTX
python3 - <<'EOF'
import json, warnings
from pathlib import Path
warnings.filterwarnings("ignore", message=".*Lookup Table.*")
from text2speech.pptx_builder import build_pptx
plan = json.load(open("/tmp/plan.json"))
build_pptx(plan, Path("data/my-talk.pptx"), Path("paper.pdf"))
EOF

# Step 3 (optional): Render narrated video from the PPTX
./run.sh data/my-talk.pptx --engine kokoro --voice bm_george
```

### What each slide plan field controls

| Field | On-slide | In video |
|---|---|---|
| `title` | Slide header (bold, white on navy) | — |
| `tag` | Section label in sky-blue above the title | — |
| `bullets` | Concise key points (em-dash markers) | Visible on screen |
| `narration` | Stored in Notes pane | Spoken as voice-over |
| `image_page` | Figure from that PDF page (right panel) | Visible on screen |

---

## PDF manuscript → slides (automated: Ollama)

For batch automation without Cursor, the `--paper` flag runs the full pipeline:

```
paper.pdf ──► extract text ──► Ollama LLM ──► slide plan
           ──► styled PPTX (bullets + figures + narration in Notes)
           ──► narrated MP4
```

```bash
# Full pipeline in one command (PPTX + MP4 by default)
./run.sh paper.pdf --paper

# Customise LLM model, slide count, and voice
./run.sh paper.pdf --paper --model mistral --n-slides 14
./run.sh paper.pdf --paper --engine kokoro --voice bm_george

# PPTX only — skip video rendering
./run.sh paper.pdf --paper --no-video
```

Ollama must be running locally (`ollama serve`) with a model pulled
(`ollama pull llama3.2`).  The PPTX is saved next to the PDF; the MP4
goes to `output/`.

---

## How slides are rendered

When you pass any supported file to `./run.sh`, the pipeline:

1. **Parses** the file into a list of `SlideSpec` objects:
   - `.pptx` — title from shape named `slide_title`; bullets from body text boxes
     (chrome shapes `slide_tag`, `slide_counter` are excluded automatically);
     narration from presenter Notes; figures from picture shapes
   - `.pdf` — title from first line per page; body from remaining text;
     figures from embedded images
   - `.yaml` — structured `title`, `bullets`, `narration`, `right_bullets` fields
   - `.tsx` — parses `SlideSpec(...)` call arguments with regex

2. **Renders** each slide to a 1280×720 PNG (Pillow) — **professional dark-slate + sky-blue theme**:
   - **Title slide**: split-panel (57% deep-navy / 43% near-white), sky-blue join strip
   - **Content slides**: deep-slate header with sky-blue accent line at bottom,
     sky-blue section tag and em-dash bullet markers, slim left accent bar,
     sky-blue progress bar at the bottom
   - Auto-scaling title and body fonts; two-column bullet layout for dense slides
   - Images in right panel with sky-blue border and white interior

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
│   ├── cli.py                      # typer CLI (paper-to-slides, canvas-video, speak, …)
│   ├── pptx_builder.py             # Builds styled PPTX from a JSON slide plan
│   ├── canvas_video.py             # Renders slides to PNG + assembles MP4
│   ├── slides.py                   # PPTX / PDF / YAML reader → SlideSpec objects
│   └── tts.py                      # TTS engine abstraction (Kokoro / pyttsx3)
├── .cursor/skills/paper-to-slides/ # /paper-to-slides Cursor skill
│   └── SKILL.md
├── data/                           # Generated PPTX files
└── output/                         # Generated MP4 videos
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
