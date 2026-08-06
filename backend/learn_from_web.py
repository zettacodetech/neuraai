"""Internet (Google/DDG) qidiruv orqali bilim bazasini o'qitadi.

Ishlatish:
    ./venv/bin/python learn_from_web.py [topics_file]

topics_file — har satrda bitta savol/javob yo'nalishi. Agar berilmasa,
QUESTS ro'yxati ishlatiladi.
"""

import sys
import time

from db import get_db
from websearch import search_answer

QUESTS = [
    "O'zbekiston aholisi nechchi million",
    "2026 yilda O'zbekistonda eng ko'p ishlatiladigan internet xizmatlar",
    "Toshkent metrosida nechta stansiya bor",
    "O'zbek tilining rasmiy maqomi",
    "Palov qanday tayyorlanadi asosiy masalliqlar",
    "Uzbekistonda IT sohasi maoshi qancha",
    "Samarqand tarixiy obidalari",
    "Android dasturlashni qayerdan o'rganish mumkin",
    "O'zbekiston milliy valyutasi",
    "2025 yil O'zbekiston yalpi ichki mahsuloti",
    "O'zbekistonda universitetlar soni",
    "Ilon Muso kim va nima qilgan",
    "Python dasturlash tili kim tomonidan yaratilgan",
    "ChatGPT nima",
    "O'zbekistonning eng baland tog'i",
    "Arslonbob yong'og'i nima bilan mashhur",
]


def learn_from_web(db, questions: list[str], delay: float = 3.0) -> int:
    added = 0
    existing = {r["question"] for r in db.get_knowledge()}
    for q in questions:
        q = q.strip()
        if not q or q in existing:
            continue
        answer = search_answer(q, 3)
        time.sleep(delay)
        if not answer:
            continue
        if db.add_knowledge(q, answer, source="web"):
            added += 1
    return added


def main() -> None:
    db = get_db()
    if len(sys.argv) > 1:
        with open(sys.argv[1], encoding="utf-8") as f:
            questions = [line for line in f.read().splitlines() if line.strip()]
    else:
        questions = QUESTS
    n = learn_from_web(db, questions)
    print(f"O'rganildi: {n} ta savol-javob bilim bazasiga qo'shildi.")


if __name__ == "__main__":
    main()
