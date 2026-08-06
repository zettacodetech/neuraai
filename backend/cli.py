#!/usr/bin/env python3
"""CLI — terminaldan Neura AI ga murojaat.

Ishlatish:
    ./venv/bin/python cli.py "Savolingiz"
    ./venv/bin/python cli.py --chat        # interaktiv suhbat
    ./venv/bin/python cli.py --image rasm.jpg   # rasm tahlili
    ./venv/bin/python cli.py --gen-image "kosmos"   # rasm yaratish
    ./venv/bin/python cli.py --gen-video "panorama" # video yaratish
    ./venv/bin/python cli.py --stats       # bilim bazasi statistikasi
"""

import argparse
import json
import sys

from brain import brain
from db import get_db


def one_shot(message: str) -> None:
    db = get_db()
    reply, source = brain.answer(message, db.get_knowledge())
    print(reply)
    if source == "fallback":
        print("\n[ℹ] Savol o'rganish ro'yxatiga qo'shildi.")


def chat_mode() -> None:
    db = get_db()
    print("Neura AI CLI — chiqish uchun: exit | yangi suhbat: new")
    conv_id = None
    user_id = db.get_or_create_user()
    while True:
        try:
            q = input("siz> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if q.lower() in ("exit", "quit", "chiqish"):
            break
        if q.lower() == "new":
            conv_id = None
            print("ai> ✨ Yangi suhbat boshlandi.")
            continue
        if not q:
            continue
        if conv_id is None:
            conv_id = db.create_conversation(user_id, q)
        db.add_message(user_id, "user", q, conversation_id=conv_id)
        reply, source = brain.answer(q, db.get_knowledge())
        msg_id = db.add_message(
            user_id, "assistant", reply, source=source, conversation_id=conv_id
        )
        if source == "fallback":
            db.add_unanswered(q, user_id)
        print(f"ai> {reply}")

        while True:
            try:
                fb = (
                    input("     (👍 yaxshi / 👎 yomon / [enter] davom) ")
                    .strip()
                    .lower()
                )
            except (EOFError, KeyboardInterrupt):
                print()
                break
            if fb in ("+", "1", "yaxshi", "👍", "ha"):
                db.rate_message(msg_id, 1)
                print("     O'rganildi, rahmat! ✅")
                break
            if fb in ("-", "0", "yomon", "👎", "yo'q"):
                db.rate_message(msg_id, -1)
                print("     Qayd etildi. ❌")
                break
            if fb in ("", "davom", "keyin"):
                break


def stats() -> None:
    db = get_db()
    k = db.get_knowledge()
    print(f"Bilim bazasi: {len(k)} ta javob")
    print(f"O'rganish navbati: {len(db.get_unanswered())} ta savol")


def main() -> None:
    parser = argparse.ArgumentParser(description="Neura AI CLI")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("message", nargs="?", help="bir martalik savol")
    group.add_argument("--chat", action="store_true", help="interaktiv suhbat")
    group.add_argument("--image", metavar="PATH", help="rasm tahlili")
    group.add_argument("--gen-image", metavar="PROMPT", help="prompt'dan rasm yaratish")
    group.add_argument(
        "--gen-video", metavar="PROMPT", help="prompt'dan video yaratish"
    )
    group.add_argument("--stats", action="store_true", help="statistika")
    args = parser.parse_args()

    if args.chat:
        chat_mode()
    elif args.image:
        from vision import analyze

        print(json.dumps(analyze(args.image), ensure_ascii=False, indent=2))
    elif args.gen_image or args.gen_video:
        from gen import generate_image, generate_video

        if args.gen_image:
            path = generate_image(args.gen_image)
            print(f"Rasm tayyor: {path}")
        else:
            path = generate_video(args.gen_video)
            print(f"Video tayyor: {path}")
    elif args.stats:
        stats()
    elif args.message:
        one_shot(args.message)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
