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
        logo = Image.open(LOGO_PATH).convert("RGBA").resize((size, size), Image.LANCZOS)
        mask = Image.new("L", (size, size), 0)
        ImageDraw.Draw(mask).rounded_rectangle([0, 0, size, size], radius=12, fill=255)
        logo.putalpha(mask)
        return logo
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


def _remove_bg(img):
    """Remueve el fondo de una imagen de producto usando rembg."""
    try:
        from rembg import remove
        img_bytes = io.BytesIO()
        img.save(img_bytes, format="PNG")
        result_bytes = remove(img_bytes.getvalue())
        return Image.open(io.BytesIO(result_bytes)).convert("RGBA")
    except Exception:
        return img


def _wrap(text, font, max_w, draw):
    # Primero dividir por signos de interrogación/exclamación (punto de corte natural)
    parts = []
    current = ""
    for ch in text:
        current += ch
        if ch in ('?', '!') and len(current.strip()) > 0:
            parts.append(current.strip())
            current = ""
    if current.strip():
        parts.append(current.strip())

    lines = []
    for part in parts:
        words = part.split()
        cur = ""
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
    draw.line([(0, 88), (W, 88)], fill=ACCENT, width=3)
    logo = _logo(48)
    if logo:
        img.paste(logo, (24, 20), logo)
    draw.text((82, 22), "El", fill=WHITE, font=_font("h", 28))
    draw.text((114, 22), " Gadget", fill=ACCENT, font=_font("h", 28))
    draw.text((82, 54), "TIENDA ONLINE", fill=(160, 160, 160), font=_font("m", 12))
    ig = "@elgadget.ok"
    igf = _font("m", 16)
    igw = draw.textbbox((0, 0), ig, font=igf)[2]
    draw.text((W - igw - 24, 36), ig, fill=(140, 140, 140), font=igf)


