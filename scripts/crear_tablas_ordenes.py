#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CREAR TABLAS DE ÓRDENES EN SQLITE
Verifica y crea las tablas: clientes, ordenes, orden_items

EJECUTAR ANTES DE USAR EL CHECKOUT:
python crear_tablas_ordenes.py
"""

import sqlite3
from pathlib import Path

# Ajusta esta ruta si tu estructura es diferente
DB_PATH = Path(r'C:\Users\damia\Desktop\ecommerce_automation\data\catalogo.db')

# DB_PATH = Path(__file__).parent / 'data' / 'catalogo.db'
# DB_PATH = Path(__file__).parent.parent / 'data' / 'catalogo.db'


def crear_tablas(conn):
    cursor = conn.cursor()

    # ── CLIENTES ──────────────────────────────────────────────────
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS clientes (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre          TEXT NOT NULL,
            email           TEXT NOT NULL UNIQUE,
            telefono        TEXT NOT NULL,
            direccion       TEXT NOT NULL,
            ciudad          TEXT NOT NULL,
            provincia       TEXT DEFAULT '',
            codigo_postal   TEXT NOT NULL,
            creado_at       TEXT DEFAULT (datetime('now')),
            actualizado_at  TEXT DEFAULT (datetime('now'))
        )
    """)

    # ── ORDENES ───────────────────────────────────────────────────
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ordenes (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            cliente_id          INTEGER NOT NULL,
            total               REAL NOT NULL,
            estado              TEXT DEFAULT 'pendiente_procesar',
            estado_pago         TEXT DEFAULT 'pending',
            metodo_pago         TEXT DEFAULT '',
            notas               TEXT DEFAULT '',
            tracking_url        TEXT DEFAULT '',
            mp_preference_id    TEXT DEFAULT '',
            mp_payment_id       TEXT DEFAULT '',
            fecha               TEXT DEFAULT (datetime('now')),
            enviado_at          TEXT DEFAULT NULL,
            FOREIGN KEY (cliente_id) REFERENCES clientes(id)
        )
    """)

    # ── ORDEN ITEMS ───────────────────────────────────────────────
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS orden_items (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            orden_id            INTEGER NOT NULL,
            producto_sku        TEXT NOT NULL,
            producto_nombre     TEXT NOT NULL,
            cantidad            INTEGER NOT NULL,
            precio_unitario     REAL NOT NULL,
            subtotal            REAL NOT NULL,
            FOREIGN KEY (orden_id) REFERENCES ordenes(id)
        )
    """)

    conn.commit()


def verificar_tablas(conn):
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    tablas = [row[0] for row in cursor.fetchall()]
    return tablas


def main():
    if not DB_PATH.exists():
        print(f"❌ No se encontró la base de datos en: {DB_PATH}")
        print("   Verificá la ruta DB_PATH en este script.")
        return

    print(f"📁 Base de datos: {DB_PATH}")

    conn = sqlite3.connect(DB_PATH)

    tablas_antes = verificar_tablas(conn)
    print(f"\nTablas existentes: {', '.join(tablas_antes)}")

    crear_tablas(conn)

    tablas_despues = verificar_tablas(conn)
    tablas_nuevas = set(tablas_despues) - set(tablas_antes)

    if tablas_nuevas:
        print(f"✅ Tablas creadas: {', '.join(tablas_nuevas)}")
    else:
        print("✅ Todas las tablas ya existían, sin cambios.")

    print(f"\nTablas finales: {', '.join(tablas_despues)}")
    conn.close()
    print("\n🚀 Listo. Ya podés usar el checkout.")


if __name__ == "__main__":
    main()
