"""
Render the Ashby 'How to Write a Paper' canvas slides into a narrated video or MP3.

Pipeline (video):
  1. For each slide, render a 1280×720 PNG with Pillow.
  2. Generate a WAV narration using the t2s engine.
  3. Assemble slides + audio into an MP4 via ffmpeg (imageio-ffmpeg bundle).

Pipeline (mp3):
  1. Parse a *.canvas.tsx file to discover slides (titles + narrations).
  2. Generate per-slide WAV narrations using the t2s engine.
  3. Convert each WAV to MP3 via ffmpeg, then concatenate into one combined MP3.
"""

from __future__ import annotations

import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from PIL import Image, ImageDraw, ImageFont

# ── colour palette (mirrors Cursor dark theme) ─────────────────────────────
BG        = (24, 24, 24)       # bg.editor
CHROME    = (20, 20, 20)       # bg.elevated
ACCENT    = (89, 156, 231)     # accent.primary
TEXT_PRI  = (228, 228, 228)    # text.primary  ~90 %
TEXT_SEC  = (228, 228, 228, 140)  # text.secondary ~55 % – stored as RGBA for blending
STROKE    = (228, 228, 228, 40)   # stroke.tertiary
WHITE     = (255, 255, 255)
DIM       = (160, 160, 160)

W, H = 1280, 720

# ── font helpers ───────────────────────────────────────────────────────────

