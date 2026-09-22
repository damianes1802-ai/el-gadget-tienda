#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Datos de envío compartidos: lee data/envios/zonas_envio.json (la MISMA fuente
que usa la API en el checkout) y la expone en una forma cómoda para publicar.

Lo usan:
- 12_generar_paginas_producto.py: JSON-LD `shippingDetails` de cada ficha y el
  bloque visible "Envío / cambios / pago" de la ficha.
- generar_pagina_envios.py: la página pública /envios (tabla de zonas + FAQ).

Regla: cualquier número de envío que se publique hacia afuera (costo, plazo)
sale de acá, nunca hardcodeado en una plantilla. Si cambia el tarifario, se
edita el JSON y se regenera; ningún HTML tiene que tocarse a mano.
"""

import json
import re
from typing import Optional, Tuple

from .config import Config

ZONAS_FILE = Config.DATA_DIR / 'envios' / 'zonas_envio.json'

# Orden de publicación (de más cerca a más lejos). Zonas nuevas que no estén
# acá se agregan al final, en el orden del JSON.
ORDEN_ZONAS = ['CABA', 'GBA1', 'GBA2', 'GBA3', 'BSAS', 'RESTO_PAIS']

# Nombres para mostrar al cliente (el JSON trae "GBA 1 (moto)", poco claro).
NOMBRES_PUBLICOS = {
    'CABA': 'CABA (Capital Federal)',
    'GBA1': 'GBA zona 1 (primer cordón)',
    'GBA2': 'GBA zona 2 (segundo cordón)',
    'GBA3': 'GBA zona 3 (tercer cordón)',
    'BSAS': 'Resto de la provincia de Buenos Aires',
    'RESTO_PAIS': 'Resto del país',
}

# Versión corta para meta descriptions y líneas de una sola frase.
NOMBRES_CORTOS = {'CABA': 'CABA', 'GBA1': 'GBA 1', 'GBA2': 'GBA 2', 'GBA3': 'GBA 3',
                  'BSAS': 'provincia de Buenos Aires', 'RESTO_PAIS': 'resto del país'}

MODALIDAD_PUBLICA = {'moto': 'Moto (mensajería)', 'correo': 'Correo'}


def cargar_zonas() -> dict:
    """Devuelve el JSON completo del tarifario (dict)."""
    with open(ZONAS_FILE, encoding='utf-8') as f:
        return json.load(f)


def parsear_plazo(texto: str) -> Optional[Tuple[int, int]]:
    """Convierte el plazo textual del JSON a (min_dias_habiles, max_dias_habiles).

    "Hasta 48 horas habiles desde el despacho" -> (1, 2)
    "2 a 5 dias habiles, segun distancia"      -> (2, 5)
    Devuelve None si no reconoce el formato (el que llama omite el dato en vez
    de inventarlo).
    """
    if not texto:
        return None
    t = texto.lower()
    m = re.search(r'(\d+)\s*a\s*(\d+)\s*d[ií]as', t)
    if m:
        return int(m.group(1)), int(m.group(2))
    m = re.search(r'hasta\s*(\d+)\s*horas', t)
    if m:
        horas = int(m.group(1))
        return 1, max(1, -(-horas // 24))  # techo de horas/24
    m = re.search(r'(\d+)\s*d[ií]as', t)
    if m:
        return int(m.group(1)), int(m.group(1))
    return None


def formatear_pesos(valor) -> str:
    """2899 -> '$2.899' (formato argentino, sin decimales)."""
    return '$' + f"{int(round(float(valor))):,}".replace(',', '.')


def zonas_publicables(data: Optional[dict] = None) -> list:
    """Lista de zonas en orden de publicación, cada una como dict plano:
    codigo, nombre, nombre_json, costo, costo_fmt, modalidad, modalidad_fmt,
    plazo (texto), dias (tupla o None), partidos (lista, solo GBA*)."""
    data = data or cargar_zonas()
    zonas = data.get('zonas', {})
    codigos = [c for c in ORDEN_ZONAS if c in zonas] + [c for c in zonas if c not in ORDEN_ZONAS]
    partidos_por_zona = {}
    for partido, codigo in (data.get('partidos_buenos_aires') or {}).items():
        partidos_por_zona.setdefault(codigo, []).append(partido)

    bonif = envio_bonificado(data)
    zonas_bonif = set(bonif['zonas']) if bonif else set()

    salida = []
    for codigo in codigos:
        z = zonas[codigo]
        modalidad = (z.get('modalidad') or '').lower()
        salida.append({
            'codigo': codigo,
            'nombre': NOMBRES_PUBLICOS.get(codigo, z.get('nombre', codigo)),
            'nombre_json': z.get('nombre', codigo),
            'costo': float(z.get('costo') or 0),
            'costo_fmt': formatear_pesos(z.get('costo') or 0),
            'modalidad': modalidad,
            'modalidad_fmt': MODALIDAD_PUBLICA.get(modalidad, modalidad.capitalize()),
            'plazo': z.get('plazo', ''),
            'dias': parsear_plazo(z.get('plazo', '')),
            'partidos': sorted(partidos_por_zona.get(codigo, [])),
            'bonificado': codigo in zonas_bonif,
        })
    return salida


def envio_bonificado(data: Optional[dict] = None) -> Optional[dict]:
    """Regla de envío bonificado del JSON (clave `envio_bonificado`: zonas + minimo).
    Devuelve {'zonas': [códigos], 'minimo': float, 'minimo_fmt': '$40.000',
    'nombres': [nombres públicos]} o None si no hay regla / está vacía.
    El mínimo se compara contra el TOTAL DE PRODUCTOS YA CON DESCUENTOS (así lo
    aplica el checkout, que es quien resuelve el envío bonificado)."""
    data = data or cargar_zonas()
    regla = data.get('envio_bonificado') or {}
    zonas = [z for z in (regla.get('zonas') or []) if z in (data.get('zonas') or {})]
    try:
        minimo = float(regla.get('minimo') or 0)
    except (TypeError, ValueError):
        minimo = 0
    if not zonas or minimo <= 0:
        return None
    return {
        'zonas': zonas,
        'minimo': minimo,
        'minimo_fmt': formatear_pesos(minimo),
        'nombres': [NOMBRES_PUBLICOS.get(z, data['zonas'][z].get('nombre', z)) for z in zonas],
        'nombres_cortos': [NOMBRES_CORTOS.get(z, z) for z in zonas],
    }


def resumen_envios(data: Optional[dict] = None) -> dict:
    """Números clave para textos y JSON-LD, derivados del tarifario real:
    caba / resto (dicts de zona), costo_min, costo_max, dias_moto, dias_correo,
    fecha_actualizacion, zonas (lista completa)."""
    data = data or cargar_zonas()
    zonas = zonas_publicables(data)
    por_codigo = {z['codigo']: z for z in zonas}
    motos = [z for z in zonas if z['modalidad'] == 'moto']
    correos = [z for z in zonas if z['modalidad'] == 'correo']

    def _rango(lista):
        rangos = [z['dias'] for z in lista if z['dias']]
        if not rangos:
            return None
        return min(r[0] for r in rangos), max(r[1] for r in rangos)

    return {
        'zonas': zonas,
        'caba': por_codigo.get(data.get('zona_caba', 'CABA')),
        'bsas': por_codigo.get(data.get('zona_default_buenos_aires', 'BSAS')),
        'resto': por_codigo.get(data.get('zona_default_resto_pais', 'RESTO_PAIS')),
        'costo_min': min(z['costo'] for z in zonas) if zonas else 0,
        'costo_max': max(z['costo'] for z in zonas) if zonas else 0,
        'dias_moto': _rango(motos),
        'dias_correo': _rango(correos),
        'fecha_actualizacion': data.get('fecha_actualizacion', ''),
        'bonificado': envio_bonificado(data),
    }


def _unir_nombres(nombres: list) -> str:
    """['CABA', 'GBA zona 1'] -> 'CABA y GBA zona 1'; tres o más con comas."""
    if not nombres:
        return ''
    if len(nombres) == 1:
        return nombres[0]
    return ', '.join(nombres[:-1]) + ' y ' + nombres[-1]


def _dias_habiles_txt(rango) -> str:
    if not rango:
        return ''
    lo, hi = rango
    if lo == hi:
        return f"{hi} día{'s' if hi != 1 else ''} hábil{'es' if hi != 1 else ''}"
    return f"{lo} a {hi} días hábiles"


def frases_envio(res: Optional[dict] = None) -> dict:
    """Frases listas para usar en HTML (sin escapar), coherentes entre páginas."""
    res = res or resumen_envios()
    caba, resto = res['caba'], res['resto']
    moto_hi = res['dias_moto'][1] if res['dias_moto'] else None
    moto_txt = f"hasta {moto_hi * 24} h hábiles" if moto_hi else ''
    bonif = res.get('bonificado')
    # "Envío gratis en CABA y GBA zona 1 (primer cordón) con compras desde $40.000."
    bonif_txt = (
        f"Envío gratis en {_unir_nombres(bonif['nombres'])} con compras desde {bonif['minimo_fmt']}."
        if bonif else ''
    )
    return {
        # "Envío en moto a CABA y GBA (hasta 48 h hábiles desde el despacho, desde $2.899) y por correo al resto del país (2 a 5 días hábiles)."
        'resumen': (
            f"Envío en moto a CABA y GBA ({moto_txt} desde el despacho, desde {caba['costo_fmt']}) "
            f"y por correo al resto del país ({_dias_habiles_txt(res['dias_correo'])})."
        ) if caba and resto else '',
        'moto': moto_txt,
        'correo': _dias_habiles_txt(res['dias_correo']),
        'costo_caba': caba['costo_fmt'] if caba else '',
        'costo_resto': resto['costo_fmt'] if resto else '',
        'costo_min': formatear_pesos(res['costo_min']),
        'costo_max': formatear_pesos(res['costo_max']),
        'bonificado': bonif_txt,
        # "Envío gratis en CABA y GBA 1 desde $40.000."
        'bonificado_corto': (f"Envío gratis en {_unir_nombres(bonif['nombres_cortos'])} desde {bonif['minimo_fmt']}."
                             if bonif else ''),
        'bonificado_zonas': _unir_nombres(bonif['nombres']) if bonif else '',
        'bonificado_zonas_corto': _unir_nombres(bonif['nombres_cortos']) if bonif else '',
        'bonificado_minimo': bonif['minimo_fmt'] if bonif else '',
    }


def shipping_details_jsonld(res: Optional[dict] = None, precio_producto: Optional[float] = None) -> list:
    """`Offer.shippingDetails` (schema.org OfferShippingDetails) para el JSON-LD
    de cada ficha. Se publican DOS entradas honestas:
    - "resto del país" como tarifa general para AR (es la MÁS CARA del tarifario,
      así ningún comprador paga más de lo declarado), y
    - CABA (ISO 3166-2: AR-C -> addressRegion "C") con su tarifa de moto.
    Los partidos del GBA no se pueden expresar con DefinedRegion (Google solo
    acepta región/código postal), así que no se declaran para no mentir.
    `transitTime` va en días hábiles desde el despacho; no hay `handlingTime`
    porque el sitio no promete un plazo de despacho concreto.

    Envío bonificado (clave `envio_bonificado` del JSON): Google solo acepta
    `shippingRate` como MonetaryAmount (`value` o `maxValue`), sin umbral. Para
    una zona bonificada: si `precio_producto` (lo que paga el cliente por ESTE
    producto) ya alcanza el mínimo, la tarifa es `value: 0` (comprándolo solo el
    envío sale gratis); si no, se declara el rango real `minValue: 0` /
    `maxValue: <tarifa>` porque depende del total del carrito."""
    res = res or resumen_envios()
    bonif = res.get('bonificado')

    def _tarifa(zona):
        if bonif and zona['codigo'] in bonif['zonas']:
            if precio_producto is not None and float(precio_producto) >= bonif['minimo']:
                return {"@type": "MonetaryAmount", "value": "0.00", "currency": "ARS"}
            return {"@type": "MonetaryAmount", "minValue": "0.00", "maxValue": f"{zona['costo']:.2f}",
                    "currency": "ARS"}
        return {"@type": "MonetaryAmount", "value": f"{zona['costo']:.2f}", "currency": "ARS"}

    def _entrada(zona, region=None):
        if not zona:
            return None
        destino = {"@type": "DefinedRegion", "addressCountry": "AR"}
        if region:
            destino["addressRegion"] = region
        d = {
            "@type": "OfferShippingDetails",
            "shippingRate": _tarifa(zona),
            "shippingDestination": destino,
        }
        if zona['dias']:
            d["deliveryTime"] = {
                "@type": "ShippingDeliveryTime",
                "transitTime": {
                    "@type": "QuantitativeValue",
                    "minValue": zona['dias'][0],
                    "maxValue": zona['dias'][1],
                    "unitCode": "DAY",
                },
            }
        return d

    return [e for e in (_entrada(res['resto']), _entrada(res['caba'], 'C')) if e]


# Política de devoluciones publicada en /devoluciones y /terminos:
# 10 días hábiles de arrepentimiento (Ley 24.240 art. 34), retiro/envío de
# vuelta sin costo, reembolso por el mismo medio de pago (Mercado Pago).
DEVOLUCION_DIAS = 10


def return_policy_jsonld() -> dict:
    """`Offer.hasMerchantReturnPolicy` (schema.org MerchantReturnPolicy)."""
    return {
        "@type": "MerchantReturnPolicy",
        "applicableCountry": "AR",
        "returnPolicyCountry": "AR",
        "returnPolicyCategory": "https://schema.org/MerchantReturnFiniteReturnWindow",
        "merchantReturnDays": DEVOLUCION_DIAS,
        "returnMethod": "https://schema.org/ReturnByMail",
        "returnFees": "https://schema.org/FreeReturn",
        "refundType": "https://schema.org/FullRefund",
    }
