"""kilo — Kilo Code CLI (500+ model agent) orqali agentic kodlash.

Ishlatish:
    neura kilo                      # interaktiv TUI
    neura kilo "task"               # bir martalik (kilo run "task")

O'rnatish:  npm install -g @kilocode/cli
"""

from __future__ import annotations

import shutil
import subprocess

import typer

from neura_cli.ui import console

INSTALL_HINT = "Kilo o'rnatilmagan. O'rnatish:\n    npm install -g @kilocode/cli\n"


def run(
    prompt: str | None = typer.Argument(
        None, help="Bir martalik topshiriq (berilmasa interaktiv TUI)"
    ),
) -> int:
    """Kilo TUI'ni yoki bir martalik topshiriqni ishga tushiradi."""
    if not shutil.which("kilo"):
        console.print(f"[bold red]Xato:[/] {INSTALL_HINT}")
        return 1

    if prompt:
        console.print("[cyan]kilo run → topshiriq bajarilmoqda...[/]")
        return subprocess.call(["kilo", "run", prompt])
    return subprocess.call(["kilo"])
