# -*- coding: utf-8 -*-
"""Envío bonificado (CABA/GBA1 desde $40.000 de productos pagados).

Dos cosas se prueban acá:
1. La regla en `calcular_envio`: zona elegible + subtotal >= mínimo → costo 0;
   por debajo del mínimo o en zonas no elegibles → tarifa de Droppers.
2. Que absorber el envío NUNCA deja una venta en pérdida, en el peor camino
   de descuentos que permite el checkout. Si alguien baja el margen, sube el
   umbral de descuentos o cambia el mínimo, este test avisa.
"""
import json
import math
import sys
from pathlib import Path

import pytest

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE / "scripts"))

ZONAS = json.loads((BASE / "data/envios/zonas_envio.json").read_text(encoding="utf-8"))
PRECIOS = json.loads((BASE / "data/precios/config_precios_v2.json").read_text(encoding="utf-8"))
BON = ZONAS["envio_bonificado"]

# Peores casos del checkout (ver crear_orden en api_local.py):
#  - códigos: hasta 30% sobre lista (20% referido + 10% bienvenida) + comisión
#    al referidor de hasta 15% sobre lo que paga el cliente
#  - oferta de temporada: hasta 30% (Cyber/Black), sin comisión
#  - bienvenida de landing: 50% sola, sin comisión
# Comisión de Mercado Pago (Checkout Pro, dinero al instante): 6,29% + IVA.
CASOS = {
    "sin descuento": (0.00, 0.00),
    "oferta temporada 30%": (0.30, 0.00),
    "códigos 30% + referidor 15%": (0.30, 0.15),
    "bienvenida landing 50%": (0.50, 0.00),
}
MP_FEE = 0.0629 * 1.21


def _factor_precio():
    margen = float(PRECIOS["perfiles_precio"]["default"]["margen_porcentaje"])
    return 1 + margen / 100  # precio de lista = costo * factor (después se redondea hacia arriba)


@pytest.mark.parametrize("zona_id", BON["zonas"])
@pytest.mark.parametrize("caso", list(CASOS))
def test_envio_bonificado_no_deja_perdida(zona_id, caso):
    """En el umbral exacto (el peor punto: el envío absorbido pesa lo máximo
    posible), la venta sigue dejando ganancia en todos los caminos."""
    desc, comision = CASOS[caso]
    pagado = float(BON["minimo"])                 # el cliente paga justo el mínimo en productos
    lista = pagado / (1 - desc)                   # precio de lista equivalente
    costo = lista / _factor_precio()              # lo que se le paga a Droppers (sin redondeo: peor caso)
    envio = float(ZONAS["zonas"][zona_id]["costo"])
    neto = pagado - pagado * comision - pagado * MP_FEE - envio
    ganancia = neto - costo
    assert ganancia > 0, (
        f"{caso} en {zona_id}: pagado {pagado:.0f}, costo {costo:.0f}, envío {envio:.0f}, "
        f"neto {neto:.0f} → pérdida de {-ganancia:.0f}"
    )


def test_calcular_envio_aplica_la_regla():
    from api_local import calcular_envio

    minimo = BON["minimo"]
    caba = calcular_envio("CABA / Capital Federal", "", subtotal_pagado=minimo)
    assert caba["zona"] == "CABA" and caba["bonificado"] is True and caba["costo"] == 0
    assert caba["costo_lista"] == ZONAS["zonas"]["CABA"]["costo"]

    caba_menos = calcular_envio("CABA / Capital Federal", "", subtotal_pagado=minimo - 1)
    assert caba_menos["bonificado"] is False and caba_menos["costo"] == ZONAS["zonas"]["CABA"]["costo"]

    # sin subtotal (llamadas viejas) → nunca bonifica
    assert calcular_envio("CABA / Capital Federal", "")["costo"] == ZONAS["zonas"]["CABA"]["costo"]

    # resto del país: no elegible aunque supere el mínimo
    resto = calcular_envio("Córdoba", "", subtotal_pagado=minimo * 10)
    assert resto["zona"] == "RESTO_PAIS" and resto["bonificado"] is False and resto["bonificable"] is False
    assert resto["costo"] == ZONAS["zonas"]["RESTO_PAIS"]["costo"]

    # GBA1 por partido (San Isidro está en GBA1 en el tarifario)
    partido_gba1 = next(p for p, z in ZONAS["partidos_buenos_aires"].items() if z == "GBA1")
    gba1 = calcular_envio("Provincia de Buenos Aires", partido_gba1, subtotal_pagado=minimo)
    assert gba1["zona"] == "GBA1" and gba1["bonificado"] is True and gba1["costo"] == 0
