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

from fastapi import FastAPI, HTTPException, Query, Header, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
import re
import sqlite3
import shutil
import sys
import uuid
import csv
import io
import hashlib
import hmac
import secrets
from typing import List, Optional
from pydantic import BaseModel, EmailStr
from pathlib import Path
from datetime import datetime
import requests
import json

sys.path.append(str(Path(__file__).parent))
from utils.config import Config
from utils.facturacion_afip import facturacion_habilitada, generar_factura_c
from utils.email_notificaciones import (
    email_habilitado, enviar_email_confirmacion, enviar_email_tracking,
    enviar_email_bienvenida, enviar_email_referido_confirmacion, enviar_email_referido_admin,
)

# Configuración
_env = Config.cargar_env()
ADMIN_PASSWORD = _env.get('ADMIN_PASSWORD')
if not ADMIN_PASSWORD:
    raise RuntimeError("ADMIN_PASSWORD no está configurado en las variables de entorno")

def _es_admin(pwd: Optional[str]) -> bool:
    """Comparación de contraseña admin en tiempo constante (evita timing oracle)."""
    if not pwd:
        return False
    return hmac.compare_digest(pwd, ADMIN_PASSWORD)

# Catálogo versionado en git (productos/historial_precios, se actualiza a
# diario vía el pipeline y se sobreescribe en cada deploy).
CATALOGO_REPO_PATH = Path(__file__).parent.parent / 'data' / 'catalogo.db'

# Tarifario de zonas de envío (Droppers): costo + plazo por zona y mapa de
# partidos de la Provincia de Buenos Aires a su zona correspondiente.
ZONAS_ENVIO_FILE = Path(__file__).parent.parent / 'data' / 'envios' / 'zonas_envio.json'
with open(ZONAS_ENVIO_FILE, 'r', encoding='utf-8') as f:
    ZONAS_ENVIO = json.load(f)

# Si hay un disco persistente montado (Render), ordenes/clientes viven ahí
# para sobrevivir a los redeploys. Si no está configurado, se usa el mismo
# archivo del repo (comportamiento local de desarrollo).
_persistent_dir = _env.get('PERSISTENT_DATA_DIR', '')
DB_PATH = Path(_persistent_dir) / 'catalogo.db' if _persistent_dir else CATALOGO_REPO_PATH

# ── MercadoPago ──────────────────────────────────────────────
_mp_env = _env.get('MP_ENV', 'test')
if _mp_env == 'production':
    MP_ACCESS_TOKEN = _env.get('MP_ACCESS_TOKEN_PROD', '')
    MP_WEBHOOK_SECRET = _env.get('MP_WEBHOOK_SECRET_PROD', '')
else:
    MP_ACCESS_TOKEN = _env.get('MP_ACCESS_TOKEN_TEST', '')
    MP_WEBHOOK_SECRET = _env.get('MP_WEBHOOK_SECRET_TEST', '')
SITE_URL = _env.get('SITE_URL', 'http://localhost:5500')
API_URL = _env.get('API_URL', 'https://el-gadget-tienda.onrender.com')

app = FastAPI(
    title="Ecommerce API",
    description="API para sistema de ecommerce con sincronización a Droppers",
    version="1.0.0"
)

def _get_real_ip(request: Request) -> str:
    # Render y la mayoría de proxies reenvían la IP real en X-Forwarded-For
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return get_remote_address(request)

limiter = Limiter(key_func=_get_real_ip)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

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
    precio_oferta: Optional[float] = None
    seo_optimizado_at: Optional[str] = None


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
    partido: Optional[str] = ""  # solo aplica para Provincia de Buenos Aires (define zona de envío)
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
    codigo_descuento: Optional[str] = None


class ActualizarTracking(BaseModel):
    """Modelo para actualizar tracking de orden"""
    tracking_url: str


class ActualizarProducto(BaseModel):
    """Modelo para editar manualmente un producto (campos opcionales, edición parcial)"""
    nombre: Optional[str] = None
    descripcion: Optional[str] = None
    categoria: Optional[str] = None
    precio_venta: Optional[float] = None
    stock: Optional[int] = None
    stock_manual: Optional[bool] = None
    imagen_principal: Optional[str] = None
    imagenes_adicionales: Optional[str] = None


class SolicitudArrepentimiento(BaseModel):
    """Modelo para solicitar el derecho de arrepentimiento (Ley 24.240 / Disposición 954/2025)"""
    orden_id: int
    email: EmailStr
    motivo: Optional[str] = ""


class Registro(BaseModel):
    """Modelo para el registro de usuarios (popup de bienvenida + creación de cuenta)"""
    nombre: str
    email: EmailStr
    telefono: str
    password: str


class Login(BaseModel):
    """Modelo para iniciar sesión en 'Mi cuenta'"""
    email: EmailStr
    password: str


class Descuento(BaseModel):
    """Modelo para crear/editar una campaña de descuento (códigos, descuentos
    programados por fecha y/o banners promocionales) desde el Panel El Gadget"""
    nombre: str
    tipo: str = "porcentaje"  # 'porcentaje' | 'fijo'
    valor: float = 0
    alcance: str = "todos"  # 'todos' | 'categoria' | 'skus'
    categoria: Optional[str] = ""
    skus: Optional[List[str]] = []
    codigo: Optional[str] = None
    email_asociado: Optional[str] = None
    fecha_inicio: Optional[str] = None
    fecha_fin: Optional[str] = None
    activo: bool = True
    uso_maximo: Optional[int] = None
    mostrar_banner: bool = False
    banner_titulo: Optional[str] = ""
    banner_texto: Optional[str] = ""


class ValidarDescuento(BaseModel):
    """Modelo para validar un código de descuento en el checkout"""
    codigo: str
    email: Optional[str] = None
    subtotal: float
    skus: Optional[List[str]] = []


class RegistroReferido(BaseModel):
    nombre: str
    email: str
    telefono: str
    dni: str
    password: str


class MarcarPagadoReferido(BaseModel):
    periodo: str  # "2026-06"


def _generar_codigo_referido(nombre: str, telefono: str, conn: sqlite3.Connection) -> str:
    """Genera NOMBRE+2dígitos del teléfono, con sufijo -2/-3/... si hay colisión."""
    base = re.sub(r'[^A-Z0-9]', '', f"{nombre.upper().split()[0]}{telefono[-2:]}")
    if not base:
        base = re.sub(r'[^A-Z0-9]', '', nombre.upper())[:6] or 'REF'
    codigo, i = base, 2
    while conn.execute("SELECT 1 FROM referidos WHERE codigo = ?", (codigo,)).fetchone():
        codigo = f"{base}-{i}"
        i += 1
    return codigo


def _descuento_referido_escalonado(subtotal: float) -> float:
    """Descuento escalonado según total del carrito: <$4k→10%, $4k-$20k→15%, >$20k→20%."""
    if subtotal < 4000:
        return 10.0
    elif subtotal <= 20000:
        return 15.0
    else:
        return 20.0


def _get_tier_comision(referido_id: int, conn: sqlite3.Connection) -> dict:
    """Tier de comisión según ventas del mes: <5→7%, 5-14→11%, ≥15→15%."""
    periodo = datetime.now().strftime('%Y-%m')
    ventas_mes = conn.execute(
        "SELECT COUNT(*) FROM comisiones_referidos WHERE referido_id=? AND periodo=?",
        (referido_id, periodo)
    ).fetchone()[0]
    if ventas_mes >= 15:
        return {'porcentaje': 15.0, 'tier': 'top', 'ventas_mes': ventas_mes,
                'next_tier_en': None, 'next_porcentaje': None}
    elif ventas_mes >= 5:
        return {'porcentaje': 11.0, 'tier': 'activo', 'ventas_mes': ventas_mes,
                'next_tier_en': 15 - ventas_mes, 'next_porcentaje': 15.0}
    else:
        return {'porcentaje': 7.0, 'tier': 'base', 'ventas_mes': ventas_mes,
                'next_tier_en': 5 - ventas_mes, 'next_porcentaje': 11.0}


