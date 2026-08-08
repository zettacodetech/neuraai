"""opencode — OpenCode CLI (terminal agent) orqali agentic kodlash.

Ishlatish:
    neura opencode                 # interaktiv TUI (o'zining UI bilan)
    neura opencode "task"          # bir martalik topshiriq (opencode run)

OpenCode yuklanmagan bo'lsa, uni o'rnatish bo'yicha ko'rsatma beriladi.
"""

from __future__ import annotations

import shutil
import subprocess

import typer

from neura_cli.ui import console

INSTALL_HINT = (
    "OpenCode o'rnatilmagan. O'rnatish:\n"
    "    curl -fsSL https://opencode.ai/install | bash\n"
    "yoki:  npm install -g opencode-ai\n"
)


def run(
    prompt: str | None = typer.Argument(
        None, help="Bir martalik topshiriq (berilmasa interaktiv TUI)"
    ),
) -> int:
    """OpenCode TUI'ni yoki bir martalik topshiriqni ishga tushiradi."""
    if not shutil.which("opencode"):
        console.print(f"[bold red]Xato:[/] {INSTALL_HINT}")
        return 1

    if prompt:
        console.print("[cyan]opencode run → topshiriq bajarilmoqda...[/]")
        return subprocess.call(["opencode", "run", prompt])
    return subprocess.call(["opencode"])
