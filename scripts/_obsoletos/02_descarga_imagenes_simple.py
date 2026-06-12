#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DESCARGADOR SIMPLE DE IMÁGENES
Descarga TODAS las imágenes de TODOS los productos SIN optimizaciones complejas
"""

import os
import requests
import time
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple
from urllib.parse import urlparse

# Imports locales
import sys
sys.path.append(str(Path(__file__).parent))
from utils.config import Config
from utils.logger import get_logger, LoggerManager

logger = get_logger('descarga_imagenes_simple')


class DescargadorSimple:
    """Descargador simple y robusto de imágenes"""
    
    def __init__(self):
        """Inicializa el descargador"""
        self.estadisticas = {
            'total_productos': 0,
            'total_imagenes': 0,
            'descargadas': 0,
            'ya_existian': 0,
            'fallidas': 0,
            'bytes_descargados': 0
        }
        
        # Configuración
        self.delay_entre_imagenes = 0.5
        self.delay_entre_productos = 1.0
        self.timeout = 30
        self.reintentos_max = 3
        
        # Sesión HTTP
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        
        logger.info("Descargador simple inicializado")
    
    def obtener_extension_desde_url(self, url: str) -> str:
        """Obtiene la extensión del archivo desde la URL"""
        parsed = urlparse(url)
        path = parsed.path
        
        if '.' in path:
            extension = path.split('.')[-1].lower().split('?')[0]
            extensiones_validas = ['jpg', 'jpeg', 'png', 'gif', 'webp', 'bmp']
            if extension in extensiones_validas:
                return f'.{extension}'
        
        return '.jpg'
    
    def descargar_imagen(self, url: str, destino: Path, reintentos: int = 0) -> Tuple[bool, int]:
        """Descarga una imagen desde una URL"""
        try:
            response = self.session.get(url, timeout=self.timeout, stream=True)
            response.raise_for_status()
            
            destino.parent.mkdir(parents=True, exist_ok=True)
            
            bytes_descargados = 0
            with open(destino, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        bytes_descargados += len(chunk)
            
            return True, bytes_descargados
            
        except requests.exceptions.RequestException as e:
            if reintentos < self.reintentos_max:
                logger.debug(f"Reintentando... ({reintentos + 1}/{self.reintentos_max})")
                time.sleep(2 * (reintentos + 1))
                return self.descargar_imagen(url, destino, reintentos + 1)
            
            logger.warning(f"Error descargando {url}: {e}")
            return False, 0
        
        except Exception as e:
            logger.error(f"Error inesperado: {e}")
            return False, 0
    
    def procesar_producto(self, sku: str, num: int, total: int):
        """
        Procesa un producto y descarga sus imágenes
        
        Args:
            sku: SKU del producto
            num: Número de producto actual
            total: Total de productos
        """
        try:
            metadata = Config.cargar_metadata(sku)
            imagenes = metadata.get('imagenes', [])
            
            if not imagenes:
                logger.warning(f"[{num}/{total}] {sku}: Sin imágenes")
                return
            
            # Carpeta de destino
            dir_imagenes = Config.get_directorio_producto(sku) / 'imagenes_originales'
            
            logger.info(f"[{num}/{total}] {sku} ({len(imagenes)} imágenes)")
            
            descargadas = 0
            ya_existian = 0
            fallidas = 0
            
            for i, url in enumerate(imagenes, 1):
                extension = self.obtener_extension_desde_url(url)
                nombre_archivo = f"img_{i:03d}{extension}"
                ruta_destino = dir_imagenes / nombre_archivo
                
                # Verificar si ya existe
                if ruta_destino.exists() and ruta_destino.stat().st_size > 1024:
                    logger.debug(f"  ✓ {nombre_archivo} ya existe")
                    ya_existian += 1
                    self.estadisticas['ya_existian'] += 1
                    continue
                
                # Descargar
                logger.debug(f"  ⬇ {i}/{len(imagenes)}: {nombre_archivo}")
                exito, bytes_desc = self.descargar_imagen(url, ruta_destino)
                
                if exito:
                    descargadas += 1
                    self.estadisticas['descargadas'] += 1
                    self.estadisticas['bytes_descargados'] += bytes_desc
                    logger.debug(f"  ✅ {nombre_archivo} ({bytes_desc / 1024:.1f} KB)")
                else:
                    fallidas += 1
                    self.estadisticas['fallidas'] += 1
                    logger.error(f"  ❌ {nombre_archivo}")
                
                time.sleep(self.delay_entre_imagenes)
            
            logger.info(
                f"  ✅ {descargadas} descargadas, "
                f"✓ {ya_existian} existían, "
                f"❌ {fallidas} fallidas"
            )
            
            time.sleep(self.delay_entre_productos)
            
        except Exception as e:
            logger.error(f"Error procesando {sku}: {e}")
    
    def descargar_todas(self, solo_faltantes: bool = False):
        """
        Descarga todas las imágenes
        
        Args:
            solo_faltantes: Si True, solo descarga productos sin imágenes
        """
        # Obtener lista de productos
        todos_productos = Config.listar_productos()
        
        if not todos_productos:
            print("\n⚠️  No hay productos para procesar")
            return
        
        # Filtrar si solo queremos los faltantes
        if solo_faltantes:
            productos_a_procesar = []
            for sku in todos_productos:
                dir_imagenes = Config.get_directorio_producto(sku) / 'imagenes_originales'
                if not dir_imagenes.exists() or not list(dir_imagenes.glob('img_*')):
                    productos_a_procesar.append(sku)
            
            print(f"\n📊 Productos sin imágenes: {len(productos_a_procesar)}")
        else:
            productos_a_procesar = todos_productos
            print(f"\n📊 Total productos: {len(productos_a_procesar)}")
        
        if not productos_a_procesar:
            print("✅ Todos los productos ya tienen imágenes")
            return
        
        self.estadisticas['total_productos'] = len(productos_a_procesar)
        
        # Calcular total de imágenes
        for sku in productos_a_procesar:
            try:
                metadata = Config.cargar_metadata(sku)
                self.estadisticas['total_imagenes'] += len(metadata.get('imagenes', []))
            except:
                pass
        
        LoggerManager.log_inicio_proceso(
            logger,
            "Descarga de Imágenes",
            self.estadisticas['total_imagenes']
        )
        
        print(f"\n{'=' * 80}")
        print(f"🖼️  DESCARGANDO IMÁGENES")
        print(f"{'=' * 80}")
        print(f"\nProductos a procesar: {len(productos_a_procesar)}")
        print(f"Imágenes estimadas: {self.estadisticas['total_imagenes']}")
        print(f"\n{'─' * 80}\n")
        
        inicio = time.time()
        
        # Procesar cada producto
        for i, sku in enumerate(productos_a_procesar, 1):
            try:
                self.procesar_producto(sku, i, len(productos_a_procesar))
                
                # Mostrar progreso cada 25 productos
                if i % 25 == 0:
                    self._mostrar_progreso(i, len(productos_a_procesar))
                    
            except KeyboardInterrupt:
                logger.warning("Descarga interrumpida por el usuario")
                print("\n\n⚠️  Descarga interrumpida")
                print("   Podés reanudar ejecutando el script de nuevo")
                break
            except Exception as e:
                logger.error(f"Error procesando {sku}: {e}")
                continue
        
        tiempo_total = time.time() - inicio
        
        LoggerManager.log_fin_proceso(
            logger,
            "Descarga de Imágenes",
            self.estadisticas['descargadas'],
            self.estadisticas['fallidas']
        )
        
        self.mostrar_resumen(tiempo_total)
        self.generar_reporte()
    
    def _mostrar_progreso(self, actual: int, total: int):
        """Muestra progreso parcial"""
        porcentaje = (actual / total) * 100
        print(f"\n{'─' * 80}")
        print(f"📊 Progreso: {actual}/{total} productos ({porcentaje:.1f}%)")
        print(f"   ✅ Descargadas: {self.estadisticas['descargadas']}")
        print(f"   ✓ Ya existían: {self.estadisticas['ya_existian']}")
        print(f"   ❌ Fallidas: {self.estadisticas['fallidas']}")
        print(f"{'─' * 80}\n")
    
    def mostrar_resumen(self, tiempo_total: float):
        """Muestra resumen final"""
        mb_descargados = self.estadisticas['bytes_descargados'] / (1024 * 1024)
        velocidad = self.estadisticas['descargadas'] / tiempo_total if tiempo_total > 0 else 0
        
        print(f"\n{'=' * 80}")
        print("📊 RESUMEN DE DESCARGA")
        print(f"{'=' * 80}")
        print(f"\nProductos procesados: {self.estadisticas['total_productos']}")
        print(f"\n📷 Imágenes:")
        print(f"   Total: {self.estadisticas['total_imagenes']}")
        print(f"   ✅ Descargadas: {self.estadisticas['descargadas']}")
        print(f"   ✓ Ya existían: {self.estadisticas['ya_existian']}")
        print(f"   ❌ Fallidas: {self.estadisticas['fallidas']}")
        
        if self.estadisticas['descargadas'] > 0:
            print(f"\n💾 Datos descargados: {mb_descargados:.2f} MB")
        
        print(f"\n⏱️  Tiempo total: {tiempo_total / 60:.1f} minutos")
        if velocidad > 0:
            print(f"   Velocidad: {velocidad:.1f} imágenes/segundo")
        
        # Tasa de éxito
        total_intentos = self.estadisticas['descargadas'] + self.estadisticas['fallidas']
        if total_intentos > 0:
            tasa_exito = (self.estadisticas['descargadas'] / total_intentos) * 100
            print(f"\n✅ Tasa de éxito: {tasa_exito:.1f}%")
        
        print(f"\n{'=' * 80}")
    
    def generar_reporte(self):
        """Genera reporte JSON"""
        fecha = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
        reporte_file = Config.LOGS_DIR / f"reporte_imagenes_{fecha}.json"
        
        reporte = {
            'fecha': datetime.now().isoformat(),
            'estadisticas': self.estadisticas
        }
        
        with open(reporte_file, 'w', encoding='utf-8') as f:
            json.dump(reporte, f, indent=2, ensure_ascii=False)
        
        logger.info(f"📄 Reporte guardado en: {reporte_file}")
        print(f"\n📄 Reporte: {reporte_file}")


def main():
    """Ejecuta el descargador"""
    print("=" * 80)
    print("🖼️  DESCARGADOR SIMPLE DE IMÁGENES")
    print("=" * 80)
    
    descargador = DescargadorSimple()
    
    # Preguntar si solo descargar faltantes
    print("\n¿Qué deseas hacer?")
    print("  1️⃣  Descargar TODAS las imágenes (sobrescribe existentes)")
    print("  2️⃣  Descargar solo productos SIN imágenes (recomendado)")
    
    opcion = input("\nSeleccionar opción (1/2): ").strip()
    
    solo_faltantes = (opcion == '2')
    
    print(f"\n{'─' * 80}")
    confirmar = input("\n¿Iniciar descarga? (s/n): ").lower()
    
    if confirmar == 's':
        descargador.descargar_todas(solo_faltantes=solo_faltantes)
    else:
        print("\nDescarga cancelada")


if __name__ == "__main__":
    main()
