"""Neura CLI — Typer + Rich asosidagi terminal yordamchisi.

Komaqalar to'g'ridan `cli`'ga ulangan, lekin har biri alohida modulda
yashaydi (`commands/chat.py`, `commands/fix.py`). Yangi buyruq qo'shish:

    1. `commands/yangi.py` yarating va `run` funksiyasini yozing.
    2. `main.py` ga:  `from neura_cli.commands import yangi`
       va `register_yangi(cli)` qo'ying (yoki `@cli.command()` ishlating).
"""

import sys
from functools import wraps

import typer

from neura_cli.commands import aider, chat, fix, kilo, ollama, opencode
from neura_cli.ui import show_banner


def _exitcode(fn):
    """Funksiya qaytargan int'ni Typer exit code'iga aylantiradi."""

    @wraps(fn)
    def wrapped(*args, **kwargs) -> None:
        code = fn(*args, **kwargs)
        if isinstance(code, int) and code:
            raise typer.Exit(code=code)

    return wrapped


cli = typer.Typer(
    name="neura",
    help="Neura AI — terminaldagi aqlli suhbatdosh va kod yordamchisi.",
    no_args_is_help=True,
)

cli.command(name="chat", help="Interaktiv suhbat")(_exitcode(chat.run))
cli.command(name="fix", help="Faylni tahlil qilib, tuzatish taklif qiladi")(
    _exitcode(fix.run)
)
cli.command(
    name="opencode", help="OpenCode CLI agent (TUI yoki bir martalik topshiriq)"
)(_exitcode(opencode.run))
cli.command(name="kilo", help="Kilo Code CLI agent (TUI yoki bir martalik topshiriq)")(
    _exitcode(kilo.run)
)
cli.command(name="aider", help="Aider AI pair programmer (fayl asosida)")(
    _exitcode(aider.run)
)
cli.command(name="ollama", help="Mahalliy Ollama modellar (list/pull/run/status)")(
    _exitcode(ollama.run)
)


@cli.callback(invoke_without_command=True)
def main(ctx: typer.Context) -> None:
    """Kirish nuqtasi — buyruqsiz chaqirilsa, banner va yo'l ko'rsatadi."""
    if ctx.invoked_subcommand is None:
        show_banner()
        sys.exit(0)


if __name__ == "__main__":
    cli()
