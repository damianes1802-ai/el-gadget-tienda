#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MARKETING EL GADGET — Compositor de imágenes branded con Pillow

Genera imágenes 1080x1080 (feed) y 1080x1350 (reels/stories) con
identidad de marca El Gadget, adaptadas por buyer persona y pilar
de contenido. Usa psicología del color por persona target.

Paletas por persona (neuromarketing):
- María (mamá): tonos cálidos, cream/soft gold — confianza, calidez, hogar
- Lucas (gen Z): alto contraste, negro/dorado/neon — energía, estatus, urgencia
- Ana (profesional): tonos neutros, blanco/gris/dorado — elegancia, seriedad
- Sofi (influencer): gradientes suaves, rosa/dorado — lifestyle, aspiracional
- Martín (mayorista): azul oscuro/dorado — negocio, confianza, números
"""

import io
import os
import textwrap
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter

BASE_DIR = Path(__file__).parent.parent
FONTS_DIR = BASE_DIR / "marketing_app" / "assets" / "fonts"
LOGO_PATH = BASE_DIR / "pages" / "assets" / "img" / "logo-cuadrado.png"
OUTPUT_DIR = BASE_DIR / "marketing_app" / "data" / "generated_images"

# ── Colores de marca ──
INK = (20, 21, 26)
WHITE = (255, 255, 255)
CREAM = (247, 246, 243)
ACCENT = (255, 199, 0)
ACCENT_DEEP = (224, 172, 0)
GREEN = (46, 139, 87)
RED = (215, 71, 58)

# ── Paletas por persona ──
PALETAS = {
    "maria": {
        "bg_primary": (253, 249, 240),       # warm cream
        "bg_secondary": (255, 247, 221),      # pale gold
        "bg_dark": (42, 36, 28),              # warm dark
        "text_primary": INK,
        "text_secondary": (111, 106, 99),     # warm gray
        "accent": ACCENT,
        "accent_soft": (255, 237, 178),       # soft gold
        "badge_bg": GREEN,
        "badge_text": WHITE,
    },
    "lucas": {
        "bg_primary": INK,                    # negro
        "bg_secondary": (30, 30, 38),         # dark purple-ish
        "bg_dark": (10, 10, 14),
        "text_primary": WHITE,
        "text_secondary": (180, 180, 190),
        "accent": ACCENT,
        "accent_soft": (255, 220, 50),        # bright gold
        "badge_bg": ACCENT,
        "badge_text": INK,
    },
    "ana": {
        "bg_primary": WHITE,                  # limpio
        "bg_secondary": (245, 245, 245),      # gris muy claro
        "bg_dark": (35, 35, 40),
        "text_primary": INK,
        "text_secondary": (120, 120, 125),
        "accent": (180, 160, 120),            # dorado sobrio
        "accent_soft": (240, 235, 225),
        "badge_bg": INK,
        "badge_text": WHITE,
    },
    "sofi": {
        "bg_primary": (255, 245, 248),        # rosa muy suave
        "bg_secondary": (255, 237, 242),
        "bg_dark": (40, 25, 35),
        "text_primary": INK,
        "text_secondary": (140, 100, 120),
        "accent": (255, 150, 180),            # rosa dorado
        "accent_soft": (255, 220, 230),
        "badge_bg": (220, 120, 160),
        "badge_text": WHITE,
    },
    "martin": {
        "bg_primary": (20, 30, 50),           # azul oscuro
        "bg_secondary": (25, 40, 65),
        "bg_dark": (10, 15, 30),
        "text_primary": WHITE,
        "text_secondary": (160, 175, 200),
        "accent": ACCENT,
        "accent_soft": (60, 80, 110),
        "badge_bg": GREEN,
        "badge_text": WHITE,
    },
}


FONT_CACHE = {}

def _load_font(name, size):
    key = (name, size)
    if key in FONT_CACHE:
        return FONT_CACHE[key]
    # Priorizar fuentes descargadas, fallback a sistema
    fallbacks = {
        "headline": [FONTS_DIR / "Inter-Bold.ttf", Path("C:/Windows/Fonts/segoeuib.ttf")],
        "sub": [FONTS_DIR / "Inter-Medium.ttf", FONTS_DIR / "Inter-Bold.ttf", Path("C:/Windows/Fonts/calibrib.ttf")],
        "body": [FONTS_DIR / "Inter-Regular.ttf", Path("C:/Windows/Fonts/calibri.ttf")],
        "price": [FONTS_DIR / "Inter-Bold.ttf", Path("C:/Windows/Fonts/ariblk.ttf")],
        "badge": [FONTS_DIR / "Inter-Bold.ttf", Path("C:/Windows/Fonts/segoeuib.ttf")],
        "small": [FONTS_DIR / "Inter-Medium.ttf", Path("C:/Windows/Fonts/calibri.ttf")],
    }
    paths = fallbacks.get(name, [FONTS_DIR / name, Path(f"C:/Windows/Fonts/{name}")])
    for p in paths:
        if p.exists():
            try:
                font = ImageFont.truetype(str(p), size)
                FONT_CACHE[key] = font
                return font
            except Exception:
                continue
    return ImageFont.load_default()


def _load_logo(size=80):
    if LOGO_PATH.exists():
        logo = Image.open(LOGO_PATH).convert("RGBA")
        logo = logo.resize((size, size), Image.LANCZOS)
        return logo
    return None


def _download_product_image(url):
    import requests
    try:
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            return Image.open(io.BytesIO(resp.content)).convert("RGBA")
    except Exception:
        pass
    return None


def _round_corners(img, radius):
    mask = Image.new("L", img.size, 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle([0, 0, img.size[0], img.size[1]], radius=radius, fill=255)
    result = img.copy()
    result.putalpha(mask)
    return result


def _draw_rounded_rect(draw, xy, fill, radius=20):
    draw.rounded_rectangle(xy, radius=radius, fill=fill)


def _wrap_text(text, font, max_width, draw):
    words = text.split()
    lines = []
    current = ""
    for word in words:
        test = f"{current} {word}".strip()
        bbox = draw.textbbox((0, 0), test, font=font)
        if bbox[2] - bbox[0] <= max_width:
            current = test
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def compose_image(
    producto_nombre: str,
    producto_precio: float,
    producto_imagen_url: str,
    persona: str,
    pilar: str,
    formato: str,
    badge_text: str = "",
    hook: str = "",
    output_filename: str = None,
) -> str:
    """Genera imagen branded 1080x1080 y retorna el path del archivo."""

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    pal = PALETAS.get(persona, PALETAS["maria"])
    size = (1080, 1080)

    # ── Canvas ──
    img = Image.new("RGBA", size, pal["bg_primary"])
    draw = ImageDraw.Draw(img)

    # ── Fonts ──
    font_headline = _load_font("headline", 48)
    font_sub = _load_font("sub", 28)
    font_body = _load_font("body", 24)
    font_price = _load_font("price", 56)
    font_badge = _load_font("badge", 22)
    font_small = _load_font("small", 18)

    # ── Top bar con logo ──
    _draw_rounded_rect(draw, [0, 0, 1080, 90], fill=pal.get("bg_dark", INK), radius=0)
    logo = _load_logo(50)
    if logo:
        img.paste(logo, (24, 20), logo)
    draw.text((84, 28), "El", fill=WHITE, font=_load_font("headline", 28))
    draw.text((116, 28), " Gadget", fill=ACCENT, font=_load_font("headline", 28))
    draw.text((84, 58), "TIENDA ONLINE", fill=pal["text_secondary"], font=_load_font("small", 10))

    # ── Pilar badge (esquina superior derecha) ──
    pilar_labels = {
        "educativo": "EDUCATIVO", "motivacional": "MOTIVACIONAL",
        "engagement": "COMUNIDAD", "producto": "PRODUCTO",
    }
    pilar_label = pilar_labels.get(pilar, pilar.upper())
    pilar_bbox = draw.textbbox((0, 0), pilar_label, font=font_small)
    pilar_w = pilar_bbox[2] - pilar_bbox[0] + 24
    _draw_rounded_rect(draw, [1080 - pilar_w - 20, 100, 1080 - 20, 132], fill=pal["accent"], radius=16)
    draw.text((1080 - pilar_w - 8, 104), pilar_label, fill=INK, font=font_small)

    # ── Producto imagen (centrada, grande) ──
    prod_img = _download_product_image(producto_imagen_url) if producto_imagen_url else None
    if prod_img:
        prod_size = 480
        prod_img = prod_img.resize((prod_size, prod_size), Image.LANCZOS)
        prod_img = _round_corners(prod_img, 24)
        # Sombra sutil
        shadow = Image.new("RGBA", (prod_size + 20, prod_size + 20), (0, 0, 0, 0))
        shadow_draw = ImageDraw.Draw(shadow)
        shadow_draw.rounded_rectangle([10, 10, prod_size + 10, prod_size + 10], radius=24, fill=(0, 0, 0, 40))
        shadow = shadow.filter(ImageFilter.GaussianBlur(radius=8))
        img.paste(shadow, (1080 // 2 - prod_size // 2 - 10, 160), shadow)
        img.paste(prod_img, (1080 // 2 - prod_size // 2, 170), prod_img)

    # ── Hook / Headline ──
    y_text = 690
    if hook:
        hook_lines = _wrap_text(hook, font_headline, 960, draw)
        for line in hook_lines[:2]:
            draw.text((60, y_text), line, fill=pal["text_primary"], font=font_headline)
            y_text += 58
        y_text += 8

    # ── Nombre producto ──
    name_lines = _wrap_text(producto_nombre, font_sub, 700, draw)
    for line in name_lines[:2]:
        draw.text((60, y_text), line, fill=pal["text_secondary"], font=font_sub)
        y_text += 36

    # ── Precio ──
    y_text += 12
    precio_text = f"${producto_precio:,.0f}".replace(",", ".")
    draw.text((60, y_text), precio_text, fill=pal["accent"], font=font_price)

    # ── Badge inferior ──
    if not badge_text:
        badge_texts = {
            "educativo": "Registrate gratis en elgadget.com.ar/referidos",
            "motivacional": "Ganá 7-15% de comisión por cada venta",
            "engagement": "¿Querés ganar plata recomendando productos?",
            "producto": "Código referido = hasta 20% OFF",
        }
        badge_text = badge_texts.get(pilar, "elgadget.com.ar")

    badge_y = 1080 - 80
    _draw_rounded_rect(draw, [0, badge_y - 10, 1080, 1080], fill=pal["badge_bg"], radius=0)
    badge_bbox = draw.textbbox((0, 0), badge_text, font=font_badge)
    badge_tw = badge_bbox[2] - badge_bbox[0]
    draw.text(((1080 - badge_tw) // 2, badge_y + 12), badge_text, fill=pal["badge_text"], font=font_badge)

    # ── Guardar ──
    final = img.convert("RGB")
    if not output_filename:
        import time
        output_filename = f"{persona}_{pilar}_{int(time.time())}.jpg"
    output_path = OUTPUT_DIR / output_filename
    final.save(str(output_path), "JPEG", quality=92)
    return str(output_path)


if __name__ == "__main__":
    # Test rápido
    for persona in ["maria", "lucas", "ana", "sofi", "martin"]:
        path = compose_image(
            producto_nombre="Estantería Plegable Metal Negra 5 Niveles con Ruedas",
            producto_precio=106125,
            producto_imagen_url="https://res.cloudinary.com/deq2ofluf/image/upload/prod_DL2321_001",
            persona=persona,
            pilar="educativo",
            formato="ED-01",
            hook="¿Tu casa parece un caos?",
            output_filename=f"test_{persona}.jpg",
        )
        print(f"{persona}: {path}")
