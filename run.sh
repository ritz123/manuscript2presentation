#!/usr/bin/env bash
# Usage:
#   ./run.sh <input> --paper [OPTIONS]   → PDF manuscript → LLM → PPTX → MP4
#   ./run.sh <input> --slide [OPTIONS]   → slide deck (PPTX/PDF/YAML/TSX) → MP4
#   ./run.sh speak "Hello world"
#   ./run.sh list-voices --engine kokoro

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Resolve the first argument to an absolute path BEFORE cd changes the CWD.
# This ensures relative paths like ./paper.pdf work regardless of where the
# script is invoked from.
if [[ -n "${1:-}" && "${1:-}" != --* && -e "$1" ]]; then
    _ABS="$(cd "$(dirname "$1")" && pwd)/$(basename "$1")"
    set -- "$_ABS" "${@:2}"
fi

cd "$SCRIPT_DIR"

VENV="$SCRIPT_DIR/.venv"
T2S="$VENV/bin/t2s"
PYPI="--default-index https://pypi.org/simple"
OUTPUT_DIR="$SCRIPT_DIR/output"

# ── bootstrap ─────────────────────────────────────────────────────────────────
# Detect a stale venv: exists but its shebang points to a different directory
# (happens after the project folder is renamed or moved).
_venv_stale() {
    [[ ! -x "$T2S" ]] && return 0
    head -1 "$T2S" 2>/dev/null | grep -qF "$VENV" || return 0
    return 1
}

if _venv_stale; then
    if [[ -d "$VENV" ]]; then
        echo "Detected stale virtual environment (project was renamed/moved). Recreating..."
        rm -rf "$VENV"
    else
        echo "Setting up environment (first run)..."
    fi
    uv venv "$VENV"
    uv pip install --python "$VENV/bin/python" $PYPI ollama pyttsx3 typer rich soundfile numpy click kokoro-onnx "misaki[en]" python-pptx pypdf pypdfium2 imageio-ffmpeg pillow pyyaml duckduckgo-search requests
    uv pip install --python "$VENV/bin/python" $PYPI -e .
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

─── --review  (PDF manuscript → structured academic review .md) ────────────────
  Uses a local Ollama LLM with web_search + fetch_url tools to produce a
  structured review (summary, strengths, citations, score, recommendation).

  ./run.sh paper.pdf --review
  ./run.sh paper.pdf --review --model qwen2.5:72b
  ./run.sh paper.pdf --review --no-web          # offline, skip citation lookup
  ./run.sh paper.pdf --review --output rev.md

─── Other commands ─────────────────────────────────────────────────────────────
  ./run.sh speak "Hello world"
  ./run.sh speak-file notes.txt
  ./run.sh list-voices --engine kokoro
  ./run.sh download-models
EOF
    exit 0
fi

# ── --review → structured academic review with web tools ─────────────────────
if _has_flag "--review" "$@"; then
    ARGS=()
    for arg in "$@"; do [[ "$arg" != "--review" ]] && ARGS+=("$arg"); done
    exec "$T2S" paper-review "${ARGS[@]}"
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
