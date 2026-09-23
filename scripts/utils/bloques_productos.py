# -*- coding: utf-8 -*-
"""Selección de productos REALES para bloques estáticos del sitio.

Lo usa el generador (12_generar_paginas_producto.py) para escribir, en cada
corrida, HTML con <a href> a fichas existentes en:

- la home (bloque "Destacados"),
- el post del Día de la Madre (regalos por presupuesto),
- el post de Cyber Monday / Black Friday (ofertas con stock).

Acá vive SOLO la elección (qué productos, en qué orden, por qué). El render
HTML queda en el generador, que es quien conoce slugs, miniaturas y cards.

Reglas comunes a todos los bloques:
- Solo productos con stock > 0, precio_venta > 0, imagen y slug (url_amigable).
- Una sola variante por familia de SKU (S6058A/B/C es un solo gorro) y como
  mucho dos productos del mismo "tipo" (dos bandoleras, no cinco).
- Diversidad de categorías (tope por categoría), para que el bloque no sea
  diez carteras.
- Rotación determinista: la semilla es la fecha (o la semana ISO), así el
  bloque cambia solo con el tiempo pero es reproducible corrida a corrida.

También define el calendario de FECHAS COMERCIALES (Día de la Madre, Cyber
Monday / Black Friday, Navidad, Día del Amigo) con la ventana en la que la
home debe linkear al post correspondiente.
"""

import random
import re
import unicodedata
from datetime import date, timedelta

# ── Afinidad "regalo" por categoría (mayor = más afín). Las que no figuran
# valen 0 y solo entran si el bloque no se llena con las demás.
PESO_CATEGORIA_REGALO = {
    'Accesorios de Moda': 3,
    'Deco': 3,
    'Home': 2,
    'Bazar y Cocina': 2,
    'Estética y Belleza': 2,
    'Nuevos Ingresos': 1,
    'OFERTAS': 1,
    'Verano': 1,
}
# Solo si faltan candidatos (el post ya cubre "mamá de la mascota" con un
# link a la categoría; en el bloque principal no hace falta).
CATEGORIAS_RESPALDO_REGALO = ('Accesorios para Mascotas', 'Artículos Infantiles')

# Lo que NO es un regalo para mamá aunque la categoría sea afín
# (se evalúa sobre el nombre sin acentos, en minúsculas).
EXCLUIR_REGALO = re.compile(
    r'infantil|\bnin[oa]s?\b|\bbebe\b|\bbody\b|\bkids?\b|escolar|cartuchera|'
    r'mascota|\bperro|\bgato|isabelino|destapaca|escobilla|rejilla|desague|'
    r'membrana|remolque|perilla|atrapa ?pelos|borde seguridad|vela cumple|'
    r'dilatador|ronquid|corrector de postura|\bfaja\b|sticker|resaltador|'
    r'\bbride\b|\bmedias\b|guantes|microfono|espejos 360|\bbici\b|monopat|'
    r'tapones|strips|depilaci|inflable|flotador|lava copas|sacapelusas|'
    r'globos|protector(?:es)? de|ninos|para chicos|soporte ducha|autoadhesiv|'
    r'escurridor|escurre'
)
# Fuera de temporada: no se regala un gorro de lana en octubre ni una lámpara
# de Navidad en septiembre. Se evalúa por el mes de la corrida.
FUERA_DE_TEMPORADA = {
    # meses en los que se EXCLUYE el patrón
    'invierno': ((9, 10, 11, 12, 1, 2, 3), re.compile(r'invierno|abrigo|beanie|\blana\b|bufanda|poncho|piluso|guantes|manton')),
    'verano':   ((4, 5, 6, 7, 8), re.compile(r'verano|pileta|bikini|\bmalla|playa|inflable')),
    'navidad':  ((1, 2, 3, 4, 5, 6, 7, 8, 9, 10), re.compile(r'navid|reyes')),
}
PRECIO_MINIMO_REGALO = 8000

