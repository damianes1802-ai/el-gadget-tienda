#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PLACA COMPARTIBLE DEL REFERIDOR

Genera una imagen (formato story 1080x1920) que el referidor puede descargar y
compartir en WhatsApp / Instagram / redes, con su código de referido bien
grande, el descuento y el link de la tienda. Se genera 100% en el servidor con
PIL (sin imágenes externas), así que no hay problemas de CORS ni de descarga.
"""

import io
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

BASE_DIR = Path(__file__).parent.parent.parent
FONTS_DIR = BASE_DIR / "marketing_app" / "assets" / "fonts"
LOGO_PATH = BASE_DIR / "marketing_app" / "assets" / "logo_transparente.png"

W, H = 1080, 1920

INK = (20, 21, 26)
INK_SOFT = (32, 33, 40)
WHITE = (255, 255, 255)
ACCENT = (255, 199, 0)
ACCENT_DEEP = (224, 172, 0)
GRAY = (150, 150, 160)

_FONT_CACHE = {}


def _font(kind, size):
    key = (kind, size)
    if key in _FONT_CACHE:
        return _FONT_CACHE[key]
    files = {
        # SpaceGrotesk del repo está roto (puntero LFS); usamos Inter-Bold, que
        # es lo que ya usa image_composer.py y renderiza bien.
        "grotesk": FONTS_DIR / "Inter-Bold.ttf",
        "bold": FONTS_DIR / "Inter-Bold.ttf",
        "semi": FONTS_DIR / "Inter-SemiBold.ttf",
        "med": FONTS_DIR / "Inter-Medium.ttf",
        "reg": FONTS_DIR / "Inter-Regular.ttf",
    }
    try:
        f = ImageFont.truetype(str(files[kind]), size)
    except Exception:
        f = ImageFont.load_default()
    _FONT_CACHE[key] = f
    return f


def _text_centered(draw, cx, y, text, font, fill, tracking=0):
    """Dibuja texto centrado horizontalmente en cx. Devuelve la altura usada."""
    if tracking:
        # Renderizar letra por letra con espaciado extra
        widths = [draw.textlength(ch, font=font) + tracking for ch in text]
        total = sum(widths) - tracking
        x = cx - total / 2
        ascent, descent = font.getmetrics()
        for ch, w in zip(text, widths):
            draw.text((x, y), ch, font=font, fill=fill)
            x += w
        return ascent + descent
    bbox = draw.textbbox((0, 0), text, font=font)
    w = bbox[2] - bbox[0]
    draw.text((cx - w / 2, y), text, font=font, fill=fill)
    return bbox[3] - bbox[1]


def _barras_ecualizador(draw, cx, y, alturas, ancho=16, gap=12, color=ACCENT):
    """Dibuja el motivo de barras tipo ecualizador (marca El Gadget)."""
    total = len(alturas) * ancho + (len(alturas) - 1) * gap
    x = cx - total / 2
    for h in alturas:
        draw.rounded_rectangle([x, y - h, x + ancho, y], radius=ancho // 2, fill=color)
        x += ancho + gap


def generar_placa_referido(codigo: str, nombre: str = "") -> bytes:
    """Genera la placa del referidor y la devuelve como bytes PNG."""
    codigo = (codigo or "TUCODIGO").strip().upper()

    img = Image.new("RGB", (W, H), INK)
    d = ImageDraw.Draw(img)

    # Fondo: degradé vertical sutil INK -> INK_SOFT
    for i in range(H):
        t = i / H
        r = int(INK[0] + (INK_SOFT[0] - INK[0]) * t)
        g = int(INK[1] + (INK_SOFT[1] - INK[1]) * t)
        b = int(INK[2] + (INK_SOFT[2] - INK[2]) * t)
        d.line([(0, i), (W, i)], fill=(r, g, b))

    cx = W // 2

    # Marco fino de acento
    d.rounded_rectangle([40, 40, W - 40, H - 40], radius=48, outline=(45, 45, 55), width=3)

    # ── Logo (arriba) ──
    try:
        logo = Image.open(LOGO_PATH).convert("RGBA")
        logo.thumbnail((200, 200), Image.LANCZOS)
        img.paste(logo, (cx - logo.width // 2, 150), logo)
        y = 150 + logo.height + 30
    except Exception:
        y = 200

    # Wordmark
    _text_centered(d, cx, y, "EL GADGET", _font("grotesk", 46), WHITE, tracking=8)
    y += 90

    # Barras ecualizador
    _barras_ecualizador(d, cx, y + 40, [22, 40, 30, 52, 34], color=ACCENT)
    y += 110

    # ── Headline ──
    _text_centered(d, cx, y, "Comprá con mi código", _font("bold", 62), WHITE)
    y += 92
    _text_centered(d, cx, y, "y ahorrá hasta", _font("reg", 40), GRAY)
    y += 66

    # 20% OFF grande en acento
    _text_centered(d, cx, y, "20% OFF", _font("grotesk", 130), ACCENT)
    y += 200

    # ── Caja del código ──
    box_w, box_h = 760, 240
    box_x = cx - box_w // 2
    d.rounded_rectangle([box_x, y, box_x + box_w, y + box_h], radius=28, fill=ACCENT)
    _text_centered(d, cx, y + 44, "TU CÓDIGO", _font("bold", 34), (120, 95, 0), tracking=6)
    # Código: reducir tamaño si es muy largo
    size = 110
    while d.textlength(codigo, font=_font("grotesk", size)) > box_w - 80 and size > 48:
        size -= 6
    _text_centered(d, cx, y + 104, codigo, _font("grotesk", size), INK)
    y += box_h + 70

    # ── Instrucción ──
    _text_centered(d, cx, y, "Usalo al finalizar tu compra en", _font("med", 38), GRAY)
    y += 62
    _text_centered(d, cx, y, "elgadget.com.ar", _font("bold", 52), ACCENT)
    y += 110

    # ── Pie: mini pasos ──
    pie_y = H - 250
    pasos = ["Entrás al sitio", "Cargás el código", "Ahorrás al pagar"]
    seg = (W - 200) / len(pasos)
    for i, paso in enumerate(pasos):
        px = 100 + seg * i + seg / 2
        d.ellipse([px - 26, pie_y - 26, px + 26, pie_y + 26], fill=ACCENT)
        _text_centered(d, px, pie_y - 22, str(i + 1), _font("bold", 40), INK)
        # texto del paso (envuelto en 2 líneas si hace falta)
        _text_centered(d, px, pie_y + 44, paso, _font("med", 27), WHITE)

    out = io.BytesIO()
    img.save(out, format="PNG")
    return out.getvalue()


if __name__ == "__main__":
    # Prueba local: genera una placa de ejemplo
    data = generar_placa_referido("MARIA21", "María")
    salida = BASE_DIR / "placa_ejemplo.png"
    salida.write_bytes(data)
    print(f"Placa generada: {salida} ({len(data)} bytes)")
