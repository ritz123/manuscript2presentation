"""Typer CLI for text2speech — text processing via Ollama + local TTS."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Annotated, Optional

import typer
from rich import print as rprint
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.table import Table
from rich.text import Text

from text2speech import __version__
from text2speech import ollama_client as ollama
from text2speech.engine import EngineChoice, get_engine
from text2speech.tts_base import TTSEngineBase

app = typer.Typer(
    name="text2speech",
    help=(
        "[bold cyan]Text-to-Speech[/] powered by local [bold green]Ollama[/] models.\n\n"
        "Engines:  [bold yellow]kokoro[/] (neural, high-quality)  •  [bold blue]pyttsx3[/] (espeak-ng, 100+ languages)"
    ),
    rich_markup_mode="rich",
    add_completion=True,
    no_args_is_help=True,
)

console = Console()
err_console = Console(stderr=True)

# Engine option shared across commands
_ENGINE_OPT = Annotated[
    EngineChoice,
    typer.Option(
        "--engine",
        "-e",
        help="TTS engine: [bold]auto[/] | [bold]kokoro[/] (neural) | [bold]pyttsx3[/] (espeak-ng).",
        show_default=True,
    ),
]


# ── helpers ─────────────────────────────────────────────────────────────────


def _abort(msg: str) -> None:
    err_console.print(f"[bold red]Error:[/] {msg}")
    raise typer.Exit(1)


def _pick_model(model: str | None, prompt_text: str = "Select Ollama model") -> str:
    if model:
        return model
    try:
        models = ollama.list_models()
    except RuntimeError as e:
        _abort(str(e))

    if not models:
        _abort("No Ollama models found. Pull one with: ollama pull <model>")

    table = Table(title="Available Ollama Models", show_lines=True)
    table.add_column("#", style="bold cyan", width=4)
    table.add_column("Model", style="bold white")
    table.add_column("Params", style="yellow")
    table.add_column("Size", style="green")
    table.add_column("Family", style="blue")

    for i, m in enumerate(models, 1):
        table.add_row(str(i), m.name, m.parameter_count, f"{m.size_gb:.1f} GB", m.family)

    console.print(table)
    choice = Prompt.ask(
        prompt_text,
        choices=[str(i) for i in range(1, len(models) + 1)],
        default="1",
    )
    return models[int(choice) - 1].name


def _build_engine(
    engine_choice: EngineChoice,
    rate: int,
    volume: float,
    voice_id: str | None,
) -> TTSEngineBase:
    engine = get_engine(engine_choice)
    engine.set_rate(rate)
    engine.set_volume(volume)
    if voice_id:
        engine.set_voice(voice_id)
    return engine


def _engine_label(engine: TTSEngineBase) -> str:
    name = type(engine).__name__
    labels = {"KokoroEngine": "[bold yellow]kokoro[/]", "Pyttsx3Engine": "[bold blue]pyttsx3[/]"}
    return labels.get(name, name)


# ── commands ─────────────────────────────────────────────────────────────────


@app.command()
def version() -> None:
    """Show the current version."""
    rprint(f"text2speech [bold cyan]v{__version__}[/]")


@app.command("list-models")
def list_models() -> None:
    """List all locally available Ollama models."""
    try:
        models = ollama.list_models()
    except RuntimeError as e:
        _abort(str(e))

    if not models:
        console.print("[yellow]No models found.[/] Run [bold]ollama pull <model>[/] to download one.")
        return

    table = Table(title="[bold]Local Ollama Models[/]", show_lines=True)
    table.add_column("#", style="bold cyan", width=4)
    table.add_column("Model", style="bold white")
    table.add_column("Parameters", style="yellow")
    table.add_column("Size (GB)", style="green", justify="right")
    table.add_column("Family", style="blue")

    for i, m in enumerate(models, 1):
        table.add_row(str(i), m.name, m.parameter_count, f"{m.size_gb:.1f}", m.family)

    console.print(table)


@app.command("list-voices")
def list_voices(
    engine: _ENGINE_OPT = EngineChoice.auto,
) -> None:
    """List all available TTS voices for the selected engine."""
    tts = get_engine(engine)
    voices = tts.list_voices()
    engine_name = _engine_label(tts)

    if not voices:
        console.print(f"[yellow]No voices found for {engine_name}.[/]")
        return

    table = Table(title=f"[bold]Voices — {engine_name}[/]", show_lines=True)
    table.add_column("#", style="bold cyan", width=4)
    table.add_column("ID / Name", style="bold white")
    table.add_column("Languages", style="green")
    table.add_column("Gender", style="yellow")

    for i, v in enumerate(voices):
        langs = ", ".join(v.languages) if v.languages else "—"
        display = f"{v.id}  ({v.name})" if v.id != v.name else v.name
        table.add_row(str(i), display, langs, v.gender)

    console.print(table)
    console.print(f"[dim]Use [bold]--voice <ID>[/bold] with any speak command to select a voice.[/]")


@app.command()
def speak(
    text: Annotated[Optional[str], typer.Argument(help="Text to speak. Reads from stdin if omitted.")] = None,
    model: Annotated[Optional[str], typer.Option("--model", "-m", help="Ollama model for text processing.")] = None,
    process: Annotated[bool, typer.Option("--process/--no-process", help="Pre-process text with Ollama for natural speech.")] = False,
    summarize: Annotated[bool, typer.Option("--summarize/--no-summarize", help="Summarize text with Ollama before speaking.")] = False,
    engine: _ENGINE_OPT = EngineChoice.auto,
    rate: Annotated[int, typer.Option("--rate", "-r", help="Speech rate (wpm for pyttsx3; maps to speed for kokoro).", min=50, max=600)] = 175,
    volume: Annotated[float, typer.Option("--volume", "-v", help="Volume level (0.0–1.0).", min=0.0, max=1.0)] = 1.0,
    voice: Annotated[Optional[str], typer.Option("--voice", help="Voice ID (see list-voices).")] = None,
    save: Annotated[Optional[Path], typer.Option("--save", "-o", help="Save audio to WAV file instead of playing.")] = None,
) -> None:
    """
    Convert text to speech.

    Text can be passed as an argument, piped via stdin, or typed interactively.
    Optionally pre-process with an Ollama LLM for cleaner, more natural output.

    [bold]Examples:[/]

      t2s speak "Hello, world!"

      t2s speak "Hello" --engine kokoro --voice af_bella

      echo "Some long article..." | t2s speak --process --model llama3.2

      t2s speak --summarize --model mistral --save output.wav < document.txt
    """
    if text is None:
        if not sys.stdin.isatty():
            text = sys.stdin.read().strip()
        else:
            text = Prompt.ask("[cyan]Enter text to speak[/]")

    if not text.strip():
        _abort("No text provided.")

    tts = _build_engine(engine, rate, volume, voice)

    display_text = text
    if process or summarize:
        selected_model = _pick_model(model)
        action = "Summarizing" if summarize else "Preparing"
        console.print(f"[dim]{action} text with [bold]{selected_model}[/bold]...[/]")
        with console.status(""):
            if summarize:
                display_text = ollama.summarize_for_speech(text, selected_model)
            else:
                display_text = ollama.prepare_for_speech(text, selected_model)

    console.print(
        Panel(
            Text(display_text, style="white"),
            title=f"[bold cyan]Speaking[/]  via {_engine_label(tts)}",
            border_style="cyan",
        )
    )

    if save:
        with console.status(f"[cyan]Saving to {save}...[/]"):
            tts.save_to_file(display_text, save)
        console.print(f"[green]Saved to:[/] {save}")
    else:
        tts.speak(display_text)


@app.command()
def interactive(
    model: Annotated[Optional[str], typer.Option("--model", "-m", help="Ollama model to chat with.")] = None,
    engine: _ENGINE_OPT = EngineChoice.auto,
    rate: Annotated[int, typer.Option("--rate", "-r", help="Speech rate.", min=50, max=600)] = 175,
    volume: Annotated[float, typer.Option("--volume", "-v", help="Volume level (0.0–1.0).", min=0.0, max=1.0)] = 1.0,
    voice: Annotated[Optional[str], typer.Option("--voice", help="Voice ID (see list-voices).")] = None,
    speak_input: Annotated[bool, typer.Option("--speak-input/--no-speak-input", help="Also speak the user's input.")] = False,
    save_dir: Annotated[Optional[Path], typer.Option("--save-dir", help="Directory to save each reply as a WAV file.")] = None,
) -> None:
    """
    Interactive chat with an Ollama model — responses are spoken aloud.

    Each assistant reply is converted to speech immediately.
    Type [bold]quit[/] or [bold]exit[/] to end the session.

    [bold]Examples:[/]

      t2s interactive --model llama3.2

      t2s interactive --model mistral --engine kokoro --voice bf_emma
    """
    selected_model = _pick_model(model)
    tts = _build_engine(engine, rate, volume, voice)

    if save_dir:
        save_dir.mkdir(parents=True, exist_ok=True)

    console.print(
        Panel(
            f"[bold green]Chatting with [cyan]{selected_model}[/cyan][/bold green]  "
            f"via {_engine_label(tts)}\n"
            "[dim]Responses will be spoken aloud. Type [bold]quit[/bold] to exit.[/dim]",
            title="[bold]Interactive TTS Session[/]",
            border_style="green",
        )
    )

    history: list[dict] = []
    turn = 0

    while True:
        try:
            user_input = Prompt.ask("\n[bold blue]You[/]").strip()
        except (KeyboardInterrupt, EOFError):
            console.print("\n[dim]Session ended.[/]")
            break

        if user_input.lower() in {"quit", "exit", "q", ":q"}:
            console.print("[dim]Goodbye![/]")
            break

        if not user_input:
            continue

        if speak_input:
            tts.speak(user_input)

        history.append({"role": "user", "content": user_input})

        try:
            with console.status(f"[cyan]{selected_model} is thinking...[/]"):
                reply = ollama.chat_turn(history, selected_model)
        except RuntimeError as e:
            err_console.print(f"[red]Error:[/] {e}")
            continue

        history.append({"role": "assistant", "content": reply})

        console.print(
            Panel(
                Text(reply, style="white"),
                title=f"[bold green]{selected_model}[/]",
                border_style="green",
            )
        )

        if save_dir:
            wav_path = save_dir / f"reply_{turn:04d}.wav"
            tts.save_to_file(reply, wav_path)
            console.print(f"[dim]Saved → {wav_path}[/]")

        tts.speak(reply)
        turn += 1


@app.command("speak-file")
def speak_file(
    file: Annotated[Path, typer.Argument(help="Path to the text file to read aloud.")],
    model: Annotated[Optional[str], typer.Option("--model", "-m", help="Ollama model for text processing.")] = None,
    process: Annotated[bool, typer.Option("--process/--no-process", help="Pre-process text with Ollama.")] = False,
    summarize: Annotated[bool, typer.Option("--summarize/--no-summarize", help="Summarize with Ollama before speaking.")] = False,
    engine: _ENGINE_OPT = EngineChoice.auto,
    rate: Annotated[int, typer.Option("--rate", "-r", help="Speech rate.", min=50, max=600)] = 175,
    volume: Annotated[float, typer.Option("--volume", "-v", help="Volume level (0.0–1.0).", min=0.0, max=1.0)] = 1.0,
    voice: Annotated[Optional[str], typer.Option("--voice", help="Voice ID (see list-voices).")] = None,
    save: Annotated[Optional[Path], typer.Option("--save", "-o", help="Save audio to WAV file.")] = None,
) -> None:
    """
    Read a text file aloud.

    [bold]Examples:[/]

      t2s speak-file document.txt --engine kokoro --voice bf_emma

      t2s speak-file notes.md --summarize --model llama3.2

      t2s speak-file article.txt --process --model mistral --save article.wav
    """
    if not file.exists():
        _abort(f"File not found: {file}")

    text = file.read_text(encoding="utf-8").strip()
    if not text:
        _abort(f"File is empty: {file}")

    console.print(f"[dim]Read {len(text):,} characters from [bold]{file}[/bold][/]")

    tts = _build_engine(engine, rate, volume, voice)

    display_text = text
    if process or summarize:
        selected_model = _pick_model(model)
        action = "Summarizing" if summarize else "Preparing"
        console.print(f"[dim]{action} with [bold]{selected_model}[/bold]...[/]")
        with console.status(""):
            if summarize:
                display_text = ollama.summarize_for_speech(text, selected_model)
            else:
                display_text = ollama.prepare_for_speech(text, selected_model)

    console.print(
        Panel(
            Text(display_text[:500] + ("…" if len(display_text) > 500 else ""), style="white"),
            title=f"[bold cyan]Speaking:[/] {file.name}  via {_engine_label(tts)}",
            border_style="cyan",
            subtitle=f"[dim]{len(display_text):,} characters[/]",
        )
    )

    if save:
        with console.status(f"[cyan]Saving to {save}...[/]"):
            tts.save_to_file(display_text, save)
        console.print(f"[green]Saved to:[/] {save}")
    else:
        tts.speak(display_text)


@app.command()
def config(
    engine: _ENGINE_OPT = EngineChoice.auto,
) -> None:
    """Show current TTS engine configuration and available properties."""
    tts = get_engine(engine)
    props = tts.get_properties()
    voices = tts.list_voices()
    engine_name = _engine_label(tts)

    table = Table(title=f"[bold]TTS Engine Configuration — {engine_name}[/]", show_lines=True)
    table.add_column("Property", style="bold cyan")
    table.add_column("Value", style="white")

    table.add_row("Engine", type(tts).__name__)
    for k, v in props.items():
        table.add_row(k.replace("_", " ").title(), str(v))
    table.add_row("Total voices", str(len(voices)))

    console.print(table)


@app.command("download-models")
def download_models() -> None:
    """
    Pre-download Kokoro model files (~300 MB).

    Files are stored in [bold]~/.local/share/text2speech/models/[/].
    This command is optional — models are also auto-downloaded on first [bold]speak[/].
    """
    from text2speech.tts_kokoro import _MODEL_PATH, _VOICES_PATH, ensure_models, models_available

    if models_available():
        console.print("[green]Kokoro model files are already downloaded.[/]")
        console.print(f"  [dim]{_MODEL_PATH}[/]")
        console.print(f"  [dim]{_VOICES_PATH}[/]")
        return

    console.print("Downloading Kokoro model files to [bold]~/.local/share/text2speech/models/[/]")
    try:
        ensure_models(progress=True)
        console.print("[bold green]Download complete![/] Kokoro engine is ready.")
    except Exception as e:
        _abort(f"Download failed: {e}")
