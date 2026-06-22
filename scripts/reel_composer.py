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
    "maria": {"bg": (253, 249, 240), "bar": (42, 36, 28), "text": INK, "text2": (90, 85, 78), "accent": ACCENT, "badge_bg": GREEN, "badge_text": WHITE, "card_bg": (255, 243, 200)},
    "lucas": {"bg": INK, "bar": (5, 5, 8), "text": WHITE, "text2": (190, 190, 195), "accent": ACCENT, "badge_bg": ACCENT, "badge_text": INK, "card_bg": (35, 35, 45)},
    "ana": {"bg": WHITE, "bar": (35, 35, 40), "text": INK, "text2": (90, 90, 95), "accent": (160, 140, 100), "badge_bg": INK, "badge_text": WHITE, "card_bg": (240, 238, 233)},
    "sofi": {"bg": (255, 245, 248), "bar": (40, 25, 35), "text": INK, "text2": (110, 75, 95), "accent": (230, 100, 145), "badge_bg": (200, 90, 140), "badge_text": WHITE, "card_bg": (255, 225, 235)},
    "martin": {"bg": (20, 30, 50), "bar": (10, 15, 30), "text": WHITE, "text2": (175, 185, 210), "accent": ACCENT, "badge_bg": GREEN, "badge_text": WHITE, "card_bg": (30, 45, 75)},
}

RITMO = {
    "maria": {"hook": 3.0, "slide": 2.8, "proof": 4.0, "cta": 4.5, "transition": 0.5},
    "lucas": {"hook": 2.0, "slide": 2.0, "proof": 3.0, "cta": 3.5, "transition": 0.3},
    "ana":   {"hook": 2.5, "slide": 2.5, "proof": 3.5, "cta": 4.0, "transition": 0.5},
    "sofi":  {"hook": 2.5, "slide": 2.2, "proof": 3.5, "cta": 4.0, "transition": 0.4},
    "martin":{"hook": 2.5, "slide": 2.5, "proof": 3.5, "cta": 4.0, "transition": 0.4},
}

