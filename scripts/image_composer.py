#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MARKETING EL GADGET — Compositor de imágenes branded para Instagram

Formatos Instagram 2026:
- Feed post/carrusel: 1080x1350 (4:5, máximo espacio en feed)
- Story/Reel cover: 1080x1920 (9:16)

4 layouts por pilar × 5 paletas por persona = contenido diferenciado.
"""

import io
import os
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter

BASE_DIR = Path(__file__).parent.parent
FONTS_DIR = BASE_DIR / "marketing_app" / "assets" / "fonts"
LOGO_PATH = BASE_DIR / "pages" / "assets" / "img" / "logo-cuadrado.png"
OUTPUT_DIR = BASE_DIR / "marketing_app" / "data" / "generated_images"

W = 1080
H_FEED = 1350    # 4:5 feed post / carrusel
H_STORY = 1920   # 9:16 story / reel

INK = (20, 21, 26)
WHITE = (255, 255, 255)
ACCENT = (255, 199, 0)
ACCENT_DEEP = (224, 172, 0)
GREEN = (46, 139, 87)

PALETAS = {
    "maria": {
        "bg": (253, 249, 240), "bar": (42, 36, 28),
        "text": INK, "text2": (111, 106, 99), "accent": ACCENT,
        "badge_bg": GREEN, "badge_text": WHITE,
        "bullet_bg": (255, 243, 200), "bullet_icon": ACCENT_DEEP,
    },
    "lucas": {
        "bg": INK, "bar": (5, 5, 8),
        "text": WHITE, "text2": (180, 180, 190), "accent": ACCENT,
        "badge_bg": ACCENT, "badge_text": INK,
        "bullet_bg": (35, 35, 45), "bullet_icon": ACCENT,
    },
    "ana": {
        "bg": WHITE, "bar": (35, 35, 40),
        "text": INK, "text2": (120, 120, 125), "accent": (180, 160, 120),
        "badge_bg": INK, "badge_text": WHITE,
        "bullet_bg": (240, 238, 233), "bullet_icon": (180, 160, 120),
    },
    "sofi": {
        "bg": (255, 245, 248), "bar": (40, 25, 35),
        "text": INK, "text2": (140, 100, 120), "accent": (255, 150, 180),
        "badge_bg": (220, 120, 160), "badge_text": WHITE,
        "bullet_bg": (255, 230, 238), "bullet_icon": (220, 120, 160),
    },
    "martin": {
        "bg": (20, 30, 50), "bar": (10, 15, 30),
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


def _logo(size=48):
    if LOGO_PATH.exists():
        return Image.open(LOGO_PATH).convert("RGBA").resize((size, size), Image.LANCZOS)
    return None


def _download_img(url):
    import requests
    try:
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            return Image.open(io.BytesIO(r.content)).convert("RGBA")
    except Exception:
        pass
    return None


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


def _text_with_emoji(draw, pos, text, font, fill, img=None):
    """Render text, replacing emoji with text fallback."""
    clean = ''.join(c if ord(c) < 0x10000 else '' for c in text).strip()
    draw.text(pos, clean, fill=fill, font=font)


def _top_bar(img, draw, pal, h):
    draw.rounded_rectangle([0, 0, W, 88], radius=0, fill=pal["bar"])
    logo = _logo(48)
    if logo:
        img.paste(logo, (24, 20), logo)
    draw.text((82, 24), "El", fill=WHITE, font=_font("h", 26))
    draw.text((112, 24), " Gadget", fill=ACCENT, font=_font("h", 26))
    draw.text((82, 54), "TIENDA ONLINE", fill=(140, 140, 140), font=_font("m", 11))


def _bottom_bar(draw, text, pal, h):
    bar_h = 72
    y = h - bar_h
    draw.rounded_rectangle([0, y, W, h], radius=0, fill=pal["badge_bg"])
    f = _font("h", 21)
    tw = draw.textbbox((0, 0), text, font=f)[2]
    draw.text(((W - tw) // 2, y + 22), text, fill=pal["badge_text"], font=f)


def _pilar_badge(draw, label, pal):
    f = _font("m", 15)
    tw = draw.textbbox((0, 0), label, font=f)[2] + 22
    draw.rounded_rectangle([W - tw - 24, 100, W - 24, 128], radius=12, fill=pal["accent"])
    draw.text((W - tw - 13, 103), label, fill=INK, font=f)


# ============================================================================
# LAYOUT 1: EDUCATIVO
# ============================================================================
def _layout_educativo(img, draw, pal, data, h):
    _top_bar(img, draw, pal, h)
    _pilar_badge(draw, "EDUCATIVO", pal)

    puntos = data.get("puntos", [])
    n = min(len(puntos), 6)
    ts = 56 if n <= 4 else 46
    ch = 110 if n <= 4 else 84
    pfs = 28 if n <= 4 else 23
    gap = 22 if n <= 4 else 16

    titulo = data.get("titulo", data.get("hook", ""))
    t_lines = _wrap(titulo, _font("h", ts), 960, draw)[:3]
    total_h = len(t_lines) * (ts + 14) + 30 + n * (ch + gap) + 40 + 30 + 3 * 36 + 20 + 30 + 30
    zone_top, zone_bot = 88, h - 72
    y = zone_top + max(10, (zone_bot - zone_top - total_h) // 2)

    for line in t_lines:
        draw.text((60, y), line, fill=pal["text"], font=_font("h", ts))
        y += ts + 14
    y += 30

    for i, punto in enumerate(puntos[:6]):
        draw.rounded_rectangle([50, y, W - 50, y + ch], radius=16, fill=pal["bullet_bg"])
        cx, cy = 96, y + ch // 2
        r = 22 if n <= 4 else 18
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=pal["bullet_icon"])
        num = str(i + 1)
        nf = _font("h", 21 if n <= 4 else 17)
        nw = draw.textbbox((0, 0), num, font=nf)[2]
        draw.text((cx - nw // 2, cy - 12), num, fill=WHITE if pal["bullet_icon"] != ACCENT else INK, font=nf)
        pt = ''.join(c if ord(c) < 0x10000 else '' for c in punto)
        draw.text((134, y + (ch - pfs) // 2 - 2), pt[:65], fill=pal["text"], font=_font("m", pfs))
        y += ch + gap

    # Bloque inferior: beneficios resumidos
    y += 40
    draw.line([(100, y), (W - 100, y)], fill=(*pal["accent"], 80), width=2)
    y += 30
    beneficios = ["Comisiones del 7% al 15%", "Sin inversion inicial", "Cobras el dia 5 de cada mes"]
    for b in beneficios:
        bf = _font("m", 22)
        draw.text((100, y), "→", fill=pal["accent"], font=bf)
        draw.text((135, y), b, fill=pal["text2"], font=bf)
        y += 36

    y += 20
    url = "elgadget.com.ar/referidos"
    uf = _font("h", 30)
    uw = draw.textbbox((0, 0), url, font=uf)[2]
    draw.text(((W - uw) // 2, y), url, fill=pal["accent"], font=uf)

    _bottom_bar(draw, data.get("cta_bar", "Registrate gratis — sin inversion"), pal, h)


# ============================================================================
# LAYOUT 2: MOTIVACIONAL
# ============================================================================
def _layout_motivacional(img, draw, pal, data, h):
    _top_bar(img, draw, pal, h)
    _pilar_badge(draw, "MOTIVACIONAL", pal)

    bullets = data.get("bullets", [])
    hook = data.get("hook", "")
    hook_h = (30 + len(_wrap(hook, _font("b", 22), 880, draw)) * 32) if hook else 0
    content_h = 92 + 30 + 26 + 30 + 3 + len(bullets) * 50 + hook_h + 40 + 30 + 100 + 30 + 30
    usable = h - 88 - 72
    mid_y = 88 + max(20, (usable - content_h) // 2)

    numero = data.get("numero_grande", "$45.600")
    nf = _font("h", 92)
    nw = draw.textbbox((0, 0), numero, font=nf)[2]
    draw.text(((W - nw) // 2, mid_y - 60), numero, fill=pal["accent"], font=nf)

    subtexto = data.get("subtexto", "")
    if subtexto:
        sf = _font("m", 26)
        sw = draw.textbbox((0, 0), subtexto, font=sf)[2]
        draw.text(((W - sw) // 2, mid_y + 50), subtexto, fill=pal["text2"], font=sf)

    draw.line([(180, mid_y + 110), (W - 180, mid_y + 110)], fill=pal["accent"], width=3)

    y = mid_y + 150
    for b in bullets[:5]:
        b_clean = ''.join(c if ord(c) < 0x10000 else '' for c in b)
        draw.text((100, y), "→", fill=pal["accent"], font=_font("h", 30))
        draw.text((145, y), b_clean, fill=pal["text"], font=_font("h", 30))
        y += 50

    if hook:
        y += 30
        for line in _wrap(hook, _font("b", 22), 880, draw)[:3]:
            draw.text((80, y), line, fill=pal["text2"], font=_font("b", 22))
            y += 32

    # Bloque inferior: 3 pasos
    y += 40
    draw.line([(180, y), (W - 180, y)], fill=pal["accent"], width=2)
    y += 30
    pasos = [("1", "Registrate gratis"), ("2", "Comparti tu codigo"), ("3", "Cobra comisiones")]
    paso_w = (W - 120) // 3
    for i, (num, txt) in enumerate(pasos):
        cx = 60 + i * paso_w + paso_w // 2
        draw.ellipse([cx - 22, y - 2, cx + 22, y + 42], fill=pal["accent"])
        nw = draw.textbbox((0, 0), num, font=_font("h", 22))[2]
        draw.text((cx - nw // 2, y + 6), num, fill=INK, font=_font("h", 22))
        tw = draw.textbbox((0, 0), txt, font=_font("m", 18))[2]
        draw.text((cx - tw // 2, y + 52), txt, fill=pal["text2"], font=_font("m", 18))

    y += 100
    url = "elgadget.com.ar/referidos"
    uf = _font("h", 30)
    uw = draw.textbbox((0, 0), url, font=uf)[2]
    draw.text(((W - uw) // 2, y), url, fill=pal["accent"], font=uf)

    _bottom_bar(draw, data.get("cta_bar", "Sumate al programa de referidos"), pal, h)


# ============================================================================
# LAYOUT 3: ENGAGEMENT
# ============================================================================
def _layout_engagement(img, draw, pal, data, h):
    _top_bar(img, draw, pal, h)
    _pilar_badge(draw, "COMUNIDAD", pal)

    pregunta = data.get("pregunta", data.get("hook", ""))
    opciones = data.get("opciones", [])
    n_opc = min(len(opciones), 4)
    card_h = 100
    gap = 22

    p_lines = _wrap(pregunta, _font("h", 54), 960, draw)[:4]
    total_h = len(p_lines) * 68 + 40 + n_opc * (card_h + gap) + 30 + 25 + 40 + 35 + 28 + 30
    zone_top, zone_bot = 88, h - 72
    y = zone_top + max(10, (zone_bot - zone_top - total_h) // 2)

    for line in p_lines:
        draw.text((60, y), line, fill=pal["text"], font=_font("h", 54))
        y += 68
    y += 40
    for i, opc in enumerate(opciones[:4]):
        by = y
        draw.rounded_rectangle([50, by, W - 50, by + card_h], radius=18, fill=pal["bullet_bg"])
        cx, cy = 110, by + card_h // 2
        draw.ellipse([cx - 28, cy - 28, cx + 28, cy + 28], fill=pal["accent"])
        letter = chr(65 + i)
        lw = draw.textbbox((0, 0), letter, font=_font("h", 26))[2]
        draw.text((cx - lw // 2, cy - 15), letter, fill=INK, font=_font("h", 26))
        opc_clean = ''.join(c if ord(c) < 0x10000 else '' for c in opc)
        opc_text = opc_clean.lstrip('💰🏖️🛍️📱🎉❤️✈️🏠 ')
        draw.text((160, by + 30), opc_text[:50], fill=pal["text"], font=_font("m", 30))
        y += card_h + gap

    # Bloque inferior con contexto del programa
    y += 30
    draw.line([(100, y), (W - 100, y)], fill=(*pal["accent"], 80), width=2)
    y += 25
    ctx_text = "Gana plata recomendando productos de El Gadget"
    ctf = _font("h", 24)
    ctw = draw.textbbox((0, 0), ctx_text, font=ctf)[2]
    draw.text(((W - ctw) // 2, y), ctx_text, fill=pal["text"], font=ctf)
    y += 40
    sub_items = ["Comisiones del 7% al 15%", "Sin inversion", "Cobro mensual"]
    sub_text = "  ·  ".join(sub_items)
    stf = _font("m", 19)
    stw = draw.textbbox((0, 0), sub_text, font=stf)[2]
    draw.text(((W - stw) // 2, y), sub_text, fill=pal["text2"], font=stf)
    y += 35
    url = "elgadget.com.ar/referidos"
    uf = _font("h", 28)
    uw = draw.textbbox((0, 0), url, font=uf)[2]
    draw.text(((W - uw) // 2, y), url, fill=pal["accent"], font=uf)

    _bottom_bar(draw, data.get("cta_bar", "Tu opinion nos importa"), pal, h)


# ============================================================================
# LAYOUT 4: PRODUCTO
# ============================================================================
def _layout_producto(img, draw, pal, data, h):
    _top_bar(img, draw, pal, h)
    _pilar_badge(draw, "PRODUCTO", pal)

    prod_url = data.get("producto_imagen", "")
    prod_img = _download_img(prod_url) if prod_url else None
    if prod_img:
        ps = 560
        prod_img = prod_img.resize((ps, ps), Image.LANCZOS)
        mask = Image.new("L", prod_img.size, 0)
        ImageDraw.Draw(mask).rounded_rectangle([0, 0, ps, ps], radius=28, fill=255)
        prod_img.putalpha(mask)
        shadow = Image.new("RGBA", (ps + 24, ps + 24), (0, 0, 0, 0))
        ImageDraw.Draw(shadow).rounded_rectangle([12, 12, ps + 12, ps + 12], radius=28, fill=(0, 0, 0, 35))
        shadow = shadow.filter(ImageFilter.GaussianBlur(12))
        img.paste(shadow, (W // 2 - ps // 2 - 12, 108), shadow)
        img.paste(prod_img, (W // 2 - ps // 2, 120), prod_img)

    # Hook grande
    hook = data.get("hook", "")
    y = 720
    for line in _wrap(hook, _font("h", 44), 960, draw)[:2]:
        draw.text((60, y), line, fill=pal["text"], font=_font("h", 44))
        y += 56

    # Nombre producto
    nombre = data.get("producto_nombre", "")
    y += 6
    for line in _wrap(nombre, _font("m", 24), 750, draw)[:2]:
        draw.text((60, y), line, fill=pal["text2"], font=_font("m", 24))
        y += 32

    # Precios: público tachado + con descuento
    precio = data.get("producto_precio", 0)
    precio_desc = round(precio * 0.80)  # 20% OFF máximo
    y += 18

    # Precio público tachado
    precio_pub = f"${precio:,.0f}".replace(",", ".")
    ppf = _font("m", 32)
    ppw = draw.textbbox((0, 0), precio_pub, font=ppf)[2]
    draw.text((60, y), precio_pub, fill=pal["text2"], font=ppf)
    # Línea de tachado
    pp_mid = y + 18
    draw.line([(58, pp_mid), (62 + ppw, pp_mid)], fill=pal["text2"], width=3)

    # Precio con descuento
    precio_off = f"${precio_desc:,.0f}".replace(",", ".")
    draw.text((80 + ppw, y - 10), precio_off, fill=pal["accent"], font=_font("h", 48))

    # Badge de descuento
    y += 60
    badge_text = "Hasta 20% OFF con codigo referido"
    btf = _font("h", 20)
    btw = draw.textbbox((0, 0), badge_text, font=btf)[2] + 28
    draw.rounded_rectangle([56, y, 56 + btw, y + 40], radius=20, fill=pal["accent"])
    draw.text((70, y + 8), badge_text, fill=INK, font=btf)

    # Info de confianza
    y += 56
    trust_items = [
        ("Envio a todo el pais", "Pagos con MercadoPago"),
        ("10 dias de devolucion", "6 meses de garantia"),
    ]
    for row in trust_items:
        text_row = "  ·  ".join(row)
        draw.text((60, y), text_row, fill=pal["text2"], font=_font("b", 19))
        y += 30

    # URL
    y += 20
    url = "elgadget.com.ar"
    uf = _font("h", 28)
    uw = draw.textbbox((0, 0), url, font=uf)[2]
    draw.text(((W - uw) // 2, y), url, fill=pal["accent"], font=uf)

    _bottom_bar(draw, data.get("cta_bar", "Link en bio · elgadget.com.ar"), pal, h)


# ============================================================================
# MAIN
# ============================================================================
LAYOUTS = {
    "educativo": _layout_educativo,
    "motivacional": _layout_motivacional,
    "engagement": _layout_engagement,
    "producto": _layout_producto,
}

def compose_image(
    producto_nombre="", producto_precio=0, producto_imagen_url="",
    persona="maria", pilar="producto", formato="PR-01", hook="",
    output_filename=None,
    titulo="", puntos=None, numero_grande="", subtexto="",
    bullets=None, pregunta="", opciones=None, cta_bar="", emoji="",
    size_format="feed",
) -> str:
    """Genera imagen branded para Instagram.
    size_format: 'feed' (1080x1350) o 'story' (1080x1920)
    """
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    pal = PALETAS.get(persona, PALETAS["maria"])
    h = H_STORY if size_format == "story" else H_FEED

    img = Image.new("RGBA", (W, h), pal["bg"])
    draw = ImageDraw.Draw(img)

    data = {
        "hook": hook, "titulo": titulo or hook,
        "puntos": puntos or [], "numero_grande": numero_grande,
        "subtexto": subtexto, "bullets": bullets or [],
        "pregunta": pregunta or hook, "opciones": opciones or [],
        "producto_nombre": producto_nombre, "producto_precio": producto_precio,
        "producto_imagen": producto_imagen_url, "cta_bar": cta_bar, "emoji": emoji,
    }

    layout_fn = LAYOUTS.get(pilar, _layout_producto)
    layout_fn(img, draw, pal, data, h)

    final = img.convert("RGB")
    if not output_filename:
        import time
        output_filename = f"{persona}_{pilar}_{int(time.time())}.jpg"
    path = OUTPUT_DIR / output_filename
    final.save(str(path), "JPEG", quality=92)
    return str(path)


if __name__ == "__main__":
    compose_image(
        persona="maria", pilar="educativo",
        titulo="5 formas de compartir tu codigo y ganar",
        puntos=["Mandalo por WhatsApp a tus contactos", "Subilo a tus Instagram Stories",
                "Compartilo en grupos de mamas", "Envia el link directo por mensaje",
                "Publicalo en Facebook o TikTok"],
        cta_bar="Registrate gratis en elgadget.com.ar/referidos",
        output_filename="test_educativo.jpg",
    )
    compose_image(
        persona="lucas", pilar="motivacional",
        numero_grande="$45.600", subtexto="ganaron nuestros referidos este mes",
        bullets=["Sin inversion inicial", "Sin manejar stock ni envios",
                 "Cobras el dia 5 de cada mes", "Comisiones de 7% a 15%"],
        hook="Empeza a ganar hoy compartiendo productos de El Gadget",
        cta_bar="Sumate gratis al programa de referidos",
        output_filename="test_motivacional.jpg",
    )
    compose_image(
        persona="maria", pilar="engagement",
        pregunta="Que harias con $30.000 extra por mes?",
        opciones=["Pagar deudas", "Vacaciones", "Compras para la casa", "Tecnologia nueva"],
        cta_bar="Contanos en los comentarios",
        output_filename="test_engagement.jpg",
    )
    compose_image(
        persona="lucas", pilar="producto",
        producto_nombre="Estanteria Plegable Metal Negra 5 Niveles",
        producto_precio=106125,
        producto_imagen_url="https://res.cloudinary.com/deq2ofluf/image/upload/prod_DL2321_001",
        hook="Tu casa parece un caos?",
        cta_bar="Codigo referido = hasta 20% OFF",
        output_filename="test_producto.jpg",
    )
    print("4 imagenes generadas (1080x1350 feed format)")
