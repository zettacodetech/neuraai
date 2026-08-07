"""Faza 5: Rasm va video generatsiya.

Ikkita rejim:
1. GPU + torch mavjud (Railway L40S) — Stable Diffusion (SDXL-Turbo) va
   Stable Video Diffusion (img2vid) bilan haqiqiy generatsiya.
2. Model yo'q (CPU / oddiy plan) — o'zimizning protsural (algoritmik)
   generatsiya: savol hashidan rang palitrasi olib, abstrakt rasm va pan
   animatsiyasi yaratamiz. Har qanday plan API ishdan chiqmaydi —
   GPU bo'lsa sifati oshadi.
"""

import hashlib
import os
import time

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

_OUT_DIR = os.environ.get(
    "GEN_OUT_DIR",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "gen"),
)
os.makedirs(_OUT_DIR, exist_ok=True)


def _seed(text: str) -> int:
    return int(hashlib.sha256(text.encode("utf-8")).hexdigest()[:8], 16)


_translate_cache: dict[str, str] = {}

_UZ_HINTS = frozenset(
    """
    va bilan uchun haqida lekin ammo yoki xoh
    yangi katta kichik chiroyli go'zal ajoyib bejirim toza
    quyosh botishi chiqishi tog' daryo o'rmon dengiz osmon bulut yulduz
    kecha tong ertalab kun oy yil bahor yoz kuz qish shahar qishloq
    uy daraxt gul bog' bog'cha qor yomg'ir shamol suv qoya tosh yo'l ko'prik
    ona ota bola qiz o'g'il odam inson ayol erkak hayvon it mushuk qush ot
    cho'l sahro o'rik olma non choy meva sabzavot qovun tarvuz uzum baliq
    rasm surat tasvir chiz chizing chizib yarat yarating yasa yasang qo'sh
    ko'rsat qanday nega nima kim qayerda qachon nechta menga senga
    o'zbek o'zbekcha toshkent samarqand buxoro xiva andijon namangan
    milliy cholg'u do'st do'stlar bolalar oila bizning mana endi hozir
    salom rahmat iltimos yaxshi yomon yo'q ha bu u shu o'sha
    """.split()
)


def _looks_english(text: str) -> bool:
    """Inglizcha bo'lishi aniq bo'lsa True.

    O'zbek lotin yozuvi ham ASCII — shuning uchun faqat belgiga emas,
    O'zbekcha kalit so'zlarga ham qaraymiz.
    """
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return True
    non_ascii = sum(1 for c in letters if ord(c) > 127)
    if non_ascii / len(letters) > 0.15:
        return False
    words = set(w.strip(".,!?;:'\"()[]{}") for w in text.lower().split())
    return not (words & _UZ_HINTS)


_META_PHRASES = (
    "the task",
    "translate the user",
    "keep every object",
    "preserving every",
    "the instruction",
    "the user wrote",
    "image request",
    "no analysis",
    "only the translated",
)


def _clean_translation(out: str) -> str:
    """Fikrlash/tahlil qismini olib, faqat tarjima qismini qoldirish."""
    out = (out or "").strip()
    for marker in (
        "The user wrote",
        "Let's parse",
        "Possibly means",
        "Actually",
        "This appears",
        "So the phrase",
        "We need to",
        "The instruction",
        "The task",
        "Always preserve",
        "Therefore",
        "is playing?",
        "Hmm",
    ):
        idx = out.lower().find(marker.lower())
        if idx >= 0:
            out = out[:idx]
            break
    if out.count('"') >= 2:
        i1, i2 = out.find('"'), out.rfind('"')
        if i2 > i1:
            out = out[i1 + 1 : i2]
    out = out.strip().strip("()[]'\" ")
    lines = [ln.strip() for ln in out.splitlines() if ln.strip()]
    if lines:
        lines = [
            ln
            for ln in lines
            if not ln.lower().startswith(("you ", "the user", "possible", "task"))
        ]
        out = lines[0] if lines else out
    return out[:400]


def _is_meta(out: str) -> bool:
    low = out.lower()
    return any(p in low for p in _META_PHRASES) or len(out) > 200


def _english_prompt(prompt: str) -> str:
    """Uzbek/o'zbekcha promptni inglizchaga tarjima qilib beradi.

    AI rasm/video modellari inglizcha promptni aniq tushunadi. Manba va boshqa
    tillardagi so'rovlar avval chiqarish provayderi orqali inglizchaga
    o'tkaziladi (2 ta urinish); ikkalasi ham bo'lmasa — asl prompt qaytariladi.
    """
    prompt = (prompt or "").strip()
    if _looks_english(prompt):
        return prompt
    if prompt in _translate_cache:
        return _translate_cache[prompt]
    from llm import llm_chat

    messages = [
        {
            "role": "system",
            "content": (
                "You are a precise, faithful translator for image generation. "
                "Translate the user's image request into English. "
                "Keep EVERY object, noun, place, and adjective from the original "
                "(e.g. mountains, river, sun, buildings). "
                "Reply with ONLY the translated English phrase in ONE short "
                "sentence. No analysis, no quotes, no explanation."
            ),
        },
        {"role": "user", "content": prompt},
    ]
    fast_model = os.environ.get("NEURA_FAST_MODEL", "").strip()
    for _ in range(2):
        try:
            out = _clean_translation(
                llm_chat(
                    messages,
                    temperature=0.2,
                    max_tokens=250,
                    model=fast_model or None,
                )
                or ""
            )
        except Exception:
            break
        if out and not _is_meta(out) and out.lower() != prompt.lower():
            letters = [c for c in out if c.isalpha()]
            if letters:
                non_ascii = sum(1 for c in letters if ord(c) > 127)
                if non_ascii / len(letters) <= 0.15:
                    _translate_cache[prompt] = out
                    return out
    return prompt


