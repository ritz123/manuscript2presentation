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
./run.sh paper.pdf --paper                # slides + video + review (all on by default)
./run.sh paper.pdf --paper --model llama3.2 --n-slides 10
./run.sh paper.pdf --paper --engine kokoro --voice bm_george
./run.sh paper.pdf --paper --no-video     # PPTX + review, skip video
./run.sh paper.pdf --paper --no-review    # PPTX + video, skip review
./run.sh paper.pdf --paper --review-no-web  # review without internet (offline)
```

> **PDF requires an explicit flag** — `--paper` for prose documents, `--slide`
> for slide-per-page PDFs — so the right pipeline is always chosen.

Output goes to `output/<timestamp>_<name>.mp4` by default.

---

## Workflow: Paper reviewer

When reviewing a paper, use this three-phase approach to build understanding
quickly before forming an opinion.

### Phase 1 — AI overview (5 min)

Generate a narrated presentation from the manuscript.  This gives you a
structured visual summary of the paper — problem, method, results, figures —
before you read a single sentence yourself.

```bash
./run.sh paper.pdf --paper
# Opens a 10–14 slide narrated MP4 covering the full paper
```

> **Tip:** Use `--n-slides 10` for short papers and `--n-slides 14` for long
> ones.  Add `--no-video` if you only want the PPTX to click through manually.

Watch or step through the output.  By the end of Phase 1 you should have a
working mental model of what the paper claims to do and how.

---

### Phase 2 — AI-assisted structured review (10–15 min)

Two options depending on whether you are inside Cursor or at the terminal:

**Option A — terminal (Ollama, web-enabled):**

```bash
./run.sh paper.pdf --review
# Saves paper_review.md next to the PDF

# Use a larger model for better quality
./run.sh paper.pdf --review --model qwen2.5:72b

# Offline — skips citation verification
./run.sh paper.pdf --review --no-web
```

The Ollama model is given `web_search` and `fetch_url` tools so it can look up
DOI records and verify citations during the review.  Output is a structured
markdown file covering all sections of the `ai-dm-paper-review` skill.

**Option B — Cursor chat (Claude, highest quality):**

Attach the PDF in the Cursor chat and ask:

```
Review paper.pdf using the ai-dm-paper-review skill
```

Both options produce a review covering:

| Section | What it covers |
|---|---|
| **Research question** | Is the RQ clearly stated? Is it novel and scoped correctly? |
| **Abstract** | Does the abstract accurately reflect the contributions and findings? |
| **Experiment setup** | Are baselines fair, datasets appropriate, ablations present? |
| **Findings** | Are claims supported by the evidence shown? Are limitations acknowledged? |
| **Methodology** | Is the approach sound, reproducible, and well-motivated? |
| **Citations** | Bibliographic correctness, relevance, in-text usage — verified online |
| **Novelty** | What is genuinely new vs incremental |
| **Score & recommendation** | Accept / Weak Accept / Borderline / Weak Reject / Reject |

Read the generated review and take notes on flagged issues before Phase 3.

---

### Phase 3 — Full read (remaining time)

Read the manuscript from start to finish with your Phase 2 notes in hand.
Focus attention on the sections flagged by reviewer comments.  Verify claims
against figures and tables directly.

By this point the narrative is already familiar from Phase 1, so the full read
is fast and purposeful rather than exploratory.

---

## PDF manuscript → slides (recommended: Claude plans)

The highest-quality workflow has **Claude read the PDF and write the slide plan** directly.
No Ollama required. The `paper-to-slides` Agent Skill handles the full pipeline
when you ask the Cursor agent in chat:

```
paper.pdf ──► extract text ──► Claude reads & plans ──► /tmp/plan.json
           ──► pptx_builder → styled PPTX (bullets + figures + narration in Notes)
           ──► (optional) ./run.sh → narrated MP4
```

**How to use it:** open the Cursor chat, attach or mention your PDF, and ask:

```
Convert paper.pdf into a slide deck
```

The agent will automatically:
1. Extract text and detect figure pages from the PDF
2. Read the full document and write a JSON slide plan to `/tmp/plan.json`
3. Call `pptx_builder` to build the styled PPTX
4. Optionally render the narrated MP4 via `./run.sh`

> This produces better slides than the Ollama pipeline because Claude
> understands argument structure, figures out what's important, and writes
> narration that reads as natural speech.

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
├── .cursor/skills/paper-to-slides/    # Cursor skill: PDF → PPTX via Claude
│   └── SKILL.md
├── .cursor/skills/ai-dm-paper-review/ # Cursor skill: structured academic review
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
