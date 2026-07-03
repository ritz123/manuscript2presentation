---
name: paper-to-slides
description: Convert a PDF paper or document into a narrated PPTX slide deck. Bullets and optional figures go in the slide body; full narration goes in the Notes. Use when the user gives a PDF and wants slides, a presentation, or a slide deck from it.
---

# paper-to-slides

Turns a PDF document into a PPTX presentation where:
- **Slide body** — concise bullets (what an audience reads)
- **Notes** — full narration sentences (what a speaker says / voice-over)
- **Images** — key figures extracted from the PDF, embedded per slide

---

## Automated workflow (preferred)

The pipeline is fully automated via `run.sh`:

```bash
# PDF → styled PPTX (saved next to the PDF)
./run.sh paper.pdf --paper

# Also render a narrated MP4 in one shot
./run.sh paper.pdf --paper --video --engine kokoro --voice bm_george

# Customise the Ollama model and slide count
./run.sh paper.pdf --paper --model mistral --n-slides 14
```

Or call the CLI command directly:

```bash
t2s paper-to-slides paper.pdf
t2s paper-to-slides paper.pdf --model llama3.2 --n-slides 10 --video --voice bm_george
```

---

## Manual workflow (fallback — no Ollama, or for custom plans)

### Step 1 — Extract PDF text

```python
import pypdf
reader = pypdf.PdfReader("paper.pdf")
pages  = [p.extract_text() or "" for p in reader.pages]
full_text = "\n\n--- PAGE BREAK ---\n\n".join(pages)
```

### Step 2 — Generate slide plan with LLM

Ask the model to read `full_text` and return a JSON array.
Use this exact prompt:

```
You are a presentation designer. Read the document below and produce a slide plan as a JSON array.

Rules:
- 8-14 slides total (first = title/overview, last = conclusions/takeaways)
- "title": short slide title (<= 8 words)
- "tag": optional short section label in ALL CAPS (e.g. "OVERVIEW", "METHOD")
- "bullets": 4-6 concise on-slide points (<= 12 words each, no full sentences)
- "narration": 3-5 full spoken sentences expanding on the bullets
- "image_page": (optional integer) the PDF page number whose figure best illustrates this slide; omit if none
- Output ONLY valid JSON, no prose

Document:
<paste full_text here>
```

Save the model's response as `plan.json`.

### Step 3 — Build the PPTX

```bash
python .cursor/skills/paper-to-slides/scripts/create_pptx.py \
    plan.json output.pptx paper.pdf
```

`paper.pdf` is optional — include it to embed extracted figures.

### Step 4 — Generate the narrated video

```bash
./run.sh output.pptx --slide --engine kokoro --voice bm_george
```

---

## Slide plan JSON schema

```json
[
  {
    "title":      "Overview of the Method",
    "tag":        "METHOD",
    "bullets":    ["Key idea A", "Key idea B", "Constraint C"],
    "narration":  "In this slide we introduce the core method. The key idea A addresses...",
    "image_page": 4
  }
]
```

`image_page` pulls the largest image from that PDF page. Omit if the slide needs no figure.

---

## Dependencies

Required (already in the manuscript2presentation venv):
- `pypdf` — PDF text + image extraction
- `python-pptx` — PPTX generation
- `pillow` — image conversion
- `ollama` — local LLM client (for automated workflow)

Install if missing:
```bash
uv pip install pypdf python-pptx pillow ollama
```

---

## Tips

- **Dense papers**: tell the LLM to focus only on contributions, method, and results.
- **Multiple figures**: assign different `image_page` values across slides to spread figures through the deck.
- **Edit then re-render**: open the PPTX in PowerPoint/LibreOffice, tweak it, then run `./run.sh output.pptx --slide` to re-render the video.
