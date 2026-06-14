#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
API LOCAL PARA ECOMMERCE
Backend con FastAPI para desarrollo local
Después se migra a Hostinger

AUTOR: Sistema Ecommerce Automation
FECHA: 2026-02-22

INSTALACIÓN:
pip install fastapi uvicorn pydantic requests

EJECUTAR:
python api_local.py

ACCEDER:
http://localhost:8000/docs (Documentación interactiva)
http://localhost:8000 (API)
"""

from fastapi import FastAPI, HTTPException, Query, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import sqlite3
import shutil
import sys
from typing import List, Optional
from pydantic import BaseModel, EmailStr
from pathlib import Path
from datetime import datetime
import requests
import json

sys.path.append(str(Path(__file__).parent))
from utils.config import Config
from utils.facturacion_afip import facturacion_habilitada, generar_factura_c
from utils.email_notificaciones import email_habilitado, enviar_email_confirmacion, enviar_email_tracking

# Configuración
_env = Config.cargar_env()
ADMIN_PASSWORD = _env.get('ADMIN_PASSWORD', 'admin2024')

# Catálogo versionado en git (productos/historial_precios, se actualiza a
# diario vía el pipeline y se sobreescribe en cada deploy).
CATALOGO_REPO_PATH = Path(__file__).parent.parent / 'data' / 'catalogo.db'

# Si hay un disco persistente montado (Render), ordenes/clientes viven ahí
# para sobrevivir a los redeploys. Si no está configurado, se usa el mismo
# archivo del repo (comportamiento local de desarrollo).
_persistent_dir = _env.get('PERSISTENT_DATA_DIR', '')
DB_PATH = Path(_persistent_dir) / 'catalogo.db' if _persistent_dir else CATALOGO_REPO_PATH

# ── MercadoPago ──────────────────────────────────────────────
_mp_env = _env.get('MP_ENV', 'test')
if _mp_env == 'production':
    MP_ACCESS_TOKEN = _env.get('MP_ACCESS_TOKEN_PROD', '')
else:
    MP_ACCESS_TOKEN = _env.get('MP_ACCESS_TOKEN_TEST', '')
SITE_URL = _env.get('SITE_URL', 'http://localhost:5500')
API_URL = _env.get('API_URL', 'https://el-gadget-tienda.onrender.com')

app = FastAPI(
    title="Ecommerce API",
    description="API para sistema de ecommerce con sincronización a Droppers",
    version="1.0.0"
)

# Configurar CORS para permitir requests desde frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # En producción: especificar dominios permitidos
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================================
# MODELOS DE DATOS
# ============================================================================

class Producto(BaseModel):
    """Modelo de producto"""
    sku: str
    nombre: str
    descripcion: Optional[str] = ""
    precio_venta: float
    precio_costo: Optional[float] = 0
    stock: int
    categoria: Optional[str] = ""
    subcategoria: Optional[str] = ""
    marca: Optional[str] = ""
    imagen_principal: Optional[str] = ""
    imagenes_adicionales: Optional[str] = ""
    item_group_id: Optional[str] = ""
    color: Optional[str] = ""
    talle: Optional[str] = ""
    link_producto: Optional[str] = ""
    url_amigable: Optional[str] = ""
    variantes_internas: Optional[str] = ""


class Cliente(BaseModel):
    """Modelo de cliente"""
    nombre: str
    apellido: Optional[str] = ""
    razon_social: Optional[str] = ""
    email: EmailStr
    telefono: str
    calle: Optional[str] = ""
    altura: Optional[str] = ""
    piso: Optional[str] = ""
    departamento: Optional[str] = ""
    direccion: str  # campo legacy / campo completo
    pais: Optional[str] = "Argentina"
    provincia: Optional[str] = ""
    ciudad: str
    codigo_postal: str
    cuit_dni: Optional[str] = ""


class ItemCarrito(BaseModel):
    """Modelo de item en carrito"""
    sku: str
    cantidad: int


class CrearOrden(BaseModel):
    """Modelo para crear una orden"""
    cliente: Cliente
    items: List[ItemCarrito]
    notas: Optional[str] = ""


class ActualizarTracking(BaseModel):
    """Modelo para actualizar tracking de orden"""
    tracking_url: str


class SolicitudArrepentimiento(BaseModel):
    """Modelo para solicitar el derecho de arrepentimiento (Ley 24.240 / Res. 424/2020)"""
    orden_id: int
    email: EmailStr
    motivo: Optional[str] = ""


# ============================================================================
# FUNCIONES DE BASE DE DATOS
# ============================================================================

def get_db():
    """Obtiene conexión a la base de datos"""
    if not DB_PATH.exists():
        raise HTTPException(
            status_code=500,
            detail=f"Base de datos no encontrada. Ejecutá primero: python 11_sincronizar_sqlite.py"
        )
    
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def sincronizar_catalogo_persistente():
    """
    Si se usa un disco persistente para ordenes/clientes (PERSISTENT_DATA_DIR),
    refresca ahí las tablas de catálogo (productos, historial_precios) desde
    el catalogo.db versionado en git, sin tocar clientes/ordenes/orden_items.
    En el primer arranque (disco vacío) copia el archivo completo como base.
    """
    if DB_PATH == CATALOGO_REPO_PATH or not CATALOGO_REPO_PATH.exists():
        return

    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    if not DB_PATH.exists():
        shutil.copy(CATALOGO_REPO_PATH, DB_PATH)
        return

    conn = sqlite3.connect(DB_PATH)
    conn.execute("ATTACH DATABASE ? AS src", (str(CATALOGO_REPO_PATH),))
    for tabla in ("productos", "historial_precios"):
        conn.execute(f"DROP TABLE IF EXISTS {tabla}")
        conn.execute(f"CREATE TABLE {tabla} AS SELECT * FROM src.{tabla}")
    conn.execute("DETACH DATABASE src")
    conn.commit()
    conn.close()


def migrar_db():
    """Agrega columnas nuevas a tabla clientes si no existen (migración automática)"""
    if not DB_PATH.exists():
        return
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    columnas_nuevas = [
        ("apellido", "TEXT DEFAULT ''"),
        ("razon_social", "TEXT DEFAULT ''"),
        ("calle", "TEXT DEFAULT ''"),
        ("altura", "TEXT DEFAULT ''"),
        ("piso", "TEXT DEFAULT ''"),
        ("departamento", "TEXT DEFAULT ''"),
        ("pais", "TEXT DEFAULT 'Argentina'"),
        ("cuit_dni", "TEXT DEFAULT ''"),
    ]
    cursor.execute("PRAGMA table_info(clientes)")
    columnas_existentes = {row[1] for row in cursor.fetchall()}
    for col_name, col_def in columnas_nuevas:
        if col_name not in columnas_existentes:
            cursor.execute(f"ALTER TABLE clientes ADD COLUMN {col_name} {col_def}")

    # Columnas de facturación AFIP y notificaciones por email en ordenes
    columnas_ordenes_nuevas = [
        ("factura_tipo", "INTEGER"),
        ("factura_punto_venta", "INTEGER"),
        ("factura_numero", "INTEGER"),
        ("factura_cae", "TEXT"),
        ("factura_cae_vencimiento", "TEXT"),
        ("factura_error", "TEXT"),
        ("email_confirmacion_enviado", "INTEGER DEFAULT 0"),
    ]
    cursor.execute("PRAGMA table_info(ordenes)")
    columnas_ordenes_existentes = {row[1] for row in cursor.fetchall()}
    for col_name, col_def in columnas_ordenes_nuevas:
        if col_name not in columnas_ordenes_existentes:
            cursor.execute(f"ALTER TABLE ordenes ADD COLUMN {col_name} {col_def}")

    # Tabla de solicitudes de derecho de arrepentimiento (Ley 24.240 / Res. 424/2020)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS solicitudes_arrepentimiento (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            orden_id INTEGER NOT NULL,
            email TEXT NOT NULL,
            motivo TEXT DEFAULT '',
            estado TEXT DEFAULT 'pendiente',
            fecha TEXT DEFAULT (datetime('now')),
            respuesta_admin TEXT DEFAULT '',
            FOREIGN KEY (orden_id) REFERENCES ordenes(id)
        )
    """)

    conn.commit()
    conn.close()

