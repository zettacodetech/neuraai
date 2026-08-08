"""chat — uzluksiz interaktiv suhbat rejimi.

Buyruqlar:
    - /exit, Ctrl+C  : chiqish
    - /new           : yangi suhbat (tarixni tozalaydi)
    - /model <nome>  : model almashtirish
    - /help          : yordam ro'yxati

Asosiy funksiya `run()` — `main.py` dan Typer orqali chaqiradi.
Beparvo bilan: `python -m neura_cli.commands.chat` ham ishlaydi.
"""

from __future__ import annotations

from rich.prompt import Prompt

from neura_cli import engine
from neura_cli.ui import console, print_markdown

_HELP_TEXT = (
    "Buyruqlar:\n"
    "  /exit  — chiqish\n"
    "  /new   — yangi suhbat (tarix tozalanadi)\n"
    "  /model <model> — model almashtirish\n"
    "  /help  — bu yordam\n"
)


def run(model: str | None = None) -> None:
    """Interaktiv suhbatni boshlaydi (tugatish uchun /exit yoki Ctrl+C)."""
    console.print("[bold cyan]Suhbat boshlandi. /exit — chiqish, /help — yordam[/]")
    if model:
        console.print(f"[dim]Model: {model}[/]")

    while True:
        try:
            q = Prompt.ask("[bold green]siz>[/]").strip()
        except (EOFError, KeyboardInterrupt):
            console.print("\n[blue]Xayr, yana kelib turing![/]")
            break

        if not q:
            continue
        if q in ("/exit", "/quit"):
            console.print("[blue]Xayr, yana kelib turing![/]")
            break
        if q == "/new":
            engine.clear_history()
            console.print("[dim]Yangi suhbat boshlandi.[/]")
            continue
        if q == "/help":
            console.print(_HELP_TEXT)
            continue
        if q.startswith("/model"):
            parts = q.split(maxsplit=1)
            if len(parts) < 2:
                console.print(_HELP_TEXT)
            else:
                model = parts[1].strip()
                console.print(f"[cyan]Model → {model}[/]")
            continue

        with console.status("Hal qilinmoqda...", spinner="dots12"):
            reply, source = engine.chat_reply(q, model=model or None)

        console.print(f"[dim]Manba: {source}[/]")
        print_markdown(reply)


def _standalone() -> None:
    """Paketdan tashqari bevosita ishga tushirish uchun Typer app."""
    import typer

    def entry(model: str | None = typer.Option(None, "--model", "-m")) -> None:
        run(model)

    typer.run(entry)


if __name__ == "__main__":
    _standalone()