def _bottom_bar(draw, text, pal, h):
    bar_h = 72
    y = h - bar_h
    draw.rounded_rectangle([0, y, W, h], radius=0, fill=pal["badge_bg"])
    draw.line([(0, y), (W, y)], fill=pal["accent"], width=3)
    f = _font("h", 21)
    tw = draw.textbbox((0, 0), text, font=f)[2]
    draw.text(((W - tw) // 2, y + 24), text, fill=pal["badge_text"], font=f)


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
    # Badge de pilar removido por diseño

    puntos = data.get("puntos", [])
    n = min(len(puntos), 6)
    ts = 56 if n <= 4 else 46
    ch = 110 if n <= 4 else 84
    pfs = 28 if n <= 4 else 23
    gap = 22 if n <= 4 else 16

    titulo = data.get("hook") or data.get("titulo", "")
    t_lines = _wrap(titulo, _font("h", ts), 960, draw)[:3]
    total_h = len(t_lines) * (ts + 14) + 30 + n * (ch + gap) + 40 + 30 + 3 * 36 + 20 + 30 + 30
    zone_top, zone_bot = 88, h - 72
    y = zone_top + max(10, (zone_bot - zone_top - total_h) // 2)

    for line in t_lines:
        tw = draw.textbbox((0, 0), line, font=_font("h", ts))[2]
        draw.text(((W - tw) // 2, y), line, fill=pal["text"], font=_font("h", ts))
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

    y += 40
    draw.line([(150, y), (W - 150, y)], fill=(*pal["accent"], 80), width=2)
    y += 30
    beneficios = ["Comisiones del 7% al 15%", "Sin inversion inicial", "Cobras el dia 5 de cada mes"]
    for b in beneficios:
        bf = _font("m", 22)
        full = f"→  {b}"
        bw = draw.textbbox((0, 0), full, font=bf)[2]
        draw.text(((W - bw) // 2, y), "→", fill=pal["accent"], font=bf)
        draw.text(((W - bw) // 2 + 35, y), b, fill=pal["text2"], font=bf)
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
    # Badge de pilar removido por diseño

    bullets = data.get("bullets", [])
    hook = data.get("hook", "")
    hook_h = (40 + len(_wrap(hook, _font("b", 24), 880, draw)) * 36) if hook else 0
    content_h = 120 + 40 + 30 + 30 + 3 + len(bullets) * 60 + hook_h + 50 + 30 + 120 + 40 + 30
    usable = h - 88 - 72
    mid_y = 88 + max(20, (usable - content_h) // 2)

    numero = data.get("numero_grande", "$45.600")
    nf = _font("h", 110)
    nw = draw.textbbox((0, 0), numero, font=nf)[2]
    draw.text(((W - nw) // 2, mid_y), numero, fill=pal["accent"], font=nf)

    subtexto = data.get("subtexto", "")
    if subtexto:
        sf = _font("m", 28)
        sw = draw.textbbox((0, 0), subtexto, font=sf)[2]
        draw.text(((W - sw) // 2, mid_y + 130), subtexto, fill=pal["text2"], font=sf)

    draw.line([(180, mid_y + 190), (W - 180, mid_y + 190)], fill=pal["accent"], width=3)

    y = mid_y + 230
    for b in bullets[:5]:
        b_clean = ''.join(c if ord(c) < 0x10000 else '' for c in b)
        full = f"→  {b_clean}"
        bf = _font("h", 34)
        bw = draw.textbbox((0, 0), full, font=bf)[2]
        bx = (W - bw) // 2
        draw.text((bx, y), "→", fill=pal["accent"], font=bf)
        draw.text((bx + 50, y), b_clean, fill=pal["text"], font=bf)
        y += 60

    if hook:
        y += 40
        for line in _wrap(hook, _font("b", 24), 880, draw)[:3]:
            lw = draw.textbbox((0, 0), line, font=_font("b", 24))[2]
            draw.text(((W - lw) // 2, y), line, fill=pal["text2"], font=_font("b", 24))
            y += 36

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
    # Badge de pilar removido por diseño

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
        lw = draw.textbbox((0, 0), line, font=_font("h", 54))[2]
        draw.text(((W - lw) // 2, y), line, fill=pal["text"], font=_font("h", 54))
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
    # Badge de pilar removido por diseño

    prod_url = data.get("producto_imagen", "")
    prod_img = _download_img(prod_url) if prod_url else None
    if prod_img:
        ps = 620
        prod_img = prod_img.resize((ps, ps), Image.LANCZOS)
        mask = Image.new("L", prod_img.size, 0)
        ImageDraw.Draw(mask).rounded_rectangle([0, 0, ps, ps], radius=28, fill=255)
        prod_img.putalpha(mask)
        shadow = Image.new("RGBA", (ps + 24, ps + 24), (0, 0, 0, 0))
        ImageDraw.Draw(shadow).rounded_rectangle([12, 12, ps + 12, ps + 12], radius=28, fill=(0, 0, 0, 35))
        shadow = shadow.filter(ImageFilter.GaussianBlur(12))
        img.paste(shadow, (W // 2 - ps // 2 - 12, 100), shadow)
        img.paste(prod_img, (W // 2 - ps // 2, 112), prod_img)

    # Hook grande (centrado)
    hook = data.get("hook", "")
    y = 770
    for line in _wrap(hook, _font("h", 44), 960, draw)[:2]:
        lw = draw.textbbox((0, 0), line, font=_font("h", 44))[2]
        draw.text(((W - lw) // 2, y), line, fill=pal["text"], font=_font("h", 44))
        y += 56

    # Nombre producto (centrado)
    nombre = data.get("producto_nombre", "")
    y += 6
    for line in _wrap(nombre, _font("m", 24), 750, draw)[:2]:
        lw = draw.textbbox((0, 0), line, font=_font("m", 24))[2]
        draw.text(((W - lw) // 2, y), line, fill=pal["text2"], font=_font("m", 24))
        y += 32

    # Precios centrados: público tachado + con descuento
    precio = data.get("producto_precio", 0)
    precio_desc = round(precio * 0.80)
    y += 18

    precio_pub = f"${precio:,.0f}".replace(",", ".")
    precio_off = f"${precio_desc:,.0f}".replace(",", ".")
    ppf = _font("m", 32)
    pof = _font("h", 48)
    ppw = draw.textbbox((0, 0), precio_pub, font=ppf)[2]
    pow_ = draw.textbbox((0, 0), precio_off, font=pof)[2]
    total_price_w = ppw + 20 + pow_
    px = (W - total_price_w) // 2

    draw.text((px, y), precio_pub, fill=pal["text2"], font=ppf)
    pp_mid = y + 18
    draw.line([(px - 2, pp_mid), (px + ppw + 2, pp_mid)], fill=pal["text2"], width=3)
    draw.text((px + ppw + 20, y - 10), precio_off, fill=pal["accent"], font=pof)

    # Badge centrado
    y += 60
    badge_text = "Hasta 20% OFF con codigo referido"
    btf = _font("h", 20)
    btw = draw.textbbox((0, 0), badge_text, font=btf)[2] + 28
    bx = (W - btw) // 2
    draw.rounded_rectangle([bx, y, bx + btw, y + 40], radius=20, fill=pal["accent"])
    draw.text((bx + 14, y + 8), badge_text, fill=INK, font=btf)

    # Trust badges centrados
    y += 56
    trust_items = [
        "Envio a todo el pais  ·  Pagos con MercadoPago",
        "10 dias de devolucion  ·  6 meses de garantia",
    ]
    for text_row in trust_items:
        trw = draw.textbbox((0, 0), text_row, font=_font("b", 19))[2]
        draw.text(((W - trw) // 2, y), text_row, fill=pal["text2"], font=_font("b", 19))
        y += 30

    # URL centrada
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


def compose_carousel(
    persona="maria", pilar="educativo", hook="", titulo="",
    puntos=None, cta_bar="", output_prefix=None,
    producto_nombre="", producto_precio=0, producto_imagen_url="",
) -> list:
    """Genera carrusel de N slides (1080x1350) y retorna lista de paths."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    pal = PALETAS.get(persona, PALETAS["maria"])
    h = H_FEED
    items = puntos or []
    if not output_prefix:
        import time as _t
        output_prefix = f"carousel_{persona}_{int(_t.time())}"

    paths = []

    # SLIDE 1: Cover (hook/titulo grande)
    img = Image.new("RGBA", (W, h), pal["bg"])
    draw = ImageDraw.Draw(img)
    _top_bar(img, draw, pal, h)
    # Badge de pilar removido por diseño

    cover_title = hook or titulo or "Tips"
    y = h // 2 - 120
    for line in _wrap(cover_title, _font("h", 58), 900, draw)[:4]:
        draw.text((80, y), line, fill=pal["text"], font=_font("h", 58))
        y += 72

    y += 30
    sub = f"{len(items)} tips que necesitas saber"
    sf = _font("m", 26)
    draw.text((80, y), sub, fill=pal["text2"], font=sf)

    y += 50
    draw.text((80, y), "Desliza para ver todos", fill=pal["accent"], font=_font("h", 28))
    draw.text((430, y), "→", fill=pal["accent"], font=_font("h", 32))

    # Indicador de slides (puntos)
    dot_y = h - 120
    total_dots = len(items) + 2
    dot_w = total_dots * 24
    dot_x = (W - dot_w) // 2
    for d in range(total_dots):
        color = pal["accent"] if d == 0 else (*pal["text2"], 80)
        draw.ellipse([dot_x + d * 24, dot_y, dot_x + d * 24 + 12, dot_y + 12], fill=color)

    _bottom_bar(draw, cta_bar or "Desliza para ver todos los tips", pal, h)
    p = OUTPUT_DIR / f"{output_prefix}_01_cover.jpg"
    img.convert("RGB").save(str(p), "JPEG", quality=92)
    paths.append(str(p))

    # SLIDES 2 a N: un punto por slide
    for idx, punto in enumerate(items[:8]):
        img = Image.new("RGBA", (W, h), pal["bg"])
        draw = ImageDraw.Draw(img)
        _top_bar(img, draw, pal, h)

        # Número grande
        num = str(idx + 1)
        nf = _font("h", 140)
        nw = draw.textbbox((0, 0), num, font=nf)[2]
        draw.text(((W - nw) // 2, h // 2 - 220), num, fill=(*pal["accent"], 40), font=nf)

        # Texto del punto centrado
        punto_clean = ''.join(c if ord(c) < 0x10000 else '' for c in punto)
        y = h // 2 - 30
        for line in _wrap(punto_clean, _font("h", 40), 860, draw)[:4]:
            tw = draw.textbbox((0, 0), line, font=_font("h", 40))[2]
            draw.text(((W - tw) // 2, y), line, fill=pal["text"], font=_font("h", 40))
            y += 52

        # Indicador de slides
        for d in range(total_dots):
            color = pal["accent"] if d == idx + 1 else (*pal["text2"], 80)
            draw.ellipse([dot_x + d * 24, dot_y, dot_x + d * 24 + 12, dot_y + 12], fill=color)

        _bottom_bar(draw, f"{idx + 1}/{len(items)}", pal, h)
        p = OUTPUT_DIR / f"{output_prefix}_{idx + 2:02d}.jpg"
        img.convert("RGB").save(str(p), "JPEG", quality=92)
        paths.append(str(p))

    # SLIDE FINAL: CTA
    img = Image.new("RGBA", (W, h), pal["bg"])
    draw = ImageDraw.Draw(img)
    _top_bar(img, draw, pal, h)

    y = h // 2 - 100
    cta_title = "Queres empezar a ganar?"
    for line in _wrap(cta_title, _font("h", 52), 900, draw)[:2]:
        tw = draw.textbbox((0, 0), line, font=_font("h", 52))[2]
        draw.text(((W - tw) // 2, y), line, fill=pal["text"], font=_font("h", 52))
        y += 66

    y += 30
    url = "elgadget.com.ar/referidos"
    uf = _font("h", 36)
    uw = draw.textbbox((0, 0), url, font=uf)[2]
    draw.text(((W - uw) // 2, y), url, fill=pal["accent"], font=uf)

    y += 60
    beneficios = ["Registro gratis", "Comisiones del 7% al 15%", "Cobro mensual"]
    for b in beneficios:
        bf = _font("m", 24)
        bw = draw.textbbox((0, 0), b, font=bf)[2]
        draw.text(((W - bw) // 2, y), b, fill=pal["text2"], font=bf)
        y += 38

    for d in range(total_dots):
        color = pal["accent"] if d == total_dots - 1 else (*pal["text2"], 80)
        draw.ellipse([dot_x + d * 24, dot_y, dot_x + d * 24 + 12, dot_y + 12], fill=color)

    _bottom_bar(draw, cta_bar or "Link en bio", pal, h)
    p = OUTPUT_DIR / f"{output_prefix}_{len(items) + 2:02d}_cta.jpg"
    img.convert("RGB").save(str(p), "JPEG", quality=92)
    paths.append(str(p))

    return paths


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