# Señales de "esto sí se regala": suman puntaje.
BOOST_REGALO = re.compile(
    r'mujer|regalo|\bdeco\b|lampara|velador|bandolera|cartera|mochila|'
    r'termic|organizador|maceta|espejo|poncho|bufanda|blusa|portacosm|'
    r'piluso|gorro|tumbler|\bvaso|botella|jabonera|difusor|luces|\bluz\b|'
    r'crochet|raffia|elegante|diseno'
)
# Para "Destacados" de la home: solo se saca lo que no luce en una vidriera.
EXCLUIR_DESTACADO = re.compile(
    r'destapaca|escobilla|rejilla|desague|membrana|remolque|perilla|'
    r'atrapa ?pelos|borde seguridad|vela cumple|dilatador|ronquid|isabelino|'
    r'\bfaja\b|tapones|strips|depilaci|lava copas|sacapelusas|\bmedias\b|'
    r'sticker|espejos 360|resaltador'
)

STOPWORDS = {'de', 'del', 'la', 'el', 'los', 'las', 'para', 'con', 'y', 'o',
             'en', 'a', 'un', 'una', 'por', 'sin', 'tu', 'tus', 'mujer', 'x',
             'pack', 'set', 'kit', 'mini', 'gigante', 'grande', 'mediana',
             # adjetivos genéricos: no distinguen un tipo de artículo de otro
             'decorativa', 'decorativo', 'moderna', 'moderno', 'doble', 'clasico',
             'clasica', 'premium', 'urbana', 'urbano', 'elegante', 'original',
             'versatil', 'divertida', 'divertido', 'ideal', 'chic', 'sport'}
# Variantes de escritura que son el mismo tipo de artículo.
SINONIMOS_TIPO = {'luces': 'luz', 'lamparas': 'lampara', 'bolso': 'bandolera',
                  'cartera': 'bandolera', 'malla': 'bikini', 'traje': 'bikini',
                  'termo': 'botella', 'vaso': 'botella', 'tumbler': 'botella'}


def normalizar(s: str) -> str:
    """Minúsculas, sin acentos, espacios simples."""
    s = unicodedata.normalize('NFKD', s or '')
    s = ''.join(c for c in s if not unicodedata.combining(c))
    return re.sub(r'\s+', ' ', s.lower()).strip()


def familia_sku(sku: str) -> str:
    """Raíz del SKU sin el sufijo de variante (color/talle).

    S6058A -> S6058 · M2028-001B -> M2028-001 · DL1172-5-BE -> DL1172-5 ·
    WH7167-59BL -> WH7167-59 · G-TERMOTAPAMADE -> (igual).
    """
    return re.sub(r'(?<=\d)[A-Z]$|-[A-Z]{2,3}$', '', (sku or '').upper())


def tipo_producto(nombre: str) -> str:
    """Clave gruesa de "tipo" (dos primeras palabras significativas, en
    singular aproximado) para no repetir cinco veces el mismo artículo."""
    palabras = [w for w in re.findall(r'[a-z]+', normalizar(nombre)) if w not in STOPWORDS and len(w) > 2]
    palabras = [SINONIMOS_TIPO.get(w, w) for w in palabras]
    palabras = [re.sub(r'(es|s)$', '', w) if len(w) > 4 else w for w in palabras]
    # orden alfabético: "gorro piluso" y "piluso gorro" son el mismo tipo
    return ' '.join(sorted(palabras[:2]))


def _semilla(hoy: date, por_semana: bool) -> str:
    if por_semana:
        iso = hoy.isocalendar()
        return f'{iso[0]}-W{iso[1]}'
    return hoy.isoformat()


def fuera_de_temporada(nombre: str, hoy: date) -> bool:
    nombre_n = normalizar(nombre)
    return any(hoy.month in meses and rx.search(nombre_n)
               for meses, rx in FUERA_DE_TEMPORADA.values())


def _elegibles(productos: list, slug_map: dict, hoy: date = None) -> list:
    hoy = hoy or date.today()
    return [p for p in productos
            if (p.get('stock') or 0) > 0 and (p.get('precio_venta') or 0) > 0
            and p.get('imagen_principal') and slug_map.get(p['sku'])
            and not fuera_de_temporada(p.get('nombre', ''), hoy)]


def _precio_efectivo(p: dict) -> float:
    oferta = p.get('precio_oferta')
    if oferta is not None and 0 < oferta < (p.get('precio_venta') or 0):
        return float(oferta)
    return float(p.get('precio_venta') or 0)


