#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
NOTIFICACIONES POR EMAIL A CLIENTES (vía Resend)

Envía emails de confirmación de pago y de seguimiento de envío usando la API
de Resend (https://resend.com). Mientras no haya un dominio propio verificado,
se puede usar la dirección sandbox onboarding@resend.dev.
"""

import html as _html
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


def _layout(cuerpo_html: str, marketing: bool = False) -> str:
    """Envoltorio común (header con logo + footer) para todos los emails.

    Estructura basada en <table> con atributos bgcolor (no solo CSS) porque
    es lo único que evita de forma confiable que la app de Gmail invierta
    los colores en modo oscuro, y mantiene el ancho fijo a 600px sin que el
    contenido se desborde en pantallas chicas.
    """
    env = Config.cargar_env()
    site_url = env.get('SITE_URL', 'https://elgadget.com.ar').rstrip('/')
    logo_url = f"{site_url}/assets/img/logo-animado.gif"
    dominio = site_url.replace('https://', '').replace('http://', '')

    return f"""<!DOCTYPE html>
<html lang="es">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="color-scheme" content="light">
    <meta name="supported-color-schemes" content="light">
    <style>
      body {{ margin:0; padding:0; }}
      table {{ border-collapse:collapse; }}
      img {{ -ms-interpolation-mode:bicubic; }}
    </style>
  </head>
  <body style="margin:0;padding:0;background-color:{CREAM};font-family:{FONT_STACK}">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"
           bgcolor="{CREAM}" style="background-color:{CREAM} !important">
      <tr>
        <td align="center" style="padding:24px 12px">
          <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"
                 bgcolor="{WHITE}" style="max-width:600px;width:100%;background-color:{WHITE} !important;
                 border-radius:16px;overflow:hidden;border:1px solid {GRAY_200}">
            <tr>
              <td align="center" bgcolor="{ACCENT_PALE}"
                  style="padding:22px 0;background-color:{ACCENT_PALE} !important;border-bottom:1px solid {GRAY_200}">
                <img src="{logo_url}" width="220" height="59" alt="El Gadget"
                     style="display:block;margin:0 auto;border:0;outline:0;max-width:220px;height:auto;border-radius:12px">
              </td>
            </tr>
            <tr>
              <td align="center" bgcolor="{WHITE}"
                  style="padding:30px 24px;background-color:{WHITE} !important;color:{INK} !important;
                  font-size:15px;line-height:1.6">
                {cuerpo_html}
              </td>
            </tr>
            <tr>
              <td align="center" bgcolor="{INK}"
                  style="padding:20px 28px;background-color:{INK} !important;color:#B8B8BD !important;
                  font-size:11px;letter-spacing:0.4px">
                <span style="color:#B8B8BD !important">{TIENDA_NOMBRE} · Tienda online</span><br>
                <a href="{site_url}" style="color:{ACCENT} !important;text-decoration:none">{dominio}</a>
                {'<br><span style="color:#7a7a7f !important;font-size:10px">No querés recibir más estos tips? <a href="' + site_url + '/mi_cuenta" style="color:#7a7a7f !important;text-decoration:underline">Desuscribirme</a></span>' if marketing else ''}
              </td>
            </tr>
          </table>
        </td>
      </tr>
    </table>
  </body>
</html>"""


def _boton(texto: str, url: str) -> str:
    return f"""
    <p style="text-align:center;margin:28px 0">
      <a href="{url}" style="display:inline-block;background-color:{ACCENT} !important;color:{INK} !important;
         padding:14px 28px;text-decoration:none;border-radius:10px;font-weight:700;
         font-size:15px">
        {texto}
      </a>
    </p>
    """


def _enviar(to_email: str, subject: str, html: str, is_marketing: bool = False) -> dict:
    env = Config.cargar_env()
    if not email_habilitado():
        return {'error': 'Email no configurado (falta RESEND_API_KEY)'}

    from_email = env.get('RESEND_FROM_EMAIL', 'onboarding@resend.dev')
    site_url = env.get('SITE_URL', 'https://elgadget.com.ar').rstrip('/')

    payload = {
        "from": f"{TIENDA_NOMBRE} <{from_email}>",
        "to": [to_email],
        "subject": subject,
        "html": html,
    }

    if is_marketing:
        unsub_url = f"{site_url}/mi_cuenta"
        payload["headers"] = {
            "List-Unsubscribe": f"<{unsub_url}>",
            "List-Unsubscribe-Post": "List-Unsubscribe=One-Click",
        }

    try:
        response = requests.post(
            RESEND_URL,
            headers={
                "Authorization": f"Bearer {env['RESEND_API_KEY']}",
                "Content-Type": "application/json",
            },
            json=payload,
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
        f"<td style='padding:10px 12px;border-bottom:1px solid {GRAY_200};word-wrap:break-word;overflow-wrap:break-word;text-align:left'>"
        f"{item['producto_nombre']}"
        f"<br><span style='color:{GRAY_600};font-size:12px'>Cantidad: {item['cantidad']}</span>"
        f"</td>"
        f"<td style='padding:10px 12px;border-bottom:1px solid {GRAY_200};text-align:right;font-weight:600;white-space:nowrap;vertical-align:top'>"
        f"${item['subtotal']:,.2f}"
        f"</td>"
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
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"
             style="width:100%;border-collapse:collapse;border:1px solid {GRAY_200};border-radius:10px;overflow:hidden">
        <thead>
          <tr bgcolor="{INK}" style="background-color:{INK} !important">
            <th style="padding:10px 12px;text-align:left;font-size:11px;letter-spacing:0.5px;text-transform:uppercase;color:{WHITE} !important">Producto</th>
            <th style="padding:10px 12px;text-align:right;font-size:11px;letter-spacing:0.5px;text-transform:uppercase;color:{WHITE} !important;white-space:nowrap">Subtotal</th>
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


def enviar_email_bienvenida(nombre: str, email: str, productos_top: list = None) -> dict:
    """Envía email de bienvenida confirmando el registro y el 10% OFF automático.

    Args:
        nombre: nombre del usuario registrado
        email: dirección de email del usuario
        productos_top: lista opcional de dicts con nombre, precio_venta,
            imagen_url (o imagen_principal), url_amigable. Si se pasan,
            se muestran como recomendaciones debajo del descuento.
    """
    nombre_s = _html.escape(nombre)
    email_s = _html.escape(email)

    env = Config.cargar_env()
    site_url = env.get('SITE_URL', 'https://elgadget.com.ar').rstrip('/')

    productos_html = ""
    if productos_top:
        cards = ""
        for p in productos_top[:3]:
            p_nombre = _html.escape(p.get('nombre', ''))
            p_precio = p.get('precio_venta', 0)
            p_img = _html.escape(p.get('imagen_url') or p.get('imagen_principal') or '')
            p_slug = (p.get('url_amigable') or '').strip()
            p_url = f"{site_url}/producto/{p_slug}/" if p_slug else site_url
            cards += f"""
            <td align="center" width="33%" style="padding:6px;vertical-align:top">
              <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"
                     style="border:1px solid {GRAY_200};border-radius:10px;overflow:hidden">
                <tr>
                  <td align="center" bgcolor="{CREAM}" style="padding:10px;background-color:{CREAM} !important">
                    <a href="{p_url}" style="text-decoration:none">
                      <img src="{p_img}" width="120" height="120" alt="{p_nombre}"
                           style="display:block;margin:0 auto;border:0;border-radius:8px;
                           object-fit:cover;max-width:120px;height:auto;background:{CREAM}">
                    </a>
                  </td>
                </tr>
                <tr>
                  <td align="center" style="padding:8px 6px 4px">
                    <a href="{p_url}" style="color:{INK};text-decoration:none;font-size:12px;
                       font-weight:600;line-height:1.3;display:block">{p_nombre}</a>
                  </td>
                </tr>
                <tr>
                  <td align="center" style="padding:0 6px 6px">
                    <span style="color:{ACCENT_DEEP};font-weight:700;font-size:14px">${p_precio:,.0f}</span>
                  </td>
                </tr>
                <tr>
                  <td align="center" style="padding:0 6px 10px">
                    <a href="{p_url}" style="display:inline-block;background:{ACCENT};color:{INK};
                       padding:6px 14px;border-radius:8px;font-weight:700;font-size:11px;
                       text-decoration:none">Ver producto</a>
                  </td>
                </tr>
              </table>
            </td>"""

        productos_html = f"""
      <p style="color:{INK};font-weight:700;font-size:15px;margin:28px 0 12px">Productos que te pueden interesar:</p>
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">
        <tr>{cards}</tr>
      </table>"""

    cuerpo = f"""
      <h2 style="margin:0 0 6px;font-size:22px;color:{INK}">¡Bienvenido/a a {TIENDA_NOMBRE}, {nombre_s}!</h2>
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
        al finalizar tu primera compra, usando este mismo email (<strong style="color:{INK}">{email_s}</strong>).
      </p>
      {productos_html}
    """

    return _enviar(email, f"¡Bienvenido/a a {TIENDA_NOMBRE}! Tu 10% OFF te espera", _layout(cuerpo))


def enviar_email_referido_confirmacion(nombre: str, email: str, codigo: str) -> dict:
    """Confirma al nuevo referente su alta en el programa: código, cómo usarlo y comisión."""
    nombre_s = _html.escape(nombre)
    codigo_s = _html.escape(codigo)
    env = Config.cargar_env()
    site_url = env.get('SITE_URL', 'https://elgadget.com.ar').rstrip('/')
    cuerpo = f"""
      <h2 style="margin:0 0 6px;font-size:22px;color:{INK}">¡Ya sos parte del programa de referidos, {nombre_s}!</h2>
      <p style="color:{GRAY_600};margin:0 0 22px">
        Tu registro fue aprobado. Este es tu código exclusivo para compartir:
      </p>
      <div style="text-align:center;margin:28px 0">
        <span style="display:inline-block;background:{ACCENT};color:{INK};padding:16px 32px;
           border-radius:12px;font-weight:700;font-size:24px;letter-spacing:1px">
          {codigo_s}
        </span>
      </div>
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"
             style="border:1px solid {GRAY_200};border-radius:12px;overflow:hidden;margin-bottom:24px">
        <tr>
          <td style="padding:14px 18px;border-bottom:1px solid {GRAY_200};background:{CREAM} !important">
            <strong style="color:{INK}">¿Cómo funciona?</strong>
          </td>
        </tr>
        <tr>
          <td style="padding:14px 18px;border-bottom:1px solid {GRAY_200}">
            Compartí tu código <strong style="color:{INK}">{codigo_s}</strong> con amigos, familia o en redes.
          </td>
        </tr>
        <tr>
          <td style="padding:14px 18px;border-bottom:1px solid {GRAY_200}">
            Cada vez que alguien compre usando tu código, obtiene entre un
            <strong style="color:{INK}">10% y 20% OFF</strong> según el monto del carrito.
          </td>
        </tr>
        <tr>
          <td style="padding:14px 18px">
            Vos ganás una <strong style="color:{INK}">comisión del 7% al 15%</strong> sobre cada venta
            (escalonada según la cantidad de ventas que generes en el mes).
            Las comisiones se liquidan mensualmente.
          </td>
        </tr>
      </table>
      <p style="color:{GRAY_600};font-size:13px;margin:0 0 8px">
        Podés ver tus comisiones y estadísticas en cualquier momento desde tu cuenta:
      </p>
      {_boton('Ver mi panel de referidos', f"{site_url}/mi_cuenta")}
    """
    return _enviar(email, f"Tu código de referido {TIENDA_NOMBRE}: {codigo_s}", _layout(cuerpo))


def enviar_email_referido_admin(nombre: str, email: str, codigo: str, admin_email: str) -> dict:
    """Notifica al admin que se registró un nuevo referido."""
    nombre_s = _html.escape(nombre)
    email_s = _html.escape(email)
    codigo_s = _html.escape(codigo)
    env = Config.cargar_env()
    site_url = env.get('SITE_URL', 'https://elgadget.com.ar').rstrip('/')
    cuerpo = f"""
      <h2 style="margin:0 0 6px;font-size:22px;color:{INK}">Nuevo referido registrado</h2>
      <p style="color:{GRAY_600};margin:0 0 22px">
        Se acaba de sumar al programa de referidos un nuevo participante:
      </p>
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"
             style="border:1px solid {GRAY_200};border-radius:12px;overflow:hidden;margin-bottom:24px">
        <tr>
          <td style="padding:12px 18px;border-bottom:1px solid {GRAY_200};background:{CREAM} !important;font-size:11.5px;text-transform:uppercase;letter-spacing:0.5px;color:{GRAY_600}">
            Dato
          </td>
          <td style="padding:12px 18px;border-bottom:1px solid {GRAY_200};background:{CREAM} !important;font-size:11.5px;text-transform:uppercase;letter-spacing:0.5px;color:{GRAY_600}">
            Valor
          </td>
        </tr>
        <tr>
          <td style="padding:12px 18px;border-bottom:1px solid {GRAY_200};color:{GRAY_600}">Nombre</td>
          <td style="padding:12px 18px;border-bottom:1px solid {GRAY_200};font-weight:600;color:{INK}">{nombre_s}</td>
        </tr>
        <tr>
          <td style="padding:12px 18px;border-bottom:1px solid {GRAY_200};color:{GRAY_600}">Email</td>
          <td style="padding:12px 18px;border-bottom:1px solid {GRAY_200};font-weight:600;color:{INK}">{email_s}</td>
        </tr>
        <tr>
          <td style="padding:12px 18px;color:{GRAY_600}">Código asignado</td>
          <td style="padding:12px 18px">
            <span style="background:{ACCENT};color:{INK};padding:4px 12px;border-radius:6px;font-weight:700;font-size:15px">
              {codigo_s}
            </span>
          </td>
        </tr>
      </table>
      {_boton('Gestionar referidos', site_url)}
    """
    return _enviar(admin_email, f"Nuevo referido: {nombre_s} ({codigo_s})", _layout(cuerpo))


# ============================================================================
# NURTURING — emails automáticos para activar referidos, rescatar carritos
# y convertir compradores en referidos.
# ============================================================================

def _producto_card(p: dict, codigo: str, site_url: str) -> str:
    """Genera una fila de producto con botón WA para emails de nurturing."""
    from urllib.parse import quote
    nombre = _html.escape(p.get('nombre', ''))
    sku = p.get('sku', '')
    slug = (p.get('url_amigable') or '').strip()
    img = _html.escape(p.get('imagen_principal') or '')
    precio = p.get('precio_venta', 0)
    url = f"{site_url}/producto/{slug}/" if slug else f"{site_url}/producto_detalle?sku={sku}"
    ref_url = f"{url}{'&' if '?' in url else '?'}ref={codigo}"
    wa_text = quote(f"Mirá este producto en El Gadget: {p.get('nombre','')} a ${precio:,.0f}. "
                    f"Usá mi código {codigo} y te hacen hasta 20% de descuento! {ref_url}")
    wa_url = f"https://wa.me/?text={wa_text}"
    return f"""
    <tr>
      <td style="padding:12px;border-bottom:1px solid {GRAY_200};width:60px;vertical-align:top">
        <img src="{img}" width="56" height="56" style="border-radius:8px;object-fit:cover;display:block;background:{CREAM}" alt="">
      </td>
      <td style="padding:12px;border-bottom:1px solid {GRAY_200};vertical-align:top">
        <strong style="color:{INK};font-size:13.5px">{nombre}</strong><br>
        <span style="color:{GRAY_600};font-size:13px">${precio:,.0f}</span>
      </td>
      <td style="padding:12px;border-bottom:1px solid {GRAY_200};vertical-align:middle;text-align:right">
        <a href="{wa_url}" style="display:inline-block;background:#25D366;color:#fff;padding:8px 14px;
           border-radius:8px;font-weight:700;font-size:12px;text-decoration:none">Compartir</a>
      </td>
    </tr>"""


def _tabla_productos(productos: list, codigo: str, site_url: str) -> str:
    if not productos:
        return ''
    filas = ''.join(_producto_card(p, codigo, site_url) for p in productos)
    return f"""
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"
           style="border:1px solid {GRAY_200};border-radius:12px;overflow:hidden;margin:20px 0">
      {filas}
    </table>"""


def enviar_email_nurturing_d3(nombre: str, email: str, codigo: str, productos_top: list) -> dict:
    """D+3: Tips para compartir + 3 productos top con botón WA."""
    nombre_s = _html.escape(nombre)
    codigo_s = _html.escape(codigo)
    env = Config.cargar_env()
    site_url = env.get('SITE_URL', 'https://elgadget.com.ar').rstrip('/')
    prods_html = _tabla_productos(productos_top[:3], codigo, site_url)
    cuerpo = f"""
      <h2 style="margin:0 0 6px;font-size:22px;color:{INK}">3 tips para empezar a ganar, {nombre_s}</h2>
      <p style="color:{GRAY_600};margin:0 0 22px">
        Ya tenés tu código <strong style="color:{INK}">{codigo_s}</strong>. Ahora compartilo y empezá a cobrar comisiones.
      </p>
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"
             style="border:1px solid {GRAY_200};border-radius:12px;overflow:hidden;margin-bottom:20px">
        <tr>
          <td style="padding:14px 18px;border-bottom:1px solid {GRAY_200};background:{ACCENT_PALE} !important">
            <strong style="color:{INK}">1. Mandalo por WhatsApp</strong>
            <div style="color:{GRAY_600};font-size:13px;margin-top:4px">Un mensaje directo a un amigo convierte mejor que cualquier publicidad.</div>
          </td>
        </tr>
        <tr>
          <td style="padding:14px 18px;border-bottom:1px solid {GRAY_200}">
            <strong style="color:{INK}">2. Compartí un producto específico</strong>
            <div style="color:{GRAY_600};font-size:13px;margin-top:4px">Un link a un producto concreto convierte 3x más que el código solo.</div>
          </td>
        </tr>
        <tr>
          <td style="padding:14px 18px">
            <strong style="color:{INK}">3. Subilo a tus Stories</strong>
            <div style="color:{GRAY_600};font-size:13px;margin-top:4px">Una foto del producto + tu código en texto. Simple y efectivo.</div>
          </td>
        </tr>
      </table>
      <p style="color:{INK};font-weight:700;font-size:15px;margin:0 0 4px">Estos productos se venden solos:</p>
      <p style="color:{GRAY_600};font-size:13px;margin:0 0 4px">Tocá "Compartir" para enviar por WhatsApp con tu código incluido.</p>
      {prods_html}
      {_boton('Ver más productos para compartir', f"{site_url}/mi_cuenta")}
    """
    return _enviar(email, f"{nombre_s}, 3 tips para empezar a ganar con tu código - {TIENDA_NOMBRE}", _layout(cuerpo, marketing=True), is_marketing=True)


def enviar_email_nurturing_d7(nombre: str, email: str, codigo: str, stats: dict) -> dict:
    """D+7: Social proof + tabla de tiers."""
    nombre_s = _html.escape(nombre)
    codigo_s = _html.escape(codigo)
    env = Config.cargar_env()
    site_url = env.get('SITE_URL', 'https://elgadget.com.ar').rstrip('/')
    total_activos = stats.get('total_referidos_activos', 1)
    comisiones_mes = stats.get('comisiones_pagadas_mes', 0)
    cuerpo = f"""
      <h2 style="margin:0 0 6px;font-size:22px;color:{INK}">Otros ya están ganando, {nombre_s}</h2>
      <p style="color:{GRAY_600};margin:0 0 22px">
        Este mes, <strong style="color:{INK}">{total_activos} referidos</strong> ya generaron ventas y acumularon comisiones.
      </p>
      <div style="text-align:center;background:{GREEN_PALE};border-radius:12px;padding:20px;margin:0 0 24px">
        <span style="font-size:28px;font-weight:700;color:{GREEN_OK}">${comisiones_mes:,.0f}</span>
        <div style="color:{GREEN_OK};font-size:13px;font-weight:600;margin-top:4px">comisiones generadas este mes</div>
      </div>
      <p style="color:{INK};font-weight:700;font-size:15px;margin:0 0 12px">Mientras más vendés, más ganás:</p>
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"
             style="border:1px solid {GRAY_200};border-radius:12px;overflow:hidden;margin-bottom:24px">
        <tr style="background:{CREAM} !important">
          <td style="padding:10px 16px;border-bottom:1px solid {GRAY_200};font-size:12px;font-weight:700;color:{GRAY_600}">VENTAS/MES</td>
          <td style="padding:10px 16px;border-bottom:1px solid {GRAY_200};font-size:12px;font-weight:700;color:{GRAY_600}">TU COMISIÓN</td>
        </tr>
        <tr>
          <td style="padding:10px 16px;border-bottom:1px solid {GRAY_200}">Menos de 5</td>
          <td style="padding:10px 16px;border-bottom:1px solid {GRAY_200};font-weight:700;color:{INK}">7%</td>
        </tr>
        <tr>
          <td style="padding:10px 16px;border-bottom:1px solid {GRAY_200}">5 a 14</td>
          <td style="padding:10px 16px;border-bottom:1px solid {GRAY_200};font-weight:700;color:{INK}">11%</td>
        </tr>
        <tr>
          <td style="padding:10px 16px">15 o más</td>
          <td style="padding:10px 16px;font-weight:700;color:{ACCENT_DEEP}">15%</td>
        </tr>
      </table>
      <p style="color:{GRAY_600};font-size:13px;margin:0 0 8px">
        Tu código: <strong style="color:{INK}">{codigo_s}</strong>. Cuanto antes empieces a compartir en el mes, más ventas acumulás.
      </p>
      {_boton('Compartir mi código ahora', f"{site_url}/mi_cuenta")}
    """
    return _enviar(email, f"Ya hay {total_activos} referidos ganando este mes - {TIENDA_NOMBRE}", _layout(cuerpo, marketing=True), is_marketing=True)


def enviar_email_nurturing_d14(nombre: str, email: str, codigo: str, productos_top: list) -> dict:
    """D+14: Los 5 productos que más se venden."""
    nombre_s = _html.escape(nombre)
    codigo_s = _html.escape(codigo)
    env = Config.cargar_env()
    site_url = env.get('SITE_URL', 'https://elgadget.com.ar').rstrip('/')
    prods_html = _tabla_productos(productos_top[:5], codigo, site_url)
    cuerpo = f"""
      <h2 style="margin:0 0 6px;font-size:22px;color:{INK}">Los 5 productos que más se venden, {nombre_s}</h2>
      <p style="color:{GRAY_600};margin:0 0 8px">
        Estos son los productos que más ventas generan cuando los compartís.
        Tocá "Compartir" para enviar por WhatsApp con tu código <strong style="color:{INK}">{codigo_s}</strong>.
      </p>
      {prods_html}
      {_boton('Ver todo el catálogo', f"{site_url}/mi_cuenta")}
    """
    return _enviar(email, f"Los 5 productos que más se venden este mes - {TIENDA_NOMBRE}", _layout(cuerpo, marketing=True), is_marketing=True)


def enviar_email_primera_venta(nombre: str, email: str, codigo: str, monto_comision: float) -> dict:
    """Celebración: primera comisión del referido."""
    nombre_s = _html.escape(nombre)
    codigo_s = _html.escape(codigo)
    env = Config.cargar_env()
    site_url = env.get('SITE_URL', 'https://elgadget.com.ar').rstrip('/')
    cuerpo = f"""
      <h2 style="margin:0 0 6px;font-size:22px;color:{INK}">¡Tu primera comisión, {nombre_s}!</h2>
      <p style="color:{GRAY_600};margin:0 0 22px">
        Alguien compró usando tu código <strong style="color:{INK}">{codigo_s}</strong> y vos ganaste:
      </p>
      <div style="text-align:center;margin:28px 0">
        <span style="display:inline-block;background:{ACCENT};color:{INK};padding:20px 40px;
           border-radius:14px;font-weight:700;font-size:34px;letter-spacing:-1px">
          ${monto_comision:,.0f}
        </span>
      </div>
      <p style="color:{GRAY_600};margin:0 0 8px">
        Esta comisión se acumula para el cobro del <strong style="color:{INK}">día 5 del próximo mes</strong>.
      </p>
      <p style="color:{GRAY_600};margin:0 0 22px;font-size:13px">
        Esta es tu primera venta. Seguí compartiendo para subir de tier y ganar hasta el 15% por venta.
      </p>
      {_boton('Ver mi panel de comisiones', f"{site_url}/mi_cuenta")}
    """
    return _enviar(email, f"¡Ganaste ${monto_comision:,.0f} con tu primera venta! - {TIENDA_NOMBRE}", _layout(cuerpo))


def enviar_email_carrito_abandonado(orden: dict, items: list) -> dict:
    """Recordatorio: pedido sin pagar después de 24hs."""
    nombre_s = _html.escape(orden.get('nombre', ''))
    env = Config.cargar_env()
    site_url = env.get('SITE_URL', 'https://elgadget.com.ar').rstrip('/')
    filas_items = "".join(
        f"<tr>"
        f"<td style='padding:10px 12px;border-bottom:1px solid {GRAY_200};text-align:left'>"
        f"{_html.escape(item.get('producto_nombre', ''))}"
        f"<br><span style='color:{GRAY_600};font-size:12px'>Cantidad: {item.get('cantidad', 1)}</span>"
        f"</td>"
        f"<td style='padding:10px 12px;border-bottom:1px solid {GRAY_200};text-align:right;font-weight:600;white-space:nowrap;vertical-align:top'>"
        f"${item.get('subtotal', 0):,.2f}"
        f"</td>"
        f"</tr>"
        for item in items
    )
    cuerpo = f"""
      <h2 style="margin:0 0 6px;font-size:22px;color:{INK}">Tu pedido te está esperando, {nombre_s}</h2>
      <p style="color:{GRAY_600};margin:0 0 22px">
        Armaste un pedido pero todavía no completaste el pago. Te dejamos el resumen:
      </p>
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"
             style="border:1px solid {GRAY_200};border-radius:10px;overflow:hidden;margin-bottom:16px">
        <thead>
          <tr bgcolor="{INK}" style="background-color:{INK} !important">
            <th style="padding:10px 12px;text-align:left;font-size:11px;letter-spacing:0.5px;text-transform:uppercase;color:{WHITE} !important">Producto</th>
            <th style="padding:10px 12px;text-align:right;font-size:11px;letter-spacing:0.5px;text-transform:uppercase;color:{WHITE} !important">Subtotal</th>
          </tr>
        </thead>
        <tbody>{filas_items}</tbody>
      </table>
      <p style="text-align:right;font-weight:700;font-size:18px;margin:0 0 24px;color:{INK}">
        Total: ${orden.get('total', 0):,.2f}
      </p>
      {_boton('Volver a la tienda', site_url)}
      <p style="color:{GRAY_600};font-size:12px;margin:16px 0 0;text-align:center">
        Envío a todo el país · Pagás con MercadoPago · 10 días de arrepentimiento
      </p>
      <p style="color:{GRAY_600};font-size:11px;margin:12px 0 0;text-align:center">
        Si ya completaste el pago, ignorá este email.
      </p>
    """
    return _enviar(orden['email'], f"Tu pedido #{orden.get('id', '')} te espera - {TIENDA_NOMBRE}", _layout(cuerpo, marketing=True), is_marketing=True)


def enviar_email_invitar_referido(nombre: str, email: str) -> dict:
    """Post-compra: invitación a sumarse al programa de referidos."""
    nombre_s = _html.escape(nombre)
    env = Config.cargar_env()
    site_url = env.get('SITE_URL', 'https://elgadget.com.ar').rstrip('/')
    cuerpo = f"""
      <h2 style="margin:0 0 6px;font-size:22px;color:{INK}">Ganá plata compartiendo El Gadget, {nombre_s}</h2>
      <p style="color:{GRAY_600};margin:0 0 22px">
        Sumate al programa de referidos: compartí tu código personalizado y ganá hasta el
        <strong style="color:{INK}">15% de comisión</strong> por cada venta que generes.
        Tus amigos obtienen hasta <strong style="color:{INK}">20% OFF</strong>.
      </p>
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"
             style="border:1px solid {GRAY_200};border-radius:12px;overflow:hidden;margin-bottom:24px">
        <tr>
          <td style="padding:16px 18px;border-bottom:1px solid {GRAY_200};background:{ACCENT_PALE} !important;text-align:center">
            <strong style="color:{INK};font-size:16px">1. Registrate</strong>
            <div style="color:{GRAY_600};font-size:13px;margin-top:4px">En 1 minuto tenés tu código</div>
          </td>
        </tr>
        <tr>
          <td style="padding:16px 18px;border-bottom:1px solid {GRAY_200};text-align:center">
            <strong style="color:{INK};font-size:16px">2. Compartí</strong>
            <div style="color:{GRAY_600};font-size:13px;margin-top:4px">Por WhatsApp, Instagram o donde quieras</div>
          </td>
        </tr>
        <tr>
          <td style="padding:16px 18px;text-align:center">
            <strong style="color:{INK};font-size:16px">3. Cobrá</strong>
            <div style="color:{GRAY_600};font-size:13px;margin-top:4px">Comisiones mensuales en tu cuenta</div>
          </td>
        </tr>
      </table>
      {_boton('Quiero ser referido', f"{site_url}/referidos")}
      <p style="color:{GRAY_600};font-size:12px;margin:12px 0 0;text-align:center">
        Sin inversión. Sin límites de referidos. Cobrás por cada venta.
      </p>
    """
    return _enviar(email, f"¿Te gustó tu compra? Ganá plata recomendándonos - {TIENDA_NOMBRE}", _layout(cuerpo, marketing=True), is_marketing=True)
