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


@app.command("speak-slides")
def speak_slides(
    file: Annotated[Path, typer.Argument(help="Path to .pptx or .pdf slide file.")],
    engine: _ENGINE_OPT = EngineChoice.auto,
    voice: Annotated[Optional[str], typer.Option("--voice", help="Voice ID (see list-voices).")] = None,
    rate: Annotated[int, typer.Option("--rate", "-r", help="Speech rate.", min=50, max=600)] = 175,
    volume: Annotated[float, typer.Option("--volume", "-v", help="Volume level (0.0–1.0).", min=0.0, max=1.0)] = 1.0,
    include_notes: Annotated[bool, typer.Option("--notes/--no-notes", help="Also speak presenter notes.")] = False,
    model: Annotated[Optional[str], typer.Option("--model", "-m", help="Ollama model to summarize each slide before speaking.")] = None,
    summarize: Annotated[bool, typer.Option("--summarize/--no-summarize", help="Summarize each slide with Ollama before speaking.")] = False,
    slide_range: Annotated[Optional[str], typer.Option("--slides", "-s", help="Slide range to read, e.g. 1-5 or 2,4,7.")] = None,
    save_dir: Annotated[Optional[Path], typer.Option("--save-dir", help="Save each slide's audio as a separate WAV file.")] = None,
    pause: Annotated[bool, typer.Option("--pause/--no-pause", help="Pause for keypress between slides.")] = False,
) -> None:
    """
    Read a presentation aloud, slide by slide.

    Supports [bold].pptx[/] (PowerPoint) and [bold].pdf[/] files.
    Each slide's title and body text are spoken in order.

    [bold]Examples:[/]

      t2s speak-slides presentation.pptx

      t2s speak-slides slides.pptx --voice bf_emma --slides 1-10

      t2s speak-slides deck.pptx --summarize --model llama3.2

      t2s speak-slides report.pdf --notes --save-dir ./audio
    """
    from text2speech.slides import read_slides

    if not file.exists():
        _abort(f"File not found: {file}")

    try:
        all_slides = read_slides(file)
    except (ValueError, RuntimeError) as e:
        _abort(str(e))

    if not all_slides:
        _abort("No slides found in the file.")

    # ── parse slide range ────────────────────────────────────────────────────
    selected_indices: set[int] = set()
    if slide_range:
        for part in slide_range.split(","):
            part = part.strip()
            if "-" in part:
                lo, hi = part.split("-", 1)
                selected_indices.update(range(int(lo), int(hi) + 1))
            else:
                selected_indices.add(int(part))
        slides = [s for s in all_slides if s.index in selected_indices]
    else:
        slides = all_slides

    if not slides:
        _abort(f"No slides matched the range '{slide_range}'.")

    tts = _build_engine(engine, rate, volume, voice)

    if save_dir:
        save_dir.mkdir(parents=True, exist_ok=True)

    selected_model = _pick_model(model) if summarize else None

    console.print(
        Panel(
            f"[bold]{file.name}[/]  —  {len(slides)} slide{'s' if len(slides) != 1 else ''}\n"
            f"[dim]Engine: {_engine_label(tts)}  |  Notes: {'on' if include_notes else 'off'}  |  "
            f"Summarize: {'on (' + (selected_model or '') + ')' if summarize else 'off'}[/]",
            title="[bold cyan]Speaking Slides[/]",
            border_style="cyan",
        )
    )

    for slide in slides:
        text = slide.spoken_text(include_notes=include_notes)
        if not text.strip():
            console.print(f"[dim]Slide {slide.index}: (empty — skipping)[/]")
            continue

        if summarize and selected_model:
            with console.status(f"[cyan]Summarizing slide {slide.index}...[/]"):
                try:
                    text = ollama.summarize_for_speech(text, selected_model)
                except RuntimeError as e:
                    err_console.print(f"[yellow]Warning:[/] {e}")

        console.print(
            Panel(
                Text(text[:400] + ("…" if len(text) > 400 else ""), style="white"),
                title=f"[bold cyan]Slide {slide.index}:[/] {slide.display_title()}",
                border_style="cyan",
                subtitle=f"[dim]{len(text)} chars[/]",
            )
        )

        if save_dir:
            wav = save_dir / f"slide_{slide.index:03d}.wav"
            tts.save_to_file(text, wav)
            console.print(f"[dim]  Saved → {wav}[/]")

        tts.speak(text)

        if pause and slide.index != slides[-1].index:
            try:
                Prompt.ask("[dim]  Press Enter for next slide[/]")
            except (KeyboardInterrupt, EOFError):
                console.print("\n[dim]Stopped.[/]")
                break

    console.print("[bold green]Done.[/]")


