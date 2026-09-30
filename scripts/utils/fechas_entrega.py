# -*- coding: utf-8 -*-
"""Hasta cuándo se puede comprar para que un regalo llegue a tiempo.

La objeción número uno de quien compra un regalo no es el precio: es "¿llega?".
Este módulo calcula la respuesta con los plazos REALES del tarifario de
Droppers (data/envios/zonas_envio.json) en vez de una fecha escrita a mano que
se pudre al año siguiente.

Cómo se cuenta, para una entrega que tiene que estar el día del evento:
  compra → +1 día hábil de despacho → +N días hábiles de tránsito → entrega.
Se usa el extremo PESIMISTA del rango de tránsito (si el correo dice "2 a 5
días", se cuentan 5) porque prometer de menos y cumplir es barato, y prometer
de más y fallar en un regalo de fecha no se arregla con un reembolso.

Sábados, domingos y feriados nacionales no cuentan, ni para despachar ni para
entregar. Por eso importa la lista de FERIADOS: el Día de la Madre 2026 cae el
domingo 18 de octubre y el lunes 12 es feriado, así que ese solo día corre
todos los límites 24 horas hacia atrás.
"""

from datetime import date, timedelta

# Feriados nacionales de Argentina con día fijo o ya trasladado. Hay que
# extenderla cada año (el calendario oficial sale por decreto en el año
# anterior). Si falta un feriado, el cálculo queda OPTIMISTA: promete una
# fecha límite más tarde de lo que conviene.
FERIADOS = {
    # 2026
    date(2026, 1, 1), date(2026, 2, 16), date(2026, 2, 17), date(2026, 3, 24),
    date(2026, 4, 2), date(2026, 4, 3), date(2026, 5, 1), date(2026, 5, 25),
    date(2026, 6, 15), date(2026, 6, 20), date(2026, 7, 9), date(2026, 8, 17),
    date(2026, 10, 12), date(2026, 11, 23), date(2026, 12, 8), date(2026, 12, 25),
    # 2027
    date(2027, 1, 1), date(2027, 2, 8), date(2027, 2, 9), date(2027, 3, 24),
    date(2027, 4, 2), date(2027, 5, 1), date(2027, 5, 25), date(2027, 6, 21),
    date(2027, 7, 9), date(2027, 8, 16), date(2027, 10, 11), date(2027, 11, 22),
    date(2027, 12, 8), date(2027, 12, 25),
}

DIAS = ['lunes', 'martes', 'miércoles', 'jueves', 'viernes', 'sábado', 'domingo']
MESES = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio',
         'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre']

DIAS_DESPACHO = 1   # lo que tarda el proveedor en poner el paquete en la calle


def es_habil(d: date) -> bool:
    return d.weekday() < 5 and d not in FERIADOS


def habil_anterior(d: date) -> date:
    """El primer día hábil en d o antes."""
    while not es_habil(d):
        d -= timedelta(days=1)
    return d


def restar_habiles(d: date, n: int) -> date:
    """n días hábiles antes de d (d no se cuenta)."""
    while n > 0:
        d -= timedelta(days=1)
        if es_habil(d):
            n -= 1
    return d


def limite_de_compra(evento: date, dias_transito: int,
                     dias_despacho: int = DIAS_DESPACHO) -> date:
    """Último día para comprar y que llegue ANTES del evento.

    Se compra el día P; el proveedor despacha al día hábil siguiente; el
    paquete tarda hasta `dias_transito` días hábiles más. La entrega tiene que
    caer como muy tarde el último día hábil previo al evento, porque nadie
    reparte un domingo. De ahí: P = última_entrega − tránsito − despacho.
    """
    ultima_entrega = habil_anterior(evento - timedelta(days=1))
    return restar_habiles(ultima_entrega, dias_transito + dias_despacho)


def fecha_larga(d: date) -> str:
    """'martes 13 de octubre'."""
    return f'{DIAS[d.weekday()]} {d.day} de {MESES[d.month - 1]}'


def limites_por_modalidad(evento: date, zonas: dict) -> list:
    """Un límite por modalidad de envío (moto / correo), desde el tarifario.

    Devuelve [(etiqueta_de_zonas, fecha_límite, plazo_en_texto)] ordenado de la
    fecha más temprana a la más tardía: primero el interior, que es el que
    tiene que comprar antes.
    """
    from utils.envios import parsear_plazo

    por_modalidad = {}
    for zid, z in (zonas.get('zonas') or {}).items():
        rango = parsear_plazo(z.get('plazo') or '')
        if not rango:
            continue
        transito = rango[1]      # el extremo pesimista del rango, en días hábiles
        mod = z.get('modalidad') or 'correo'
        actual = por_modalidad.get(mod)
        if actual is None or transito > actual[0]:
            por_modalidad[mod] = (transito, z.get('plazo') or '', [])
        por_modalidad[mod][2].append(z.get('nombre') or zid)

    salida = []
    for mod, (transito, plazo, nombres) in por_modalidad.items():
        etiqueta = 'CABA y GBA' if mod == 'moto' else 'resto del país'
        salida.append((etiqueta, limite_de_compra(evento, transito), plazo))
    return sorted(salida, key=lambda x: x[1])
