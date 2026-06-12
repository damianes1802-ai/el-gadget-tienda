#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DIAGNÓSTICO COMPLETO DEL SISTEMA
Compara metadata, SQLite, Google Sheets y frontend
"""

import json
import sqlite3
from pathlib import Path
from collections import Counter, defaultdict

# Configuración
PRODUCTOS_DIR = Path(r"C:\Users\damia\Desktop\ecommerce_automation\data\productos")
DB_PATH = Path(r"C:\Users\damia\Desktop\ecommerce_automation\data\catalogo.db")

def diagnostico_completo():
    """Diagnóstico completo del sistema"""
    
    print("\n" + "="*80)
    print("🔍 DIAGNÓSTICO COMPLETO DEL SISTEMA")
    print("="*80 + "\n")
    
    # ============================================================
    # 1. METADATA (Fuente de verdad)
    # ============================================================
    
    print("📂 PASO 1: Analizando METADATA (archivos locales)")
    print("-"*80)
    
    metadata_stats = {
        'total': 0,
        'con_categoria': 0,
        'sin_categoria': 0,
        'disponibles_con_categoria': 0,
        'disponibles_sin_categoria': 0,
        'agotados_con_categoria': 0,
        'agotados_sin_categoria': 0
    }
    
    categorias_metadata = Counter()
    productos_por_categoria_metadata = defaultdict(list)
    
    for carpeta in PRODUCTOS_DIR.iterdir():
        if not carpeta.is_dir():
            continue
        
        metadata_file = carpeta / 'metadata.json'
        if not metadata_file.exists():
            continue
        
        try:
            with open(metadata_file, 'r', encoding='utf-8') as f:
                metadata = json.load(f)
            
            metadata_stats['total'] += 1
            
            sku = metadata.get('sku', carpeta.name)
            categoria = metadata.get('categoria_principal') or metadata.get('categoria')
            disponibilidad = metadata.get('disponibilidad', metadata.get('availability', 'in stock'))
            precio = metadata.get('precio_venta', 0)
            
            # Contar categorías
            if categoria:
                metadata_stats['con_categoria'] += 1
                categorias_metadata[categoria] += 1
                
                if disponibilidad != 'out of stock' and precio > 0:
                    productos_por_categoria_metadata[categoria].append(sku)
                
                if disponibilidad == 'out of stock':
                    metadata_stats['agotados_con_categoria'] += 1
                else:
                    metadata_stats['disponibles_con_categoria'] += 1
            else:
                metadata_stats['sin_categoria'] += 1
                if disponibilidad == 'out of stock':
                    metadata_stats['agotados_sin_categoria'] += 1
                else:
                    metadata_stats['sin_categoria'] += 1
        
        except Exception as e:
            pass
    
    print(f"Total productos: {metadata_stats['total']}")
    print(f"Con categoría: {metadata_stats['con_categoria']}")
    print(f"Sin categoría: {metadata_stats['sin_categoria']}")
    print(f"\nDisponibles con categoría: {metadata_stats['disponibles_con_categoria']}")
    print(f"Disponibles sin categoría: {metadata_stats['disponibles_sin_categoria']}")
    print(f"\nCategorías encontradas: {len(categorias_metadata)}")
    
    print(f"\n📊 TOP 10 CATEGORÍAS EN METADATA:")
    for cat, count in categorias_metadata.most_common(10):
        productos_disponibles = len(productos_por_categoria_metadata.get(cat, []))
        print(f"   • {cat}: {count} total ({productos_disponibles} disponibles)")
    
    # ============================================================
    # 2. SQLITE (Para frontend)
    # ============================================================
    
    print(f"\n📊 PASO 2: Analizando SQLITE (base de datos)")
    print("-"*80)
    
    if not DB_PATH.exists():
        print("❌ No existe catalogo.db")
        return
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Total productos
    cursor.execute("SELECT COUNT(*) FROM productos")
    total_db = cursor.fetchone()[0]
    
    # Por categoría
    cursor.execute("""
        SELECT categoria, COUNT(*) as total
        FROM productos
        WHERE categoria IS NOT NULL AND categoria != ''
        GROUP BY categoria
        ORDER BY total DESC
    """)
    
    categorias_db = {}
    for cat, count in cursor.fetchall():
        categorias_db[cat] = count
    
    print(f"Total productos en DB: {total_db}")
    print(f"Categorías en DB: {len(categorias_db)}")
    
    print(f"\n📊 TOP 10 CATEGORÍAS EN SQLITE:")
    for cat, count in sorted(categorias_db.items(), key=lambda x: x[1], reverse=True)[:10]:
        print(f"   • {cat}: {count} productos")
    
    conn.close()
    
    # ============================================================
    # 3. COMPARACIÓN
    # ============================================================
    
    print(f"\n🔍 PASO 3: COMPARACIÓN")
    print("="*80)
    
    # Categorías en metadata pero NO en SQLite
    cats_solo_metadata = set(categorias_metadata.keys()) - set(categorias_db.keys())
    
    # Categorías en SQLite pero NO en metadata
    cats_solo_db = set(categorias_db.keys()) - set(categorias_metadata.keys())
    
    # Categorías en ambos con diferente cantidad
    cats_diferentes = []
    for cat in set(categorias_metadata.keys()) & set(categorias_db.keys()):
        count_metadata = len(productos_por_categoria_metadata.get(cat, []))
        count_db = categorias_db.get(cat, 0)
        
        if count_metadata != count_db:
            cats_diferentes.append({
                'categoria': cat,
                'metadata': count_metadata,
                'sqlite': count_db,
                'diferencia': count_metadata - count_db
            })
    
    # REPORTES
    
    if cats_solo_metadata:
        print(f"\n⚠️  CATEGORÍAS EN METADATA PERO NO EN SQLITE ({len(cats_solo_metadata)}):")
        for cat in sorted(cats_solo_metadata):
            count = len(productos_por_categoria_metadata.get(cat, []))
            print(f"   ❌ {cat}: {count} productos disponibles NO sincronizados")
    
    if cats_solo_db:
        print(f"\n⚠️  CATEGORÍAS EN SQLITE PERO NO EN METADATA ({len(cats_solo_db)}):")
        for cat in sorted(cats_solo_db):
            print(f"   ❌ {cat}: {categorias_db[cat]} productos (datos viejos?)")
    
    if cats_diferentes:
        print(f"\n⚠️  CATEGORÍAS CON DIFERENTE CANTIDAD ({len(cats_diferentes)}):")
        for diff in sorted(cats_diferentes, key=lambda x: abs(x['diferencia']), reverse=True)[:10]:
            signo = "+" if diff['diferencia'] > 0 else ""
            print(f"   • {diff['categoria']}: Metadata={diff['metadata']}, SQLite={diff['sqlite']} ({signo}{diff['diferencia']})")
    
    # ============================================================
    # 4. DIAGNÓSTICO FINAL
    # ============================================================
    
    print(f"\n" + "="*80)
    print("💡 DIAGNÓSTICO Y SOLUCIÓN")
    print("="*80)
    
    problemas = []
    
    if cats_solo_metadata:
        problemas.append({
            'problema': 'Categorías nuevas no sincronizadas a SQLite',
            'cantidad': len(cats_solo_metadata),
            'solucion': 'Ejecutar: python 11_sincronizar_sqlite.py'
        })
    
    if cats_diferentes:
        problemas.append({
            'problema': 'Diferencias en cantidad de productos por categoría',
            'cantidad': len(cats_diferentes),
            'solucion': 'Ejecutar: python 11_sincronizar_sqlite.py'
        })
    
    if metadata_stats['disponibles_sin_categoria'] > 0:
        problemas.append({
            'problema': f"Productos disponibles sin categoría",
            'cantidad': metadata_stats['disponibles_sin_categoria'],
            'solucion': 'Ejecutar: python asignar_categoria_ofertas.py'
        })
    
    if problemas:
        print("\n🔴 PROBLEMAS ENCONTRADOS:\n")
        for i, p in enumerate(problemas, 1):
            print(f"{i}. {p['problema']}: {p['cantidad']}")
            print(f"   → Solución: {p['solucion']}\n")
        
        print("="*80)
        print("📋 ORDEN DE EJECUCIÓN RECOMENDADO:")
        print("="*80)
        print("1. python asignar_categoria_ofertas.py  (si hay productos sin categoría)")
        print("2. python 11_sincronizar_sqlite.py")
        print("3. python 06_sincronizar_google_sheets_OPTIMIZADO.py")
        print("4. Refrescar frontend (Ctrl+F5)")
        print("="*80 + "\n")
    else:
        print("\n✅ TODO SINCRONIZADO CORRECTAMENTE")
        print("\nSi el frontend muestra datos incorrectos:")
        print("  1. Refrescar con Ctrl+F5 (limpiar caché)")
        print("  2. Verificar que la API esté corriendo")
        print("  3. Revisar consola del navegador (F12)\n")
    
    # Guardar reporte
    output_dir = PRODUCTOS_DIR.parent
    reporte_file = output_dir / f'diagnostico_completo_{Path(__file__).stem}.json'
    
    reporte = {
        'fecha': Path(__file__).stem,
        'metadata': {
            'total': metadata_stats['total'],
            'categorias': dict(categorias_metadata),
            'productos_por_categoria': {k: len(v) for k, v in productos_por_categoria_metadata.items()}
        },
        'sqlite': {
            'total': total_db,
            'categorias': categorias_db
        },
        'problemas': {
            'categorias_solo_metadata': list(cats_solo_metadata),
            'categorias_solo_db': list(cats_solo_db),
            'categorias_diferentes': cats_diferentes
        }
    }
    
    with open(reporte_file, 'w', encoding='utf-8') as f:
        json.dump(reporte, f, indent=2, ensure_ascii=False)
    
    print(f"📄 Reporte detallado: {reporte_file}\n")


if __name__ == "__main__":
    diagnostico_completo()