# Ejecutar migración al iniciar
sincronizar_catalogo_persistente()
migrar_db()




# ============================================================================
# ENDPOINTS - HOME
# ============================================================================

@app.get("/")
def home():
    """Endpoint raíz - información de la API"""
    return {
        "mensaje": "API Ecommerce funcionando! 🚀",
        "version": "1.0.0",
        "documentacion": "/docs",
        "endpoints": {
            "productos": "/api/productos",
            "categorias": "/api/categorias",
            "ordenes": "/api/ordenes"
        }
    }


@app.get("/health")
def health_check():
    """Verifica que la API y la base de datos estén funcionando"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as total FROM productos")
        total = cursor.fetchone()['total']
        conn.close()
        
        return {
            "status": "ok",
            "database": "connected",
            "productos": total
        }
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"status": "error", "mensaje": str(e)}
        )


# ============================================================================
# ENDPOINTS - PRODUCTOS
# ============================================================================

@app.get("/api/productos", response_model=List[Producto])
def listar_productos(
    categoria: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = Query(500, le=1000),
    offset: int = 0
):
    """
    Lista productos con filtros opcionales
    
    - **categoria**: Filtrar por categoría
    - **search**: Buscar en nombre y descripción
    - **limit**: Cantidad máxima de resultados (default: 500, max: 1000)
    - **offset**: Desplazamiento para paginación
    """
    conn = get_db()
    cursor = conn.cursor()
    
    query = "SELECT * FROM productos WHERE stock > 0"
    params = []
    
    if categoria:
        query += " AND categoria = ?"
        params.append(categoria)
    
    if search:
        query += " AND (nombre LIKE ? OR descripcion LIKE ?)"
        search_term = f"%{search}%"
        params.append(search_term)
        params.append(search_term)
    
    query += " ORDER BY nombre LIMIT ? OFFSET ?"
    params.extend([limit, offset])
    
    cursor.execute(query, params)
    productos = cursor.fetchall()
    conn.close()
    
    return [dict(p) for p in productos]


def parsear_imagenes(producto_dict: dict) -> list:
    """Convierte imagen_principal + imagenes_adicionales (string) en un array de URLs"""
    imagenes_principales = []
    if producto_dict.get('imagen_principal'):
        imagenes_principales.append(producto_dict['imagen_principal'])

    imagenes_adicionales = []
    if producto_dict.get('imagenes_adicionales'):
        # Puede estar separado por comas o saltos de línea
        adicionales_str = producto_dict['imagenes_adicionales']
        imagenes_adicionales = [
            img.strip()
            for img in adicionales_str.replace('\n', ',').split(',')
            if img.strip()
        ]

    return imagenes_principales + imagenes_adicionales


@app.get("/api/producto/{sku}")
def detalle_producto(sku: str):
    """
    Obtiene el detalle COMPLETO de un producto incluyendo:
    - Datos del producto
    - Todas sus variantes (si tiene)
    - Productos relacionados (misma categoría)
    - Imágenes parseadas como array
    
    - **sku**: SKU del producto
    """
    conn = get_db()
    cursor = conn.cursor()
    
    # 1. Obtener producto principal
    cursor.execute("SELECT * FROM productos WHERE sku = ?", (sku,))
    producto = cursor.fetchone()
    
    if not producto:
        conn.close()
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    
    producto_dict = dict(producto)

    # 2. Parsear imágenes (convertir string a array)
    producto_dict['imagenes'] = parsear_imagenes(producto_dict)

    # 3. Obtener variantes (productos con mismo item_group_id)
    variantes = []
    item_group_id = producto_dict.get('item_group_id', '')

    if item_group_id and item_group_id != sku:
        # Tiene grupo, buscar todas las variantes
        cursor.execute("""
            SELECT * FROM productos
            WHERE item_group_id = ? AND sku != ?
            ORDER BY color, talle
        """, (item_group_id, sku))

        variantes_raw = cursor.fetchall()

        for var in variantes_raw:
            var_dict = dict(var)
            # Parsear imágenes de variantes también (principal + adicionales)
            var_dict['imagenes'] = parsear_imagenes(var_dict)
            variantes.append(var_dict)
    
    producto_dict['variantes'] = variantes
    producto_dict['tiene_variantes'] = len(variantes) > 0

    # 3b. Variantes "internas" (configurable product de Magento: color/talle
    # que cambian dentro de la misma página de Droppers)
    try:
        producto_dict['variantes_internas'] = json.loads(producto_dict.get('variantes_internas') or '[]')
    except (TypeError, ValueError):
        producto_dict['variantes_internas'] = []
    
    # 4. Obtener productos relacionados (misma categoría, excluir actual)
    relacionados = []
    categoria = producto_dict.get('categoria', '')
    
    if categoria:
        cursor.execute("""
            SELECT * FROM productos 
            WHERE categoria = ? AND sku != ? AND stock > 0
            ORDER BY RANDOM()
            LIMIT 8
        """, (categoria, sku))
        
        relacionados_raw = cursor.fetchall()
        
        for rel in relacionados_raw:
            rel_dict = dict(rel)
            # Solo imagen principal para relacionados
            rel_dict['imagenes'] = [rel_dict.get('imagen_principal', '')]
            relacionados.append(rel_dict)
    
    producto_dict['productos_relacionados'] = relacionados
    
    conn.close()
    
    return producto_dict


@app.get("/api/productos/grupo/{item_group_id}")
def productos_por_grupo(item_group_id: str):
    """
    Obtiene todas las variantes de un grupo
    
    - **item_group_id**: ID del grupo de variantes
    """
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute(
        "SELECT * FROM productos WHERE item_group_id = ? ORDER BY color, talle",
        (item_group_id,)
    )
    productos = cursor.fetchall()
    conn.close()
    
    if not productos:
        raise HTTPException(status_code=404, detail="Grupo no encontrado")
    
    return [dict(p) for p in productos]


@app.get("/api/categorias")
def listar_categorias():
    """Lista todas las categorías disponibles"""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT DISTINCT categoria, COUNT(*) as total 
        FROM productos 
        WHERE categoria != '' AND stock > 0
        GROUP BY categoria
        ORDER BY categoria
    """)
    categorias = cursor.fetchall()
    conn.close()
    
    return [{"categoria": c['categoria'], "total": c['total']} for c in categorias]


