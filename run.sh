#!/usr/bin/env bash
# Usage:
#   ./run.sh <slides.pptx> [OPTIONS]          → narrated MP4 (from existing slides)
#   ./run.sh <paper.pdf> --plan [OPTIONS]      → PDF → LLM → PPTX → MP4
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
    uv pip install $PYPI ollama pyttsx3 typer rich soundfile numpy click kokoro-onnx "misaki[en]" python-pptx pypdf imageio-ffmpeg pillow pyyaml
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
Usage: ./run.sh <input> [OPTIONS]
       ./run.sh COMMAND [ARGS...]

─── Narrated video from a slide deck ──────────────────────────────────────────
  ./run.sh slides.pptx
      → output/<timestamp>_slides.mp4  (auto-timestamped)

  ./run.sh slides.pptx --engine kokoro --voice bm_george
  ./run.sh slides.pptx --slides 1-5
  ./run.sh slides.pptx --output ~/Desktop/talk.mp4

  Same syntax works for:  .pdf  .yaml  .tsx

─── PDF manuscript → slides → video (full automation) ─────────────────────────
  ./run.sh paper.pdf --plan
      Uses Ollama LLM to plan slides, builds a styled PPTX, renders MP4.

  ./run.sh paper.pdf --plan --model llama3.2 --n-slides 10
  ./run.sh paper.pdf --plan --engine kokoro --voice bm_george --video

─── Other commands ─────────────────────────────────────────────────────────────
  ./run.sh speak "Hello world"
  ./run.sh speak-file notes.txt
  ./run.sh list-voices --engine kokoro
  ./run.sh download-models
EOF
    exit 0
fi

# ── PDF + --plan → full LLM pipeline ─────────────────────────────────────────
if [[ "$COMMAND" == *.pdf ]] && _has_flag "--plan" "$@"; then
    # Strip --plan from args before passing to paper-to-slides
    ARGS=()
    for arg in "${@:2}"; do [[ "$arg" != "--plan" ]] && ARGS+=("$arg"); done
    exec "$T2S" paper-to-slides "$COMMAND" "${ARGS[@]}"
fi

# ── slide decks → narrated MP4 ───────────────────────────────────────────────
if [[ "$COMMAND" == *.yaml || "$COMMAND" == *.yml || "$COMMAND" == *.tsx || \
      "$COMMAND" == *.pptx || "$COMMAND" == *.pdf ]]; then
    if ! _has_flag "--output" "$@" && ! _has_flag "-o" "$@"; then
        mkdir -p "$OUTPUT_DIR"
        STEM="$(basename "$COMMAND")"
        STEM="${STEM%.canvas.tsx}"; STEM="${STEM%.tsx}"
        STEM="${STEM%.yaml}"; STEM="${STEM%.yml}"
        STEM="${STEM%.pptx}"; STEM="${STEM%.pdf}"
        AUTO_SAVE="$OUTPUT_DIR/${TIMESTAMP}_${STEM}.mp4"
        echo "Video → $AUTO_SAVE"
        exec "$T2S" canvas-video "$@" --output "$AUTO_SAVE"
    fi
    exec "$T2S" canvas-video "$@"
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