def _comision_producto_referido(precio: float, tier_pct: float) -> dict:
    """Calcula descuento del comprador y comisión ARS del referido para un producto."""
    descuento_pct = _descuento_referido_escalonado(precio)
    precio_con_descuento = round(precio * (1 - descuento_pct / 100), 2)
    comision_ars = round(precio_con_descuento * (tier_pct / 100), 2)
    return {'descuento_pct': descuento_pct, 'precio_con_descuento': precio_con_descuento,
            'comision_ars': comision_ars}


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

    # isolation_level=None desactiva los commits implícitos de Python antes de DDL,
    # lo que permite que DROP + CREATE queden en la misma transacción atómica.
    conn = sqlite3.connect(DB_PATH, isolation_level=None)
    conn.execute("ATTACH DATABASE ? AS src", (str(CATALOGO_REPO_PATH),))
    conn.execute("BEGIN")
    try:
        for tabla in ("productos", "historial_precios", "historial_actualizaciones"):
            src_exists = conn.execute(
                "SELECT COUNT(*) FROM src.sqlite_master WHERE type='table' AND name=?", (tabla,)
            ).fetchone()[0]
            if src_exists:
                conn.execute(f"DROP TABLE IF EXISTS {tabla}")
                conn.execute(f"CREATE TABLE {tabla} AS SELECT * FROM src.{tabla}")
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    finally:
        conn.execute("DETACH DATABASE src")
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
        ("partido", "TEXT DEFAULT ''"),
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
        ("costo_envio", "REAL DEFAULT 0"),
        ("zona_envio", "TEXT DEFAULT ''"),
        ("descuento_codigo", "TEXT"),
        ("descuento_monto", "REAL DEFAULT 0"),
    ]
    cursor.execute("PRAGMA table_info(ordenes)")
    columnas_ordenes_existentes = {row[1] for row in cursor.fetchall()}
    for col_name, col_def in columnas_ordenes_nuevas:
        if col_name not in columnas_ordenes_existentes:
            cursor.execute(f"ALTER TABLE ordenes ADD COLUMN {col_name} {col_def}")

    # Columna de protección de stock manual en productos
    cursor.execute("PRAGMA table_info(productos)")
    columnas_productos_existentes = {row[1] for row in cursor.fetchall()}
    if 'stock_manual' not in columnas_productos_existentes:
        cursor.execute("ALTER TABLE productos ADD COLUMN stock_manual INTEGER NOT NULL DEFAULT 0")

    # Tabla de solicitudes de derecho de arrepentimiento (Ley 24.240 / Disposición 954/2025)
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

    # Usuarios registrados desde el popup de bienvenida (10% OFF en la primera compra)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS usuarios_registrados (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT,
            email TEXT UNIQUE,
            telefono TEXT DEFAULT '',
            codigo_descuento TEXT UNIQUE,
            descuento_usado INTEGER DEFAULT 0,
            creado_at TEXT DEFAULT (datetime('now'))
        )
    """)

    # Columnas de cuenta (login) en usuarios_registrados
    columnas_usuarios_nuevas = [
        ("password_hash", "TEXT DEFAULT ''"),
        ("password_salt", "TEXT DEFAULT ''"),
        ("mayorista", "INTEGER DEFAULT 0"),
    ]
    cursor.execute("PRAGMA table_info(usuarios_registrados)")
    columnas_usuarios_existentes = {row[1] for row in cursor.fetchall()}
    for col_name, col_def in columnas_usuarios_nuevas:
        if col_name not in columnas_usuarios_existentes:
            cursor.execute(f"ALTER TABLE usuarios_registrados ADD COLUMN {col_name} {col_def}")

    # Monto mínimo de carrito para activar un descuento (NULL = sin límite)
    cursor.execute("PRAGMA table_info(descuentos)")
    columnas_descuentos_existentes = {row[1] for row in cursor.fetchall()}
    if 'monto_minimo' not in columnas_descuentos_existentes:
        cursor.execute("ALTER TABLE descuentos ADD COLUMN monto_minimo REAL")

    # Sesiones activas de "Mi cuenta" (login con email + contraseña)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sesiones_usuario (
            token TEXT PRIMARY KEY,
            usuario_id INTEGER NOT NULL,
            creado_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (usuario_id) REFERENCES usuarios_registrados(id)
        )
    """)

    # Campañas de descuento: códigos, descuentos programados por fecha
    # (sobre todos los productos, una categoría o SKUs puntuales) y/o
    # banners promocionales para la home
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS descuentos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            tipo TEXT NOT NULL DEFAULT 'porcentaje',
            valor REAL NOT NULL DEFAULT 0,
            alcance TEXT NOT NULL DEFAULT 'todos',
            categoria TEXT DEFAULT '',
            skus TEXT DEFAULT '[]',
            codigo TEXT UNIQUE,
            email_asociado TEXT,
            fecha_inicio TEXT,
            fecha_fin TEXT,
            activo INTEGER DEFAULT 1,
            uso_maximo INTEGER,
            usos_actuales INTEGER DEFAULT 0,
            mostrar_banner INTEGER DEFAULT 0,
            banner_titulo TEXT DEFAULT '',
            banner_texto TEXT DEFAULT '',
            creado_at TEXT DEFAULT (datetime('now'))
        )
    """)

    # Historial de actualizaciones diarias del catálogo (redeploys automáticos):
    # cuenta y detalle de productos nuevos/agotados/reingresados por corrida
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS historial_actualizaciones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha TEXT DEFAULT (datetime('now')),
            total_productos INTEGER DEFAULT 0,
            nuevos_count INTEGER DEFAULT 0,
            agotados_count INTEGER DEFAULT 0,
            reingresados_count INTEGER DEFAULT 0,
            nuevos_json TEXT DEFAULT '[]',
            agotados_json TEXT DEFAULT '[]',
            reingresados_json TEXT DEFAULT '[]',
            exitoso INTEGER DEFAULT 1
        )
    """)

    # Sistema de referidos: usuarios que comparten su código único a cambio
    # de una comisión del 5% sobre cada venta que generen (pago mensual).
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS referidos (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre    TEXT NOT NULL,
            email     TEXT NOT NULL UNIQUE,
            telefono  TEXT NOT NULL,
            dni       TEXT NOT NULL UNIQUE,
            codigo    TEXT NOT NULL UNIQUE,
            activo    INTEGER NOT NULL DEFAULT 1,
            creado_at TEXT DEFAULT (datetime('now'))
        )
    """)

    # Cada fila = una venta realizada usando el código de un referido.
    # orden_id es UNIQUE para evitar doble conteo si el webhook llega dos veces.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS comisiones_referidos (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            referido_id     INTEGER NOT NULL REFERENCES referidos(id),
            orden_id        INTEGER NOT NULL UNIQUE REFERENCES ordenes(id),
            comprador_email TEXT NOT NULL,
            monto_base      REAL NOT NULL,
            comision        REAL NOT NULL,
            periodo         TEXT NOT NULL,
            pagado          INTEGER NOT NULL DEFAULT 0,
            pagado_at       TEXT,
            creado_at       TEXT DEFAULT (datetime('now'))
        )
    """)

    conn.commit()
    conn.close()

# Ejecutar migración al iniciar
sincronizar_catalogo_persistente()
migrar_db()


# ============================================================================
# AUTENTICACIÓN - CONTRASEÑAS Y SESIONES DE "MI CUENTA"
# ============================================================================

def _hash_password(password: str, salt: Optional[str] = None) -> tuple:
    """Genera (hash, salt) de una contraseña con PBKDF2-HMAC-SHA256."""
    if salt is None:
        salt = secrets.token_hex(16)
    hash_hex = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt.encode("utf-8"), 100_000
    ).hex()
    return hash_hex, salt


def _verificar_password(password: str, password_hash: str, password_salt: str) -> bool:
    """Compara una contraseña en texto plano contra el hash almacenado."""
    if not password_hash or not password_salt:
        return False
    hash_hex, _ = _hash_password(password, password_salt)
    return hmac.compare_digest(hash_hex, password_hash)


def _crear_sesion(usuario_id: int, cursor) -> str:
    """Crea una sesión nueva para 'Mi cuenta' y devuelve el token."""
    token = secrets.token_hex(32)
    cursor.execute(
        "INSERT INTO sesiones_usuario (token, usuario_id) VALUES (?, ?)",
        (token, usuario_id),
    )
    return token


def _extraer_token(authorization: Optional[str]) -> Optional[str]:
    """Extrae el token de un header Authorization: Bearer <token>."""
    if not authorization:
        return None
    if authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    return authorization.strip()


def _usuario_desde_token(token: Optional[str], cursor) -> Optional[dict]:
    """Devuelve el usuario asociado a un token de sesión, o None si no es válido."""
    if not token:
        return None
    cursor.execute("""
        SELECT u.* FROM sesiones_usuario s
        JOIN usuarios_registrados u ON u.id = s.usuario_id
        WHERE s.token = ?
    """, (token,))
    row = cursor.fetchone()
    return dict(row) if row else None


def calcular_envio(provincia: str, partido: str = "") -> dict:
    """
    Determina la zona de envío y su tarifa (costo, modalidad, plazo) según
    la provincia y, si corresponde, el partido del comprador.

    - CABA / Capital Federal -> zona CABA
    - Provincia de Buenos Aires -> zona según el partido (GBA1/GBA2/GBA3/BSAS)
    - Cualquier otra provincia -> RESTO_PAIS
    """
    provincia = (provincia or "").strip()
    partido = (partido or "").strip()

    if provincia == ZONAS_ENVIO["provincia_caba"]:
        zona_id = ZONAS_ENVIO["zona_caba"]
    elif provincia == ZONAS_ENVIO["provincia_buenos_aires"]:
        zona_id = ZONAS_ENVIO["partidos_buenos_aires"].get(
            partido, ZONAS_ENVIO["zona_default_buenos_aires"]
        )
    else:
        zona_id = ZONAS_ENVIO["zona_default_resto_pais"]

    zona = ZONAS_ENVIO["zonas"][zona_id]
    return {
        "zona": zona_id,
        "zona_nombre": zona["nombre"],
        "costo": zona["costo"],
        "modalidad": zona["modalidad"],
        "plazo": zona["plazo"],
    }


def obtener_descuentos_programados(cursor) -> list:
    """Devuelve las campañas de descuento automáticas (sin código) vigentes,
    es decir las que reflejan un precio_oferta directamente en el catálogo."""
    ahora = datetime.now().strftime("%Y-%m-%d")
    cursor.execute("""
        SELECT * FROM descuentos
        WHERE codigo IS NULL AND activo = 1
        AND (fecha_inicio IS NULL OR fecha_inicio = '' OR fecha_inicio <= ?)
        AND (fecha_fin IS NULL OR fecha_fin = '' OR fecha_fin >= ?)
    """, (ahora, ahora))
    return [dict(r) for r in cursor.fetchall()]


def calcular_precio_oferta(producto: dict, descuentos_programados: list) -> Optional[float]:
    """Calcula el precio de oferta de un producto según las campañas vigentes
    que lo alcancen (por SKU, categoría o todos los productos)."""
    precio_venta = producto.get("precio_venta") or 0
    mejor_precio = None

    for d in descuentos_programados:
        alcance = d.get("alcance")
        aplica = False

        if alcance == "todos":
            aplica = True
        elif alcance == "categoria" and d.get("categoria") and d.get("categoria") == producto.get("categoria"):
            aplica = True
        elif alcance == "skus":
            try:
                skus = json.loads(d.get("skus") or "[]")
            except (TypeError, ValueError):
                skus = []
            aplica = producto.get("sku") in skus

        if not aplica:
            continue

        if d.get("tipo") == "porcentaje":
            precio = precio_venta * (1 - (d.get("valor") or 0) / 100)
        else:
            precio = precio_venta - (d.get("valor") or 0)
        precio = max(precio, 0)

        if mejor_precio is None or precio < mejor_precio:
            mejor_precio = precio

    if mejor_precio is not None and mejor_precio < precio_venta:
        return round(mejor_precio, 2)
    return None


