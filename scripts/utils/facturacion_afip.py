#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FACTURACIÓN ELECTRÓNICA AFIP/ARCA (vía AfipSDK)

Genera Facturas C (Monotributo) para las órdenes pagadas, usando el wrapper
afip.py de AfipSDK (https://afipsdk.com). En modo desarrollo (sin certificado
propio) se usa el CUIT de pruebas público de AfipSDK (20409378472) junto con
un AFIP_ACCESS_TOKEN obtenido en https://app.afipsdk.com.
"""

import sys
from datetime import datetime
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))
from utils.logger import get_logger
from utils.config import Config

logger = get_logger('facturacion_afip')

CBTE_TIPO_FACTURA_C = 11
CBTE_TIPO_NOTA_CREDITO_C = 13
CONCEPTO_PRODUCTOS = 1
DOC_TIPO_CUIT = 80
DOC_TIPO_DNI = 96
DOC_TIPO_CONSUMIDOR_FINAL = 99
CONDICION_IVA_CONSUMIDOR_FINAL = 5

CUIT_TEST_AFIPSDK = '20409378472'


def facturacion_habilitada() -> bool:
    """True si hay certificado propio o access_token configurado."""
    env = Config.cargar_env()
    has_cert_files = bool(env.get('AFIP_CERT_PATH')) and bool(env.get('AFIP_KEY_PATH'))
    has_cert_content = bool(env.get('AFIP_CERT_CONTENT')) and bool(env.get('AFIP_KEY_CONTENT'))
    has_token = bool(env.get('AFIP_ACCESS_TOKEN'))
    return has_cert_files or has_cert_content or has_token


def _get_afip_client():
    from afip import Afip

    env = Config.cargar_env()
    cuit = int(env.get('AFIP_CUIT', CUIT_TEST_AFIPSDK))

    base_dir = Path(__file__).parent.parent.parent
    cert_path = env.get('AFIP_CERT_PATH', '')
    key_path = env.get('AFIP_KEY_PATH', '')

    config = {'CUIT': cuit}

    cert_content = env.get('AFIP_CERT_CONTENT', '')
    key_content = env.get('AFIP_KEY_CONTENT', '')

    if cert_content and key_content:
        config['cert'] = cert_content.replace('\\n', '\n')
        config['key'] = key_content.replace('\\n', '\n')
    elif cert_path and key_path:
        cert_full = base_dir / cert_path if not Path(cert_path).is_absolute() else Path(cert_path)
        key_full = base_dir / key_path if not Path(key_path).is_absolute() else Path(key_path)
        config['cert'] = cert_full.read_text()
        config['key'] = key_full.read_text()

    access_token = env.get('AFIP_ACCESS_TOKEN', '')
    if access_token:
        config['access_token'] = access_token

    # Sin este flag la librería usa el entorno de homologación aunque el
    # certificado sea de producción: las facturas no tienen validez fiscal.
    if env.get('AFIP_PRODUCTION', '').strip().lower() in ('1', 'true', 'si'):
        config['production'] = True

    return Afip(config)


def entorno_afip() -> str:
    """'produccion' o 'homologacion' según AFIP_PRODUCTION en config/.env."""
    env = Config.cargar_env()
    prod = env.get('AFIP_PRODUCTION', '').strip().lower() in ('1', 'true', 'si')
    return 'produccion' if prod else 'homologacion'


def _doc_tipo_y_nro(cuit_dni: str):
    cuit_dni = (cuit_dni or '').strip().replace('-', '').replace('.', '')
    if not cuit_dni:
        return DOC_TIPO_CONSUMIDOR_FINAL, 0
    if len(cuit_dni) == 11:
        return DOC_TIPO_CUIT, int(cuit_dni)
    if len(cuit_dni) in (7, 8):
        return DOC_TIPO_DNI, int(cuit_dni)
    return DOC_TIPO_CONSUMIDOR_FINAL, 0


def generar_factura_c(orden_id: int, cliente: dict, total: float) -> dict:
    """
    Genera una Factura C (Monotributo, sin discriminar IVA) para una orden.

    Args:
        orden_id: ID interno de la orden (solo para logging)
        cliente: dict con datos del cliente (al menos 'cuit_dni')
        total: importe total de la orden

    Returns:
        dict con 'punto_venta', 'numero', 'cae', 'cae_vencimiento' si fue
        exitoso, o dict con 'error' si falló.
    """
    if not facturacion_habilitada():
        return {'error': 'Facturación AFIP no configurada (falta AFIP_ACCESS_TOKEN)'}

    try:
        afip = _get_afip_client()
        env = Config.cargar_env()
        punto_venta = int(env.get('AFIP_PUNTO_VENTA', '1'))

        doc_tipo, doc_nro = _doc_tipo_y_nro(cliente.get('cuit_dni', ''))
        total_redondeado = round(float(total), 2)

        data = {
            'CantReg': 1,
            'PtoVta': punto_venta,
            'CbteTipo': CBTE_TIPO_FACTURA_C,
            'Concepto': CONCEPTO_PRODUCTOS,
            'DocTipo': doc_tipo,
            'DocNro': doc_nro,
            'CbteFch': int(datetime.now().strftime('%Y%m%d')),
            'ImpTotal': total_redondeado,
            'ImpTotConc': 0,
            'ImpNeto': total_redondeado,
            'ImpOpEx': 0,
            'ImpIVA': 0,
            'ImpTrib': 0,
            'MonId': 'PES',
            'MonCotiz': 1,
            'CondicionIVAReceptorId': CONDICION_IVA_CONSUMIDOR_FINAL,
        }

        resultado = afip.ElectronicBilling.createNextVoucher(data)

        logger.info(
            f"Factura C generada para orden {orden_id} ({entorno_afip()}): "
            f"{punto_venta:04d}-{resultado['voucherNumber']:08d} CAE {resultado['CAE']}"
        )

        return {
            'tipo': CBTE_TIPO_FACTURA_C,
            'punto_venta': punto_venta,
            'numero': resultado['voucherNumber'],
            'cae': resultado['CAE'],
            'cae_vencimiento': resultado['CAEFchVto'],
            'fecha': datetime.now().strftime('%Y-%m-%d'),
            'doc_tipo': doc_tipo,
            'doc_nro': doc_nro,
        }
    except Exception as e:
        logger.error(f"Error generando factura AFIP para orden {orden_id}: {e}")
        return {'error': str(e)}


def generar_nota_credito_c(orden_id: int, cliente: dict, total: float,
                           factura_original: dict) -> dict:
    """
    Genera una Nota de Crédito C que anula (total o parcialmente) una Factura C
    ya emitida. Se usa al reembolsar una venta: fiscalmente la factura original
    no se "borra", se compensa con esta nota.

    Args:
        orden_id: ID interno de la orden (para logging)
        cliente: dict con datos del cliente (al menos 'cuit_dni')
        total: importe a acreditar (normalmente el total de la factura original)
        factura_original: dict con 'tipo', 'punto_venta', 'numero' de la factura
            que se está anulando (para el comprobante asociado obligatorio)

    Returns:
        dict con datos de la nota de crédito, o dict con 'error' si falló.
    """
    if not facturacion_habilitada():
        return {'error': 'Facturación AFIP no configurada (falta AFIP_ACCESS_TOKEN)'}

    if not factura_original or not factura_original.get('numero'):
        return {'error': 'Falta la factura original a anular'}

    try:
        afip = _get_afip_client()
        env = Config.cargar_env()
        punto_venta = int(env.get('AFIP_PUNTO_VENTA', '1'))

        doc_tipo, doc_nro = _doc_tipo_y_nro(cliente.get('cuit_dni', ''))
        total_redondeado = round(float(total), 2)

        data = {
            'CantReg': 1,
            'PtoVta': punto_venta,
            'CbteTipo': CBTE_TIPO_NOTA_CREDITO_C,
            'Concepto': CONCEPTO_PRODUCTOS,
            'DocTipo': doc_tipo,
            'DocNro': doc_nro,
            'CbteFch': int(datetime.now().strftime('%Y%m%d')),
            'ImpTotal': total_redondeado,
            'ImpTotConc': 0,
            'ImpNeto': total_redondeado,
            'ImpOpEx': 0,
            'ImpIVA': 0,
            'ImpTrib': 0,
            'MonId': 'PES',
            'MonCotiz': 1,
            'CondicionIVAReceptorId': CONDICION_IVA_CONSUMIDOR_FINAL,
            # Comprobante asociado obligatorio: la factura que se anula.
            'CbtesAsoc': [{
                'Tipo': int(factura_original.get('tipo', CBTE_TIPO_FACTURA_C)),
                'PtoVta': int(factura_original['punto_venta']),
                'Nro': int(factura_original['numero']),
            }],
        }

        resultado = afip.ElectronicBilling.createNextVoucher(data)

        logger.info(
            f"Nota de Crédito C generada para orden {orden_id} ({entorno_afip()}): "
            f"{punto_venta:04d}-{resultado['voucherNumber']:08d} CAE {resultado['CAE']} "
            f"(anula {factura_original['punto_venta']:04d}-{factura_original['numero']:08d})"
        )

        return {
            'tipo': CBTE_TIPO_NOTA_CREDITO_C,
            'punto_venta': punto_venta,
            'numero': resultado['voucherNumber'],
            'cae': resultado['CAE'],
            'cae_vencimiento': resultado['CAEFchVto'],
            'fecha': datetime.now().strftime('%Y-%m-%d'),
            'doc_tipo': doc_tipo,
            'doc_nro': doc_nro,
        }
    except Exception as e:
        logger.error(f"Error generando nota de crédito AFIP para orden {orden_id}: {e}")
        return {'error': str(e)}
