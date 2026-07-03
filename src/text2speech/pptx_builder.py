"""Build a styled 16:9 PPTX from a JSON slide plan.

The public API is :func:`build_pptx`.  All other names are private helpers.
"""

from __future__ import annotations
import io
import warnings
from pathlib import Path

# ── Slide dimensions (16:9 widescreen, EMU units) ─────────────────────────────
from pptx.util import Inches, Pt, Emu
W = Inches(13.333)
H = Inches(7.5)

# ── Colour palette ─────────────────────────────────────────────────────────────
from pptx.dml.color import RGBColor

C_BG      = RGBColor(0xF8, 0xFA, 0xFC)   # very light blue-gray background
C_HEADER  = RGBColor(0x0F, 0x17, 0x2A)   # deep navy
C_ACCENT  = RGBColor(0x38, 0x82, 0xF6)   # blue accent
C_ACCENT2 = RGBColor(0x93, 0xC5, 0xFD)   # light blue (tag text in header)
C_TITLE   = RGBColor(0xFF, 0xFF, 0xFF)   # white title on header
C_TEXT    = RGBColor(0x1E, 0x29, 0x3B)   # dark body text
C_SUB     = RGBColor(0x47, 0x55, 0x69)   # gray sub-bullet text
C_DIM     = RGBColor(0x94, 0xA3, 0xB8)   # dim counter / rule
C_RULE    = RGBColor(0xE2, 0xE8, 0xF0)   # light rule line
C_IMGBG   = RGBColor(0xEF, 0xF6, 0xFF)   # image panel tint

# ── Layout constants (Inches) ──────────────────────────────────────────────────
HDR_H    = Inches(2.1)      # header height
ACCENT_W = Inches(0.07)     # left accent bar width
MARGIN_X = Inches(0.55)     # left margin
MARGIN_Y = Inches(0.3)      # top margin inside header
GUTTER   = Inches(0.25)     # gap between accent bar and bullet text
IMG_X    = Inches(8.9)      # image panel left edge
IMG_W    = Inches(4.1)      # image panel width
IMG_TOP  = Inches(2.25)     # image panel top
IMG_BTM  = Inches(7.1)      # image panel bottom


# ── Helpers ────────────────────────────────────────────────────────────────────

def _solid(shape, color: RGBColor) -> None:
    """Fill a shape with a solid colour and remove its border."""
    shape.fill.solid()
    shape.fill.fore_color.rgb = color
    shape.line.fill.background()


def _textbox(slide, left, top, width, height):
    """Add a transparent-background text box."""
    tb = slide.shapes.add_textbox(left, top, width, height)
    tb.fill.background()
    tb.line.fill.background()
    return tb


def _para(tf, text: str, size_pt: int, bold: bool = False,
          color: RGBColor = C_TEXT, space_before_pt: int = 0,
          align=None) -> None:
    """Append a paragraph to text-frame *tf*."""
    from pptx.enum.text import PP_ALIGN
    p = tf.add_paragraph()
    p.text = text
    p.space_before = Pt(space_before_pt)
    if align:
        p.alignment = align
    run = p.runs[0] if p.runs else p.add_run()
    run.font.size = Pt(size_pt)
    run.font.bold = bold
    run.font.color.rgb = color
    run.font.name = "Calibri"


def _set_bg(slide, color: RGBColor) -> None:
    bg = slide.background
    fill = bg.fill
    fill.solid()
    fill.fore_color.rgb = color


def _add_rect(slide, left, top, width, height, color: RGBColor):
    shape = slide.shapes.add_shape(1, left, top, width, height)  # 1 = RECTANGLE
    _solid(shape, color)
    return shape


def _extract_pdf_page_image(pdf_path: Path, page_num: int) -> bytes | None:
    """Return PNG bytes for the best figure on `page_num` of `pdf_path`.

    Strategy:
    1. Extract the largest embedded raster image from the page (fast, exact).
    2. If none found, render the whole page via pypdfium2 (handles vector graphics).
    3. Returns None if both approaches fail.
    """
    try:
        import pypdf
        from PIL import Image as PILImage
    except ImportError:
        return None

    warnings.filterwarnings("ignore", message=".*Lookup Table.*")
    reader = pypdf.PdfReader(str(pdf_path))
    idx = page_num - 1
    if idx < 0 or idx >= len(reader.pages):
        return None

    # ── attempt 1: largest embedded raster ───────────────────────────────────
    warnings.filterwarnings("ignore", message=".*Lookup Table.*")
    best_blob, best_area = None, 0
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            page_images = list(reader.pages[idx].images)
        for img_file in page_images:
            try:
                pil = PILImage.open(io.BytesIO(img_file.data))
                area = pil.width * pil.height
                if area > best_area and area > 10_000:
                    best_area, best_blob = area, img_file.data
            except Exception:
                continue
    except Exception:
        pass

    if best_blob is not None:
        try:
            buf = io.BytesIO()
            PILImage.open(io.BytesIO(best_blob)).convert("RGB").save(buf, format="PNG")
            return buf.getvalue()
        except Exception:
            pass

    # ── attempt 2: render full page with pypdfium2 (vector-safe) ─────────────
    try:
        import pypdfium2 as pdfium  # type: ignore
        doc = pdfium.PdfDocument(str(pdf_path))
        page = doc[idx]
        bitmap = page.render(scale=2.0)   # 144 dpi — sharp enough for slides
        pil = bitmap.to_pil()
        buf = io.BytesIO()
        pil.convert("RGB").save(buf, format="PNG")
        return buf.getvalue()
    except Exception:
        pass

    return None