def _validar_descuento_row(d: Optional[dict], email: Optional[str], subtotal: float, skus: Optional[List[str]] = None) -> dict:
    """Valida una campaña de descuento con código contra el email y el
    subtotal del carrito, y calcula el monto a descontar."""
    if not d:
        return {"valido": False, "motivo": "Código de descuento inválido"}

    if not d.get("activo"):
        return {"valido": False, "motivo": "Este código ya no está activo"}

    ahora = datetime.now().strftime("%Y-%m-%d")
    if d.get("fecha_inicio") and ahora < d["fecha_inicio"]:
        return {"valido": False, "motivo": "Este código todavía no está vigente"}
    if d.get("fecha_fin") and ahora > d["fecha_fin"]:
        return {"valido": False, "motivo": "Este código expiró"}

    if d.get("uso_maximo") is not None and (d.get("usos_actuales") or 0) >= d["uso_maximo"]:
        return {"valido": False, "motivo": "Este código alcanzó el límite de usos"}

    if d.get("email_asociado"):
        if not email or email.strip().lower() != d["email_asociado"].strip().lower():
            return {"valido": False, "motivo": "Este código no corresponde a tu cuenta"}

    if d.get("monto_minimo") is not None and subtotal < d["monto_minimo"]:
        minimo_fmt = f"${d['monto_minimo']:,.0f}".replace(",", ".")
        return {"valido": False, "motivo": f"Este código requiere un mínimo de {minimo_fmt} en el carrito"}

    # Verificar si el código pertenece a un referido
    if d.get("codigo"):
        try:
            conn_check = sqlite3.connect(DB_PATH)
            ref_row = conn_check.execute(
                "SELECT id, email FROM referidos WHERE codigo = ? AND activo = 1",
                (d["codigo"],)
            ).fetchone()
            conn_check.close()
            if ref_row:
                # Auto-referido bloqueado
                if email and ref_row[1].strip().lower() == email.strip().lower():
                    return {"valido": False, "motivo": "No podés usar tu propio código de referido"}
                # Aplicar descuento escalonado según total del carrito
                porcentaje = _descuento_referido_escalonado(subtotal)
                monto = round(subtotal * porcentaje / 100, 2)
                return {
                    "valido": True,
                    "monto_descuento": monto,
                    "porcentaje_aplicado": porcentaje,
                    "descripcion": d.get("nombre", f"Código de referido {d.get('codigo', '')}"),
                    "id": d.get("id"),
                    "tipo": "referido_escalonado",
                }
        except Exception:
            pass

    if d.get("tipo") == "porcentaje":
        monto = round(subtotal * (d.get("valor") or 0) / 100, 2)
    else:
        monto = round(min(d.get("valor") or 0, subtotal), 2)

    return {
        "valido": True,
        "monto_descuento": monto,
        "descripcion": d.get("nombre", ""),
        "id": d.get("id"),
    }


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


@app.api_route("/health", methods=["GET", "HEAD"])
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
    offset: int = 0,
    incluir_agotados: bool = False
):
    """
    Lista productos con filtros opcionales

    - **categoria**: Filtrar por categoría
    - **search**: Buscar en nombre y descripción
    - **limit**: Cantidad máxima de resultados (default: 500, max: 1000)
    - **offset**: Desplazamiento para paginación
    - **incluir_agotados**: Si es true, incluye productos sin stock (default: false)
    """
    conn = get_db()
    cursor = conn.cursor()

    if incluir_agotados:
        query = "SELECT * FROM productos WHERE 1=1"
    else:
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

    descuentos_programados = obtener_descuentos_programados(cursor)
    conn.close()

    productos_dict = [dict(p) for p in productos]
    for p in productos_dict:
        p["precio_oferta"] = calcular_precio_oferta(p, descuentos_programados)

    return productos_dict


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

    # 1b. Calcular precio de oferta si hay alguna campaña programada vigente
    descuentos_programados = obtener_descuentos_programados(cursor)
    producto_dict['precio_oferta'] = calcular_precio_oferta(producto_dict, descuentos_programados)

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

    # 5. Contar órdenes pagadas que contienen este SKU
    try:
        row = cursor.execute("""
            SELECT COUNT(DISTINCT oi.orden_id)
            FROM orden_items oi
            JOIN ordenes o ON oi.orden_id = o.id
            WHERE oi.producto_sku = ?
              AND o.estado_pago = 'aprobado'
        """, (sku,)).fetchone()
        producto_dict['ventas_count'] = row[0] if row else 0
    except Exception:
        producto_dict['ventas_count'] = 0

    conn.close()

    return producto_dict


@app.get("/api/producto/{sku}/ventas")
def ventas_producto(sku: str):
    """Devuelve la cantidad de órdenes pagadas que contienen este SKU."""
    conn = get_db()
    try:
        row = conn.execute("""
            SELECT COUNT(DISTINCT oi.orden_id)
            FROM orden_items oi
            JOIN ordenes o ON oi.orden_id = o.id
            WHERE oi.producto_sku = ?
              AND o.estado_pago = 'aprobado'
        """, (sku,)).fetchone()
        return {"ventas": row[0] if row else 0}
    except Exception:
        return {"ventas": 0}
    finally:
        conn.close()


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


@app.get("/api/envio/zonas")
def envio_zonas():
    """
    Devuelve el tarifario de zonas de envío y el mapa de partidos de la
    Provincia de Buenos Aires, para que el checkout calcule el costo de
    envío en vivo según la ubicación del comprador.
    """
    return ZONAS_ENVIO


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
# ENDPOINTS - REGISTRO DE USUARIOS Y DESCUENTOS
# ============================================================================

@app.post("/api/registro")
@limiter.limit("3/minute")
def registrar_usuario(request: Request, registro: Registro):
    """
    Crea una cuenta de usuario (nombre, email, teléfono, contraseña) desde el
    popup de bienvenida y le asigna un código de descuento del 10% para su
    primera compra. Si el email ya tiene una cuenta con contraseña, devuelve
    409 para que el usuario inicie sesión en su lugar.
    """
    if len(registro.password) < 6:
        raise HTTPException(status_code=400, detail="La contraseña debe tener al menos 6 caracteres")

    conn = get_db()
    cursor = conn.cursor()

    try:
        cursor.execute("SELECT * FROM usuarios_registrados WHERE email = ?", (registro.email,))
        existente = cursor.fetchone()

        if existente:
            existente_dict = dict(existente)

            if existente_dict.get("password_hash"):
                conn.close()
                raise HTTPException(
                    status_code=409,
                    detail="Ya existe una cuenta con ese email. Iniciá sesión.",
                )

            # Cuenta creada antes de que existieran contraseñas: la completamos ahora
            password_hash, password_salt = _hash_password(registro.password)
            cursor.execute(
                "UPDATE usuarios_registrados SET nombre = ?, telefono = ?, password_hash = ?, password_salt = ? WHERE email = ?",
                (registro.nombre, registro.telefono, password_hash, password_salt, registro.email)
            )
            token = _crear_sesion(existente_dict["id"], cursor)
            conn.commit()
            conn.close()
            return {
                "mensaje": "Cuenta completada",
                "codigo_descuento": existente_dict.get("codigo_descuento"),
                "descuento_usado": existente_dict.get("descuento_usado", 0),
                "nuevo": False,
                "token": token,
                "nombre": registro.nombre,
            }

        codigo = f"BIENVENIDO-{uuid.uuid4().hex[:6].upper()}"
        password_hash, password_salt = _hash_password(registro.password)

        cursor.execute(
            "INSERT INTO usuarios_registrados (nombre, email, telefono, codigo_descuento, password_hash, password_salt) VALUES (?, ?, ?, ?, ?, ?)",
            (registro.nombre, registro.email, registro.telefono, codigo, password_hash, password_salt)
        )
        usuario_id = cursor.lastrowid

        cursor.execute("""
            INSERT INTO descuentos (nombre, tipo, valor, alcance, codigo, email_asociado, activo, uso_maximo)
            VALUES (?, 'porcentaje', 10, 'todos', ?, ?, 1, 1)
        """, (f"Bienvenida {registro.email}", codigo, registro.email))
        token = _crear_sesion(usuario_id, cursor)

        conn.commit()
        conn.close()

        if email_habilitado():
            try:
                enviar_email_bienvenida(registro.nombre, registro.email)
            except Exception as e:
                print(f"⚠️ No se pudo enviar email de bienvenida: {e}")

        return {
            "mensaje": "Registro exitoso",
            "codigo_descuento": codigo,
            "descuento_usado": 0,
            "nuevo": True,
            "token": token,
            "nombre": registro.nombre,
        }

    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        conn.close()
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/login")
@limiter.limit("5/minute")
def login_usuario(request: Request, datos: Login):
    """Inicia sesión en 'Mi cuenta' con email + contraseña y devuelve un token."""
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM usuarios_registrados WHERE email = ?", (datos.email,))
    usuario = cursor.fetchone()

    if not usuario or not _verificar_password(datos.password, usuario["password_hash"], usuario["password_salt"]):
        conn.close()
        raise HTTPException(status_code=401, detail="Email o contraseña incorrectos")

    usuario = dict(usuario)
    token = _crear_sesion(usuario["id"], cursor)
    conn.commit()
    conn.close()

    return {
        "token": token,
        "nombre": usuario["nombre"],
        "email": usuario["email"],
        "telefono": usuario["telefono"],
        "codigo_descuento": usuario["codigo_descuento"],
        "descuento_usado": usuario["descuento_usado"],
    }


@app.post("/api/logout")
def logout_usuario(authorization: Optional[str] = Header(None)):
    """Invalida el token de sesión actual de 'Mi cuenta'."""
    token = _extraer_token(authorization)
    if token:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM sesiones_usuario WHERE token = ?", (token,))
        conn.commit()
        conn.close()
    return {"ok": True}


@app.get("/api/mi_cuenta")
def obtener_mi_cuenta(authorization: Optional[str] = Header(None)):
    """Devuelve los datos de la cuenta del usuario autenticado."""
    conn = get_db()
    cursor = conn.cursor()
    usuario = _usuario_desde_token(_extraer_token(authorization), cursor)
    conn.close()

    if not usuario:
        raise HTTPException(status_code=401, detail="Sesión inválida, iniciá sesión nuevamente")

    mayorista = bool(usuario["mayorista"]) if "mayorista" in usuario.keys() else False
    codigo_mayorista = None
    if mayorista:
        conn2 = get_db()
        row = conn2.execute(
            "SELECT codigo FROM descuentos WHERE email_asociado=? AND monto_minimo=100000 AND activo=1 ORDER BY id DESC LIMIT 1",
            (usuario["email"],)
        ).fetchone()
        conn2.close()
        codigo_mayorista = row[0] if row else None

    return {
        "nombre": usuario["nombre"],
        "email": usuario["email"],
        "telefono": usuario["telefono"],
        "codigo_descuento": usuario["codigo_descuento"],
        "descuento_usado": usuario["descuento_usado"],
        "creado_at": usuario["creado_at"],
        "mayorista": mayorista,
        "codigo_mayorista": codigo_mayorista,
    }


