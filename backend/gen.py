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
    """Prompt'ga mos PNG yaratib, yo'lini qaytaradi (GPU → SDXL, aksida protsur)."""
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
    """Prompt'aga mosa qisqa video (MP4) yarat. GPU → SVD animatsiyasi."""
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
    return {"gpu": _available(), "mode": "diffusion" if _available() else "procedural"}
