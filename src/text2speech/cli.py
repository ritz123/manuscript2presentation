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
    video: Annotated[bool, typer.Option("--video/--no-video", help="Render a narrated MP4 (default: on)")] = True,
    engine: Annotated[str, typer.Option("--engine", help="TTS engine for video: kokoro or pyttsx3")] = "kokoro",
    voice: Annotated[Optional[str], typer.Option("--voice", help="TTS voice ID")] = None,
    review: Annotated[bool, typer.Option("--review/--no-review", help="Generate a structured review .md (default: on)")] = True,
    review_no_web: Annotated[bool, typer.Option("--review-no-web", help="Disable web tools for the review (offline mode)")] = False,
) -> None:
    """
    Convert a PDF manuscript into a styled PPTX presentation (and optionally a narrated video and review).

    Uses [bold green]Ollama[/] to intelligently plan slides from the document content,
    then builds a styled PPTX with bullets in the slide body and full narration in Notes.
    Also runs the structured academic review agent by default.

    [bold]Examples:[/]

      t2s paper-to-slides paper.pdf

      t2s paper-to-slides paper.pdf --model llama3.2 --n-slides 10

      t2s paper-to-slides paper.pdf --video --engine kokoro --voice bm_george

      t2s paper-to-slides paper.pdf --no-review   # skip the review step
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
        import warnings as _warnings
        _warnings.filterwarnings("ignore", message=".*Lookup Table.*")
        _warnings.filterwarnings("ignore", message=".*PdfReadWarning.*")
    except ImportError:
        _abort("pypdf is required. Run: uv pip install pypdf")

    import warnings as _warnings
    with _warnings.catch_warnings():
        _warnings.simplefilter("ignore")   # suppress pypdf LookupTable noise
        reader = pypdf.PdfReader(str(pdf_file))
        pages  = [p.extract_text() or "" for p in reader.pages]
    full_text = "\n\n--- PAGE BREAK ---\n\n".join(pages)
    console.print(f"  [green]✓[/] {len(reader.pages)} pages, {len(full_text):,} characters")

    # Scan for pages that have embedded images (figures / diagrams)
    import io as _io
    import warnings as _warnings
    from PIL import Image as _PILImage
    figure_pages: list[int] = []
    with _warnings.catch_warnings():
        _warnings.simplefilter("ignore")
        reader2 = pypdf.PdfReader(str(pdf_file))   # fresh reader for image scan
    for pg_idx, page in enumerate(reader2.pages):
        try:
            with _warnings.catch_warnings():
                _warnings.simplefilter("ignore")
                imgs = list(page.images)
        except Exception:
            imgs = []
        for img_file in imgs:
            try:
                pil = _PILImage.open(_io.BytesIO(img_file.data))
                if pil.width * pil.height > 10_000:   # skip tiny decorative images
                    figure_pages.append(pg_idx + 1)
                    break
            except Exception:
                pass

    # Also look for pages whose text starts with "Fig" / "Figure" in any line
    # (helpful for vector-graphics-only pages that have no embedded rasters)
    import re as _re
    for pg_idx, pg_text in enumerate(pages):
        pg_num = pg_idx + 1
        if pg_num not in figure_pages:
            if _re.search(r"\bFig(?:ure)?\s*\d", pg_text, _re.IGNORECASE):
                figure_pages.append(pg_num)

    figure_pages.sort()
    console.print(f"  [green]✓[/] Figure pages found: {figure_pages or 'none'}")

    # Build figure catalog for the LLM
    if figure_pages:
        catalog_lines = [
            "AVAILABLE FIGURE PAGES (only use these for image_page):",
        ]
        for pg_num in figure_pages:
            snippet = pages[pg_num - 1][:200].replace("\n", " ").strip()
            catalog_lines.append(f"  Page {pg_num}: {snippet}")
        figure_catalog = "\n".join(catalog_lines)
        image_rule = (
            f'- "image_page": assign from the list below to slides where the figure is relevant; '
            f"omit for slides where no figure fits"
        )
    else:
        figure_catalog = ""
        image_rule = '- "image_page": omit (no figures detected in this document)'

    # ── Step 2a: summarise the paper ─────────────────────────────────────────
    # Chunk the full text so long papers aren't silently truncated.
    CHUNK = 35_000
    chunks = [full_text[i : i + CHUNK] for i in range(0, len(full_text), CHUNK)]
    console.print(
        f"\n[bold]Step 2a/3[/] Summarising paper with [green]{model}[/] "
        f"({len(chunks)} chunk{'s' if len(chunks) != 1 else ''})…"
    )

    try:
        import ollama as _ollama
    except ImportError:
        _abort("ollama is required. Run: uv pip install ollama")

    def _ollama_call(prompt_text: str) -> str:
        with console.status(f"  Calling {model}…"):
            resp = _ollama.generate(model=model, prompt=prompt_text)
        return resp.response if hasattr(resp, "response") else resp["response"]

    summary_prompt = (
        "You are a research assistant. Read the document excerpt(s) below and write a structured summary "
        "covering: (1) the problem or research question, (2) the approach or methods, "
        "(3) key results or findings, (4) main contributions or conclusions. "
        "Be concise but complete — this summary will be used to create a presentation. "
        "Output plain prose, no JSON.\n\n"
    )
    for idx, chunk in enumerate(chunks):
        label = f"[Part {idx + 1}/{len(chunks)}]" if len(chunks) > 1 else ""
        summary_prompt += f"=== DOCUMENT {label} ===\n{chunk}\n\n"

    try:
        paper_summary = _ollama_call(summary_prompt)
    except Exception as e:
        _abort(f"Ollama call failed: {e}\nMake sure Ollama is running and '{model}' is pulled.")

    console.print(f"  [green]✓[/] Summary: {len(paper_summary):,} characters")

    # ── Step 2b: generate slide plan from summary ─────────────────────────────
    console.print(f"\n[bold]Step 2b/3[/] Planning {n_slides} slides with [green]{model}[/]…")

    plan_prompt = f"""You are a presentation designer. Using the paper summary below, produce a slide plan as a JSON array.

