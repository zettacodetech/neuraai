"""fix <filename> — faylni o'qib, AI orqali tuzatish taklif qiladi.

Xatolik bilan ishlash:
    - Fayl topilmasa → chiroyli xato, exit code 1.
    - Direktoriya berilsa → xato (fayl emas).
    - Kod o'qib bo'lmasa (encoding) → aniq xabar.

Saqlash: tuzatilgan kodni faylga yozish taklif etiladi (ruxsat bilan).

Asgi funksiya `run()` — `main.py` Typer orqali ulaydi.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from rich.markup import escape

from neura_cli import engine
from neura_cli.ui import (
    console,
    confirm_save,
    print_diff,
    print_syntax,
)


def _read_file(path: Path) -> str:
    """Faylni o'qish: encoding xatolarda fallback."""
    for enc in ("utf-8", "latin-1"):
        try:
            return path.read_text(encoding=enc)
        except UnicodeDecodeError:
            continue
    raise ValueError(f"Fayl o'qib bo'lmadi (kodlash noma'lum): {path}")


def run(filename: str, model: str | None = None, save: bool = False) -> int:
    """Faylni tahlil qilib, tuzatilgan kod + diff ko'rsatadi. 0/1 qaytaradi."""
    path = Path(filename)

    # --- 1. Xatolik tekshirish: mavjudlik va turi ---
    if not path.exists():
        console.print(f"[bold red]Xato:[/] '{escape(filename)}' topilmadi!")
        console.print(f"[dim]Ishchi papka: {os.getcwd()}[/]")
        return 1
    if path.is_dir():
        console.print(
            f"[bold red]Xato:[/] '{escape(filename)}' — bu papka, fayl bering."
        )
        return 1

    # --- 2. O'qish ---
    try:
        original = _read_file(path)
    except ValueError as exc:
        console.print(f"[bold red]Xato:[/] {exc}")
        return 1
    if not original.strip():
        console.print("[yellow]Ogohlantirish:[/] fayl bo'sh — tuzatishga narsa yo'q.")
        return 1

    # --- 3. Turini aniqlash (Syntax bo'yash uchun) ---
    lang = path.suffix.lstrip(".") or "text"
    console.print(
        f"[bold green]→[/] Tahlil: {escape(filename)} ({len(original)} belgi)"
    )

    # --- 4. LLM so'rov ---
    with console.status("AI tahlil qilyapti...", spinner="dots"):
        fixed = engine.fix_code(original, filename, model=model or None)

    if not fixed:
        console.print(
            "[bold yellow]Tuzatish olinmadi[/] — LLM provideri javob bermadi "
            "(NEURA_LLM_API_KEY sozlanishi kerak)."
        )
        return 1

    # --- 5. Natija ---
    cleaned = fixed.strip()
    console.print("\n[bold cyan]Tuzatilgan natija:[/]")
    print_syntax(cleaned, lang)

    if cleaned != original.strip():
        console.print("\n[bold cyan]Farq (diff):[/]")
        print_diff(original, cleaned + "\n", str(path))
    else:
        console.print("[dim]Kodda o'zgarish aniqlanmadi.[/]")

    # --- 6. Saqlash ---
    if save:
        path.write_text(cleaned + "\n", encoding="utf-8")
        console.print(f"[bold green]Saqlab qo'yildi:[/] {escape(filename)}")
    elif confirm_save():
        path.write_text(cleaned + "\n", encoding="utf-8")
        console.print(f"[bold green]Saqlab qo'yildi:[/] {escape(filename)}")
    else:
        console.print("[dim]O'zgarishlar saqlanmadi.[/]")
    return 0


def _standalone() -> None:
    """Paketdan tashqari bevosita ishga tushirish uchun Typer app."""
    import typer

    def entry(
        filename: str = typer.Argument(..., help="Tuzatish kerak bo'lgan fayl"),
        model: str | None = typer.Option(None, "--model", "-m"),
        save: bool = typer.Option(False, "--save", "-s", help="Avtomatik saqlash"),
    ) -> None:
        raise typer.Exit(run(filename, model, save))

    typer.run(entry)


if __name__ == "__main__":
    _standalone()
