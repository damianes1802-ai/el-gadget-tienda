#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DIAGNÓSTICO DE DESCARGA DE IMÁGENES
Investiga por qué no se descargaron todas las imágenes
"""

import json
from pathlib import Path
from collections import defaultdict

# Imports locales
import sys
sys.path.append(str(Path(__file__).parent))
from utils.config import Config

def diagnostico_completo():
    """Realiza un diagnóstico completo del problema"""
    
    print("=" * 80)
    print("🔍 DIAGNÓSTICO DE DESCARGA DE IMÁGENES")
    print("=" * 80)
    
    # 1. Verificar archivo de variantes
    print("\n1️⃣ VERIFICANDO ARCHIVO DE VARIANTES...")
    
    archivos_variantes = sorted(
        Config.GRUPOS_VARIANTES_DIR.glob("variantes_*.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True
    )
    
    if not archivos_variantes:
        print("   ❌ No se encontró archivo de variantes")
        return
    
    archivo_variantes = archivos_variantes[0]
    print(f"   ✅ Archivo encontrado: {archivo_variantes.name}")
    
    # Cargar archivo
    with open(archivo_variantes, 'r', encoding='utf-8') as f:
        datos_variantes = json.load(f)
    
    grupos_confirmados = datos_variantes.get('grupos_confirmados', [])
    print(f"   📊 Total grupos en archivo: {len(grupos_confirmados)}")
    
    # Separar por acción
    aprobados = [g for g in grupos_confirmados if g['accion'] == 'APROBADO']
    manuales = [g for g in grupos_confirmados if g['accion'] == 'MANUAL']
    rechazados = [g for g in grupos_confirmados if g['accion'] == 'RECHAZADO']
    
    print(f"      ✅ Aprobados: {len(aprobados)}")
    print(f"      🔨 Manuales: {len(manuales)}")
    print(f"      ❌ Rechazados: {len(rechazados)}")
    
    # 2. Verificar SKUs en grupos
    print("\n2️⃣ ANALIZANDO SKUs EN GRUPOS...")
    
    skus_en_grupos = set()
    for grupo in grupos_confirmados:
        if grupo['accion'] in ['APROBADO', 'MANUAL', 'MODIFICADO']:
            skus_en_grupos.update(grupo.get('skus', []))
    
    print(f"   📊 SKUs en grupos de variantes: {len(skus_en_grupos)}")
    
    # 3. Verificar SKUs con metadata
    print("\n3️⃣ VERIFICANDO METADATA DE PRODUCTOS...")
    
    todos_skus = Config.listar_productos()
    print(f"   📊 Total productos con metadata: {len(todos_skus)}")
    
    # 4. Verificar carpetas de imágenes creadas
    print("\n4️⃣ VERIFICANDO CARPETAS DE IMÁGENES...")
    
    carpetas_con_imagenes = []
    total_imagenes = 0
    
    if Config.PRODUCTOS_DIR.exists():
        for item in Config.PRODUCTOS_DIR.iterdir():
            if item.is_dir():
                # Buscar imágenes en cualquier subcarpeta
                imagenes = list(item.rglob("*.jpg")) + list(item.rglob("*.png")) + list(item.rglob("*.webp"))
                if imagenes:
                    carpetas_con_imagenes.append(item.name)
                    total_imagenes += len(imagenes)
    
    print(f"   📊 Carpetas con imágenes: {len(carpetas_con_imagenes)}")
    print(f"   📊 Total imágenes descargadas: {total_imagenes}")
    
    # 5. Identificar productos NO descargados
    print("\n5️⃣ IDENTIFICANDO PRODUCTOS NO DESCARGADOS...")
    
    productos_sin_imagenes = set(todos_skus) - set(carpetas_con_imagenes)
    print(f"   ❌ Productos SIN imágenes: {len(productos_sin_imagenes)}")
    
    if productos_sin_imagenes:
        print(f"\n   Primeros 20 productos sin imágenes:")
        for i, sku in enumerate(list(productos_sin_imagenes)[:20], 1):
            print(f"      {i}. {sku}")
        
        if len(productos_sin_imagenes) > 20:
            print(f"      ... y {len(productos_sin_imagenes) - 20} más")
    
    # 6. Verificar grupos específicos
    print("\n6️⃣ VERIFICANDO GRUPOS ESPECÍFICOS...")
    
    print(f"\n   Ejemplos de grupos aprobados:")
    for i, grupo in enumerate(aprobados[:5], 1):
        skus = grupo.get('skus', [])
        print(f"   {i}. {grupo.get('producto_base', 'N/A')}")
        print(f"      SKUs: {', '.join(skus[:3])}", end='')
        if len(skus) > 3:
            print(f" ... (+{len(skus) - 3} más)")
        else:
            print()
        
        # Verificar si esos SKUs tienen carpetas
        skus_con_carpeta = [sku for sku in skus if sku in carpetas_con_imagenes]
        print(f"      Con imágenes: {len(skus_con_carpeta)}/{len(skus)}")
        
        if len(skus_con_carpeta) < len(skus):
            sin_carpeta = set(skus) - set(skus_con_carpeta)
            print(f"      Sin imágenes: {', '.join(list(sin_carpeta)[:3])}")
    
    # 7. Verificar metadata de un grupo específico
    print("\n7️⃣ ANALIZANDO METADATA DE UN GRUPO...")
    
    if aprobados:
        grupo_ejemplo = aprobados[0]
        skus_ejemplo = grupo_ejemplo.get('skus', [])[:3]
        
        print(f"\n   Grupo: {grupo_ejemplo.get('producto_base')}")
        print(f"   SKUs a analizar: {', '.join(skus_ejemplo)}")
        
        for sku in skus_ejemplo:
            try:
                metadata = Config.cargar_metadata(sku)
                imagenes = metadata.get('imagenes', [])
                print(f"\n   {sku}:")
                print(f"      Imágenes en metadata: {len(imagenes)}")
                if imagenes:
                    print(f"      Primera URL: {imagenes[0][:80]}...")
            except Exception as e:
                print(f"\n   {sku}:")
                print(f"      ❌ Error: {e}")
    
    # RESUMEN
    print("\n" + "=" * 80)
    print("📊 RESUMEN DEL DIAGNÓSTICO")
    print("=" * 80)
    print(f"\nProductos totales: {len(todos_skus)}")
    print(f"Grupos de variantes: {len(aprobados) + len(manuales)}")
    print(f"SKUs en grupos: {len(skus_en_grupos)}")
    print(f"Productos individuales esperados: {len(todos_skus) - len(skus_en_grupos)}")
    print(f"\nCarpetas con imágenes: {len(carpetas_con_imagenes)}")
    print(f"Imágenes descargadas: {total_imagenes}")
    print(f"Productos sin imágenes: {len(productos_sin_imagenes)}")
    
    print("\n" + "=" * 80)
    
    if productos_sin_imagenes:
        print("\n⚠️  PROBLEMA DETECTADO:")
        print(f"   {len(productos_sin_imagenes)} productos NO tienen imágenes descargadas")
        print("\n💡 Posibles causas:")
        print("   1. Error al procesar grupos de variantes")
        print("   2. Metadata.json sin URLs de imágenes")
        print("   3. Error en la descarga silenciada")
        print("   4. Script interrumpido antes de terminar")
    else:
        print("\n✅ Todos los productos tienen imágenes")


if __name__ == "__main__":
    diagnostico_completo()
