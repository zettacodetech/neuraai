"""aider — Aider AI pair programmer orqali fayl asosida kodlash.

Ishlatish:
    neura aider app.py              # fayllar bilan interaktiv
    neura aider "task" "app.py"     # topshiriq + fayllar (--message)

O'rnatish:  pip install aider-chat   (kalit: OPENAI_API_KEY yoki ANTHROPIC_API_KEY)
"""

from __future__ import annotations

import shutil
import subprocess

import typer

from neura_cli.ui import console

INSTALL_HINT = "Aider o'rnatilmagan. O'rnatish:\n    pip install aider-chat\n"


def run(
    files: list[str] = typer.Argument(None, help="Ishlanadigan fayllar (ixtiyoriy)"),
    message: str | None = typer.Option(
        None, "--message", "-m", help="Bir martalik topshiriq"
    ),
) -> int:
    """Aider'ni ishga tushiradi (interaktiv yoki --message bilan)."""
    if not shutil.which("aider"):
        console.print(f"[bold red]Xato:[/] {INSTALL_HINT}")
        return 1

    cmd = ["aider"]
    if message:
        cmd += ["--message", message]
    if files:
        cmd += list(files)
    console.print("[cyan]aider ishga tushyapti...[/]")
    return subprocess.call(cmd)