Rules:
- {n_slides} slides total (first = title/overview, last = conclusions/takeaways)
- "title": short slide title (<= 8 words)
- "tag": optional short section label in ALL CAPS (e.g. "OVERVIEW", "METHOD")
- "bullets": 4-6 concise on-slide points (<= 12 words each, no full sentences)
- "narration": 3-5 full spoken sentences that read as natural speech, not bullet-point prose
- {image_rule}
- Output ONLY valid JSON array, no markdown, no prose

{figure_catalog}

Paper summary:
{paper_summary}"""

    try:
        raw = _ollama_call(plan_prompt)
    except Exception as e:
        _abort(f"Ollama call failed: {e}\nMake sure Ollama is running and '{model}' is pulled.")

    # Strip markdown code fences if the model wrapped the JSON
    raw = re.sub(r"```(?:json)?\s*", "", raw).strip().rstrip("`").strip()

    # Extract all top-level JSON arrays and merge them into one.
    # Some models emit multiple arrays (e.g. two chunks of slides) instead of one.
    array_matches = list(re.finditer(r"\[.*?\](?=\s*(?:\[|$))", raw, re.DOTALL))
    if not array_matches:
        # Fall back: grab everything from first '[' to last ']'
        match = re.search(r"\[.*\]", raw, re.DOTALL)
        if not match:
            _abort("Ollama did not return a valid JSON array. Try a different model or check Ollama is working.")
        json_str = match.group()
    elif len(array_matches) == 1:
        json_str = array_matches[0].group()
    else:
        # Merge multiple arrays: strip outer brackets and join into one array
        inner_parts = []
        for m in array_matches:
            inner = m.group().strip()
            inner_parts.append(inner[1:-1].strip())  # strip leading [ and trailing ]
        json_str = "[" + ",\n".join(p for p in inner_parts if p) + "]"

    def _fix_json(s: str) -> str:
        """Fix common LLM JSON issues: trailing commas, missing commas, Python literals, smart quotes."""
        s = s.replace("\u2018", "'").replace("\u2019", "'")    # smart single quotes
        s = s.replace("\u201c", '"').replace("\u201d", '"')    # smart double quotes
        # Python literals → JSON
        s = re.sub(r'\bNone\b', 'null', s)
        s = re.sub(r'\bTrue\b', 'true', s)
        s = re.sub(r'\bFalse\b', 'false', s)
        # "image_page": Page 4  →  "image_page": 4
        s = re.sub(r'("image_page"\s*:\s*)Page\s*(\d+)', r'\g<1>\2', s, flags=re.IGNORECASE)
        s = re.sub(r",\s*([}\]])", r"\1", s)                  # trailing commas
        # Missing comma between two string values on adjacent lines:
        #   "some value"
        #   "next value"   →  "some value",\n  "next value"
        s = re.sub(r'(")\s*\n(\s*")', r'",\n\2', s)
        # Missing comma between closing ] or } and the next key/value
        s = re.sub(r'(["\d\]}])\s*\n(\s*["\[{])', r'\1,\n\2', s)
        return s

    def _try_parse(s: str) -> list[dict]:
        for attempt in (s, _fix_json(s)):
            try:
                return json.loads(attempt)
            except json.JSONDecodeError:
                pass
        raise json.JSONDecodeError("", s, 0)

    try:
        plan: list[dict] = _try_parse(json_str)
    except json.JSONDecodeError as e:
        # Re-run to get the real error position from the fixed string
        fixed = _fix_json(json_str)
        try:
            plan = json.loads(fixed)
        except json.JSONDecodeError as e2:
            char = e2.pos
            snippet = fixed[max(0, char - 80):char + 80]
            _abort(
                f"Could not parse Ollama response as JSON: {e2}\n"
                f"Problem near: …{snippet!r}…\n"
                f"Try --model mistral or a larger model for cleaner JSON output."
            )

    # ── Figure assignment ─────────────────────────────────────────────────────
    # 1. Validate: discard image_page values the LLM hallucinated (not in catalog)
    if figure_pages:
        for slide_data in plan:
            pg = slide_data.get("image_page")
            if pg is not None and pg not in figure_pages:
                slide_data.pop("image_page", None)

    # 2. Fallback: assign any still-unmatched figure pages via keyword overlap
    _STOP = {"the","a","an","of","in","to","and","is","are","it","this","that",
             "with","for","on","be","by","as","at","from","was","were","or","but"}
    already_used = {s["image_page"] for s in plan if s.get("image_page")}
    for pg_num in figure_pages:
        if pg_num in already_used:
            continue
        pg_text = pages[pg_num - 1].lower()
        best_i, best_score = -1, 0
        for i, slide_data in enumerate(plan):
            if slide_data.get("image_page"):
                continue   # slide already has an image
            keywords = (
                slide_data.get("title", "") + " "
                + " ".join(slide_data.get("bullets", []))
            ).lower()
            words = {w for w in _re.split(r"\W+", keywords) if len(w) > 3 and w not in _STOP}
            score = sum(1 for w in words if w in pg_text)
            if score > best_score:
                best_score, best_i = score, i
        if best_i >= 0 and best_score > 0:
            plan[best_i]["image_page"] = pg_num
            already_used.add(pg_num)

    assigned = [s["image_page"] for s in plan if s.get("image_page")]
    console.print(f"  [green]✓[/] {len(plan)} slides planned, {len(assigned)} with figures: {assigned}")

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
        mp4_out = pptx_out.with_suffix(".mp4")
        try:
            import shutil as _shutil
            import tempfile as _tempfile

            from text2speech.canvas_video import (
                assemble_video,
                generate_audio,
                render_slide,
                slides_from_presentation,
            )

            tts = _build_engine(EngineChoice(engine), rate=160, volume=1.0, voice_id=voice)
            all_slides = slides_from_presentation(pptx_out)

            if not all_slides:
                raise RuntimeError("No slides found in the PPTX.")

            _work = Path(_tempfile.mkdtemp(prefix="t2s_video_"))
            img_dir = _work / "images"
            aud_dir = _work / "audio"
            img_dir.mkdir()
            aud_dir.mkdir()

            try:
                console.print("  [bold]Rendering slide images…[/]")
                for spec in all_slides:
                    img_path = img_dir / f"slide_{spec.index:02d}.png"
                    with console.status(f"    Slide {spec.index}: {spec.title[:50]}…"):
                        render_slide(spec, img_path, total=len(all_slides))
                    console.print(f"    [green]✓[/] Slide {spec.index}")

                console.print("  [bold]Generating narration audio…[/]")
                for spec in all_slides:
                    aud_path = aud_dir / f"slide_{spec.index:02d}.wav"
                    with console.status(f"    Slide {spec.index}: narrating…"):
                        generate_audio(spec, aud_path, tts)
                    console.print(f"    [green]✓[/] Slide {spec.index}")

                console.print("  [bold]Assembling video…[/]")
                with console.status("    Running ffmpeg…"):
                    assemble_video(all_slides, img_dir, aud_dir, mp4_out)

            finally:
                _shutil.rmtree(_work, ignore_errors=True)

            if mp4_out.exists() and mp4_out.stat().st_size > 0:
                console.print(f"  [green]✓[/] Video: {mp4_out}")
            else:
                raise RuntimeError("ffmpeg finished but the output file was not created.")

        except Exception as _e:
            console.print(f"  [yellow]⚠[/] Video rendering failed: {_e}")
            console.print(f"  [dim]Re-run manually: ./run.sh {pptx_out} --slide --engine {engine}[/]")

    # ── Optional: generate structured review ──────────────────────────────────
    review_out: Optional[Path] = None
    if review:
        web_label = "web tools ON" if not review_no_web else "web tools OFF"
        console.print(f"\n[bold]Review[/] Generating structured review with [green]{model}[/] ({web_label})…")
        if not review_no_web:
            console.print("  [dim]The model may call web_search / fetch_url to verify citations.[/]")
        review_out = pdf_file.with_stem(pdf_file.stem + "_review").with_suffix(".md")
        try:
            _skill_path = (
                Path(__file__).parent.parent.parent
                / ".cursor" / "skills" / "ai-dm-paper-review" / "SKILL.md"
            )
            import re as _re2
            if _skill_path.exists():
                raw_skill = _skill_path.read_text()
                _system_prompt = _re2.sub(r"^---.*?---\s*", "", raw_skill, flags=_re2.DOTALL).strip()
            else:
                _system_prompt = (
                    "You are an expert academic reviewer. Produce a structured review covering: "
                    "summary, strengths, technical correctness, consistency, clarity, research "
                    "integrity, citations (verify online), authenticity, novelty, fit for venue, "
                    "gaps, suggestions, and an overall score (1–10) with recommendation "
                    "(Accept / Weak Accept / Borderline / Weak Reject / Reject)."
                )
            review_text = _run_review_agent(
                model=model,
                paper_text=full_text[:50_000],
                system_prompt=_system_prompt,
                web=not review_no_web,
            )
            review_out.write_text(review_text, encoding="utf-8")
            console.print(f"  [green]✓[/] Review: {review_out}")
        except Exception as _re:
            console.print(f"  [yellow]⚠[/] Review failed: {_re}")
            console.print(f"  [dim]Re-run manually: ./run.sh {pdf_file} --review --model {model}[/]")
            review_out = None

    console.print(f"\n[bold green]Done![/]")
    console.print(f"  PPTX:   {pptx_out}")
    if review_out and review_out.exists():
        console.print(f"  Review: {review_out}")
    console.print(f"  Video:  [dim]./run.sh {pptx_out} --engine kokoro[/]  (to generate later)")


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


# ── paper-review tool functions ────────────────────────────────────────────────

def _web_search(query: str, max_results: int = 5) -> str:
    """Search the web via DuckDuckGo (no API key required)."""
    try:
        from duckduckgo_search import DDGS
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
        if not results:
            return "No results found."
        lines = []
        for r in results:
            lines.append(f"Title: {r.get('title', '').strip()}")
            lines.append(f"URL:   {r.get('href', '').strip()}")
            lines.append(f"Snippet: {r.get('body', '').strip()}")
            lines.append("")
        return "\n".join(lines).strip()
    except ImportError:
        return "duckduckgo_search not installed. Run: uv pip install duckduckgo-search"
    except Exception as e:
        return f"Search failed: {e}"


def _fetch_url(url: str, max_chars: int = 4000) -> str:
    """Fetch a URL and return its cleaned text (strips HTML tags)."""
    import re
    try:
        import requests as _requests
        headers = {"User-Agent": "Mozilla/5.0 (compatible; paper-reviewer/1.0)"}
        resp = _requests.get(url, headers=headers, timeout=12)
        resp.raise_for_status()
        text = re.sub(r"<[^>]+>", " ", resp.text)
        text = re.sub(r"\s+", " ", text).strip()
        return text[:max_chars]
    except ImportError:
        return "requests not installed. Run: uv pip install requests"
    except Exception as e:
        return f"Fetch failed: {e}"


def _run_review_agent(
    model: str,
    paper_text: str,
    system_prompt: str,
    web: bool,
    max_tool_rounds: int = 30,
) -> str:
    """
    ReAct agent loop: call Ollama chat with optional web_search / fetch_url tools.
    Returns the final review text.
    """
    try:
        import ollama as _ollama
    except ImportError:
        return "ollama package not found. Run: uv pip install ollama"

    tools = []
    tool_functions: dict = {}

    if web:
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "web_search",
                    "description": (
                        "Search the web for papers, authors, DOIs, or citation details. "
                        "Use this to verify bibliographic metadata or find missing references."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "Search query, e.g. 'Smith 2020 attention mechanism NeurIPS'",
                            }
                        },
                        "required": ["query"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "fetch_url",
                    "description": (
                        "Fetch the content of a URL. Use this to verify a DOI record, "
                        "check a publisher page, or read an abstract."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "url": {
                                "type": "string",
                                "description": "Full URL to fetch, e.g. 'https://doi.org/10.1234/example'",
                            }
                        },
                        "required": ["url"],
                    },
                },
            },
        ]
        tool_functions = {
            "web_search": lambda a: _web_search(a.get("query", "")),
            "fetch_url":  lambda a: _fetch_url(a.get("url", "")),
        }

    messages = [
        {"role": "system", "content": system_prompt},
        {
            "role": "user",
            "content": (
                "Please review the following paper according to your instructions.\n\n"
                f"=== PAPER TEXT ===\n{paper_text[:50_000]}"
            ),
        },
    ]

    for _round in range(max_tool_rounds):
        kwargs: dict = {"model": model, "messages": messages}
        if tools:
            kwargs["tools"] = tools

        resp = _ollama.chat(**kwargs)
        msg  = resp.message

        # Build the assistant message dict carefully
        asst: dict = {"role": "assistant", "content": msg.content or ""}
        if msg.tool_calls:
            asst["tool_calls"] = [
                {
                    "id": getattr(tc, "id", f"call_{i}"),
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    },
                }
                for i, tc in enumerate(msg.tool_calls)
            ]
        messages.append(asst)

        if not msg.tool_calls:
            return msg.content or ""

        # Execute each tool call and append results
        for i, tc in enumerate(msg.tool_calls):
            fn   = tc.function.name
            args = tc.function.arguments if isinstance(tc.function.arguments, dict) else {}
            result = tool_functions.get(fn, lambda _: f"Unknown tool: {fn}")(args)
            console.print(f"  [dim]→ {fn}({list(args.values())[0] if args else ''})[/]")
            messages.append({
                "role":       "tool",
                "tool_call_id": getattr(tc, "id", f"call_{i}"),
                "content":    str(result),
            })

    return "Review agent hit the maximum tool-call limit without finishing."


@app.command("paper-review")
def paper_review(
    pdf_file: Annotated[Path, typer.Argument(help="PDF manuscript to review")],
    model: Annotated[str, typer.Option("--model", "-m", help="Ollama model")] = "llama3.2",
    output: Annotated[Optional[Path], typer.Option("--output", "-o", help="Output markdown path")] = None,
    no_web: Annotated[bool, typer.Option("--no-web", help="Disable internet tools (offline mode)")] = False,
    max_chars: Annotated[int, typer.Option("--max-chars", help="Max PDF characters sent to the model")] = 50_000,
) -> None:
    """
    Generate a structured academic review of a PDF manuscript using a local Ollama model.

    The model is given web_search and fetch_url tools so it can verify citations
    and look up DOI records during the review (pass --no-web to disable).

    [bold]Examples:[/]

      t2s paper-review paper.pdf

      t2s paper-review paper.pdf --model qwen2.5:72b

      t2s paper-review paper.pdf --no-web --output review.md
    """
    import warnings as _warnings

    if not pdf_file.exists():
        _abort(f"File not found: {pdf_file}")
    if pdf_file.suffix.lower() != ".pdf":
        _abort(f"Expected a .pdf file, got: {pdf_file}")

    out_path = output or pdf_file.with_stem(pdf_file.stem + "_review").with_suffix(".md")

    # ── Step 1: extract PDF text ───────────────────────────────────────────────
    console.print(f"\n[bold]Step 1/2[/] Extracting text from [cyan]{pdf_file.name}[/]…")
    try:
        import pypdf as _pypdf
    except ImportError:
        _abort("pypdf is required. Run: uv pip install pypdf")

    with _warnings.catch_warnings():
        _warnings.simplefilter("ignore")
        reader = _pypdf.PdfReader(str(pdf_file))
        pages  = [p.extract_text() or "" for p in reader.pages]
    full_text = "\n\n--- PAGE BREAK ---\n\n".join(pages)
    console.print(f"  [green]✓[/] {len(reader.pages)} pages, {len(full_text):,} characters")

    # ── Step 2: run review agent ───────────────────────────────────────────────
    web_label = "[green]web tools ON[/]" if not no_web else "[yellow]web tools OFF (offline)[/]"
    console.print(f"\n[bold]Step 2/2[/] Reviewing with [green]{model}[/] — {web_label}…")
    if not no_web:
        console.print("  [dim]The model may call web_search / fetch_url to verify citations.[/]")

    # Load the review skill prompt from the bundled SKILL.md
    _skill_path = Path(__file__).parent.parent.parent / ".cursor" / "skills" / "ai-dm-paper-review" / "SKILL.md"
    if _skill_path.exists():
        raw_skill = _skill_path.read_text()
        # Strip the YAML front-matter (--- ... ---) if present
        import re as _re
        system_prompt = _re.sub(r"^---.*?---\s*", "", raw_skill, flags=_re.DOTALL).strip()
    else:
        # Fallback: embedded minimal prompt
        system_prompt = (
            "You are an expert academic reviewer. Produce a structured review covering: "
            "1. Summary, 2. Strengths, 3. Technical correctness, 4. Consistency, "
            "5. Clarity, 6. Research integrity, 7. Citations (verify online), "
            "8. Authenticity, 9. Novelty, 10. Fit for venue, 11. Gaps, "
            "12. Suggestions, 13. Overall score (1-10) and recommendation "
            "(Accept / Weak Accept / Borderline / Weak Reject / Reject)."
        )

    try:
        review_text = _run_review_agent(
            model=model,
            paper_text=full_text[:max_chars],
            system_prompt=system_prompt,
            web=not no_web,
        )
    except Exception as e:
        _abort(f"Review agent failed: {e}\nMake sure Ollama is running and '{model}' is pulled.")

    # ── Write output ───────────────────────────────────────────────────────────
    out_path.write_text(review_text, encoding="utf-8")
    console.print(
        Panel(
            f"[bold green]Review saved:[/] {out_path}\n"
            f"[dim]{model} · {len(review_text):,} characters[/]",
            border_style="green",
        )
    )
