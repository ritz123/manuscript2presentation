---
name: paper-to-slides
description: Convert a PDF paper or document into a narrated PPTX slide deck. Bullets and figures go in the slide body; full narration goes in the Notes. Use when the user gives a PDF and wants slides, a presentation, or a slide deck from it.
---

# paper-to-slides

Turns a PDF document into a PPTX presentation where:
- **Slide body** — concise bullets (what an audience reads) + relevant figures extracted from the PDF
- **Notes** — full narration sentences (what a speaker says / voice-over)

---

## Preferred workflow — Claude plans the slides (highest quality)

This approach uses Claude (you, the Cursor AI) to read the document and generate the slide plan.
The CLI then handles PPTX building and video rendering. No Ollama required.

### Step 1 — Scan the PDF for figure pages

Run this to extract text and identify which pages contain figures:

```bash
cd /path/to/manuscript2presentation
source .venv/bin/activate
python3 - <<'EOF'
import warnings, pypdf, io, re
from PIL import Image as PILImage

warnings.filterwarnings("ignore", message=".*Lookup Table.*")
pdf_path = "paper.pdf"   # ← change this
reader = pypdf.PdfReader(pdf_path)
pages = [p.extract_text() or "" for p in reader.pages]

# Find pages with embedded raster images
figure_pages = []
reader2 = pypdf.PdfReader(pdf_path)
for i, page in enumerate(reader2.pages):
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            imgs = list(page.images)
    except Exception:
        imgs = []
    for img in imgs:
        try:
            pil = PILImage.open(io.BytesIO(img.data))
            if pil.width * pil.height > 10_000:
                figure_pages.append(i + 1)
                break
        except Exception:
            pass

# Also flag pages with "Fig N" captions (vector-only figures)
for i, text in enumerate(pages):
    pg = i + 1
    if pg not in figure_pages and re.search(r"\bFig(?:ure)?\s*\d", text, re.IGNORECASE):
        figure_pages.append(pg)

figure_pages.sort()

# Write text + catalog to a temp file for Claude to read
with open("/tmp/paper_extracted.txt", "w") as f:
    f.write(f"FIGURE PAGES (pages that contain images or figure captions): {figure_pages}\n\n")
    for i, text in enumerate(pages):
        f.write(f"=== PAGE {i+1} ===\n{text}\n\n")

print(f"Pages: {len(pages)}, chars: {sum(len(t) for t in pages):,}")
print(f"Figure pages: {figure_pages}")
print("Written to /tmp/paper_extracted.txt")
EOF
```

### Step 2 — Claude reads the document and generates the slide plan

Read `/tmp/paper_extracted.txt` using the Read tool, then produce a JSON slide plan directly.

**Slide plan rules:**
- 10–14 slides (first = title/overview, last = key takeaways)
- `"title"`: ≤ 8 words, punchy
- `"tag"`: short section label in ALL CAPS (e.g. `"METHOD"`, `"RESULTS"`)
- `"bullets"`: 4–6 concise on-slide points, ≤ 12 words each, no full sentences
- `"narration"`: 3–5 full spoken sentences that expand meaningfully on the bullets
- `"image_page"`: integer from the **FIGURE PAGES list only**; assign to slides where the figure is relevant; omit if none fits

**Quality bar for narration:** it should read as natural speech, not bullet-point prose. Aim for the voice of a knowledgeable presenter explaining ideas to an engaged audience.

Write the plan to a temp file:

```bash
cat > /tmp/plan.json << 'EOF'
[ ... your JSON here ... ]
EOF
python3 -c "import json; d=json.load(open('/tmp/plan.json')); print(len(d), 'slides OK')"
```

### Step 3 — Build the PPTX

```bash
cd /path/to/manuscript2presentation && source .venv/bin/activate
python3 - <<'EOF'
import json, warnings
from pathlib import Path
warnings.filterwarnings("ignore", message=".*Lookup Table.*")
from text2speech.pptx_builder import build_pptx

plan = json.load(open("/tmp/plan.json"))
build_pptx(plan, Path("output.pptx"), Path("paper.pdf"))
EOF
```

### Step 4 — Render the narrated video

```bash
./run.sh output.pptx --slide
# With a specific voice:
./run.sh output.pptx --slide --engine kokoro --voice bm_george
```

---

## Automated workflow — Ollama (fully batch, lower quality)

Use when you need batch automation and have Ollama running locally.

```bash
# Full pipeline: PDF → PPTX + MP4
./run.sh paper.pdf --paper

# Choose model and slide count
./run.sh paper.pdf --paper --model mistral --n-slides 12

# PPTX only (skip video)
./run.sh paper.pdf --paper --no-video
```

Or via the CLI directly:

```bash
t2s paper-to-slides paper.pdf
t2s paper-to-slides paper.pdf --model llama3.2 --n-slides 10 --voice bm_george
```

The automated pipeline:
1. Extracts full text from the PDF
2. Scans every page for embedded raster images and "Fig N" captions → builds a **figure catalog**
3. Calls the Ollama model with the catalog so it only assigns real figure pages
4. Validates all `image_page` values; discards any the model hallucinated
5. Uses a keyword-overlap matcher to assign any remaining figure pages to the best-fit slide
6. Builds the PPTX and optionally renders the MP4

---

## How figures are extracted and placed

The pipeline uses two strategies, tried in order:

| Strategy | When it works |
|---|---|
| **Embedded raster** | PDF contains JPEG/PNG images (most scanned docs, photographs) |
| **Full-page render** via `pypdfium2` | PDF uses vector graphics (LaTeX, matplotlib) — page rendered at 144 dpi |

On each slide that has an `image_page`, the figure occupies the right ~42% of the content area; bullets fill the left ~55%. Slides without a figure use the full width for bullets.

---

## Slide plan JSON schema

```json
[
  {
    "title":      "Overview of the Method",
    "tag":        "METHOD",
    "bullets":    ["Key idea A", "Key idea B", "Constraint C"],
    "narration":  "In this slide we introduce the core method. The key idea A addresses the fundamental challenge of X by doing Y...",
    "image_page": 4
  }
]
```

`image_page` must be a page number from the **FIGURE PAGES** list. Omit the field entirely if no figure is relevant to the slide.

---

## Dependencies

Required (already in the manuscript2presentation venv):

```
pypdf         — PDF text + embedded image extraction
pypdfium2     — full-page PDF rendering (vector figure fallback)
python-pptx   — PPTX generation
pillow        — image decoding and conversion
ollama        — local LLM client (automated workflow only)
```

Install if missing:
```bash
uv pip install pypdf pypdfium2 python-pptx pillow ollama
```

---

## Tips

- **Claude workflow produces better slides** than Ollama because it understands context, argument structure, and what makes a good narration sentence.
- **Dense papers**: focus the plan on contributions, method, and results; skip background material that the audience can look up.
- **Spread figures**: assign different `image_page` values across slides so the deck feels visually varied.
- **Edit then re-render**: open the PPTX in LibreOffice/PowerPoint, tweak bullets or narration in the Notes pane, then re-run `./run.sh output.pptx --slide` to regenerate the video without re-planning.
- **Voice selection**: `--voice bm_george` (male, British) or `--voice af_heart` (female, American). Run `./run.sh list-voices --engine kokoro` for the full list.
