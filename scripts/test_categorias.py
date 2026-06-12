import sqlite3
from pathlib import Path

db = Path('../data/catalogo.db')
conn = sqlite3.connect(db)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

# Ver algunos productos
cursor.execute("SELECT sku, nombre, categoria, subcategoria FROM productos LIMIT 5")
productos = cursor.fetchall()

print("\n📦 PRIMEROS 5 PRODUCTOS:")
for p in productos:
    print(f"  SKU: {p['sku']}")
    print(f"  Nombre: {p['nombre']}")
    print(f"  Categoría: '{p['categoria']}'")
    print(f"  Subcategoría: '{p['subcategoria']}'")
    print()

# Contar productos con categoría
cursor.execute("SELECT COUNT(*) as total FROM productos WHERE categoria != '' AND categoria IS NOT NULL")
con_cat = cursor.fetchone()['total']

cursor.execute("SELECT COUNT(*) as total FROM productos")
total = cursor.fetchone()['total']

print(f"📊 ESTADÍSTICAS:")
print(f"  Total productos: {total}")
print(f"  Con categoría: {con_cat}")
print(f"  Sin categoría: {total - con_cat}")

conn.close()
