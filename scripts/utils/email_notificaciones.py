#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
NOTIFICACIONES POR EMAIL A CLIENTES (vía Resend)

Envía emails de confirmación de pago y de seguimiento de envío usando la API
de Resend (https://resend.com). Mientras no haya un dominio propio verificado,
se puede usar la dirección sandbox onboarding@resend.dev.
"""

import sys
from pathlib import Path

import requests

sys.path.append(str(Path(__file__).parent.parent))
from utils.logger import get_logger
from utils.config import Config

logger = get_logger('email_notificaciones')

RESEND_URL = "https://api.resend.com/emails"
TIENDA_NOMBRE = "El Gadget"


def email_habilitado() -> bool:
    """True si hay un RESEND_API_KEY configurado en config/.env"""
    env = Config.cargar_env()
    return bool(env.get('RESEND_API_KEY'))


def _enviar(to_email: str, subject: str, html: str) -> dict:
    env = Config.cargar_env()
    if not email_habilitado():
        return {'error': 'Email no configurado (falta RESEND_API_KEY)'}

    from_email = env.get('RESEND_FROM_EMAIL', 'onboarding@resend.dev')

    try:
        response = requests.post(
            RESEND_URL,
            headers={
                "Authorization": f"Bearer {env['RESEND_API_KEY']}",
                "Content-Type": "application/json",
            },
            json={
                "from": f"{TIENDA_NOMBRE} <{from_email}>",
                "to": [to_email],
                "subject": subject,
                "html": html,
            },
            timeout=10,
        )
        if response.status_code >= 300:
            logger.error(f"Error enviando email a {to_email}: {response.status_code} - {response.text}")
            return {'error': response.text}
        return response.json()
    except Exception as e:
        logger.error(f"Excepción enviando email a {to_email}: {e}")
        return {'error': str(e)}


def enviar_email_confirmacion(orden: dict, items: list, factura: dict = None) -> dict:
    """
    Envía email de confirmación de pago aprobado.

    Args:
        orden: dict con datos de la orden + cliente (id, nombre, email, total)
        items: lista de dicts con producto_nombre, cantidad, subtotal
        factura: dict con punto_venta/numero/cae (opcional, si AFIP está habilitado)
    """
    filas_items = "".join(
        f"<tr>"
        f"<td style='padding:6px 12px;border-bottom:1px solid #eee'>{item['producto_nombre']}</td>"
        f"<td style='padding:6px 12px;border-bottom:1px solid #eee;text-align:center'>{item['cantidad']}</td>"
        f"<td style='padding:6px 12px;border-bottom:1px solid #eee;text-align:right'>${item['subtotal']:,.2f}</td>"
        f"</tr>"
        for item in items
    )

    factura_html = ""
    if factura and not factura.get('error'):
        factura_html = (
            f"<p>Factura C N° {factura['punto_venta']:04d}-{factura['numero']:08d} "
            f"— CAE {factura['cae']}</p>"
        )

    html = f"""
    <div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto">
      <h2 style="color:#111">¡Gracias por tu compra, {orden['nombre']}!</h2>
      <p>Tu pago fue aprobado. Te confirmamos los detalles de tu pedido #{orden['id']}:</p>
      <table style="width:100%;border-collapse:collapse;border:1px solid #eee">
        <thead>
          <tr style="background:#111;color:#fff">
            <th style="padding:6px 12px;text-align:left">Producto</th>
            <th style="padding:6px 12px">Cant.</th>
            <th style="padding:6px 12px;text-align:right">Subtotal</th>
          </tr>
        </thead>
        <tbody>{filas_items}</tbody>
      </table>
      <p style="text-align:right;font-weight:bold;font-size:1.1em">Total: ${orden['total']:,.2f}</p>
      {factura_html}
      <p>Te avisaremos por email cuando tu pedido sea despachado, junto con el link de seguimiento.</p>
      <p style="color:#888;font-size:0.9em">{TIENDA_NOMBRE}</p>
    </div>
    """

    return _enviar(orden['email'], f"Confirmación de tu pedido #{orden['id']} - {TIENDA_NOMBRE}", html)


def enviar_email_tracking(orden: dict, tracking_url: str) -> dict:
    """Envía email con el link de seguimiento del envío."""
    html = f"""
    <div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto">
      <h2 style="color:#111">¡Tu pedido #{orden['id']} fue despachado!</h2>
      <p>Hola {orden['nombre']}, tu pedido ya está en camino.</p>
      <p>
        <a href="{tracking_url}" style="background:#FFD500;color:#111;padding:10px 20px;
           text-decoration:none;border-radius:4px;font-weight:bold;display:inline-block">
          Seguir mi envío
        </a>
      </p>
      <p>O copiá este link en tu navegador:<br>{tracking_url}</p>
      <p style="color:#888;font-size:0.9em">{TIENDA_NOMBRE}</p>
    </div>
    """

    return _enviar(orden['email'], f"Tu pedido #{orden['id']} fue despachado - {TIENDA_NOMBRE}", html)
