#!/usr/bin/env bash
# Usage:
#   ./run.sh <slides.canvas.tsx> [OPTIONS]   → narrated MP4
#   ./run.sh <slides.canvas.tsx> --engine kokoro
#   ./run.sh <slides.canvas.tsx> --output /path/to/out.mp4
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
    uv pip install $PYPI ollama pyttsx3 typer rich soundfile numpy click kokoro-onnx "misaki[en]" python-pptx pypdf imageio-ffmpeg pillow
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
Usage: ./run.sh <slides.canvas.tsx> [OPTIONS]
       ./run.sh COMMAND [ARGS...]

Generate a narrated MP4 video from a Canvas presentation:

  ./run.sh slides.canvas.tsx
      → output/<timestamp>_slides.mp4  (auto-timestamped)

  ./run.sh slides.canvas.tsx --engine kokoro
      Use the high-quality neural voice (recommended).

  ./run.sh slides.canvas.tsx --engine kokoro --voice bf_emma
      Choose a specific voice (see: ./run.sh list-voices --engine kokoro).

  ./run.sh slides.canvas.tsx --slides 1-5
      Render only slides 1 through 5.

  ./run.sh slides.canvas.tsx --output ~/Desktop/talk.mp4
      Save to a specific path instead of output/.

Other commands:
  ./run.sh speak "Hello world"
  ./run.sh speak-file notes.txt
  ./run.sh list-voices --engine kokoro
  ./run.sh download-models
EOF
    exit 0
fi

# ── *.tsx → narrated MP4 ──────────────────────────────────────────────────────
if [[ "$COMMAND" == *.tsx ]]; then
    if ! _has_flag "--output" "$@" && ! _has_flag "-o" "$@"; then
        mkdir -p "$OUTPUT_DIR"
        STEM="$(basename "${COMMAND%.canvas.tsx}")"
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
