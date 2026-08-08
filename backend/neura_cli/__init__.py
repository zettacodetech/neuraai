"""Neura CLI — Typer + Rich asosidagi terminal yordamchisi.

Yangi buyruq qo'shish uchun:
    1. Bu papkada yangi modul yarating (masalan: `todo.py`).
    2. Modul ichida `@app.command()` dekoratori bilan funksiya yozing.
    3. `main.py` dagi `cli` funksiyasiga callback-registry qo'shing
       yoki komanda funksiyasini `cli.add_typer(...)` bilan ulang.

Misol:
    @cli.command("todo")
    def todo(item: str = typer.Argument(...)):
        \"\"\"Yangi reja qo'shadi.\"\"\"
        engine.append_todo(item)
"""