@app.command("canvas-video")
def canvas_video(
    tsx_file: Annotated[Path, typer.Argument(help="Path to the *.canvas.tsx presentation file.")],
    output: Annotated[Optional[Path], typer.Option("--output", "-o", help="Output MP4 path (default: <stem>.mp4 next to the TSX file).")] = None,
    engine: _ENGINE_OPT = EngineChoice.auto,
    voice: Annotated[Optional[str], typer.Option("--voice", help="Voice ID (see list-voices).")] = None,
    rate: Annotated[int, typer.Option("--rate", "-r", help="Speech rate.", min=50, max=600)] = 160,
    volume: Annotated[float, typer.Option("--volume", "-v", help="Volume level (0.0–1.0).", min=0.0, max=1.0)] = 1.0,
    slide_range: Annotated[Optional[str], typer.Option("--slides", "-s", help="Slides to include, e.g. 1-5 or 1,3,5.")] = None,
    work_dir: Annotated[Optional[Path], typer.Option("--work-dir", help="Keep intermediate PNGs and WAVs here (default: temp dir).")] = None,
    fps: Annotated[int, typer.Option("--fps", help="Video frame rate.", min=1, max=60)] = 25,
    tail: Annotated[float, typer.Option("--tail", help="Seconds of silence after each slide.", min=0.0, max=10.0)] = 1.5,
) -> None:
    """
    Generate a narrated MP4 video from a [bold]*.canvas.tsx[/bold] presentation.

    The output MP4 is saved next to the TSX file (or to [bold]--output[/bold]).

    [bold]Examples:[/]

      t2s canvas-video slides.canvas.tsx

      t2s canvas-video slides.canvas.tsx --engine kokoro --voice bf_emma

      t2s canvas-video slides.canvas.tsx --output my_video.mp4 --slides 1-5
    """
    import tempfile, shutil
    from text2speech.canvas_video import (
        slides_from_tsx, slides_from_yaml, slides_from_presentation,
        generate_audio, render_slide, assemble_video,
    )

    if not tsx_file.exists():
        _abort(f"File not found: {tsx_file}")

    suffix = tsx_file.suffix.lower()
    if suffix in (".yaml", ".yml"):
        all_slides = slides_from_yaml(tsx_file)
        stem = tsx_file.stem
    elif suffix == ".tsx":
        all_slides = slides_from_tsx(tsx_file)
        stem = tsx_file.stem.replace(".canvas", "")
    elif suffix in (".pptx", ".pdf"):
        all_slides = slides_from_presentation(tsx_file)
        stem = tsx_file.stem
    else:
        _abort(f"Unsupported format: {suffix!r}. Pass a .yaml, .pptx, .pdf, or .tsx file.")

    if not all_slides:
        _abort("No slides found in the file.")

    _output = output or (tsx_file.parent / f"{stem}.mp4")

    # ── filter slides ────────────────────────────────────────────────────────
    if slide_range:
        wanted: set[int] = set()
        for part in slide_range.split(","):
            part = part.strip()
            if "-" in part:
                lo, hi = part.split("-", 1)
                wanted.update(range(int(lo), int(hi) + 1))
            else:
                wanted.add(int(part))
        selected = [s for s in all_slides if s.index in wanted]
    else:
        selected = all_slides

    if not selected:
        _abort(f"No slides matched the range '{slide_range}'.")

    tts = _build_engine(engine, rate, volume, voice)

    console.print(
        Panel(
            f"[bold]{len(selected)} slide{'s' if len(selected) != 1 else ''}[/] → [cyan]{_output}[/]\n"
            f"[dim]Engine: {_engine_label(tts)}  |  {W}×{H} @ {fps} fps  |  tail: {tail}s[/]",
            title="[bold cyan]Canvas Video[/]",
            border_style="cyan",
        )
    )

    use_tmp = work_dir is None
    _work = Path(tempfile.mkdtemp(prefix="t2s_canvas_")) if use_tmp else work_dir
    _work.mkdir(parents=True, exist_ok=True)

    img_dir = _work / "images"
    aud_dir = _work / "audio"
    img_dir.mkdir(exist_ok=True)
    aud_dir.mkdir(exist_ok=True)

    try:
        # ── render images ────────────────────────────────────────────────────
        console.print("[bold]Rendering slide images…[/]")
        for spec in selected:
            img_path = img_dir / f"slide_{spec.index:02d}.png"
            with console.status(f"  Slide {spec.index}: {spec.title[:50]}…"):
                render_slide(spec, img_path, total=len(selected))
            console.print(f"  [green]✓[/] Slide {spec.index} → {img_path.name}")

        # ── generate audio ───────────────────────────────────────────────────
        console.print("\n[bold]Generating narration audio…[/]")
        for spec in selected:
            aud_path = aud_dir / f"slide_{spec.index:02d}.wav"
            with console.status(f"  Slide {spec.index}: narrating…"):
                generate_audio(spec, aud_path, tts)
            console.print(f"  [green]✓[/] Slide {spec.index} → {aud_path.name}")

        # ── assemble video ───────────────────────────────────────────────────
        console.print("\n[bold]Assembling video…[/]")
        with console.status("[cyan]Running ffmpeg…[/]"):
            assemble_video(
                selected, img_dir, aud_dir, _output,
                fps=fps, tail_seconds=tail,
            )

        size_mb = _output.stat().st_size / 1_048_576
        console.print(
            Panel(
                f"[bold green]Video saved:[/] {_output}\n"
                f"[dim]{len(selected)} slides · {size_mb:.1f} MB[/]",
                border_style="green",
            )
        )

        if not use_tmp:
            console.print(f"[dim]Intermediate files kept in: {_work}[/]")

    finally:
        if use_tmp and _work.exists():
            shutil.rmtree(_work, ignore_errors=True)