# ── Main slide builder ─────────────────────────────────────────────────────────

def _render_slide(prs, slide_data: dict, idx: int, total: int,
                  pdf_path: Path | None) -> None:
    from pptx.enum.text import PP_ALIGN
    from PIL import Image as PILImage

    blank   = prs.slide_layouts[6]   # truly blank layout
    slide   = prs.slides.add_slide(blank)

    title_text  = slide_data.get("title", f"Slide {idx}")
    tag_text    = (slide_data.get("tag") or "").upper()
    bullets     = slide_data.get("bullets", [])
    narration   = slide_data.get("narration", "")
    image_page  = slide_data.get("image_page")

    is_title_slide = (idx == 1)

    # ── background ───────────────────────────────────────────────────────────
    _set_bg(slide, C_BG)

    if is_title_slide:
        _render_title_slide(slide, title_text, tag_text, bullets,
                             narration, idx, total)
    else:
        _render_content_slide(slide, title_text, tag_text, bullets,
                               narration, idx, total, image_page, pdf_path)


def _render_title_slide(slide, title, tag, bullets, narration, idx, total):
    from pptx.enum.text import PP_ALIGN

    # full-height dark panel on the left 55%
    panel_w = int(W * 0.55)
    _add_rect(slide, 0, 0, panel_w, H, C_HEADER)

    # accent strip at bottom of panel
    _add_rect(slide, 0, H - Inches(0.12), panel_w, Inches(0.12), C_ACCENT)

    # title text
    tb = _textbox(slide, MARGIN_X, Inches(1.8), panel_w - MARGIN_X - Inches(0.3), Inches(2.4))
    tb.name = "slide_title"
    tf = tb.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.text = title
    run = p.runs[0]
    run.font.size = Pt(44)
    run.font.bold = True
    run.font.color.rgb = C_TITLE
    run.font.name = "Calibri"

    # tag / subtitle
    if tag or bullets:
        sub_text = tag if tag else (bullets[0] if bullets else "")
        tb2 = _textbox(slide, MARGIN_X, Inches(4.4), panel_w - MARGIN_X - Inches(0.3), Inches(0.6))
        tf2 = tb2.text_frame
        p2  = tf2.paragraphs[0]
        p2.text = sub_text
        run2 = p2.runs[0]
        run2.font.size = Pt(18)
        run2.font.color.rgb = C_ACCENT2
        run2.font.name = "Calibri"

    # bullet list on left panel (remaining bullets)
    show_bullets = bullets[1:] if (tag or bullets) else bullets
    if show_bullets:
        tb3 = _textbox(slide, MARGIN_X, Inches(5.2), panel_w - MARGIN_X - Inches(0.3), Inches(1.8))
        tf3 = tb3.text_frame
        tf3.word_wrap = True
        for j, b in enumerate(show_bullets[:5]):
            _para(tf3, ("• " if not b.startswith("  ") else "  ◦ ") + b.lstrip(),
                  16, color=RGBColor(0xCB, 0xD5, 0xE1),
                  space_before_pt=(4 if j > 0 else 0))

    # decorative right side — light accent column
    right_x = panel_w + Inches(0.15)
    _add_rect(slide, right_x, Inches(1.5), Inches(0.06), Inches(4.5), C_ACCENT)

    # slide counter bottom right
    tb4 = _textbox(slide, W - Inches(1.5), H - Inches(0.45), Inches(1.3), Inches(0.35))
    tf4 = tb4.text_frame
    _para(tf4, f"{idx} / {total}", 13, color=C_DIM, align=None)

    # narration in notes
    if narration:
        slide.notes_slide.notes_text_frame.text = narration


