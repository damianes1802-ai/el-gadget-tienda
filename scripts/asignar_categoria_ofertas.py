#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ASIGNADOR DE CATEGORÍA OFERTAS - VERSIÓN CORRECTA
Asigna automáticamente categoría "OFERTAS" SOLO a productos DISPONIBLES sin categoría
"""

import json
from pathlib import Path
from datetime import datetime

# Configuración
PRODUCTOS_DIR = Path(__file__).parent.parent / "data" / "productos"

def asignar_categoria_ofertas():
    """Asigna categoría OFERTAS SOLO a productos disponibles sin categoría"""
    
    print("\n" + "="*70)
    print("🏷️  ASIGNADOR DE CATEGORÍA 'OFERTAS' - SOLO DISPONIBLES")
    print("="*70 + "\n")
    
    print(f"📂 Escaneando: {PRODUCTOS_DIR}\n")
    
    # Contadores
    total_procesados = 0
    sin_categoria_encontrados = 0
    actualizados = 0
    ya_tenian_categoria = 0
    errores = 0
    
    # Estadísticas por disponibilidad
    disponibles_actualizados = []
    agotados_sin_categoria = []
    
    # Recorrer todos los productos
    for carpeta in PRODUCTOS_DIR.iterdir():
        if not carpeta.is_dir():
            continue
        
        metadata_file = carpeta / 'metadata.json'
        if not metadata_file.exists():
            continue
        
        total_procesados += 1
        
        try:
            # Leer metadata
            with open(metadata_file, 'r', encoding='utf-8') as f:
                metadata = json.load(f)
            
            sku = metadata.get('sku', carpeta.name)
            categoria_actual = metadata.get('categoria_principal') or metadata.get('categoria')
            disponibilidad = metadata.get('disponibilidad', metadata.get('availability', 'in stock'))
            
            # Verificar si tiene categoría
            if not categoria_actual:
                sin_categoria_encontrados += 1
                
                # ✅ SOLO ASIGNAR "OFERTAS" SI ESTÁ DISPONIBLE
                if disponibilidad != 'out of stock':
                    # ASIGNAR CATEGORÍA "OFERTAS"
                    metadata['categoria_principal'] = 'OFERTAS'
                    metadata['categoria'] = 'OFERTAS'
                    metadata['categorias_secundarias'] = []
                    metadata['todas_las_categorias'] = ['OFERTAS']
                    metadata['total_categorias'] = 1
                    metadata['fecha_actualizacion_categorias'] = datetime.now().isoformat()
                    metadata['categoria_asignada_automaticamente'] = True
                    metadata['razon_categoria_ofertas'] = 'Producto disponible sin categoría en Droppers'
                    # Marcar como "asignada" para que el scraper no la vuelva a
                    # marcar como pendiente en futuros re-scrapeos
                    metadata['categorias_asignadas'] = True
                    metadata['fecha_mapeo_categorias'] = datetime.now().isoformat()
                    metadata.pop('categorias_pendientes', None)
                    metadata.pop('nota', None)
                    
                    # Guardar
                    with open(metadata_file, 'w', encoding='utf-8') as f:
                        json.dump(metadata, f, indent=2, ensure_ascii=False)
                    
                    actualizados += 1
                    disponibles_actualizados.append(sku)
                    
                    # Progress cada 20
                    if actualizados % 20 == 0:
                        print(f"   ⏳ {actualizados} productos actualizados...")
                else:
                    # ❌ Producto agotado - NO asignar categoría
                    agotados_sin_categoria.append(sku)
            else:
                ya_tenian_categoria += 1
        
        except Exception as e:
            print(f"❌ Error en {carpeta.name}: {e}")
            errores += 1
    
    # REPORTE FINAL
    print("\n" + "="*70)
    print("📊 RESUMEN")
    print("="*70)
    
    print(f"\n📦 Productos procesados: {total_procesados}")
    print(f"✅ Ya tenían categoría: {ya_tenian_categoria}")
    print(f"❌ Sin categoría encontrados: {sin_categoria_encontrados}")
    print(f"   • 🟢 Disponibles: {len(disponibles_actualizados)} → Actualizados a 'OFERTAS'")
    print(f"   • 🔴 Agotados: {len(agotados_sin_categoria)} → Sin cambios (no se asigna categoría)")
    print(f"\n🏷️  Total actualizados: {actualizados}")
    
    if errores > 0:
        print(f"⚠️  Errores: {errores}")
    
    # Mostrar algunos ejemplos
    if disponibles_actualizados:
        print(f"\n🟢 Productos DISPONIBLES actualizados a 'OFERTAS' (primeros 10):")
        for sku in disponibles_actualizados[:10]:
            print(f"   ✅ {sku}")
        
        if len(disponibles_actualizados) > 10:
            print(f"   ... y {len(disponibles_actualizados) - 10} más")
    
    if agotados_sin_categoria:
        print(f"\n🔴 Productos AGOTADOS sin categoría (NO modificados - primeros 5):")
        for sku in agotados_sin_categoria[:5]:
            print(f"   ⏸️  {sku}")
        
        if len(agotados_sin_categoria) > 5:
            print(f"   ... y {len(agotados_sin_categoria) - 5} más")
    
    # Guardar reporte
    output_dir = PRODUCTOS_DIR.parent
    reporte_file = output_dir / f'reporte_ofertas_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
    
    reporte = {
        'fecha_ejecucion': datetime.now().isoformat(),
        'total_procesados': total_procesados,
        'ya_tenian_categoria': ya_tenian_categoria,
        'sin_categoria_encontrados': sin_categoria_encontrados,
        'actualizados': actualizados,
        'disponibles_actualizados': disponibles_actualizados,
        'agotados_sin_categoria': agotados_sin_categoria,
        'errores': errores
    }
    
    with open(reporte_file, 'w', encoding='utf-8') as f:
        json.dump(reporte, f, indent=2, ensure_ascii=False)
    
    print("\n" + "="*70)
    print(f"📄 Reporte: {reporte_file}")
    print("="*70)
    
    # Siguiente paso
    if actualizados > 0:
        print("\n💡 SIGUIENTE PASO:")
        print("   1. python 11_sincronizar_sqlite.py")
        print("   2. python 06_sincronizar_google_sheets_OPTIMIZADO.py")
        print(f"\n✅ Los {actualizados} productos disponibles ahora aparecerán en categoría 'OFERTAS'")
        print(f"❌ Los {len(agotados_sin_categoria)} agotados NO se sincronizarán (correcto)")
    
    print("="*70 + "\n")


if __name__ == "__main__":
    asignar_categoria_ofertas()