W, H = 1280, 720   # exposed so the status Panel can reference it


@app.command("canvas-mp3")
def canvas_mp3(
    tsx_file: Annotated[Path, typer.Argument(help="Path to the *.canvas.tsx presentation file.")],
    out_dir: Annotated[Optional[Path], typer.Option("--out-dir", "-d", help="Directory for per-slide MP3s (default: <stem>_mp3/).")] = None,
    combined: Annotated[Optional[Path], typer.Option("--combined", "-o", help="Also write a single combined MP3 to this path.")] = None,
    engine: _ENGINE_OPT = EngineChoice.auto,
    voice: Annotated[Optional[str], typer.Option("--voice", help="Voice ID (see list-voices).")] = None,
    rate: Annotated[int, typer.Option("--rate", "-r", help="Speech rate.", min=50, max=600)] = 160,
    volume: Annotated[float, typer.Option("--volume", "-v", help="Volume level (0.0–1.0).", min=0.0, max=1.0)] = 1.0,
    slide_range: Annotated[Optional[str], typer.Option("--slides", "-s", help="Slides to include, e.g. 1-5 or 1,3,5.")] = None,
    bitrate: Annotated[str, typer.Option("--bitrate", "-b", help="MP3 bitrate (e.g. 128k, 192k, 320k).")] = "192k",
) -> None:
    """
    Generate per-slide MP3 narrations from a [bold]*.canvas.tsx[/bold] presentation.

    Reads the canvas file to discover slides, then produces one MP3 per slide
    plus an optional single combined MP3 that plays straight through.

    [bold]Examples:[/]

      t2s canvas-mp3 slides.pptx

      t2s canvas-mp3 slides.canvas.tsx --out-dir ./mp3s --combined all.mp3

      t2s canvas-mp3 slides.canvas.tsx --engine kokoro --voice bf_emma --slides 1-5

      t2s canvas-mp3 slides.canvas.tsx --bitrate 320k --rate 140
    """
    import tempfile
    from text2speech.canvas_video import (
        slides_from_tsx, slides_from_yaml, slides_from_presentation,
        generate_audio, wav_to_mp3, concat_mp3s,
    )

    if not tsx_file.exists():
        _abort(f"File not found: {tsx_file}")

    suffix = tsx_file.suffix.lower()
    if suffix in (".yaml", ".yml"):
        all_slides = slides_from_yaml(tsx_file)
        stem = tsx_file.stem
    elif suffix == ".tsx":
        all_slides = slides_from_tsx(tsx_file)
        stem = tsx_file.stem.replace(".canvas", "")
    elif suffix in (".pptx", ".pdf"):
        all_slides = slides_from_presentation(tsx_file)
        stem = tsx_file.stem
    else:
        _abort(f"Unsupported format: {suffix!r}. Pass a .yaml, .pptx, .pdf, or .tsx file.")

    if not all_slides:
        _abort("No slides found in the file.")

    # ── filter by range ──────────────────────────────────────────────────────
    if slide_range:
        wanted: set[int] = set()
        for part in slide_range.split(","):
            part = part.strip()
            if "-" in part:
                lo, hi = part.split("-", 1)
                wanted.update(range(int(lo), int(hi) + 1))
            else:
                wanted.add(int(part))
        selected = [s for s in all_slides if s.index in wanted]
    else:
        selected = all_slides

    if not selected:
        _abort(f"No slides matched the range '{slide_range}'.")

    tts = _build_engine(engine, rate, volume, voice)

    # ── output directory ─────────────────────────────────────────────────────
    stem = tsx_file.stem.replace(".canvas", "")
    _out_dir = out_dir or (tsx_file.parent / f"{stem}_mp3")
    _out_dir.mkdir(parents=True, exist_ok=True)

    console.print(
        Panel(
            f"[bold]{tsx_file.name}[/]  →  [cyan]{_out_dir}/[/]\n"
            f"[dim]{len(selected)} slide{'s' if len(selected) != 1 else ''}  |  "
            f"Engine: {_engine_label(tts)}  |  Bitrate: {bitrate}[/]",
            title="[bold cyan]Canvas MP3[/]",
            border_style="cyan",
        )
    )

    mp3_files: list[Path] = []

    with tempfile.TemporaryDirectory(prefix="t2s_mp3_") as tmp:
        tmp_path = Path(tmp)

        for spec in selected:
            # 1. generate WAV narration
            wav_path = tmp_path / f"slide_{spec.index:02d}.wav"
            mp3_path = _out_dir / f"slide_{spec.index:02d}_{_slug(spec.title)}.mp3"

            with console.status(f"  [cyan]Slide {spec.index}:[/] generating narration…"):
                generate_audio(spec, wav_path, tts)

            # 2. convert WAV → MP3
            with console.status(f"  [cyan]Slide {spec.index}:[/] encoding MP3…"):
                wav_to_mp3(wav_path, mp3_path, bitrate=bitrate)

            mp3_files.append(mp3_path)
            size_kb = mp3_path.stat().st_size // 1024
            console.print(
                f"  [green]✓[/] Slide {spec.index:>2}  "
                f"[dim]{spec.title[:48]}[/]  "
                f"[dim]{size_kb} KB[/] → {mp3_path.name}"
            )

    # ── combined MP3 ─────────────────────────────────────────────────────────
    if combined or len(mp3_files) > 1:
        _combined = combined or (_out_dir / f"{stem}_combined.mp3")
        with console.status(f"[cyan]Concatenating {len(mp3_files)} MP3s…[/]"):
            concat_mp3s(mp3_files, _combined)
        size_mb = _combined.stat().st_size / 1_048_576
        console.print(f"\n[bold green]Combined MP3:[/] {_combined}  [dim]({size_mb:.1f} MB)[/]")

    total_kb = sum(p.stat().st_size for p in mp3_files) // 1024
    console.print(
        Panel(
            f"[bold green]{len(mp3_files)} MP3 file{'s' if len(mp3_files) != 1 else ''}[/] "
            f"saved to [cyan]{_out_dir}/[/]\n"
            f"[dim]Total: {total_kb} KB[/]",
            border_style="green",
        )
    )


