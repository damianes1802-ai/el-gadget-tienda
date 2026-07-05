#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VERIFICACIÓN DE FACTURACIÓN ARCA EN PRODUCCIÓN (solo lectura)

Valida certificado, autorización del web service wsfe y punto de venta
contra el entorno configurado en config/.env, SIN emitir ninguna factura.
Usa únicamente métodos de consulta (getServerStatus, getSalesPoints,
getLastVoucher).

Uso:
    python scripts/verificar_afip_produccion.py

Para probar contra producción real: AFIP_PRODUCTION=1 en config/.env
(requiere AFIP_ACCESS_TOKEN de app.afipsdk.com y el certificado propio).
"""

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent))
from utils.config import Config
from utils.facturacion_afip import _get_afip_client, entorno_afip, CBTE_TIPO_FACTURA_C


def main():
    env = Config.cargar_env()
    cuit = env.get('AFIP_CUIT', '(sin configurar)')
    punto_venta = int(env.get('AFIP_PUNTO_VENTA', '1'))
    entorno = entorno_afip()

    print(f'Entorno:        {entorno}')
    print(f'CUIT emisor:    {cuit}')
    print(f'Punto de venta: {punto_venta}')
    print('-' * 50)

    afip = _get_afip_client()
    fallas = 0

    # 1. Estado del servidor de ARCA
    try:
        status = afip.ElectronicBilling.getServerStatus()
        print(f'[OK]   Servidor ARCA: {status}')
    except Exception as e:
        print(f'[FAIL] Servidor ARCA: {e}')
        fallas += 1

    # 2. Puntos de venta habilitados para web services
    #    (getSalesPoints falla en homologación para algunos CUIT de prueba; es normal)
    try:
        puntos = afip.ElectronicBilling.getSalesPoints()
        print(f'[OK]   Puntos de venta: {puntos}')
        numeros = [p.get('Nro') for p in puntos] if isinstance(puntos, list) else []
        if numeros and punto_venta not in numeros:
            print(f'[WARN] El punto de venta configurado ({punto_venta}) no está en la lista {numeros}')
    except Exception as e:
        print(f'[WARN] Puntos de venta no consultables: {e}')

    # 3. Último comprobante autorizado (valida certificado + relación wsfe + pto vta)
    try:
        ultimo = afip.ElectronicBilling.getLastVoucher(punto_venta, CBTE_TIPO_FACTURA_C)
        print(f'[OK]   Última Factura C autorizada en pto {punto_venta}: N° {ultimo}')
        print()
        print(f'TODO LISTO — el certificado y el punto de venta funcionan en {entorno}.')
        if entorno == 'produccion':
            print('La próxima venta aprobada emitirá una factura REAL con validez fiscal.')
    except Exception as e:
        print(f'[FAIL] getLastVoucher: {e}')
        fallas += 1
        print()
        print('Revisar: ¿el certificado está autorizado para "Facturación Electrónica"')
        print('en el Administrador de Relaciones? ¿El punto de venta existe con modalidad')
        print('"Factura Electrónica - Web Services"? ¿AFIP_ACCESS_TOKEN es válido?')

    return 1 if fallas else 0


if __name__ == '__main__':
    sys.exit(main())
