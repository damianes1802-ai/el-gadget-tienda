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

# ── Paleta de marca (igual a pages/assets/css/style.css) ──
INK = "#14151A"
WHITE = "#FFFFFF"
CREAM = "#F7F6F3"
ACCENT = "#FFC700"
ACCENT_DEEP = "#E0AC00"
ACCENT_PALE = "#FFF7DD"
GRAY_200 = "#E5E2DD"
GRAY_600 = "#6F6A63"
GREEN_OK = "#2E8B57"
GREEN_PALE = "#E9F5EE"

FONT_STACK = "'Segoe UI', Helvetica, Arial, sans-serif"


def email_habilitado() -> bool:
    """True si hay un RESEND_API_KEY configurado en config/.env"""
    env = Config.cargar_env()
    return bool(env.get('RESEND_API_KEY'))


def _layout(cuerpo_html: str) -> str:
    """Envoltorio común (header con logo + footer) para todos los emails."""
    env = Config.cargar_env()
    site_url = env.get('SITE_URL', 'https://elgadget.com.ar').rstrip('/')
    logo_url = f"{site_url}/assets/img/logo-animado.gif"
    dominio = site_url.replace('https://', '').replace('http://', '')

    return f"""
    <div style="background:{CREAM};padding:24px 12px;font-family:{FONT_STACK}">
      <div style="max-width:600px;margin:0 auto;background:{WHITE};border-radius:16px;
                  overflow:hidden;border:1px solid {GRAY_200}">
        <div style="padding:22px 28px;background:{CREAM};border-bottom:1px solid {GRAY_200}">
          <img src="{logo_url}" width="220" height="59" alt="El Gadget"
               style="display:block;border:0;outline:0;max-width:220px;height:auto">
        </div>
        <div style="padding:30px 28px;color:{INK};font-size:15px;line-height:1.6">
          {cuerpo_html}
        </div>
        <div style="padding:20px 28px;background:{INK};color:rgba(255,255,255,0.55);
                    font-size:11px;text-align:center;letter-spacing:0.4px">
          {TIENDA_NOMBRE} · Tienda online<br>
          <a href="{site_url}" style="color:{ACCENT};text-decoration:none">{dominio}</a>
        </div>
      </div>
    </div>
    """


def _boton(texto: str, url: str) -> str:
    return f"""
    <p style="text-align:center;margin:28px 0">
      <a href="{url}" style="display:inline-block;background:{ACCENT};color:{INK};
         padding:14px 28px;text-decoration:none;border-radius:10px;font-weight:700;
         font-size:15px">
        {texto}
      </a>
    </p>
    """


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
        f"<td style='padding:10px 14px;border-bottom:1px solid {GRAY_200}'>{item['producto_nombre']}</td>"
        f"<td style='padding:10px 14px;border-bottom:1px solid {GRAY_200};text-align:center'>{item['cantidad']}</td>"
        f"<td style='padding:10px 14px;border-bottom:1px solid {GRAY_200};text-align:right;font-weight:600'>${item['subtotal']:,.2f}</td>"
        f"</tr>"
        for item in items
    )

    factura_html = ""
    if factura and not factura.get('error'):
        factura_html = (
            f"<p style='margin:18px 0 0;padding:12px 16px;background:{GREEN_PALE};"
            f"color:{GREEN_OK};border-radius:10px;font-size:13px;font-weight:600'>"
            f"Factura C N° {factura['punto_venta']:04d}-{factura['numero']:08d} "
            f"— CAE {factura['cae']}</p>"
        )

    cuerpo = f"""
      <h2 style="margin:0 0 6px;font-size:22px;color:{INK}">¡Gracias por tu compra, {orden['nombre']}!</h2>
      <p style="color:{GRAY_600};margin:0 0 22px">
        Tu pago fue aprobado. Te confirmamos los detalles de tu pedido
        <strong style="color:{INK}">#{orden['id']}</strong>.
      </p>
      <table style="width:100%;border-collapse:collapse;border:1px solid {GRAY_200};border-radius:10px;overflow:hidden">
        <thead>
          <tr style="background:{INK};color:{WHITE}">
            <th style="padding:10px 14px;text-align:left;font-size:12px;letter-spacing:0.5px;text-transform:uppercase">Producto</th>
            <th style="padding:10px 14px;font-size:12px;letter-spacing:0.5px;text-transform:uppercase">Cant.</th>
            <th style="padding:10px 14px;text-align:right;font-size:12px;letter-spacing:0.5px;text-transform:uppercase">Subtotal</th>
          </tr>
        </thead>
        <tbody>{filas_items}</tbody>
      </table>
      <p style="text-align:right;font-weight:700;font-size:18px;margin:16px 4px 0;color:{INK}">
        Total: ${orden['total']:,.2f}
      </p>
      {factura_html}
      <p style="color:{GRAY_600};margin-top:24px">
        Te avisaremos por email cuando tu pedido sea despachado, junto con el link de seguimiento.
      </p>
    """

    return _enviar(orden['email'], f"Confirmación de tu pedido #{orden['id']} - {TIENDA_NOMBRE}", _layout(cuerpo))


def enviar_email_tracking(orden: dict, tracking_url: str) -> dict:
    """Envía email con el link de seguimiento del envío."""
    cuerpo = f"""
      <h2 style="margin:0 0 6px;font-size:22px;color:{INK}">¡Tu pedido #{orden['id']} fue despachado!</h2>
      <p style="color:{GRAY_600};margin:0">
        Hola {orden['nombre']}, tu pedido ya está en camino.
      </p>
      {_boton('Seguir mi envío', tracking_url)}
      <p style="color:{GRAY_600};font-size:13px;margin:0;word-break:break-all">
        O copiá este link en tu navegador:<br>
        <a href="{tracking_url}" style="color:{ACCENT_DEEP}">{tracking_url}</a>
      </p>
    """

    return _enviar(orden['email'], f"Tu pedido #{orden['id']} fue despachado - {TIENDA_NOMBRE}", _layout(cuerpo))


def enviar_email_bienvenida(nombre: str, email: str) -> dict:
    """Envía email de bienvenida confirmando el registro y el 10% OFF automático."""
    cuerpo = f"""
      <h2 style="margin:0 0 6px;font-size:22px;color:{INK}">¡Bienvenido/a a {TIENDA_NOMBRE}, {nombre}!</h2>
      <p style="color:{GRAY_600};margin:0 0 4px">
        Tu registro se completó con éxito. Como agradecimiento, tenés un
        <strong style="color:{INK}">10% OFF</strong> para tu primera compra.
      </p>
      <div style="text-align:center;margin:28px 0">
        <span style="display:inline-block;background:{ACCENT};color:{INK};padding:16px 32px;
           border-radius:12px;font-weight:700;font-size:18px;letter-spacing:0.3px">
          10% OFF en tu primera compra
        </span>
      </div>
      <p style="color:{GRAY_600};margin:0">
        No necesitás hacer nada más: el descuento se aplica <strong style="color:{INK}">automáticamente</strong>
        al finalizar tu primera compra, usando este mismo email (<strong style="color:{INK}">{email}</strong>).
      </p>
    """

    return _enviar(email, f"¡Bienvenido/a a {TIENDA_NOMBRE}! Tu 10% OFF te espera", _layout(cuerpo))