def _available() -> bool:
    """CUDA GPU mavjudmi?"""
    try:
        import torch

        return bool(torch.cuda.is_available())
    except Exception:
        return False


# ================= protsurul (model siz) =================


def _hsv_to_rgb(h, s, v):
    h = h % 1.0
    i = int(h * 6)
    f = h * 6 - i
    p = v * (1 - s)
    q = v * (1 - f * s)
    t = v * (1 - (1 - f) * s)
    return [(v, t, p), (q, v, p), (p, v, t), (p, q, v), (t, p, v), (v, p, q)][i % 6]


def _palette(seed):
    rng = np.random.RandomState(seed)
    hue = rng.rand()
    return (
        tuple(int(c * 255) for c in _hsv_to_rgb(hue, 0.9, 0.16)),
        tuple(int(c * 255) for c in _hsv_to_rgb((hue + 0.14) % 1, 0.75, 0.45)),
        (255, 214, 120),
        tuple(int(c * 255) for c in _hsv_to_rgb((hue + 0.34) % 1, 0.6, 0.7)),
    )


def _flow(prompt: str, size: tuple[int, int] = (512, 512)) -> Image.Image:
    """Savol hashidan rang palitrasi + gradient + loyqa dog'lar (abstrakt)."""
    seed = _seed(prompt)
    rng = np.random.RandomState(seed)
    w, h = size
    c1, c2, gold, c4 = _palette(seed)

    img = Image.new("RGB", (w, h), c1)
    grad = Image.new("L", (1, h))
    for y in range(h):
        grad.putpixel((0, y), int(60 + 195 * y / h))
    img = Image.composite(Image.new("RGB", (w, h), c2), img, grad.resize((w, h)))

    layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    for i in range(6):
        x = rng.randint(-w // 4, w)
        y = rng.randint(-h // 4, h)
        r = rng.randint(w // 6, w // 2)
        color = [c1, c2, gold, c4][i % 4]
        draw.ellipse((x, y, x + r, y + r), fill=color + (rng.randint(90, 160),))
    layer = layer.filter(ImageFilter.GaussianBlur(radius=40))
    img = Image.alpha_composite(img.convert("RGBA"), layer).convert("RGB")

    noise = Image.new("RGBA", (w, h))
    nd = ImageDraw.Draw(noise)
    for _ in range(900):
        x = rng.randint(0, w)
        y = rng.randint(0, h)
        v = rng.randint(180, 255)
        nd.point((x, y), fill=(v, v, v, 90))
    noise = noise.filter(ImageFilter.GaussianBlur(radius=1))
    img = Image.alpha_composite(img.convert("RGBA"), noise).convert("RGB")
    return img


def _text_overlay(img: Image.Image, prompt: str) -> Image.Image:
    d = ImageDraw.Draw(img)
    txt = (prompt[:60] + "…") if len(prompt) > 60 else prompt
    d.text((16, 16), txt, fill=(255, 255, 255, 200))
    return img


# ================= Stable Diffusion (GPU) =================

_pipe_sd = None
_pipe_svd = None


def _load_sd():
    global _pipe_sd
    from diffusers import StableDiffusionXLPipeline
    import torch

    if _pipe_sd is None:
        _pipe_sd = StableDiffusionXLPipeline.from_pretrained(
            "stabilityai/sdxl-turbo", torch_dtype=torch.float16, variant="fp16"
        )
        _pipe_sd.to("cuda")
        _pipe_sd.set_progress_bar_config(disable=True)
    return _pipe_sd


def _load_svd():
    global _pipe_svd
    from diffusers import StableVideoDiffusionPipeline
    import torch

    if _pipe_svd is None:
        _pipe_svd = StableVideoDiffusionPipeline.from_pretrained(
            "stabilityai/stable-video-diffusion-img2vid-xt",
            torch_dtype=torch.float16,
            variant="fp16",
        )
        _pipe_svd.to("cuda")
        _pipe_svd.set_progress_bar_config(disable=True)
    return _pipe_svd


# ================= public API =================


def generate_image(prompt: str) -> str:
    """Prompt'ga mos PNG yaratib, yo'lini qaytaradi.

    Tartib: Pollinations (haqiqiy AI) → deAPI → Magic Hour → GPU SDXL → protsur.
    O'zbekcha so'rovlar avval inglizchaga tarjima qilinadi.
    """
    prompt = _english_prompt(prompt)
    try:
        import pollinations

        if pollinations.available():
            data = pollinations.generate_image(prompt)
            if data:
                seed = _seed(prompt)
                path = os.path.join(
                    _OUT_DIR,
                    f"poll_img_{seed:08x}_{int(time.time() * 1000) % 100000}.webp",
                )
                with open(path, "wb") as f:
                    f.write(data)
                return path
    except Exception:
        pass

    try:
        from deapi import available as de_available
        from deapi import generate_image as de_image

        if de_available():
            path = de_image(prompt)
            if path:
                return path
    except Exception:
        pass

    try:
        from magic import available as mh_available
        from magic import generate_image as mh_image

        if mh_available():
            path = mh_image(prompt)
            if path:
                return path
    except Exception:
        pass

    seed = _seed(prompt)
    anyalon = int(time.time() * 1000)
    path = os.path.join(_OUT_DIR, f"img_{seed:08x}_{anyalon % 100000}.png")

    if _available():
        try:
            img = _load_sd()(
                prompt=prompt, num_inference_steps=2, guidance_scale=0.0
            ).images[0]
        except Exception:
            img = _flow(prompt)
    else:
        img = _flow(prompt)
    img.save(path)
    return path


def generate_video(prompt: str) -> str:
    """Prompt'a mos qisqa video (MP4) yarat.

    Tartib: Pollinations (real AI) → JSON2Video (real render) → deAPI
    (LTX-Video) → Magic Hour (haqiqiy AI) → GPU SVD → protsur animatsiya.
    O'zbekcha so'rovlar avval inglizchaga tarjima qilinadi.
    """
    prompt = _english_prompt(prompt)
    try:
        import pollinations

        if pollinations.available():
            data = pollinations.generate_video(prompt)
            if data:
                seed = _seed(prompt)
                path = os.path.join(
                    _OUT_DIR,
                    f"poll_vid_{seed:08x}_{int(time.time() * 1000) % 100000}.mp4",
                )
                with open(path, "wb") as f:
                    f.write(data)
                return path
    except Exception:
        pass

    try:
        from json2video import available as j2v_available
        from json2video import generate_video as j2v_video

        if j2v_available():
            path = j2v_video(prompt)
            if path:
                return path
    except Exception:
        pass

    try:
        from deapi import available as de_available
        from deapi import generate_video as de_video

        if de_available():
            path = de_video(prompt)
            if path:
                return path
    except Exception:
        pass

    try:
        from magic import available as mh_available
        from magic import generate_video as mh_video

        if mh_available():
            path = mh_video(prompt)
            if path:
                return path
    except Exception:
        pass

    seed = _seed(prompt)
    ts = int(time.time())
    path = os.path.join(_OUT_DIR, f"vid_{seed:08x}_{ts % 100000}.mp4")

    frames: list[np.ndarray] = []
    if _available():
        try:
            import torch

            first = _flow(prompt)
            pipe = _load_svd()
            gen = torch.Generator(device="cuda").manual_seed(seed)
            frames = pipe(
                image=first,
                decode_chunk_size=6,
                generator=gen,
                num_frames=25,
            ).frames[0]
        except Exception:
            pass

    if not frames:
        frames = _animated(prompt)

    _write_mp4(path, frames)
    return path


def _animated(prompt: str, frames_n=48, size=(384, 384)) -> list[np.ndarray]:
    """Pan+zoom efeckti bilan protsural video."""
    seed = _seed(prompt)
    rng = np.random.RandomState(seed)
    base = _flow(prompt).resize((size[0] * 2, size[1] * 2))
    out = []
    for i in range(frames_n):
        zoom = 1.0 + 0.18 * (i / frames_n)
        dx = int((base.width - size[0] * zoom) * (0.3 + 0.4 * rng.rand()))
        dy = int((base.height - size[1] * zoom) * (0.3 + 0.4 * rng.rand()))
        crop = base.crop([dx, dy, dx + int(size[0] * zoom), dy + int(size[1] * zoom)])
        out.append(np.asarray(crop.resize(size).convert("RGB")))
    return out


def _write_mp4(path: str, frames: list[np.ndarray], fps: int = 24) -> None:
    import cv2

    h, w = frames[0].shape[:2]
    writer = cv2.VideoWriter(path, cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h))
    for fr in frames:
        writer.write(cv2.cvtColor(np.asarray(fr), cv2.COLOR_RGB2BGR))
    writer.release()


def status() -> dict:
    def _flag(module: str) -> bool:
        try:
            import importlib

            mod = importlib.import_module(module)
            return bool(mod.available())
        except Exception:
            return False

    return {
        "gpu": _available(),
        "mode": "diffusion" if _available() else "procedural",
        "magic_hour": _flag("magic"),
        "deapi": _flag("deapi"),
        "json2video": _flag("json2video"),
    }
