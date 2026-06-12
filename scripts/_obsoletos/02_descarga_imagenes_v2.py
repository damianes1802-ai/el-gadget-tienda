#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DESCARGADOR DE IMÁGENES CON DETECCIÓN INTELIGENTE DE VARIANTES
Descarga imágenes evitando duplicados en grupos de variantes
"""

import os
import requests
import time
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple, Set
from urllib.parse import urlparse
from collections import defaultdict

# Imports locales
import sys
sys.path.append(str(Path(__file__).parent))
from utils.config import Config
from utils.logger import get_logger, LoggerManager

logger = get_logger('descarga_imagenes')


class AnalizadorVariantes:
    """Analiza grupos de variantes para detectar imágenes comunes y únicas"""
    
    @staticmethod
    def analizar_grupo(skus_grupo: List[str]) -> Dict:
        """
        Analiza un grupo de variantes y determina qué imágenes son comunes
        
        Args:
            skus_grupo: Lista de SKUs del grupo
        
        Returns:
            dict: {
                'tipo': 'identicas' | 'mixtas' | 'unicas',
                'imagenes_comunes': [urls],
                'imagenes_por_variante': {sku: [urls_unicas]},
                'todas_imagenes': {sku: [todas_urls]}
            }
        """
        # Cargar imágenes de cada variante
        imagenes_por_sku = {}
        
        for sku in skus_grupo:
            try:
                metadata = Config.cargar_metadata(sku)
                imagenes = metadata.get('imagenes', [])
                imagenes_por_sku[sku] = set(imagenes)
            except Exception as e:
                logger.warning(f"Error cargando {sku}: {e}")
                imagenes_por_sku[sku] = set()
        
        # Si alguno no tiene imágenes, retornar análisis básico
        if not all(imagenes_por_sku.values()):
            logger.warning("Algunas variantes no tienen imágenes")
        
        # Encontrar intersección (imágenes comunes a TODAS las variantes)
        if imagenes_por_sku:
            imagenes_comunes = set.intersection(*imagenes_por_sku.values()) if len(imagenes_por_sku) > 1 else imagenes_por_sku[skus_grupo[0]]
        else:
            imagenes_comunes = set()
        
        # Calcular imágenes únicas por variante
        imagenes_unicas_por_sku = {}
        for sku, imagenes in imagenes_por_sku.items():
            imagenes_unicas_por_sku[sku] = imagenes - imagenes_comunes
        
        # Determinar tipo de grupo
        if len(skus_grupo) == 1:
            tipo = 'producto_unico'
        elif all(len(imgs) == 0 for imgs in imagenes_unicas_por_sku.values()):
            tipo = 'identicas'  # Todas las variantes tienen exactamente las mismas imágenes
        elif len(imagenes_comunes) == 0:
            tipo = 'unicas'  # Cada variante tiene solo imágenes únicas
        else:
            tipo = 'mixtas'  # Hay imágenes comunes + únicas
        
        return {
            'tipo': tipo,
            'imagenes_comunes': list(imagenes_comunes),
            'imagenes_por_variante': {sku: list(imgs) for sku, imgs in imagenes_unicas_por_sku.items()},
            'todas_imagenes': {sku: list(imgs) for sku, imgs in imagenes_por_sku.items()},
            'cantidad_comunes': len(imagenes_comunes),
            'cantidad_total': sum(len(imgs) for imgs in imagenes_por_sku.values())
        }


class DescargadorImagenesConVariantes:
    """Descarga imágenes optimizando duplicados en variantes"""
    
    def __init__(self, archivo_variantes: Path = None):
        """
        Inicializa el descargador
        
        Args:
            archivo_variantes: Path al archivo de variantes confirmadas
        """
        self.archivo_variantes = archivo_variantes
        self.grupos = []
        self.productos_individuales = []
        
        self.estadisticas = {
            'total_productos': 0,
            'total_grupos': 0,
            'total_imagenes': 0,
            'imagenes_unicas': 0,
            'imagenes_duplicadas_evitadas': 0,
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
        
        logger.info("Descargador con detección de variantes inicializado")
    
    def cargar_variantes(self):
        """Carga grupos de variantes desde el archivo"""
        if not self.archivo_variantes or not self.archivo_variantes.exists():
            logger.warning("No se encontró archivo de variantes, procesando productos individualmente")
            return self._cargar_productos_individuales()
        
        try:
            with open(self.archivo_variantes, 'r', encoding='utf-8') as f:
                datos = json.load(f)
            
            grupos_confirmados = datos.get('grupos_confirmados', [])
            
            # Separar grupos aprobados/manuales de rechazados
            skus_en_grupos = set()
            
            for grupo in grupos_confirmados:
                accion = grupo.get('accion')
                
                if accion in ['APROBADO', 'MANUAL', 'MODIFICADO']:
                    # Este es un grupo de variantes válido
                    skus = grupo.get('skus', [])
                    if skus:
                        self.grupos.append({
                            'id_grupo': grupo.get('id_grupo'),
                            'nombre': grupo.get('producto_base', 'Grupo'),
                            'tipo_variante': grupo.get('atributo_variante'),
                            'skus': skus,
                            'valores_variantes': grupo.get('valores_variantes', {})
                        })
                        skus_en_grupos.update(skus)
            
            # Productos que NO están en ningún grupo
            todos_los_skus = set(Config.listar_productos())
            skus_individuales = todos_los_skus - skus_en_grupos
            
            self.productos_individuales = list(skus_individuales)
            
            self.estadisticas['total_grupos'] = len(self.grupos)
            self.estadisticas['total_productos'] = len(self.productos_individuales) + sum(len(g['skus']) for g in self.grupos)
            
            logger.info(f"✅ Cargados {len(self.grupos)} grupos de variantes")
            logger.info(f"✅ {len(self.productos_individuales)} productos individuales")
            
        except Exception as e:
            logger.error(f"Error cargando variantes: {e}")
            return self._cargar_productos_individuales()
    
    def _cargar_productos_individuales(self):
        """Carga todos los productos como individuales (sin variantes)"""
        skus = Config.listar_productos()
        self.productos_individuales = skus
        self.estadisticas['total_productos'] = len(skus)
        logger.info(f"✅ Cargados {len(skus)} productos (modo individual)")
    
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
    
    def procesar_grupo(self, grupo: Dict, num: int, total: int):
        """
        Procesa un grupo de variantes
        
        Args:
            grupo: Datos del grupo
            num: Número de grupo actual
            total: Total de grupos
        """
        id_grupo = grupo['id_grupo']
        nombre = grupo['nombre']
        skus = grupo['skus']
        
        logger.info(f"[Grupo {num}/{total}] {nombre} ({len(skus)} variantes)")
        
        # Analizar el grupo
        analisis = AnalizadorVariantes.analizar_grupo(skus)
        tipo = analisis['tipo']
        
        logger.info(f"  Tipo detectado: {tipo}")
        logger.info(f"  Imágenes comunes: {analisis['cantidad_comunes']}")
        
        if tipo == 'identicas':
            # Todas las variantes tienen las mismas imágenes
            # Descargar UNA VEZ en carpeta del primer SKU
            self._descargar_identicas(skus[0], analisis['todas_imagenes'][skus[0]])
            
            # Contar duplicados evitados
            imagenes_evitadas = analisis['cantidad_comunes'] * (len(skus) - 1)
            self.estadisticas['imagenes_duplicadas_evitadas'] += imagenes_evitadas
            logger.info(f"  ✓ Duplicados evitados: {imagenes_evitadas} imágenes")
            
        elif tipo == 'mixtas':
            # Hay imágenes comunes + específicas
            self._descargar_mixtas(id_grupo, analisis)
            
        elif tipo == 'unicas':
            # Cada variante tiene solo sus imágenes
            self._descargar_unicas(id_grupo, analisis)
        
        time.sleep(self.delay_entre_productos)
    
    def _descargar_identicas(self, sku_base: str, urls: List[str]):
        """Descarga imágenes cuando todas las variantes son idénticas"""
        dir_destino = Config.get_directorio_producto(sku_base) / 'imagenes_originales'
        
        logger.info(f"  Descargando en: {sku_base}/imagenes_originales/")
        
        for i, url in enumerate(urls, 1):
            extension = self.obtener_extension_desde_url(url)
            nombre = f"img_{i:03d}{extension}"
            ruta = dir_destino / nombre
            
            if ruta.exists() and ruta.stat().st_size > 1024:
                logger.debug(f"    ✓ {nombre} ya existe")
                self.estadisticas['ya_existian'] += 1
                continue
            
            exito, bytes_desc = self.descargar_imagen(url, ruta)
            
            if exito:
                self.estadisticas['descargadas'] += 1
                self.estadisticas['bytes_descargados'] += bytes_desc
                self.estadisticas['imagenes_unicas'] += 1
                logger.debug(f"    ✅ {nombre} ({bytes_desc / 1024:.1f} KB)")
            else:
                self.estadisticas['fallidas'] += 1
                logger.error(f"    ❌ {nombre}")
            
            time.sleep(self.delay_entre_imagenes)
    
    def _descargar_mixtas(self, id_grupo: str, analisis: Dict):
        """Descarga imágenes cuando hay comunes + específicas"""
        # Crear carpeta del grupo
        dir_grupo = Config.PRODUCTOS_DIR / id_grupo
        dir_grupo.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"  Estructura: {id_grupo}/")
        
        # 1. Descargar imágenes comunes
        if analisis['imagenes_comunes']:
            dir_comunes = dir_grupo / 'imagenes_comunes'
            logger.info(f"    - imagenes_comunes/ ({len(analisis['imagenes_comunes'])} imgs)")
            
            for i, url in enumerate(analisis['imagenes_comunes'], 1):
                extension = self.obtener_extension_desde_url(url)
                nombre = f"img_{i:03d}{extension}"
                ruta = dir_comunes / nombre
                
                if ruta.exists() and ruta.stat().st_size > 1024:
                    self.estadisticas['ya_existian'] += 1
                    continue
                
                exito, bytes_desc = self.descargar_imagen(url, ruta)
                
                if exito:
                    self.estadisticas['descargadas'] += 1
                    self.estadisticas['bytes_descargados'] += bytes_desc
                    self.estadisticas['imagenes_unicas'] += 1
                else:
                    self.estadisticas['fallidas'] += 1
                
                time.sleep(self.delay_entre_imagenes)
        
        # 2. Descargar imágenes específicas por variante
        for sku, urls_unicas in analisis['imagenes_por_variante'].items():
            if urls_unicas:
                dir_variante = dir_grupo / sku
                logger.info(f"    - {sku}/ ({len(urls_unicas)} imgs)")
                
                for i, url in enumerate(urls_unicas, 1):
                    extension = self.obtener_extension_desde_url(url)
                    nombre = f"img_{i:03d}{extension}"
                    ruta = dir_variante / nombre
                    
                    if ruta.exists() and ruta.stat().st_size > 1024:
                        self.estadisticas['ya_existian'] += 1
                        continue
                    
                    exito, bytes_desc = self.descargar_imagen(url, ruta)
                    
                    if exito:
                        self.estadisticas['descargadas'] += 1
                        self.estadisticas['bytes_descargados'] += bytes_desc
                        self.estadisticas['imagenes_unicas'] += 1
                    else:
                        self.estadisticas['fallidas'] += 1
                    
                    time.sleep(self.delay_entre_imagenes)
    
    def _descargar_unicas(self, id_grupo: str, analisis: Dict):
        """Descarga cuando cada variante tiene solo imágenes únicas"""
        dir_grupo = Config.PRODUCTOS_DIR / id_grupo
        dir_grupo.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"  Estructura: {id_grupo}/")
        
        for sku, urls in analisis['todas_imagenes'].items():
            if urls:
                dir_variante = dir_grupo / sku
                logger.info(f"    - {sku}/ ({len(urls)} imgs)")
                
                for i, url in enumerate(urls, 1):
                    extension = self.obtener_extension_desde_url(url)
                    nombre = f"img_{i:03d}{extension}"
                    ruta = dir_variante / nombre
                    
                    if ruta.exists() and ruta.stat().st_size > 1024:
                        self.estadisticas['ya_existian'] += 1
                        continue
                    
                    exito, bytes_desc = self.descargar_imagen(url, ruta)
                    
                    if exito:
                        self.estadisticas['descargadas'] += 1
                        self.estadisticas['bytes_descargados'] += bytes_desc
                        self.estadisticas['imagenes_unicas'] += 1
                    else:
                        self.estadisticas['fallidas'] += 1
                    
                    time.sleep(self.delay_entre_imagenes)
    
    def procesar_producto_individual(self, sku: str):
        """Procesa un producto que no está en ningún grupo"""
        try:
            metadata = Config.cargar_metadata(sku)
            imagenes = metadata.get('imagenes', [])
            
            if not imagenes:
                logger.warning(f"{sku}: Sin imágenes")
                return
            
            dir_destino = Config.get_directorio_producto(sku) / 'imagenes_originales'
            
            for i, url in enumerate(imagenes, 1):
                extension = self.obtener_extension_desde_url(url)
                nombre = f"img_{i:03d}{extension}"
                ruta = dir_destino / nombre
                
                if ruta.exists() and ruta.stat().st_size > 1024:
                    self.estadisticas['ya_existian'] += 1
                    continue
                
                exito, bytes_desc = self.descargar_imagen(url, ruta)
                
                if exito:
                    self.estadisticas['descargadas'] += 1
                    self.estadisticas['bytes_descargados'] += bytes_desc
                    self.estadisticas['imagenes_unicas'] += 1
                else:
                    self.estadisticas['fallidas'] += 1
                
                time.sleep(self.delay_entre_imagenes)
                
        except Exception as e:
            logger.error(f"Error procesando {sku}: {e}")
    
    def descargar_todas(self):
        """Descarga todas las imágenes con detección de variantes"""
        print(f"\n{'=' * 80}")
        print(f"🖼️  DESCARGA INTELIGENTE DE IMÁGENES")
        print(f"{'=' * 80}")
        print(f"\n📊 Resumen:")
        print(f"   Grupos de variantes: {len(self.grupos)}")
        print(f"   Productos individuales: {len(self.productos_individuales)}")
        print(f"   Total productos: {self.estadisticas['total_productos']}")
        print(f"\n{'─' * 80}\n")
        
        inicio = time.time()
        
        # Procesar grupos de variantes
        if self.grupos:
            print(f"📦 Procesando {len(self.grupos)} grupos de variantes...\n")
            for i, grupo in enumerate(self.grupos, 1):
                try:
                    self.procesar_grupo(grupo, i, len(self.grupos))
                except KeyboardInterrupt:
                    print("\n\n⚠️  Descarga interrumpida")
                    break
                except Exception as e:
                    logger.error(f"Error en grupo {grupo['id_grupo']}: {e}")
        
        # Procesar productos individuales
        if self.productos_individuales:
            print(f"\n📄 Procesando {len(self.productos_individuales)} productos individuales...\n")
            for i, sku in enumerate(self.productos_individuales, 1):
                try:
                    if i % 10 == 0:
                        print(f"  Progreso: {i}/{len(self.productos_individuales)} ({i/len(self.productos_individuales)*100:.1f}%)")
                    self.procesar_producto_individual(sku)
                except KeyboardInterrupt:
                    print("\n\n⚠️  Descarga interrumpida")
                    break
        
        tiempo_total = time.time() - inicio
        
        self.mostrar_resumen(tiempo_total)
        self.generar_reporte()
    
    def mostrar_resumen(self, tiempo_total: float):
        """Muestra resumen final"""
        mb_descargados = self.estadisticas['bytes_descargados'] / (1024 * 1024)
        
        print(f"\n{'=' * 80}")
        print("📊 RESUMEN DE DESCARGA")
        print(f"{'=' * 80}")
        print(f"\n📦 Grupos procesados: {self.estadisticas['total_grupos']}")
        print(f"📷 Imágenes únicas descargadas: {self.estadisticas['imagenes_unicas']}")
        print(f"♻️  Duplicados evitados: {self.estadisticas['imagenes_duplicadas_evitadas']}")
        print(f"\n   ✅ Descargadas: {self.estadisticas['descargadas']}")
        print(f"   ✓ Ya existían: {self.estadisticas['ya_existian']}")
        print(f"   ❌ Fallidas: {self.estadisticas['fallidas']}")
        print(f"\n💾 Datos descargados: {mb_descargados:.2f} MB")
        print(f"⏱️  Tiempo total: {tiempo_total / 60:.1f} minutos")
        print(f"{'=' * 80}")
    
    def generar_reporte(self):
        """Genera reporte JSON"""
        fecha = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
        reporte_file = Config.LOGS_DIR / f"reporte_imagenes_{fecha}.json"
        
        reporte = {
            'fecha': datetime.now().isoformat(),
            'estadisticas': self.estadisticas,
            'grupos_procesados': len(self.grupos),
            'productos_individuales': len(self.productos_individuales)
        }
        
        with open(reporte_file, 'w', encoding='utf-8') as f:
            json.dump(reporte, f, indent=2, ensure_ascii=False)
        
        print(f"\n📄 Reporte: {reporte_file}")


def main():
    """Ejecuta el descargador"""
    print("=" * 80)
    print("🖼️  DESCARGADOR INTELIGENTE DE IMÁGENES")
    print("=" * 80)
    
    # Buscar archivo de variantes
    archivos_variantes = sorted(
        Config.GRUPOS_VARIANTES_DIR.glob("variantes_*.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True
    )
    
    archivo_variantes = archivos_variantes[0] if archivos_variantes else None
    
    if archivo_variantes:
        print(f"\n✅ Archivo de variantes encontrado: {archivo_variantes.name}")
        print("   Se optimizarán descargas para grupos de variantes")
    else:
        print("\n⚠️  No se encontró archivo de variantes")
        print("   Se descargarán todos los productos individualmente")
    
    descargador = DescargadorImagenesConVariantes(archivo_variantes)
    descargador.cargar_variantes()
    
    print(f"\n{'─' * 80}")
    confirmar = input("\n¿Iniciar descarga? (s/n): ").lower()
    
    if confirmar == 's':
        descargador.descargar_todas()
    else:
        print("\nDescarga cancelada")


if __name__ == "__main__":
    main()