@app.get("/api/mi_cuenta/pedidos")
def obtener_mis_pedidos(authorization: Optional[str] = Header(None)):
    """Devuelve el historial de pedidos del usuario autenticado (por email)."""
    conn = get_db()
    cursor = conn.cursor()
    usuario = _usuario_desde_token(_extraer_token(authorization), cursor)

    if not usuario:
        conn.close()
        raise HTTPException(status_code=401, detail="Sesión inválida, iniciá sesión nuevamente")

    cursor.execute("""
        SELECT o.id, o.total, o.estado, o.estado_pago, o.tracking_url, o.fecha, o.enviado_at
        FROM ordenes o
        JOIN clientes c ON o.cliente_id = c.id
        WHERE LOWER(c.email) = LOWER(?)
        ORDER BY o.fecha DESC
    """, (usuario["email"],))
    pedidos = [dict(r) for r in cursor.fetchall()]

    for pedido in pedidos:
        cursor.execute("""
            SELECT producto_sku AS sku, producto_nombre AS nombre, cantidad, precio_unitario, subtotal
            FROM orden_items WHERE orden_id = ?
        """, (pedido["id"],))
        pedido["items"] = [dict(i) for i in cursor.fetchall()]

    conn.close()
    return {"pedidos": pedidos}


@app.get("/api/admin/usuarios")
def listar_usuarios_registrados(x_admin_password: Optional[str] = Header(None)):
    """Lista los usuarios registrados desde el popup de bienvenida (solo admin)"""
    if not _es_admin(x_admin_password):
        raise HTTPException(status_code=401, detail="No autorizado")

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, nombre, email, telefono, codigo_descuento, descuento_usado, mayorista, creado_at
        FROM usuarios_registrados ORDER BY creado_at DESC
    """)
    usuarios = cursor.fetchall()
    conn.close()

    return [dict(u) for u in usuarios]


@app.get("/api/admin/usuarios/csv")
def exportar_usuarios_csv(x_admin_password: Optional[str] = Header(None)):
    """Exporta los usuarios registrados como CSV (solo admin)"""
    if not _es_admin(x_admin_password):
        raise HTTPException(status_code=401, detail="No autorizado")

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM usuarios_registrados ORDER BY creado_at DESC")
    usuarios = cursor.fetchall()
    conn.close()

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["id", "nombre", "email", "telefono", "codigo_descuento", "descuento_usado", "creado_at"])
    for u in usuarios:
        u = dict(u)
        writer.writerow([
            u["id"], u["nombre"], u["email"], u["telefono"],
            u["codigo_descuento"], u["descuento_usado"], u["creado_at"],
        ])

    return Response(
        content=buffer.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=usuarios_el_gadget.csv"},
    )


@app.delete("/api/admin/usuarios/{usuario_id}")
def eliminar_usuario_registrado(usuario_id: int, x_admin_password: Optional[str] = Header(None)):
    """Elimina un usuario registrado y sus sesiones activas (solo admin)"""
    if not _es_admin(x_admin_password):
        raise HTTPException(status_code=401, detail="No autorizado")

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT id FROM usuarios_registrados WHERE id = ?", (usuario_id,))
    if not cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    cursor.execute("DELETE FROM sesiones_usuario WHERE usuario_id = ?", (usuario_id,))
    cursor.execute("DELETE FROM usuarios_registrados WHERE id = ?", (usuario_id,))
    conn.commit()
    conn.close()

    return {"mensaje": "Usuario eliminado", "usuario_id": usuario_id}


@app.post("/api/admin/usuarios/{usuario_id}/mayorista")
def toggle_mayorista(usuario_id: int, x_admin_password: Optional[str] = Header(None)):
    """Activa o desactiva el precio mayorista (25% off, mínimo $100.000) para un usuario."""
    if not _es_admin(x_admin_password):
        raise HTTPException(status_code=401, detail="No autorizado")

    conn = get_db()
    cursor = conn.cursor()

    usuario = cursor.execute(
        "SELECT id, nombre, email, mayorista FROM usuarios_registrados WHERE id = ?", (usuario_id,)
    ).fetchone()
    if not usuario:
        conn.close()
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    nuevo_estado = 0 if usuario["mayorista"] else 1
    cursor.execute("UPDATE usuarios_registrados SET mayorista = ? WHERE id = ?", (nuevo_estado, usuario_id))

    codigo_may = f"MAY{usuario_id}"

    if nuevo_estado == 1:
        # Crear código mayorista en descuentos si no existe
        existente = cursor.execute(
            "SELECT id FROM descuentos WHERE codigo = ?", (codigo_may,)
        ).fetchone()
        if existente:
            cursor.execute("UPDATE descuentos SET activo = 1 WHERE codigo = ?", (codigo_may,))
        else:
            cursor.execute("""
                INSERT INTO descuentos (nombre, tipo, valor, alcance, codigo, email_asociado, monto_minimo, activo, uso_maximo)
                VALUES (?, 'porcentaje', 25, 'todos', ?, ?, 100000, 1, NULL)
            """, (f"Precio mayorista — {usuario['nombre']}", codigo_may, usuario["email"]))
    else:
        # Desactivar el código mayorista
        cursor.execute("UPDATE descuentos SET activo = 0 WHERE codigo = ?", (codigo_may,))

    conn.commit()
    conn.close()

    return {
        "usuario_id": usuario_id,
        "mayorista": bool(nuevo_estado),
        "codigo_mayorista": codigo_may if nuevo_estado else None,
        "mensaje": f"Precio mayorista {'activado' if nuevo_estado else 'desactivado'}",
    }


@app.post("/api/mayorista/activar")
def activar_mayorista_self(authorization: Optional[str] = Header(None)):
    """Permite a un referido activo activar su precio mayorista de forma autónoma."""
    conn = get_db()
    cursor = conn.cursor()
    usuario = _usuario_desde_token(_extraer_token(authorization), cursor)
    if not usuario:
        conn.close()
        raise HTTPException(status_code=401, detail="Sesión inválida")

    ref = cursor.execute(
        "SELECT id FROM referidos WHERE email = ? AND activo = 1", (usuario["email"],)
    ).fetchone()
    if not ref:
        conn.close()
        raise HTTPException(status_code=403, detail="Solo los referidos activos pueden activar el precio mayorista")

    ya_activo = bool(usuario["mayorista"]) if "mayorista" in usuario.keys() else False
    if ya_activo:
        conn.close()
        return {"mensaje": "Ya tenés precio mayorista activo", "codigo_mayorista": f"MAY{usuario['id']}"}

    cursor.execute("UPDATE usuarios_registrados SET mayorista = 1 WHERE id = ?", (usuario["id"],))
    codigo_may = f"MAY{usuario['id']}"
    existente = cursor.execute("SELECT id FROM descuentos WHERE codigo = ?", (codigo_may,)).fetchone()
    if existente:
        cursor.execute("UPDATE descuentos SET activo = 1 WHERE codigo = ?", (codigo_may,))
    else:
        cursor.execute("""
            INSERT INTO descuentos (nombre, tipo, valor, alcance, codigo, email_asociado, monto_minimo, activo, uso_maximo)
            VALUES (?, 'porcentaje', 25, 'todos', ?, ?, 100000, 1, NULL)
        """, (f"Precio mayorista — {usuario['nombre']}", codigo_may, usuario["email"]))
    conn.commit()
    conn.close()
    return {"mensaje": "Precio mayorista activado", "codigo_mayorista": codigo_may}


@app.get("/api/mayorista/dashboard")
def mayorista_dashboard(authorization: Optional[str] = Header(None)):
    """Dashboard del usuario mayorista: estadísticas + historial de compras propias."""
    conn = get_db()
    cursor = conn.cursor()
    usuario = _usuario_desde_token(_extraer_token(authorization), cursor)
    if not usuario:
        conn.close()
        raise HTTPException(status_code=401, detail="Sesión inválida")

    if not (bool(usuario["mayorista"]) if "mayorista" in usuario.keys() else False):
        conn.close()
        raise HTTPException(status_code=403, detail="No tenés precio mayorista activo")

    codigo_may = f"MAY{usuario['id']}"

    ordenes_rows = cursor.execute("""
        SELECT o.id, o.total, o.estado, o.estado_pago, o.fecha,
               o.costo_envio, o.descuento_monto, o.tracking_url
        FROM ordenes o
        JOIN clientes c ON o.cliente_id = c.id
        WHERE LOWER(c.email) = LOWER(?) AND o.descuento_codigo = ?
        ORDER BY o.fecha DESC
    """, (usuario["email"], codigo_may)).fetchall()

    ordenes = []
    total_pagado = 0.0
    total_ahorrado = 0.0

    for o in ordenes_rows:
        o_dict = dict(o)
        items = cursor.execute("""
            SELECT producto_sku AS sku, producto_nombre AS nombre,
                   cantidad, precio_unitario, subtotal
            FROM orden_items WHERE orden_id = ?
        """, (o_dict["id"],)).fetchall()
        o_dict["items"] = [dict(i) for i in items]
        o_dict["total_normal"] = round(o_dict["total"] + (o_dict["descuento_monto"] or 0), 2)
        total_pagado += o_dict["total"] or 0
        total_ahorrado += o_dict["descuento_monto"] or 0
        ordenes.append(o_dict)

    conn.close()
    return {
        "codigo_mayorista": codigo_may,
        "stats": {
            "total_pagado": round(total_pagado, 2),
            "total_ahorrado": round(total_ahorrado, 2),
            "cantidad_ordenes": len(ordenes),
        },
        "ordenes": ordenes,
    }


@app.get("/api/mayorista/catalogo")
def catalogo_mayorista(
    authorization: Optional[str] = Header(None),
    search: Optional[str] = None,
    categoria: Optional[str] = None,
    precio_min: Optional[float] = None,
    precio_max: Optional[float] = None,
    sort: Optional[str] = "precio",
    order: Optional[str] = "asc",
    page: int = 1,
    limit: int = 50,
):
    """Catálogo con precio mayorista (25% off) para el usuario mayorista autenticado."""
    conn = get_db()
    cursor = conn.cursor()
    usuario = _usuario_desde_token(_extraer_token(authorization), cursor)
    if not usuario:
        conn.close()
        raise HTTPException(status_code=401, detail="Sesión inválida")

    if not (bool(usuario["mayorista"]) if "mayorista" in usuario.keys() else False):
        conn.close()
        raise HTTPException(status_code=403, detail="No tenés precio mayorista activo")

    DESCUENTO_MAYORISTA = 0.25

    categorias = [r[0] for r in cursor.execute(
        "SELECT DISTINCT categoria FROM productos WHERE stock > 0 AND categoria IS NOT NULL ORDER BY categoria"
    ).fetchall()]

    where_clauses = ["stock > 0"]
    params = []

    if search:
        where_clauses.append("(nombre LIKE ? OR sku LIKE ? OR marca LIKE ?)")
        like = f"%{search}%"
        params.extend([like, like, like])
    if categoria:
        where_clauses.append("categoria = ?")
        params.append(categoria)
    if precio_min is not None:
        where_clauses.append("precio_venta >= ?")
        params.append(precio_min)
    if precio_max is not None:
        where_clauses.append("precio_venta <= ?")
        params.append(precio_max)

    where_sql = " AND ".join(where_clauses)
    sort_col_map = {"precio": "precio_venta", "nombre": "nombre", "ahorro": "precio_venta"}
    sort_col = sort_col_map.get(sort, "precio_venta")
    order_sql = "DESC" if order == "desc" else "ASC"
    if sort == "nombre":
        order_sql = "ASC" if order != "desc" else "DESC"

    total_count = cursor.execute(
        f"SELECT COUNT(*) FROM productos WHERE {where_sql}", params
    ).fetchone()[0]

    offset = (page - 1) * limit
    rows = cursor.execute(
        f"""SELECT sku, nombre, precio_venta, categoria, marca, imagen_principal, stock, url_amigable
            FROM productos WHERE {where_sql}
            ORDER BY {sort_col} {order_sql}
            LIMIT ? OFFSET ?""",
        params + [limit, offset]
    ).fetchall()

    productos = []
    for r in rows:
        sku, nombre, precio, cat, marca, imagen, stock, url_amigable = r
        precio_normal = float(precio)
        ahorro = round(precio_normal * DESCUENTO_MAYORISTA, 2)
        precio_mayorista = round(precio_normal * (1 - DESCUENTO_MAYORISTA), 2)
        if not imagen or imagen.strip() == '':
            imagen_url = f"https://res.cloudinary.com/deq2ofluf/image/upload/prod_{sku}_001"
        else:
            imagen_url = imagen
        if url_amigable and url_amigable.strip():
            url_tienda = f"https://elgadget.com.ar/producto/{url_amigable.strip()}/"
        else:
            url_tienda = f"https://elgadget.com.ar/producto_detalle?sku={sku}"
        productos.append({
            "sku": sku,
            "nombre": nombre,
            "precio_normal": precio_normal,
            "precio_mayorista": precio_mayorista,
            "ahorro": ahorro,
            "categoria": cat,
            "marca": marca,
            "imagen_url": imagen_url,
            "stock": stock,
            "url_tienda": url_tienda,
        })

    conn.close()
    return {
        "categorias": categorias,
        "total": total_count,
        "page": page,
        "limit": limit,
        "pages": -(-total_count // limit),
        "productos": productos,
    }


@app.get("/api/descuentos/activos")
def descuentos_activos():
    """Devuelve la campaña activa (vigente) que deba mostrarse como banner
    promocional en la home, si existe."""
    conn = get_db()
    cursor = conn.cursor()

    ahora = datetime.now().strftime("%Y-%m-%d")
    cursor.execute("""
        SELECT * FROM descuentos
        WHERE mostrar_banner = 1 AND activo = 1
        AND (fecha_inicio IS NULL OR fecha_inicio = '' OR fecha_inicio <= ?)
        AND (fecha_fin IS NULL OR fecha_fin = '' OR fecha_fin >= ?)
        ORDER BY id DESC LIMIT 1
    """, (ahora, ahora))
    banner = cursor.fetchone()
    conn.close()

    if not banner:
        return {"banner": None}

    banner_dict = dict(banner)
    return {
        "banner": {
            "titulo": banner_dict.get("banner_titulo") or "",
            "texto": banner_dict.get("banner_texto") or "",
            "codigo": banner_dict.get("codigo"),
        }
    }


@app.post("/api/descuentos/validar")
@limiter.limit("10/minute")
def validar_descuento(request: Request, datos: ValidarDescuento):
    """Valida un código de descuento y calcula el monto a aplicar sobre el subtotal"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM descuentos WHERE UPPER(codigo) = UPPER(?)", (datos.codigo,))
    fila = cursor.fetchone()
    conn.close()

    resultado = _validar_descuento_row(dict(fila) if fila else None, datos.email, datos.subtotal, datos.skus)
    return resultado


