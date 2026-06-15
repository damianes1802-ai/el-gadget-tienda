#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Genera un GIF animado con el isotipo de El Gadget (mismo diseño del logo del
sitio: insignia oscura con "altavoz" blanco + barras tipo ecualizador) para
usar como banner de cabecera en los emails automáticos.

Salida: pages/assets/img/logo-animado.gif
"""

import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

BASE_DIR = Path(__file__).parent.parent
SALIDA = BASE_DIR / "pages" / "assets" / "img" / "logo-animado.gif"

# Paleta de marca (pages/assets/css/style.css)
INK = "#14151A"
ACCENT = "#FFC700"
ACCENT_DEEP = "#E0AC00"
CREAM = "#F7F6F3"
GRAY = "#6F6A63"
WHITE = "#FFFFFF"

ANCHO, ALTO = 600, 160
BADGE_X, BADGE_Y, BADGE_SIZE = 30, 30, 100

FONT_BOLD = "C:/Windows/Fonts/arialbd.ttf"
FONT_REG = "C:/Windows/Fonts/arial.ttf"

N_FRAMES = 12
DURACION_MS = 110


def dibujar_frame(t: float) -> Image.Image:
    img = Image.new("RGB", (ANCHO, ALTO), WHITE)
    draw = ImageDraw.Draw(img)

    # Insignia (cuadrado redondeado oscuro)
    draw.rounded_rectangle(
        [BADGE_X, BADGE_Y, BADGE_X + BADGE_SIZE, BADGE_Y + BADGE_SIZE],
        radius=22, fill=INK,
    )

    # "Altavoz" blanco (rectángulo redondeado sin relleno + círculo)
    case = [BADGE_X + 14, BADGE_Y + 34, BADGE_X + 86, BADGE_Y + 68]
    draw.rounded_rectangle(case, radius=17, outline=WHITE, width=7)
    cx, cy, r = BADGE_X + 34, BADGE_Y + 51, 6
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=WHITE)

    # Barras tipo ecualizador (animadas)
    bottom = BADGE_Y + 68
    bars = [
        (BADGE_X + 58, 18, 0.0),
        (BADGE_X + 68, 30, 0.6),
        (BADGE_X + 78, 12, 1.2),
    ]
    for x, base_h, fase in bars:
        h = base_h + 9 * math.sin(t + fase)
        h = max(8, h)
        draw.rounded_rectangle([x, bottom - h, x + 6, bottom], radius=2, fill=ACCENT)

    # Texto "El Gadget"
    font_titulo = ImageFont.truetype(FONT_BOLD, 34)
    tx = BADGE_X + BADGE_SIZE + 22
    ty = 48
    draw.text((tx, ty), "El", font=font_titulo, fill=INK)
    ancho_el = draw.textlength("El ", font=font_titulo)
    draw.text((tx + ancho_el, ty), "Gadget", font=font_titulo, fill=ACCENT_DEEP)

    # Tagline
    font_tag = ImageFont.truetype(FONT_REG, 13)
    draw.text((tx + 2, ty + 46), "T I E N D A   O N L I N E", font=font_tag, fill=GRAY)

    return img


def main():
    SALIDA.parent.mkdir(parents=True, exist_ok=True)
    frames = [dibujar_frame(2 * math.pi * i / N_FRAMES) for i in range(N_FRAMES)]
    frames[0].save(
        SALIDA,
        save_all=True,
        append_images=frames[1:],
        duration=DURACION_MS,
        loop=0,
        optimize=False,
    )
    print(f"GIF generado: {SALIDA} ({SALIDA.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
