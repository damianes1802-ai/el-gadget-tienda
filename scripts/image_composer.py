#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MARKETING EL GADGET — Compositor de imágenes branded con Pillow

4 layouts diferenciados por pilar de contenido:
- EDUCATIVO: texto-first, bullets, guía visual
- MOTIVACIONAL: número grande, storytelling, aspiracional
- ENGAGEMENT: pregunta grande, opciones, interactivo
- PRODUCTO: foto producto centrada, precio, hook

Paletas por buyer persona (neuromarketing/psicología del color).
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

# ── Paletas por persona ──
PALETAS = {
    "maria": {
        "bg": (253, 249, 240), "bg_alt": (255, 247, 221), "bar": (42, 36, 28),
        "text": INK, "text2": (111, 106, 99), "accent": ACCENT,
        "badge_bg": GREEN, "badge_text": WHITE,
        "bullet_bg": (255, 243, 200), "bullet_icon": ACCENT_DEEP,
    },
    "lucas": {
        "bg": INK, "bg_alt": (30, 30, 38), "bar": (5, 5, 8),
        "text": WHITE, "text2": (180, 180, 190), "accent": ACCENT,
        "badge_bg": ACCENT, "badge_text": INK,
        "bullet_bg": (35, 35, 45), "bullet_icon": ACCENT,
    },
    "ana": {
        "bg": WHITE, "bg_alt": (245, 245, 245), "bar": (35, 35, 40),
        "text": INK, "text2": (120, 120, 125), "accent": (180, 160, 120),
        "badge_bg": INK, "badge_text": WHITE,
        "bullet_bg": (240, 238, 233), "bullet_icon": (180, 160, 120),
    },
    "sofi": {
        "bg": (255, 245, 248), "bg_alt": (255, 237, 242), "bar": (40, 25, 35),
        "text": INK, "text2": (140, 100, 120), "accent": (255, 150, 180),
        "badge_bg": (220, 120, 160), "badge_text": WHITE,
        "bullet_bg": (255, 230, 238), "bullet_icon": (220, 120, 160),
    },
    "martin": {
        "bg": (20, 30, 50), "bg_alt": (25, 40, 65), "bar": (10, 15, 30),
        "text": WHITE, "text2": (160, 175, 200), "accent": ACCENT,
        "badge_bg": GREEN, "badge_text": WHITE,
        "bullet_bg": (30, 45, 75), "bullet_icon": ACCENT,
    },
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


def _logo(size=50):
    if LOGO_PATH.exists():
        img = Image.open(LOGO_PATH).convert("RGBA")
        return img.resize((size, size), Image.LANCZOS)
    return None


def _download_img(url):
    import requests
    try:
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            return Image.open(io.BytesIO(resp.content)).convert("RGBA")
    except Exception:
        pass
    return None


def _round_rect(draw, xy, fill, radius=20):
    draw.rounded_rectangle(xy, radius=radius, fill=fill)


def _wrap(text, font, max_w, draw):
    words = text.split()
    lines, cur = [], ""
    for w in words:
        test = f"{cur} {w}".strip()
        if draw.textbbox((0, 0), test, font=font)[2] <= max_w:
            cur = test
        else:
            if cur: lines.append(cur)
            cur = w
    if cur: lines.append(cur)
    return lines


def _draw_top_bar(img, draw, pal):
    _round_rect(draw, [0, 0, 1080, 88], fill=pal["bar"], radius=0)
    logo = _logo(48)
    if logo:
        img.paste(logo, (24, 20), logo)
    draw.text((82, 24), "El", fill=WHITE, font=_font("h", 26))
    draw.text((112, 24), " Gadget", fill=ACCENT, font=_font("h", 26))
    draw.text((82, 54), "TIENDA ONLINE", fill=pal["text2"], font=_font("m", 11))


def _draw_bottom_bar(draw, text, pal):
    _round_rect(draw, [0, 998, 1080, 1080], fill=pal["badge_bg"], radius=0)
    tw = draw.textbbox((0, 0), text, font=_font("h", 22))[2]
    draw.text(((1080 - tw) // 2, 1022), text, fill=pal["badge_text"], font=_font("h", 22))


def _draw_pilar_badge(draw, label, pal):
    f = _font("m", 16)
    tw = draw.textbbox((0, 0), label, font=f)[2] + 24
    _round_rect(draw, [1080 - tw - 24, 100, 1080 - 24, 130], fill=pal["accent"], radius=14)
    draw.text((1080 - tw - 12, 104), label, fill=INK, font=f)


# ============================================================================
# LAYOUT 1: EDUCATIVO — texto-first, bullets
# ============================================================================

def _layout_educativo(img, draw, pal, data):
    _draw_top_bar(img, draw, pal)
    _draw_pilar_badge(draw, "EDUCATIVO", pal)

    # Emoji decorativo
    emoji = data.get("emoji", "📋")
    draw.text((60, 130), emoji, font=_font("b", 52), fill=pal["text"])

    # Título grande
    titulo = data.get("titulo", data.get("hook", ""))
    y = 200
    for line in _wrap(titulo, _font("h", 52), 960, draw)[:3]:
        draw.text((60, y), line, fill=pal["text"], font=_font("h", 52))
        y += 64

    # Bullets/puntos
    puntos = data.get("puntos", [])
    y += 30
    for i, punto in enumerate(puntos[:5]):
        box_y = y
        _round_rect(draw, [50, box_y, 1030, box_y + 72], fill=pal["bullet_bg"], radius=14)
        # Número circular
        cx, cy = 90, box_y + 36
        draw.ellipse([cx - 18, cy - 18, cx + 18, cy + 18], fill=pal["bullet_icon"])
        num = str(i + 1)
        nw = draw.textbbox((0, 0), num, font=_font("h", 20))[2]
        draw.text((cx - nw // 2, cy - 12), num, fill=WHITE if pal["bullet_icon"] != ACCENT else INK, font=_font("h", 20))
        # Texto del punto
        draw.text((124, box_y + 20), punto[:55], fill=pal["text"], font=_font("m", 24))
        y += 86

    _draw_bottom_bar(draw, data.get("cta_bar", "Registrate gratis en elgadget.com.ar/referidos"), pal)


# ============================================================================
# LAYOUT 2: MOTIVACIONAL — número grande, aspiracional
# ============================================================================

def _layout_motivacional(img, draw, pal, data):
    _draw_top_bar(img, draw, pal)
    _draw_pilar_badge(draw, "MOTIVACIONAL", pal)

    # Número ENORME centrado
    numero = data.get("numero_grande", "$45.600")
    nf = _font("h", 96)
    nw = draw.textbbox((0, 0), numero, font=nf)[2]
    draw.text(((1080 - nw) // 2, 200), numero, fill=pal["accent"], font=nf)

    # Subtexto debajo del número
    subtexto = data.get("subtexto", "ganaron nuestros referidos este mes")
    sf = _font("m", 28)
    sw = draw.textbbox((0, 0), subtexto, font=sf)[2]
    draw.text(((1080 - sw) // 2, 320), subtexto, fill=pal["text2"], font=sf)

    # Línea separadora
    draw.line([(200, 400), (880, 400)], fill=pal["accent"], width=3)

    # Bullets de valor
    bullets = data.get("bullets", ["Sin inversión", "Sin stock", "Sin riesgo"])
    y = 440
    for b in bullets[:4]:
        bf = _font("h", 32)
        draw.text((100, y), "→", fill=pal["accent"], font=bf)
        draw.text((150, y), b, fill=pal["text"], font=bf)
        y += 56

    # Hook/storytelling inferior
    hook = data.get("hook", "")
    if hook:
        y += 30
        for line in _wrap(hook, _font("b", 24), 900, draw)[:3]:
            draw.text((80, y), line, fill=pal["text2"], font=_font("b", 24))
            y += 34

    _draw_bottom_bar(draw, data.get("cta_bar", "Sumate al programa de referidos"), pal)


# ============================================================================
# LAYOUT 3: ENGAGEMENT — pregunta grande, opciones
# ============================================================================

def _layout_engagement(img, draw, pal, data):
    _draw_top_bar(img, draw, pal)
    _draw_pilar_badge(draw, "COMUNIDAD", pal)

    # Pregunta GRANDE
    pregunta = data.get("pregunta", data.get("hook", "¿Qué opinás?"))
    y = 160
    for line in _wrap(pregunta, _font("h", 56), 960, draw)[:4]:
        draw.text((60, y), line, fill=pal["text"], font=_font("h", 56))
        y += 70

    # Opciones como cards
    opciones = data.get("opciones", [])
    y += 40
    for i, opc in enumerate(opciones[:4]):
        box_y = y
        _round_rect(draw, [50, box_y, 1030, box_y + 90], fill=pal["bullet_bg"], radius=16)
        # Letra circular
        cx, cy = 104, box_y + 45
        draw.ellipse([cx - 24, cy - 24, cx + 24, cy + 24], fill=pal["accent"])
        letter = chr(65 + i)  # A, B, C, D
        lw = draw.textbbox((0, 0), letter, font=_font("h", 24))[2]
        draw.text((cx - lw // 2, cy - 14), letter, fill=INK, font=_font("h", 24))
        # Texto opción
        draw.text((150, box_y + 26), opc[:50], fill=pal["text"], font=_font("m", 28))
        y += 110

    _draw_bottom_bar(draw, data.get("cta_bar", "Contanos en los comentarios"), pal)


# ============================================================================
# LAYOUT 4: PRODUCTO — foto centrada, precio, hook
# ============================================================================

def _layout_producto(img, draw, pal, data):
    _draw_top_bar(img, draw, pal)
    _draw_pilar_badge(draw, "PRODUCTO", pal)

    # Producto imagen centrada
    prod_url = data.get("producto_imagen", "")
    prod_img = _download_img(prod_url) if prod_url else None
    if prod_img:
        ps = 480
        prod_img = prod_img.resize((ps, ps), Image.LANCZOS)
        # Sombra
        shadow = Image.new("RGBA", (ps + 20, ps + 20), (0, 0, 0, 0))
        sd = ImageDraw.Draw(shadow)
        sd.rounded_rectangle([10, 10, ps + 10, ps + 10], radius=24, fill=(0, 0, 0, 40))
        shadow = shadow.filter(ImageFilter.GaussianBlur(8))
        img.paste(shadow, (1080 // 2 - ps // 2 - 10, 115), shadow)
        # Bordes redondeados
        mask = Image.new("L", prod_img.size, 0)
        ImageDraw.Draw(mask).rounded_rectangle([0, 0, ps, ps], radius=24, fill=255)
        prod_img.putalpha(mask)
        img.paste(prod_img, (1080 // 2 - ps // 2, 125), prod_img)

    # Hook
    hook = data.get("hook", "")
    y = 650
    for line in _wrap(hook, _font("h", 48), 960, draw)[:2]:
        draw.text((60, y), line, fill=pal["text"], font=_font("h", 48))
        y += 58

    # Nombre producto
    nombre = data.get("producto_nombre", "")
    y += 8
    for line in _wrap(nombre, _font("m", 26), 700, draw)[:2]:
        draw.text((60, y), line, fill=pal["text2"], font=_font("m", 26))
        y += 34

    # Precio
    precio = data.get("producto_precio", 0)
    y += 12
    draw.text((60, y), f"${precio:,.0f}".replace(",", "."), fill=pal["accent"], font=_font("h", 56))

    _draw_bottom_bar(draw, data.get("cta_bar", "Código referido = hasta 20% OFF"), pal)


# ============================================================================
# FUNCIÓN PRINCIPAL
# ============================================================================

LAYOUT_FN = {
    "educativo": _layout_educativo,
    "motivacional": _layout_motivacional,
    "engagement": _layout_engagement,
    "producto": _layout_producto,
}

def compose_image(
    producto_nombre="",
    producto_precio=0,
    producto_imagen_url="",
    persona="maria",
    pilar="producto",
    formato="PR-01",
    hook="",
    output_filename=None,
    # Datos estructurados por pilar (opcionales)
    titulo="",
    puntos=None,
    numero_grande="",
    subtexto="",
    bullets=None,
    pregunta="",
    opciones=None,
    cta_bar="",
    emoji="",
) -> str:
    """Genera imagen branded 1080x1080 con layout específico por pilar."""

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    pal = PALETAS.get(persona, PALETAS["maria"])

    img = Image.new("RGBA", (1080, 1080), pal["bg"])
    draw = ImageDraw.Draw(img)

    data = {
        "hook": hook, "titulo": titulo or hook,
        "puntos": puntos or [], "numero_grande": numero_grande,
        "subtexto": subtexto, "bullets": bullets or [],
        "pregunta": pregunta or hook, "opciones": opciones or [],
        "producto_nombre": producto_nombre, "producto_precio": producto_precio,
        "producto_imagen": producto_imagen_url, "cta_bar": cta_bar, "emoji": emoji,
    }

    layout_fn = LAYOUT_FN.get(pilar, _layout_producto)
    layout_fn(img, draw, pal, data)

    final = img.convert("RGB")
    if not output_filename:
        import time
        output_filename = f"{persona}_{pilar}_{int(time.time())}.jpg"
    path = OUTPUT_DIR / output_filename
    final.save(str(path), "JPEG", quality=92)
    return str(path)


if __name__ == "__main__":
    # Test: un layout por pilar
    compose_image(
        persona="maria", pilar="educativo", formato="ED-02",
        titulo="5 formas de compartir tu código",
        emoji="📋",
        puntos=["Mandalo por WhatsApp", "Subilo a tus Stories", "Compartilo en grupos de mamás",
                "Enviá el link directo", "Publicalo en Facebook"],
        output_filename="test_educativo.jpg",
    )
    compose_image(
        persona="lucas", pilar="motivacional", formato="MO-01",
        numero_grande="$45.600",
        subtexto="ganaron nuestros referidos este mes",
        bullets=["Sin inversión", "Sin stock", "Sin envíos", "Cobrás el día 5"],
        hook="Empezá a ganar hoy mismo compartiendo productos de El Gadget",
        output_filename="test_motivacional.jpg",
    )
    compose_image(
        persona="maria", pilar="engagement", formato="EN-01",
        pregunta="¿Qué harías con $30.000 extra por mes?",
        opciones=["💰 Pagar deudas", "🏖️ Vacaciones", "🛍️ Compras", "📱 Tecnología"],
        output_filename="test_engagement.jpg",
    )
    compose_image(
        persona="lucas", pilar="producto", formato="PR-01",
        producto_nombre="Estantería Plegable Metal Negra 5 Niveles",
        producto_precio=106125,
        producto_imagen_url="https://res.cloudinary.com/deq2ofluf/image/upload/prod_DL2321_001",
        hook="¿Tu casa parece un caos?",
        output_filename="test_producto.jpg",
    )
    print("4 layouts generados en marketing_app/data/generated_images/")