@app.get("/api/productos/destacados")
def productos_destacados(limit: int = 10):
    """Obtiene productos destacados (más recientes o con mejor precio)"""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT * FROM productos 
        WHERE stock > 0 
        ORDER BY actualizado_at DESC 
        LIMIT ?
    """, (limit,))
    productos = cursor.fetchall()
    conn.close()
    
    return [dict(p) for p in productos]


# ============================================================================
# ENDPOINTS - ÓRDENES
# ============================================================================

@app.post("/api/orden")
def crear_orden(orden: CrearOrden):
    """
    Crea una nueva orden
    
    Proceso:
    1. Crea o busca el cliente
    2. Calcula el total
    3. Crea la orden
    4. Agrega los items
    """
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        # 1. Buscar o crear cliente
        cursor.execute("SELECT id FROM clientes WHERE email = ?", (orden.cliente.email,))
        cliente = cursor.fetchone()
        
        if cliente:
            cliente_id = cliente['id']
            # Actualizar datos del cliente
            cursor.execute("""
                UPDATE clientes 
                SET nombre = ?, apellido = ?, razon_social = ?, telefono = ?,
                    calle = ?, altura = ?, piso = ?, departamento = ?,
                    direccion = ?, pais = ?, provincia = ?, ciudad = ?,
                    codigo_postal = ?, cuit_dni = ?
                WHERE id = ?
            """, (
                orden.cliente.nombre,
                orden.cliente.apellido or "",
                orden.cliente.razon_social or "",
                orden.cliente.telefono,
                orden.cliente.calle or "",
                orden.cliente.altura or "",
                orden.cliente.piso or "",
                orden.cliente.departamento or "",
                orden.cliente.direccion,
                orden.cliente.pais or "Argentina",
                orden.cliente.provincia or "",
                orden.cliente.ciudad,
                orden.cliente.codigo_postal,
                orden.cliente.cuit_dni or "",
                cliente_id
            ))
        else:
            # Crear nuevo cliente
            cursor.execute("""
                INSERT INTO clientes (nombre, apellido, razon_social, email, telefono,
                    calle, altura, piso, departamento, direccion, pais, provincia, ciudad,
                    codigo_postal, cuit_dni)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                orden.cliente.nombre,
                orden.cliente.apellido or "",
                orden.cliente.razon_social or "",
                orden.cliente.email,
                orden.cliente.telefono,
                orden.cliente.calle or "",
                orden.cliente.altura or "",
                orden.cliente.piso or "",
                orden.cliente.departamento or "",
                orden.cliente.direccion,
                orden.cliente.pais or "Argentina",
                orden.cliente.provincia or "",
                orden.cliente.ciudad,
                orden.cliente.codigo_postal,
                orden.cliente.cuit_dni or ""
            ))
            cliente_id = cursor.lastrowid
        
        # 2. Calcular total y preparar items
        total = 0
        items_con_precio = []
        
        for item in orden.items:
            cursor.execute(
                "SELECT sku, nombre, precio_venta, stock FROM productos WHERE sku = ?",
                (item.sku,)
            )
            producto = cursor.fetchone()
            
            if not producto:
                raise HTTPException(
                    status_code=404,
                    detail=f"Producto {item.sku} no encontrado"
                )
            
            if producto['stock'] < item.cantidad:
                raise HTTPException(
                    status_code=400,
                    detail=f"Stock insuficiente para {producto['nombre']} (disponible: {producto['stock']})"
                )
            
            subtotal = producto['precio_venta'] * item.cantidad
            total += subtotal
            
            items_con_precio.append({
                'sku': item.sku,
                'nombre': producto['nombre'],
                'cantidad': item.cantidad,
                'precio_unitario': producto['precio_venta'],
                'subtotal': subtotal
            })
        
        # 3. Crear orden
        cursor.execute("""
            INSERT INTO ordenes (cliente_id, total, estado, notas)
            VALUES (?, ?, 'pendiente_procesar', ?)
        """, (cliente_id, total, orden.notas or ""))
        
        orden_id = cursor.lastrowid
        
        # 4. Agregar items
        for item in items_con_precio:
            cursor.execute("""
                INSERT INTO orden_items (
                    orden_id, producto_sku, producto_nombre, 
                    cantidad, precio_unitario, subtotal
                )
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                orden_id,
                item['sku'],
                item['nombre'],
                item['cantidad'],
                item['precio_unitario'],
                item['subtotal']
            ))
        
        conn.commit()
        conn.close()

        # ── Generar preferencia de MercadoPago ──
        mp_checkout_url = None
        try:
            mp_items = [
                {
                    "id": item['sku'],
                    "title": item['nombre'],
                    "quantity": item['cantidad'],
                    "unit_price": float(item['precio_unitario']),
                    "currency_id": "ARS"
                }
                for item in items_con_precio
            ]
            preference_data = {
                "items": mp_items,
                "payer": {
                    "name": orden.cliente.nombre,
                    "surname": orden.cliente.apellido or "",
                    "email": orden.cliente.email,
                    "phone": {"number": orden.cliente.telefono}
                },
                "back_urls": {
                    "success": f"{SITE_URL}/confirmacion.html?orden_id={orden_id}&status=approved",
                    "failure": f"{SITE_URL}/confirmacion.html?orden_id={orden_id}&status=failure",
                    "pending": f"{SITE_URL}/confirmacion.html?orden_id={orden_id}&status=pending"
                },
                "auto_return": "approved",
                "external_reference": str(orden_id),
                "notification_url": f"{API_URL}/api/mp/webhook"
            }
            print(f"🔵 Llamando MP para orden #{orden_id}...")
            mp_response = requests.post(
                "https://api.mercadopago.com/checkout/preferences",
                headers={
                    "Authorization": f"Bearer {MP_ACCESS_TOKEN}",
                    "Content-Type": "application/json"
                },
                json=preference_data,
                timeout=10
            )
            print(f"🔵 MP status: {mp_response.status_code}")
            print(f"🔵 MP response: {mp_response.text[:500]}")
            if mp_response.status_code == 201:
                mp_data = mp_response.json()
                mp_checkout_url = mp_data.get("init_point")
                print(f"✅ MP checkout URL: {mp_checkout_url}")
            else:
                print(f"❌ MP error: {mp_response.status_code} - {mp_response.text}")
        except Exception as mp_err:
            print(f"❌ Excepción MP: {type(mp_err).__name__}: {mp_err}")

        return {
            "orden_id": orden_id,
            "cliente_id": cliente_id,
            "total": total,
            "items": len(items_con_precio),
            "estado": "pendiente_procesar",
            "mp_checkout_url": mp_checkout_url,
            "mensaje": "Orden creada exitosamente"
        }
        
    except HTTPException:
        conn.rollback()
        conn.close()
        raise
    except Exception as e:
        conn.rollback()
        conn.close()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/ordenes")
def listar_ordenes(
    estado: Optional[str] = None,
    limit: int = Query(50, le=200)
):
    """
    Lista órdenes con filtros opcionales
    
    - **estado**: Filtrar por estado (pendiente_procesar, procesando, enviado, entregado)
    - **limit**: Cantidad máxima de resultados
    """
    conn = get_db()
    cursor = conn.cursor()
    
    query = """
        SELECT o.*, c.nombre as cliente_nombre, c.email as cliente_email
        FROM ordenes o
        JOIN clientes c ON o.cliente_id = c.id
    """
    params = []
    
    if estado:
        query += " WHERE o.estado = ?"
        params.append(estado)
    
    query += " ORDER BY o.fecha DESC LIMIT ?"
    params.append(limit)
    
    cursor.execute(query, params)
    ordenes = cursor.fetchall()
    conn.close()
    
    return [dict(o) for o in ordenes]


@app.get("/api/orden/{orden_id}")
def detalle_orden(orden_id: int):
    """Obtiene el detalle completo de una orden"""
    conn = get_db()
    cursor = conn.cursor()
    
    # Datos de la orden
    cursor.execute("""
        SELECT o.*, c.nombre, c.apellido, c.email, c.telefono, c.razon_social,
               c.calle, c.altura, c.piso, c.departamento,
               c.direccion, c.provincia, c.ciudad, c.codigo_postal, c.cuit_dni
        FROM ordenes o
        JOIN clientes c ON o.cliente_id = c.id
        WHERE o.id = ?
    """, (orden_id,))
    orden = cursor.fetchone()
    
    if not orden:
        conn.close()
        raise HTTPException(status_code=404, detail="Orden no encontrada")
    
    # Items de la orden
    cursor.execute("""
        SELECT * FROM orden_items WHERE orden_id = ?
    """, (orden_id,))
    items = cursor.fetchall()
    
    conn.close()
    
    orden_dict = dict(orden)
    orden_dict['items'] = [dict(item) for item in items]
    
    return orden_dict


@app.post("/api/mp/webhook")
async def mp_webhook(request: Request):
    try:
        body = await request.json()
        topic = body.get("type") or body.get("topic", "")
        resource_id = None
        if topic == "payment":
            resource_id = body.get("data", {}).get("id")
        elif topic == "merchant_order":
            resource_id = body.get("resource", "").split("/")[-1]

        if resource_id:
            mp_res = requests.get(
                f"https://api.mercadopago.com/v1/payments/{resource_id}",
                headers={"Authorization": f"Bearer {MP_ACCESS_TOKEN}"},
                timeout=10
            )
            if mp_res.status_code == 200:
                pago = mp_res.json()
                estado_pago = pago.get("status", "")
                orden_id = pago.get("external_reference")
                if orden_id:
                    conn = get_db()
                    conn.execute(
                        "UPDATE ordenes SET estado_pago = ? WHERE id = ?",
                        (estado_pago, int(orden_id))
                    )
                    conn.commit()

                    if estado_pago == "approved":
                        procesar_pago_aprobado(conn, int(orden_id))

                    conn.close()
    except Exception as e:
        print(f"Webhook error: {e}")
    return {"status": "ok"}


def procesar_pago_aprobado(conn: sqlite3.Connection, orden_id: int):
    """
    Tras un pago aprobado: genera la Factura C (AFIP) si está habilitado y
    todavía no se generó, y envía el email de confirmación al cliente.
    Ambas integraciones son best-effort: si no están configuradas o fallan,
    se loguea el error pero no se interrumpe el webhook.
    """
    cursor = conn.cursor()
    cursor.execute("""
        SELECT o.*, c.nombre, c.email, c.cuit_dni
        FROM ordenes o
        JOIN clientes c ON o.cliente_id = c.id
        WHERE o.id = ?
    """, (orden_id,))
    orden = cursor.fetchone()
    if not orden:
        return
    orden = dict(orden)

    factura = None
    if facturacion_habilitada() and not orden.get('factura_cae'):
        factura = generar_factura_c(orden_id, orden, orden['total'])
        if factura.get('error'):
            cursor.execute(
                "UPDATE ordenes SET factura_error = ? WHERE id = ?",
                (factura['error'], orden_id)
            )
        else:
            cursor.execute("""
                UPDATE ordenes
                SET factura_tipo = ?, factura_punto_venta = ?, factura_numero = ?,
                    factura_cae = ?, factura_cae_vencimiento = ?, factura_error = NULL
                WHERE id = ?
            """, (
                factura['tipo'], factura['punto_venta'], factura['numero'],
                factura['cae'], factura['cae_vencimiento'], orden_id
            ))
        conn.commit()

    if email_habilitado() and not orden.get('email_confirmacion_enviado'):
        cursor.execute("SELECT * FROM orden_items WHERE orden_id = ?", (orden_id,))
        items = [dict(item) for item in cursor.fetchall()]
        resultado = enviar_email_confirmacion(orden, items, factura)
        if not resultado.get('error'):
            cursor.execute(
                "UPDATE ordenes SET email_confirmacion_enviado = 1 WHERE id = ?",
                (orden_id,)
            )
            conn.commit()


@app.post("/api/admin/orden/{orden_id}/procesar-pago")
def admin_procesar_pago(orden_id: int, x_admin_password: Optional[str] = Header(None)):
    """
    Dispara manualmente la generación de Factura C (AFIP) + email de
    confirmación para una orden (solo admin). Útil para reintentar si
    falló en el webhook, o para probar la integración sin un pago nuevo.
    """
    if x_admin_password != ADMIN_PASSWORD:
        raise HTTPException(status_code=401, detail="No autorizado")

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM ordenes WHERE id = ?", (orden_id,))
    if not cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail="Orden no encontrada")

    procesar_pago_aprobado(conn, orden_id)

    cursor.execute("""
        SELECT factura_tipo, factura_punto_venta, factura_numero, factura_cae,
               factura_cae_vencimiento, factura_error, email_confirmacion_enviado
        FROM ordenes WHERE id = ?
    """, (orden_id,))
    resultado = dict(cursor.fetchone())
    conn.close()
    return resultado


@app.patch("/api/orden/{orden_id}/tracking")
def actualizar_tracking(orden_id: int, datos: ActualizarTracking, x_admin_password: Optional[str] = Header(None)):
    """
    Actualiza el link de seguimiento de Droppers de una orden (solo admin).
    Marca la orden como 'enviado' y registra la fecha de envío.
    """
    if x_admin_password != ADMIN_PASSWORD:
        raise HTTPException(status_code=401, detail="No autorizado")

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE ordenes
        SET tracking_url = ?, estado = 'enviado', enviado_at = datetime('now')
        WHERE id = ?
    """, (datos.tracking_url, orden_id))

    if cursor.rowcount == 0:
        conn.close()
        raise HTTPException(status_code=404, detail="Orden no encontrada")

    conn.commit()

    if email_habilitado():
        cursor.execute("""
            SELECT o.id, o.tracking_enviado, c.nombre, c.email
            FROM ordenes o
            JOIN clientes c ON o.cliente_id = c.id
            WHERE o.id = ?
        """, (orden_id,))
        orden = dict(cursor.fetchone())
        if not orden['tracking_enviado']:
            resultado = enviar_email_tracking(orden, datos.tracking_url)
            if not resultado.get('error'):
                cursor.execute(
                    "UPDATE ordenes SET tracking_enviado = 1 WHERE id = ?",
                    (orden_id,)
                )
                conn.commit()

    conn.close()

    return {"mensaje": "Tracking actualizado", "orden_id": orden_id}


