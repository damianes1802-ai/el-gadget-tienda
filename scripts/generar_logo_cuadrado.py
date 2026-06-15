#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Genera un PNG cuadrado con el isotipo de El Gadget para usar como foto de
perfil (ej. cuenta de Google de tienda@elgadget.com.ar). Las fotos de perfil
no admiten GIF animado, por eso esta versión es estática.

Salida: pages/assets/img/logo-cuadrado.png
"""

from pathlib import Path

from PIL import Image, ImageDraw

BASE_DIR = Path(__file__).parent.parent
SALIDA = BASE_DIR / "pages" / "assets" / "img" / "logo-cuadrado.png"

INK = "#14151A"
ACCENT = "#FFC700"
WHITE = "#FFFFFF"
ACCENT_PALE = "#FFF7DD"

LADO = 512
MARGEN = 56  # espacio alrededor de la insignia (queda bien al recortar en círculo)


def main():
    SALIDA.parent.mkdir(parents=True, exist_ok=True)
    img = Image.new("RGB", (LADO, LADO), ACCENT_PALE)
    draw = ImageDraw.Draw(img)

    badge = LADO - 2 * MARGEN
    x0, y0 = MARGEN, MARGEN
    draw.rounded_rectangle([x0, y0, x0 + badge, y0 + badge], radius=int(badge * 0.22), fill=INK)

    s = badge / 100.0  # escala respecto al viewBox 100x100 del logo del sitio
    case = [x0 + 14 * s, y0 + 34 * s, x0 + 86 * s, y0 + 68 * s]
    draw.rounded_rectangle(case, radius=int(17 * s), outline=WHITE, width=int(7 * s))

    cx, cy, r = x0 + 34 * s, y0 + 51 * s, 6 * s
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=WHITE)

    for bx, h in ((58, 18), (68, 30), (78, 12)):
        x = x0 + bx * s
        bottom = y0 + 68 * s
        draw.rounded_rectangle([x, bottom - h * s, x + 6 * s, bottom], radius=int(2 * s), fill=ACCENT)

    img.save(SALIDA)
    print(f"PNG generado: {SALIDA} ({SALIDA.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