def _slug(text: str) -> str:
    """Convert a title to a safe filename slug."""
    import re
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")[:40]


@app.command("paper-to-slides")
def paper_to_slides(
    pdf_file: Annotated[Path, typer.Argument(help="PDF manuscript to convert into a presentation")],
    model: Annotated[str, typer.Option("--model", "-m", help="Ollama model for slide planning")] = "llama3.2",
    n_slides: Annotated[int, typer.Option("--n-slides", help="Target number of slides (8-14)")] = 12,
    output: Annotated[Optional[Path], typer.Option("--output", "-o", help="Output PPTX path")] = None,
    video: Annotated[bool, typer.Option("--video/--no-video", help="Also render a narrated MP4")] = False,
    engine: Annotated[str, typer.Option("--engine", help="TTS engine for video: kokoro or pyttsx3")] = "kokoro",
    voice: Annotated[Optional[str], typer.Option("--voice", help="TTS voice ID")] = None,
) -> None:
    """
    Convert a PDF manuscript into a styled PPTX presentation (and optionally a narrated video).

    Uses [bold green]Ollama[/] to intelligently plan slides from the document content,
    then builds a styled PPTX with bullets in the slide body and full narration in Notes.

    [bold]Examples:[/]

      t2s paper-to-slides paper.pdf

      t2s paper-to-slides paper.pdf --model llama3.2 --n-slides 10

      t2s paper-to-slides paper.pdf --video --engine kokoro --voice bm_george
    """
    import json
    import re

    if not pdf_file.exists():
        _abort(f"File not found: {pdf_file}")
    if pdf_file.suffix.lower() != ".pdf":
        _abort(f"Expected a .pdf file, got: {pdf_file}")

    stem    = pdf_file.stem
    pptx_out = output or (pdf_file.parent / f"{stem}.pptx")

    # ── Step 1: extract PDF text ──────────────────────────────────────────────
    console.print(f"\n[bold]Step 1/3[/] Extracting text from [cyan]{pdf_file.name}[/]…")
    try:
        import pypdf
    except ImportError:
        _abort("pypdf is required. Run: uv pip install pypdf")

    reader = pypdf.PdfReader(str(pdf_file))
    pages  = [p.extract_text() or "" for p in reader.pages]
    full_text = "\n\n--- PAGE BREAK ---\n\n".join(pages)
    console.print(f"  [green]✓[/] {len(reader.pages)} pages, {len(full_text):,} characters")

    # ── Step 2: call Ollama to generate slide plan ────────────────────────────
    console.print(f"\n[bold]Step 2/3[/] Generating slide plan with [green]{model}[/]…")

    prompt = f"""You are a presentation designer. Read the document below and produce a slide plan as a JSON array.

Rules:
- {n_slides} slides total (first = title/overview, last = conclusions/takeaways)
- "title": short slide title (<= 8 words)
- "tag": optional short section label in ALL CAPS (e.g. "OVERVIEW", "METHOD")
- "bullets": 4-6 concise on-slide points (<= 12 words each, no full sentences)
- "narration": 3-5 full spoken sentences expanding on the bullets
- "image_page": (optional integer) PDF page number whose figure best illustrates this slide; omit if none
- Output ONLY valid JSON array, no markdown, no prose

Document:
{full_text[:40000]}"""

    try:
        import ollama as _ollama
        with console.status(f"  Calling {model}…"):
            response = _ollama.generate(model=model, prompt=prompt)
        raw = response.response if hasattr(response, "response") else response["response"]
    except Exception as e:
        _abort(f"Ollama call failed: {e}\nMake sure Ollama is running and '{model}' is pulled.")

    # Strip markdown code fences if the model wrapped the JSON
    raw = re.sub(r"```(?:json)?\s*", "", raw).strip().rstrip("`").strip()

    # Extract the JSON array (in case there's any leading/trailing prose)
    match = re.search(r"\[.*\]", raw, re.DOTALL)
    if not match:
        _abort("Ollama did not return a valid JSON array. Try a different model or check Ollama is working.")
    try:
        plan: list[dict] = json.loads(match.group())
    except json.JSONDecodeError as e:
        _abort(f"Could not parse Ollama response as JSON: {e}")

    console.print(f"  [green]✓[/] {len(plan)} slides planned")

    # ── Step 3: build PPTX ────────────────────────────────────────────────────
    console.print(f"\n[bold]Step 3/3[/] Building PPTX [cyan]{pptx_out.name}[/]…")
    try:
        from text2speech.pptx_builder import build_pptx
    except ImportError as e:
        _abort(f"pptx_builder not available: {e}")

    with console.status("  Rendering slides…"):
        build_pptx(plan, pptx_out, pdf_file)
    console.print(f"  [green]✓[/] Saved: {pptx_out}")

    # ── Optional: render video ─────────────────────────────────────────────────
    if video:
        console.print(f"\n[bold]Bonus[/] Rendering narrated video…")
        voice_args = ["--voice", voice] if voice else []
        import subprocess, sys as _sys
        cmd = [_sys.executable, "-m", "text2speech.cli",
               "canvas-video", str(pptx_out),
               "--engine", engine,
               "--output", str(pptx_out.with_suffix(".mp4")),
               *voice_args]
        result = subprocess.run(cmd)
        if result.returncode == 0:
            console.print(f"  [green]✓[/] Video: {pptx_out.with_suffix('.mp4')}")

    console.print(f"\n[bold green]Done![/]")
    console.print(f"  PPTX:  {pptx_out}")
    console.print(f"  Video: [dim]./run.sh {pptx_out} --engine kokoro[/]  (to generate later)")


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