@app.patch("/api/orden/{orden_id}/estado")
def actualizar_estado_orden(orden_id: int, estado: str):
    """
    Actualiza el estado de una orden
    
    Estados válidos: pendiente_procesar, procesando, enviado, entregado
    """
    estados_validos = ['pendiente_procesar', 'procesando', 'enviado', 'entregado']
    
    if estado not in estados_validos:
        raise HTTPException(
            status_code=400,
            detail=f"Estado inválido. Debe ser uno de: {', '.join(estados_validos)}"
        )
    
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("UPDATE ordenes SET estado = ? WHERE id = ?", (estado, orden_id))
    
    if cursor.rowcount == 0:
        conn.close()
        raise HTTPException(status_code=404, detail="Orden no encontrada")
    
    conn.commit()
    conn.close()
    
    return {"mensaje": "Estado actualizado", "orden_id": orden_id, "nuevo_estado": estado}


@app.delete("/api/orden/{orden_id}")
def eliminar_orden(orden_id: int, x_admin_password: Optional[str] = Header(None)):
    """
    Elimina/cancela una orden (solo admin).
    Requiere header X-Admin-Password con la clave correcta.
    """
    if x_admin_password != ADMIN_PASSWORD:
        raise HTTPException(status_code=401, detail="No autorizado")

    conn = get_db()
    cursor = conn.cursor()

    # Verificar que existe
    cursor.execute("SELECT id FROM ordenes WHERE id = ?", (orden_id,))
    if not cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail="Orden no encontrada")

    # Eliminar items primero (FK)
    cursor.execute("DELETE FROM orden_items WHERE orden_id = ?", (orden_id,))
    cursor.execute("DELETE FROM ordenes WHERE id = ?", (orden_id,))
    conn.commit()
    conn.close()

    return {"mensaje": "Orden eliminada", "orden_id": orden_id}