@app.get("/api/admin/descuentos")
def listar_descuentos(x_admin_password: Optional[str] = Header(None)):
    """Lista las campañas de descuento gestionables (solo admin).

    Excluye los códigos de bienvenida (10% por registro) generados
    automáticamente para cada usuario: son una regla fija del sitio,
    no una campaña que se administre desde el panel.
    """
    if not _es_admin(x_admin_password):
        raise HTTPException(status_code=401, detail="No autorizado")

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM descuentos WHERE email_asociado IS NULL ORDER BY id DESC")
    descuentos = cursor.fetchall()
    conn.close()

    resultado = []
    for d in descuentos:
        d = dict(d)
        try:
            d["skus"] = json.loads(d.get("skus") or "[]")
        except (TypeError, ValueError):
            d["skus"] = []
        resultado.append(d)

    return resultado


@app.post("/api/admin/descuentos")
def crear_descuento(datos: Descuento, x_admin_password: Optional[str] = Header(None)):
    """Crea una nueva campaña de descuento (código, programado o banner) (solo admin)"""
    if not _es_admin(x_admin_password):
        raise HTTPException(status_code=401, detail="No autorizado")

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO descuentos (
            nombre, tipo, valor, alcance, categoria, skus, codigo, email_asociado,
            fecha_inicio, fecha_fin, activo, uso_maximo, mostrar_banner, banner_titulo, banner_texto
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        datos.nombre, datos.tipo, datos.valor, datos.alcance, datos.categoria or "",
        json.dumps(datos.skus or []), (datos.codigo or None), (datos.email_asociado or None),
        (datos.fecha_inicio or None), (datos.fecha_fin or None), 1 if datos.activo else 0,
        datos.uso_maximo, 1 if datos.mostrar_banner else 0,
        datos.banner_titulo or "", datos.banner_texto or "",
    ))
    conn.commit()
    descuento_id = cursor.lastrowid
    conn.close()

    return {"id": descuento_id, "mensaje": "Descuento creado"}


@app.patch("/api/admin/descuentos/{descuento_id}")
def editar_descuento(descuento_id: int, datos: Descuento, x_admin_password: Optional[str] = Header(None)):
    """Edita una campaña de descuento existente (solo admin)"""
    if not _es_admin(x_admin_password):
        raise HTTPException(status_code=401, detail="No autorizado")

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM descuentos WHERE id = ?", (descuento_id,))
    if not cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail="Descuento no encontrado")

    cursor.execute("""
        UPDATE descuentos SET
            nombre = ?, tipo = ?, valor = ?, alcance = ?, categoria = ?, skus = ?,
            codigo = ?, email_asociado = ?, fecha_inicio = ?, fecha_fin = ?,
            activo = ?, uso_maximo = ?, mostrar_banner = ?, banner_titulo = ?, banner_texto = ?
        WHERE id = ?
    """, (
        datos.nombre, datos.tipo, datos.valor, datos.alcance, datos.categoria or "",
        json.dumps(datos.skus or []), (datos.codigo or None), (datos.email_asociado or None),
        (datos.fecha_inicio or None), (datos.fecha_fin or None), 1 if datos.activo else 0,
        datos.uso_maximo, 1 if datos.mostrar_banner else 0,
        datos.banner_titulo or "", datos.banner_texto or "",
        descuento_id,
    ))
    conn.commit()
    conn.close()

    return {"mensaje": "Descuento actualizado"}


@app.delete("/api/admin/descuentos/{descuento_id}")
def eliminar_descuento(descuento_id: int, x_admin_password: Optional[str] = Header(None)):
    """Elimina una campaña de descuento (solo admin)"""
    if not _es_admin(x_admin_password):
        raise HTTPException(status_code=401, detail="No autorizado")

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM descuentos WHERE id = ?", (descuento_id,))
    if not cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail="Descuento no encontrado")

    cursor.execute("DELETE FROM descuentos WHERE id = ?", (descuento_id,))
    conn.commit()
    conn.close()

    return {"mensaje": "Descuento eliminado"}


# ============================================================================
# ENDPOINTS - ÓRDENES
# ============================================================================

