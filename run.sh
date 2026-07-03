#!/usr/bin/env bash
# Usage:
#   ./run.sh <input> --paper [OPTIONS]   → PDF manuscript → LLM → PPTX → MP4
#   ./run.sh <input> --slide [OPTIONS]   → slide deck (PPTX/PDF/YAML/TSX) → MP4
#   ./run.sh speak "Hello world"
#   ./run.sh list-voices --engine kokoro

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

VENV="$SCRIPT_DIR/.venv"
T2S="$VENV/bin/t2s"
PYPI="--default-index https://pypi.org/simple"
OUTPUT_DIR="$SCRIPT_DIR/output"

# ── bootstrap ─────────────────────────────────────────────────────────────────

if [[ ! -x "$T2S" ]]; then
    echo "Setting up environment (first run)..."
    uv pip install $PYPI ollama pyttsx3 typer rich soundfile numpy click kokoro-onnx "misaki[en]" python-pptx pypdf pypdfium2 imageio-ffmpeg pillow pyyaml
    uv pip install $PYPI -e .
    echo ""
    echo "Ready. Kokoro model files (~300 MB) will be downloaded on first speak."
    echo ""
fi

COMMAND="${1:-}"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"

_has_flag() {
    local flag="$1"; shift
    for arg in "$@"; do [[ "$arg" == "$flag" ]] && return 0; done
    return 1
}

# ── help ──────────────────────────────────────────────────────────────────────
if [[ "$COMMAND" == "--help" || "$COMMAND" == "-h" || -z "$COMMAND" ]]; then
    cat <<'EOF'
Usage: ./run.sh <input> --paper|--slide [OPTIONS]
       ./run.sh COMMAND [ARGS...]

─── --paper  (PDF manuscript → LLM → PPTX → MP4) ──────────────────────────────
  Uses a local Ollama LLM to plan slides, builds a styled PPTX, and renders
  a narrated MP4 — all in one shot.

  ./run.sh paper.pdf --paper
  ./run.sh paper.pdf --paper --model llama3.2 --n-slides 10
  ./run.sh paper.pdf --paper --engine kokoro --voice bm_george
  ./run.sh paper.pdf --paper --no-video   # PPTX only, skip video

─── --slide  (existing slide deck → MP4) ───────────────────────────────────────
  Renders a slide deck directly — one slide at a time — with voice-over.
  Accepted formats: .pptx  .pdf  .yaml  .tsx

  ./run.sh slides.pptx --slide
  ./run.sh slides.pptx --slide --engine kokoro --voice bm_george
  ./run.sh slides.pptx --slide --slides 1-5
  ./run.sh slides.pptx --slide --output ~/Desktop/talk.mp4

  Note: --slide is the default for .pptx, .yaml, and .tsx files.
        For .pdf, use --paper or --slide explicitly.

─── Other commands ─────────────────────────────────────────────────────────────
  ./run.sh speak "Hello world"
  ./run.sh speak-file notes.txt
  ./run.sh list-voices --engine kokoro
  ./run.sh download-models
EOF
    exit 0
fi

# ── --paper → full LLM pipeline (manuscript → slides → video) ────────────────
if _has_flag "--paper" "$@"; then
    ARGS=()
    for arg in "$@"; do [[ "$arg" != "--paper" ]] && ARGS+=("$arg"); done
    exec "$T2S" paper-to-slides "${ARGS[@]}"
fi

# ── slide decks → narrated MP4 ───────────────────────────────────────────────
# --slide is explicit; also implicit for .pptx / .yaml / .tsx
# For .pdf with no flag, require --slide to avoid ambiguity.
IS_SLIDE_DECK=false
if _has_flag "--slide" "$@"; then
    IS_SLIDE_DECK=true
elif [[ "$COMMAND" == *.yaml || "$COMMAND" == *.yml || \
        "$COMMAND" == *.tsx  || "$COMMAND" == *.pptx ]]; then
    IS_SLIDE_DECK=true
fi

if [[ "$IS_SLIDE_DECK" == true ]]; then
    # Strip --slide before forwarding
    ARGS=()
    for arg in "$@"; do [[ "$arg" != "--slide" ]] && ARGS+=("$arg"); done
    if ! _has_flag "--output" "${ARGS[@]}" && ! _has_flag "-o" "${ARGS[@]}"; then
        mkdir -p "$OUTPUT_DIR"
        STEM="$(basename "$COMMAND")"
        STEM="${STEM%.canvas.tsx}"; STEM="${STEM%.tsx}"
        STEM="${STEM%.yaml}"; STEM="${STEM%.yml}"
        STEM="${STEM%.pptx}"; STEM="${STEM%.pdf}"
        AUTO_SAVE="$OUTPUT_DIR/${TIMESTAMP}_${STEM}.mp4"
        echo "Video → $AUTO_SAVE"
        exec "$T2S" canvas-video "${ARGS[@]}" --output "$AUTO_SAVE"
    fi
    exec "$T2S" canvas-video "${ARGS[@]}"
fi

# ── PDF without a mode flag → tell the user to be explicit ───────────────────
if [[ "$COMMAND" == *.pdf ]]; then
    echo "Error: PDF input requires --paper or --slide."
    echo ""
    echo "  --paper  Manuscript (prose document) → LLM plans the slides"
    echo "  --slide  Already a slide-per-page PDF → render directly"
    echo ""
    echo "Run ./run.sh --help for full usage."
    exit 1
fi

# ── other commands ────────────────────────────────────────────────────────────
case "$COMMAND" in
    speak|speak-file|speak-slides)
        if ! _has_flag "--save" "$@" && ! _has_flag "-o" "$@"; then
            mkdir -p "$OUTPUT_DIR"
            exec "$T2S" "$@" --save "$OUTPUT_DIR/${TIMESTAMP}_${COMMAND//-/_}.wav"
        fi
        ;;
    interactive)
        if ! _has_flag "--save-dir" "$@"; then
            AUTO_DIR="$OUTPUT_DIR/${TIMESTAMP}_interactive"
            mkdir -p "$AUTO_DIR"
            exec "$T2S" "$@" --save-dir "$AUTO_DIR"
        fi
        ;;
esac

exec "$T2S" "$@"
