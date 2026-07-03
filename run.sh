#!/usr/bin/env bash
# Run script for text2speech
#
# Usage:  ./run.sh COMMAND [ARGS...]
#
# Speech output is automatically saved to ./output/<timestamp>.wav
# (unless --save / --save-dir is already specified, or the command doesn't produce audio).
#
# Examples:
#   ./run.sh speak "Hello world"
#     → plays audio AND saves to ./output/20260703_125301_speak.wav
#
#   ./run.sh speak "Hello" --voice bf_emma --save my_file.wav
#     → saves to my_file.wav (your path takes precedence)
#
#   ./run.sh interactive --model llama3.2
#     → saves each reply under ./output/20260703_125301_interactive/reply_0000.wav ...
#
#   ./run.sh speak-file notes.txt --summarize --model llama3.2
#   ./run.sh list-voices --engine kokoro
#   ./run.sh download-models

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

VENV="$SCRIPT_DIR/.venv"
T2S="$VENV/bin/t2s"
PYPI="--default-index https://pypi.org/simple"
OUTPUT_DIR="$SCRIPT_DIR/output"

# ── bootstrap ────────────────────────────────────────────────────────────────

if [[ ! -x "$T2S" ]]; then
    echo "Setting up environment (first run)..."
    uv pip install $PYPI ollama pyttsx3 typer rich soundfile numpy click kokoro-onnx "misaki[en]"
    uv pip install $PYPI -e .
    echo ""
    echo "Ready. Kokoro model files (~300 MB) will be downloaded on first speak."
    echo ""
fi

# ── auto-save injection ───────────────────────────────────────────────────────
# For commands that produce audio (speak, speak-file, interactive), automatically
# inject --save / --save-dir with a timestamped path unless the caller already
# provided one.

COMMAND="${1:-}"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"

_has_flag() {
    local flag="$1"; shift
    for arg in "$@"; do
        [[ "$arg" == "$flag" ]] && return 0
    done
    return 1
}

case "$COMMAND" in
    speak|speak-file)
        if ! _has_flag "--save" "$@" && ! _has_flag "-o" "$@"; then
            mkdir -p "$OUTPUT_DIR"
            AUTO_SAVE="$OUTPUT_DIR/${TIMESTAMP}_${COMMAND//-/_}.wav"
            echo "Audio will also be saved to: $AUTO_SAVE"
            exec "$T2S" "$@" --save "$AUTO_SAVE"
        fi
        ;;
    interactive)
        if ! _has_flag "--save-dir" "$@"; then
            AUTO_DIR="$OUTPUT_DIR/${TIMESTAMP}_interactive"
            mkdir -p "$AUTO_DIR"
            echo "Replies will also be saved to: $AUTO_DIR/"
            exec "$T2S" "$@" --save-dir "$AUTO_DIR"
        fi
        ;;
esac

exec "$T2S" "$@"
