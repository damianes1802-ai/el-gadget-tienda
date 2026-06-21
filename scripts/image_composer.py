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
LOGO_PATH = BASE_DIR / "marketing_app" / "assets" / "logo_transparente.png"
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
        "text": INK, "text2": (90, 85, 78), "accent": ACCENT,
        "badge_bg": GREEN, "badge_text": WHITE,
        "bullet_bg": (255, 243, 200), "bullet_icon": ACCENT_DEEP,
    },
    "lucas": {
        "bg": INK, "bar": (5, 5, 8),
        "text": WHITE, "text2": (190, 190, 195), "accent": ACCENT,
        "badge_bg": ACCENT, "badge_text": INK,
        "bullet_bg": (35, 35, 45), "bullet_icon": ACCENT,
    },
    "ana": {
        "bg": WHITE, "bar": (35, 35, 40),
        "text": INK, "text2": (90, 90, 95), "accent": (160, 140, 100),
        "badge_bg": INK, "badge_text": WHITE,
        "bullet_bg": (240, 238, 233), "bullet_icon": (160, 140, 100),
    },
    "sofi": {
        "bg": (255, 245, 248), "bar": (40, 25, 35),
        "text": INK, "text2": (110, 75, 95), "accent": (230, 100, 145),
        "badge_bg": (200, 90, 140), "badge_text": WHITE,
        "bullet_bg": (255, 225, 235), "bullet_icon": (200, 90, 140),
    },
    "martin": {
        "bg": (20, 30, 50), "bar": (10, 15, 30),
        "text": WHITE, "text2": (175, 185, 210), "accent": ACCENT,
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
    logo = _logo(44)
    if logo:
        img.paste(logo, (26, 22), logo)
    draw.text((80, 22), "El", fill=WHITE, font=_font("h", 28))
    draw.text((112, 22), " Gadget", fill=ACCENT, font=_font("h", 28))
    draw.text((80, 54), "TIENDA ONLINE", fill=(160, 160, 160), font=_font("m", 12))
    ig = "@elgadget.ok"
    igf = _font("m", 16)
    igw = draw.textbbox((0, 0), ig, font=igf)[2]
    draw.text((W - igw - 24, 36), ig, fill=(140, 140, 140), font=igf)


def _bottom_bar(draw, text, pal, h):
    bar_h = 72
    y = h - bar_h
    text = _clean(text)
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
        tw = draw.textbbox((0, 0), txt, font=_font("m", 20))[2]
        draw.text((cx - tw // 2, y + 52), txt, fill=pal["text2"], font=_font("m", 20))

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
        trw = draw.textbbox((0, 0), text_row, font=_font("b", 22))[2]
        draw.text(((W - trw) // 2, y), text_row, fill=pal["text2"], font=_font("b", 22))
        y += 30

    # URL centrada
    y += 20
    url = "elgadget.com.ar"
    uf = _font("h", 28)
    uw = draw.textbbox((0, 0), url, font=uf)[2]
    draw.text(((W - uw) // 2, y), url, fill=pal["accent"], font=uf)

    _bottom_bar(draw, data.get("cta_bar", "Link en bio · elgadget.com.ar"), pal, h)


# ============================================================================
# HELPERS REUTILIZABLES
# ============================================================================

def _programa_footer(draw, pal, y, h):
    """3 pasos circulares: Registrate → Compartí → Cobrá"""
    draw.line([(180, y), (W - 180, y)], fill=pal["accent"], width=2)
    y += 30
    pasos = [("1", "Registrate gratis"), ("2", "Comparti tu codigo"), ("3", "Cobra comisiones")]
    paso_w = (W - 120) // 3
    for i, (num, txt) in enumerate(pasos):
        cx = 60 + i * paso_w + paso_w // 2
        draw.ellipse([cx - 22, y - 2, cx + 22, y + 42], fill=pal["accent"])
        nw = draw.textbbox((0, 0), num, font=_font("h", 22))[2]
        draw.text((cx - nw // 2, y + 6), num, fill=INK, font=_font("h", 22))
        tw = draw.textbbox((0, 0), txt, font=_font("m", 20))[2]
        draw.text((cx - tw // 2, y + 52), txt, fill=pal["text2"], font=_font("m", 20))
    return y + 100


def _url_block(draw, pal, y, url="elgadget.com.ar/referidos"):
    """URL centrada en dorado"""
    uf = _font("h", 30)
    uw = draw.textbbox((0, 0), url, font=uf)[2]
    draw.text(((W - uw) // 2, y), url, fill=pal["accent"], font=uf)
    return y + 40


def _centered_text(draw, y, text, font, fill, max_w=960):
    """Dibuja texto centrado, retorna nuevo Y"""
    for line in _wrap(text, font, max_w, draw):
        lw = draw.textbbox((0, 0), line, font=font)[2]
        draw.text(((W - lw) // 2, y), line, fill=fill, font=font)
        y += font.size + 14
    return y


def _clean(text):
    """Limpia emojis unicode no renderizables"""
    return ''.join(c if ord(c) < 0x10000 else '' for c in str(text))


# ============================================================================
# LAYOUT L02: ANTES / DESPUÉS (split screen)
# ============================================================================
def _layout_antes_despues(img, draw, pal, data, h):
    _top_bar(img, draw, pal, h)

    hook = data.get("hook", "")
    antes = _clean(data.get("antes_texto", "Antes"))
    despues = _clean(data.get("despues_texto", "Después"))

    zone = h - 88 - 72
    card_w = 480
    card_h = min(620, zone - 340)
    gap = 20
    lx = (W - card_w * 2 - gap) // 2
    rx = lx + card_w + gap

    total_h = 80 + 40 + card_h + 50 + 100 + 40
    y = 88 + max(20, (zone - total_h) // 2)

    # Hook centrado
    y = _centered_text(draw, y, hook, _font("h", 44), pal["text"], 900)
    y += 30

    antes_bg = (255, 230, 230) if pal["bg"][0] > 100 else (60, 25, 25)
    antes_color = (200, 50, 50) if pal["bg"][0] > 100 else (255, 120, 120)
    desp_bg = (225, 250, 230) if pal["bg"][0] > 100 else (20, 50, 28)
    desp_color = (40, 150, 70) if pal["bg"][0] > 100 else (100, 220, 130)

    # Card ANTES
    draw.rounded_rectangle([lx, y, lx + card_w, y + card_h], radius=22, fill=antes_bg)
    lf = _font("h", 30)
    lw = draw.textbbox((0, 0), "ANTES", font=lf)[2]
    draw.text((lx + (card_w - lw) // 2, y + 30), "ANTES", fill=antes_color, font=lf)
    af = _font("m", 26)
    a_lines = _wrap(antes, af, card_w - 60, draw)[:8]
    ay = y + 80 + (card_h - 110 - len(a_lines) * 36) // 2
    for line in a_lines:
        alw = draw.textbbox((0, 0), line, font=af)[2]
        draw.text((lx + (card_w - alw) // 2, ay), line, fill=pal["text"], font=af)
        ay += 36

    # Card DESPUÉS
    draw.rounded_rectangle([rx, y, rx + card_w, y + card_h], radius=22, fill=desp_bg)
    lw = draw.textbbox((0, 0), "DESPUÉS", font=lf)[2]
    draw.text((rx + (card_w - lw) // 2, y + 30), "DESPUÉS", fill=desp_color, font=lf)
    d_lines = _wrap(despues, af, card_w - 60, draw)[:8]
    dy = y + 80 + (card_h - 110 - len(d_lines) * 36) // 2
    for line in d_lines:
        dlw = draw.textbbox((0, 0), line, font=af)[2]
        draw.text((rx + (card_w - dlw) // 2, dy), line, fill=pal["text"], font=af)
        dy += 36

    y += card_h + 30
    y = _programa_footer(draw, pal, y, h)
    y = _url_block(draw, pal, y)
    _bottom_bar(draw, data.get("cta_bar", "Guardalo y volve cuando lo necesites"), pal, h)


# ============================================================================
# LAYOUT L04: HISTORIA + CTA (storytelling centrado)
# ============================================================================
def _layout_historia(img, draw, pal, data, h):
    _top_bar(img, draw, pal, h)

    hook = data.get("hook", "")
    historia = _clean(data.get("historia_texto", ""))

    zone = h - 88 - 72
    hf = _font("h", 50)
    bf = _font("m", 28)
    h_lines = _wrap(hook, hf, 880, draw)[:3]
    b_lines = _wrap(historia, bf, 840, draw)[:8] if historia else []

    # Separador visual entre hook y historia
    content_h = len(h_lines) * 64 + 30 + 3 + 30 + len(b_lines) * 40 + 50 + 100 + 40
    y = 88 + max(20, (zone - content_h) // 2)

    for line in h_lines:
        lw = draw.textbbox((0, 0), line, font=hf)[2]
        draw.text(((W - lw) // 2, y), line, fill=pal["text"], font=hf)
        y += 64
    y += 30

    # Línea separadora
    draw.line([(200, y), (W - 200, y)], fill=pal["accent"], width=3)
    y += 30

    # Historia centrada
    for line in b_lines:
        lw = draw.textbbox((0, 0), line, font=bf)[2]
        draw.text(((W - lw) // 2, y), line, fill=pal["text2"], font=bf)
        y += 40
    y += 40

    y = _programa_footer(draw, pal, y, h)
    y = _url_block(draw, pal, y)
    _bottom_bar(draw, data.get("cta_bar", "Guardalo y registrate cuando puedas"), pal, h)


# ============================================================================
# LAYOUT L06: MITO VS REALIDAD (2 columnas)
# ============================================================================
def _layout_mito_realidad(img, draw, pal, data, h):
    _top_bar(img, draw, pal, h)

    hook = data.get("hook", "")
    mitos = [_clean(m) for m in (data.get("mitos") or [])][:3]
    realidades = [_clean(r) for r in (data.get("realidades") or [])][:3]
    n = max(len(mitos), len(realidades), 1)

    mito_color = (200, 60, 60) if pal["bg"][0] > 100 else (255, 100, 100)
    real_color = (40, 160, 70) if pal["bg"][0] > 100 else (100, 220, 130)

    # Calcular tamaño para llenar el espacio
    zone = h - 88 - 72
    card_h = min(160, (zone - 200) // n - 24)
    col_w = 475
    gap = 20
    lx = (W - col_w * 2 - gap) // 2
    rx = lx + col_w + gap
    total_h = 80 + 44 + n * (card_h + 24) + 60 + 40
    y = 88 + max(20, (zone - total_h) // 2)

    # Hook
    y = _centered_text(draw, y, hook, _font("h", 44), pal["text"], 900)
    y += 24

    # Headers
    hf = _font("h", 26)
    mhw = draw.textbbox((0, 0), "MITO", font=hf)[2]
    rhw = draw.textbbox((0, 0), "REALIDAD", font=hf)[2]
    draw.text((lx + (col_w - mhw) // 2, y), "MITO", fill=mito_color, font=hf)
    draw.text((rx + (col_w - rhw) // 2, y), "REALIDAD", fill=real_color, font=hf)
    y += 44

    for i in range(n):
        m_bg = (255, 240, 240) if pal["bg"][0] > 100 else (50, 25, 25)
        r_bg = (235, 250, 238) if pal["bg"][0] > 100 else (20, 45, 25)
        draw.rounded_rectangle([lx, y, lx + col_w, y + card_h], radius=16, fill=m_bg)
        draw.rounded_rectangle([rx, y, rx + col_w, y + card_h], radius=16, fill=r_bg)
        # Icons
        draw.text((lx + 18, y + card_h // 2 - 18), "✗", fill=mito_color, font=_font("h", 34))
        draw.text((rx + 18, y + card_h // 2 - 18), "✓", fill=real_color, font=_font("h", 34))
        # Texto centrado verticalmente
        mf = _font("m", 24)
        if i < len(mitos):
            m_lines = _wrap(mitos[i], mf, col_w - 80, draw)[:3]
            my = y + (card_h - len(m_lines) * 32) // 2
            for ml in m_lines:
                draw.text((lx + 60, my), ml, fill=pal["text"], font=mf)
                my += 32
        if i < len(realidades):
            r_lines = _wrap(realidades[i], mf, col_w - 80, draw)[:3]
            ry = y + (card_h - len(r_lines) * 32) // 2
            for rl in r_lines:
                draw.text((rx + 60, ry), rl, fill=pal["text"], font=mf)
                ry += 32
        y += card_h + 24

    y += 20
    y = _programa_footer(draw, pal, y, h)
    y = _url_block(draw, pal, y)
    _bottom_bar(draw, data.get("cta_bar", "Guardalo y volve cuando lo necesites"), pal, h)


# ============================================================================
# LAYOUT L08: COMPARATIVA PRECIOS (El Gadget vs competencia)
# ============================================================================
def _layout_comparativa(img, draw, pal, data, h):
    _top_bar(img, draw, pal, h)

    hook = data.get("hook", "")
    comp_label = _clean(data.get("precio_competencia_label", "En otros lados: $150.000"))
    prop_label = _clean(data.get("precio_propio_label", "En El Gadget: $106.125"))

    zone = h - 88 - 72
    card_w = 460
    card_h = min(380, (zone - 400) // 1)
    gap = 30
    lx = (W - card_w * 2 - gap) // 2
    rx = lx + card_w + gap

    total_h = 80 + 50 + card_h + 40 + 100 + 40
    y = 88 + max(20, (zone - total_h) // 2)

    y = _centered_text(draw, y, hook, _font("h", 44), pal["text"], 900)
    y += 40

    comp_parts = comp_label.split(":")
    comp_title = (comp_parts[0].strip() if comp_parts else "Otros")
    comp_price = (comp_parts[1].strip() if len(comp_parts) > 1 else comp_label)
    prop_parts = prop_label.split(":")
    prop_title = (prop_parts[0].strip() if prop_parts else "El Gadget")
    prop_price = (prop_parts[1].strip() if len(prop_parts) > 1 else prop_label)

    # Card competencia
    comp_bg = (245, 238, 238) if pal["bg"][0] > 100 else (50, 35, 35)
    draw.rounded_rectangle([lx, y, lx + card_w, y + card_h], radius=22, fill=comp_bg)
    ctf = _font("m", 24)
    ctw = draw.textbbox((0, 0), comp_title, font=ctf)[2]
    draw.text((lx + (card_w - ctw) // 2, y + 40), comp_title, fill=pal["text2"], font=ctf)
    max_price_w = card_w - 50
    cp_sz = 56
    cpf = _font("h", cp_sz)
    cpw = draw.textbbox((0, 0), comp_price, font=cpf)[2]
    while cpw > max_price_w and cp_sz > 28:
        cp_sz -= 4
        cpf = _font("h", cp_sz)
        cpw = draw.textbbox((0, 0), comp_price, font=cpf)[2]
    cp_y = y + card_h // 2 - 20
    draw.text((lx + (card_w - cpw) // 2, cp_y), comp_price, fill=pal["text2"], font=cpf)
    draw.line([(lx + (card_w - cpw) // 2 - 10, cp_y + cp_sz // 2 + 4), (lx + (card_w + cpw) // 2 + 10, cp_y + cp_sz // 2 + 4)], fill=(200, 60, 60), width=4)

    # Card El Gadget
    prop_bg = pal["bullet_bg"]
    draw.rounded_rectangle([rx, y, rx + card_w, y + card_h], radius=22, fill=prop_bg)
    ptw = draw.textbbox((0, 0), prop_title, font=ctf)[2]
    draw.text((rx + (card_w - ptw) // 2, y + 40), prop_title, fill=pal["text"], font=ctf)
    pp_sz = 62
    ppf = _font("h", pp_sz)
    ppw = draw.textbbox((0, 0), prop_price, font=ppf)[2]
    while ppw > max_price_w and pp_sz > 28:
        pp_sz -= 4
        ppf = _font("h", pp_sz)
        ppw = draw.textbbox((0, 0), prop_price, font=ppf)[2]
    draw.text((rx + (card_w - ppw) // 2, y + card_h // 2 - 25), prop_price, fill=pal["accent"], font=ppf)
    badge = "Hasta 20% OFF extra con referido"
    bbf = _font("h", 18)
    bbw = draw.textbbox((0, 0), badge, font=bbf)[2] + 28
    bx = rx + (card_w - bbw) // 2
    draw.rounded_rectangle([bx, y + card_h - 70, bx + bbw, y + card_h - 36], radius=16, fill=pal["accent"])
    draw.text((bx + 14, y + card_h - 65), badge, fill=INK, font=bbf)

    # VS
    vs_f = _font("h", 40)
    vs_w = draw.textbbox((0, 0), "VS", font=vs_f)[2]
    draw.text(((W - vs_w) // 2, y + card_h // 2 - 22), "VS", fill=pal["text2"], font=vs_f)

    y += card_h + 30
    y = _programa_footer(draw, pal, y, h)
    y = _url_block(draw, pal, y)
    _bottom_bar(draw, data.get("cta_bar", "Mejor precio + descuento referido"), pal, h)


# ============================================================================
# LAYOUT L09: PASO A PASO (N pasos circulares)
# ============================================================================
def _layout_pasos(img, draw, pal, data, h):
    _top_bar(img, draw, pal, h)

    hook = data.get("hook", "")
    pasos = [_clean(p) for p in (data.get("pasos") or [])][:5]

    # Hook centrado
    zone_top, zone_bot = 88, h - 72
    hf = _font("h", 48)
    h_lines = _wrap(hook, hf, 900, draw)[:3]
    content_h = len(h_lines) * 62 + 40 + len(pasos) * 160 + 80 + 40
    y = zone_top + max(20, (zone_bot - zone_top - content_h) // 2)

    for line in h_lines:
        lw = draw.textbbox((0, 0), line, font=hf)[2]
        draw.text(((W - lw) // 2, y), line, fill=pal["text"], font=hf)
        y += 62
    y += 40

    # Pasos como cards verticales con número circular
    for i, paso in enumerate(pasos):
        card_y = y
        draw.rounded_rectangle([80, card_y, W - 80, card_y + 120], radius=16, fill=pal["bullet_bg"])

        # Número circular
        cx = 150
        cy = card_y + 60
        draw.ellipse([cx - 28, cy - 28, cx + 28, cy + 28], fill=pal["accent"])
        num = str(i + 1)
        nf = _font("h", 28)
        nw = draw.textbbox((0, 0), num, font=nf)[2]
        draw.text((cx - nw // 2, cy - 16), num, fill=INK, font=nf)

        # Texto del paso
        pf = _font("m", 28)
        for j, pl in enumerate(_wrap(paso, pf, W - 320, draw)[:2]):
            draw.text((200, card_y + 30 + j * 36), pl, fill=pal["text"], font=pf)

        # Línea conectora (excepto último)
        if i < len(pasos) - 1:
            draw.line([(150, card_y + 120), (150, card_y + 150)], fill=pal["accent"], width=3)

        y += 150

    y += 10
    y = _url_block(draw, pal, y)
    _bottom_bar(draw, data.get("cta_bar", "Empeza hoy mismo"), pal, h)


# ============================================================================
# LAYOUT L10: CHECKLIST (items con checkmarks)
# ============================================================================
def _layout_checklist(img, draw, pal, data, h):
    _top_bar(img, draw, pal, h)

    hook = data.get("hook", "")
    items = [_clean(it) for it in (data.get("items_check") or [])][:6]

    # Hook centrado
    zone_top, zone_bot = 88, h - 72
    hf = _font("h", 48)
    h_lines = _wrap(hook, hf, 900, draw)[:3]
    ch = 90
    gap = 18
    content_h = len(h_lines) * 62 + 30 + len(items) * (ch + gap) + 80 + 40
    y = zone_top + max(20, (zone_bot - zone_top - content_h) // 2)

    for line in h_lines:
        lw = draw.textbbox((0, 0), line, font=hf)[2]
        draw.text(((W - lw) // 2, y), line, fill=pal["text"], font=hf)
        y += 62
    y += 30

    # Items con checkmarks
    check_color = (40, 160, 70) if pal["bg"][0] > 100 else (100, 220, 130)
    for item in items:
        draw.rounded_rectangle([50, y, W - 50, y + ch], radius=14, fill=pal["bullet_bg"])
        # Checkmark circle
        cx, cy = 96, y + ch // 2
        draw.ellipse([cx - 20, cy - 20, cx + 20, cy + 20], fill=check_color)
        draw.text((cx - 10, cy - 14), "✓", fill=WHITE, font=_font("h", 22))
        # Item text
        draw.text((134, y + (ch - 26) // 2), item[:60], fill=pal["text"], font=_font("m", 26))
        y += ch + gap

    y += 20
    y = _url_block(draw, pal, y)
    _bottom_bar(draw, data.get("cta_bar", "elgadget.com.ar/referidos"), pal, h)


# ============================================================================
# MAIN
# ============================================================================
LAYOUTS = {
    # Mapeo L01-L10
    "L01": _layout_educativo,
    "L02": _layout_antes_despues,
    "L03": _layout_motivacional,
    "L04": _layout_historia,
    "L05": _layout_engagement,
    "L06": _layout_mito_realidad,
    "L07": _layout_producto,
    "L08": _layout_comparativa,
    "L09": _layout_pasos,
    "L10": _layout_checklist,
    # Legacy fallbacks (pilar name → function)
    "educativo": _layout_educativo,
    "motivacional": _layout_motivacional,
    "engagement": _layout_engagement,
    "producto": _layout_producto,
}

def compose_image(
    producto_nombre="", producto_precio=0, producto_imagen_url="",
    persona="maria", pilar="producto", formato="PR-01", hook="",
    output_filename=None, layout_id=None,
    titulo="", puntos=None, numero_grande="", subtexto="",
    bullets=None, pregunta="", opciones=None, cta_bar="", emoji="",
    antes_texto="", despues_texto="", historia_texto="",
    mitos=None, realidades=None,
    precio_competencia_label="", precio_propio_label="",
    pasos=None, items_check=None,
    size_format="feed",
) -> str:
    """Genera imagen branded para Instagram.
    layout_id: L01-L10 (toma precedencia sobre pilar)
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
        "antes_texto": antes_texto, "despues_texto": despues_texto,
        "historia_texto": historia_texto,
        "mitos": mitos or [], "realidades": realidades or [],
        "precio_competencia_label": precio_competencia_label,
        "precio_propio_label": precio_propio_label,
        "pasos": pasos or [], "items_check": items_check or [],
    }

    # Layout resolution: layout_id > pilar > fallback
    if layout_id and layout_id in LAYOUTS:
        layout_fn = LAYOUTS[layout_id]
    else:
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
    # Centrado vertical del bloque completo
    hf = _font("h", 56)
    c_lines = _wrap(cover_title, hf, 880, draw)[:4]
    block_h = len(c_lines) * 70 + 30 + 3 + 40 + 30 + 34
    y = 88 + max(40, (h - 88 - 72 - block_h) // 2)

    for line in c_lines:
        lw = draw.textbbox((0, 0), line, font=hf)[2]
        draw.text(((W - lw) // 2, y), line, fill=pal["text"], font=hf)
        y += 70

    y += 20
    draw.line([(250, y), (W - 250, y)], fill=pal["accent"], width=3)
    y += 30

    sub = f"{len(items)} tips que necesitas saber"
    sf = _font("m", 28)
    sw = draw.textbbox((0, 0), sub, font=sf)[2]
    draw.text(((W - sw) // 2, y), sub, fill=pal["text2"], font=sf)

    y += 50
    desliza = "Desliza para ver todos  →"
    df = _font("h", 30)
    dw = draw.textbbox((0, 0), desliza, font=df)[2]
    draw.text(((W - dw) // 2, y), desliza, fill=pal["accent"], font=df)

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
    tests = [
        ("L01", dict(persona="maria", layout_id="L01", hook="5 formas de compartir tu codigo",
            titulo="5 formas de compartir tu codigo", puntos=["Mandalo por WhatsApp", "Subilo a Stories", "Grupos de mamas", "Link directo", "Facebook o TikTok"])),
        ("L02", dict(persona="lucas", layout_id="L02", hook="Tu espacio de trabajo cambio para siempre",
            antes_texto="Escritorio lleno de cables, papeles y tazas de ayer. No encontras nada cuando lo necesitas.",
            despues_texto="Todo organizado, cada cosa en su lugar. Arrancas el dia con la cabeza despejada.")),
        ("L03", dict(persona="lucas", layout_id="L03", hook="La matematica es simple",
            numero_grande="$45.600", subtexto="ganaron nuestros referidos este mes",
            bullets=["Sin inversion inicial", "Sin stock ni envios", "Cobras el dia 5", "Comisiones 7-15%"])),
        ("L04", dict(persona="ana", layout_id="L04", hook="No es otro trabajo. Es cobrar por lo que ya haces.",
            historia_texto="Cada vez que alguien te pregunta donde compraste algo, le estas regalando una recomendacion. El programa de referidos de El Gadget convierte eso en comisiones reales. Sin contratos, sin obligaciones.")),
        ("L05", dict(persona="maria", layout_id="L05", hook="Tu opinion nos importa",
            pregunta="Que harias con $30.000 extra por mes?", opciones=["Pagar deudas", "Vacaciones", "Compras para casa", "Tecnologia"])),
        ("L06", dict(persona="lucas", layout_id="L06", hook="Lo que pensas vs lo que es",
            mitos=["Necesitas invertir plata", "Tenes que vender puerta a puerta", "Solo ganan los influencers"],
            realidades=["Registrarte es 100% gratis", "Compartis un link y listo", "Cualquiera puede ganar"])),
        ("L07", dict(persona="maria", layout_id="L07", hook="Tu casa parece un caos?",
            producto_nombre="Estanteria Plegable Metal Negra", producto_precio=106125,
            producto_imagen_url="https://res.cloudinary.com/deq2ofluf/image/upload/prod_DL2321_001")),
        ("L08", dict(persona="sofi", layout_id="L08", hook="El mismo producto, diferente precio",
            precio_competencia_label="En MercadoLibre: $153.000", precio_propio_label="En El Gadget: $106.125")),
        ("L09", dict(persona="lucas", layout_id="L09", hook="Empeza a ganar en 3 pasos",
            pasos=["Registrate gratis en 2 minutos", "Recibi tu codigo personalizado", "Comparti con amigos y familia", "Cobra comisiones el dia 5"])),
        ("L10", dict(persona="ana", layout_id="L10", hook="Checklist del referido exitoso",
            items_check=["Registrarse gratis", "Compartir codigo con 5 amigos", "Esperar la primera compra", "Cobrar comision el dia 5", "Repetir y subir de tier"])),
    ]
    for name, kwargs in tests:
        compose_image(**kwargs, output_filename=f"test_{name}.jpg")
        print(f"  {name}: OK")
    print(f"\n{len(tests)} layouts generados (1080x1350)")
