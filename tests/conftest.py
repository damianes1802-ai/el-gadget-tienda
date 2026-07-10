# -*- coding: utf-8 -*-
"""Configuración común de los tests.

REGLA CRÍTICA: los tests JAMÁS deben disparar emails ni pagos reales.
`Config.cargar_env()` prioriza config/.env (con las claves reales) sobre las
variables de entorno, así que apagar por env var NO alcanza: hay que
monkeypatchear los símbolos en el namespace de api_local (acá abajo).
"""
import os
import sys
from pathlib import Path

BASE = Path(__file__).parent.parent
sys.path.insert(0, str(BASE / 'scripts'))
os.chdir(BASE)

import api_local  # noqa: E402

# Apagar TODOS los efectos externos:
api_local.email_habilitado = lambda: False   # Resend (emails cliente/admin)
api_local.MP_ACCESS_TOKEN = ''               # MercadoPago (preferencias)
# AFIP queda naturalmente apagado en local (sin AFIP_ACCESS_TOKEN el intento
# de factura falla de forma controlada y best-effort).
# El rate limiter comparte la IP ficticia "testclient" entre TODOS los tests,
# así que los límites por minuto se agotan enseguida: apagado en tests.
api_local.limiter.enabled = False
