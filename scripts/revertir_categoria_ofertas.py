#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
REVERTIR CATEGORÍA OFERTAS
Elimina la categoría "OFERTAS" asignada automáticamente
"""

import json
from pathlib import Path
from datetime import datetime

# Configuración
PRODUCTOS_DIR = Path(r"C:\Users\damia\Desktop\ecommerce_automation\data\productos")

def revertir_categoria_ofertas():
    """Revierte categorías OFERTAS asignadas automáticamente"""
    
    print("\n" + "="*70)
    print("🔄 REVERTIR CATEGORÍA 'OFERTAS'")
    print("="*70 + "\n")
    
    print(f"📂 Escaneando: {PRODUCTOS_DIR}\n")
    
    # Contadores
    total_procesados = 0
    con_ofertas_automatica = 0
    con_ofertas_manual = 0
    revertidos = 0
    errores = 0
    
    # Listas
    skus_revertidos = []
    skus_ofertas_manual = []
    
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
            asignada_automaticamente = metadata.get('categoria_asignada_automaticamente', False)
            
            # Verificar si tiene categoría OFERTAS
            if categoria_actual == 'OFERTAS':
                
                # Si fue asignada automáticamente → REVERTIR
                if asignada_automaticamente:
                    con_ofertas_automatica += 1
                    
                    # ELIMINAR campos de categoría
                    if 'categoria_principal' in metadata:
                        del metadata['categoria_principal']
                    if 'categoria' in metadata:
                        del metadata['categoria']
                    if 'categorias_secundarias' in metadata:
                        del metadata['categorias_secundarias']
                    if 'todas_las_categorias' in metadata:
                        del metadata['todas_las_categorias']
                    if 'total_categorias' in metadata:
                        del metadata['total_categorias']
                    if 'fecha_actualizacion_categorias' in metadata:
                        del metadata['fecha_actualizacion_categorias']
                    if 'categoria_asignada_automaticamente' in metadata:
                        del metadata['categoria_asignada_automaticamente']
                    if 'razon_categoria_ofertas' in metadata:
                        del metadata['razon_categoria_ofertas']
                    
                    # Guardar
                    with open(metadata_file, 'w', encoding='utf-8') as f:
                        json.dump(metadata, f, indent=2, ensure_ascii=False)
                    
                    revertidos += 1
                    skus_revertidos.append(sku)
                    
                    # Progress cada 20
                    if revertidos % 20 == 0:
                        print(f"   ⏳ {revertidos} productos revertidos...")
                
                else:
                    # Categoría OFERTAS asignada manualmente → NO tocar
                    con_ofertas_manual += 1
                    skus_ofertas_manual.append(sku)
        
        except Exception as e:
            print(f"❌ Error en {carpeta.name}: {e}")
            errores += 1
    
    # REPORTE FINAL
    print("\n" + "="*70)
    print("📊 RESUMEN")
    print("="*70)
    
    print(f"\n📦 Productos procesados: {total_procesados}")
    print(f"🔄 Con OFERTAS automática: {con_ofertas_automatica}")
    print(f"✋ Con OFERTAS manual: {con_ofertas_manual} (no modificados)")
    print(f"✅ Revertidos: {revertidos}")
    
    if errores > 0:
        print(f"⚠️  Errores: {errores}")
    
    # Mostrar ejemplos
    if skus_revertidos:
        print(f"\n🔄 Productos revertidos (ahora sin categoría - primeros 10):")
        for sku in skus_revertidos[:10]:
            print(f"   • {sku}")
        
        if len(skus_revertidos) > 10:
            print(f"   ... y {len(skus_revertidos) - 10} más")
    
    if skus_ofertas_manual:
        print(f"\n✋ Productos con OFERTAS manual (no modificados):")
        for sku in skus_ofertas_manual:
            print(f"   • {sku}")
    
    # Guardar reporte
    output_dir = PRODUCTOS_DIR.parent
    reporte_file = output_dir / f'reporte_reversion_ofertas_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
    
    reporte = {
        'fecha_ejecucion': datetime.now().isoformat(),
        'total_procesados': total_procesados,
        'con_ofertas_automatica': con_ofertas_automatica,
        'con_ofertas_manual': con_ofertas_manual,
        'revertidos': revertidos,
        'skus_revertidos': skus_revertidos,
        'skus_ofertas_manual': skus_ofertas_manual,
        'errores': errores
    }
    
    with open(reporte_file, 'w', encoding='utf-8') as f:
        json.dump(reporte, f, indent=2, ensure_ascii=False)
    
    print("\n" + "="*70)
    print(f"📄 Reporte: {reporte_file}")
    print("="*70)
    
    # Siguiente paso
    if revertidos > 0:
        print("\n💡 CAMBIOS REVERTIDOS:")
        print(f"   ✅ {revertidos} productos ahora SIN categoría nuevamente")
        print("\n💡 AHORA PODÉS EJECUTAR:")
        print("   python asignar_categoria_ofertas.py (versión corregida)")
    else:
        print("\n✅ No había productos con categoría OFERTAS automática")
    
    print("="*70 + "\n")


if __name__ == "__main__":
    # Confirmación
    print("\n⚠️  ESTE SCRIPT VA A:")
    print("   • Eliminar categoría 'OFERTAS' asignada automáticamente")
    print("   • NO tocará categorías OFERTAS asignadas manualmente")
    print("   • Dejará los productos sin categoría nuevamente\n")
    
    respuesta = input("¿Continuar? (s/n): ")
    
    if respuesta.lower() == 's':
        revertir_categoria_ofertas()
    else:
        print("\n⛔ Operación cancelada\n")
