#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DIAGNÓSTICO ESPECÍFICO - CATEGORÍA FITNESS
Compara metadata vs SQLite para encontrar productos no sincronizados
"""

import sqlite3
import json
from pathlib import Path

# Rutas
DB_PATH = Path(r"C:\Users\damia\Desktop\ecommerce_automation\data\catalogo.db")
PRODUCTOS_DIR = Path(r"C:\Users\damia\Desktop\ecommerce_automation\data\productos")

print("="*70)
print("🔍 DIAGNÓSTICO CATEGORÍA FITNESS")
print("="*70)

# 1. Ver en METADATA
print("\n📂 PASO 1: Productos Fitness en METADATA")
print("-"*70)

fitness_metadata = []
for carpeta in PRODUCTOS_DIR.iterdir():
    if not carpeta.is_dir():
        continue
    
    metadata_file = carpeta / 'metadata.json'
    if not metadata_file.exists():
        continue
    
    try:
        with open(metadata_file, 'r', encoding='utf-8') as f:
            metadata = json.load(f)
        
        categoria = metadata.get('categoria_principal') or metadata.get('categoria')
        
        if categoria == 'Fitness':
            sku = metadata.get('sku', carpeta.name)
            disponibilidad = metadata.get('disponibilidad', metadata.get('availability', 'in stock'))
            precio = metadata.get('precio_venta', 0)
            
            fitness_metadata.append({
                'sku': sku,
                'nombre': metadata.get('titulo', '')[:40],
                'disponibilidad': disponibilidad,
                'precio': precio
            })
    except Exception as e:
        pass

disponibles_metadata = [p for p in fitness_metadata if p['disponibilidad'] != 'out of stock' and p['precio'] > 0]

print(f"Total en metadata: {len(fitness_metadata)}")
print(f"Disponibles con precio: {len(disponibles_metadata)}")

print("\n📋 Productos disponibles en metadata:")
for p in disponibles_metadata:
    print(f"  • {p['sku']}: {p['nombre']}")

# 2. Ver en SQLITE
print(f"\n📊 PASO 2: Productos Fitness en SQLITE")
print("-"*70)

conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

cursor.execute("""
    SELECT sku, nombre, stock, precio_venta 
    FROM productos 
    WHERE categoria = 'Fitness'
    ORDER BY sku
""")

fitness_sqlite = cursor.fetchall()
fitness_sqlite_disponibles = [p for p in fitness_sqlite if p['stock'] > 0]

print(f"Total en SQLite: {len(fitness_sqlite)}")
print(f"Con stock > 0: {len(fitness_sqlite_disponibles)}")

print("\n📋 Productos en SQLite:")
for p in fitness_sqlite:
    stock_emoji = "✅" if p['stock'] > 0 else "❌"
    print(f"  {stock_emoji} {p['sku']}: {p['nombre'][:40]} - Stock: {p['stock']}")

conn.close()

# 3. COMPARAR
print(f"\n🔍 PASO 3: COMPARACIÓN")
print("="*70)

skus_metadata = set([p['sku'] for p in disponibles_metadata])
skus_sqlite = set([p['sku'] for p in fitness_sqlite])
skus_sqlite_disponibles = set([p['sku'] for p in fitness_sqlite_disponibles])

solo_metadata = skus_metadata - skus_sqlite
solo_sqlite = skus_sqlite - skus_metadata
en_ambos_pero_sin_stock = skus_metadata & (skus_sqlite - skus_sqlite_disponibles)

if solo_metadata:
    print(f"\n⚠️  EN METADATA PERO NO EN SQLITE ({len(solo_metadata)}):")
    for sku in sorted(solo_metadata):
        prod = next(p for p in fitness_metadata if p['sku'] == sku)
        print(f"   ❌ {sku}: {prod['nombre']}")

if en_ambos_pero_sin_stock:
    print(f"\n⚠️  EN AMBOS PERO CON STOCK = 0 EN SQLITE ({len(en_ambos_pero_sin_stock)}):")
    for sku in sorted(en_ambos_pero_sin_stock):
        prod = next(p for p in fitness_metadata if p['sku'] == sku)
        print(f"   ⚠️  {sku}: {prod['nombre']}")

if solo_sqlite:
    print(f"\n⚠️  EN SQLITE PERO NO EN METADATA ({len(solo_sqlite)}):")
    for sku in sorted(solo_sqlite):
        print(f"   ❌ {sku} (datos viejos?)")

print("\n" + "="*70)
print("💡 CONCLUSIÓN")
print("="*70)

total_problemas = len(solo_metadata) + len(en_ambos_pero_sin_stock)

if total_problemas > 0:
    print(f"\n🔴 HAY {total_problemas} PRODUCTOS DE FITNESS CON PROBLEMAS:")
    if solo_metadata:
        print(f"   • {len(solo_metadata)} productos NO sincronizados a SQLite")
    if en_ambos_pero_sin_stock:
        print(f"   • {len(en_ambos_pero_sin_stock)} productos con stock = 0 (deberían tener 999)")
    
    print("\n📋 SOLUCIÓN:")
    print("   1. python 11_sincronizar_sqlite.py")
    print("   2. Refrescar frontend (Ctrl+F5)")
    
else:
    print("\n✅ Todos los productos de Fitness están correctamente sincronizados")
    print("   Si solo ves 3 en el frontend, puede ser:")
    print("   • Límite del endpoint (aumentar limit=100 a limit=500)")
    print("   • Caché del navegador (Ctrl+Shift+R)")

print("="*70 + "\n")
