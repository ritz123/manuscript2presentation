"""
Render slide decks (.pptx, .pdf, .yaml, .tsx) into a narrated video or MP3.

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

# ── colour palette (light theme) ──────────────────────────────────────────
BG        = (252, 252, 255)    # off-white slide background
CHROME    = (235, 237, 243)    # nav bar / chrome areas
ACCENT    = (37,  99, 235)     # blue accent (darker for contrast on light bg)
TEXT_PRI  = (18,  18,  28)     # primary text
TEXT_SEC  = (80,  80, 100)     # secondary text
STROKE    = (200, 200, 210)    # dividers / borders
WHITE     = (255, 255, 255)    # pure white (card backgrounds, etc.)
DIM       = (100, 100, 120)    # de-emphasised text

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
    images: list[bytes] = field(default_factory=list)         # raw PNG/JPEG blobs


# Slides are loaded at runtime from an external file (.pptx, .pdf, .yaml, .tsx).
# See slides_from_presentation(), slides_from_yaml(), slides_from_tsx() below.




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


def _fit_text(
    text: str,
    font: "ImageFont.FreeTypeFont",
    max_w: int,
    max_lines: int,
) -> list[str]:
    """
    Return at most *max_lines* wrapped lines for *text*.
    If the text would require more lines, the last kept line gets '...' appended.
    """
    lines = _wrap(text, font, max_w)
    if len(lines) <= max_lines:
        return lines
    truncated = lines[:max_lines]
    # shorten the last kept line to fit the trailing ellipsis
    last = truncated[-1]
    dummy = Image.new("RGB", (1, 1))
    draw  = ImageDraw.Draw(dummy)
    while last and draw.textlength(last + "...", font=font) > max_w:
        last = last.rsplit(" ", 1)[0]
    truncated[-1] = (last + "...").strip()
    return truncated


def _measure_bullets(
    items: list[str],
    f_body: "ImageFont.FreeTypeFont",
    col_w: int,
    line_h: int,
    max_lines: int = 2,
) -> int:
    """Return total pixel height needed to draw *items* in a column of *col_w*."""
    total = 0
    for item in items:
        raw = _safe(item)
        if not raw.strip():
            total += line_h // 2
            continue
        is_indented = raw.startswith("  ") or raw.startswith("    ")
        indent = 28 if is_indented else 0
        text = raw.lstrip() if is_indented else raw
        if is_indented and text.startswith("- "):
            text = text[2:]
        lines = _fit_text(text, f_body, col_w - indent - 4, max_lines)
        total += line_h * len(lines)
    return total


def _draw_bullet_column(
    draw: "ImageDraw.ImageDraw",
    items: list[str],
    f_body: "ImageFont.FreeTypeFont",
    x0: int,
    y0: int,
    col_w: int,
    bottom: int,
    line_h: int,
    max_lines: int = 2,
) -> None:
    """Draw bullet items in a single column, strictly stopping at *bottom*."""
    y = y0
    for item in items:
        if y + line_h > bottom:
            break
        raw = _safe(item)
        if not raw.strip():
            y += line_h // 2
            continue

        is_indented = raw.startswith("  ") or raw.startswith("    ")
        indent = 0
        text = raw

        if is_indented:
            indent = 28
            text = raw.lstrip()
            if text.startswith("- "):
                text = text[2:]
                cy = y + line_h // 2 - 3
                draw.ellipse([x0 + indent - 14, cy, x0 + indent - 6, cy + 8], fill=ACCENT)
            col = DIM
        else:
            col = TEXT_PRI

        lines = _fit_text(text, f_body, col_w - indent - 4, max_lines)
        for ln in lines:
            if y + line_h > bottom:
                break
            draw.text((x0 + indent, y), ln, font=f_body, fill=col)
            y += line_h


def render_slide(spec: SlideSpec, out_path: Path, total: int = 0) -> None:
    """Render *spec* as a 1280×720 PNG saved to *out_path*."""
    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)

    MARGIN = 56
    NAV_H  = 50   # thin nav — no footer, maximise content space
    BOTTOM = H - 14
    max_w  = W - 2 * MARGIN

    # ── nav bar ─────────────────────────────────────────────────────────────
    draw.rectangle([0, 0, W, NAV_H], fill=CHROME)
    draw.line([0, NAV_H, W, NAV_H], fill=STROKE, width=1)
    f_nav = _font(20)
    label = _safe(spec.tag.upper()) if spec.tag else ""
    draw.text((MARGIN, (NAV_H - 20) // 2), label, font=f_nav, fill=DIM)
    n = total if total > 0 else spec.index
    counter = f"{spec.index} / {n}"
    cw = int(draw.textlength(counter, font=f_nav))
    draw.text((W - MARGIN - cw, (NAV_H - 20) // 2), counter, font=f_nav, fill=DIM)
    # progress bar flush with bottom of nav
    prog_filled = int(max_w * spec.index / n)
    draw.rectangle([MARGIN, NAV_H - 4, W - MARGIN, NAV_H], fill=STROKE)
    draw.rectangle([MARGIN, NAV_H - 4, MARGIN + prog_filled, NAV_H], fill=ACCENT)

    y = NAV_H + 18

    # ── section tag ─────────────────────────────────────────────────────────
    f_tag = _font(22)
    if spec.tag:
        draw.text((MARGIN, y), _safe(spec.tag), font=f_tag, fill=ACCENT)
        y += 30

    # ── title — auto-scale so it always fits in ≤ 2 lines ──────────────────
    title_text = _safe(spec.title)
    f_title = _font(72, bold=True)
    title_lines = _wrap(title_text, f_title, max_w)
    if len(title_lines) > 2:
        f_title = _font(56, bold=True)
        title_lines = _wrap(title_text, f_title, max_w)
    if len(title_lines) > 2:
        f_title = _font(44, bold=True)
        title_lines = _wrap(title_text, f_title, max_w)

    title_step = int(f_title.size * 1.18)
    for line in title_lines[:2]:
        draw.text((MARGIN, y), line, font=f_title, fill=TEXT_PRI)
        y += title_step
    y += 10

    # ── divider ─────────────────────────────────────────────────────────────
    draw.line([MARGIN, y, W - MARGIN, y], fill=STROKE, width=1)
    y += 16

    body_top = y
    body_h   = BOTTOM - body_top

    # ── quote (if any) ───────────────────────────────────────────────────────
    if spec.quote:
        f_q = _font(30)
        q_lines = _wrap(f'"{_safe(spec.quote)}"', f_q, max_w - 20)
        bar_top = y
        for ql in q_lines[:3]:
            draw.text((MARGIN + 18, y), ql, font=f_q, fill=DIM)
            y += 38
        draw.rectangle([MARGIN, bar_top, MARGIN + 4, y], fill=ACCENT)
        y += 10
        body_top = y
        body_h = BOTTOM - body_top

    # ── decide layout: images present? ──────────────────────────────────────
    has_images  = bool(spec.images)
    has_bullets = bool(spec.bullets or spec.right_bullets)
    IMG_GAP     = 24   # gap between bullet column and image panel

    if has_images and has_bullets:
        # bullets on left ~55%, images on right ~42%
        bullet_col_w = int(max_w * 0.55)
        img_panel_x  = MARGIN + bullet_col_w + IMG_GAP
        img_panel_w  = W - MARGIN - img_panel_x
    elif has_images:
        # no bullets — images fill the whole content area
        bullet_col_w = 0
        img_panel_x  = MARGIN
        img_panel_w  = max_w
    else:
        bullet_col_w = max_w
        img_panel_x  = 0
        img_panel_w  = 0

    # ── bullets — adaptive font + two-column when needed ────────────────────
    if has_bullets:
        all_b   = spec.bullets
        right_b = spec.right_bullets

        if right_b:
            left_items, right_items = all_b, right_b
            two_col = True
        elif has_images:
            # with an image panel, never auto-split into two bullet columns
            left_items, right_items = all_b, []
            two_col = False
        elif len(all_b) > 6:
            mid = (len(all_b) + 1) // 2
            left_items, right_items = all_b[:mid], all_b[mid:]
            two_col = True
        else:
            left_items, right_items = all_b, []
            two_col = False

        col_gap = 32
        n_rows  = max(len(left_items), len(right_items)) if two_col else len(left_items)
        max_lines_per_bullet = 1 if n_rows > 8 else 2

        for bsz in [40, 34, 29, 25, 22, 19]:
            lh   = int(bsz * 1.42)
            cw   = (bullet_col_w - col_gap) // 2 if two_col else bullet_col_w
            f_b  = _font(bsz)
            lh_m = _measure_bullets(left_items,  f_b, cw, lh, max_lines_per_bullet)
            rh_m = _measure_bullets(right_items, f_b, cw, lh, max_lines_per_bullet) if right_items else 0
            if max(lh_m, rh_m) <= body_h:
                break

        f_body = _font(bsz)
        lh     = int(bsz * 1.42)
        col_w  = (bullet_col_w - col_gap) // 2 if two_col else bullet_col_w

        accent_bar_x = MARGIN - 16
        est_h = _measure_bullets(left_items, f_body, col_w, lh)
        if right_items:
            est_h = max(est_h, _measure_bullets(right_items, f_body, col_w, lh))
        draw.rectangle(
            [accent_bar_x, body_top, accent_bar_x + 3, min(body_top + est_h, BOTTOM)],
            fill=ACCENT,
        )

        _draw_bullet_column(draw, left_items,  f_body, MARGIN,              body_top, col_w, BOTTOM, lh, max_lines_per_bullet)
        if two_col:
            _draw_bullet_column(draw, right_items, f_body, MARGIN + col_w + col_gap, body_top, col_w, BOTTOM, lh, max_lines_per_bullet)

    # ── images ───────────────────────────────────────────────────────────────
    if has_images:
        import io as _io
        panel_h     = BOTTOM - body_top
        n_imgs      = len(spec.images)
        slot_h      = (panel_h - IMG_GAP * (n_imgs - 1)) // n_imgs

        iy = body_top
        for blob in spec.images:
            try:
                src = Image.open(_io.BytesIO(blob)).convert("RGBA")
            except Exception:
                iy += slot_h + IMG_GAP
                continue

            # scale to fit slot while preserving aspect ratio
            iw, ih = src.size
            scale  = min(img_panel_w / iw, slot_h / ih, 1.0)
            nw     = max(1, int(iw * scale))
            nh     = max(1, int(ih * scale))
            src    = src.resize((nw, nh), Image.LANCZOS)

            # center horizontally within the panel
            ox = img_panel_x + (img_panel_w - nw) // 2
            oy = iy + (slot_h - nh) // 2

            # paste with alpha mask so PNGs with transparency work
            img.paste(src, (ox, oy), mask=src.split()[3] if src.mode == "RGBA" else None)

            iy += slot_h + IMG_GAP

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


# ── PPTX / PDF loader ──────────────────────────────────────────────────────

def slides_from_presentation(path: Path) -> list[SlideSpec]:
    """
    Load slides from a *.pptx or *.pdf file and convert them to SlideSpec objects.

    - Slide title      → SlideSpec.title
    - Body text lines  → SlideSpec.bullets  (one line per bullet)
    - Presenter notes  → SlideSpec.narration  (falls back to body text if empty)
    - Tag              → "SLIDE N" (overridable by adding a tag comment in notes,
                         see below)

    Optional: add a line ``TAG: My Section Label`` anywhere in the presenter
    notes to set a custom section tag shown above the title.
    """
    from text2speech.slides import read_slides

    raw_slides = read_slides(path)
    specs: list[SlideSpec] = []

    for s in raw_slides:
        # Parse optional TAG: directive out of notes
        tag = f"SLIDE {s.index}"
        notes_clean = s.notes
        if notes_clean:
            tag_lines = [ln for ln in notes_clean.splitlines() if ln.strip().upper().startswith("TAG:")]
            if tag_lines:
                tag = tag_lines[0].split(":", 1)[1].strip()
                # Remove the TAG line from narration
                notes_clean = "\n".join(
                    ln for ln in notes_clean.splitlines()
                    if not ln.strip().upper().startswith("TAG:")
                ).strip()

        # Build bullets from body lines (preserve indentation for sub-items)
        bullets: list[str] = []
        for line in s.body.splitlines():
            stripped = line.strip()
            if not stripped:
                bullets.append("")
                continue
            # Detect indented sub-items (leading spaces/tabs in original)
            if line.startswith(("  ", "\t")):
                bullets.append(f"  {stripped}")
            else:
                bullets.append(stripped)

        # Narration: use presenter notes if present, else fall back to body text
        narration = notes_clean or s.spoken_text(include_notes=False)

        specs.append(SlideSpec(
            index     = s.index,
            title     = s.title or f"Slide {s.index}",
            tag       = tag,
            bullets   = bullets,
            narration = narration,
            images    = s.images,
        ))

    return specs


# ── YAML slide loader ──────────────────────────────────────────────────────

def slides_from_yaml(yaml_path: Path) -> list[SlideSpec]:
    """
    Load slides from a YAML file.

    Expected format::

        title: "My Presentation"   # optional, used for reference only
        slides:
          - title: "Slide Title"
            tag: "SECTION 1"       # optional small label above the title
            bullets:               # shown on screen (keep short!)
              - "Key point one"
              - "Key point two"
              - "  - indented sub-point"   # indent with 2+ spaces
            right_bullets:         # optional second column
              - "Column 2 item"
            quote: "Optional pull-quote"   # optional
            narration: |           # spoken aloud (not shown on slide)
              Full explanation goes here.
              Can span multiple lines.
    """
    import yaml  # lazy import — not needed at module load time

    raw = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))

    if isinstance(raw, list):
        slide_list = raw                      # bare list of slide dicts
    elif isinstance(raw, dict):
        slide_list = raw.get("slides", [])    # {title: ..., slides: [...]}
    else:
        raise ValueError(f"Unexpected YAML structure in {yaml_path}")

    specs: list[SlideSpec] = []
    for i, item in enumerate(slide_list, 1):
        specs.append(SlideSpec(
            index       = item.get("index", i),
            title       = str(item.get("title", f"Slide {i}")),
            tag         = str(item.get("tag", "")),
            bullets     = [str(b) for b in item.get("bullets", [])],
            right_bullets = [str(b) for b in item.get("right_bullets", [])],
            quote       = str(item.get("quote", "")),
            narration   = str(item.get("narration", item.get("title", ""))),
        ))
    return specs


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