def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    candidates = [
        # DejaVu (confirmed present on this system at this path)
        "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf" if bold else
        "/usr/share/fonts/dejavu/DejaVuSans.ttf",
        # Liberation Sans
        "/usr/share/fonts/liberation/LiberationSans-Bold.ttf" if bold else
        "/usr/share/fonts/liberation/LiberationSans-Regular.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf" if bold else
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        # DejaVu alternate locations
        "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf" if bold else
        "/usr/share/fonts/TTF/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for path in candidates:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    # PIL built-in scalable font (Pillow >= 10)
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def _wrap(text: str, font: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    """Word-wrap *text* to fit within *max_width* pixels."""
    words = text.split()
    lines: list[str] = []
    current = ""
    dummy = Image.new("RGB", (1, 1))
    draw = ImageDraw.Draw(dummy)
    for word in words:
        test = f"{current} {word}".strip()
        w = draw.textlength(test, font=font)
        if w <= max_width:
            current = test
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


# ── slide data ─────────────────────────────────────────────────────────────

@dataclass
class SlideSpec:
    index: int
    title: str
    tag: str                          # small uppercase label
    bullets: list[str]                # left column bullet points
    right_bullets: list[str] = field(default_factory=list)   # optional right column
    quote: str = ""
    narration: str = ""               # text spoken for this slide


SLIDES: list[SlideSpec] = [
    SlideSpec(
        index=1,
        title="How to Write a Paper",
        tag="MIKE ASHBY  |  CAMBRIDGE  |  6TH EDITION 2005",
        bullets=[
            "A prescriptive guide for researchers writing their first - or fifth - paper.",
            "Covers the full journey: from blank page to polished publication.",
            "Structured like engineering design:",
            "  Market -> Concept -> Embodiment -> Detail -> End-product.",
            "9 sections | Appendix with real examples | Checklist",
        ],
        narration=(
            "How to Write a Paper, by Mike Ashby of the Engineering Department at the University "
            "of Cambridge. This guide, in its sixth edition, offers prescriptive advice for writing "
            "clear and effective research papers — covering the full journey from a blank page to a "
            "polished publication, structured around the principles of engineering design."
        ),
    ),
    SlideSpec(
        index=2,
        title="1. The Design Process",
        tag="SECTION 1",
        bullets=[
            "Well-written papers are read, remembered, cited.",
            "Poorly written papers are not.",
            "",
            "Five design steps:",
            "  1. Market Need  - who will read it, and how?",
            "  2. Concept      - plan before you draft.",
            "  3. Embodiment   - first draft, facts first.",
            "  4. Detail       - craft clarity, balance, style.",
            "  5. End-Product  - layout, headings, figures.",
        ],
        narration=(
            "Ashby opens with a core principle: well-written papers are read, remembered, and cited. "
            "Poorly written ones are not. Writing a paper is a design activity with five essential steps: "
            "understand your market, form a concept, produce an embodiment — the first draft — refine the "
            "details, and deliver a polished end product. Each step depends on the one before."
        ),
    ),
    SlideSpec(
        index=3,
        title="2. Know Your Readers",
        tag="SECTION 2 - THE MARKET",
        bullets=[
            "Thesis examiners: all relevant research, background, thinking, conclusions.",
            "Journal referees: rigour, novelty, concision.",
            "Funding panels: alignment with priorities, quality, promise.",
            "Popular audience: intelligent but non-specialist — the hardest to write for.",
            "",
            "Write poorly → bore, exasperate, and lose your readers.",
            "Write well → they respond in the way you plan.",
        ],
        narration=(
            "Section two asks: who are your readers? Your thesis examiners want everything relevant — "
            "why you did the research, what you found, and what you concluded. Journal referees expect "
            "rigour and novelty. Funding panels want alignment with their priorities. And a popular "
            "audience — intelligent but non-specialist — demands the finest-tuned style of all. "
            "Write poorly, and you lose every one of them."
        ),
    ),
    SlideSpec(
        index=4,
        title="3. The Concept Sheet",
        tag="SECTION 3 - CONCEPT",
        bullets=[
            "When you can't write, it's because you don't know what to say.",
            "",
            "How to make one:",
            "  · A3 sheet, landscape orientation.",
            "  · Title at the top; section headings in boxes.",
            "  · Ideas, references, figures in bubbles with arrows.",
            "  · Add to it at any time — it is your road-map.",
            "",
            "Breaks writer's block. Lets you see the whole before drafting any part.",
        ],
        narration=(
            "Before writing a single word, make a concept sheet. Take an A3 sheet in landscape mode, "
            "write a tentative title at the top, then sketch your section headings in boxes. "
            "Scatter ideas, references, and planned figures as bubbles connected to their sections. "
            "This simple act breaks writer's block and gives you a road-map of the entire paper "
            "before the hard work of drafting begins."
        ),
    ),
    SlideSpec(
        index=5,
        title="4. Paper Structure - All 12 Sections",
        tag="SECTION 4 - EMBODIMENT",
        bullets=[
            "4.1  Title — meaningful and brief",
            "4.2  Attribution — names, institute, date",
            "4.3  Abstract — ≤100 words: motive, method, results, conclusions",
            "4.4  Introduction — problem, literature, novel contribution",
            "4.5  Method — sufficient detail to reproduce",
            "4.6  Results — output only, no interpretation",
            "4.7  Discussion — principles, models, comparison",
            "4.8  Conclusion — advances in knowledge",
            "4.9  Acknowledgements — simple, full names",
            "4.10 References — complete: name, year, journal, pages",
            "4.11 Figures — self-contained, titled, captioned, labelled",
            "4.12 Appendices — essential material that interrupts flow",
        ],
        narration=(
            "A paper has twelve parts: title, attribution, abstract, introduction, method, results, "
            "discussion, conclusion, acknowledgements, references, figures, and appendices. "
            "You don't write them in order — draft whichever section you have the clearest ideas "
            "for first. Get the pieces assembled, then worry about how they fit together."
        ),
    ),
    SlideSpec(
        index=6,
        title="Abstract & Introduction",
        tag="SECTIONS 4.3 & 4.4",
        bullets=[
            "Abstract - one sentence each on:",
            "  - Motive   - Method   - Key results   - Conclusions",
            "  Target <= 100 words. No waffle. No spurious detail.",
            "  Imagine you're paying 10p per word.",
            "",
            "Introduction - tell the reader:",
            "  - What is the problem and why is it interesting?",
            "  - Who has worked on it and what did they do?",
            "  - What will YOU do that is new?",
            "  Start with a good first sentence - not a platitude.",
        ],
        narration=(
            "The abstract is your paper in miniature: one sentence each on motive, method, key results, "
            "and conclusions. Target a hundred words. Imagine you are paying ten pence per word — "
            "that sharpens the mind. "
            "The introduction states the problem, reviews the literature briefly, and tells the reader "
            "exactly what novel contribution you are about to make. Start with a hook, not a platitude."
        ),
    ),
    SlideSpec(
        index=7,
        title="Results & Discussion",
        tag="SECTIONS 4.6 & 4.7",
        bullets=[
            "Results - report without interpretation:",
            "  - All symbols and units defined.",
            "  - Error bars or confidence limits given.",
            "  - Concise and economical.",
            "",
            "  POOR:   'It is clearly shown in Figure 3 that shear loading",
            "           had caused cell-walls to suffer ductile fracture...'",
            "  BETTER: 'Shear loading fractures cell-walls (Figure 3).'",
            "",
            "Discussion - extract principles, compare model with data.",
            "Never mix Results with Discussion.",
        ],
        narration=(
            "Results are reported without interpretation — just the data, with error bars and proper units. "
            "Discussion is where you extract principles, compare data to theory, and build toward your conclusions. "
            "Never mix the two. And always prefer brevity: "
            "'Shear loading fractures cell walls' is far better than a two-line description of what Figure 3 already shows."
        ),
    ),
    SlideSpec(
        index=8,
        title="5. Grammar Essentials",
        tag="SECTION 5",
        bullets=[
            "Mess up grammar -> confuse the reader.",
            "",
            "'that' vs 'which':",
            "  'that' limits the noun - no commas.",
            "    'Computations that were on a Cray were more accurate.'",
            "    (only the Cray ones, not others)",
            "  'which' adds a new fact - use commas.",
            "    'Computations, which were on a Cray, were more accurate.'",
            "    (all of them happened to be on a Cray)",
            "",
            "Compound sentences must balance comparable ideas.",
            "Never mix major findings with trivial observations.",
        ],
        narration=(
            "Grammar tells the reader the function of words. The most misused distinction is "
            "that versus which. That limits the noun it qualifies — no commas needed. "
            "Which introduces an additional fact about the noun — commas required. "
            "Compound sentences must balance comparable ideas of similar weight. "
            "Do not link a major finding with an observation that the team went to lunch."
        ),
    ),
    SlideSpec(
        index=9,
        title="7. Punctuation",
        tag="SECTION 7",
        bullets=[
            "Full stop  .   Ends declarative sentences.",
            "Comma      ,   Separates parts that would confuse if they touched.",
            "Semi-colon ;   Links closely related independent clauses.",
            "Colon      :   Introduces elaboration - sets up anticipation.",
            "Dash       --  Sets off a parenthetic aside; introduces a final upshot.",
            "Hyphen     -   Connects compound words: ball-and-stick, box-girder.",
            "Apostrophe '   Possession (Sutcliffe's) or contraction (it's = it is).",
            "               NO apostrophe in 'its' as a possessive.",
            "Exclamation !  Avoid in scientific writing. Say what you mean directly.",
            "Parentheses () Embrace asides. Don't let them cloud the main meaning.",
        ],
        narration=(
            "Punctuation orders prose and signals how to interpret it. "
            "The colon sets up anticipation. The semi-colon links closely related clauses. "
            "The dash sets off a parenthetic aside or introduces a final summary. "
            "The apostrophe shows possession or contraction — but never in its as a possessive. "
            "And the exclamation mark: delete it. Say what you mean directly."
        ),
    ),
    SlideSpec(
        index=10,
        title="8. Style - Clarity & Precision",
        tag="SECTION 8",
        bullets=[
            "8.1 Be clear - simple language, short words, familiar words.",
            "8.3 Define everything - all symbols, all abbreviations.",
            "8.4 Avoid empty words:",
            "    Weak qualifiers: very, rather, somewhat, quite.",
            "    'This very important point' -> 'This point'",
            "    'The agreement is quite good' -> suggests it is not.",
            "8.5 Revise and rewrite:",
            "    Nobody gets it right first time.",
            "    Some papers go through 8-10 drafts.",
            "    Put the draft aside for at least 48 hours.",
        ],
        narration=(
            "Style begins with clarity. Use simple words, familiar constructions, short sentences. "
            "Every word must earn its place. Avoid weak qualifiers — very, quite, rather — they dilute the message. "
            "'This very important point' becomes simply 'this point'. "
            "And revise. Nobody gets it right the first time. The most spontaneous-seeming prose "
            "is often the most rewritten. Let the draft sit for forty-eight hours before returning to it."
        ),
    ),
    SlideSpec(
        index=11,
        title="Common Pitfalls to Avoid",
        tag="SECTIONS 8.6 - 8.8",
        bullets=[
            "Overstating: 'This paper questions the basic assumptions of fracture mechanics'",
            "  -> Fills the reader with mistrust. Let them decide on importance.",
            "",
            "Apologising: 'Unfortunately, there was insufficient time to complete...'",
            "  -> Suggests bad planning. Never, ever, apologise.",
            "",
            "Jargon: excludes the intelligent non-specialist. Avoid it.",
            "",
            "Patronising: 'The amazingly perceptive comment by Fleck...'",
            "",
            "Acronym overload: 'The MEM, analysed by FE, photographed by SEM, by SAM.'",
            "  -> Minimise acronyms. Find other ways.",
        ],
        narration=(
            "Six pitfalls to avoid. Overstating undermines credibility — let the reader decide on importance. "
            "Apologising suggests incompetence — never, ever apologise in a paper. "
            "Jargon excludes the intelligent non-specialist reader. "
            "Patronising your reader breaks their trust. "
            "Breezy web-speak says nothing and shows off. "
            "And an acronym-dense sentence like 'the MEM, analysed by FE, photographed by SEM' is simply unreadable."
        ),
    ),
    SlideSpec(
        index=12,
        title="Good Writing Techniques",
        tag="SECTIONS 8.9 - 8.12",
        bullets=[
            "8.9 Good First Sentence:",
            "   POOR:   'Metal foams are a new class of material attracting interest...'",
            "   BETTER: 'Metal foams are not as strong as they should be.'",
            "   -> New fact, new idea, or revealing comparison in the first line.",
            "",
            "8.10 Analogies: make the abstract concrete.",
            "   'Rolling friction is like riding a bicycle through sand.'",
            "",
            "8.11 Linking Sentences:",
            "   End each paragraph with a word the next paragraph picks up.",
            "   '...we need a material index. A material index is...'",
            "   -> Reader knows what's coming before they read it.",
        ],
        narration=(
            "Start with a hook, not a platitude. "
            "'Metal foams are not as strong as they should be' is far better than "
            "'Metal foams are a new class of material with great potential.' "
            "Use analogies to make the abstract concrete: rolling friction is like riding a bicycle through sand. "
            "And link your paragraphs — end each one with a word or phrase that the next one picks up, "
            "so the reader always knows what is coming before they read it."
        ),
    ),
    SlideSpec(
        index=13,
        title="Checklist for Progress",
        tag="FINAL PAGE OF MANUAL",
        bullets=[
            "Concept:    [ ] Make concept sheet",
            "",
            "First draft:",
            "  [ ] Title & attribution    [ ] Abstract",
            "  [ ] Introduction           [ ] Method",
            "  [ ] Results                [ ] Discussion",
            "  [ ] Conclusions            [ ] Acknowledgements",
            "  [ ] References             [ ] Figures & captions",
            "",
            "Edited draft:",
            "  [ ] Grammar  [ ] Spelling  [ ] Punctuation  [ ] Style",
            "  [ ] Waffle removed   [ ] All symbols defined",
            "  [ ] 48-hour rest period observed",
            "",
            "Visual: [ ] Layout  [ ] Headings  [ ] Figures  [ ] Legibility",
        ],
        narration=(
            "Finally, use a checklist. First pass: make the concept sheet, then draft all twelve sections. "
            "Second pass: check grammar, spelling, punctuation, and style. Remove waffle. Define all symbols. "
            "Then — and this is crucial — put the draft away for at least forty-eight hours "
            "before returning with fresh eyes to review layout, figures, and visual presentation. "
            "That pause is what separates a good paper from a great one."
        ),
    ),
]


# ── image renderer ─────────────────────────────────────────────────────────

def _safe(text: str) -> str:
    """Replace Unicode chars that Liberation/DejaVu Sans may not render."""
    return (
        text
        .replace("\u2014", " - ")   # em dash  —
        .replace("\u2013", " - ")   # en dash  –
        .replace("\u2022", "-")     # bullet   *
        .replace("\u00b7", "-")     # mid dot  *
        .replace("\u2192", "->")    # arrow    ->
        .replace("\u2264", "<=")    # <=
        .replace("\u2265", ">=")    # >=
        .replace("\u00d7", "x")     # times    x
        .replace("\u2026", "...")   # ellipsis ...
    )


def _draw_bullets(
    draw: "ImageDraw.ImageDraw",
    items: list[str],
    f_body: "ImageFont.FreeTypeFont",
    x0: int,
    y0: int,
    max_w: int,
    bottom: int,
    line_h: int,
) -> None:
    """Draw a list of bullet items starting at (x0, y0), stopping at bottom."""
    y = y0
    for item in items:
        if y > bottom:
            break
        raw = _safe(item)
        if not raw.strip():
            y += line_h // 2
            continue
        indent = 0
        text = raw
        is_indented = raw.startswith("  ") or raw.startswith("    ")
        if is_indented:
            indent = 28
            text = raw.lstrip()
            if text.startswith("- "):
                text = text[2:]
                dot_y = y + line_h // 2 - 4
                draw.ellipse([x0 + indent - 14, dot_y, x0 + indent - 6, dot_y + 8], fill=ACCENT)
        elif raw.startswith("[ ]"):
            indent = 6
            text = raw.strip()
        wrapped = _wrap(text, f_body, max_w - indent - 4)
        for wl in wrapped[:2]:
            col = TEXT_PRI if not is_indented else DIM
            draw.text((x0 + indent, y), wl, font=f_body, fill=col)
            y += line_h
        if len(wrapped) > 2:
            y += line_h


def render_slide(spec: SlideSpec, out_path: Path) -> None:
    """Render *spec* as a 1280×720 PNG saved to *out_path*."""
    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)

    # ── fonts (sized for comfortable 1280x720 viewing) ─────────────────────
    f_nav   = _font(24)
    f_tag   = _font(28)
    f_title = _font(80, bold=True)
    f_foot  = _font(22)

    # Body size adapts: text-heavy slides (> 7 bullets) use a smaller font
    # and two-column layout; lighter slides use a bigger, more readable size.
    total_bullets = len(spec.bullets) + len(spec.right_bullets)
    dense = total_bullets > 7
    f_body  = _font(34 if dense else 44)
    line_h  = 44 if dense else 56

    NAV_H  = 62
    FOOT_H = 54
    MARGIN = 64
    TOP    = NAV_H + 18
    BOTTOM = H - FOOT_H - 10

    # ── nav bar ────────────────────────────────────────────────────────────
    draw.rectangle([0, 0, W, NAV_H], fill=CHROME)
    draw.line([0, NAV_H, W, NAV_H], fill=(60, 60, 60), width=1)
    draw.text((28, (NAV_H - 24) // 2), "HOW TO WRITE A PAPER  |  MIKE ASHBY", font=f_nav, fill=DIM)
    counter = f"{spec.index} / {len(SLIDES)}"
    cw = draw.textlength(counter, font=f_nav)
    draw.text((W - 28 - cw, (NAV_H - 24) // 2), counter, font=f_nav, fill=DIM)

    # progress bar
    bar_w = 200
    bar_x = (W - bar_w) // 2
    bar_y = NAV_H - 5
    draw.rectangle([bar_x, bar_y, bar_x + bar_w, bar_y + 3], fill=(60, 60, 60))
    filled = int(bar_w * spec.index / len(SLIDES))
    draw.rectangle([bar_x, bar_y, bar_x + filled, bar_y + 3], fill=ACCENT)

    if spec.index == 1:
        draw.rectangle([0, NAV_H, W, NAV_H + 3], fill=ACCENT)

    # ── content ────────────────────────────────────────────────────────────
    max_body_w = W - 2 * MARGIN
    y = TOP

    # section tag
    if spec.tag:
        draw.text((MARGIN, y), _safe(spec.tag), font=f_tag, fill=ACCENT)
        y += 38

    # title (wrap if needed)
    for line in _wrap(_safe(spec.title), f_title, max_body_w):
        draw.text((MARGIN, y), line, font=f_title, fill=WHITE)
        y += 90
    y += 6

    # divider
    draw.line([MARGIN, y, W - MARGIN, y], fill=(70, 70, 70), width=1)
    y += 20

    # quote
    if spec.quote:
        q_text = f'"{_safe(spec.quote)}"'
        q_lines = _wrap(q_text, f_body, max_body_w - 20)
        bar_top = y
        for ql in q_lines[:3]:
            draw.text((MARGIN + 18, y), ql, font=f_body, fill=DIM)
            y += line_h
        draw.rectangle([MARGIN, bar_top, MARGIN + 4, y], fill=ACCENT)
        y += 12

    # bullets — single or two-column
    if spec.right_bullets:
        col_w = (max_body_w - 24) // 2
        _draw_bullets(draw, spec.bullets, f_body, MARGIN, y, col_w, BOTTOM, line_h)
        _draw_bullets(draw, spec.right_bullets, f_body, MARGIN + col_w + 24, y, col_w, BOTTOM, line_h)
    elif dense:
        # auto two-column for long single-column lists
        mid = (len(spec.bullets) + 1) // 2
        col_w = (max_body_w - 24) // 2
        _draw_bullets(draw, spec.bullets[:mid], f_body, MARGIN, y, col_w, BOTTOM, line_h)
        _draw_bullets(draw, spec.bullets[mid:], f_body, MARGIN + col_w + 24, y, col_w, BOTTOM, line_h)
    else:
        _draw_bullets(draw, spec.bullets, f_body, MARGIN, y, max_body_w, BOTTOM, line_h)

    # ── footer ────────────────────────────────────────────────────────────
    draw.rectangle([0, H - FOOT_H, W, H], fill=CHROME)
    draw.line([0, H - FOOT_H, W, H - FOOT_H], fill=(50, 50, 50), width=1)
    footer = _safe(f"Slide {spec.index}: {spec.title}")
    fy = H - FOOT_H + (FOOT_H - 22) // 2
    draw.text((MARGIN, fy), footer, font=f_foot, fill=(110, 110, 110))

    img.save(str(out_path))


# ── audio generation ───────────────────────────────────────────────────────

def generate_audio(
    spec: SlideSpec,
    out_path: Path,
    tts,           # TTSEngineBase instance
) -> None:
    """Save narration WAV for *spec*."""
    tts.save_to_file(spec.narration, out_path)


# ── video assembly ─────────────────────────────────────────────────────────

def get_ffmpeg() -> str:
    """Return path to ffmpeg binary (bundled imageio-ffmpeg or system)."""
    import shutil
    sys_ffmpeg = shutil.which("ffmpeg")
    if sys_ffmpeg:
        return sys_ffmpeg
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        raise RuntimeError(
            "ffmpeg not found. Install imageio-ffmpeg:\n"
            "  uv pip install imageio-ffmpeg"
        )


def wav_duration(path: Path) -> float:
    """Return duration of a WAV file in seconds."""
    import wave
    with wave.open(str(path), "rb") as wf:
        frames = wf.getnframes()
        rate = wf.getframerate()
        return frames / float(rate)


def assemble_video(
    slides: list[SlideSpec],
    image_dir: Path,
    audio_dir: Path,
    out_path: Path,
    fps: int = 25,
    tail_seconds: float = 1.5,
    progress_cb=None,
) -> None:
    """
    Combine per-slide images + audio into a single MP4.

    Each slide is shown for exactly as long as its narration audio lasts
    (plus *tail_seconds* of silence at the end of each slide).
    """
    ffmpeg = get_ffmpeg()

    # Build a concat filter: each image loops for audio_duration + tail
    # Strategy: write a concat file for the video stream and a concat for audio,
    # then merge via ffmpeg.

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        # concat demuxer file for video
        video_concat = tmp_path / "video.txt"
        audio_concat = tmp_path / "audio.txt"
        v_lines: list[str] = []
        a_lines: list[str] = []

        # Create a silent audio file for tails
        silence_wav = tmp_path / "silence.wav"
        _make_silence(silence_wav, tail_seconds, sample_rate=22050)

        for spec in slides:
            img_file = image_dir / f"slide_{spec.index:02d}.png"
            aud_file = audio_dir / f"slide_{spec.index:02d}.wav"

            dur = wav_duration(aud_file) + tail_seconds

            # Video: show this image for `dur` seconds
            v_lines.append(f"file '{img_file}'")
            v_lines.append(f"duration {dur:.3f}")

            # Audio: real narration + silence tail as separate entries
            narr_dur = wav_duration(aud_file)
            a_lines.append(f"file '{aud_file}'")
            a_lines.append(f"file '{silence_wav}'")
            a_lines.append(f"duration {dur:.3f}")

            if progress_cb:
                progress_cb(spec.index)

        # Repeat last image (ffmpeg concat needs it)
        last_img = image_dir / f"slide_{slides[-1].index:02d}.png"
        v_lines.append(f"file '{last_img}'")

        video_concat.write_text("\n".join(v_lines) + "\n")

        # Build audio via concat of individual wavs + silence
        # Easier: create a single merged audio file using ffmpeg inputs list
        merged_audio = tmp_path / "merged.wav"
        _merge_audio(ffmpeg, slides, audio_dir, silence_wav, merged_audio, tail_seconds)

        cmd = [
            ffmpeg, "-y",
            "-f", "concat", "-safe", "0", "-i", str(video_concat),
            "-i", str(merged_audio),
            "-c:v", "libx264", "-preset", "fast", "-crf", "23",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "128k",
            "-movflags", "+faststart",
            "-shortest",
            str(out_path),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(
                f"ffmpeg failed:\n{result.stderr[-2000:]}"
            )


def _make_silence(path: Path, duration: float, sample_rate: int = 22050) -> None:
    """Write a silent WAV file of the given duration."""
    import wave, struct, math
    n_frames = int(sample_rate * duration)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(b"\x00\x00" * n_frames)


def _merge_audio(
    ffmpeg: str,
    slides: list[SlideSpec],
    audio_dir: Path,
    silence_wav: Path,
    out_path: Path,
    tail_seconds: float,
) -> None:
    """Concatenate all slide WAVs (each followed by a tail silence) into one WAV."""
    inputs: list[str] = []
    for spec in slides:
        aud = audio_dir / f"slide_{spec.index:02d}.wav"
        inputs += ["-i", str(aud)]
    inputs += ["-i", str(silence_wav)]

    # Build filter_complex for concat
    # Each slide: its audio + silence repeated
    n = len(slides)
    silence_idx = n  # the silence input is at index n

    parts: list[str] = []
    for i in range(n):
        parts.append(f"[{i}:a]")
        parts.append(f"[{silence_idx}:a]")

    filter_complex = "".join(parts) + f"concat=n={2*n}:v=0:a=1[out]"

    cmd = [
        ffmpeg, "-y",
        *inputs,
        "-filter_complex", filter_complex,
        "-map", "[out]",
        str(out_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg audio merge failed:\n{result.stderr[-1500:]}")


# ── TSX canvas parser ──────────────────────────────────────────────────────

import re as _re


def slides_from_tsx(tsx_path: Path) -> list[SlideSpec]:
    """
    Return the SlideSpec list for a *.canvas.tsx presentation.

    Strategy:
      1. Read the TSX source.
      2. Scan for `title:` strings (quoted) to collect slide titles in order.
      3. Match each title against the known SLIDES list.
      4. Fall back to a generic SlideSpec with the raw title as narration
         for any unmatched titles.
    """
    source = tsx_path.read_text(encoding="utf-8")

    # Extract quoted title values in the order they appear.
    # Matches: title: "..." or title: '...'  but NOT subtitle: or CardHeader title=
    title_pattern = _re.compile(r'''(?<![a-zA-Z])title\s*:\s*["']([^"'\n]+)["']''')
    found_titles = [m.group(1) for m in title_pattern.finditer(source)]

    # De-duplicate while preserving order (same title may appear in
    # CardHeader, H1, etc. – we only want unique slide titles).
    seen: set[str] = set()
    unique_titles: list[str] = []
    for t in found_titles:
        if t not in seen:
            seen.add(t)
            unique_titles.append(t)

    # Build a lookup from the known SLIDES by (normalised) title.
    known: dict[str, SlideSpec] = {
        _normalise(s.title): s for s in SLIDES
    }

    result: list[SlideSpec] = []
    for i, title in enumerate(unique_titles, 1):
        key = _normalise(title)
        if key in known:
            result.append(known[key])
        else:
            # Generic fallback: speak the title itself.
            result.append(SlideSpec(
                index=i,
                title=title,
                tag="",
                bullets=[],
                narration=title,
            ))

    # If no titles found, return the full SLIDES list (safe default).
    return result if result else list(SLIDES)


def _normalise(text: str) -> str:
    """Lower-case, strip punctuation/whitespace for fuzzy title matching."""
    return _re.sub(r"[^a-z0-9]+", "", text.lower())


# ── MP3 export ─────────────────────────────────────────────────────────────

def wav_to_mp3(wav_path: Path, mp3_path: Path, bitrate: str = "128k") -> None:
    """Convert a WAV file to MP3 using the bundled ffmpeg."""
    ffmpeg = get_ffmpeg()
    cmd = [
        ffmpeg, "-y",
        "-i", str(wav_path),
        "-codec:a", "libmp3lame",
        "-b:a", bitrate,
        str(mp3_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"WAV->MP3 conversion failed:\n{result.stderr[-1000:]}")


def concat_mp3s(mp3_files: list[Path], out_path: Path) -> None:
    """Concatenate multiple MP3 files into one using ffmpeg concat demuxer."""
    ffmpeg = get_ffmpeg()
    import tempfile as _tempfile
    with _tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as flist:
        for p in mp3_files:
            flist.write(f"file '{p.resolve()}'\n")
        flist_path = flist.name

    cmd = [
        ffmpeg, "-y",
        "-f", "concat", "-safe", "0",
        "-i", flist_path,
        "-c", "copy",
        str(out_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    Path(flist_path).unlink(missing_ok=True)
    if result.returncode != 0:
        raise RuntimeError(f"MP3 concat failed:\n{result.stderr[-1000:]}")