# Multiplicador de duración por tipo de reel
# < 1.0 = más corto, > 1.0 = más largo
REEL_DURATION_SCALE = {
    "R01": 1.0,   # Classic (20-25s)
    "R02": 1.1,   # Antes/después (22-28s) — necesita tiempo para el contraste
    "R03": 0.6,   # Número corto (12-15s) — viral, rápido
    "R04": 1.3,   # Storytelling (26-32s) — necesita desarrollo
    "R05": 1.0,   # Paso a paso (20-25s)
    "R06": 1.0,   # Mito/realidad (20-25s)
    "R07": 0.9,   # Producto (18-22s)
    "R08": 1.0,   # Comparativa (20-25s)
    "R09": 0.9,   # Checklist (18-22s)
    "R10": 0.5,   # Dato viral (10-12s) — ultra corto, impacto
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


# ── Elementos decorativos por persona (psicología visual) ──

def _v(base, var, rang=22):
    """Desplaza una coordenada entre slides — notorio pero controlado."""
    offsets = [0, 18, -12, 25, -20, 10, -15, 22, -8, 16]
    return base + offsets[var % len(offsets)] * rang // 22


def _decor_color(pal):
    """Color de decorativos con contraste garantizado sobre el fondo."""
    bg_lum = sum(pal["bg"][:3]) / 3
    if bg_lum > 180:
        return (180, 160, 120)
    elif bg_lum > 80:
        return (120, 110, 100)
    else:
        return (60, 65, 80)


def _decor_maria(draw, pal, var=0):
    """María: círculos suaves, puntos dispersos — calidez, seguridad maternal."""
    c = _decor_color(pal)
    for cx, cy, r in [(120, 250, 35), (950, 300, 25), (80, 1500, 30), (980, 1550, 20), (200, 1600, 15), (900, 1650, 22)]:
        dx, dy = _v(cx, var, 22), _v(cy, var, 18)
        draw.ellipse([dx - r, dy - r, dx + r, dy + r], outline=c, width=3)
    for cx, cy in [(160, 350), (920, 400), (100, 1400), (960, 1480), (200, 1700), (880, 1720), (500, 200), (600, 1680)]:
        dx, dy = _v(cx, var, 18), _v(cy, var, 15)
        draw.ellipse([dx - 6, dy - 6, dx + 6, dy + 6], fill=c)


def _decor_lucas(draw, pal, var=0):
    """Lucas: líneas diagonales, flechas — energía, acción, movimiento."""
    c = _decor_color(pal)
    draw.line([(_v(0, var, 20), _v(200, var, 18)), (_v(180, var, 20), _v(100, var, 18))], fill=c, width=2)
    draw.line([(_v(W, var, 20), _v(250, var, 18)), (_v(W - 160, var, 20), _v(150, var, 18))], fill=c, width=2)
    draw.line([(_v(0, var, 20), _v(1550, var, 18)), (_v(140, var, 20), _v(1650, var, 18))], fill=c, width=2)
    draw.line([(_v(W, var, 20), _v(1500, var, 18)), (_v(W - 120, var, 20), _v(1600, var, 18))], fill=c, width=2)
    for bx, by, s in [(60, 300, 20), (W - 80, 350, 16), (80, 1450, 18), (W - 60, 1500, 14)]:
        dx, dy = _v(bx, var, 20), _v(by, var, 18)
        draw.rectangle([dx, dy, dx + s, dy + s], outline=c, width=2)


def _decor_ana(draw, pal, var=0):
    """Ana: líneas finas horizontales, grid sutil — profesionalismo, estructura."""
    c = _decor_color(pal)
    positions = [220, 260, 1560, 1600]
    for i, y_pos in enumerate(positions):
        dy = _v(y_pos, var + i, 18)
        margin = 80 + (var * 5 + i * 10) % 30
        draw.line([(margin, dy), (W - margin, dy)], fill=c, width=1)


def _decor_sofi(draw, pal, var=0):
    """Sofi: formas orgánicas suaves — autenticidad, creatividad."""
    c = _decor_color(pal)
    for cx, cy, rx, ry in [(100, 280, 50, 35), (960, 320, 40, 28), (120, 1520, 45, 30), (940, 1580, 35, 25)]:
        dx, dy = _v(cx, var, 22), _v(cy, var, 18)
        draw.ellipse([dx - rx, dy - ry, dx + rx, dy + ry], outline=c, width=2)
    for cx, cy in [(180, 350), (880, 380), (200, 1620), (860, 1660)]:
        dx, dy = _v(cx, var, 18), _v(cy, var, 15)
        draw.ellipse([dx - 6, dy - 6, dx + 6, dy + 6], fill=c)


def _decor_martin(draw, pal, var=0):
    """Martín: barras gruesas, bordes sólidos — estabilidad, negocio, resultados."""
    c = _decor_color(pal)
    bars = [(60, 220, 80, 320), (W - 80, 240, W - 60, 340), (60, 1500, 80, 1600), (W - 80, 1520, W - 60, 1620)]
    for i, (x1, y1, x2, y2) in enumerate(bars):
        dy = _v(0, var + i, 18)
        draw.rectangle([x1, y1 + dy, x2, y2 + dy], fill=c)
    crosses = [(120, 280), (W - 120, 300), (120, 1560), (W - 120, 1580)]
    for i, (x, y) in enumerate(crosses):
        dx, dy = _v(x, var + i, 18), _v(y, var + i, 15)
        draw.line([(dx - 10, dy), (dx + 10, dy)], fill=c, width=3)
        draw.line([(dx, dy - 10), (dx, dy + 10)], fill=c, width=3)


DECOR_MAP = {
    "maria": _decor_maria,
    "lucas": _decor_lucas,
    "ana": _decor_ana,
    "sofi": _decor_sofi,
    "martin": _decor_martin,
}


def _apply_decor(draw, pal, persona, slide_index=0):
    fn = DECOR_MAP.get(persona)
    if fn:
        fn(draw, pal, slide_index)


# ── Drawing helpers ──

def _shadow(draw, xy, text, font, fill, offset=0):
    draw.text(xy, text, fill=fill, font=font)


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

VISUAL_STYLES = ["centered", "bold", "card", "gradient"]


def _highlight_lines(draw, text, font, fill, highlight_color, max_w, base_y, spacing=8):
    """Texto centrado con highlight/marcador detrás de cada línea."""
    lines = _wrap(text, font, max_w, draw)[:5]
    bbox_h = draw.textbbox((0, 0), "Ay", font=font)[3]
    gap = bbox_h + spacing
    pad_x, pad_y = 18, 6
    for i, line in enumerate(lines):
        lw = draw.textbbox((0, 0), line, font=font)[2]
        x = (W - lw) // 2
        y = base_y + i * gap
        draw.rounded_rectangle([x - pad_x, y - pad_y, x + lw + pad_x, y + bbox_h + pad_y], radius=8, fill=highlight_color)
        draw.text((x, y), line, fill=fill, font=font)
    return base_y + len(lines) * gap


def _gradient_bg(img, color_top, color_bot):
    """Aplica un degradé vertical entre dos colores."""
    pixels = img.load()
    for y in range(H):
        t = y / H
        r = int(color_top[0] * (1 - t) + color_bot[0] * t)
        g = int(color_top[1] * (1 - t) + color_bot[1] * t)
        b = int(color_top[2] * (1 - t) + color_bot[2] * t)
        for x in range(W):
            pixels[x, y] = (r, g, b)


# ── Slide renderers ──

def _slide_standard(pal, text, font_size=52, bar_text="elgadget.com.ar/referidos", style="centered", persona="lucas", slide_index=0):
    img = Image.new("RGB", (W, H), pal["bg"])
    if style == "gradient":
        dark = tuple(max(0, c - 40) for c in pal["bg"])
        _gradient_bg(img, dark, pal["bg"])
    draw = ImageDraw.Draw(img)
    _apply_decor(draw, pal, persona, slide_index)
    _top_bar(img, draw, pal)
    tf = _font("h", font_size)
    lines = _wrap(text, tf, 860, draw)[:5]
    bbox_h = draw.textbbox((0, 0), "Ay", font=tf)[3]
    total_h = len(lines) * (bbox_h + 14)
    base_y = (H - total_h) // 2

    if style == "bold":
        hl_color = (*pal["accent"][:3],) if len(pal["accent"]) >= 3 else pal["accent"]
        _highlight_lines(draw, text, tf, INK, hl_color, 860, base_y, 14)
    elif style == "card":
        pad = 50
        card_y1 = base_y - pad
        card_y2 = base_y + total_h + pad
        card_bg = pal["card_bg"]
        draw.rounded_rectangle([60, card_y1, W - 60, card_y2], radius=28, fill=card_bg)
        draw.line([(60, card_y1 + 28), (60, card_y2 - 28)], fill=pal["accent"], width=6)
        _centered_lines(draw, text, tf, pal["text"], 800, base_y, 14)
    else:
        _centered_lines(draw, text, tf, pal["text"], 860, base_y, 14)

    _bottom_bar(draw, bar_text, pal)
    return np.array(img)


def _slide_hook(pal, hook, style="centered", persona="lucas", slide_index=0):
    img = Image.new("RGB", (W, H), pal["bg"])
    if style == "gradient":
        dark = tuple(max(0, c - 50) for c in pal["bg"])
        _gradient_bg(img, dark, pal["bg"])
    draw = ImageDraw.Draw(img)
    _apply_decor(draw, pal, persona, slide_index)
    _top_bar(img, draw, pal)
    hf = _font("h", 78)
    lines = _wrap(hook, hf, 860, draw)[:3]
    bbox_h = draw.textbbox((0, 0), "Ay", font=hf)[3]
    total_h = len(lines) * (bbox_h + 20)
    base_y = (H - total_h) // 2 - 40

    if style == "bold":
        y = _highlight_lines(draw, hook, hf, INK, pal["accent"], 860, base_y, 20)
    elif style == "card":
        pad = 50
        card_bg = pal["card_bg"]
        draw.rounded_rectangle([50, base_y - pad, W - 50, base_y + total_h + pad + 20], radius=30, fill=card_bg)
        draw.line([(50, base_y + total_h + pad - 2), (W - 50, base_y + total_h + pad - 2)], fill=pal["accent"], width=5)
        y = _centered_lines(draw, hook, hf, pal["text"], 820, base_y, 20)
    else:
        y = _centered_lines(draw, hook, hf, pal["text"], 860, base_y, 20)
        draw.line([(W // 2 - 200, y + 10), (W // 2 + 200, y + 10)], fill=pal["accent"], width=4)

    _bottom_bar(draw, "elgadget.com.ar/referidos", pal)
    return np.array(img)


def _slide_proof_counting(pal, numero_text, subtexto, frame_progress, style="centered", persona="lucas", slide_index=0):
    img = Image.new("RGB", (W, H), pal["bg"])
    if style == "gradient":
        dark = tuple(max(0, c - 40) for c in pal["bg"])
        _gradient_bg(img, dark, pal["bg"])
    draw = ImageDraw.Draw(img)
    _apply_decor(draw, pal, persona, slide_index)
    _top_bar(img, draw, pal)

    cleaned = numero_text.replace(".", "").replace(",", "")
    prefix = ""
    suffix = ""
    digits_started = False
    digits_ended = False
    for c in cleaned:
        if c.isdigit():
            digits_started = True
        elif not digits_started:
            prefix += c
        elif digits_started:
            digits_ended = True
        if digits_ended:
            suffix += c
    digits = ''.join(c for c in cleaned if c.isdigit())
    target = int(digits) if digits else 0

    linear = min(frame_progress * 1.5, 1.0)
    current = int(target * linear)
    if target < 100:
        display = f"{prefix}{current}{suffix}"
    else:
        display = f"{prefix}{current:,.0f}{suffix}".replace(",", ".")

    if style == "card":
        card_w, card_h = 740, 420
        cx = (W - card_w) // 2
        cy = H // 2 - card_h // 2 - 40
        draw.rounded_rectangle([cx, cy, cx + card_w, cy + card_h], radius=28, fill=pal["card_bg"])
        draw.line([(cx, cy + card_h - 6), (cx + card_w, cy + card_h - 6)], fill=pal["accent"], width=6)
        nf = _font("h", 100)
        nw = draw.textbbox((0, 0), display, font=nf)[2]
        _shadow(draw, ((W - nw) // 2, cy + 70), display, nf, pal["accent"])
        if frame_progress > 0.3:
            sf = _font("m", 28)
            lines = _wrap(subtexto, sf, card_w - 60, draw)[:3]
            sy = cy + 220
            for line in lines:
                sw = draw.textbbox((0, 0), line, font=sf)[2]
                draw.text(((W - sw) // 2, sy), line, fill=pal["text2"], font=sf)
                sy += 40
    elif style == "bold":
        nf = _font("h", 120)
        nw = draw.textbbox((0, 0), display, font=nf)[2]
        pad_x, pad_y = 30, 10
        nx = (W - nw) // 2
        ny = H // 2 - 180
        draw.rounded_rectangle([nx - pad_x, ny - pad_y, nx + nw + pad_x, ny + 120 + pad_y], radius=12, fill=pal["accent"])
        draw.text((nx, ny), display, fill=INK, font=nf)
        if frame_progress > 0.3:
            sf = _font("m", 32)
            lines = _wrap(subtexto, sf, 800, draw)[:3]
            y = H // 2 + 20
            for line in lines:
                sw = draw.textbbox((0, 0), line, font=sf)[2]
                _shadow(draw, ((W - sw) // 2, y), line, sf, pal["text2"])
                y += 44
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

    _bottom_bar(draw, "elgadget.com.ar/referidos", pal)
    return np.array(img)


def _slide_benefit(pal, texto, badge_text="Sin inversion - Desde el celular", style="centered", persona="lucas", slide_index=0):
    img = Image.new("RGB", (W, H), pal["bg"])
    if style == "gradient":
        dark = tuple(max(0, c - 40) for c in pal["bg"])
        _gradient_bg(img, dark, pal["bg"])
    draw = ImageDraw.Draw(img)
    _apply_decor(draw, pal, persona, slide_index)
    _top_bar(img, draw, pal)
    bf = _font("h", 56)
    bbf = _font("h", 24)
    lines = _wrap(texto, bf, 860, draw)[:4]
    bbox_h = draw.textbbox((0, 0), "Ay", font=bf)[3]
    total_h = len(lines) * (bbox_h + 14)

    if style == "card":
        base_y = (H - total_h) // 2 - 60
        pad = 50
        card_bg = pal["card_bg"]
        draw.rounded_rectangle([60, base_y - pad, W - 60, base_y + total_h + pad + 70], radius=28, fill=card_bg)
        y = _centered_lines(draw, texto, bf, pal["text"], 800, base_y, 14)
        bbw = draw.textbbox((0, 0), badge_text, font=bbf)[2] + 40
        bx = (W - bbw) // 2
        draw.rounded_rectangle([bx, y + 20, bx + bbw, y + 68], radius=24, fill=pal["accent"])
        draw.text((bx + 20, y + 30), badge_text, fill=INK, font=bbf)
    elif style == "bold":
        base_y = (H - total_h) // 2 - 50
        y = _highlight_lines(draw, texto, bf, INK, pal["accent"], 860, base_y, 14)
        bbw = draw.textbbox((0, 0), badge_text, font=bbf)[2] + 40
        bx = (W - bbw) // 2
        draw.rounded_rectangle([bx, y + 20, bx + bbw, y + 68], radius=24, fill=pal["bar"])
        draw.text((bx + 20, y + 30), badge_text, fill=WHITE, font=bbf)
    else:
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
    reel_type="R01",
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
    base_ritmo = RITMO.get(persona, RITMO["lucas"])
    scale = REEL_DURATION_SCALE.get(reel_type, 1.0)
    ritmo = {k: round(v * scale, 1) if k != "transition" else v for k, v in base_ritmo.items()}
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

    si = 0
    if hook:
        slides.append(("hook", _slide_hook(pal, hook, style, persona, si)))
        durations.append(ritmo["hook"])
        transitions.append("zoom")
        si += 1

    if dolor:
        slides.append(("dolor", _slide_standard(pal, dolor, 50, "elgadget.com.ar/referidos", style, persona, si)))
        durations.append(ritmo["slide"])
        transitions.append("slide_right")
        si += 1

    if solucion:
        slides.append(("solucion", _slide_standard(pal, solucion, 48, "elgadget.com.ar/referidos", style, persona, si)))
        durations.append(ritmo["slide"])
        transitions.append("crossfade")
        si += 1

    proof_si = si
    if numero_grande:
        slides.append(("proof", None))
        durations.append(ritmo["proof"])
        transitions.append("scale_in")
        si += 1

    if beneficio:
        slides.append(("benefit", _slide_benefit(pal, beneficio, style=style, persona=persona, slide_index=si)))
        durations.append(ritmo["slide"])
        transitions.append("crossfade")
        si += 1

    if dato_extra:
        slides.append(("extra", _slide_standard(pal, dato_extra, 44, "elgadget.com.ar/referidos", style, persona, si)))
        durations.append(2.0)
        transitions.append("slide_right")
        si += 1

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
                frame = _slide_proof_counting(pal, numero_grande, subtexto_proof, progress, style, persona, proof_si)
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
            next_static = next_arr if next_arr is not None else _slide_proof_counting(pal, numero_grande, subtexto_proof, 0.0, style, persona, proof_si)

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
                music_clip = music_clip.with_volume_scaled(0.06)
            else:
                music_clip = music_clip.with_volume_scaled(0.25)
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


# ── Slide renderers para variantes R02-R10 ──

def _slide_antes_despues(pal, label, text, is_positive, persona, slide_index):
    """Renders ANTES/DESPUES or MITO/REALIDAD cards. Red tint negative, green positive."""
    import random as _rnd
    style = _rnd.choice(VISUAL_STYLES)
    img = Image.new("RGB", (W, H), pal["bg"])
    if style == "gradient":
        dark = tuple(max(0, c - 40) for c in pal["bg"])
        _gradient_bg(img, dark, pal["bg"])
    draw = ImageDraw.Draw(img)
    _apply_decor(draw, pal, persona, slide_index)
    _top_bar(img, draw, pal)

    # Tint color for the card
    if is_positive:
        tint = (30, 120, 60)
        label_color = (46, 180, 90)
    else:
        tint = (140, 30, 30)
        label_color = (200, 50, 50)

    # Card background with tint
    card_bg = tuple(min(255, c + 20) for c in tint)
    card_w, card_h = 900, 500
    cx = (W - card_w) // 2
    cy = H // 2 - card_h // 2 - 40
    draw.rounded_rectangle([cx, cy, cx + card_w, cy + card_h], radius=28, fill=card_bg)
    draw.line([(cx, cy + card_h - 6), (cx + card_w, cy + card_h - 6)], fill=label_color, width=6)

    # Label
    lf = _font("h", 60)
    lw = draw.textbbox((0, 0), label, font=lf)[2]
    _shadow(draw, ((W - lw) // 2, cy + 40), label, lf, WHITE)

    # Separator line
    sep_y = cy + 130
    draw.line([(cx + 60, sep_y), (cx + card_w - 60, sep_y)], fill=label_color, width=3)

    # Text content
    tf = _font("h", 44)
    _centered_lines(draw, text, tf, WHITE, card_w - 120, cy + 160, 14)

    _bottom_bar(draw, "elgadget.com.ar/referidos", pal)
    return np.array(img)


def _slide_step(pal, step_num, text, persona, slide_index):
    """Renders a step with big number + text."""
    import random as _rnd
    style = _rnd.choice(VISUAL_STYLES)
    img = Image.new("RGB", (W, H), pal["bg"])
    if style == "gradient":
        dark = tuple(max(0, c - 40) for c in pal["bg"])
        _gradient_bg(img, dark, pal["bg"])
    draw = ImageDraw.Draw(img)
    _apply_decor(draw, pal, persona, slide_index)
    _top_bar(img, draw, pal)

    # Big step number
    nf = _font("h", 180)
    num_str = str(step_num)
    nw = draw.textbbox((0, 0), num_str, font=nf)[2]
    nh = draw.textbbox((0, 0), num_str, font=nf)[3]
    _shadow(draw, ((W - nw) // 2, H // 2 - 280), num_str, nf, pal["accent"])

    # Separator
    sep_y = H // 2 - 60
    draw.line([(W // 2 - 150, sep_y), (W // 2 + 150, sep_y)], fill=pal["accent"], width=4)

    # Step text
    tf = _font("h", 48)
    _centered_lines(draw, text, tf, pal["text"], 860, H // 2, 14)

    _bottom_bar(draw, "elgadget.com.ar/referidos", pal)
    return np.array(img)


def _slide_check_item(pal, text, persona, slide_index):
    """Renders a checklist item with checkmark in accent color + text."""
    import random as _rnd
    style = _rnd.choice(VISUAL_STYLES)
    img = Image.new("RGB", (W, H), pal["bg"])
    if style == "gradient":
        dark = tuple(max(0, c - 40) for c in pal["bg"])
        _gradient_bg(img, dark, pal["bg"])
    draw = ImageDraw.Draw(img)
    _apply_decor(draw, pal, persona, slide_index)
    _top_bar(img, draw, pal)

    # Checkmark
    check = "✓"
    cf = _font("h", 140)
    cw = draw.textbbox((0, 0), check, font=cf)[2]
    _shadow(draw, ((W - cw) // 2, H // 2 - 260), check, cf, pal["accent"])

    # Separator
    sep_y = H // 2 - 60
    draw.line([(W // 2 - 150, sep_y), (W // 2 + 150, sep_y)], fill=pal["accent"], width=4)

    # Item text
    tf = _font("h", 52)
    _centered_lines(draw, text, tf, pal["text"], 860, H // 2, 14)

    _bottom_bar(draw, "elgadget.com.ar/referidos", pal)
    return np.array(img)


def _slide_precio(pal, nombre, precio_orig, precio_desc, persona, slide_index):
    """Renders price comparison: original crossed out + discounted price."""
    import random as _rnd
    style = _rnd.choice(VISUAL_STYLES)
    img = Image.new("RGB", (W, H), pal["bg"])
    if style == "gradient":
        dark = tuple(max(0, c - 40) for c in pal["bg"])
        _gradient_bg(img, dark, pal["bg"])
    draw = ImageDraw.Draw(img)
    _apply_decor(draw, pal, persona, slide_index)
    _top_bar(img, draw, pal)

    # Product name
    nf = _font("h", 48)
    _centered_lines(draw, nombre, nf, pal["text"], 860, H // 2 - 280, 14)

    # Original price (crossed out)
    opf = _font("h", 56)
    orig_str = str(precio_orig)
    ow = draw.textbbox((0, 0), orig_str, font=opf)[2]
    oh = draw.textbbox((0, 0), orig_str, font=opf)[3]
    ox = (W - ow) // 2
    oy = H // 2 - 100
    _shadow(draw, (ox, oy), orig_str, opf, pal["text2"])
    # Strikethrough line
    draw.line([(ox - 10, oy + oh // 2), (ox + ow + 10, oy + oh // 2)], fill=(200, 50, 50), width=4)

    # Discounted price (big, accent color)
    dpf = _font("h", 90)
    desc_str = str(precio_desc)
    dw = draw.textbbox((0, 0), desc_str, font=dpf)[2]
    _shadow(draw, ((W - dw) // 2, H // 2 + 20), desc_str, dpf, pal["accent"])

    # Savings badge
    badge = "PRECIO REFERIDO"
    bf = _font("h", 26)
    bw = draw.textbbox((0, 0), badge, font=bf)[2] + 40
    bx = (W - bw) // 2
    by = H // 2 + 170
    draw.rounded_rectangle([bx, by, bx + bw, by + 50], radius=24, fill=pal["accent"])
    draw.text((bx + 20, by + 12), badge, fill=INK, font=bf)

    _bottom_bar(draw, "elgadget.com.ar/referidos", pal)
    return np.array(img)


def _slide_dato_gigante(pal, dato, persona, slide_index):
    """Renders just a giant number/stat centered (no hook, just the number)."""
    import random as _rnd
    style = _rnd.choice(VISUAL_STYLES)
    img = Image.new("RGB", (W, H), pal["bg"])
    if style == "gradient":
        dark = tuple(max(0, c - 50) for c in pal["bg"])
        _gradient_bg(img, dark, pal["bg"])
    draw = ImageDraw.Draw(img)
    _apply_decor(draw, pal, persona, slide_index)
    _top_bar(img, draw, pal)

    # Giant number/stat
    df = _font("h", 140)
    lines = _wrap(dato, df, 960, draw)[:2]
    bbox_h = draw.textbbox((0, 0), "Ay", font=df)[3]
    total_h = len(lines) * (bbox_h + 20)
    base_y = (H - total_h) // 2 - 40

    for i, line in enumerate(lines):
        lw = draw.textbbox((0, 0), line, font=df)[2]
        _shadow(draw, ((W - lw) // 2, base_y + i * (bbox_h + 20)), line, df, pal["accent"])

    _bottom_bar(draw, "elgadget.com.ar/referidos", pal)
    return np.array(img)


def _slide_comision(pal, comision_text, persona, slide_index):
    """Renders commission calculation slide."""
    import random as _rnd
    style = _rnd.choice(VISUAL_STYLES)
    img = Image.new("RGB", (W, H), pal["bg"])
    if style == "gradient":
        dark = tuple(max(0, c - 40) for c in pal["bg"])
        _gradient_bg(img, dark, pal["bg"])
    draw = ImageDraw.Draw(img)
    _apply_decor(draw, pal, persona, slide_index)
    _top_bar(img, draw, pal)

    # Label
    lf = _font("h", 36)
    label = "TU COMISION"
    lw = draw.textbbox((0, 0), label, font=lf)[2]
    _shadow(draw, ((W - lw) // 2, H // 2 - 220), label, lf, pal["text2"])

    # Separator
    draw.line([(W // 2 - 150, H // 2 - 160), (W // 2 + 150, H // 2 - 160)], fill=pal["accent"], width=3)

    # Big commission amount
    cf = _font("h", 100)
    cw = draw.textbbox((0, 0), comision_text, font=cf)[2]
    _shadow(draw, ((W - cw) // 2, H // 2 - 120), comision_text, cf, pal["accent"])

    # Sub-label
    sf = _font("m", 30)
    sub = "por cada venta referida"
    sw = draw.textbbox((0, 0), sub, font=sf)[2]
    _shadow(draw, ((W - sw) // 2, H // 2 + 30), sub, sf, pal["text2"])

    _bottom_bar(draw, "elgadget.com.ar/referidos", pal)
    return np.array(img)


def _slide_bullets(pal, bullets, persona, slide_index):
    """Renders 3 bullet points stacked centered."""
    import random as _rnd
    style = _rnd.choice(VISUAL_STYLES)
    img = Image.new("RGB", (W, H), pal["bg"])
    if style == "gradient":
        dark = tuple(max(0, c - 40) for c in pal["bg"])
        _gradient_bg(img, dark, pal["bg"])
    draw = ImageDraw.Draw(img)
    _apply_decor(draw, pal, persona, slide_index)
    _top_bar(img, draw, pal)

    bf = _font("h", 46)
    bbox_h = draw.textbbox((0, 0), "Ay", font=bf)[3]
    gap = bbox_h + 50
    total_h = len(bullets) * gap
    base_y = (H - total_h) // 2

    for i, bullet in enumerate(bullets[:3]):
        dot = "•"
        line = f"{dot}  {bullet}"
        lw = draw.textbbox((0, 0), line, font=bf)[2]
        _shadow(draw, ((W - lw) // 2, base_y + i * gap), line, bf, pal["text"])

    _bottom_bar(draw, "elgadget.com.ar/referidos", pal)
    return np.array(img)


# ── Compositor de variantes R02-R10 ──

def compose_reel_variant(
    reel_type="R02",
    persona="lucas",
    hook="",
    antes_texto="", despues_texto="",
    numero_grande="", subtexto_proof="",
    bullets=None,
    historia_slides=None,
    pasos=None,
    mitos=None, realidades=None,
    producto_nombre="", precio_original="", precio_descuento="", comision="",
    otros_stats="", gadget_stats="",
    items_check=None,
    dato_grande="", dato_contexto="", dato_como="",
    beneficio="",
    cta_text="",
    voiceover_text="",
    output_filename=None,
) -> str:
    """
    Genera un Reel con estructura variable segun reel_type (R02-R10).

    Cada tipo tiene su propia cantidad de slides y estructura,
    pero reutiliza los helpers existentes y el sistema de paletas/ritmo/decor.

    Args:
        reel_type: tipo de reel (R02-R10)
        persona: buyer persona (paleta + ritmo)
        hook: frase hook (slide 1 en la mayoria)
        antes_texto/despues_texto: textos para R02
        numero_grande/subtexto_proof: para conteo animado (R03, R10)
        bullets: lista de 3 strings (R03)
        historia_slides: lista de 4 strings (R04)
        pasos: lista de 4 strings (R05)
        mitos/realidades: listas de 2 strings cada una (R06)
        producto_nombre/precio_original/precio_descuento/comision: R07
        otros_stats/gadget_stats: R08
        items_check: lista de 5 strings (R09)
        dato_grande/dato_contexto/dato_como: R10
        beneficio: texto beneficio generico
        cta_text: texto del CTA final
        voiceover_text: texto completo para voz en off (opcional)
        output_filename: nombre del archivo de salida

    Returns: path al .mp4
    """
    from moviepy import VideoClip, AudioFileClip, CompositeAudioClip

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    pal = PALETAS.get(persona, PALETAS["lucas"])
    base_ritmo = RITMO.get(persona, RITMO["lucas"])
    scale = REEL_DURATION_SCALE.get(reel_type, 1.0)
    ritmo = {k: round(v * scale, 1) if k != "transition" else v for k, v in base_ritmo.items()}
    if not output_filename:
        import time as _t
        output_filename = f"reel_{reel_type}_{persona}_{int(_t.time())}.mp4"
    if not cta_text:
        cta_text = "¿Queres empezar a ganar?"

    import random as _rnd
    style = _rnd.choice(VISUAL_STYLES)
    trans_frames = int(ritmo["transition"] * FPS)
    print(f"[REEL {reel_type}] Estilo visual: {style}")

    slides = []
    durations = []
    transitions = []
    proof_si = None
    si = 0

    if reel_type == "R02":
        # Antes/despues: 5 slides, ~18s
        if hook:
            slides.append(("hook", _slide_hook(pal, hook, style, persona, si)))
            durations.append(ritmo["hook"])
            transitions.append("zoom")
            si += 1

        slides.append(("antes", _slide_antes_despues(pal, "ANTES", antes_texto, False, persona, si)))
        durations.append(ritmo["slide"])
        transitions.append("slide_right")
        si += 1

        slides.append(("despues", _slide_antes_despues(pal, "DESPUES", despues_texto, True, persona, si)))
        durations.append(ritmo["slide"])
        transitions.append("crossfade")
        si += 1

        proof_si = si
        if numero_grande:
            slides.append(("proof", None))
            durations.append(ritmo["proof"])
            transitions.append("scale_in")
            si += 1

        slides.append(("cta", _slide_cta(pal, cta_text)))
        durations.append(ritmo["cta"])
        transitions.append("crossfade")

    elif reel_type == "R03":
        # Numero corto: 4 slides, ~12s
        if hook:
            slides.append(("hook", _slide_hook(pal, hook, style, persona, si)))
            durations.append(ritmo["hook"])
            transitions.append("zoom")
            si += 1

        proof_si = si
        if numero_grande:
            slides.append(("proof", None))
            durations.append(ritmo["proof"])
            transitions.append("scale_in")
            si += 1

        if bullets:
            slides.append(("bullets", _slide_bullets(pal, bullets, persona, si)))
            durations.append(ritmo["slide"])
            transitions.append("crossfade")
            si += 1

        slides.append(("cta", _slide_cta(pal, cta_text)))
        durations.append(ritmo["cta"])
        transitions.append("crossfade")

    elif reel_type == "R04":
        # Storytelling: 6 slides, ~20s
        if hook:
            slides.append(("hook", _slide_hook(pal, hook, style, persona, si)))
            durations.append(ritmo["hook"])
            transitions.append("zoom")
            si += 1

        historia = historia_slides or ["", "", "", ""]
        for h_text in historia[:4]:
            slides.append(("story", _slide_standard(pal, h_text, 52, "elgadget.com.ar/referidos", style, persona, si)))
            durations.append(ritmo["slide"])
            transitions.append("crossfade")
            si += 1

        slides.append(("cta", _slide_cta(pal, cta_text)))
        durations.append(ritmo["cta"])
        transitions.append("crossfade")

    elif reel_type == "R05":
        # Paso a paso: 6 slides, ~20s
        if hook:
            slides.append(("hook", _slide_hook(pal, hook, style, persona, si)))
            durations.append(ritmo["hook"])
            transitions.append("zoom")
            si += 1

        steps = pasos or ["", "", "", ""]
        for step_i, step_text in enumerate(steps[:4], 1):
            slides.append(("step", _slide_step(pal, step_i, step_text, persona, si)))
            durations.append(ritmo["slide"])
            transitions.append("slide_right")
            si += 1

        slides.append(("cta", _slide_cta(pal, cta_text)))
        durations.append(ritmo["cta"])
        transitions.append("crossfade")

    elif reel_type == "R06":
        # Mito vs realidad: 6 slides, ~20s
        if hook:
            slides.append(("hook", _slide_hook(pal, hook, style, persona, si)))
            durations.append(ritmo["hook"])
            transitions.append("zoom")
            si += 1

        mitos_list = mitos or ["", ""]
        realidades_list = realidades or ["", ""]
        for m_i in range(min(2, len(mitos_list))):
            slides.append(("mito", _slide_antes_despues(pal, "MITO", mitos_list[m_i], False, persona, si)))
            durations.append(ritmo["slide"])
            transitions.append("slide_right")
            si += 1

            if m_i < len(realidades_list):
                slides.append(("realidad", _slide_antes_despues(pal, "REALIDAD", realidades_list[m_i], True, persona, si)))
                durations.append(ritmo["slide"])
                transitions.append("crossfade")
                si += 1

        slides.append(("cta", _slide_cta(pal, cta_text)))
        durations.append(ritmo["cta"])
        transitions.append("crossfade")

    elif reel_type == "R07":
        # Producto showcase: 5 slides, ~18s
        if hook:
            slides.append(("hook", _slide_hook(pal, hook, style, persona, si)))
            durations.append(ritmo["hook"])
            transitions.append("zoom")
            si += 1

        slides.append(("precio", _slide_precio(pal, producto_nombre, precio_original, precio_descuento, persona, si)))
        durations.append(ritmo["slide"])
        transitions.append("scale_in")
        si += 1

        if comision:
            slides.append(("comision", _slide_comision(pal, comision, persona, si)))
            durations.append(ritmo["slide"])
            transitions.append("crossfade")
            si += 1

        if beneficio:
            slides.append(("benefit", _slide_benefit(pal, beneficio, style=style, persona=persona, slide_index=si)))
            durations.append(ritmo["slide"])
            transitions.append("crossfade")
            si += 1

        slides.append(("cta", _slide_cta(pal, cta_text)))
        durations.append(ritmo["cta"])
        transitions.append("crossfade")

    elif reel_type == "R08":
        # Comparativa: 5 slides, ~18s
        if hook:
            slides.append(("hook", _slide_hook(pal, hook, style, persona, si)))
            durations.append(ritmo["hook"])
            transitions.append("zoom")
            si += 1

        slides.append(("otros", _slide_antes_despues(pal, "OTROS PROGRAMAS", otros_stats, False, persona, si)))
        durations.append(ritmo["slide"])
        transitions.append("slide_right")
        si += 1

        slides.append(("gadget", _slide_antes_despues(pal, "EL GADGET", gadget_stats, True, persona, si)))
        durations.append(ritmo["slide"])
        transitions.append("crossfade")
        si += 1

        if beneficio:
            slides.append(("benefit", _slide_benefit(pal, beneficio, style=style, persona=persona, slide_index=si)))
            durations.append(ritmo["slide"])
            transitions.append("crossfade")
            si += 1

        slides.append(("cta", _slide_cta(pal, cta_text)))
        durations.append(ritmo["cta"])
        transitions.append("crossfade")

    elif reel_type == "R09":
        # Checklist: 7 slides, ~18s
        if hook:
            slides.append(("hook", _slide_hook(pal, hook, style, persona, si)))
            durations.append(ritmo["hook"])
            transitions.append("zoom")
            si += 1

        items = items_check or ["", "", "", "", ""]
        for item_text in items[:5]:
            slides.append(("check", _slide_check_item(pal, item_text, persona, si)))
            durations.append(ritmo["slide"] * 0.7)
            transitions.append("slide_right")
            si += 1

        slides.append(("cta", _slide_cta(pal, cta_text)))
        durations.append(ritmo["cta"])
        transitions.append("crossfade")

    elif reel_type == "R10":
        # Dato viral: 4 slides, ~10s (shortest)
        slides.append(("dato", _slide_dato_gigante(pal, dato_grande, persona, si)))
        durations.append(ritmo["hook"])
        transitions.append("zoom")
        si += 1

        slides.append(("contexto", _slide_standard(pal, dato_contexto, 48, "elgadget.com.ar/referidos", style, persona, si)))
        durations.append(ritmo["slide"])
        transitions.append("crossfade")
        si += 1

        slides.append(("como", _slide_standard(pal, dato_como, 46, "elgadget.com.ar/referidos", style, persona, si)))
        durations.append(ritmo["slide"])
        transitions.append("slide_right")
        si += 1

        slides.append(("cta", _slide_cta(pal, cta_text)))
        durations.append(ritmo["cta"])
        transitions.append("crossfade")

    else:
        raise ValueError(f"Tipo de reel no soportado: {reel_type}")

    # Build all frames (same pattern as compose_reel)
    all_frames = []
    bg_frame = np.full((H, W, 3), pal["bg"], dtype=np.uint8)

    for idx, (slide_type, slide_arr) in enumerate(slides):
        dur = durations[idx]
        hold_n = int(dur * FPS)
        trans_type = transitions[idx]

        if slide_type == "proof":
            for i in range(hold_n):
                progress = i / hold_n
                frame = _slide_proof_counting(pal, numero_grande, subtexto_proof, progress, style, persona, proof_si if proof_si is not None else 0)
                all_frames.append(frame)
        elif slide_type in ("hook", "dato") and trans_type == "zoom":
            static_frames = [slide_arr] * hold_n
            zoomed = _apply_zoom(static_frames, 1.0, 1.08)
            all_frames.extend(zoomed)
        else:
            for _ in range(hold_n):
                all_frames.append(slide_arr)

        if idx < len(slides) - 1:
            next_type, next_arr = slides[idx + 1]
            current_arr = all_frames[-1] if all_frames else bg_frame
            if next_arr is not None:
                next_static = next_arr
            else:
                next_static = _slide_proof_counting(pal, numero_grande, subtexto_proof, 0.0, style, persona, proof_si if proof_si is not None else 0)

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

    # Audio: generar voz primero para saber su duracion
    vo_clip = None
    music_clip = None

    if voiceover_text:
        vo_path = generate_voiceover(voiceover_text, persona)
        if vo_path and Path(vo_path).exists():
            try:
                vo_clip = AudioFileClip(vo_path)
                print(f"[REEL {reel_type}] Voz en off: {vo_path} ({vo_clip.duration:.1f}s)")
            except Exception as e:
                print(f"[REEL {reel_type}] Error loading voiceover: {e}")
                vo_clip = None

    # Si la voz es mas larga que el video, extender el ultimo slide
    if vo_clip and vo_clip.duration > total_duration:
        extra = vo_clip.duration - total_duration + 1.0
        last_frame = all_frames[-1]
        extra_frames = [last_frame] * int(extra * FPS)
        all_frames.extend(extra_frames)
        total_duration = len(all_frames) / FPS
        print(f"[REEL {reel_type}] Video extendido a {total_duration:.1f}s para completar la voz")

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
                music_clip = music_clip.with_volume_scaled(0.06)
            else:
                music_clip = music_clip.with_volume_scaled(0.25)
            print(f"[REEL {reel_type}] Musica: {bg_music_path}")
        except Exception as e:
            print(f"[REEL {reel_type}] Error loading music: {e}")
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
            print(f"[REEL {reel_type}] Error compositing audio: {e}")

    output_path = str(OUTPUT_DIR / output_filename)
    clip.write_videofile(
        output_path, fps=FPS, codec="libx264",
        audio_codec="aac" if audio_parts else None,
        audio=bool(audio_parts),
        preset="medium", threads=4, logger=None,
    )
    clip.close()

    print(f"[REEL {reel_type}] {persona} | {len(slides)} slides | {total_duration:.1f}s | {output_path}")
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
