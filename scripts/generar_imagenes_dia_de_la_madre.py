#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
IMÁGENES DE SALUDO "FELIZ DÍA DE LA MADRE" (descargables desde el blog)

Genera 4 PNG cuadrados (1080x1080, < 300 KB cada uno) en el estilo de marca
de El Gadget (negro #14151A, amarillo #FFC700, Space Grotesk / Inter) en
pages/assets/img/dia-de-la-madre/, con nombres de archivo pensados para el
intent de búsqueda "imágenes feliz día de la madre 2026".

Las usa el post /blog/regalos-dia-de-la-madre/ (ver utils/blog_posts.py,
IMAGENES_DIA_DE_LA_MADRE: nombre de archivo + alt). Si se cambia un nombre
acá hay que cambiarlo allá.

Es reproducible: mismo script, mismas imágenes. Se corre a mano cuando se
quiere cambiar el diseño (no forma parte del pipeline diario):

    python scripts/generar_imagenes_dia_de_la_madre.py
"""

import math
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

BASE_DIR = Path(__file__).resolve().parent.parent
FONTS_DIR = BASE_DIR / 'marketing_app' / 'assets' / 'fonts'
OUT_DIR = BASE_DIR / 'pages' / 'assets' / 'img' / 'dia-de-la-madre'

INK = (20, 21, 26)
INK_SOFT = (44, 46, 54)
ACCENT = (255, 199, 0)
ACCENT_DEEP = (224, 172, 0)
CREAM = (247, 246, 243)
WHITE = (255, 255, 255)
GRAY = (172, 167, 159)

SIZE = 1080
SS = 2  # supersampling: se dibuja al doble y se reduce (bordes suaves en las formas)
W = SIZE * SS
MAX_BYTES = 300 * 1024

# (archivo, alt) — el post los referencia por este orden
IMAGENES = [
    ('imagen-feliz-dia-de-la-madre-2026-negro-y-amarillo.png',
     'Imagen de Feliz Día de la Madre 2026 para compartir por WhatsApp: letras blancas y amarillas sobre fondo negro con corazones'),
    ('imagen-feliz-dia-de-la-madre-2026-gracias-mama.png',
     'Imagen de Feliz Día de la Madre 2026 con el mensaje "Gracias por todo, mamá" sobre fondo amarillo'),
    ('imagen-feliz-dia-de-la-madre-2026-corazon.png',
     'Imagen de Feliz Día de la Madre 2026 con un gran corazón amarillo y el texto "Feliz día, mamá"'),
    ('imagen-feliz-dia-de-la-madre-2026-flores.png',
     'Imagen de Feliz Día de la Madre 2026 con flores amarillas minimalistas sobre fondo claro, para la mejor mamá del mundo'),
]


def font(role: str, size: int) -> ImageFont.FreeTypeFont:
    """Fuentes de marca del repo; si faltan, una fuente limpia del sistema."""
    rutas = {
        'display': [FONTS_DIR / 'SpaceGrotesk-Bold.ttf', FONTS_DIR / 'Inter-Bold.ttf',
                    Path('C:/Windows/Fonts/segoeuib.ttf'), Path('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf')],
        'medium': [FONTS_DIR / 'SpaceGrotesk-Medium.ttf', FONTS_DIR / 'Inter-Medium.ttf',
                   Path('C:/Windows/Fonts/segoeui.ttf'), Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf')],
        'body': [FONTS_DIR / 'Inter-SemiBold.ttf', FONTS_DIR / 'Inter-Medium.ttf',
                 Path('C:/Windows/Fonts/segoeui.ttf'), Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf')],
    }
    for ruta in rutas[role]:
        # Los SpaceGrotesk-*.ttf del repo son páginas HTML de una descarga
        # fallida (1,6 KB): se valida la firma TrueType/OpenType antes de usar.
        if ruta.exists() and ruta.stat().st_size > 10_000:
            with open(ruta, 'rb') as fh:
                firma = fh.read(4)
            if firma in (bytes([0, 1, 0, 0]), b'OTTO', b'true'):
                return ImageFont.truetype(str(ruta), size * SS)
    return ImageFont.load_default()


def ancho_texto(draw: ImageDraw.ImageDraw, texto: str, f) -> int:
    b = draw.textbbox((0, 0), texto, font=f)
    return b[2] - b[0]


def texto_centrado(draw, y, texto, f, fill, x_centro=None, spacing=0):
    x_centro = W // 2 if x_centro is None else x_centro
    ancho = ancho_texto(draw, texto, f)
    draw.text((x_centro - ancho // 2, y), texto, font=f, fill=fill)
    return ancho


def corazon(draw, cx, cy, r, fill):
    """Corazón paramétrico (curva clásica), centrado en (cx, cy), 'r' ~ mitad del ancho."""
    puntos = []
    for i in range(0, 360, 2):
        t = math.radians(i)
        x = 16 * math.sin(t) ** 3
        y = 13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t)
        puntos.append((cx + x * r / 16, cy - y * r / 16 + r * 0.1))
    draw.polygon(puntos, fill=fill)


def flor(draw, cx, cy, r, petalo, centro, n=6):
    """Flor minimalista: n pétalos circulares + centro."""
    for i in range(n):
        a = 2 * math.pi * i / n
        px, py = cx + math.cos(a) * r, cy + math.sin(a) * r
        draw.ellipse((px - r * 0.62, py - r * 0.62, px + r * 0.62, py + r * 0.62), fill=petalo)
    draw.ellipse((cx - r * 0.5, cy - r * 0.5, cx + r * 0.5, cy + r * 0.5), fill=centro)


def marca(draw, fill_el, fill_gadget, fill_url, y=None):
    """Wordmark "El Gadget" + dominio, al pie (misma jerarquía que el logo del sitio)."""
    y = y if y is not None else W - 150 * SS
    f = font('display', 30)
    el, gadget = 'El', ' Gadget'
    w1, w2 = ancho_texto(draw, el, f), ancho_texto(draw, gadget, f)
    x = (W - w1 - w2) // 2
    draw.text((x, y), el, font=f, fill=fill_el)
    draw.text((x + w1, y), gadget, font=f, fill=fill_gadget)
    texto_centrado(draw, y + 46 * SS, 'elgadget.com.ar · envíos a todo el país', font('body', 18), fill_url)


def lienzo(color):
    img = Image.new('RGB', (W, W), color)
    return img, ImageDraw.Draw(img)


def guardar(img: Image.Image, nombre: str):
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    final = img.resize((SIZE, SIZE), Image.LANCZOS)
    destino = OUT_DIR / nombre
    final.save(destino, 'PNG', optimize=True)
    if destino.stat().st_size > MAX_BYTES:
        # Paleta de 256 colores: los diseños son planos, no se nota y pesa 3-4x menos
        final.quantize(colors=256, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.FLOYDSTEINBERG) \
             .save(destino, 'PNG', optimize=True)
    kb = destino.stat().st_size / 1024
    estado = 'OK' if kb * 1024 <= MAX_BYTES else 'SUPERA 300 KB'
    print(f'  {nombre}: {kb:.0f} KB {estado}')
    return destino


# ── Diseños ──────────────────────────────────────────────────────────────────

def diseno_1_negro_amarillo():
    img, d = lienzo(INK)
    # Corazones amarillos "flotando" en las esquinas (composición asimétrica)
    for cx, cy, r, col in [(150, 190, 70, ACCENT), (960, 150, 42, ACCENT_DEEP), (110, 900, 38, ACCENT_DEEP),
                           (930, 880, 88, ACCENT), (250, 1000, 26, ACCENT), (880, 300, 22, ACCENT)]:
        corazon(d, cx * SS, cy * SS, r * SS, col)
    # Eyebrow
    texto_centrado(d, 318 * SS, '18 DE OCTUBRE · ARGENTINA', font('body', 24), GRAY)
    # Título en 3 líneas
    f_big = font('display', 118)
    texto_centrado(d, 372 * SS, 'Feliz', f_big, WHITE)
    texto_centrado(d, 492 * SS, 'Día de la', f_big, WHITE)
    texto_centrado(d, 612 * SS, 'Madre', f_big, ACCENT)
    # Barra de acento (la misma que usan los h2 del sitio)
    d.rounded_rectangle((W // 2 - 60 * SS, 760 * SS, W // 2 + 60 * SS, 770 * SS), radius=5 * SS, fill=ACCENT)
    texto_centrado(d, 800 * SS, 'Gracias por estar siempre.', font('medium', 34), (215, 213, 208))
    marca(d, WHITE, ACCENT, GRAY)
    return img


def diseno_2_gracias_mama():
    img, d = lienzo(ACCENT)
    # Círculo negro grande detrás del mensaje
    d.ellipse((W // 2 - 400 * SS, 150 * SS, W // 2 + 400 * SS, 950 * SS), fill=INK)
    texto_centrado(d, 330 * SS, 'GRACIAS', font('display', 112), ACCENT)
    texto_centrado(d, 452 * SS, 'por todo,', font('display', 84), WHITE)
    texto_centrado(d, 548 * SS, 'mamá', font('display', 130), WHITE)
    corazon(d, W // 2, 770 * SS, 34 * SS, ACCENT)
    texto_centrado(d, 830 * SS, 'Feliz Día de la Madre 2026', font('body', 26), (215, 213, 208))
    marca(d, INK, INK_SOFT, INK_SOFT, y=W - 110 * SS)
    return img


def diseno_3_corazon():
    img, d = lienzo(INK)
    # Corazón gigante con texto adentro
    corazon(d, W // 2, 450 * SS, 350 * SS, ACCENT)
    corazon(d, W // 2, 450 * SS, 326 * SS, ACCENT_DEEP)
    corazon(d, W // 2, 450 * SS, 312 * SS, ACCENT)
    texto_centrado(d, 345 * SS, 'Feliz día,', font('display', 92), INK)
    texto_centrado(d, 445 * SS, 'mamá', font('display', 144), INK)
    texto_centrado(d, 905 * SS, 'Domingo 18 de octubre · Día de la Madre', font('body', 26), GRAY)
    marca(d, WHITE, ACCENT, GRAY, y=W - 100 * SS)
    return img


def diseno_4_flores():
    img, d = lienzo(CREAM)
    # Ramo de flores en la base
    for cx, cy, r in [(200, 850, 58), (330, 930, 44), (860, 870, 62), (740, 960, 40), (540, 990, 34)]:
        d.line((cx * SS, cy * SS, cx * SS, W), fill=INK, width=8 * SS)
        flor(d, cx * SS, cy * SS, r * SS, ACCENT, INK)
    for cx, cy, r in [(120, 160, 30), (980, 220, 36)]:
        flor(d, cx * SS, cy * SS, r * SS, ACCENT, INK)
    texto_centrado(d, 200 * SS, 'PARA LA MEJOR MAMÁ DEL MUNDO', font('body', 24), (111, 106, 99))
    f_big = font('display', 108)
    texto_centrado(d, 258 * SS, 'Feliz', f_big, INK)
    texto_centrado(d, 368 * SS, 'Día de la', f_big, INK)
    texto_centrado(d, 478 * SS, 'Madre', f_big, INK)
    d.rounded_rectangle((W // 2 - 60 * SS, 620 * SS, W // 2 + 60 * SS, 630 * SS), radius=5 * SS, fill=ACCENT)
    texto_centrado(d, 650 * SS, '18 de octubre de 2026', font('medium', 34), (111, 106, 99))
    marca(d, INK, ACCENT_DEEP, (111, 106, 99), y=W - 380 * SS)
    return img


DISENOS = [diseno_1_negro_amarillo, diseno_2_gracias_mama, diseno_3_corazon, diseno_4_flores]


def main() -> int:
    print(f'Generando {len(DISENOS)} imágenes en {OUT_DIR}')
    for (nombre, _alt), fn in zip(IMAGENES, DISENOS):
        guardar(fn(), nombre)
    return 0


if __name__ == '__main__':
    sys.exit(main())