@app.post("/api/orden")
@limiter.limit("5/minute")
def crear_orden(request: Request, orden: CrearOrden):
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
                    direccion = ?, pais = ?, provincia = ?, partido = ?, ciudad = ?,
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
                orden.cliente.partido or "",
                orden.cliente.ciudad,
                orden.cliente.codigo_postal,
                orden.cliente.cuit_dni or "",
                cliente_id
            ))
        else:
            # Crear nuevo cliente
            cursor.execute("""
                INSERT INTO clientes (nombre, apellido, razon_social, email, telefono,
                    calle, altura, piso, departamento, direccion, pais, provincia, partido, ciudad,
                    codigo_postal, cuit_dni)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                orden.cliente.partido or "",
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
            
            if item.cantidad > 15:
                raise HTTPException(
                    status_code=400,
                    detail=f"El máximo por producto es 15 unidades ({producto['nombre']}). Para compras de mayor volumen escribinos por WhatsApp."
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
        
        # 2.2 Validar y aplicar código de descuento (sobre el subtotal de productos)
        subtotal_productos = total
        descuento_codigo = None
        descuento_monto = 0
        descuento_fila = None
        if orden.codigo_descuento:
            cursor.execute("SELECT * FROM descuentos WHERE UPPER(codigo) = UPPER(?)", (orden.codigo_descuento,))
            fila = cursor.fetchone()
            resultado = _validar_descuento_row(
                dict(fila) if fila else None, orden.cliente.email, total,
                [item.sku for item in orden.items]
            )
            if not resultado.get("valido"):
                raise HTTPException(status_code=400, detail=resultado.get("motivo", "Código de descuento inválido"))

            descuento_fila = dict(fila)
            descuento_codigo = descuento_fila["codigo"]
            descuento_monto = resultado["monto_descuento"]
            total -= descuento_monto

        # 2.1 Calcular costo de envío según zona del cliente
        envio = calcular_envio(orden.cliente.provincia or "", orden.cliente.partido or "")
        total += envio["costo"]

        # 3. Crear orden
        cursor.execute("""
            INSERT INTO ordenes (cliente_id, total, estado, notas, costo_envio, zona_envio, descuento_codigo, descuento_monto)
            VALUES (?, ?, 'pendiente_procesar', ?, ?, ?, ?, ?)
        """, (cliente_id, total, orden.notas or "", envio["costo"], envio["zona"], descuento_codigo, descuento_monto))

        orden_id = cursor.lastrowid

        # 3.1 Registrar el uso del código de descuento
        if descuento_fila:
            cursor.execute(
                "UPDATE descuentos SET usos_actuales = usos_actuales + 1 WHERE id = ?",
                (descuento_fila["id"],)
            )
            if descuento_fila.get("email_asociado"):
                cursor.execute(
                    "UPDATE usuarios_registrados SET descuento_usado = 1 WHERE email = ?",
                    (descuento_fila["email_asociado"],)
                )
        
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
            # Si hay descuento, se prorratea entre los items para que el total
            # cobrado por MP coincida con el total de la orden (MP no admite
            # ítems con precio negativo)
            factor_descuento = (
                (subtotal_productos - descuento_monto) / subtotal_productos
                if descuento_monto and subtotal_productos > 0 else 1
            )
            mp_items = [
                {
                    "id": item['sku'],
                    "title": item['nombre'],
                    "quantity": item['cantidad'],
                    "unit_price": round(float(item['precio_unitario']) * factor_descuento, 2),
                    "currency_id": "ARS"
                }
                for item in items_con_precio
            ]
            if envio["costo"] > 0:
                mp_items.append({
                    "id": "envio",
                    "title": f"Costo de envío ({envio['zona_nombre']})",
                    "quantity": 1,
                    "unit_price": float(envio["costo"]),
                    "currency_id": "ARS"
                })
            preference_data = {
                "items": mp_items,
                "payer": {
                    "name": orden.cliente.nombre,
                    "surname": orden.cliente.apellido or "",
                    "email": orden.cliente.email,
                    "phone": {"number": orden.cliente.telefono}
                },
                "back_urls": {
                    "success": f"{SITE_URL}/confirmacion?orden_id={orden_id}&status=approved",
                    "failure": f"{SITE_URL}/confirmacion?orden_id={orden_id}&status=failure",
                    "pending": f"{SITE_URL}/confirmacion?orden_id={orden_id}&status=pending"
                },
                "auto_return": "approved",
                "external_reference": str(orden_id),
                "notification_url": f"{API_URL}/api/mp/webhook",
                "statement_descriptor": "EL GADGET TIENDA"
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
            "costo_envio": envio["costo"],
            "zona_envio": envio["zona"],
            "zona_envio_nombre": envio["zona_nombre"],
            "plazo_envio": envio["plazo"],
            "descuento_codigo": descuento_codigo,
            "descuento_monto": descuento_monto,
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
    # Verificar firma HMAC-SHA256 enviada por MercadoPago en x-signature
    if MP_WEBHOOK_SECRET:
        sig_header = request.headers.get('x-signature', '')
        request_id = request.headers.get('x-request-id', '')
        ts = v1 = ''
        for part in sig_header.split(','):
            k, _, val = part.partition('=')
            if k.strip() == 'ts':
                ts = val.strip()
            elif k.strip() == 'v1':
                v1 = val.strip()
        data_id = request.query_params.get('data.id', '')
        template = f"id:{data_id};request-id:{request_id};ts:{ts}"
        expected = hmac.new(
            MP_WEBHOOK_SECRET.encode(), template.encode(), hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(expected, v1):
            print(f"Webhook MP: firma inválida (template={template!r})")
            return JSONResponse(status_code=400, content={"error": "invalid signature"})

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

    # Registrar comisión de referido si la orden usó un código de referido activo
    try:
        codigo_usado = orden.get('descuento_codigo')
        if codigo_usado:
            ref = cursor.execute(
                "SELECT id FROM referidos WHERE codigo = ? AND activo = 1",
                (codigo_usado,)
            ).fetchone()
            if ref:
                monto_base = max(0.0, float(orden.get('total') or 0) - float(orden.get('costo_envio') or 0))
                tier = _get_tier_comision(ref[0], conn)
                comision = round(monto_base * (tier['porcentaje'] / 100), 2)
                periodo = datetime.now().strftime('%Y-%m')
                cursor.execute("""
                    INSERT OR IGNORE INTO comisiones_referidos
                        (referido_id, orden_id, comprador_email, monto_base, comision, periodo)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (ref[0], orden_id, orden.get('email', ''), monto_base, comision, periodo))
                conn.commit()
    except Exception:
        pass  # best-effort: no interrumpir el flujo por error en comisiones


@app.post("/api/admin/orden/{orden_id}/procesar-pago")
def admin_procesar_pago(orden_id: int, x_admin_password: Optional[str] = Header(None)):
    """
    Dispara manualmente la generación de Factura C (AFIP) + email de
    confirmación para una orden (solo admin). Útil para reintentar si
    falló en el webhook, o para probar la integración sin un pago nuevo.
    """
    if not _es_admin(x_admin_password):
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
    if not _es_admin(x_admin_password):
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
    if not _es_admin(x_admin_password):
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