def _render_content_slide(slide, title, tag, bullets, narration,
                           idx, total, image_page, pdf_path):
    from pptx.enum.text import PP_ALIGN

    # ── header bar ───────────────────────────────────────────────────────────
    _add_rect(slide, 0, 0, W, HDR_H, C_HEADER)
    # accent line at bottom of header
    _add_rect(slide, 0, HDR_H - Inches(0.07), W, Inches(0.07), C_ACCENT)

    # tag label (small, light blue)
    if tag:
        tb_tag = _textbox(slide, MARGIN_X, MARGIN_Y, W - MARGIN_X * 2, Inches(0.35))
        tf_tag = tb_tag.text_frame
        _para(tf_tag, tag, 13, color=C_ACCENT2)

    # title
    title_top = MARGIN_Y + (Inches(0.32) if tag else 0)
    title_h   = HDR_H - title_top - Inches(0.2)
    tb_title = _textbox(slide, MARGIN_X, title_top, W - MARGIN_X * 2 - Inches(1.4), title_h)
    tb_title.name = "slide_title"
    tb_title.text_frame.word_wrap = True
    p = tb_title.text_frame.paragraphs[0]
    p.text = title

    # auto-shrink title font if long
    font_sz = 36 if len(title) < 40 else (28 if len(title) < 60 else 22)
    run = p.runs[0]
    run.font.size   = Pt(font_sz)
    run.font.bold   = True
    run.font.color.rgb = C_TITLE
    run.font.name   = "Calibri"

    # slide counter — top right of header
    tb_cnt = _textbox(slide, W - Inches(1.6), MARGIN_Y + Inches(0.6),
                      Inches(1.4), Inches(0.4))
    tf_cnt = tb_cnt.text_frame
    _para(tf_cnt, f"{idx} / {total}", 14, color=C_DIM)

    # progress bar at very bottom
    prog_frac = idx / total
    _add_rect(slide, 0, H - Inches(0.08), W, Inches(0.08), C_RULE)
    _add_rect(slide, 0, H - Inches(0.08), int(W * prog_frac), Inches(0.08), C_ACCENT)

    # ── content area layout ──────────────────────────────────────────────────
    content_top = HDR_H + Inches(0.22)
    content_bot = H - Inches(0.2)
    content_h   = content_bot - content_top

    # try to fetch image
    img_blob = None
    if image_page and pdf_path:
        img_blob = _extract_pdf_page_image(pdf_path, image_page)

    # left accent bar
    _add_rect(slide, MARGIN_X - Inches(0.18), content_top,
              ACCENT_W, content_h, C_ACCENT)

    # bullet column width depends on whether there is an image
    if img_blob:
        bullet_w = IMG_X - MARGIN_X - GUTTER - Inches(0.15)
    else:
        bullet_w = W - MARGIN_X - Inches(0.4)

    bullet_x = MARGIN_X + GUTTER

    # ── bullets ──────────────────────────────────────────────────────────────
    if bullets:
        tb_b = _textbox(slide, bullet_x, content_top, bullet_w, content_h)
        tf_b = tb_b.text_frame
        tf_b.word_wrap = True

        n_bullets = len([b for b in bullets if b.strip()])
        base_sz   = 22 if n_bullets <= 4 else (19 if n_bullets <= 6 else 16)

        for j, bullet in enumerate(bullets):
            is_sub = bullet.startswith("  ")
            text   = bullet.lstrip()
            if not text:
                if j > 0:
                    _para(tf_b, "", base_sz - 4, space_before_pt=2)
                continue
            prefix = "  ◦ " if is_sub else "• "
            color  = C_SUB if is_sub else C_TEXT
            sz     = base_sz - 3 if is_sub else base_sz
            _para(tf_b, prefix + text, sz, color=color,
                  space_before_pt=(6 if j > 0 and not is_sub else 2))

    # ── image ─────────────────────────────────────────────────────────────────
    if img_blob:
        try:
            from PIL import Image as PILImage
            pil = PILImage.open(io.BytesIO(img_blob))
            iw, ih = pil.size

            # image panel bounds
            panel_h = int(content_bot - IMG_TOP)
            panel_w = int(IMG_W)

            # scale to fit panel preserving aspect ratio
            scale = min(panel_w / iw, panel_h / ih, 1.0)
            nw = max(1, int(iw * scale))
            nh = max(1, int(ih * scale))

            # tinted background for image area
            _add_rect(slide, IMG_X - Inches(0.1), IMG_TOP - Inches(0.1),
                      IMG_W + Inches(0.2), Inches(panel_h / 914400 + 0.2), C_IMGBG)

            # center within panel
            ox = IMG_X + (IMG_W - nw) // 2
            oy = IMG_TOP + (panel_h - nh) // 2

            slide.shapes.add_picture(io.BytesIO(img_blob), ox, oy, nw, nh)
        except Exception:
            pass

    # ── narration in notes ───────────────────────────────────────────────────
    if narration:
        slide.notes_slide.notes_text_frame.text = narration


def build_pptx(plan: list[dict], out_path: Path,
               pdf_path: Path | None = None) -> None:
    from pptx import Presentation

    prs = Presentation()
    prs.slide_width  = W
    prs.slide_height = H

    total = len(plan)
    for i, slide_data in enumerate(plan, 1):
        _render_slide(prs, slide_data, i, total, pdf_path)

    prs.save(str(out_path))
    print(f"Saved: {out_path}  ({total} slides)")


