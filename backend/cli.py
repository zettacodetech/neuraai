#!/usr/bin/env python3
"""Inomjon AI CLI — terminaldagi aqlli suhbatdosh.

Ishlatish:
    python cli.py "Savolingiz"            # bir martalik savol (⚡ tez model)
    python cli.py --chat                  # interaktiv suhbat
    python cli.py --model think "Savol"   # model tanlash: fast | think
    python cli.py --image rasm.jpg        # rasm tahlili
    python cli.py --gen-image "kosmos"    # rasm yaratish
    python cli.py --gen-video "panorama"  # video yaratish
    python cli.py --stats                 # statistika
"""

import argparse
import json
import os
import sys

from brain import brain
from db import get_db

DARK = "\033[90m"
BOLD = "\033[1m"
RESET = "\033[0m"
GREEN = "\033[32m"
CYAN = "\033[36m"
YELLOW = "\033[33m"
RED = "\033[31m"
MAG = "\033[35m"

BANNER = rf"""
{GREEN}   ╔══════════════════════════════════════════════════════════╗
   ║                                                          ║
   ║   {CYAN}██████╗ ███████╗██╗   ██╗██████╗  █████╗ ██╗{GREEN}           ║
   ║   {CYAN}██╔══██╗██╔════╝ ██║   ██║██╔══██╗██╔══██╗██║{GREEN}           ║
   ║   {CYAN}██████╔╝█████╗   ██║   ██║██████╔╝███████║██║{GREEN}           ║
   ║   {CYAN}██╔══██╗██╔══╝   ██║   ██║██╔══██╗██╔══██║██║{GREEN}           ║
   ║   {CYAN}██║  ██║███████╗ ╚██████╔╝██║  ██║██║  ██║██║{GREEN}           ║
   ║   {CYAN}╚═╝  ╚═╝╚══════╝  ╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═╝╚═╝{GREEN}           ║
   ║                                                              ║
   ║   {YELLOW}Sun'iy intellekt yordamchingiz — terminalda  {GREEN}✦ {YELLOW}v2{GREEN}   ║
   ╚══════════════════════════════════════════════════════════════╝{RESET}
"""

MODELS = {
    "fast": "gemini-flash-latest ⚡ (1–3s)",
    "think": "command-a-plus-05-2026 🧠 (aniq, 5–6s)",
}


def one_shot(message: str, model: str = "fast") -> None:
    db = get_db()
    reply, source = brain.answer(message, db.get_knowledge(), model=model)
    print(f"\n{reply}\n")
    if source == "fallback":
        print(f"{DARK}[ℹ] Savol o'rganish ro'yxatiga qo'shildi.{RESET}")


