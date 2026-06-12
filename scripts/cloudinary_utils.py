#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
UTILIDADES DE CLOUDINARY
Gestión de imágenes en Cloudinary (listar, eliminar, estadísticas)
"""

import json
import cloudinary
import cloudinary.api
import cloudinary.uploader
from pathlib import Path
from datetime import datetime

# Imports locales
import sys
sys.path.append(str(Path(__file__).parent))
from utils.config import Config
from utils.logger import get_logger

logger = get_logger('cloudinary_utils')


class CloudinaryManager:
    """Gestor de Cloudinary"""
    
    def __init__(self):
        """Inicializa la conexión con Cloudinary"""
        # Cargar credenciales
        credenciales = Config.get_credenciales_cloudinary()
        
        cloudinary.config(
            cloud_name=credenciales['cloud_name'],
            api_key=credenciales['api_key'],
            api_secret=credenciales['api_secret']
        )
        
        self.cloud_name = credenciales['cloud_name']
        logger.info(f"Conectado a Cloudinary: {self.cloud_name}")
    
    def listar_recursos(self, max_results: int = 500):
        """
        Lista todos los recursos en Cloudinary
        
        Args:
            max_results: Máximo de resultados (default 500, max 500 por llamada)
        
        Returns:
            list: Lista de recursos
        """
        recursos = []
        next_cursor = None
        
        try:
            while True:
                if next_cursor:
                    result = cloudinary.api.resources(
                        max_results=max_results,
                        next_cursor=next_cursor
                    )
                else:
                    result = cloudinary.api.resources(max_results=max_results)
                
                recursos.extend(result.get('resources', []))
                
                next_cursor = result.get('next_cursor')
                if not next_cursor:
                    break
                
                logger.info(f"Cargados {len(recursos)} recursos...")
            
            logger.info(f"✅ Total recursos encontrados: {len(recursos)}")
            return recursos
            
        except Exception as e:
            logger.error(f"Error listando recursos: {e}")
            return []
    
    def limpiar_metadata_json(self):
        """Limpia referencias de Cloudinary en todos los metadata.json"""
        print("\n" + "="*80)
        print("🧹 LIMPIANDO REFERENCIAS EN METADATA.JSON")
        print("="*80)
        print("\nEliminando campo 'imagenes_cloudinary' de todos los productos...")
        
        try:
            from utils.config import Config
            
            productos_dir = Config.PRODUCTOS_DIR
            
            total_productos = 0
            productos_limpiados = 0
            
            for carpeta in productos_dir.iterdir():
                if not carpeta.is_dir():
                    continue
                
                metadata_file = carpeta / 'metadata.json'
                if not metadata_file.exists():
                    continue
                
                total_productos += 1
                sku = carpeta.name
                
                try:
                    # Leer metadata
                    with open(metadata_file, 'r', encoding='utf-8') as f:
                        metadata = json.load(f)
                    
                    # Verificar si tiene referencias de Cloudinary
                    if 'imagenes_cloudinary' in metadata:
                        num_imagenes = len(metadata.get('imagenes_cloudinary', []))
                        
                        if num_imagenes > 0:
                            # Eliminar campo
                            del metadata['imagenes_cloudinary']
                            
                            # Guardar
                            with open(metadata_file, 'w', encoding='utf-8') as f:
                                json.dump(metadata, f, indent=2, ensure_ascii=False)
                            
                            productos_limpiados += 1
                
                except Exception as e:
                    logger.error(f"Error limpiando {sku}: {e}")
            
            print(f"\n✅ Limpieza completada:")
            print(f"   • Total productos: {total_productos}")
            print(f"   • Limpiados: {productos_limpiados}")
            print(f"   • Sin cambios: {total_productos - productos_limpiados}")
            
            logger.info(f"Limpieza de metadata: {productos_limpiados} productos limpiados")
            
            return productos_limpiados
            
        except Exception as e:
            logger.error(f"Error en limpieza de metadata: {e}")
            print(f"\n❌ Error limpiando metadata: {e}")
            return 0
    
    def eliminar_todos(self, confirmar_callback=None) -> dict:
        """
        Elimina TODOS los recursos de Cloudinary y limpia metadata.json
        
        Args:
            confirmar_callback: Función de confirmación (opcional)
        
        Returns:
            dict: Estadísticas de la eliminación
        """
        print("\n" + "=" * 80)
        print("⚠️  ELIMINAR TODAS LAS IMÁGENES DE CLOUDINARY")
        print("=" * 80)
        
        # Listar recursos
        print("\n📊 Consultando recursos en Cloudinary...")
        recursos = self.listar_recursos()
        
        if not recursos:
            print("\n✅ No hay recursos para eliminar")
            
            # Pero igual limpiar metadata por si acaso
            print("\n🧹 Limpiando referencias en metadata.json...")
            self.limpiar_metadata_json()
            
            return {'total': 0, 'eliminados': 0, 'fallidos': 0}
        
        total = len(recursos)
        
        # Mostrar info
        print(f"\n📷 Total de imágenes encontradas: {total}")
        
        # Calcular tamaño total (si está disponible)
        tamano_total = sum(r.get('bytes', 0) for r in recursos) / (1024 * 1024)
        if tamano_total > 0:
            print(f"💾 Tamaño total: {tamano_total:.2f} MB")
        
        # Solicitar confirmación
        print(f"\n{'─' * 80}")
        print("⚠️  ADVERTENCIA: Esta acción NO se puede deshacer")
        print("   Se eliminarán PERMANENTEMENTE todas las imágenes")
        print("   También se limpiarán las referencias en metadata.json")
        print(f"{'─' * 80}")
        
        if confirmar_callback:
            if not confirmar_callback():
                print("\n❌ Operación cancelada")
                return {'total': total, 'eliminados': 0, 'fallidos': 0, 'cancelado': True}
        else:
            print("\n¿Estás SEGURO que querés eliminar TODAS las imágenes?")
            confirmar1 = input("Escribí 'ELIMINAR TODO' para confirmar: ")
            
            if confirmar1 != 'ELIMINAR TODO':
                print("\n❌ Operación cancelada")
                return {'total': total, 'eliminados': 0, 'fallidos': 0, 'cancelado': True}
            
            confirmar2 = input("\n¿Confirmar eliminación? (s/n): ").lower()
            
            if confirmar2 != 's':
                print("\n❌ Operación cancelada")
                return {'total': total, 'eliminados': 0, 'fallidos': 0, 'cancelado': True}
        
        # Proceder con la eliminación
        print(f"\n🗑️  Eliminando {total} recursos...")
        print("   Esto puede tardar varios minutos...\n")
        
        eliminados = 0
        fallidos = 0
        
        # Eliminar en lotes de 100 (límite de la API)
        public_ids = [r['public_id'] for r in recursos]
        
        for i in range(0, len(public_ids), 100):
            lote = public_ids[i:i+100]
            
            try:
                result = cloudinary.api.delete_resources(lote)
                
                # Contar eliminados y fallidos
                deleted = result.get('deleted', {})
                for public_id, status in deleted.items():
                    if status == 'deleted':
                        eliminados += 1
                    else:
                        fallidos += 1
                
                porcentaje = ((i + len(lote)) / len(public_ids)) * 100
                print(f"   Progreso: {porcentaje:.1f}% ({eliminados} eliminados, {fallidos} fallidos)")
                
            except Exception as e:
                logger.error(f"Error eliminando lote: {e}")
                fallidos += len(lote)
        
        # Limpiar metadata.json automáticamente
        self.limpiar_metadata_json()
        
        # Resumen
        print(f"\n{'=' * 80}")
        print("📊 RESUMEN DE ELIMINACIÓN")
        print(f"{'=' * 80}")
        print(f"\nTotal recursos: {total}")
        print(f"✅ Eliminados: {eliminados}")
        print(f"❌ Fallidos: {fallidos}")
        print(f"\n✅ Referencias en metadata.json limpiadas")
        print(f"{'=' * 80}")
        
        logger.info(f"Eliminación completada: {eliminados}/{total}")
        
        return {
            'total': total,
            'eliminados': eliminados,
            'fallidos': fallidos
        }
    
    def obtener_estadisticas(self):
        """Obtiene estadísticas de uso de Cloudinary"""
        try:
            # Obtener info de la cuenta
            result = cloudinary.api.usage()
            
            print("\n" + "=" * 80)
            print("📊 ESTADÍSTICAS DE CLOUDINARY")
            print("=" * 80)
            print(f"\nCloud: {self.cloud_name}")
            print(f"\n💾 Almacenamiento:")
            
            # Límites y uso
            plan = result.get('plan', 'Desconocido')
            print(f"   Plan: {plan}")
            
            if 'credits' in result:
                credits = result['credits']
                used = credits.get('used_percent', 0)
                print(f"   Créditos usados: {used}%")
            
            if 'storage' in result:
                storage = result['storage']
                used_bytes = storage.get('used', 0)
                limit_bytes = storage.get('limit', 0)
                
                used_mb = used_bytes / (1024 * 1024)
                limit_mb = limit_bytes / (1024 * 1024) if limit_bytes > 0 else 0
                
                print(f"   Usado: {used_mb:.2f} MB")
                if limit_mb > 0:
                    print(f"   Límite: {limit_mb:.2f} MB")
                    porcentaje = (used_mb / limit_mb) * 100
                    print(f"   Porcentaje: {porcentaje:.1f}%")
            
            # Recursos
            recursos = self.listar_recursos()
            print(f"\n📷 Recursos:")
            print(f"   Total imágenes: {len(recursos)}")
            
            print(f"\n{'=' * 80}")
            
        except Exception as e:
            logger.error(f"Error obteniendo estadísticas: {e}")
            print(f"\n❌ Error: {e}")


def main():
    """Menú de utilidades de Cloudinary"""
    print("=" * 80)
    print("☁️  UTILIDADES DE CLOUDINARY")
    print("=" * 80)
    
    try:
        manager = CloudinaryManager()
    except Exception as e:
        print(f"\n❌ Error conectando a Cloudinary: {e}")
        print("   Verificar credenciales en config/.env")
        return
    
    while True:
        print(f"\n{'─' * 80}")
        print("📋 OPCIONES:")
        print("  1️⃣  Ver estadísticas")
        print("  2️⃣  Listar recursos")
        print("  3️⃣  Eliminar TODAS las imágenes")
        print("  0️⃣  Salir")
        print(f"{'─' * 80}")
        
        opcion = input("\nSeleccionar opción: ").strip()
        
        if opcion == '1':
            manager.obtener_estadisticas()
            
        elif opcion == '2':
            print("\n📊 Listando recursos...")
            recursos = manager.listar_recursos()
            
            if recursos:
                print(f"\n{'─' * 80}")
                print(f"Total: {len(recursos)} imágenes")
                print(f"{'─' * 80}")
                print(f"{'Public ID':<50} {'Tamaño':>15}")
                print(f"{'─' * 80}")
                
                for i, r in enumerate(recursos[:20], 1):  # Primeros 20
                    public_id = r.get('public_id', '')
                    bytes_size = r.get('bytes', 0)
                    kb_size = bytes_size / 1024
                    print(f"{public_id:<50} {kb_size:>12.1f} KB")
                
                if len(recursos) > 20:
                    print(f"\n... y {len(recursos) - 20} más")
            else:
                print("\n✅ No hay recursos en Cloudinary")
            
            input("\nPresionar Enter para continuar...")
            
        elif opcion == '3':
            manager.eliminar_todos()
            input("\nPresionar Enter para continuar...")
            
        elif opcion == '0':
            print("\n👋 ¡Hasta luego!")
            break
            
        else:
            print("\n❌ Opción inválida")


if __name__ == "__main__":
    main()