@app.get("/api/admin/verificar")
def verificar_admin(x_admin_password: Optional[str] = Header(None)):
    """Verifica si la clave admin es correcta"""
    if x_admin_password != ADMIN_PASSWORD:
        raise HTTPException(status_code=401, detail="Contraseña incorrecta")
    return {"autorizado": True}


# ============================================================================
# ENDPOINTS - SEGUIMIENTO DE PEDIDOS
# ============================================================================

@app.get("/api/seguimiento/{orden_id}")
def seguimiento_orden(orden_id: int, email: str = Query(...)):
    """
    Seguimiento de un pedido para el cliente.
    Requiere el email usado en la compra para validar que el pedido le pertenece.
    """
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT o.id, o.total, o.estado, o.estado_pago, o.tracking_url,
               o.fecha, o.enviado_at, c.email, c.nombre, c.apellido
        FROM ordenes o
        JOIN clientes c ON o.cliente_id = c.id
        WHERE o.id = ?
    """, (orden_id,))
    orden = cursor.fetchone()

    if not orden or orden['email'].strip().lower() != email.strip().lower():
        conn.close()
        raise HTTPException(status_code=404, detail="No encontramos un pedido con esos datos")

    cursor.execute("""
        SELECT producto_sku AS sku, producto_nombre AS nombre, cantidad
        FROM orden_items WHERE orden_id = ?
    """, (orden_id,))
    items = cursor.fetchall()
    conn.close()

    orden_dict = dict(orden)
    orden_dict['items'] = [dict(i) for i in items]
    return orden_dict


# ============================================================================
# ENDPOINTS - BOTÓN DE ARREPENTIMIENTO (Ley 24.240 / Res. 424/2020)
# ============================================================================

@app.post("/api/arrepentimiento")
def crear_solicitud_arrepentimiento(solicitud: SolicitudArrepentimiento):
    """
    Registra una solicitud de derecho de arrepentimiento (revocación de compra).
    El cliente tiene 10 días corridos desde la compra para ejercerlo, sin necesidad
    de justificar el motivo (Ley 24.240, Res. 424/2020).
    """
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT o.id, o.fecha, c.email
        FROM ordenes o
        JOIN clientes c ON o.cliente_id = c.id
        WHERE o.id = ?
    """, (solicitud.orden_id,))
    orden = cursor.fetchone()

    if not orden:
        conn.close()
        raise HTTPException(status_code=404, detail="No encontramos una orden con ese número")

    if orden['email'].strip().lower() != solicitud.email.strip().lower():
        conn.close()
        raise HTTPException(status_code=400, detail="El email no coincide con el de la orden")

    dias_transcurridos = (datetime.now() - datetime.fromisoformat(orden['fecha'])).days
    if dias_transcurridos > 10:
        conn.close()
        raise HTTPException(
            status_code=400,
            detail="Pasaron más de 10 días corridos desde la compra. Escribinos por WhatsApp para evaluar tu caso."
        )

    cursor.execute("""
        INSERT INTO solicitudes_arrepentimiento (orden_id, email, motivo)
        VALUES (?, ?, ?)
    """, (solicitud.orden_id, solicitud.email, solicitud.motivo or ""))

    conn.commit()
    solicitud_id = cursor.lastrowid
    conn.close()

    return {
        "mensaje": "Solicitud registrada correctamente. Te contactaremos por WhatsApp o email para coordinar la devolución.",
        "solicitud_id": solicitud_id
    }


