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
import sys
from typing import List, Optional
from pydantic import BaseModel, EmailStr
from pathlib import Path
from datetime import datetime
import requests
import json

sys.path.append(str(Path(__file__).parent))
from utils.config import Config

# Configuración
_env = Config.cargar_env()
ADMIN_PASSWORD = _env.get('ADMIN_PASSWORD', 'admin2024')
DB_PATH = Path(__file__).parent.parent / 'data' / 'catalogo.db'

# ── MercadoPago ──────────────────────────────────────────────
_mp_env = _env.get('MP_ENV', 'test')
if _mp_env == 'production':
    MP_ACCESS_TOKEN = _env.get('MP_ACCESS_TOKEN_PROD', '')
else:
    MP_ACCESS_TOKEN = _env.get('MP_ACCESS_TOKEN_TEST', '')
SITE_URL = _env.get('SITE_URL', 'http://localhost:5500')

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
    conn.commit()
    conn.close()

# Ejecutar migración al iniciar
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
    
    producto_dict['imagenes'] = imagenes_principales + imagenes_adicionales
    
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
            # Parsear imágenes de variantes también
            var_imagenes = []
            if var_dict.get('imagen_principal'):
                var_imagenes.append(var_dict['imagen_principal'])
            var_dict['imagenes'] = var_imagenes
            variantes.append(var_dict)
    
    producto_dict['variantes'] = variantes
    producto_dict['tiene_variantes'] = len(variantes) > 0
    
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
                "external_reference": str(orden_id),
                "notification_url": f"{SITE_URL}/api/mp/webhook"
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
                    conn.close()
    except Exception as e:
        print(f"Webhook error: {e}")
    return {"status": "ok"}
def actualizar_tracking(orden_id: int, datos: ActualizarTracking):
    """Actualiza el tracking de una orden"""
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