def chat_mode(model: str) -> None:
    db = get_db()
    print(BANNER)
    print(
        f"{DARK}🎛  Model: {MODELS[model]}   (almashtirish: /model fast yoki /model think)"
    )
    print(
        f"{DARK}📝 Buyruqlar: exit (chiqish) · new (yangi suhbat) · /model <fast|think>{RESET}\n"
    )

    conv_id = None
    user_id = db.get_or_create_user()

    def prompt():
        print(f"{GREEN}siz>{RESET} ", end="", flush=True)

    while True:
        try:
            prompt()
            q = input().strip()
        except (EOFError, KeyboardInterrupt):
            print(f"\n{RESET}{GREEN}👋 Xayr! Yana kelib turing.{RESET}")
            break
        low = q.lower()
        if low in ("exit", "quit", "chiqish"):
            print(f"{GREEN}👋 Xayr!{RESET}")
            break
        if low == "new":
            conv_id = None
            print(f"{CYAN}ai> ✨ Yangi suhbat boshlandi.{RESET}")
            continue
        if low.startswith("/model"):
            parts = q.split()
            if len(parts) > 1 and parts[1].lower() in MODELS:
                model = parts[1].lower()
                print(f"{CYAN}ai> ✅ Model: {MODELS[model]}{RESET}")
            else:
                print(f"{CYAN}ai> Mavjud modellar:{RESET}")
                for k, v in MODELS.items():
                    mark = " →" if k == model else ""
                    print(f"   {k}: {v}{mark}")
            continue
        if low in ("/help", "yordam"):
            print(f"{CYAN}ai> Nima qila olaman:{RESET}")
            print("   • Istalgan savolga javob beraman")
            print("   • Kod yozaman (masalan: 'telegram bot yoz')")
            print("   • Rasm tahlil qilaman (--image)")
            print("   • Yangi rasm/video yarataman (--gen-image --gen-video)")
            print("   • Internetdan izlayman")
            continue
        if not q:
            continue

        if conv_id is None:
            conv_id = db.create_conversation(user_id, q)
        db.add_message(user_id, "user", q, conversation_id=conv_id)

        print(f"{CYAN}ai> (o'ylayabdi…){RESET}")
        try:
            reply, source = brain.answer(q, db.get_knowledge(), model=model)
        except Exception as e:
            reply, source = (f"⚠️ Xatolik: {e}", "fallback")
        msg_id = db.add_message(
            user_id, "assistant", reply, source=source, conversation_id=conv_id
        )
        if source == "fallback":
            db.add_unanswered(q, user_id)
        print(f"{MAG}ai> {reply}{RESET}")

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
                print(f"     {GREEN}O'rganildi, rahmat! ✅{RESET}")
                break
            if fb in ("-", "0", "yomon", "👎", "yo'q"):
                db.rate_message(msg_id, -1)
                print(f"     {RED}Qayd etildi. ❌{RESET}")
                break
            if fb in ("", "davom", "keyin"):
                break


def _stats() -> None:
    db = get_db()
    k = db.get_knowledge()
    print(BANNER)
    print(f"Bilim bazasi: {len(k)} ta javob")
    print(f"O'rganish navbati: {len(db.get_unanswered())} ta savol")
    print(f"Model: fast → {MODELS['fast']} | think → {MODELS['think']}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Inomjon AI CLI — terminal'dan sun'iy intellekt",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Yuklab olish / o'rnatish:
  git clone https://github.com/zettacodetech/neuraai
  cd neuraai && pip install -r requirements.txt
  python backend/cli.py --chat
""",
    )
    parser.add_argument("message", nargs="?", help="bir martalik savol")
    parser.add_argument("--chat", action="store_true", help="interaktiv suhbat")
    parser.add_argument(
        "--model",
        choices=["fast", "think"],
        default="fast",
        help="model: fast (tez) | think (aniq)",
    )
    parser.add_argument("--image", metavar="PATH", help="rasm tahlili")
    parser.add_argument(
        "--gen-image", metavar="PROMPT", help="prompt' dan rasm yaratish"
    )
    parser.add_argument(
        "--gen-video", metavar="PROMPT", help="prompt'dan video yaratish"
    )
    parser.add_argument("--stats", action="store_true", help="statistika")
    args = parser.parse_args()

    model = args.model
    if args.chat:
        chat_mode(model)
    elif args.image:
        from vision import analyze

        print(json.dumps(analyze(args.image), ensure_ascii=False, indent=2))
    elif args.gen_image or args.gen_video:
        from gen import generate_image, generate_video

        if args.gen_image:
            print(BANNER)
            path = generate_image(args.gen_image)
            print(f"Rasm tayyor: {path}")
        else:
            print(BANNER)
            path = generate_video(args.gen_video)
            print(f"Video tayyor: {path}")
    elif args.stats:
        _stats()
    elif args.message:
        if not sys.stdin.isatty():
            one_shot(args.message, model)
        else:
            print(BANNER)
            one_shot(args.message, model)
    else:
        print(BANNER)
        print(
            f"{YELLOW}Mavjud model: ⚡ fast → {MODELS['fast']} | 🧠 think → {MODELS['think']}{RESET}"
        )
        print()
        parser.print_help()


if __name__ == "__main__":
    import sys

    main()
