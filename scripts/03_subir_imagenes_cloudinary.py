#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SUBIDA DE IMÁGENES A CLOUDINARY - VERSIÓN 2026
Actualizado para usar Asset Folders (Cloudinary SDK 1.44+)

AUTOR: Sistema Ecommerce Automation
FECHA: 2026-03-01
VERSION: 3.0 (Asset Folders)
"""

import json
import time
from pathlib import Path
from typing import Dict, List
from datetime import datetime

# SDK oficial de Cloudinary
import cloudinary
import cloudinary.uploader
import cloudinary.api

# Imports locales
import sys
sys.path.append(str(Path(__file__).parent))
from utils.config import Config
from utils.logger import get_logger

logger = get_logger('cloudinary_uploader_v3')


class SubidorCloudinary2026:
    """Subidor de imágenes usando Asset Folders (2026)"""
    
    def __init__(self):
        """Inicializa conexión con Cloudinary"""
        # Obtener credenciales
        credenciales = Config.get_credenciales_cloudinary()
        
        # Configurar SDK (método 2026)
        cloudinary.config(
            cloud_name=credenciales['cloud_name'],
            api_key=credenciales['api_key'],
            api_secret=credenciales['api_secret'],
            secure=True  # Obligatorio en 2026
        )
        
        self.cloud_name = credenciales['cloud_name']
        
        # Estadísticas
        self.stats = {
            'total_productos': 0,
            'total_imagenes': 0,
            'subidas_exitosas': 0,
            'ya_existentes': 0,
            'subidas_fallidas': 0,
            'tiempo_inicio': None,
            'tiempo_fin': None
        }
        
        logger.info(f"Conectado a Cloudinary: {self.cloud_name}")
        print(f"✅ Conectado a Cloudinary: {self.cloud_name}")
    
    def verificar_producto_en_cloudinary(self, sku: str, num_imagenes_local: int) -> dict:
        """
        Verifica qué imágenes tiene el producto en Cloudinary usando Asset Folders
        
        Args:
            sku: SKU del producto
            num_imagenes_local: Número de imágenes locales
            
        Returns:
            dict con estado de las imágenes
        """
        try:
            # Carpeta de asset (organización interna)
            asset_folder = f"ecommerce/productos/{sku}"
            
            # Listar recursos en esta carpeta (método 2026)
            recursos = cloudinary.api.resources_by_asset_folder(
                asset_folder,
                max_results=500
            )
            
            # Extraer public_ids
            imagenes_existentes = []
            for recurso in recursos.get('resources', []):
                public_id = recurso.get('public_id', '')
                imagenes_existentes.append(public_id)
            
            num_cloudinary = len(imagenes_existentes)
            completo = (num_cloudinary == num_imagenes_local)
            
            return {
                'completo': completo,
                'num_cloudinary': num_cloudinary,
                'imagenes_existentes': set(imagenes_existentes)
            }
            
        except cloudinary.exceptions.NotFound:
            # Carpeta no existe
            return {
                'completo': False,
                'num_cloudinary': 0,
                'imagenes_existentes': set()
            }
        except Exception as e:
            logger.debug(f"Error verificando {sku}: {e}")
            return {
                'completo': False,
                'num_cloudinary': 0,
                'imagenes_existentes': set()
            }
    
    def subir_imagen(self, ruta_imagen: Path, asset_folder: str, public_id: str) -> str:
        """
        Sube una imagen a Cloudinary usando Asset Folders
        
        Args:
            ruta_imagen: Ruta local de la imagen
            asset_folder: Carpeta de organización (ej: "ecommerce/productos/600053")
            public_id: ID público para la URL (ej: "prod_600053_001")
            
        Returns:
            URL segura de Cloudinary o None si falla
        """
        try:
            resultado = cloudinary.uploader.upload(
                str(ruta_imagen),
                asset_folder=asset_folder,
                public_id=public_id,
                use_asset_folder_as_public_id_prefix=False,  # URLs limpias
                unique_filename=False,
                overwrite=True,
                resource_type='image'
            )
            
            return resultado.get('secure_url')
            
        except Exception as e:
            logger.error(f"Error subiendo {public_id}: {e}")
            return None
    
    def procesar_producto_simple(self, carpeta_producto: Path) -> Dict:
        """
        Procesa un producto simple
        
        Args:
            carpeta_producto: Carpeta del producto
            
        Returns:
            dict con URLs de Cloudinary
        """
        sku = carpeta_producto.name
        print(f"\n📦 Producto: {sku}")
        
        # Buscar imágenes
        carpeta_imagenes = carpeta_producto / "imagenes_originales"
        if not carpeta_imagenes.exists():
            carpeta_imagenes = carpeta_producto
        
        imagenes = sorted(carpeta_imagenes.glob("*.jpg")) + \
                   sorted(carpeta_imagenes.glob("*.png")) + \
                   sorted(carpeta_imagenes.glob("*.webp"))
        
        if not imagenes:
            print(f"  ⚠️  Sin imágenes")
            return {'sku': sku, 'urls': []}
        
        num_imagenes_local = len(imagenes)
        
        # Verificar en Cloudinary
        print(f"  🔍 Verificando en Cloudinary ({num_imagenes_local} imágenes)...", end=" ")
        
        estado = self.verificar_producto_en_cloudinary(sku, num_imagenes_local)
        
        if estado['completo']:
            print(f"✓ Completo ({estado['num_cloudinary']})")
            self.stats['ya_existentes'] += num_imagenes_local
            
            # Construir URLs (ya existen)
            urls = []
            for i in range(1, num_imagenes_local + 1):
                public_id = f"prod_{sku}_{i:03d}"
                url = f"https://res.cloudinary.com/{self.cloud_name}/image/upload/{public_id}"
                urls.append(url)
            
            return {'sku': sku, 'urls': urls}
        
        # Subir imágenes
        num_cloud = estado['num_cloudinary']
        imagenes_existentes = estado['imagenes_existentes']
        
        if num_cloud == 0:
            print(f"✗ No existe")
            print(f"  ⚠️  Subiendo {num_imagenes_local} imágenes...")
        else:
            faltantes = num_imagenes_local - num_cloud
            print(f"⚠️  Incompleto ({num_cloud}/{num_imagenes_local})")
            print(f"  ⚠️  Subiendo {faltantes} faltantes...")
        
        urls_cloudinary = []
        asset_folder = f"ecommerce/productos/{sku}"
        
        for i, imagen in enumerate(imagenes, 1):
            public_id = f"prod_{sku}_{i:03d}"
            
            # Verificar si ya existe
            if public_id in imagenes_existentes:
                # Construir URL
                url = f"https://res.cloudinary.com/{self.cloud_name}/image/upload/{public_id}"
                urls_cloudinary.append(url)
                self.stats['ya_existentes'] += 1
                print(f"  ✓ {imagen.name} (existe)")
                continue
            
            # Subir
            print(f"  ⬆️  {imagen.name}...", end=" ")
            
            url = self.subir_imagen(imagen, asset_folder, public_id)
            
            if url:
                urls_cloudinary.append(url)
                self.stats['subidas_exitosas'] += 1
                print("✅")
            else:
                self.stats['subidas_fallidas'] += 1
                print("❌")
            
            self.stats['total_imagenes'] += 1
            time.sleep(0.2)  # Rate limiting
        
        print(f"  ✅ Completado: {len(urls_cloudinary)}/{num_imagenes_local}")
        
        return {'sku': sku, 'urls': urls_cloudinary}
    
    def actualizar_metadata(self, carpeta: Path, urls: List[str]):
        """Actualiza metadata.json con URLs de Cloudinary"""
        metadata_file = carpeta / "metadata.json"
        
        if not metadata_file.exists():
            return
        
        try:
            with open(metadata_file, 'r', encoding='utf-8') as f:
                metadata = json.load(f)
            
            metadata['imagenes_cloudinary'] = urls
            
            with open(metadata_file, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, indent=2, ensure_ascii=False)
                
        except Exception as e:
            logger.error(f"Error actualizando metadata: {e}")
    
    def ejecutar(self):
        """Ejecuta el proceso completo"""
        print("\n" + "="*70)
        print("☁️  SUBIDA A CLOUDINARY (Asset Folders 2026)")
        print("="*70)
        
        self.stats['tiempo_inicio'] = time.time()
        
        # Obtener productos
        productos_dir = Config.PRODUCTOS_DIR
        carpetas = sorted([d for d in productos_dir.iterdir() if d.is_dir()])
        
        self.stats['total_productos'] = len(carpetas)
        
        print(f"\n📦 Productos encontrados: {len(carpetas)}\n")
        
        # Procesar cada producto
        for i, carpeta in enumerate(carpetas, 1):
            try:
                resultado = self.procesar_producto_simple(carpeta)
                self.actualizar_metadata(carpeta, resultado['urls'])
                
                # Progreso cada 25
                if i % 25 == 0:
                    porcentaje = (i / len(carpetas)) * 100
                    print(f"\n{'─'*70}")
                    print(f"📊 Progreso: {i}/{len(carpetas)} ({porcentaje:.1f}%)")
                    print(f"   ✅ Subidas: {self.stats['subidas_exitosas']}")
                    print(f"   ✓ Existentes: {self.stats['ya_existentes']}")
                    print(f"   ❌ Fallidas: {self.stats['subidas_fallidas']}")
                    print(f"{'─'*70}\n")
                    
            except KeyboardInterrupt:
                print("\n\n⚠️  Interrumpido por usuario")
                break
            except Exception as e:
                logger.error(f"Error en {carpeta.name}: {e}")
                continue
        
        self.stats['tiempo_fin'] = time.time()
        self.mostrar_resumen()
    
    def mostrar_resumen(self):
        """Muestra resumen final"""
        tiempo_total = self.stats['tiempo_fin'] - self.stats['tiempo_inicio']
        minutos = int(tiempo_total // 60)
        segundos = int(tiempo_total % 60)
        
        print(f"\n{'='*70}")
        print("📊 RESUMEN DE SUBIDA")
        print(f"{'='*70}")
        print(f"\n📦 Productos: {self.stats['total_productos']}")
        print(f"📷 Imágenes:")
        print(f"   ✅ Subidas: {self.stats['subidas_exitosas']}")
        print(f"   ✓ Ya existían: {self.stats['ya_existentes']}")
        print(f"   ❌ Fallidas: {self.stats['subidas_fallidas']}")
        print(f"\n⏱️  Tiempo: {minutos}m {segundos}s")
        print(f"\n{'='*70}")


def main():
    """Función principal"""
    try:
        subidor = SubidorCloudinary2026()
        subidor.ejecutar()
        return 0
    except Exception as e:
        print(f"\n❌ Error fatal: {e}")
        logger.exception("Error fatal")
        return 1


if __name__ == "__main__":
    sys.exit(main())
