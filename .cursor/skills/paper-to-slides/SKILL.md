---
name: paper-to-slides
description: Convert a PDF paper or document into a narrated PPTX slide deck. Bullets and optional figures go in the slide body; full narration goes in the Notes. Use when the user gives a PDF and wants slides, a presentation, or a slide deck from it.
---

# paper-to-slides

Turns a PDF document into a PPTX presentation where:
- **Slide body** — concise bullets (what an audience reads)
- **Notes** — full narration sentences (what a speaker says / voice-over)
- **Images** — key figures extracted from the PDF, embedded per slide

## Workflow

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

### Step 4 — Verify and offer next step

Open or inspect `output.pptx`. Tell the user:

> PPTX created: `output.pptx`
> To generate a narrated video: `./run.sh output.pptx --engine kokoro`

---

## Slide plan JSON schema

```json
[
  {
    "title":      "Overview of the Method",
    "bullets":    ["Key idea A", "Key idea B", "Constraint C"],
    "narration":  "In this slide we introduce the core method. The key idea A addresses...",
    "image_page": 4
  }
]
```

`image_page` pulls the largest image from that PDF page. Omit the field if the slide needs no figure.

---

## Dependencies

Required (already in the text2speech venv):
- `pypdf` — PDF text + image extraction
- `python-pptx` — PPTX generation
- `pillow` — image conversion

Install if missing:
```bash
uv pip install pypdf python-pptx pillow
```

---

## Tips

- **Dense papers**: ask the LLM to focus only on contributions, method, and results — skip background that experts already know.
- **Multiple figures**: set `image_page` on different slides to spread figures across the deck.
- **After PPTX is generated**: the user can edit it in PowerPoint/LibreOffice, then run `./run.sh` to re-render the video.
