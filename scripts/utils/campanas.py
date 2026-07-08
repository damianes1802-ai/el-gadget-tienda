#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LÓGICA COMPARTIDA DE CAMPAÑAS DE DESCUENTO

Vigencia por fechas (con soporte de campañas recurrentes anuales) y cálculo
del precio de oferta. La usan tanto la API (api_local.py) como el generador
de páginas/catálogo estático (12_generar_paginas_producto.py), así las dos
vías calculan EXACTAMENTE lo mismo y nunca se desincronizan.
"""

import json
from datetime import datetime
from typing import Optional


def mmdd(fecha: str) -> str:
    """Extrae 'MM-DD' de una fecha 'YYYY-MM-DD'. '' si no aplica."""
    if not fecha or len(fecha) < 10:
        return ""
    return fecha[5:10]


def fecha_campana_vigente(d: dict, hoy: str) -> bool:
    """True si la campaña está dentro de su ventana de fechas HOY.

    - No recurrente: compara la fecha completa YYYY-MM-DD (una sola vez).
    - Recurrente anual: compara solo mes-día, así aplica todos los años.
      Soporta ventanas que cruzan el año (ej. 26/12 → 06/01).
    hoy es 'YYYY-MM-DD'.
    """
    ini, fin = d.get("fecha_inicio"), d.get("fecha_fin")

    if not d.get("recurrente_anual"):
        if ini and hoy < ini:
            return False
        if fin and hoy > fin:
            return False
        return True

    # Recurrente: comparar por mes-día
    hoy_md = hoy[5:10]
    ini_md, fin_md = mmdd(ini), mmdd(fin)
    if ini_md and fin_md:
        if ini_md <= fin_md:
            # ventana normal dentro del mismo año calendario
            return ini_md <= hoy_md <= fin_md
        # ventana que cruza el fin de año (ej. 26-12 → 06-01)
        return hoy_md >= ini_md or hoy_md <= fin_md
    if ini_md:
        return hoy_md >= ini_md
    if fin_md:
        return hoy_md <= fin_md
    return True


def campanas_programadas_vigentes(cursor, hoy: str = None) -> list:
    """Campañas automáticas (sin código) vigentes hoy: las que reflejan un
    precio_oferta directamente en el catálogo."""
    hoy = hoy or datetime.now().strftime("%Y-%m-%d")
    cursor.execute("SELECT * FROM descuentos WHERE codigo IS NULL AND activo = 1")
    return [dict(r) for r in cursor.fetchall() if fecha_campana_vigente(dict(r), hoy)]


def calcular_precio_oferta(producto: dict, descuentos_programados: list) -> Optional[float]:
    """Calcula el precio de oferta de un producto según las campañas vigentes
    que lo alcancen (por SKU, categoría o todos los productos)."""
    precio_venta = producto.get("precio_venta") or 0
    mejor_precio = None

    for d in descuentos_programados:
        alcance = d.get("alcance")
        aplica = False

        if alcance == "todos":
            aplica = True
        elif alcance == "categoria" and d.get("categoria") and d.get("categoria") == producto.get("categoria"):
            aplica = True
        elif alcance == "skus":
            try:
                skus = json.loads(d.get("skus") or "[]")
            except (TypeError, ValueError):
                skus = []
            aplica = producto.get("sku") in skus

        if not aplica:
            continue

        if d.get("tipo") == "porcentaje":
            precio = precio_venta * (1 - (d.get("valor") or 0) / 100)
        else:
            precio = precio_venta - (d.get("valor") or 0)
        precio = max(precio, 0)

        if mejor_precio is None or precio < mejor_precio:
            mejor_precio = precio

    if mejor_precio is not None and mejor_precio < precio_venta:
        return round(mejor_precio, 2)
    return None