def _puntuar(productos: list, pesos_cat: dict, boost: re.Pattern, jitter: int, rnd: random.Random,
             respaldo: tuple = ()) -> list:
    """Devuelve [(puntaje, producto)] ordenado de mayor a menor."""
    out = []
    for p in productos:
        cat = p.get('categoria') or ''
        peso = pesos_cat.get(cat, 0)
        if cat in respaldo:
            peso = -1  # al final de todo: solo si no hay nada mejor
        nombre_n = normalizar(p.get('nombre', ''))
        puntaje = peso * 10
        puntaje += 3 * min(len(boost.findall(nombre_n)), 3) if boost else 0
        if _precio_efectivo(p) < (p.get('precio_venta') or 0):
            puntaje += 8  # en oferta hoy: se destaca
        puntaje += rnd.randint(0, jitter)
        out.append((puntaje, p))
    out.sort(key=lambda t: (-t[0], t[1]['sku']))
    return out


def _tomar(ranking: list, n: int, max_por_cat: int, max_por_tipo: int = 2,
           familias_usadas: set = None, tipos_usados: dict = None,
           cats_usadas: dict = None, max_por_cat_local: int = None) -> list:
    """Recorre el ranking respetando los topes de familia / tipo / categoría.

    Los contadores compartidos (familias/tipos/cats) permiten encadenar varias
    llamadas (un tramo de precio tras otro) sin repetir producto; el tope
    local de categoría evita que un tramo sea todo carteras."""
    familias_usadas = familias_usadas if familias_usadas is not None else set()
    tipos_usados = tipos_usados if tipos_usados is not None else {}
    cats_usadas = cats_usadas if cats_usadas is not None else {}
    cats_local = {}
    elegidos = []
    for _, p in ranking:
        if len(elegidos) >= n:
            break
        fam = familia_sku(p['sku'])
        tipo = tipo_producto(p.get('nombre', ''))
        cat = p.get('categoria') or ''
        if fam in familias_usadas or tipos_usados.get(tipo, 0) >= max_por_tipo \
                or cats_usadas.get(cat, 0) >= max_por_cat \
                or (max_por_cat_local and cats_local.get(cat, 0) >= max_por_cat_local):
            continue
        familias_usadas.add(fam)
        tipos_usados[tipo] = tipos_usados.get(tipo, 0) + 1
        cats_usadas[cat] = cats_usadas.get(cat, 0) + 1
        cats_local[cat] = cats_local.get(cat, 0) + 1
        elegidos.append(p)
    return elegidos


# ── Bloques ───────────────────────────────────────────────────────────────────

TRAMOS_PRESUPUESTO = [
    # (tope inferior exclusivo, tope superior inclusivo, título)
    (0, 15000, 'Hasta $15.000'),
    (15000, 40000, 'De $15.000 a $40.000'),
    (40000, None, 'Más de $40.000'),
]


