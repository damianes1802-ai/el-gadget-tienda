#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ANALIZADOR DE PRODUCTOS SIN CATEGORÍA
Identifica qué productos no tienen categoría asignada
"""

import json
from pathlib import Path

# Configuración
PRODUCTOS_DIR = Path(r"C:\Users\damia\Desktop\ecommerce_automation\data\productos")

def analizar_categorias():
    """Analiza categorías en metadata"""
    
    sin_categoria = []
    con_categoria = []
    agotados_sin_categoria = []
    disponibles_sin_categoria = []
    
    print(f"📂 Escaneando: {PRODUCTOS_DIR}\n")
    
    # Contar carpetas
    carpetas_totales = 0
    carpetas_con_metadata = 0
    
    # Recorrer todos los productos
    for carpeta in PRODUCTOS_DIR.iterdir():
        if not carpeta.is_dir():
            continue
        
        carpetas_totales += 1
        
        metadata_file = carpeta / 'metadata.json'
        if not metadata_file.exists():
            continue
        
        carpetas_con_metadata += 1
        
        try:
            with open(metadata_file, 'r', encoding='utf-8') as f:
                metadata = json.load(f)
            
            sku = metadata.get('sku', carpeta.name)
            categoria = metadata.get('categoria_principal') or metadata.get('categoria')
            disponibilidad = metadata.get('disponibilidad', metadata.get('availability', 'in stock'))
            precio_venta = metadata.get('precio_venta', 0)
            
            # Verificar si tiene categoría
            if not categoria:
                sin_categoria.append({
                    'sku': sku,
                    'titulo': metadata.get('titulo', '')[:50],
                    'disponibilidad': disponibilidad,
                    'precio_venta': precio_venta
                })
                
                # Clasificar por disponibilidad
                if disponibilidad == 'out of stock':
                    agotados_sin_categoria.append(sku)
                else:
                    disponibles_sin_categoria.append(sku)
            else:
                con_categoria.append(sku)
        
        except Exception as e:
            print(f"⚠️  Error en {carpeta.name}: {e}")
    
    print(f"📊 Carpetas escaneadas: {carpetas_totales}")
    print(f"📋 Con metadata.json: {carpetas_con_metadata}\n")
    
    # REPORTE
    print("="*70)
    print("📊 ANÁLISIS DE CATEGORÍAS")
    print("="*70)
    
    print(f"\n✅ Con categoría: {len(con_categoria)} productos")
    print(f"❌ Sin categoría: {len(sin_categoria)} productos")
    print(f"   • Disponibles: {len(disponibles_sin_categoria)}")
    print(f"   • Agotados: {len(agotados_sin_categoria)}")
    
    # Productos sin categoría
    if sin_categoria:
        print("\n" + "="*70)
        print("📋 PRODUCTOS SIN CATEGORÍA")
        print("="*70)
        
        # Separar por disponibilidad
        print(f"\n🟢 DISPONIBLES SIN CATEGORÍA ({len(disponibles_sin_categoria)}):")
        print("-"*70)
        for prod in sin_categoria:
            if prod['disponibilidad'] != 'out of stock':
                print(f"SKU: {prod['sku']:<15} | ${prod['precio_venta']:>8,.0f} | {prod['titulo']}")
        
        print(f"\n🔴 AGOTADOS SIN CATEGORÍA ({len(agotados_sin_categoria)}):")
        print("-"*70)
        for prod in sin_categoria:
            if prod['disponibilidad'] == 'out of stock':
                print(f"SKU: {prod['sku']:<15} | ${prod['precio_venta']:>8,.0f} | {prod['titulo']}")
    
    # Exportar listas de SKUs
    print("\n" + "="*70)
    print("💾 EXPORTANDO LISTAS")
    print("="*70)
    
    # Lista completa sin categoría
    output_dir = PRODUCTOS_DIR.parent
    
    # Todos sin categoría
    file_todos = output_dir / 'sin_categoria_todos.txt'
    with open(file_todos, 'w', encoding='utf-8') as f:
        for prod in sorted(sin_categoria, key=lambda x: x['sku']):
            f.write(f"{prod['sku']}\n")
    print(f"✅ Todos: {file_todos}")
    
    # Solo disponibles sin categoría
    file_disponibles = output_dir / 'sin_categoria_disponibles.txt'
    with open(file_disponibles, 'w', encoding='utf-8') as f:
        for sku in sorted(disponibles_sin_categoria):
            f.write(f"{sku}\n")
    print(f"✅ Disponibles: {file_disponibles}")
    
    # Solo agotados sin categoría
    file_agotados = output_dir / 'sin_categoria_agotados.txt'
    with open(file_agotados, 'w', encoding='utf-8') as f:
        for sku in sorted(agotados_sin_categoria):
            f.write(f"{sku}\n")
    print(f"✅ Agotados: {file_agotados}")
    
    # JSON detallado
    file_json = output_dir / 'sin_categoria_detalle.json'
    with open(file_json, 'w', encoding='utf-8') as f:
        json.dump({
            'total_sin_categoria': len(sin_categoria),
            'disponibles': len(disponibles_sin_categoria),
            'agotados': len(agotados_sin_categoria),
            'productos': sin_categoria
        }, f, indent=2, ensure_ascii=False)
    print(f"✅ Detalle JSON: {file_json}")
    
    print("\n" + "="*70)
    print("✅ Análisis completado")
    print("="*70 + "\n")


if __name__ == "__main__":
    analizar_categorias()