@app.get("/api/arrepentimientos")
def listar_solicitudes_arrepentimiento(x_admin_password: Optional[str] = Header(None)):
    """Lista las solicitudes de arrepentimiento (solo admin)"""
    if x_admin_password != ADMIN_PASSWORD:
        raise HTTPException(status_code=401, detail="No autorizado")

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT s.*, o.total, o.estado AS estado_orden, c.nombre AS cliente_nombre, c.telefono
        FROM solicitudes_arrepentimiento s
        JOIN ordenes o ON s.orden_id = o.id
        JOIN clientes c ON o.cliente_id = c.id
        ORDER BY s.fecha DESC
    """)
    solicitudes = cursor.fetchall()
    conn.close()

    return [dict(s) for s in solicitudes]


@app.patch("/api/arrepentimiento/{solicitud_id}/estado")
def actualizar_estado_arrepentimiento(
    solicitud_id: int,
    estado: str,
    x_admin_password: Optional[str] = Header(None)
):
    """Actualiza el estado de una solicitud de arrepentimiento (solo admin)"""
    if x_admin_password != ADMIN_PASSWORD:
        raise HTTPException(status_code=401, detail="No autorizado")

    estados_validos = ['pendiente', 'aprobado', 'rechazado']
    if estado not in estados_validos:
        raise HTTPException(
            status_code=400,
            detail=f"Estado inválido. Debe ser uno de: {', '.join(estados_validos)}"
        )

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE solicitudes_arrepentimiento SET estado = ? WHERE id = ?", (estado, solicitud_id))

    if cursor.rowcount == 0:
        conn.close()
        raise HTTPException(status_code=404, detail="Solicitud no encontrada")

    conn.commit()
    conn.close()

    return {"mensaje": "Estado actualizado", "solicitud_id": solicitud_id, "nuevo_estado": estado}


# ============================================================================
# ENDPOINTS - ESTADÍSTICAS
# ============================================================================

@app.get("/api/estadisticas")
def obtener_estadisticas():
    """Obtiene estadísticas generales del sistema"""
    conn = get_db()
    cursor = conn.cursor()
    
    # Total productos
    cursor.execute("SELECT COUNT(*) as total FROM productos")
    total_productos = cursor.fetchone()['total']
    
    # Productos en stock
    cursor.execute("SELECT COUNT(*) as total FROM productos WHERE stock > 0")
    en_stock = cursor.fetchone()['total']
    
    # Total órdenes
    cursor.execute("SELECT COUNT(*) as total FROM ordenes")
    total_ordenes = cursor.fetchone()['total']
    
    # Órdenes pendientes
    cursor.execute("SELECT COUNT(*) as total FROM ordenes WHERE estado = 'pendiente_procesar'")
    ordenes_pendientes = cursor.fetchone()['total']
    
    # Ventas totales
    cursor.execute("SELECT SUM(total) as ventas FROM ordenes WHERE estado_pago = 'approved'")
    ventas = cursor.fetchone()['ventas'] or 0
    
    conn.close()
    
    return {
        "productos": {
            "total": total_productos,
            "en_stock": en_stock,
            "agotados": total_productos - en_stock
        },
        "ordenes": {
            "total": total_ordenes,
            "pendientes": ordenes_pendientes
        },
        "ventas_totales": ventas
    }


# ============================================================================
# EJECUTAR SERVIDOR
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    
    print("\n" + "="*60)
    print("🚀 INICIANDO API LOCAL")
    print("="*60)
    print(f"📁 Base de datos: {DB_PATH}")
    print(f"🌐 Servidor: http://localhost:8000")
    print(f"📖 Documentación: http://localhost:8000/docs")
    print("="*60 + "\n")
    
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
