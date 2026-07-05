#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PDF DE FACTURA C CON QR (RG 4892/2020)

Genera la representación gráfica en PDF de una Factura C emitida vía
web services, incluyendo el código QR obligatorio de ARCA. El PDF se
adjunta al email de confirmación de compra.

Datos del emisor: se leen de config/.env (AFIP_RAZON_SOCIAL,
AFIP_DOMICILIO_COMERCIAL, AFIP_INICIO_ACTIVIDADES, AFIP_IIBB). Si faltan,
se usan valores genéricos de la tienda y el PDF igual se genera.
"""

import base64
import io
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))
from utils.logger import get_logger
from utils.config import Config

logger = get_logger('factura_pdf')

# Paleta de marca (igual a email_notificaciones.py / style.css)
INK = '#14151A'
ACCENT = '#FFC700'
GRAY_600 = '#6F6A63'
GRAY_200 = '#E5E2DD'
CREAM = '#F7F6F3'

TIENDA_NOMBRE = 'El Gadget'
TIENDA_URL = 'elgadget.com.ar'

QR_URL_BASE = 'https://www.afip.gob.ar/fe/qr/?p='

COND_IVA_EMISOR = 'Responsable Monotributo'
COND_IVA_RECEPTOR = 'Consumidor Final'

DOC_TIPO_LABELS = {80: 'CUIT', 96: 'DNI', 99: ''}


def _fmt_fecha(valor: str) -> str:
    """Normaliza 'YYYYMMDD' o 'YYYY-MM-DD' a 'DD/MM/YYYY'."""
    v = str(valor or '').strip().replace('-', '')
    if len(v) == 8 and v.isdigit():
        return f'{v[6:8]}/{v[4:6]}/{v[0:4]}'
    return str(valor)


def _fmt_monto(valor: float) -> str:
    """Formato monetario argentino: $28.990,00"""
    s = f'{float(valor):,.2f}'
    return '$' + s.translate(str.maketrans(',.', '.,'))


def _armar_url_qr(cuit_emisor: int, factura: dict, total: float) -> str:
    """URL del QR según especificación RG 4892/2020."""
    datos = {
        'ver': 1,
        'fecha': factura.get('fecha') or datetime.now().strftime('%Y-%m-%d'),
        'cuit': int(cuit_emisor),
        'ptoVta': int(factura['punto_venta']),
        'tipoCmp': int(factura.get('tipo', 11)),
        'nroCmp': int(factura['numero']),
        'importe': round(float(total), 2),
        'moneda': 'PES',
        'ctz': 1,
        'tipoDocRec': int(factura.get('doc_tipo', 99)),
        'nroDocRec': int(factura.get('doc_nro', 0)),
        'tipoCodAut': 'E',
        'codAut': int(factura['cae']),
    }
    payload = base64.b64encode(json.dumps(datos).encode()).decode()
    return QR_URL_BASE + payload


def generar_pdf_factura(orden: dict, items: list, factura: dict) -> bytes:
    """
    Genera el PDF de la Factura C y lo devuelve como bytes.

    Args:
        orden: dict de la orden + cliente (nombre, apellido, cuit_dni,
               direcciones, total, descuento_monto, costo_envio)
        items: lista de dicts (producto_nombre, cantidad, precio_unitario, subtotal)
        factura: dict devuelto por generar_factura_c (punto_venta, numero,
                 cae, cae_vencimiento, fecha, doc_tipo, doc_nro)

    Returns:
        bytes del PDF, o lanza excepción si falla (el caller decide si es fatal).
    """
    import qrcode
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.colors import HexColor
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfgen import canvas as rl_canvas

    env = Config.cargar_env()
    cuit_emisor = env.get('AFIP_CUIT', '')
    razon_social = env.get('AFIP_RAZON_SOCIAL', '') or TIENDA_NOMBRE
    domicilio = env.get('AFIP_DOMICILIO_COMERCIAL', '')
    inicio_act = env.get('AFIP_INICIO_ACTIVIDADES', '')
    iibb = env.get('AFIP_IIBB', '') or str(cuit_emisor)

    # Si la factura fue reconstruida desde la DB no trae doc_tipo/doc_nro:
    # derivarlos del cuit_dni de la orden para que el QR quede correcto.
    if 'doc_tipo' not in factura:
        from utils.facturacion_afip import _doc_tipo_y_nro
        doc_tipo_calc, doc_nro_calc = _doc_tipo_y_nro(orden.get('cuit_dni', ''))
        factura = {**factura, 'doc_tipo': doc_tipo_calc, 'doc_nro': doc_nro_calc}

    ink = HexColor(INK)
    gray = HexColor(GRAY_600)
    line = HexColor(GRAY_200)
    accent = HexColor(ACCENT)
    cream = HexColor(CREAM)

    buf = io.BytesIO()
    W, H = A4
    c = rl_canvas.Canvas(buf, pagesize=A4)
    M = 40  # margen

    numero_fmt = f"{int(factura['punto_venta']):04d}-{int(factura['numero']):08d}"
    fecha_emision = _fmt_fecha(factura.get('fecha') or datetime.now().strftime('%Y-%m-%d'))

    # ── CABECERA ────────────────────────────────────────────────
    y_top = H - M

    # Recuadro cabecera
    header_h = 110
    c.setStrokeColor(line)
    c.setLineWidth(1)
    c.rect(M, y_top - header_h, W - 2 * M, header_h)

    # Recuadro central con la letra "C"
    box_w = 56
    box_x = W / 2 - box_w / 2
    c.setFillColor(ink)
    c.rect(box_x, y_top - 52, box_w, 52, fill=1, stroke=0)
    c.setFillColor(accent)
    c.setFont('Helvetica-Bold', 30)
    c.drawCentredString(W / 2, y_top - 38, 'C')
    c.setFillColor(ink)
    c.setFont('Helvetica', 7)
    c.drawCentredString(W / 2, y_top - 62, 'COD. 011')

    # Izquierda: emisor
    lx = M + 12
    c.setFillColor(ink)
    c.setFont('Helvetica-Bold', 16)
    c.drawString(lx, y_top - 24, TIENDA_NOMBRE)
    c.setFont('Helvetica', 8)
    c.setFillColor(gray)
    ly = y_top - 38
    for linea in [
        f'Razón social: {razon_social}',
        f'Domicilio comercial: {domicilio}' if domicilio else None,
        f'Condición frente al IVA: {COND_IVA_EMISOR}',
        TIENDA_URL,
    ]:
        if linea:
            c.drawString(lx, ly, linea)
            ly -= 11

    # Derecha: datos del comprobante
    rx = W / 2 + box_w / 2 + 14
    c.setFillColor(ink)
    c.setFont('Helvetica-Bold', 12)
    c.drawString(rx, y_top - 24, 'FACTURA')
    c.setFont('Helvetica', 8)
    ry = y_top - 38
    filas_der = [
        ('Punto de venta - Nro.:', numero_fmt),
        ('Fecha de emisión:', fecha_emision),
        ('CUIT:', str(cuit_emisor)),
        ('Ingresos Brutos:', iibb),
    ]
    if inicio_act:
        filas_der.append(('Inicio de actividades:', inicio_act))
    for etiqueta, valor in filas_der:
        c.setFillColor(gray)
        c.drawString(rx, ry, etiqueta)
        c.setFillColor(ink)
        c.drawString(rx + 105, ry, str(valor))
        ry -= 11

    # ── RECEPTOR ────────────────────────────────────────────────
    y = y_top - header_h - 8
    rec_h = 52
    c.setStrokeColor(line)
    c.rect(M, y - rec_h, W - 2 * M, rec_h)

    nombre_cliente = f"{orden.get('nombre', '') or ''} {orden.get('apellido', '') or ''}".strip() or 'Consumidor Final'
    doc_tipo = int(factura.get('doc_tipo', 99))
    doc_nro = int(factura.get('doc_nro', 0))
    doc_label = DOC_TIPO_LABELS.get(doc_tipo, '')
    doc_texto = f'{doc_label}: {doc_nro}' if doc_label and doc_nro else 'Sin identificar'

    partes_dir = [orden.get('calle', ''), orden.get('altura', '')]
    direccion = ' '.join(str(p) for p in partes_dir if p).strip()
    localidad = ', '.join(str(p) for p in [orden.get('ciudad', ''), orden.get('provincia', '')] if p)

    c.setFillColor(ink)
    c.setFont('Helvetica-Bold', 9)
    c.drawString(M + 12, y - 16, nombre_cliente)
    c.setFont('Helvetica', 8)
    c.setFillColor(gray)
    ry = y - 28
    for linea in [
        f'Condición frente al IVA: {COND_IVA_RECEPTOR}  ·  {doc_texto}',
        f'Domicilio: {direccion}' + (f' — {localidad}' if localidad else '') if direccion else None,
    ]:
        if linea:
            c.drawString(M + 12, ry, linea)
            ry -= 11

    # ── TABLA DE ITEMS ──────────────────────────────────────────
    y = y - rec_h - 14
    col_desc = M
    col_cant = W - M - 190
    col_precio = W - M - 120
    col_sub = W - M

    def _fila_encabezado(y_pos):
        c.setFillColor(ink)
        c.rect(M, y_pos - 18, W - 2 * M, 18, fill=1, stroke=0)
        c.setFillColor(HexColor('#FFFFFF'))
        c.setFont('Helvetica-Bold', 8)
        c.drawString(col_desc + 8, y_pos - 13, 'DESCRIPCIÓN')
        c.drawRightString(col_cant + 30, y_pos - 13, 'CANT.')
        c.drawRightString(col_precio + 40, y_pos - 13, 'P. UNITARIO')
        c.drawRightString(col_sub - 8, y_pos - 13, 'SUBTOTAL')
        return y_pos - 18

    y = _fila_encabezado(y)
    c.setFont('Helvetica', 8)

    for item in items:
        if y < 190:  # espacio reservado para totales + QR
            c.showPage()
            y = H - M
            y = _fila_encabezado(y)
            c.setFont('Helvetica', 8)
        nombre_item = str(item.get('producto_nombre', ''))[:70]
        cantidad = item.get('cantidad', 1)
        precio_u = item.get('precio_unitario')
        subtotal = float(item.get('subtotal', 0))
        if precio_u is None:
            precio_u = subtotal / cantidad if cantidad else subtotal
        y -= 16
        c.setFillColor(ink)
        c.drawString(col_desc + 8, y + 3, nombre_item)
        c.drawRightString(col_cant + 30, y + 3, str(cantidad))
        c.drawRightString(col_precio + 40, y + 3, _fmt_monto(precio_u))
        c.drawRightString(col_sub - 8, y + 3, _fmt_monto(subtotal))
        c.setStrokeColor(line)
        c.setLineWidth(0.5)
        c.line(M, y - 2, W - M, y - 2)

    # ── TOTALES ─────────────────────────────────────────────────
    y -= 14
    descuento = float(orden.get('descuento_monto') or 0)
    envio = float(orden.get('costo_envio') or 0)
    total = float(orden.get('total') or 0)

    filas_tot = []
    if descuento > 0:
        filas_tot.append(('Descuento', -descuento))
    if envio > 0:
        filas_tot.append(('Envío', envio))

    c.setFont('Helvetica', 9)
    for etiqueta, monto in filas_tot:
        y -= 14
        c.setFillColor(gray)
        c.drawRightString(col_precio + 40, y, etiqueta)
        c.setFillColor(ink)
        signo = '-' if monto < 0 else ''
        c.drawRightString(col_sub - 8, y, signo + _fmt_monto(abs(monto)))

    y -= 22
    c.setFillColor(cream)
    c.rect(W - M - 240, y - 6, 240, 22, fill=1, stroke=0)
    c.setFillColor(ink)
    c.setFont('Helvetica-Bold', 11)
    c.drawRightString(col_precio + 40, y, 'IMPORTE TOTAL')
    c.drawRightString(col_sub - 8, y, _fmt_monto(total))

    # ── PIE: QR + CAE ───────────────────────────────────────────
    pie_y = 66

    url_qr = _armar_url_qr(int(str(cuit_emisor).replace('-', '') or 0), factura, total)
    qr_img = qrcode.make(url_qr)
    qr_buf = io.BytesIO()
    qr_img.save(qr_buf, format='PNG')
    qr_buf.seek(0)
    qr_size = 78
    c.drawImage(ImageReader(qr_buf), M, pie_y - 10, width=qr_size, height=qr_size)

    tx = M + qr_size + 14
    c.setFillColor(ink)
    c.setFont('Helvetica-Bold', 9)
    c.drawString(tx, pie_y + 46, 'Comprobante Autorizado')
    c.setFont('Helvetica', 8)
    c.setFillColor(gray)
    c.drawString(tx, pie_y + 33, f'CAE N°: {factura["cae"]}')
    c.drawString(tx, pie_y + 21, f'Fecha de Vto. de CAE: {_fmt_fecha(factura.get("cae_vencimiento"))}')
    c.setFont('Helvetica', 7)
    c.drawString(tx, pie_y + 6, f'Consultá la validez de este comprobante escaneando el código QR — {TIENDA_URL}')

    c.setStrokeColor(line)
    c.setLineWidth(1)
    c.line(M, pie_y + 60, W - M, pie_y + 60)

    c.showPage()
    c.save()
    pdf = buf.getvalue()
    logger.info(f'PDF Factura C {numero_fmt} generado ({len(pdf)} bytes)')
    return pdf


def nombre_archivo_factura(factura: dict) -> str:
    """Nombre estándar del PDF: Factura-C-0002-00000123.pdf"""
    return f"Factura-C-{int(factura['punto_venta']):04d}-{int(factura['numero']):08d}.pdf"
