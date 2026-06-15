#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Genera un GIF animado cuadrado con la insignia de El Gadget (mismo diseño
que el logo de los emails, recortado a la insignia) para usar como ícono del
logo en el header/footer del ecommerce.

Salida: pages/assets/img/logo-badge-animado.gif
"""

import math
from pathlib import Path

from PIL import Image, ImageDraw

BASE_DIR = Path(__file__).parent.parent
SALIDA = BASE_DIR / "pages" / "assets" / "img" / "logo-badge-animado.gif"

# Paleta de marca (pages/assets/css/style.css)
INK = "#14151A"
ACCENT = "#FFC700"
WHITE = "#FFFFFF"

LADO = 200
N_FRAMES = 12
DURACION_MS = 110


def dibujar_frame(t: float) -> Image.Image:
    img = Image.new("RGB", (LADO, LADO), INK)
    draw = ImageDraw.Draw(img)

    # "Altavoz" blanco (rectángulo redondeado sin relleno + círculo)
    draw.rounded_rectangle([28, 68, 172, 136], radius=34, outline=WHITE, width=14)
    draw.ellipse([56, 90, 80, 114], fill=WHITE)

    # Barras tipo ecualizador (animadas)
    bottom = 136
    bars = [
        (116, 36, 0.0),
        (136, 60, 0.6),
        (156, 24, 1.2),
    ]
    for x, base_h, fase in bars:
        h = base_h + 18 * math.sin(t + fase)
        h = max(16, h)
        draw.rounded_rectangle([x, bottom - h, x + 12, bottom], radius=4, fill=ACCENT)

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
