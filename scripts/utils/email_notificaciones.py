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

    # Bloque de ahorro con código de referido (si aplica)
    codigo_ref = orden.get('descuento_codigo', '') or ''
    descuento_monto = orden.get('descuento_monto', 0) or 0
    referido_ahorro_html = ""
    if codigo_ref and descuento_monto > 0:
        codigo_ref_s = _html.escape(codigo_ref)
        referido_ahorro_html = (
            f"<div style='margin:18px 0 0;padding:14px 18px;background:{ACCENT_PALE};"
            f"border-radius:10px;border:1px solid {GRAY_200};text-align:center'>"
            f"<span style='color:{INK};font-size:14px'>Usaste el código "
            f"<strong>{codigo_ref_s}</strong> y te ahorraste "
            f"<strong style=\"color:{GREEN_OK}\">${descuento_monto:,.0f}</strong> en esta compra.</span>"
            f"</div>"
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
      {referido_ahorro_html}
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
    """D+3: Social proof — resultados de otros referidos."""
    nombre_s = _html.escape(nombre)
    codigo_s = _html.escape(codigo)
    env = Config.cargar_env()
    site_url = env.get('SITE_URL', 'https://elgadget.com.ar').rstrip('/')
    cuerpo = f"""
      <h2 style="margin:0 0 6px;font-size:22px;color:{INK}">Referidos como vos ya están cobrando comisiones</h2>
      <p style="color:{GRAY_600};margin:0 0 22px">
        ¡Hola {nombre_s}! Mirá lo que están ganando otros referidos:
      </p>
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"
             style="border:1px solid {GRAY_200};border-radius:12px;overflow:hidden;margin-bottom:20px">
        <tr>
          <td style="padding:14px 18px;border-bottom:1px solid {GRAY_200};background:{GREEN_PALE} !important">
            <strong style="color:{GREEN_OK}">Carolina M. (CABA)</strong>
            <div style="color:{GRAY_600};font-size:13px;margin-top:4px">$9.800/mes compartiendo por WhatsApp</div>
          </td>
        </tr>
        <tr>
          <td style="padding:14px 18px;border-bottom:1px solid {GRAY_200}">
            <strong style="color:{INK}">Nico G. (4.100 seguidores)</strong>
            <div style="color:{GRAY_600};font-size:13px;margin-top:4px">$14.200 en su primer mes</div>
          </td>
        </tr>
        <tr>
          <td style="padding:14px 18px">
            <strong style="color:{INK}">Julieta S. (Rosario)</strong>
            <div style="color:{GRAY_600};font-size:13px;margin-top:4px">$8.900 vendiendo por catálogo de WhatsApp</div>
          </td>
        </tr>
      </table>
      <p style="color:{INK};font-weight:700;font-size:15px;margin:0 0 8px">¿Ya compartiste tu código?</p>
      <p style="color:{GRAY_600};margin:0 0 4px">
        Tu código: <strong style="color:{INK};font-size:16px">{codigo_s}</strong>
      </p>
      <p style="color:{GRAY_600};margin:0 0 22px;font-size:13px">
        Solo necesitás 1 venta para ver tu primera comisión.
        Pasale tu código a 3 personas hoy y fijate qué pasa.
      </p>
      {_boton('Ver mi panel', f"{site_url}/mi_cuenta")}
    """
    return _enviar(email, f"Referidos como vos ya están cobrando comisiones - {TIENDA_NOMBRE}", _layout(cuerpo, marketing=True), is_marketing=True)


def enviar_email_nurturing_d7(nombre: str, email: str, codigo: str, stats: dict) -> dict:
    """D+7: Tips para maximizar comisiones + progreso de tier."""
    nombre_s = _html.escape(nombre)
    codigo_s = _html.escape(codigo)
    env = Config.cargar_env()
    site_url = env.get('SITE_URL', 'https://elgadget.com.ar').rstrip('/')
    tier = stats.get('tier', 'base')
    porcentaje = stats.get('porcentaje', 7)
    ventas_mes = stats.get('ventas_mes', 0)
    siguiente_tier = stats.get('next_tier', 'Activo')
    faltan = stats.get('next_tier_en', 5)
    tier_label = {'base': 'Base', 'activo': 'Activo', 'top': 'Top'}.get(tier, 'Base')
    sig_label = {'activo': 'Activo', 'top': 'Top'}.get(siguiente_tier, 'Activo')
    cuerpo = f"""
      <h2 style="margin:0 0 6px;font-size:22px;color:{INK}">3 tips para maximizar tus comisiones</h2>
      <p style="color:{GRAY_600};margin:0 0 22px">
        ¡Hola {nombre_s}! 3 cosas que hacen los referidos que más ganan:
      </p>
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"
             style="border:1px solid {GRAY_200};border-radius:12px;overflow:hidden;margin-bottom:20px">
        <tr>
          <td style="padding:14px 18px;border-bottom:1px solid {GRAY_200};background:{ACCENT_PALE} !important">
            <strong style="color:{INK}">1. Comparten su código en el estado de WhatsApp</strong>
            <div style="color:{GRAY_600};font-size:13px;margin-top:4px">Se ve sin ser invasivo, dura 24hs y lo renuevan cada semana.</div>
          </td>
        </tr>
        <tr>
          <td style="padding:14px 18px;border-bottom:1px solid {GRAY_200}">
            <strong style="color:{INK}">2. Recomiendan productos que ya probaron</strong>
            <div style="color:{GRAY_600};font-size:13px;margin-top:4px">Recordá: tenés 50% OFF en tu primera compra para probar.</div>
          </td>
        </tr>
        <tr>
          <td style="padding:14px 18px">
            <strong style="color:{INK}">3. Mencionan el descuento, no el programa</strong>
            <div style="color:{GRAY_600};font-size:13px;margin-top:4px">"Te paso un código con 20% OFF" funciona mejor que "me anoté en un programa de referidos".</div>
          </td>
        </tr>
      </table>
      <p style="color:{INK};font-weight:700;font-size:15px;margin:0 0 12px">Tu progreso actual:</p>
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"
             style="border:1px solid {GRAY_200};border-radius:12px;overflow:hidden;margin-bottom:24px">
        <tr>
          <td style="padding:10px 16px;border-bottom:1px solid {GRAY_200};color:{GRAY_600}">Nivel</td>
          <td style="padding:10px 16px;border-bottom:1px solid {GRAY_200};font-weight:700;color:{INK}">{tier_label} ({porcentaje}%)</td>
        </tr>
        <tr>
          <td style="padding:10px 16px;border-bottom:1px solid {GRAY_200};color:{GRAY_600}">Ventas este mes</td>
          <td style="padding:10px 16px;border-bottom:1px solid {GRAY_200};font-weight:700;color:{INK}">{ventas_mes}</td>
        </tr>
        <tr>
          <td style="padding:10px 16px;color:{GRAY_600}">Para subir a {sig_label}</td>
          <td style="padding:10px 16px;font-weight:700;color:{ACCENT_DEEP}">{faltan} ventas más</td>
        </tr>
      </table>
      {_boton('Ver productos para recomendar', f"{site_url}/mi_cuenta")}
    """
    return _enviar(email, f"3 tips para maximizar tus comisiones - {TIENDA_NOMBRE}", _layout(cuerpo, marketing=True), is_marketing=True)


def enviar_email_nurturing_d14(nombre: str, email: str, codigo: str, productos_top: list, stats: dict = None) -> dict:
    """D+14: Re-engagement condicional según ventas (0 ventas vs 1+)."""
    nombre_s = _html.escape(nombre)
    codigo_s = _html.escape(codigo)
    env = Config.cargar_env()
    site_url = env.get('SITE_URL', 'https://elgadget.com.ar').rstrip('/')

    ventas = 0
    tier_label = 'Base'
    porcentaje = 7
    total_comisiones = 0
    faltan = 5
    sig_label = 'Activo'
    sig_pct = 11
    if stats:
        ventas = stats.get('ventas_mes', 0)
        tier_label = {'base': 'Base', 'activo': 'Activo', 'top': 'Top'}.get(stats.get('tier', 'base'), 'Base')
        porcentaje = stats.get('porcentaje', 7)
        total_comisiones = stats.get('total_comisiones', 0)
        faltan = stats.get('next_tier_en', 5)
        sig_label = {'activo': 'Activo', 'top': 'Top'}.get(stats.get('next_tier', 'activo'), 'Activo')
        sig_pct = stats.get('next_porcentaje', 11)

    if ventas == 0:
        # 0 ventas: re-engagement con social proof + textos listos
        cuerpo = f"""
          <h2 style="margin:0 0 6px;font-size:22px;color:{INK}">¿Necesitás una mano para arrancar?</h2>
          <p style="color:{GRAY_600};margin:0 0 22px">
            Hola {nombre_s}, sabemos que arrancar puede parecer difícil.
            Pero la mayoría de los referidos activos empezaron igual:
            compartiendo su código con 3-5 personas cercanas.
          </p>
          <div style="background:{GREEN_PALE};border-radius:12px;padding:16px 18px;margin:0 0 22px">
            <strong style="color:{GREEN_OK}">Carolina M.</strong>
            <span style="color:{GRAY_600};font-size:13px"> empezó pasándole el código a 3 amigas del jardín.</span>
            <div style="color:{GREEN_OK};font-size:13px;font-weight:600;margin-top:4px">En su primer mes cobró $6.200. Hoy lleva $9.800/mes.</div>
          </div>
          <p style="color:{INK};font-weight:700;font-size:15px;margin:0 0 8px">
            Tu código: <span style="font-size:18px">{codigo_s}</span>
          </p>
          <p style="color:{GRAY_600};margin:0 0 8px;font-size:13px">Texto listo para compartir:</p>
          <div style="background:{CREAM};border-radius:10px;padding:14px 16px;margin:0 0 22px;font-size:13px;color:{GRAY_600};border:1px solid {GRAY_200}">
            Les dejo mi código de descuento en El Gadget: <strong style="color:{INK}">{codigo_s}</strong><br>
            Hasta 20% OFF en auriculares, luces, gadgets y más.<br>
            elgadget.com.ar
          </div>
          <p style="color:{GRAY_600};margin:0 0 22px;font-size:13px">
            No tenés que venderle nada a nadie.
            Solo pasarles un código de descuento genuino.
          </p>
          {_boton('Ver productos más vendidos', site_url)}
        """
        subject = f"¿Necesitás una mano para arrancar? - {TIENDA_NOMBRE}"
    else:
        # 1+ ventas: celebración + progreso
        cerca_html = ""
        if faltan and faltan <= 5:
            cerca_html = f"""
          <p style="color:{ACCENT_DEEP};font-weight:600;font-size:14px;margin:0 0 22px">
            Dato: te faltan solo {faltan} ventas para subir a {sig_label}
            y empezar a ganar {sig_pct}% por venta.
          </p>"""
        cuerpo = f"""
          <h2 style="margin:0 0 6px;font-size:22px;color:{INK}">¡Vas bien, {nombre_s}! Mirá tu progreso</h2>
          <p style="color:{GRAY_600};margin:0 0 22px">
            En tus primeras 2 semanas como referido:
          </p>
          <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"
                 style="border:1px solid {GRAY_200};border-radius:12px;overflow:hidden;margin-bottom:20px">
            <tr>
              <td style="padding:10px 16px;border-bottom:1px solid {GRAY_200};color:{GRAY_600}">Ventas generadas</td>
              <td style="padding:10px 16px;border-bottom:1px solid {GRAY_200};font-weight:700;color:{INK}">{ventas}</td>
            </tr>
            <tr>
              <td style="padding:10px 16px;border-bottom:1px solid {GRAY_200};color:{GRAY_600}">Comisiones acumuladas</td>
              <td style="padding:10px 16px;border-bottom:1px solid {GRAY_200};font-weight:700;color:{GREEN_OK}">${total_comisiones:,.0f}</td>
            </tr>
            <tr>
              <td style="padding:10px 16px;color:{GRAY_600}">Nivel actual</td>
              <td style="padding:10px 16px;font-weight:700;color:{INK}">{tier_label} ({porcentaje}%)</td>
            </tr>
          </table>
          {cerca_html}
          <p style="color:{GRAY_600};margin:0 0 22px;font-size:13px">
            Seguí así. Cada código que compartís es una posible comisión.
          </p>
          {_boton('Ver mi panel', f"{site_url}/mi_cuenta")}
        """
        subject = f"¡Vas bien, {nombre_s}! Mirá tu progreso - {TIENDA_NOMBRE}"

    return _enviar(email, subject, _layout(cuerpo, marketing=True), is_marketing=True)


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


def enviar_email_activacion_d1(nombre: str, email: str, codigo: str, source: str = None) -> dict:
    """N4 — D+1: Activación del referido — código destacado + textos listos para compartir."""
    nombre_s = _html.escape(nombre)
    codigo_s = _html.escape(codigo)
    env = Config.cargar_env()
    site_url = env.get('SITE_URL', 'https://elgadget.com.ar').rstrip('/')

    cuerpo = f"""
      <h2 style="margin:0 0 6px;font-size:22px;color:{INK}">¡Hola {nombre_s}!</h2>
      <p style="color:{GRAY_600};margin:0 0 22px">
        Tu código de referido es:
      </p>
      <div style="text-align:center;margin:28px 0">
        <span style="display:inline-block;background:{INK};color:{ACCENT};padding:20px 40px;
           border-radius:14px;font-weight:700;font-size:28px;letter-spacing:2px">
          {codigo_s}
        </span>
      </div>
      <p style="color:{GRAY_600};margin:0 0 22px">
        Cuanto antes lo compartas, antes cobrás tu primera comisión.
      </p>
      <p style="color:{INK};font-weight:700;font-size:15px;margin:0 0 12px">Acá tenés 3 textos listos para copiar y pegar:</p>
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"
             style="border:1px solid {GRAY_200};border-radius:12px;overflow:hidden;margin-bottom:20px">
        <tr>
          <td style="padding:14px 18px;border-bottom:1px solid {GRAY_200};background:{ACCENT_PALE} !important">
            <strong style="color:{INK}">Para tu Story o estado de WhatsApp</strong>
            <div style="color:{GRAY_600};font-size:13px;margin-top:6px;background:{CREAM};padding:10px 12px;border-radius:8px">
              Les dejo mi código de descuento en El Gadget: <strong>{codigo_s}</strong><br>
              Hasta 20% OFF en auriculares, luces, gadgets y más.<br>
              elgadget.com.ar
            </div>
          </td>
        </tr>
        <tr>
          <td style="padding:14px 18px;border-bottom:1px solid {GRAY_200}">
            <strong style="color:{INK}">Para mandarle a un amigo/a</strong>
            <div style="color:{GRAY_600};font-size:13px;margin-top:6px;background:{CREAM};padding:10px 12px;border-radius:8px">
              Che, encontré esta tienda El Gadget que tiene cosas re buenas.
              Si querés comprar algo, usá mi código <strong>{codigo_s}</strong> y te hacen
              hasta 20% de descuento: elgadget.com.ar
            </div>
          </td>
        </tr>
        <tr>
          <td style="padding:14px 18px">
            <strong style="color:{INK}">Para un grupo de WhatsApp</strong>
            <div style="color:{GRAY_600};font-size:13px;margin-top:6px;background:{CREAM};padding:10px 12px;border-radius:8px">
              Les dejo un código de descuento de hasta 20% en El Gadget
              (tienen auriculares, luces, gadgets y más).
              Código: <strong>{codigo_s}</strong> en elgadget.com.ar
            </div>
          </td>
        </tr>
      </table>
      <p style="color:{GRAY_600};margin:0 0 22px;font-size:13px">
        Y no te olvides: tenés <strong style="color:{INK}">50% OFF</strong> en tu primera compra como referido.
        Probá un producto, usalo, y después recomendalo con conocimiento real.
      </p>
      {_boton('Comprar con 50% OFF', site_url)}
      {_boton('Ver mi panel', f"{site_url}/mi_cuenta")}
    """
    return _enviar(email, f"Tu código {codigo_s} está listo — compartilo ahora", _layout(cuerpo, marketing=True), is_marketing=True)


def enviar_email_notificacion_venta(nombre: str, email: str, codigo: str, comision: float,
                                    total_mes: float, tier: str, n_ventas: int,
                                    siguiente_tier: str, faltan: int) -> dict:
    """N1 — Notificación por cada venta generada (ventas #2+). Transaccional."""
    nombre_s = _html.escape(nombre)
    codigo_s = _html.escape(codigo)
    tier_label = {'base': 'Base', 'activo': 'Activo', 'top': 'Top'}.get(tier, 'Base')
    tier_pct = {'base': '7', 'activo': '11', 'top': '15'}.get(tier, '7')
    sig_label = _html.escape(siguiente_tier) if siguiente_tier else ''
    sig_pct = {'activo': '11', 'top': '15'}.get(siguiente_tier, '')
    env = Config.cargar_env()
    site_url = env.get('SITE_URL', 'https://elgadget.com.ar').rstrip('/')

    faltan_html = ""
    if siguiente_tier and faltan and faltan > 0:
        faltan_html = f"""
        <tr>
          <td style="padding:10px 16px;color:{GRAY_600}">Para subir a {sig_label} ({sig_pct}%)</td>
          <td style="padding:10px 16px;font-weight:700;color:{ACCENT_DEEP}">Te faltan {faltan} ventas</td>
        </tr>"""

    cuerpo = f"""
      <h2 style="margin:0 0 6px;font-size:22px;color:{INK}">¡Nueva venta con tu código!</h2>
      <p style="color:{GRAY_600};margin:0 0 22px">
        ¡{nombre_s}! Alguien compró con tu código <strong style="color:{INK}">{codigo_s}</strong>.
      </p>
      <div style="text-align:center;margin:28px 0">
        <span style="display:inline-block;background:{ACCENT};color:{INK};padding:20px 40px;
           border-radius:14px;font-weight:700;font-size:34px;letter-spacing:-1px">
          +${comision:,.0f}
        </span>
        <div style="color:{GRAY_600};font-size:13px;margin-top:6px">Tu comisión por esta venta</div>
      </div>
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"
             style="border:1px solid {GRAY_200};border-radius:12px;overflow:hidden;margin-bottom:24px">
        <tr>
          <td style="padding:10px 16px;border-bottom:1px solid {GRAY_200};color:{GRAY_600}">Total acumulado este mes</td>
          <td style="padding:10px 16px;border-bottom:1px solid {GRAY_200};font-weight:700;color:{GREEN_OK}">${total_mes:,.0f}</td>
        </tr>
        <tr>
          <td style="padding:10px 16px;border-bottom:1px solid {GRAY_200};color:{GRAY_600}">Nivel actual</td>
          <td style="padding:10px 16px;border-bottom:1px solid {GRAY_200};font-weight:700;color:{INK}">{tier_label} ({tier_pct}%)</td>
        </tr>
        <tr>
          <td style="padding:10px 16px;{'border-bottom:1px solid ' + GRAY_200 + ';' if faltan_html else ''}color:{GRAY_600}">Ventas este mes</td>
          <td style="padding:10px 16px;{'border-bottom:1px solid ' + GRAY_200 + ';' if faltan_html else ''}font-weight:700;color:{INK}">{n_ventas}</td>
        </tr>
        {faltan_html}
      </table>
      {_boton('Ver mi panel', f"{site_url}/mi_cuenta")}
    """
    return _enviar(email, f"¡Nueva venta con tu código! Ganaste ${comision:,.0f}", _layout(cuerpo))


def enviar_email_ascenso_tier(nombre: str, email: str, codigo: str,
                              tier_anterior: str, tier_nuevo: str,
                              pct_anterior: float, pct_nuevo: float) -> dict:
    """N2 — Ascenso de tier. Transaccional."""
    nombre_s = _html.escape(nombre)
    tier_ant_label = {'base': 'Base', 'activo': 'Activo', 'top': 'Top'}.get(tier_anterior, tier_anterior)
    tier_new_label = {'base': 'Base', 'activo': 'Activo', 'top': 'Top'}.get(tier_nuevo, tier_nuevo)
    env = Config.cargar_env()
    site_url = env.get('SITE_URL', 'https://elgadget.com.ar').rstrip('/')

    antes_15k = round(15000 * (pct_anterior / 100))
    ahora_15k = round(15000 * (pct_nuevo / 100))
    antes_25k = round(25000 * (pct_anterior / 100))
    ahora_25k = round(25000 * (pct_nuevo / 100))

    cuerpo = f"""
      <h2 style="margin:0 0 6px;font-size:22px;color:{INK}">¡Felicitaciones {nombre_s}!</h2>
      <p style="color:{GRAY_600};margin:0 0 22px">
        Subiste de nivel en el programa de referidos:
      </p>
      <div style="text-align:center;margin:28px 0">
        <span style="display:inline-block;background:{CREAM};color:{GRAY_600};padding:12px 20px;
           border-radius:10px;font-weight:600;font-size:16px;text-decoration:line-through">
          {tier_ant_label} {pct_anterior:.0f}%
        </span>
        <span style="display:inline-block;padding:0 10px;color:{GRAY_600};font-size:20px">→</span>
        <span style="display:inline-block;background:{ACCENT};color:{INK};padding:12px 20px;
           border-radius:10px;font-weight:700;font-size:16px">
          {tier_new_label} {pct_nuevo:.0f}%
        </span>
      </div>
      <p style="color:{GRAY_600};margin:0 0 22px">
        A partir de ahora, cada venta te deja más comisión.
      </p>
      <p style="color:{INK};font-weight:700;font-size:15px;margin:0 0 12px">Ejemplo:</p>
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"
             style="border:1px solid {GRAY_200};border-radius:12px;overflow:hidden;margin-bottom:20px">
        <tr>
          <td style="padding:10px 16px;border-bottom:1px solid {GRAY_200};color:{GRAY_600}">Venta de $15.000</td>
          <td style="padding:10px 16px;border-bottom:1px solid {GRAY_200};color:{GRAY_600};text-decoration:line-through">${antes_15k:,}</td>
          <td style="padding:10px 16px;border-bottom:1px solid {GRAY_200};font-weight:700;color:{GREEN_OK}">${ahora_15k:,}</td>
        </tr>
        <tr>
          <td style="padding:10px 16px;color:{GRAY_600}">Venta de $25.000</td>
          <td style="padding:10px 16px;color:{GRAY_600};text-decoration:line-through">${antes_25k:,}</td>
          <td style="padding:10px 16px;font-weight:700;color:{GREEN_OK}">${ahora_25k:,}</td>
        </tr>
      </table>
      <p style="color:{GRAY_600};margin:0 0 22px;font-size:13px">
        Y recordá: este nivel no se resetea. Es tuyo para siempre.
      </p>
      {_boton('Ver mi panel', f"{site_url}/mi_cuenta")}
    """
    return _enviar(email, f"¡Subiste a {tier_new_label}! Tu comisión ahora es {pct_nuevo:.0f}%", _layout(cuerpo))


def enviar_email_postcompra_50(nombre: str, email: str, codigo: str, producto_nombre: str) -> dict:
    """N3 — Post-compra 50% OFF: activar al referido como recomendador. Transaccional."""
    nombre_s = _html.escape(nombre)
    codigo_s = _html.escape(codigo)
    prod_s = _html.escape(producto_nombre)
    env = Config.cargar_env()
    site_url = env.get('SITE_URL', 'https://elgadget.com.ar').rstrip('/')

    cuerpo = f"""
      <h2 style="margin:0 0 6px;font-size:22px;color:{INK}">Ya tenés tu {prod_s} — ahora recomendalo con experiencia real</h2>
      <p style="color:{GRAY_600};margin:0 0 22px">
        ¡{nombre_s}! Tu {prod_s} ya está en camino.
      </p>
      <p style="color:{GRAY_600};margin:0 0 22px">
        Ahora que lo vas a probar, podés recomendarlo con experiencia propia.
        Tus seguidores/amigos notan cuando recomendás algo que realmente usás.
      </p>
      <p style="color:{INK};font-weight:700;font-size:15px;margin:0 0 12px">Textos listos para compartir:</p>
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"
             style="border:1px solid {GRAY_200};border-radius:12px;overflow:hidden;margin-bottom:20px">
        <tr>
          <td style="padding:14px 18px;border-bottom:1px solid {GRAY_200};background:{ACCENT_PALE} !important">
            <strong style="color:{INK}">Para Story/WhatsApp</strong>
            <div style="color:{GRAY_600};font-size:13px;margin-top:6px;background:{CREAM};padding:10px 12px;border-radius:8px">
              Compré {prod_s} en El Gadget y está buenísimo.
              Si querés uno con descuento, usá mi código <strong>{codigo_s}</strong>:
              elgadget.com.ar
            </div>
          </td>
        </tr>
        <tr>
          <td style="padding:14px 18px">
            <strong style="color:{INK}">Para DM/mensaje directo</strong>
            <div style="color:{GRAY_600};font-size:13px;margin-top:6px;background:{CREAM};padding:10px 12px;border-radius:8px">
              Che, te recomiendo esto que compré en El Gadget: {prod_s}.
              Con mi código <strong>{codigo_s}</strong> te hacen hasta 20% OFF: elgadget.com.ar
            </div>
          </td>
        </tr>
      </table>
      <p style="color:{GRAY_600};margin:0 0 22px;font-size:13px">
        Cada persona que compre con tu código te genera entre 7% y 15% de comisión.
      </p>
      {_boton('Ver todos los productos', site_url)}
    """
    return _enviar(email, f"Ya tenés tu {prod_s} — ahora recomendalo con experiencia real", _layout(cuerpo))


def enviar_email_ultimo_recordatorio_d30(nombre: str, email: str, codigo: str) -> dict:
    """N5 — Último recordatorio D+30 (0 ventas). Nurturing/marketing."""
    nombre_s = _html.escape(nombre)
    codigo_s = _html.escape(codigo)
    env = Config.cargar_env()
    site_url = env.get('SITE_URL', 'https://elgadget.com.ar').rstrip('/')

    cuerpo = f"""
      <h2 style="margin:0 0 6px;font-size:22px;color:{INK}">Tu código {codigo_s} sigue activo</h2>
      <p style="color:{GRAY_600};margin:0 0 22px">
        Hola {nombre_s}, tu código de referido <strong style="color:{INK}">{codigo_s}</strong> sigue listo para usar.
        No tiene vencimiento — podés compartirlo cuando quieras.
      </p>
      <p style="color:{GRAY_600};margin:0 0 8px;font-size:13px">
        Si en algún momento querés ganar comisiones recomendando
        productos de El Gadget, acá te dejamos un texto listo:
      </p>
      <div style="background:{CREAM};border-radius:10px;padding:14px 16px;margin:0 0 22px;font-size:13px;color:{GRAY_600};border:1px solid {GRAY_200}">
        Les dejo mi código de descuento en El Gadget: <strong style="color:{INK}">{codigo_s}</strong><br>
        Hasta 20% OFF en auriculares, luces, gadgets y más.<br>
        elgadget.com.ar
      </div>
      <p style="color:{GRAY_600};margin:0 0 22px;font-size:13px">
        Sin presión. Cuando quieras, estamos.
      </p>
      {_boton('Ver productos', site_url)}
    """
    return _enviar(email, f"Tu código {codigo_s} sigue activo", _layout(cuerpo, marketing=True), is_marketing=True)


def enviar_email_carrito_abandonado_2(orden: dict, items: list) -> dict:
    """N6 — Carrito abandonado #2 (+24h). Nurturing/marketing."""
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

    codigo_ref = orden.get('descuento_codigo', '') or ''
    descuento_monto = orden.get('descuento_monto', 0) or 0
    ahorro_html = ""
    if codigo_ref and descuento_monto > 0:
        codigo_ref_s = _html.escape(codigo_ref)
        ahorro_html = (
            f"<p style='text-align:center;color:{GREEN_OK};font-weight:600;font-size:14px;margin:0 0 16px'>"
            f"Con el código {codigo_ref_s} aplicado, te estás ahorrando ${descuento_monto:,.0f}.</p>"
        )

    cuerpo = f"""
      <h2 style="margin:0 0 6px;font-size:22px;color:{INK}">Tu carrito en El Gadget te está esperando</h2>
      <p style="color:{GRAY_600};margin:0 0 22px">
        Hola {nombre_s}, dejaste estos productos en tu carrito:
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
      <p style="text-align:right;font-weight:700;font-size:18px;margin:0 0 16px;color:{INK}">
        Total: ${orden.get('total', 0):,.2f}
      </p>
      {ahorro_html}
      {_boton('Completar mi compra', site_url)}
      <p style="color:{GRAY_600};font-size:12px;margin:16px 0 0;text-align:center">
        ¿Tenés alguna duda? Respondé este email o escribinos por WhatsApp.
      </p>
    """
    return _enviar(orden['email'], f"Tu carrito en El Gadget te está esperando", _layout(cuerpo, marketing=True), is_marketing=True)


def enviar_email_carrito_abandonado_3(orden: dict, items: list) -> dict:
    """N7 — Carrito abandonado #3 (+72h). Último recordatorio. Nurturing/marketing."""
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
      <h2 style="margin:0 0 6px;font-size:22px;color:{INK}">Último recordatorio — tu carrito se vacía pronto</h2>
      <p style="color:{GRAY_600};margin:0 0 22px">
        {nombre_s}, tus productos siguen esperándote:
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
      <p style="text-align:right;font-weight:700;font-size:18px;margin:0 0 16px;color:{INK}">
        Total: ${orden.get('total', 0):,.2f}
      </p>
      <p style="color:{GRAY_600};margin:0 0 22px;font-size:13px">
        Los precios y el stock pueden cambiar. Si te interesaban,
        este es un buen momento para completar la compra.
      </p>
      {_boton('Ir a mi carrito', site_url)}
      <p style="color:{GRAY_600};font-size:11px;margin:12px 0 0;text-align:center">
        Si ya completaste el pago, ignorá este email.
      </p>
    """
    return _enviar(orden['email'], f"Último recordatorio — tu carrito se vacía pronto", _layout(cuerpo, marketing=True), is_marketing=True)


def enviar_email_review_request(nombre: str, email: str, producto_nombre: str) -> dict:
    """N8 — Review request post-entrega. Nurturing/marketing."""
    nombre_s = _html.escape(nombre)
    prod_s = _html.escape(producto_nombre)
    env = Config.cargar_env()
    site_url = env.get('SITE_URL', 'https://elgadget.com.ar').rstrip('/')

    cuerpo = f"""
      <h2 style="margin:0 0 6px;font-size:22px;color:{INK}">¿Qué te pareció tu {prod_s}?</h2>
      <p style="color:{GRAY_600};margin:0 0 22px">
        ¡Hola {nombre_s}! Ya pasaron unos días desde que recibiste tu {prod_s}.
        ¿Qué te pareció?
      </p>
      <p style="color:{GRAY_600};margin:0 0 22px;font-size:13px">
        Tu opinión nos ayuda a mejorar y le sirve a otros compradores.
      </p>
      {_boton('Contanos tu experiencia', f"mailto:tienda@elgadget.com.ar?subject=Mi+experiencia+con+{prod_s}")}
      <p style="color:{GRAY_600};font-size:13px;margin:0;text-align:center">
        ¡Gracias por confiar en El Gadget!
      </p>
    """
    return _enviar(email, f"¿Qué te pareció tu {prod_s}?", _layout(cuerpo, marketing=True), is_marketing=True)


def enviar_email_repeat_purchase(nombre: str, email: str, productos_top: list, codigo: str = None) -> dict:
    """N9 — Repeat purchase D+30 post-compra. Nurturing/marketing."""
    nombre_s = _html.escape(nombre)
    env = Config.cargar_env()
    site_url = env.get('SITE_URL', 'https://elgadget.com.ar').rstrip('/')

    codigo_html = ""
    if codigo:
        codigo_s = _html.escape(codigo)
        codigo_html = f"""
      <p style="color:{GRAY_600};margin:0 0 22px;font-size:13px">
        Recordá que con tu código <strong style="color:{INK}">{codigo_s}</strong> tenés hasta 20% OFF.
      </p>"""

    cards = ""
    for p in (productos_top or [])[:3]:
        p_nombre = _html.escape(p.get('nombre', ''))
        p_precio = p.get('precio_venta', 0)
        p_img = _html.escape(p.get('imagen_principal') or '')
        p_slug = (p.get('url_amigable') or '').strip()
        p_url = f"{site_url}/producto/{p_slug}/" if p_slug else site_url
        cards += f"""
        <tr>
          <td style="padding:12px;border-bottom:1px solid {GRAY_200};width:60px;vertical-align:top">
            <img src="{p_img}" width="56" height="56" style="border-radius:8px;object-fit:cover;display:block;background:{CREAM}" alt="">
          </td>
          <td style="padding:12px;border-bottom:1px solid {GRAY_200};vertical-align:top">
            <a href="{p_url}" style="color:{INK};text-decoration:none;font-weight:600;font-size:13.5px">{p_nombre}</a><br>
            <span style="color:{ACCENT_DEEP};font-weight:700;font-size:14px">${p_precio:,.0f}</span>
          </td>
        </tr>"""

    prods_html = ""
    if cards:
        prods_html = f"""
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"
             style="border:1px solid {GRAY_200};border-radius:12px;overflow:hidden;margin:20px 0">
        {cards}
      </table>"""

    cuerpo = f"""
      <h2 style="margin:0 0 6px;font-size:22px;color:{INK}">Novedades en El Gadget que te pueden gustar</h2>
      <p style="color:{GRAY_600};margin:0 0 22px">
        ¡Hola {nombre_s}! Desde tu última compra agregamos productos nuevos que te pueden interesar:
      </p>
      {prods_html}
      {codigo_html}
      {_boton('Ver novedades', site_url)}
    """
    return _enviar(email, f"Novedades en El Gadget que te pueden gustar", _layout(cuerpo, marketing=True), is_marketing=True)


def enviar_email_winback(nombre: str, email: str, dias_inactivo: int, es_referido: bool,
                         codigo: str = None) -> dict:
    """N10 — Win-back D+60 sin actividad. Nurturing/marketing."""
    nombre_s = _html.escape(nombre)
    env = Config.cargar_env()
    site_url = env.get('SITE_URL', 'https://elgadget.com.ar').rstrip('/')

    if es_referido and codigo:
        codigo_s = _html.escape(codigo)
        referido_html = f"""
      <p style="color:{GRAY_600};margin:0 0 22px;font-size:13px">
        Tu código <strong style="color:{INK}">{codigo_s}</strong> sigue activo. Compartilo cuando quieras.
      </p>
      {_boton('Ver novedades', site_url)}"""
    else:
        referido_html = f"""
      <div style="background:{ACCENT_PALE};border-radius:12px;padding:16px 18px;margin:0 0 22px;border:1px solid {GRAY_200}">
        <strong style="color:{INK}">¿Sabías que podés ganar plata recomendando productos?</strong>
        <p style="color:{GRAY_600};font-size:13px;margin:8px 0 0">
          Con nuestro programa de referidos ganás entre 7% y 15%
          de comisión por cada venta. Sin inversión.
        </p>
      </div>
      {_boton('Conocer el programa', f"{site_url}/referidos")}"""

    cuerpo = f"""
      <h2 style="margin:0 0 6px;font-size:22px;color:{INK}">Hace rato que no te vemos, {nombre_s}</h2>
      <p style="color:{GRAY_600};margin:0 0 22px">
        ¡Hola {nombre_s}! Pasaron {dias_inactivo} días desde tu última compra en El Gadget.
        Queríamos contarte que tenemos novedades:
      </p>
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"
             style="border:1px solid {GRAY_200};border-radius:12px;overflow:hidden;margin-bottom:20px">
        <tr>
          <td style="padding:12px 18px;border-bottom:1px solid {GRAY_200}">
            <span style="color:{INK};font-weight:600">Envío en 48hs a CABA/GBA</span>
          </td>
        </tr>
        <tr>
          <td style="padding:12px 18px;border-bottom:1px solid {GRAY_200}">
            <span style="color:{INK};font-weight:600">10 días de devolución, 6 meses de garantía</span>
          </td>
        </tr>
        <tr>
          <td style="padding:12px 18px">
            <span style="color:{INK};font-weight:600">Productos nuevos en el catálogo</span>
          </td>
        </tr>
      </table>
      {referido_html}
      <div style="text-align:center;background:{ACCENT_PALE};border-radius:12px;padding:16px;margin:20px 0">
        <span style="font-size:13px;color:{GRAY_600}">Te dejamos un cupón especial:</span><br>
        <span style="font-weight:700;font-size:20px;color:{INK}">VUELVO10</span><br>
        <span style="font-size:13px;color:{GRAY_600}">10% de descuento en tu próxima compra (válido por 7 días)</span>
      </div>
    """
    return _enviar(email, f"Hace rato que no te vemos, {nombre_s}", _layout(cuerpo, marketing=True), is_marketing=True)


def enviar_email_venta_admin(orden: dict, items: list, factura: dict = None) -> dict:
    """Notifica al admin de una nueva venta aprobada con TODOS los datos del checkout."""
    env = Config.cargar_env()
    admin_email = env.get('ADMIN_EMAIL', 'damianes1802@gmail.com')

    nombre = _html.escape(orden.get('nombre', 'Cliente'))
    apellido = _html.escape(orden.get('apellido', '') or '')
    nombre_completo = f"{nombre} {apellido}".strip()
    email_cliente = _html.escape(orden.get('email', ''))
    telefono = _html.escape(orden.get('telefono', '') or '')
    cuit_dni = _html.escape(orden.get('cuit_dni', '') or '')
    orden_id = orden.get('id', '?')
    total = orden.get('total', 0)
    costo_envio = orden.get('costo_envio', 0)
    zona = _html.escape(orden.get('zona_envio', 'No especificada'))
    codigo_ref = _html.escape(orden.get('descuento_codigo', '') or '')

    # Dirección completa
    calle = _html.escape(orden.get('calle', '') or '')
    altura = _html.escape(orden.get('altura', '') or '')
    piso = _html.escape(orden.get('piso', '') or '')
    depto = _html.escape(orden.get('departamento', '') or '')
    provincia = _html.escape(orden.get('provincia', '') or '')
    partido = _html.escape(orden.get('partido', '') or '')
    ciudad = _html.escape(orden.get('ciudad', '') or '')
    cp = _html.escape(orden.get('codigo_postal', '') or '')

    dir_line = f"{calle} {altura}".strip()
    if piso:
        dir_line += f", Piso {piso}"
    if depto:
        dir_line += f" Dpto {depto}"
    localidad = ", ".join(p for p in [ciudad, partido, provincia] if p)
    if cp:
        localidad += f" (CP {cp})"

    filas = "".join(
        f"<tr>"
        f"<td style='padding:8px 12px;border-bottom:1px solid {GRAY_200};font-size:14px'>"
        f"{_html.escape(item.get('producto_nombre', ''))}"
        f"<br><span style='color:{GRAY_600};font-size:12px'>x{item.get('cantidad', 1)}</span>"
        f"</td>"
        f"<td style='padding:8px 12px;border-bottom:1px solid {GRAY_200};text-align:right;font-weight:600;font-size:14px'>"
        f"${item.get('subtotal', 0):,.2f}"
        f"</td>"
        f"</tr>"
        for item in items
    )

    referido_html = ""
    if codigo_ref:
        referido_html = (
            f"<tr><td style='padding:6px 12px;color:{GRAY_600}'>Codigo referido</td>"
            f"<td style='padding:6px 12px;text-align:right;font-weight:600;color:{GREEN_OK}'>{codigo_ref}</td></tr>"
        )

    factura_html = ""
    if factura and not factura.get('error'):
        factura_html = (
            f"<p style='margin:12px 0 0;padding:10px 14px;background:{GREEN_PALE};"
            f"color:{GREEN_OK};border-radius:8px;font-size:13px;font-weight:600'>"
            f"Factura C N.° {factura['punto_venta']:04d}-{factura['numero']:08d} "
            f"— CAE {factura['cae']}</p>"
        )
    elif factura and factura.get('error'):
        factura_html = (
            f"<p style='margin:12px 0 0;padding:10px 14px;background:#FFF0F0;"
            f"color:#C0392B;border-radius:8px;font-size:13px;font-weight:600'>"
            f"Error AFIP: {_html.escape(str(factura['error'])[:100])}</p>"
        )

    cuerpo = f"""
      <h2 style="margin:0 0 6px;font-size:22px;color:{INK}">Nueva venta #{orden_id}</h2>

      <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"
             style="border:1px solid {GRAY_200};border-radius:10px;overflow:hidden;margin-bottom:16px">
        <tr bgcolor="{ACCENT_PALE}" style="background-color:{ACCENT_PALE} !important">
          <td colspan="2" style="padding:10px 12px;font-weight:700;font-size:13px;text-transform:uppercase;letter-spacing:0.5px;color:{INK}">Datos del cliente</td>
        </tr>
        <tr>
          <td style="padding:6px 12px;color:{GRAY_600};font-size:13px;width:120px">Nombre</td>
          <td style="padding:6px 12px;font-weight:600;font-size:14px">{nombre_completo}</td>
        </tr>
        <tr>
          <td style="padding:6px 12px;color:{GRAY_600};font-size:13px">Email</td>
          <td style="padding:6px 12px;font-size:14px">{email_cliente}</td>
        </tr>
        <tr>
          <td style="padding:6px 12px;color:{GRAY_600};font-size:13px">Telefono</td>
          <td style="padding:6px 12px;font-size:14px">{telefono}</td>
        </tr>
        <tr>
          <td style="padding:6px 12px;color:{GRAY_600};font-size:13px">DNI/CUIT</td>
          <td style="padding:6px 12px;font-size:14px">{cuit_dni}</td>
        </tr>
        <tr bgcolor="{ACCENT_PALE}" style="background-color:{ACCENT_PALE} !important">
          <td colspan="2" style="padding:10px 12px;font-weight:700;font-size:13px;text-transform:uppercase;letter-spacing:0.5px;color:{INK}">Direccion de envio</td>
        </tr>
        <tr>
          <td style="padding:6px 12px;color:{GRAY_600};font-size:13px">Direccion</td>
          <td style="padding:6px 12px;font-size:14px">{dir_line}</td>
        </tr>
        <tr>
          <td style="padding:6px 12px;color:{GRAY_600};font-size:13px">Localidad</td>
          <td style="padding:6px 12px;font-size:14px">{localidad}</td>
        </tr>
        <tr>
          <td style="padding:6px 12px;color:{GRAY_600};font-size:13px">Zona envio</td>
          <td style="padding:6px 12px;font-size:14px">{zona}</td>
        </tr>
      </table>

      <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"
             style="border:1px solid {GRAY_200};border-radius:10px;overflow:hidden;margin-bottom:8px">
        <thead>
          <tr bgcolor="{INK}" style="background-color:{INK} !important">
            <th style="padding:8px 12px;text-align:left;font-size:11px;letter-spacing:0.5px;text-transform:uppercase;color:{WHITE} !important">Producto</th>
            <th style="padding:8px 12px;text-align:right;font-size:11px;letter-spacing:0.5px;text-transform:uppercase;color:{WHITE} !important">Subtotal</th>
          </tr>
        </thead>
        <tbody>{filas}</tbody>
      </table>

      <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"
             style="font-size:14px;margin-bottom:12px">
        <tr>
          <td style="padding:6px 12px;color:{GRAY_600}">Envio ({zona})</td>
          <td style="padding:6px 12px;text-align:right;font-weight:600">${costo_envio:,.2f}</td>
        </tr>
        {referido_html}
        <tr style="border-top:2px solid {INK}">
          <td style="padding:10px 12px;font-weight:700;font-size:18px;color:{INK}">Total</td>
          <td style="padding:10px 12px;text-align:right;font-weight:700;font-size:18px;color:{INK}">${total:,.2f}</td>
        </tr>
      </table>

      {factura_html}
    """

    return _enviar(admin_email, f"[VENTA] #{orden_id} · ${total:,.0f} · {nombre} - {TIENDA_NOMBRE}", _layout(cuerpo))
