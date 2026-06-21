#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MARKETING EL GADGET — Compositor de Reels v2 (1080x1920, 20-25s)

7 slides dinámicos con transiciones variadas, zoom, conteo animado,
ritmo adaptado por persona, soporte de voz (ElevenLabs) y música.

Estructura:
  1. Hook (2.5s)  — zoom lento + texto grande
  2. Dolor (2s)   — slide lateral
  3. Solución (3s) — fade in
  4. Prueba (3.5s) — número con conteo animado
  5. Beneficio (2.5s) — fade + badge
  6. Social proof (2s) — dato extra
  7. CTA (4s)     — fondo dorado + URL
"""

import math
import io
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import numpy as np

BASE_DIR = Path(__file__).parent.parent
FONTS_DIR = BASE_DIR / "marketing_app" / "assets" / "fonts"
LOGO_PATH = BASE_DIR / "marketing_app" / "assets" / "logo_transparente.png"
OUTPUT_DIR = BASE_DIR / "marketing_app" / "data" / "generated_reels"
AUDIO_DIR = BASE_DIR / "marketing_app" / "assets" / "audio"

W = 1080
H = 1920
FPS = 30

INK = (20, 21, 26)
WHITE = (255, 255, 255)
ACCENT = (255, 199, 0)
GREEN = (46, 139, 87)

PALETAS = {
    "maria": {"bg": (253, 249, 240), "bar": (42, 36, 28), "text": INK, "text2": (90, 85, 78), "accent": ACCENT, "badge_bg": GREEN, "badge_text": WHITE},
    "lucas": {"bg": INK, "bar": (5, 5, 8), "text": WHITE, "text2": (190, 190, 195), "accent": ACCENT, "badge_bg": ACCENT, "badge_text": INK},
    "ana": {"bg": WHITE, "bar": (35, 35, 40), "text": INK, "text2": (90, 90, 95), "accent": (160, 140, 100), "badge_bg": INK, "badge_text": WHITE},
    "sofi": {"bg": (255, 245, 248), "bar": (40, 25, 35), "text": INK, "text2": (110, 75, 95), "accent": (230, 100, 145), "badge_bg": (200, 90, 140), "badge_text": WHITE},
    "martin": {"bg": (20, 30, 50), "bar": (10, 15, 30), "text": WHITE, "text2": (175, 185, 210), "accent": ACCENT, "badge_bg": GREEN, "badge_text": WHITE},
}

RITMO = {
    "maria": {"hook": 3.0, "slide": 2.8, "proof": 4.0, "cta": 4.5, "transition": 0.5},
    "lucas": {"hook": 2.0, "slide": 2.0, "proof": 3.0, "cta": 3.5, "transition": 0.3},
    "ana":   {"hook": 2.5, "slide": 2.5, "proof": 3.5, "cta": 4.0, "transition": 0.5},
    "sofi":  {"hook": 2.5, "slide": 2.2, "proof": 3.5, "cta": 4.0, "transition": 0.4},
    "martin":{"hook": 2.5, "slide": 2.5, "proof": 3.5, "cta": 4.0, "transition": 0.4},
}

FONT_CACHE = {}
def _font(role, size):
    key = (role, size)
    if key in FONT_CACHE:
        return FONT_CACHE[key]
    paths = {
        "h": [FONTS_DIR / "Inter-Bold.ttf", Path("C:/Windows/Fonts/segoeuib.ttf")],
        "b": [FONTS_DIR / "Inter-Regular.ttf", Path("C:/Windows/Fonts/calibri.ttf")],
        "m": [FONTS_DIR / "Inter-Medium.ttf", Path("C:/Windows/Fonts/calibrib.ttf")],
    }
    for p in paths.get(role, paths["b"]):
        if p.exists():
            try:
                f = ImageFont.truetype(str(p), size)
                FONT_CACHE[key] = f
                return f
            except Exception:
                continue
    return ImageFont.load_default()


def _logo(size=48):
    if LOGO_PATH.exists():
        return Image.open(LOGO_PATH).convert("RGBA").resize((size, size), Image.LANCZOS)
    return None


def _wrap(text, font, max_w, draw):
    text = ''.join(c if ord(c) < 0x10000 else '' for c in (text or ''))
    words = text.split()
    lines, current = [], ""
    for w in words:
        test = f"{current} {w}".strip()
        if draw.textbbox((0, 0), test, font=font)[2] <= max_w:
            current = test
        else:
            if current:
                lines.append(current)
            current = w
    if current:
        lines.append(current)
    return lines or [""]


def ease_out(t):
    return 1 - (1 - t) ** 3

def ease_out_expo(t):
    return 1 if t >= 1 else 1 - 2 ** (-10 * t)


# ── Drawing helpers ──

def _shadow(draw, xy, text, font, fill, offset=3):
    x, y = xy
    shadow = (0, 0, 0) if sum(fill[:3]) > 384 else (60, 60, 60)
    draw.text((x + offset, y + offset), text, fill=shadow, font=font)
    draw.text((x, y), text, fill=fill, font=font)


def _top_bar(img, draw, pal):
    draw.rectangle([0, 0, W, 100], fill=pal["bar"])
    draw.line([(0, 100), (W, 100)], fill=ACCENT, width=3)
    logo = _logo(48)
    if logo:
        img.paste(logo, (28, 26), logo)
    draw.text((86, 26), "El", fill=WHITE, font=_font("h", 30))
    draw.text((120, 26), " Gadget", fill=ACCENT, font=_font("h", 30))
    draw.text((86, 62), "TIENDA ONLINE", fill=(160, 160, 160), font=_font("m", 13))
    ig = "@elgadget.ok"
    igf = _font("m", 17)
    igw = draw.textbbox((0, 0), ig, font=igf)[2]
    draw.text((W - igw - 28, 40), ig, fill=(140, 140, 140), font=igf)


def _bottom_bar(draw, text, pal):
    y = H - 80
    draw.rectangle([0, y, W, H], fill=pal["badge_bg"])
    draw.line([(0, y), (W, y)], fill=pal["accent"], width=3)
    f = _font("h", 22)
    tw = draw.textbbox((0, 0), text, font=f)[2]
    draw.text(((W - tw) // 2, y + 28), text, fill=pal["badge_text"], font=f)


def _centered_lines(draw, text, font, fill, max_w, base_y, spacing=0):
    lines = _wrap(text, font, max_w, draw)[:4]
    bbox_h = draw.textbbox((0, 0), "Ay", font=font)[3]
    gap = bbox_h + spacing
    for i, line in enumerate(lines):
        lw = draw.textbbox((0, 0), line, font=font)[2]
        _shadow(draw, ((W - lw) // 2, base_y + i * gap), line, font, fill)
    return base_y + len(lines) * gap


# ── Visual styles ──
# Cada estilo define cómo se renderizan los slides internos (no hook ni CTA)
# Esto genera variedad visual real entre reels de la misma persona

VISUAL_STYLES = ["centered", "lateral", "card", "split"]


def _left_aligned_lines(draw, text, font, fill, max_w, base_y, x_start=80, spacing=0):
    lines = _wrap(text, font, max_w, draw)[:5]
    bbox_h = draw.textbbox((0, 0), "Ay", font=font)[3]
    gap = bbox_h + spacing
    for i, line in enumerate(lines):
        _shadow(draw, (x_start, base_y + i * gap), line, font, fill)
    return base_y + len(lines) * gap


# ── Slide renderers ──

def _slide_standard(pal, text, font_size=48, bar_text="elgadget.com.ar/referidos", style="centered"):
    img = Image.new("RGB", (W, H), pal["bg"])
    draw = ImageDraw.Draw(img)
    _top_bar(img, draw, pal)
    tf = _font("h", font_size)
    lines = _wrap(text, tf, 780 if style != "centered" else 860, draw)[:5]
    bbox_h = draw.textbbox((0, 0), "Ay", font=tf)[3]
    total_h = len(lines) * (bbox_h + 14)
    base_y = (H - total_h) // 2

    if style == "lateral":
        draw.rectangle([0, 100, 12, H - 80], fill=pal["accent"])
        _left_aligned_lines(draw, text, tf, pal["text"], 780, base_y, 80, 14)
    elif style == "card":
        pad = 50
        card_y1 = base_y - pad
        card_y2 = base_y + total_h + pad
        draw.rounded_rectangle([60, card_y1, W - 60, card_y2], radius=28, fill=pal.get("bullet_bg", pal["bar"]))
        draw.rounded_rectangle([60, card_y1, W - 60, card_y1 + 6], radius=0, fill=pal["accent"])
        _centered_lines(draw, text, tf, pal["text"], 780, base_y, 14)
    elif style == "split":
        draw.rectangle([0, 100, W // 3, H - 80], fill=pal["accent"])
        _left_aligned_lines(draw, text, tf, pal["text"], 620, base_y, W // 3 + 60, 14)
    else:
        _centered_lines(draw, text, tf, pal["text"], 860, base_y, 14)

    _bottom_bar(draw, bar_text, pal)
    return np.array(img)


def _slide_hook(pal, hook, style="centered"):
    img = Image.new("RGB", (W, H), pal["bg"])
    draw = ImageDraw.Draw(img)
    _top_bar(img, draw, pal)
    hf = _font("h", 72)

    if style == "lateral":
        draw.rectangle([0, 100, 16, H - 80], fill=pal["accent"])
        lines = _wrap(hook, hf, 800, draw)[:3]
        bbox_h = draw.textbbox((0, 0), "Ay", font=hf)[3]
        total_h = len(lines) * (bbox_h + 20)
        base_y = (H - total_h) // 2 - 40
        y = _left_aligned_lines(draw, hook, hf, pal["text"], 800, base_y, 80, 20)
        draw.line([(80, y + 10), (480, y + 10)], fill=pal["accent"], width=4)
    elif style == "card":
        lines = _wrap(hook, hf, 820, draw)[:3]
        bbox_h = draw.textbbox((0, 0), "Ay", font=hf)[3]
        total_h = len(lines) * (bbox_h + 20)
        base_y = (H - total_h) // 2 - 40
        pad = 50
        draw.rounded_rectangle([50, base_y - pad, W - 50, base_y + total_h + pad + 20], radius=30, fill=pal.get("bullet_bg", pal["bar"]))
        draw.rounded_rectangle([50, base_y + total_h + pad - 4, W - 50, base_y + total_h + pad + 20], radius=0, fill=pal["accent"])
        y = _centered_lines(draw, hook, hf, pal["text"], 820, base_y, 20)
    elif style == "split":
        draw.rectangle([0, H // 2 - 40, W, H - 80], fill=pal["accent"])
        lines = _wrap(hook, hf, 900, draw)[:3]
        bbox_h = draw.textbbox((0, 0), "Ay", font=hf)[3]
        total_h = len(lines) * (bbox_h + 20)
        base_y = (H - total_h) // 2 - 60
        y = _centered_lines(draw, hook, hf, pal["text"], 900, base_y, 20)
        sub = "@elgadget.ok"
        sf = _font("m", 28)
        sw = draw.textbbox((0, 0), sub, font=sf)[2]
        draw.text(((W - sw) // 2, H // 2 + 60), sub, fill=INK, font=sf)
    else:
        lines = _wrap(hook, hf, 860, draw)[:3]
        bbox_h = draw.textbbox((0, 0), "Ay", font=hf)[3]
        total_h = len(lines) * (bbox_h + 20)
        base_y = (H - total_h) // 2 - 40
        y = _centered_lines(draw, hook, hf, pal["text"], 860, base_y, 20)
        draw.line([(W // 2 - 200, y + 10), (W // 2 + 200, y + 10)], fill=pal["accent"], width=4)

    _bottom_bar(draw, "Referidos El Gadget - hasta 15% - dia 5", pal)
    return np.array(img)


def _slide_proof_counting(pal, numero_text, subtexto, frame_progress, style="centered"):
    img = Image.new("RGB", (W, H), pal["bg"])
    draw = ImageDraw.Draw(img)
    _top_bar(img, draw, pal)

    cleaned = numero_text.replace(".", "").replace(",", "")
    prefix = ""
    for c in cleaned:
        if c.isdigit():
            break
        prefix += c
    digits = ''.join(c for c in cleaned if c.isdigit())
    target = int(digits) if digits else 0

    eased = ease_out_expo(min(frame_progress * 1.5, 1.0))
    current = int(target * eased)
    display = f"{prefix}{current:,.0f}".replace(",", ".")

    if style == "card":
        card_w, card_h = 700, 400
        cx = (W - card_w) // 2
        cy = H // 2 - card_h // 2 - 40
        draw.rounded_rectangle([cx, cy, cx + card_w, cy + card_h], radius=28, fill=pal.get("bullet_bg", pal["bar"]))
        nf = _font("h", 100)
        nw = draw.textbbox((0, 0), display, font=nf)[2]
        _shadow(draw, ((W - nw) // 2, cy + 60), display, nf, pal["accent"])
        if frame_progress > 0.3:
            sf = _font("m", 28)
            lines = _wrap(subtexto, sf, card_w - 60, draw)[:2]
            sy = cy + 200
            for line in lines:
                sw = draw.textbbox((0, 0), line, font=sf)[2]
                draw.text(((W - sw) // 2, sy), line, fill=pal["text2"], font=sf)
                sy += 38
    elif style == "lateral":
        draw.rectangle([0, 100, 12, H - 80], fill=pal["accent"])
        nf = _font("h", 110)
        _shadow(draw, (80, H // 2 - 180), display, nf, pal["accent"])
        if frame_progress > 0.3:
            sf = _font("m", 30)
            _left_aligned_lines(draw, subtexto, sf, pal["text2"], 700, H // 2 + 10, 80, 10)
    elif style == "split":
        draw.rectangle([0, 100, W, H // 2 + 60], fill=pal["accent"])
        nf = _font("h", 110)
        nw = draw.textbbox((0, 0), display, font=nf)[2]
        _shadow(draw, ((W - nw) // 2, H // 2 - 200), display, nf, INK, offset=2)
        if frame_progress > 0.3:
            sf = _font("m", 30)
            lines = _wrap(subtexto, sf, 800, draw)[:3]
            sy = H // 2 + 100
            for line in lines:
                sw = draw.textbbox((0, 0), line, font=sf)[2]
                _shadow(draw, ((W - sw) // 2, sy), line, sf, pal["text2"])
                sy += 44
    else:
        nf = _font("h", 120)
        nw = draw.textbbox((0, 0), display, font=nf)[2]
        _shadow(draw, ((W - nw) // 2, H // 2 - 180), display, nf, pal["accent"])
        if frame_progress > 0.3:
            sf = _font("m", 32)
            lines = _wrap(subtexto, sf, 800, draw)[:3]
            y = H // 2 + 20
            for line in lines:
                sw = draw.textbbox((0, 0), line, font=sf)[2]
                _shadow(draw, ((W - sw) // 2, y), line, sf, pal["text2"])
                y += 44

    _bottom_bar(draw, "Referidos El Gadget - hasta 15% - dia 5", pal)
    return np.array(img)


def _slide_benefit(pal, texto, badge_text="Sin inversion - Desde el celular", style="centered"):
    img = Image.new("RGB", (W, H), pal["bg"])
    draw = ImageDraw.Draw(img)
    _top_bar(img, draw, pal)
    bf = _font("h", 52)
    bbf = _font("h", 24)

    if style == "lateral":
        draw.rectangle([0, 100, 12, H - 80], fill=pal["accent"])
        base_y = (H - 300) // 2
        y = _left_aligned_lines(draw, texto, bf, pal["text"], 780, base_y, 80, 14)
        bbw = draw.textbbox((0, 0), badge_text, font=bbf)[2] + 40
        draw.rounded_rectangle([80, y + 20, 80 + bbw, y + 68], radius=24, fill=pal["accent"])
        draw.text((100, y + 30), badge_text, fill=INK, font=bbf)
    elif style == "card":
        lines = _wrap(texto, bf, 780, draw)[:4]
        bbox_h = draw.textbbox((0, 0), "Ay", font=bf)[3]
        total_h = len(lines) * (bbox_h + 14)
        base_y = (H - total_h) // 2 - 60
        pad = 50
        draw.rounded_rectangle([60, base_y - pad, W - 60, base_y + total_h + pad + 70], radius=28, fill=pal.get("bullet_bg", pal["bar"]))
        y = _centered_lines(draw, texto, bf, pal["text"], 780, base_y, 14)
        bbw = draw.textbbox((0, 0), badge_text, font=bbf)[2] + 40
        bx = (W - bbw) // 2
        draw.rounded_rectangle([bx, y + 20, bx + bbw, y + 68], radius=24, fill=pal["accent"])
        draw.text((bx + 20, y + 30), badge_text, fill=INK, font=bbf)
    elif style == "split":
        draw.rectangle([0, H - 350, W, H - 80], fill=pal["accent"])
        base_y = (H - 300) // 2 - 80
        _centered_lines(draw, texto, bf, pal["text"], 860, base_y, 14)
        bbw = draw.textbbox((0, 0), badge_text, font=bbf)[2] + 40
        bx = (W - bbw) // 2
        draw.rounded_rectangle([bx, H - 300, bx + bbw, H - 252], radius=24, fill=INK)
        draw.text((bx + 20, H - 290), badge_text, fill=ACCENT, font=bbf)
    else:
        lines = _wrap(texto, bf, 860, draw)[:4]
        bbox_h = draw.textbbox((0, 0), "Ay", font=bf)[3]
        total_h = len(lines) * (bbox_h + 14)
        base_y = (H - total_h) // 2 - 50
        y = _centered_lines(draw, texto, bf, pal["text"], 860, base_y, 14)
        bbw = draw.textbbox((0, 0), badge_text, font=bbf)[2] + 40
        bx = (W - bbw) // 2
        draw.rounded_rectangle([bx, y + 20, bx + bbw, y + 68], radius=24, fill=pal["accent"])
        draw.text((bx + 20, y + 30), badge_text, fill=INK, font=bbf)

    _bottom_bar(draw, "elgadget.com.ar/referidos", pal)
    return np.array(img)


def _slide_cta(pal, cta_text):
    img = Image.new("RGB", (W, H), ACCENT)
    draw = ImageDraw.Draw(img)
    draw.rectangle([0, 0, W, 100], fill=INK)
    draw.line([(0, 100), (W, 100)], fill=ACCENT, width=3)
    logo = _logo(48)
    if logo:
        img.paste(logo, (28, 26), logo)
    draw.text((86, 26), "El", fill=WHITE, font=_font("h", 30))
    draw.text((120, 26), " Gadget", fill=ACCENT, font=_font("h", 30))

    lf = _font("h", 64)
    lines = _wrap(cta_text, lf, 880, draw)[:3]
    bbox_h = draw.textbbox((0, 0), "Ay", font=lf)[3]
    total_h = len(lines) * (bbox_h + 18)
    y = H // 2 - total_h - 40

    for line in lines:
        lw = draw.textbbox((0, 0), line, font=lf)[2]
        _shadow(draw, ((W - lw) // 2, y), line, lf, INK, offset=2)
        y += bbox_h + 18

    y += 20
    draw.line([(W // 2 - 180, y), (W // 2 + 180, y)], fill=INK, width=3)
    y += 40

    for b in ["Registro gratis", "Comisiones del 7% al 15%", "Cobro mensual"]:
        bf = _font("h", 30)
        bw = draw.textbbox((0, 0), b, font=bf)[2]
        draw.text(((W - bw) // 2, y), b, fill=INK, font=bf)
        y += 48

    y += 30
    url = "elgadget.com.ar/referidos"
    uf = _font("h", 42)
    uw = draw.textbbox((0, 0), url, font=uf)[2]
    pad = 24
    draw.rounded_rectangle([(W - uw) // 2 - pad, y - 10, (W + uw) // 2 + pad, y + 56], radius=16, fill=INK)
    draw.text(((W - uw) // 2, y), url, fill=ACCENT, font=uf)

    draw.rectangle([0, H - 80, W, H], fill=INK)
    draw.line([(0, H - 80), (W, H - 80)], fill=ACCENT, width=3)
    bar = "Comenta CODIGO y te mando el link"
    btf = _font("h", 22)
    btw = draw.textbbox((0, 0), bar, font=btf)[2]
    draw.text(((W - btw) // 2, H - 52), bar, fill=ACCENT, font=btf)

    return np.array(img)


# ── Transition effects (operate on numpy arrays) ──

def _apply_zoom(frames, zoom_start=1.0, zoom_end=1.05):
    """Aplica zoom solo al contenido (entre barras), manteniendo barras fijas."""
    result = []
    top_h = 103
    bot_h = 80
    for i, frame in enumerate(frames):
        t = i / max(len(frames) - 1, 1)
        scale = zoom_start + (zoom_end - zoom_start) * ease_out(t)
        full_h, full_w = frame.shape[:2]
        content_h = full_h - top_h - bot_h

        top_bar = frame[:top_h]
        content = frame[top_h:full_h - bot_h]
        bot_bar = frame[full_h - bot_h:]

        ch, cw = content.shape[:2]
        new_ch, new_cw = int(ch * scale), int(cw * scale)
        zoomed = Image.fromarray(content).resize((new_cw, new_ch), Image.LANCZOS)
        left = (new_cw - cw) // 2
        top = (new_ch - ch) // 2
        cropped = np.array(zoomed.crop((left, top, left + cw, top + ch)))

        combined = np.vstack([top_bar, cropped, bot_bar])
        result.append(combined)
    return result


def _crossfade(arr_a, arr_b, n_frames):
    frames = []
    for i in range(n_frames):
        alpha = ease_out(i / max(n_frames - 1, 1))
        blended = (arr_a.astype(float) * (1 - alpha) + arr_b.astype(float) * alpha).astype(np.uint8)
        frames.append(blended)
    return frames


def _slide_from_right(arr_new, arr_bg, n_frames):
    frames = []
    h, w = arr_new.shape[:2]
    for i in range(n_frames):
        t = ease_out(i / max(n_frames - 1, 1))
        offset = int(w * (1 - t))
        composite = arr_bg.copy()
        if offset < w:
            composite[:, offset:] = arr_new[:, :w - offset]
        frames.append(composite)
    return frames


def _scale_in(arr_new, arr_bg, n_frames):
    frames = []
    h, w = arr_new.shape[:2]
    for i in range(n_frames):
        t = ease_out_expo(i / max(n_frames - 1, 1))
        scale = max(0.3, t)
        sh, sw = int(h * scale), int(w * scale)
        small = Image.fromarray(arr_new).resize((sw, sh), Image.LANCZOS)
        composite = Image.fromarray(arr_bg.copy())
        x = (w - sw) // 2
        y = (h - sh) // 2
        composite.paste(small, (x, y))
        frames.append(np.array(composite))
    return frames


# ── Audio helpers ──

def generate_voiceover(text, persona="maria", output_path=None):
    """
    Genera voz en off con ElevenLabs. La voz NO repite el texto en pantalla,
    sino que agrega contexto persuasivo complementario.
    Retorna path al .mp3 o None.
    """
    import sys
    sys.path.append(str(Path(__file__).parent))
    from utils.config import Config
    env = Config.cargar_env()

    api_key = env.get('ELEVENLABS_API_KEY', '')
    if not api_key:
        return None

    try:
        from elevenlabs import ElevenLabs
        client = ElevenLabs(api_key=api_key)

        voice_map = {
            "maria": "cgSgspJ2msm6clMCkdW9",
            "lucas": "TX3LPaxmHKxFdv7VOQHJ",
            "ana": "EXAVITQu4vr4xnSDxMaL",
            "sofi": "FGY2WhTYpPnrIDTdsKH5",
            "martin": "cjVigY5qzO86Huf0OWal",
        }
        voice = voice_map.get(persona, "cgSgspJ2msm6clMCkdW9")

        audio_gen = client.text_to_speech.convert(
            text=text,
            voice_id=voice,
            model_id="eleven_multilingual_v2",
            output_format="mp3_44100_128",
        )

        if not output_path:
            OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
            import time as _t
            output_path = str(OUTPUT_DIR / f"vo_{persona}_{int(_t.time())}.mp3")

        with open(output_path, "wb") as f:
            for chunk in audio_gen:
                f.write(chunk)

        return output_path
    except Exception as e:
        print(f"[REEL] ElevenLabs error: {e}")
        return None


MUSIC_MAP = {
    "lucas": "upbeat",
    "maria": "calido",
    "ana": "corporativo",
    "sofi": "corporativo",
    "martin": "upbeat",
}

def _find_bg_music(persona="lucas"):
    """Busca música por persona. Nombres: upbeat.mp3, calido.mp3, corporativo.mp3"""
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    mood = MUSIC_MAP.get(persona, "upbeat")
    for ext in (".mp3", ".wav", ".ogg"):
        target = AUDIO_DIR / f"{mood}{ext}"
        if target.exists():
            return str(target)
    for ext in ("*.mp3", "*.wav", "*.ogg"):
        files = list(AUDIO_DIR.glob(ext))
        if files:
            return str(files[0])
    return None


# ── Compositor principal ──

def compose_reel(
    persona="lucas",
    hook="",
    dolor="",
    solucion="",
    numero_grande="",
    subtexto_proof="",
    beneficio="",
    dato_extra="",
    cta_text="",
    voiceover_text="",
    output_filename=None,
) -> str:
    """
    Genera un Reel con 7 slides dinámicos, transiciones variadas y audio opcional.

    Args:
        persona: buyer persona (paleta + ritmo)
        hook: frase hook (slide 1)
        dolor: ampliación del dolor (slide 2)
        solucion: cómo se resuelve (slide 3)
        numero_grande: "$X.XXX" para conteo animado (slide 4)
        subtexto_proof: contexto del número (slide 4)
        beneficio: frase emocional (slide 5)
        dato_extra: prueba social adicional (slide 6)
        cta_text: texto del CTA final (slide 7)
        voiceover_text: texto completo para voz en off (opcional)
        output_filename: nombre del archivo de salida

    Returns: path al .mp4
    """
    from moviepy import VideoClip, AudioFileClip, CompositeAudioClip

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    pal = PALETAS.get(persona, PALETAS["lucas"])
    ritmo = RITMO.get(persona, RITMO["lucas"])
    if not output_filename:
        import time as _t
        output_filename = f"reel_{persona}_{int(_t.time())}.mp4"
    if not cta_text:
        cta_text = "¿Queres empezar a ganar?"

    import random as _rnd
    style = _rnd.choice(VISUAL_STYLES)
    trans_frames = int(ritmo["transition"] * FPS)
    print(f"[REEL] Estilo visual: {style}")

    # Render static slides
    slides = []
    durations = []
    transitions = []

    if hook:
        slides.append(("hook", _slide_hook(pal, hook, style)))
        durations.append(ritmo["hook"])
        transitions.append("zoom")

    if dolor:
        slides.append(("dolor", _slide_standard(pal, dolor, 46, "Referidos El Gadget - hasta 15% - dia 5", style)))
        durations.append(ritmo["slide"])
        transitions.append("slide_right")

    if solucion:
        slides.append(("solucion", _slide_standard(pal, solucion, 44, "elgadget.com.ar/referidos", style)))
        durations.append(ritmo["slide"])
        transitions.append("crossfade")

    if numero_grande:
        slides.append(("proof", None))
        durations.append(ritmo["proof"])
        transitions.append("scale_in")

    if beneficio:
        slides.append(("benefit", _slide_benefit(pal, beneficio, style=style)))
        durations.append(ritmo["slide"])
        transitions.append("crossfade")

    if dato_extra:
        slides.append(("extra", _slide_standard(pal, dato_extra, 40, "elgadget.com.ar/referidos", style)))
        durations.append(2.0)
        transitions.append("slide_right")

    slides.append(("cta", _slide_cta(pal, cta_text)))
    durations.append(ritmo["cta"])
    transitions.append("crossfade")

    # Build all frames
    all_frames = []
    bg_frame = np.full((H, W, 3), pal["bg"], dtype=np.uint8)

    for idx, (slide_type, slide_arr) in enumerate(slides):
        dur = durations[idx]
        hold_n = int(dur * FPS)
        trans_type = transitions[idx]

        if slide_type == "proof":
            for i in range(hold_n):
                progress = i / hold_n
                frame = _slide_proof_counting(pal, numero_grande, subtexto_proof, progress, style)
                all_frames.append(frame)
        elif slide_type == "hook" and trans_type == "zoom":
            static_frames = [slide_arr] * hold_n
            zoomed = _apply_zoom(static_frames, 1.0, 1.08)
            all_frames.extend(zoomed)
        else:
            for _ in range(hold_n):
                all_frames.append(slide_arr)

        if idx < len(slides) - 1:
            next_type, next_arr = slides[idx + 1]
            current_arr = all_frames[-1] if all_frames else bg_frame
            next_static = next_arr if next_arr is not None else _slide_proof_counting(pal, numero_grande, subtexto_proof, 0.0, style)

            if trans_type == "slide_right":
                tf = _slide_from_right(next_static, current_arr, trans_frames)
            elif trans_type == "scale_in":
                tf = _scale_in(next_static, current_arr, trans_frames)
            else:
                tf = _crossfade(current_arr, next_static, trans_frames)
            all_frames.extend(tf)

    total_duration = len(all_frames) / FPS

    def make_frame(t):
        idx = min(int(t * FPS), len(all_frames) - 1)
        return all_frames[idx]

    # Audio: generar voz primero para saber su duración
    vo_clip = None
    music_clip = None

    if voiceover_text:
        vo_path = generate_voiceover(voiceover_text, persona)
        if vo_path and Path(vo_path).exists():
            try:
                vo_clip = AudioFileClip(vo_path)
                print(f"[REEL] Voz en off: {vo_path} ({vo_clip.duration:.1f}s)")
            except Exception as e:
                print(f"[REEL] Error loading voiceover: {e}")
                vo_clip = None

    # Si la voz es más larga que el video, extender el último slide
    if vo_clip and vo_clip.duration > total_duration:
        extra = vo_clip.duration - total_duration + 1.0
        last_frame = all_frames[-1]
        extra_frames = [last_frame] * int(extra * FPS)
        all_frames.extend(extra_frames)
        total_duration = len(all_frames) / FPS
        print(f"[REEL] Video extendido a {total_duration:.1f}s para completar la voz")

    clip = VideoClip(make_frame, duration=total_duration)

    bg_music_path = _find_bg_music(persona)
    if bg_music_path:
        try:
            music_clip = AudioFileClip(bg_music_path)
            if music_clip.duration < total_duration:
                loops_needed = int(total_duration / music_clip.duration) + 1
                from moviepy import concatenate_audioclips
                music_clip = concatenate_audioclips([music_clip] * loops_needed)
            music_clip = music_clip.subclipped(0, total_duration)

            if vo_clip:
                music_clip = music_clip.with_volume_scaled(0.12)
            else:
                music_clip = music_clip.with_volume_scaled(0.35)
            print(f"[REEL] Musica: {bg_music_path}")
        except Exception as e:
            print(f"[REEL] Error loading music: {e}")
            music_clip = None

    audio_parts = [c for c in [vo_clip, music_clip] if c is not None]

    if audio_parts:
        try:
            if len(audio_parts) == 1:
                clip = clip.with_audio(audio_parts[0])
            else:
                final_audio = CompositeAudioClip(audio_parts)
                clip = clip.with_audio(final_audio)
        except Exception as e:
            print(f"[REEL] Error compositing audio: {e}")

    output_path = str(OUTPUT_DIR / output_filename)
    clip.write_videofile(
        output_path, fps=FPS, codec="libx264",
        audio_codec="aac" if audio_parts else None,
        audio=bool(audio_parts),
        preset="medium", threads=4, logger=None,
    )
    clip.close()

    print(f"[REEL] {persona} | {len(slides)} slides | {total_duration:.1f}s | {output_path}")
    return output_path


if __name__ == "__main__":
    print("Generando Reel de prueba (Lucas - side hustle)...")
    path = compose_reel(
        persona="lucas",
        hook="¿Laburas 8 horas y seguis sin plata?",
        dolor="Tus amigos ya generan plata con las redes. Vos seguis scrolleando.",
        solucion="Comparti un link por WhatsApp. Tu contacto compra con hasta 20% OFF. Vos cobras comision.",
        numero_grande="$10.500",
        subtexto_proof="es lo que ganas si 3 amigos compran este mes",
        beneficio="Sin jefe. Sin horarios. Sin inversion. Desde el celular.",
        dato_extra="El programa recien arranca. Los primeros tienen ventaja.",
        cta_text="¿Queres empezar a ganar?",
    )
    print(f"Reel: {path}")

    print("\nGenerando Reel de prueba (Maria - mama)...")
    path2 = compose_reel(
        persona="maria",
        hook="¿Tu casa es un caos cuando llegas cansada?",
        dolor="Los chicos, el trabajo, el super. No das mas. Y encima no alcanza.",
        solucion="Tus amigas ya te piden recomendaciones. Ahora cobra por ellas.",
        numero_grande="$3.675",
        subtexto_proof="ganas si 3 amigas compran este mes con tu codigo",
        beneficio="Sin salir de casa. Mientras los chicos duermen. Desde el celular.",
        dato_extra="Ya hay mamás cobrando comisiones todos los meses.",
        cta_text="¿Queres empezar a ganar?",
    )
    print(f"Reel: {path2}")
