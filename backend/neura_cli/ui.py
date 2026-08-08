"""Rich orqali chiroyli terminal chiqishi — umumiy UI yordamchilari.

Barcha chiqishlar shu modul orqali bo'ladi, shunda uslubni bir joyda
o'zgartirish mumkin (rang, banner, spinner turi va h.k.).
"""

from __future__ import annotations

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.syntax import Syntax
from rich.text import Text

console = Console()

BANNER = r"""
███╗   ██╗███████╗██╗   ██╗██████╗  █████╗     █████╗ ██╗
████╗  ██║██╔════╝██║   ██║██╔══██╗██╔══██╗   ██╔══██╗██║
██╔██╗ ██║█████╗  ██║   ██║██████╔╝███████║   ███████║██║
██║╚██╗██║██╔══╝  ██║   ██║██╔══██╗██╔══██║   ██╔══██║██║
██║ ╚████║███████╗╚██████╔╝██║  ██║██║  ██║██╗██║  ██║██║
╚═╝  ╚═══╝╚══════╝ ╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═╝╚═╝╚═╝  ╚═╝╚═╝
"""


def show_banner() -> None:
    """Dastur boshlanishidagi banner."""
    console.print(Text(BANNER, style="bold cyan"))
    console.print(
        Panel(
            "Terminaldagi aqlli suhbatdosh va kod yordamchisi",
            border_style="blue",
        )
    )


def print_markdown(text: str) -> None:
    """Markdown'ni terminalga chiqaradi (kod bloklarini ham qo'llab)."""
    console.print(Markdown(text))


def print_syntax(code: str, lang: str = "python") -> None:
    """Kodni sintaksis bo'yalgan holda chiqaradi."""
    console.print(Syntax(code, lang, theme="monokai", word_wrap=True))


def print_diff(before: str, after: str, filename: str) -> None:
    """Ikki variant o'rtasidagi farqni chiroyli ko'rsatadi."""
    import difflib

    diff = difflib.unified_diff(
        before.splitlines(keepends=True),
        after.splitlines(keepends=True),
        fromfile=f"a/{filename}",
        tofile=f"b/{filename}",
    )
    console.print("".join(diff), style="yellow")


def confirm_save() -> bool:
    """Foydalanuvchidan tuzatilgan faylni saqlashga rozilik so'raydi."""
    return console.input("[bold green]Faylni saqlashmi? [y/N]: ").strip().lower() in (
        "y",
        "yes",
    )
