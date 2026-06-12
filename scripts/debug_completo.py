"""
DIAGNÓSTICO COMPLETO DEL SISTEMA
Revisa cada paso del flujo de datos
"""

import json
import sqlite3
from pathlib import Path

print("\n" + "="*60)
print("🔍 DIAGNÓSTICO COMPLETO DEL SISTEMA")
print("="*60 + "\n")

# ============================================================
# PASO 1: Revisar metadata.json
# ============================================================
print("📁 PASO 1: Revisando archivos metadata.json\n")

productos_dir = Path('../data/productos')
total_carpetas = 0
con_metadata = 0
disponibles_meta = 0
agotados_meta = 0
sin_campo_meta = 0

sample_disponible = None
sample_agotado = None

for carpeta in productos_dir.iterdir():
    if not carpeta.is_dir():
        continue
    
    total_carpetas += 1
    meta_file = carpeta / 'metadata.json'
    
    if not meta_file.exists():
        continue
    
    con_metadata += 1
    
    try:
        with open(meta_file, 'r', encoding='utf-8') as f:
            meta = json.load(f)
        
        disp = meta.get('disponibilidad', '')
        avail = meta.get('availability', '')
        
        if disp == 'in stock' or avail == 'in stock':
            disponibles_meta += 1
            if not sample_disponible:
                sample_disponible = (carpeta.name, disp, avail)
        elif disp == 'out of stock' or avail == 'out of stock':
            agotados_meta += 1
            if not sample_agotado:
                sample_agotado = (carpeta.name, disp, avail)
        else:
            sin_campo_meta += 1
    except:
        pass

print(f"Total carpetas: {total_carpetas}")
print(f"Con metadata.json: {con_metadata}")
print(f"  ✅ Disponibles: {disponibles_meta}")
print(f"  🔴 Agotados: {agotados_meta}")
print(f"  ⚠️  Sin campo: {sin_campo_meta}")

if sample_disponible:
    print(f"\nEjemplo DISPONIBLE:")
    print(f"  SKU: {sample_disponible[0]}")
    print(f"  disponibilidad: '{sample_disponible[1]}'")
    print(f"  availability: '{sample_disponible[2]}'")

if sample_agotado:
    print(f"\nEjemplo AGOTADO:")
    print(f"  SKU: {sample_agotado[0]}")
    print(f"  disponibilidad: '{sample_agotado[1]}'")
    print(f"  availability: '{sample_agotado[2]}'")

# ============================================================
# PASO 2: Ver qué lee el sincronizador
# ============================================================
print("\n" + "-"*60)
print("🔄 PASO 2: Simulando lectura del sincronizador\n")

# Tomar un metadata de muestra
muestra_dir = productos_dir / sample_disponible[0] if sample_disponible else None
if muestra_dir and (muestra_dir / 'metadata.json').exists():
    with open(muestra_dir / 'metadata.json', 'r', encoding='utf-8') as f:
        producto = json.load(f)
    
    sku = producto.get('sku', muestra_dir.name)
    disponibilidad = producto.get('disponibilidad', producto.get('availability', 'in stock'))
    
    print(f"Producto de prueba: {sku}")
    print(f"Campo 'disponibilidad': '{producto.get('disponibilidad', 'NO EXISTE')}'")
    print(f"Campo 'availability': '{producto.get('availability', 'NO EXISTE')}'")
    print(f"Valor que leería el sincronizador: '{disponibilidad}'")
    print(f"¿Se saltaría? {disponibilidad == 'out of stock'}")

# ============================================================
# PASO 3: Ver qué hay en la base de datos
# ============================================================
print("\n" + "-"*60)
print("💾 PASO 3: Revisando base de datos SQLite\n")

db_path = Path('../data/catalogo.db')
if db_path.exists():
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Total productos
    cursor.execute("SELECT COUNT(*) as total FROM productos")
    total_db = cursor.fetchone()['total']
    
    # Ver algunos productos
    cursor.execute("SELECT sku, nombre, precio_venta FROM productos LIMIT 3")
    productos_db = cursor.fetchall()
    
    print(f"Total productos en DB: {total_db}")
    print(f"\nPrimeros 3 productos en DB:")
    for p in productos_db:
        print(f"  • {p['sku']}: {p['nombre'][:40]}... (${p['precio_venta']})")
    
    conn.close()
else:
    print("❌ No existe catalogo.db")

# ============================================================
# PASO 4: Verificar script sincronizador
# ============================================================
print("\n" + "-"*60)
print("📜 PASO 4: Verificando código del sincronizador\n")

sync_script = Path('11_sincronizar_sqlite.py')
if sync_script.exists():
    with open(sync_script, 'r', encoding='utf-8') as f:
        contenido = f.read()
    
    # Buscar el filtro de agotados
    if "FILTRO: Saltar productos agotados" in contenido:
        print("✅ Filtro de agotados EXISTE en el código")
        
        # Extraer las líneas del filtro
        lineas = contenido.split('\n')
        filtro_encontrado = False
        for i, linea in enumerate(lineas):
            if "FILTRO: Saltar productos agotados" in linea:
                print("\nCódigo del filtro:")
                for j in range(i, min(i+6, len(lineas))):
                    print(f"  {lineas[j]}")
                filtro_encontrado = True
                break
    else:
        print("❌ Filtro de agotados NO ENCONTRADO en el código")
else:
    print("❌ No existe 11_sincronizar_sqlite.py")

# ============================================================
# RESUMEN Y DIAGNÓSTICO
# ============================================================
print("\n" + "="*60)
print("📊 DIAGNÓSTICO FINAL")
print("="*60 + "\n")

if disponibles_meta == 0 and sin_campo_meta > 0:
    print("🚨 PROBLEMA ENCONTRADO:")
    print(f"   {sin_campo_meta} productos NO tienen campo 'disponibilidad'")
    print("   El detector NO los está marcando como disponibles")
    print("\n💡 SOLUCIÓN:")
    print("   Re-ejecutar: python 17_deteccion_agotados_robusto.py")

elif disponibles_meta > 0 and total_db > disponibles_meta:
    print("🚨 PROBLEMA ENCONTRADO:")
    print(f"   Metadata tiene {disponibles_meta} disponibles")
    print(f"   Base de datos tiene {total_db} productos")
    print("   El sincronizador NO está filtrando los agotados")
    print("\n💡 SOLUCIÓN:")
    print("   El filtro en el sincronizador no funciona correctamente")

else:
    print("✅ Sistema parece estar correcto")
    print(f"   Metadata: {disponibles_meta} disponibles, {agotados_meta} agotados")
    print(f"   Base de datos: {total_db} productos")

print()
