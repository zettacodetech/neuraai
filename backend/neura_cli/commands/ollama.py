"""ollama — mahalliy Ollama server orqali model ishga tushirish.

Ishlatish:
    neura ollama list               # o'rnatilgan modellar
    neura ollama pull qwen2.5:3b    # model yuklab olish
    neura ollama run qwen2.5:3b "savol"   # model bilan suhbat
    neura ollama status             # server holati

Ollama o'rnatilgan bo'lmasa, server ham ishga tushmaydi.
Railway'da GPU yo'q — kichik modellar (qwen2.5:0.5b, phi3:mini) tez ishlaydi.
"""

from __future__ import annotations

import shutil
import subprocess
import urllib.request

import typer
from rich.table import Table

from neura_cli.ui import console

OLLAMA_URL = "http://127.0.0.1:11434"

INSTALL_HINT = (
    "Ollama o'rnatilmagan. O'rnatish:\n"
    "    curl -fsSL https://ollama.com/install.sh | sh\n"
)


def _server_alive() -> bool:
    """Ollama server ishlayotganini tekshiradi."""
    try:
        urllib.request.urlopen(f"{OLLAMA_URL}/api/tags", timeout=3)
        return True
    except Exception:
        return False


def run(
    action: str = typer.Argument("list"),
    arg: str | None = typer.Argument(None),
) -> int:
    """Ollama boshqarish: list | pull | run | status."""
    if not shutil.which("ollama"):
        console.print(f"[bold red]Xato:[/] {INSTALL_HINT}")
        return 1

    action = (action or "list").lower()

    if action == "status":
        if _server_alive():
            console.print("[bold green]Ollama server ishlayapti[/]")
            return 0
        console.print(
            "[bold yellow]Ollama server ishlamayapti — 'ollama serve' boshlang.[/]"
        )
        return 1

    if not _server_alive():
        console.print(
            "[bold yellow]Ollama server ishlamayapti — 'ollama serve' boshlang, keyin qaytaring.[/]"
        )
        return 1

    if action == "list":
        out = subprocess.run(["ollama", "list"], capture_output=True, text=True)
        table = Table(title="Ollama modellar", show_lines=True)
        table.add_column("Model", style="cyan")
        table.add_column("Hajmi", style="green")
        table.add_column("O'zgartirilgan", style="dim")
        for line in out.stdout.strip().splitlines()[1:]:
            cols = line.split()
            if len(cols) >= 3:
                table.add_row(cols[0], cols[1], " ".join(cols[2:]))
        console.print(table)
        return 0

    if action == "pull":
        if not arg:
            console.print(
                "[bold red]Xato:[/] model nomi kerak: neura ollama pull qwen2.5:3b"
            )
            return 1
        console.print(f"[cyan]Model yuklab olinmoqda: {arg}...[/]")
        return subprocess.call(["ollama", "pull", arg])

    if action == "run":
        if not arg:
            console.print(
                "[bold red]Xato:[/] model nomi kerak: neura ollama run qwen2.5:3b"
            )
            return 1
        return subprocess.call(["ollama", "run", arg])

    console.print(f"[bold red]Xato:[/] noma'lum amal '{action}' (list|pull|run|status)")
    return 1