@app.post("/api/admin/backup")
def crear_backup(x_admin_password: Optional[str] = Header(None)):
    """Exporta órdenes, clientes y referidos a JSON. Guarda copia en disco persistente."""
    if not _es_admin(x_admin_password):
        raise HTTPException(status_code=401, detail="No autorizado")

    conn = get_db()
    tablas: dict = {}
    for tabla in ("ordenes", "clientes", "referidos", "comisiones_referidos"):
        existe = conn.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name=?", (tabla,)
        ).fetchone()[0]
        tablas[tabla] = [dict(r) for r in conn.execute(f"SELECT * FROM {tabla}").fetchall()] if existe else []
    conn.close()

    backup = {"fecha": datetime.now().isoformat(), **tablas}

    if _persistent_dir:
        backup_dir = Path(_persistent_dir) / "backups"
        backup_dir.mkdir(exist_ok=True)
        (backup_dir / f"backup_{datetime.now().strftime('%Y-%m-%d')}.json").write_text(
            json.dumps(backup, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        for viejo in sorted(backup_dir.glob("backup_*.json"))[:-30]:
            viejo.unlink()

    return backup


@app.get("/api/clientes")
def listar_clientes(x_admin_password: Optional[str] = Header(None)):
    """Lista clientes con cantidad de órdenes y total comprado (solo admin)"""
    if not _es_admin(x_admin_password):
        raise HTTPException(status_code=401, detail="No autorizado")

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT c.*,
               COUNT(o.id) AS cantidad_ordenes,
               COALESCE(SUM(CASE WHEN o.estado_pago = 'approved' THEN o.total ELSE 0 END), 0) AS total_comprado
        FROM clientes c
        LEFT JOIN ordenes o ON o.cliente_id = c.id
        GROUP BY c.id
        ORDER BY c.id DESC
    """)
    clientes = cursor.fetchall()
    conn.close()

    return [dict(c) for c in clientes]


@app.delete("/api/admin/clientes/{cliente_id}")
def eliminar_cliente(cliente_id: int, x_admin_password: Optional[str] = Header(None)):
    """
    Elimina un cliente (solo admin). No se permite si tiene órdenes asociadas,
    para no dejar pedidos/facturas huérfanos: hay que eliminar primero esas
    órdenes desde la pestaña Pedidos.
    """
    if not _es_admin(x_admin_password):
        raise HTTPException(status_code=401, detail="No autorizado")

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT id FROM clientes WHERE id = ?", (cliente_id,))
    if not cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail="Cliente no encontrado")

    cursor.execute("SELECT COUNT(*) as total FROM ordenes WHERE cliente_id = ?", (cliente_id,))
    cantidad_ordenes = cursor.fetchone()['total']
    if cantidad_ordenes > 0:
        conn.close()
        raise HTTPException(
            status_code=409,
            detail=f"No se puede eliminar: el cliente tiene {cantidad_ordenes} pedido(s) asociado(s)"
        )

    cursor.execute("DELETE FROM clientes WHERE id = ?", (cliente_id,))
    conn.commit()
    conn.close()

    return {"mensaje": "Cliente eliminado", "cliente_id": cliente_id}


@app.patch("/api/admin/producto/{sku}")
def actualizar_producto(sku: str, datos: ActualizarProducto, x_admin_password: Optional[str] = Header(None)):
    """
    Edita manualmente nombre, descripción, categoría, precio de venta o stock
    de un producto en la base en vivo (solo admin). Usado por el Panel de
    escritorio; los mismos cambios se guardan también en data/catalogo.db
    como overrides_manuales para que sobrevivan a la sincronización diaria.
    """
    if not _es_admin(x_admin_password):
        raise HTTPException(status_code=401, detail="No autorizado")

    cambios = datos.dict(exclude_unset=True)
    if not cambios:
        raise HTTPException(status_code=400, detail="No se enviaron cambios")

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT sku, overrides_manuales FROM productos WHERE sku = ?", (sku,))
    fila = cursor.fetchone()
    if not fila:
        conn.close()
        raise HTTPException(status_code=404, detail="Producto no encontrado")

    overrides = {}
    if fila['overrides_manuales']:
        try:
            overrides = json.loads(fila['overrides_manuales'])
        except Exception:
            overrides = {}

    stock_manual_val = cambios.pop('stock_manual', None)

    columnas = []
    valores = []

    for campo in ('nombre', 'descripcion', 'categoria', 'precio_venta', 'imagen_principal', 'imagenes_adicionales'):
        if campo in cambios:
            columnas.append(campo)
            valores.append(cambios[campo])
            if campo in ('categoria', 'precio_venta', 'imagen_principal', 'imagenes_adicionales'):
                overrides[campo] = cambios[campo]

    if 'nombre' in cambios or 'descripcion' in cambios:
        columnas.append('seo_optimizado_at')
        valores.append(datetime.now().strftime('%Y-%m-%d %H:%M:%S'))

    if 'stock' in cambios:
        columnas.append('stock')
        valores.append(cambios['stock'])
        protect = stock_manual_val is not False
        columnas.append('stock_manual')
        valores.append(1 if protect else 0)
        if protect:
            overrides['stock'] = cambios['stock']
        else:
            overrides.pop('stock', None)
    elif stock_manual_val is False:
        columnas.append('stock_manual')
        valores.append(0)
        overrides.pop('stock', None)

    columnas.append('overrides_manuales')
    valores.append(json.dumps(overrides, ensure_ascii=False) if overrides else None)

    set_clause = ", ".join(f"{col} = ?" for col in columnas)
    cursor.execute(f"UPDATE productos SET {set_clause} WHERE sku = ?", (*valores, sku))
    conn.commit()

    cursor.execute("SELECT * FROM productos WHERE sku = ?", (sku,))
    producto = dict(cursor.fetchone())
    conn.close()

    return producto


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
# ENDPOINTS - BOTÓN DE ARREPENTIMIENTO (Ley 24.240 / Disposición 954/2025)
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
    if not _es_admin(x_admin_password):
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
    if not _es_admin(x_admin_password):
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

    # Ventas por mes (últimos 6 meses con ventas)
    cursor.execute("""
        SELECT strftime('%Y-%m', fecha) as mes, SUM(total) as total, COUNT(*) as cantidad
        FROM ordenes
        WHERE estado_pago = 'approved'
        GROUP BY mes
        ORDER BY mes DESC
        LIMIT 6
    """)
    ventas_por_mes = [dict(r) for r in cursor.fetchall()][::-1]

    # Top 5 productos por cantidad vendida
    cursor.execute("""
        SELECT oi.producto_sku as sku, oi.producto_nombre as nombre,
               SUM(oi.cantidad) as cantidad_vendida, SUM(oi.subtotal) as total_vendido
        FROM orden_items oi
        JOIN ordenes o ON oi.orden_id = o.id
        WHERE o.estado_pago = 'approved'
        GROUP BY oi.producto_sku, oi.producto_nombre
        ORDER BY cantidad_vendida DESC
        LIMIT 5
    """)
    top_productos = [dict(r) for r in cursor.fetchall()]

    # Facturación AFIP
    cursor.execute("SELECT COUNT(*) as total FROM ordenes WHERE factura_cae IS NOT NULL")
    facturas_emitidas = cursor.fetchone()['total']

    cursor.execute("""
        SELECT COUNT(*) as total FROM ordenes
        WHERE estado_pago = 'approved' AND factura_cae IS NULL
    """)
    pedidos_sin_facturar = cursor.fetchone()['total']

    # Usuarios registrados (popup de bienvenida / "Mi cuenta")
    cursor.execute("SELECT COUNT(*) as total FROM usuarios_registrados")
    total_usuarios = cursor.fetchone()['total']

    # Estado de optimización SEO automática (solo productos con stock,
    # que son los elegibles para 13_optimizar_seo_ia.py)
    cursor.execute("SELECT COUNT(*) as total FROM productos WHERE stock > 0 AND seo_optimizado_at IS NOT NULL")
    seo_optimizados = cursor.fetchone()['total']

    cursor.execute("SELECT COUNT(*) as total FROM productos WHERE stock > 0 AND seo_optimizado_at IS NULL")
    seo_pendientes = cursor.fetchone()['total']

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
        "ventas_totales": ventas,
        "ventas_por_mes": ventas_por_mes,
        "top_productos": top_productos,
        "facturas_emitidas": facturas_emitidas,
        "pedidos_sin_facturar": pedidos_sin_facturar,
        "usuarios_registrados": total_usuarios,
        "seo": {
            "optimizados": seo_optimizados,
            "pendientes": seo_pendientes
        }
    }


# ============================================================================
# ENDPOINTS - HISTORIAL DE ACTUALIZACIONES (redeploys automáticos)
# ============================================================================

@app.get("/api/admin/historial")
def listar_historial_actualizaciones(
    limit: int = Query(30, le=200),
    x_admin_password: Optional[str] = Header(None)
):
    """
    Lista las corridas de la actualización diaria automática del catálogo
    (redeploys), ordenadas por fecha descendente, con el detalle de
    productos nuevos/agotados/reingresados de cada corrida (solo admin).
    """
    if not _es_admin(x_admin_password):
        raise HTTPException(status_code=401, detail="No autorizado")

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, fecha, total_productos, nuevos_count, agotados_count,
               reingresados_count, nuevos_json, agotados_json, reingresados_json, exitoso
        FROM historial_actualizaciones
        ORDER BY fecha DESC, id DESC
        LIMIT ?
    """, (limit,))
    filas = cursor.fetchall()
    conn.close()

    historial = []
    for fila in filas:
        item = dict(fila)
        for campo in ("nuevos_json", "agotados_json", "reingresados_json"):
            clave = campo.replace("_json", "")
            try:
                item[clave] = json.loads(item.pop(campo) or "[]")
            except (json.JSONDecodeError, TypeError):
                item[clave] = []
        historial.append(item)

    return historial


# ============================================================================
# REFERIDOS
# ============================================================================

@app.post("/api/referidos/registro")
def registro_referido(datos: RegistroReferido):
    """
    Registra un usuario en el programa de referidos. Si ya tiene cuenta de
    usuario (mismo email), la vincula y le agrega DNI + código. Si no tiene
    cuenta, la crea junto con el perfil de referido.
    """
    conn = get_db()
    cursor = conn.cursor()

    # Verificar que el DNI no esté ya registrado
    if cursor.execute("SELECT 1 FROM referidos WHERE dni = ?", (datos.dni,)).fetchone():
        conn.close()
        raise HTTPException(status_code=409, detail="Ese DNI ya está registrado en el programa de referidos")

    # Verificar que el email no tenga ya un perfil de referido
    if cursor.execute("SELECT 1 FROM referidos WHERE email = ?", (datos.email.lower(),)).fetchone():
        conn.close()
        raise HTTPException(status_code=409, detail="Ese email ya está registrado en el programa de referidos")

    # Crear o recuperar la cuenta de usuario
    usuario = cursor.execute(
        "SELECT id, nombre FROM usuarios_registrados WHERE email = ?", (datos.email.lower(),)
    ).fetchone()

    token = None
    if not usuario:
        password_salt = secrets.token_hex(32)
        password_hash = hashlib.pbkdf2_hmac(
            'sha256', datos.password.encode(), password_salt.encode(), 260000
        ).hex()
        codigo_bienvenida = f"BIENVENIDO-{uuid.uuid4().hex[:6].upper()}"
        cursor.execute("""
            INSERT INTO usuarios_registrados (nombre, email, telefono, codigo_descuento, password_hash, password_salt)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (datos.nombre, datos.email.lower(), datos.telefono, codigo_bienvenida, password_hash, password_salt))
        usuario_id = cursor.lastrowid
        cursor.execute("""
            INSERT OR IGNORE INTO descuentos (nombre, tipo, valor, alcance, codigo, email_asociado, activo, uso_maximo)
            VALUES (?, 'porcentaje', 10, 'todos', ?, ?, 1, 1)
        """, (f"Bienvenida: {datos.nombre}", codigo_bienvenida, datos.email.lower()))
        token = secrets.token_hex(32)
        cursor.execute("INSERT INTO sesiones_usuario (token, usuario_id) VALUES (?, ?)", (token, usuario_id))
    else:
        usuario_id = usuario[0]
        token_row = cursor.execute(
            "INSERT INTO sesiones_usuario (token, usuario_id) VALUES (?, ?) RETURNING token",
            (secrets.token_hex(32), usuario_id)
        ).fetchone()
        token = token_row[0] if token_row else secrets.token_hex(32)

    # Generar código único de referido
    codigo = _generar_codigo_referido(datos.nombre, datos.telefono, conn)

    cursor.execute("""
        INSERT INTO referidos (nombre, email, telefono, dni, codigo)
        VALUES (?, ?, ?, ?, ?)
    """, (datos.nombre, datos.email.lower(), datos.telefono, datos.dni, codigo))

    # Insertar el código en la tabla descuentos (15% off, ilimitado, para todos)
    cursor.execute("""
        INSERT OR IGNORE INTO descuentos (nombre, tipo, valor, alcance, codigo, activo)
        VALUES (?, 'porcentaje', 15, 'todos', ?, 1)
    """, (f"Referido: {datos.nombre}", codigo))

    conn.commit()
    conn.close()

    try:
        enviar_email_referido_confirmacion(datos.nombre, datos.email, codigo)
    except Exception as e:
        print(f"Email confirmación referido fallido: {e}")

    try:
        admin_email = _env.get('ADMIN_EMAIL', 'damianes1802@gmail.com')
        enviar_email_referido_admin(datos.nombre, datos.email, codigo, admin_email)
    except Exception as e:
        print(f"Email notificación admin referido fallido: {e}")

    return {"codigo": codigo, "token": token, "nombre": datos.nombre,
            "mensaje": f"¡Bienvenido al programa de referidos! Tu código es {codigo}"}


@app.get("/api/referidos/dashboard")
def dashboard_referido(authorization: Optional[str] = Header(None)):
    """Dashboard del referido autenticado: su código, comisiones por periodo y totales."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Token requerido")
    token = authorization.split(" ", 1)[1]

    conn = get_db()
    cursor = conn.cursor()

    sesion = cursor.execute(
        "SELECT usuario_id FROM sesiones_usuario WHERE token = ?", (token,)
    ).fetchone()
    if not sesion:
        conn.close()
        raise HTTPException(status_code=401, detail="Sesión inválida o expirada")

    usuario = cursor.execute(
        "SELECT email FROM usuarios_registrados WHERE id = ?", (sesion[0],)
    ).fetchone()
    if not usuario:
        conn.close()
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    ref = cursor.execute(
        "SELECT * FROM referidos WHERE email = ?", (usuario[0],)
    ).fetchone()
    if not ref:
        conn.close()
        raise HTTPException(status_code=404, detail="No estás registrado en el programa de referidos")
    ref = dict(ref)

    comisiones = cursor.execute("""
        SELECT comprador_email, monto_base, comision, periodo, pagado, pagado_at, creado_at
        FROM comisiones_referidos
        WHERE referido_id = ?
        ORDER BY creado_at DESC
    """, (ref['id'],)).fetchall()
    comisiones = [dict(c) for c in comisiones]

    # Totales agrupados por periodo
    periodos = {}
    for c in comisiones:
        p = c['periodo']
        if p not in periodos:
            periodos[p] = {'periodo': p, 'cantidad_ventas': 0, 'monto_total': 0.0,
                           'comision_total': 0.0, 'comision_pendiente': 0.0, 'pagado': True}
        periodos[p]['cantidad_ventas'] += 1
        periodos[p]['monto_total'] = round(periodos[p]['monto_total'] + c['monto_base'], 2)
        periodos[p]['comision_total'] = round(periodos[p]['comision_total'] + c['comision'], 2)
        if not c['pagado']:
            periodos[p]['comision_pendiente'] = round(periodos[p]['comision_pendiente'] + c['comision'], 2)
            periodos[p]['pagado'] = False

    tier = _get_tier_comision(ref['id'], conn)

    # Próximo cobro: día 5 del mes siguiente
    from datetime import date
    hoy = date.today()
    if hoy.month == 12:
        proximo_cobro = f"5 de enero {hoy.year + 1}"
    else:
        nombres_meses = ['enero','febrero','marzo','abril','mayo','junio',
                         'julio','agosto','septiembre','octubre','noviembre','diciembre']
        proximo_cobro = f"5 de {nombres_meses[hoy.month]} {hoy.year}"

    conn.close()
    return {
        "nombre": ref['nombre'], "email": ref['email'],
        "codigo": ref['codigo'], "activo": bool(ref['activo']),
        "creado_at": ref['creado_at'],
        "tier": tier,
        "proximo_cobro": proximo_cobro,
        "comisiones": comisiones,
        "resumen_por_periodo": sorted(periodos.values(), key=lambda x: x['periodo'], reverse=True),
        "total_comision": round(sum(c['comision'] for c in comisiones), 2),
        "total_pendiente": round(sum(c['comision'] for c in comisiones if not c['pagado']), 2),
    }


@app.get("/api/referidos/catalogo")
def catalogo_referido(
    authorization: Optional[str] = Header(None),
    search: Optional[str] = None,
    categoria: Optional[str] = None,
    precio_min: Optional[float] = None,
    precio_max: Optional[float] = None,
    sort: Optional[str] = "comision",  # comision | precio | nombre
    order: Optional[str] = "desc",
    page: int = 1,
    limit: int = 50,
):
    """Catálogo de productos con comisión por producto para el referido autenticado."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Token requerido")
    token = authorization.split(" ", 1)[1]

    conn = get_db()
    cursor = conn.cursor()

    sesion = cursor.execute(
        "SELECT usuario_id FROM sesiones_usuario WHERE token = ?", (token,)
    ).fetchone()
    if not sesion:
        conn.close()
        raise HTTPException(status_code=401, detail="Sesión inválida o expirada")

    usuario = cursor.execute(
        "SELECT email FROM usuarios_registrados WHERE id = ?", (sesion[0],)
    ).fetchone()
    if not usuario:
        conn.close()
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    ref = cursor.execute(
        "SELECT id, codigo FROM referidos WHERE email = ? AND activo = 1", (usuario[0],)
    ).fetchone()
    if not ref:
        conn.close()
        raise HTTPException(status_code=404, detail="No estás registrado en el programa de referidos")

    tier = _get_tier_comision(ref[0], conn)
    tier_pct = tier['porcentaje']

    # Categorías disponibles
    categorias = [r[0] for r in cursor.execute(
        "SELECT DISTINCT categoria FROM productos WHERE stock > 0 AND categoria IS NOT NULL ORDER BY categoria"
    ).fetchall()]

    # Construir query con filtros
    where_clauses = ["stock > 0"]
    params = []

    if search:
        where_clauses.append("(nombre LIKE ? OR sku LIKE ? OR marca LIKE ?)")
        like = f"%{search}%"
        params.extend([like, like, like])
    if categoria:
        where_clauses.append("categoria = ?")
        params.append(categoria)
    if precio_min is not None:
        where_clauses.append("precio_venta >= ?")
        params.append(precio_min)
    if precio_max is not None:
        where_clauses.append("precio_venta <= ?")
        params.append(precio_max)

    where_sql = " AND ".join(where_clauses)

    # Mapeo de columnas para sort
    sort_col_map = {"precio": "precio_venta", "nombre": "nombre", "comision": "precio_venta"}
    sort_col = sort_col_map.get(sort, "precio_venta")
    order_sql = "DESC" if order == "desc" else "ASC"
    # Para comisión desc = precio desc (comisión es proporcional al precio)
    if sort == "nombre":
        order_sql = "ASC" if order != "desc" else "DESC"

    total_count = cursor.execute(
        f"SELECT COUNT(*) FROM productos WHERE {where_sql}", params
    ).fetchone()[0]

    offset = (page - 1) * limit
    rows = cursor.execute(
        f"""SELECT sku, nombre, precio_venta, categoria, marca, imagen_principal, stock, url_amigable
            FROM productos WHERE {where_sql}
            ORDER BY {sort_col} {order_sql}
            LIMIT ? OFFSET ?""",
        params + [limit, offset]
    ).fetchall()

    productos = []
    for r in rows:
        sku, nombre, precio, cat, marca, imagen, stock, url_amigable = r
        calc = _comision_producto_referido(float(precio), tier_pct)
        if not imagen or imagen.strip() == '':
            imagen_url = f"https://res.cloudinary.com/deq2ofluf/image/upload/prod_{sku}_001"
        else:
            imagen_url = imagen
        if url_amigable and url_amigable.strip():
            url_tienda = f"https://elgadget.com.ar/producto/{url_amigable.strip()}/?ref={ref[1]}"
        else:
            url_tienda = f"https://elgadget.com.ar/producto_detalle?sku={sku}&ref={ref[1]}"
        productos.append({
            "sku": sku,
            "nombre": nombre,
            "precio_venta": float(precio),
            "categoria": cat,
            "marca": marca,
            "imagen_url": imagen_url,
            "stock": stock,
            "descuento_pct": calc['descuento_pct'],
            "precio_con_descuento": calc['precio_con_descuento'],
            "comision_ars": calc['comision_ars'],
            "url_tienda": url_tienda,
        })

    conn.close()
    return {
        "tier": tier,
        "categorias": categorias,
        "total": total_count,
        "page": page,
        "limit": limit,
        "pages": -(-total_count // limit),  # ceil division
        "productos": productos,
    }


@app.get("/api/admin/referidos")
def admin_listar_referidos(x_admin_password: Optional[str] = Header(None)):
    """Lista todos los referidos con estadísticas agregadas (admin)."""
    if not _es_admin(x_admin_password):
        raise HTTPException(status_code=401, detail="No autorizado")

    conn = get_db()
    cursor = conn.cursor()
    referidos = cursor.execute("SELECT * FROM referidos ORDER BY creado_at DESC").fetchall()

    resultado = []
    for ref in referidos:
        ref = dict(ref)
        stats = cursor.execute("""
            SELECT COUNT(*) cantidad_ventas, COALESCE(SUM(monto_base),0) total_ventas,
                   COALESCE(SUM(comision),0) comision_total,
                   COALESCE(SUM(CASE WHEN pagado=0 THEN comision ELSE 0 END),0) comision_pendiente
            FROM comisiones_referidos WHERE referido_id = ?
        """, (ref['id'],)).fetchone()
        ref.update(dict(stats))

        periodos_rows = cursor.execute("""
            SELECT periodo,
                   COUNT(*) cantidad_ventas,
                   COALESCE(SUM(monto_base),0) monto_total,
                   COALESCE(SUM(comision),0) comision_total,
                   MAX(pagado) pagado
            FROM comisiones_referidos
            WHERE referido_id = ?
            GROUP BY periodo
            ORDER BY periodo DESC
        """, (ref['id'],)).fetchall()
        ref['periodos'] = [dict(p) for p in periodos_rows]

        resultado.append(ref)

    conn.close()
    return resultado


@app.delete("/api/admin/referidos/{ref_id}")
def admin_desactivar_referido(ref_id: int, x_admin_password: Optional[str] = Header(None)):
    """Desactiva un referido y su código de descuento (sin eliminar la cuenta de usuario)."""
    if not _es_admin(x_admin_password):
        raise HTTPException(status_code=401, detail="No autorizado")

    conn = get_db()
    cursor = conn.cursor()
    ref = cursor.execute("SELECT codigo FROM referidos WHERE id = ?", (ref_id,)).fetchone()
    if not ref:
        conn.close()
        raise HTTPException(status_code=404, detail="Referido no encontrado")

    cursor.execute("UPDATE referidos SET activo = 0 WHERE id = ?", (ref_id,))
    cursor.execute("UPDATE descuentos SET activo = 0 WHERE codigo = ?", (ref[0],))
    conn.commit()
    conn.close()
    return {"ok": True, "mensaje": "Referido desactivado correctamente"}


@app.post("/api/admin/referidos/{ref_id}/eliminar")
def admin_eliminar_referido(ref_id: int, x_admin_password: Optional[str] = Header(None)):
    """Elimina permanentemente un referido, sus comisiones y su código de descuento."""
    if not _es_admin(x_admin_password):
        raise HTTPException(status_code=401, detail="No autorizado")

    conn = get_db()
    cursor = conn.cursor()
    ref = cursor.execute("SELECT codigo FROM referidos WHERE id = ?", (ref_id,)).fetchone()
    if not ref:
        conn.close()
        raise HTTPException(status_code=404, detail="Referido no encontrado")

    pendientes = cursor.execute(
        "SELECT COUNT(*) FROM comisiones_referidos WHERE referido_id = ? AND pagado = 1", (ref_id,)
    ).fetchone()[0]
    if pendientes:
        conn.close()
        raise HTTPException(
            status_code=409,
            detail=f"No se puede eliminar: el referido tiene {pendientes} comisión/es ya pagada/s en el historial. Desactivalo en su lugar para conservar el registro contable."
        )

    cursor.execute("DELETE FROM comisiones_referidos WHERE referido_id = ?", (ref_id,))
    cursor.execute("DELETE FROM descuentos WHERE codigo = ?", (ref[0],))
    cursor.execute("DELETE FROM referidos WHERE id = ?", (ref_id,))
    conn.commit()
    conn.close()
    return {"ok": True, "mensaje": "Referido eliminado correctamente"}


@app.post("/api/admin/referidos/{ref_id}/marcar-pagado")
def admin_marcar_pagado_referido(ref_id: int, datos: MarcarPagadoReferido,
                                  x_admin_password: Optional[str] = Header(None)):
    """Marca como pagadas todas las comisiones de un periodo para un referido."""
    if not _es_admin(x_admin_password):
        raise HTTPException(status_code=401, detail="No autorizado")

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE comisiones_referidos
        SET pagado = 1, pagado_at = datetime('now')
        WHERE referido_id = ? AND periodo = ? AND pagado = 0
    """, (ref_id, datos.periodo))
    filas = cursor.rowcount
    conn.commit()
    conn.close()
    return {"ok": True, "comisiones_actualizadas": filas}


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