def seleccionar_regalos_por_presupuesto(productos: list, slug_map: dict, hoy: date = None,
                                        n_total: int = 12, tramos: list = None) -> list:
    """Regalos reales agrupados por presupuesto: [(título_tramo, [productos])].

    Reparte n_total en partes iguales entre los tramos; si un tramo no llega
    (hoy el catálogo tiene pocos productos de hasta $15.000), los lugares que
    sobran se completan con los otros tramos. Categorías afines a regalo
    primero (PESO_CATEGORIA_REGALO); infantiles/mascotas solo de respaldo.
    """
    hoy = hoy or date.today()
    tramos = tramos or TRAMOS_PRESUPUESTO
    rnd = random.Random('regalos|' + _semilla(hoy, por_semana=False))
    base = [p for p in _elegibles(productos, slug_map, hoy)
            if not EXCLUIR_REGALO.search(normalizar(p.get('nombre', '')))
            and _precio_efectivo(p) >= PRECIO_MINIMO_REGALO]
    ranking = _puntuar(base, PESO_CATEGORIA_REGALO, BOOST_REGALO, jitter=6, rnd=rnd,
                       respaldo=CATEGORIAS_RESPALDO_REGALO)

    def en_tramo(p, lo, hi):
        precio = _precio_efectivo(p)
        return precio > lo and (hi is None or precio <= hi)

    por_tramo = [[t for t in ranking if en_tramo(t[1], lo, hi)] for lo, hi, _ in tramos]
    # Candidatos "fuertes": categorías afines (peso >= 1). Los de peso 0
    # (fitness, electrónica, baño) o de respaldo solo entran en la última pasada.
    fuertes = [[t for t in rk if PESO_CATEGORIA_REGALO.get(t[1].get('categoria') or '', 0) >= 1]
               for rk in por_tramo]
    cupo = [n_total // len(tramos)] * len(tramos)
    for i in range(n_total - sum(cupo)):
        cupo[1 % len(tramos) if len(tramos) > 1 else 0] += 1

    familias, tipos, cats = set(), {}, {}
    elegidos = [[] for _ in tramos]
    max_por_cat = max(4, n_total // 2)       # global: ninguna categoría es la mitad del bloque
    local = max(2, cupo[0] // 2)             # por tramo: como mucho la mitad de una categoría
    # 1ª pasada: cupo base por tramo, solo candidatos fuertes (un producto por tipo en todo el bloque)
    for i, rk in enumerate(fuertes):
        elegidos[i] = _tomar(rk, cupo[i], max_por_cat, 1, familias, tipos, cats, local)
    # 2ª pasada: lo que faltó se reparte entre tramos con candidatos fuertes de sobra
    # (medio primero, después alto, después bajo): mejor 6 regalos buenos de $15-40k
    # que rellenar "hasta $15.000" con moldes de helado.
    faltan = n_total - sum(len(e) for e in elegidos)
    for i in (1, 2, 0)[:len(tramos)]:
        if faltan <= 0:
            break
        extra = _tomar(fuertes[i], faltan, max_por_cat + 1, 1, familias, tipos, cats)
        elegidos[i] += extra
        faltan -= len(extra)
    # 3ª pasada (solo si el catálogo está muy flaco): cualquier candidato, cualquier tramo
    for i in (1, 2, 0)[:len(tramos)]:
        if faltan <= 0:
            break
        extra = _tomar(por_tramo[i], faltan, max_por_cat + 2, 1, familias, tipos, cats)
        elegidos[i] += extra
        faltan -= len(extra)
    return [(tramos[i][2], sorted(elegidos[i], key=_precio_efectivo)) for i in range(len(tramos)) if elegidos[i]]


def seleccionar_destacados(productos: list, slug_map: dict, hoy: date = None, n: int = 10) -> list:
    """Vidriera de la home: variedad de categorías, ofertas del día primero,
    rotación SEMANAL (así el lastmod de la home solo cambia cuando cambió
    algo de verdad: stock, precio o semana)."""
    hoy = hoy or date.today()
    rnd = random.Random('destacados|' + _semilla(hoy, por_semana=True))
    base = [p for p in _elegibles(productos, slug_map, hoy)
            if not EXCLUIR_DESTACADO.search(normalizar(p.get('nombre', '')))
            and (p.get('precio_venta') or 0) >= 5000]
    pesos = {'Accesorios de Moda': 2, 'Deco': 2, 'Bazar y Cocina': 2, 'Home': 2,
             'Verano': 1, 'OFERTAS': 1, 'Nuevos Ingresos': 2, 'Artículos Infantiles': 1,
             'Accesorios para Mascotas': 1, 'Estética y Belleza': 1}
    ranking = _puntuar(base, pesos, BOOST_REGALO, jitter=14, rnd=rnd)
    return _tomar(ranking, n, max_por_cat=2, max_por_tipo=1)


def seleccionar_ofertas(productos: list, slug_map: dict, hoy: date = None, n: int = 10) -> tuple:
    """Bloque de ofertas para el post de Cyber Monday / Black Friday.

    1) Productos con precio_oferta vigente (campaña automática del día).
    2) Si no hay campaña (o alcanza a menos de 4 productos): destacados
       generales, donde la categoría OFERTAS (ofertas rotativas) ya suma.
    Devuelve (productos, 'campana' | 'destacados').
    """
    hoy = hoy or date.today()
    rnd = random.Random('ofertas|' + _semilla(hoy, por_semana=False))
    base = [p for p in _elegibles(productos, slug_map, hoy)
            if not EXCLUIR_DESTACADO.search(normalizar(p.get('nombre', '')))]
    con_campana = [p for p in base if _precio_efectivo(p) < (p.get('precio_venta') or 0)]
    if len(con_campana) >= 4:
        ranking = _puntuar(con_campana, PESO_CATEGORIA_REGALO, BOOST_REGALO, jitter=6, rnd=rnd)
        return _tomar(ranking, n, max_por_cat=4, max_por_tipo=2), 'campana'
    return seleccionar_destacados(productos, slug_map, hoy, n), 'destacados'


# ── Fechas comerciales ────────────────────────────────────────────────────────

def _n_esimo_dia(anio: int, mes: int, weekday: int, n: int) -> date:
    """n-ésimo weekday (0=lunes … 6=domingo) del mes."""
    d = date(anio, mes, 1)
    d += timedelta(days=(weekday - d.weekday()) % 7)
    return d + timedelta(weeks=n - 1)


def dia_de_la_madre(anio: int) -> date:
    """Argentina: tercer domingo de octubre."""
    return _n_esimo_dia(anio, 10, 6, 3)


def cyber_monday(anio: int) -> date:
    """CACE: arranca el primer lunes de noviembre (2026: 2/11)."""
    return _n_esimo_dia(anio, 11, 0, 1)


def black_friday(anio: int) -> date:
    """Viernes posterior al cuarto jueves de noviembre (2026: 27/11)."""
    return _n_esimo_dia(anio, 11, 3, 4) + timedelta(days=1)


def fechas_comerciales_vigentes(hoy: date = None) -> list:
    """Fechas comerciales cuya ventana incluye a `hoy`, en orden de prioridad.

    Cada una: {'id', 'label', 'href', 'sub'}. La home linkea a todas las
    vigentes (arriba del catálogo y en el nav). Ventanas:
    - Día de la Madre: 4 semanas antes → el domingo mismo (la curva de búsqueda
      arranca en septiembre; en 2026 el post ya tenía impresiones el 21/9).
    - Cyber Monday / Black Friday: 5 de octubre → 30 de noviembre.
    - Navidad y Reyes: 1 de diciembre → 6 de enero.
    - Día del Amigo: 1 → 20 de julio.
    """
    hoy = hoy or date.today()
    a = hoy.year
    madre = dia_de_la_madre(a)
    cm, bf = cyber_monday(a), black_friday(a)
    ventanas = [
        ('dia-de-la-madre', madre - timedelta(days=28), madre, {
            'label': '🎁 Regalos para el Día de la Madre',
            'href': '/blog/regalos-dia-de-la-madre/',
            'sub': f'Es el domingo {madre.day} de octubre: ideas con stock, por presupuesto, con envío a todo el país',
        }),
        ('cyber-monday-black-friday', date(a, 10, 5), date(a, 11, 30), {
            'label': '🛒 Cyber Monday y Black Friday',
            'href': '/blog/hot-sale-cyber-monday-black-friday/',
            'sub': f'Cyber Monday {cm.day} al {(cm + timedelta(days=2)).day}/11 · Black Friday {bf.day}/11: fechas y ofertas reales',
        }),
        ('navidad', date(a, 12, 1), date(a + 1, 1, 6), {
            'label': '🎄 Regalos de Navidad y Reyes',
            'href': '/blog/regalos-de-navidad/',
            'sub': 'Ideas por edad y presupuesto, con envío a todo el país',
        }),
        ('navidad', date(a - 1, 12, 1), date(a, 1, 6), {  # primeros días de enero
            'label': '🎄 Regalos de Navidad y Reyes',
            'href': '/blog/regalos-de-navidad/',
            'sub': 'Ideas por edad y presupuesto, con envío a todo el país',
        }),
        ('dia-del-amigo', date(a, 7, 1), date(a, 7, 20), {
            'label': '🧉 Día del Amigo: regalos e imágenes',
            'href': '/blog/dia-del-amigo/',
            'sub': 'Es el 20 de julio: ideas, imágenes para saludar y amigo invisible gratis',
        }),
    ]
    vistas, out = set(), []
    for fid, ini, fin, datos in ventanas:
        if ini <= hoy <= fin and fid not in vistas:
            vistas.add(fid)
            out.append({'id': fid, **datos})
    return out
