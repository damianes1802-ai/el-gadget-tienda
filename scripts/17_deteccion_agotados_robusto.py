#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DETECCIÓN ROBUSTA DE AGOTADOS POR SKU
Usa el scraper de categorías para obtener SKUs disponibles en Droppers
y compara con la base de datos para detectar agotados/reingresados/nuevos

AUTOR: Sistema Ecommerce Automation
FECHA: 2026-02-22
VERSION: 1.0

WORKFLOW:
1. Scrapea todas las categorías de Droppers (rápido, solo SKUs)
2. Compara con base de datos local
3. Detecta agotados, reingresados, nuevos
4. Actualiza metadata.json con estado actualizado
5. Genera reporte con validaciones de seguridad
"""

import json
import time
from pathlib import Path
from typing import Set, Dict, List
from datetime import datetime
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
import os

import sys
sys.path.append(str(Path(__file__).parent))
from utils.logger import get_logger
from utils.config import Config

logger = get_logger('deteccion_agotados')
load_dotenv(Config.CONFIG_DIR / '.env')


class DetectorAgotadosRobusto:
    """Detecta productos agotados comparando SKUs de Droppers vs base local"""
    
    # CONFIGURACIÓN DE SEGURIDAD
    MIN_SKUS_DROPPERS = 100  # Mínimo esperado en Droppers
    MAX_PORCENTAJE_AGOTADOS = 0.50  # Máximo 50% agotados de golpe
    
    def __init__(self):
        self.session = requests.Session()
        self.base_url = "https://droppers.com.ar"
        
        # User agent
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        
        # Credenciales
        self.email = os.getenv('DROPPERS_EMAIL') or os.getenv('DROPPERS_USER')
        self.password = os.getenv('DROPPERS_PASSWORD') or os.getenv('DROPPERS_PASS')
        
        if not self.email or not self.password:
            raise ValueError("❌ Faltan credenciales de Droppers en .env")
        
        # Conjuntos de SKUs
        self.skus_droppers = set()  # SKUs disponibles en Droppers
        self.skus_base_datos = set()  # SKUs en nuestra base
        self.skus_anteriormente_agotados = set()  # SKUs marcados como agotados
        
        # Resultados
        self.agotados = set()
        self.reingresados = set()
        self.nuevos = set()
        
        # Estadísticas
        self.stats = {
            'total_skus_droppers': 0,
            'total_skus_base': 0,
            'nuevos_agotados': 0,
            'reingresados': 0,
            'nuevos_productos': 0,
            'errores': [],
            'advertencias': []
        }
    
    def login(self) -> bool:
        """Login en Droppers"""
        print("🔐 Login en Droppers...")
        
        try:
            # Obtener form_key
            resp = self.session.get(f"{self.base_url}/customer/account/login/", timeout=30)
            soup = BeautifulSoup(resp.content, 'html.parser')
            form_key_input = soup.find('input', {'name': 'form_key'})
            
            if not form_key_input:
                return False
            
            form_key = form_key_input.get('value')
            
            # Login
            resp = self.session.post(f"{self.base_url}/customer/account/loginPost/", data={
                'form_key': form_key,
                'login[username]': self.email,
                'login[password]': self.password
            }, timeout=30, allow_redirects=True)
            
            if any(x in resp.text for x in ['Mi cuenta', 'customer/account']):
                print("✅ Login exitoso\n")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error en login: {e}")
            return False
    
    def obtener_skus_de_categoria(self, url_cat: str) -> Set[str]:
        """Scrapea SKUs de una categoría (todas las páginas)"""
        skus = set()
        pagina = 1
        max_paginas = 20  # Límite de seguridad
        
        while pagina <= max_paginas:
            try:
                # URL con paginación
                if pagina == 1:
                    url = url_cat
                else:
                    separator = '&' if '?' in url_cat else '?'
                    url = f"{url_cat}{separator}p={pagina}"
                
                resp = self.session.get(url, timeout=30)
                if resp.status_code != 200:
                    break
                
                soup = BeautifulSoup(resp.content, 'html.parser')
                
                # Obtener enlaces a productos
                enlaces = soup.select('a.product-item-link') or soup.select('a.product-photo')
                
                if not enlaces:
                    # No hay más productos
                    break
                
                productos_en_pagina = 0
                
                # Extraer SKU de cada producto
                for enlace in enlaces:
                    url_prod = enlace.get('href')
                    if url_prod:
                        # Extraer SKU de la página del producto
                        sku = self.extraer_sku_rapido(url_prod)
                        if sku:
                            skus.add(sku)
                            productos_en_pagina += 1
                        time.sleep(0.1)  # Rate limiting
                
                if productos_en_pagina == 0:
                    break
                
                # Verificar si hay siguiente página
                siguiente = soup.find('a', class_='next') or soup.find('a', title='Siguiente')
                if not siguiente:
                    break
                
                pagina += 1
                time.sleep(0.5)  # Pausa entre páginas
                
            except Exception as e:
                logger.error(f"Error en página {pagina} de categoría: {e}")
                break
        
        return skus
    
    def extraer_sku_rapido(self, url_producto: str) -> str:
        """Extrae SKU de un producto (versión rápida)"""
        try:
            resp = self.session.get(url_producto, timeout=15)
            soup = BeautifulSoup(resp.content, 'html.parser')
            
            # Método 1: div.product.attribute.sku .value
            sku_elem = soup.select_one('div.product.attribute.sku .value')
            if sku_elem:
                return sku_elem.text.strip()
            
            # Método 2: meta sku
            meta = soup.find('meta', {'itemprop': 'sku'})
            if meta:
                return meta.get('content', '').strip()
            
            return None
        except:
            return None
    
    def scrapear_todos_los_skus_droppers(self):
        """Scrapea TODOS los SKUs disponibles en Droppers"""
        
        print("🔍 Scrapeando SKUs disponibles en Droppers...\n")
        
        # Cargar configuración de categorías
        config_file = Config.CONFIG_DIR / 'categorias_droppers.json'
        
        if not config_file.exists():
            raise FileNotFoundError(f"No existe: {config_file}")
        
        with open(config_file, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        categorias = config.get('categorias', {})
        
        total_categorias = len(categorias)
        print(f"📋 {total_categorias} categorías configuradas\n")
        
        # Scrapear cada categoría
        for idx, (nombre, datos) in enumerate(categorias.items(), 1):
            print(f"[{idx}/{total_categorias}] {nombre}...")
            
            skus_cat = self.obtener_skus_de_categoria(datos['url'])
            self.skus_droppers.update(skus_cat)
            
            print(f"               ✅ {len(skus_cat)} SKUs totales\n")
            
            time.sleep(0.5)  # Rate limiting entre categorías
        
        self.stats['total_skus_droppers'] = len(self.skus_droppers)
        
        print(f"\n✅ Total SKUs en Droppers: {len(self.skus_droppers)}\n")
    
    def cargar_skus_base_datos(self):
        """Carga SKUs de nuestra base de datos"""
        
        print("📦 Cargando SKUs de base de datos local...\n")
        
        productos_dir = Config.PRODUCTOS_DIR
        
        for carpeta in productos_dir.iterdir():
            if not carpeta.is_dir():
                continue
            
            metadata_file = carpeta / 'metadata.json'
            
            if not metadata_file.exists():
                continue
            
            try:
                with open(metadata_file, 'r', encoding='utf-8') as f:
                    metadata = json.load(f)
                
                sku = metadata.get('sku', carpeta.name)
                self.skus_base_datos.add(sku)
                
                # Guardar si estaba marcado como agotado
                if metadata.get('disponibilidad') == 'out of stock':
                    self.skus_anteriormente_agotados.add(sku)
                
            except Exception as e:
                logger.error(f"Error leyendo {carpeta}: {e}")
        
        self.stats['total_skus_base'] = len(self.skus_base_datos)
        
        print(f"✅ SKUs en base de datos: {len(self.skus_base_datos)}")
        print(f"⚠️  Anteriormente agotados: {len(self.skus_anteriormente_agotados)}\n")
    
    def validar_datos(self) -> bool:
        """Validaciones de seguridad antes de procesar"""
        
        print("🔒 Ejecutando validaciones de seguridad...\n")
        
        errores = []
        advertencias = []
        
        # VALIDACIÓN 1: Mínimo de SKUs en Droppers
        if len(self.skus_droppers) < self.MIN_SKUS_DROPPERS:
            errores.append(
                f"❌ Solo se encontraron {len(self.skus_droppers)} SKUs en Droppers. "
                f"Mínimo esperado: {self.MIN_SKUS_DROPPERS}. "
                "Droppers puede tener problemas o el scraping falló."
            )
        
        # VALIDACIÓN 2: SKUs en base de datos
        if len(self.skus_base_datos) == 0:
            errores.append("❌ No se encontraron SKUs en la base de datos local.")
        
        # VALIDACIÓN 3: Detectar agotados preliminares
        agotados_preliminar = self.skus_base_datos - self.skus_droppers
        porcentaje_agotados = len(agotados_preliminar) / len(self.skus_base_datos) if self.skus_base_datos else 0
        
        if porcentaje_agotados > self.MAX_PORCENTAJE_AGOTADOS:
            errores.append(
                f"❌ {len(agotados_preliminar)} productos ({porcentaje_agotados*100:.1f}%) "
                f"aparecerían como agotados. Máximo permitido: {self.MAX_PORCENTAJE_AGOTADOS*100}%. "
                "Esto sugiere un problema en el scraping."
            )
        
        # VALIDACIÓN 4: Diferencia razonable
        diferencia = abs(len(self.skus_droppers) - len(self.skus_base_datos))
        if diferencia > 100:
            advertencias.append(
                f"⚠️  Gran diferencia entre Droppers ({len(self.skus_droppers)}) "
                f"y base de datos ({len(self.skus_base_datos)}). "
                "Revisar que las categorías estén completas."
            )
        
        # Guardar errores y advertencias
        self.stats['errores'] = errores
        self.stats['advertencias'] = advertencias
        
        # Mostrar resultados
        if errores:
            print("🚨 ERRORES CRÍTICOS:")
            for error in errores:
                print(f"   {error}")
            print()
            return False
        
        if advertencias:
            print("⚠️  ADVERTENCIAS:")
            for adv in advertencias:
                print(f"   {adv}")
            print()
        
        print("✅ Validaciones pasadas\n")
        return True
    
    def detectar_cambios(self):
        """Detecta agotados, reingresados y nuevos"""
        
        print("🔄 Detectando cambios...\n")
        
        # AGOTADOS: En tu base PERO NO en Droppers
        self.agotados = self.skus_base_datos - self.skus_droppers
        
        # REINGRESADOS: Antes agotados PERO AHORA sí en Droppers
        self.reingresados = self.skus_anteriormente_agotados & self.skus_droppers
        
        # NUEVOS: En Droppers PERO NO en tu base
        self.nuevos = self.skus_droppers - self.skus_base_datos
        
        # Estadísticas
        self.stats['nuevos_agotados'] = len(self.agotados)
        self.stats['reingresados'] = len(self.reingresados)
        self.stats['nuevos_productos'] = len(self.nuevos)
        
        # Mostrar resumen
        print("📊 CAMBIOS DETECTADOS:")
        print(f"   🔴 Nuevos agotados: {len(self.agotados)}")
        print(f"   🟢 Reingresados: {len(self.reingresados)}")
        print(f"   🆕 Productos nuevos en Droppers: {len(self.nuevos)}")
        print()
    
    def actualizar_metadata(self):
        """Actualiza metadata.json con los estados"""
        
        print("📝 Actualizando metadata...\n")
        
        productos_dir = Config.PRODUCTOS_DIR
        actualizados = 0
        
        # Actualizar TODOS los productos que están en Droppers como disponibles
        print("  Marcando productos disponibles...")
        for sku in self.skus_droppers:
            carpeta = productos_dir / sku
            metadata_file = carpeta / 'metadata.json'
            
            if not metadata_file.exists():
                continue
            
            try:
                with open(metadata_file, 'r', encoding='utf-8') as f:
                    metadata = json.load(f)
                
                # Solo actualizar si no tiene el campo o estaba agotado
                disponibilidad_actual = metadata.get('disponibilidad', '')
                if disponibilidad_actual != 'in stock':
                    metadata['disponibilidad'] = 'in stock'
                    metadata['availability'] = 'in stock'
                    
                    # Si era reingreso, agregar fecha
                    if sku in self.reingresados:
                        metadata['fecha_reingreso'] = datetime.now().isoformat()
                        if 'fecha_agotado' in metadata:
                            del metadata['fecha_agotado']
                    
                    with open(metadata_file, 'w', encoding='utf-8') as f:
                        json.dump(metadata, f, indent=2, ensure_ascii=False)
                    
                    actualizados += 1
                
            except Exception as e:
                logger.error(f"Error actualizando {sku}: {e}")
        
        # Actualizar agotados
        print("  Marcando productos agotados...")
        for sku in self.agotados:
            carpeta = productos_dir / sku
            metadata_file = carpeta / 'metadata.json'
            
            if not metadata_file.exists():
                continue
            
            try:
                with open(metadata_file, 'r', encoding='utf-8') as f:
                    metadata = json.load(f)
                
                metadata['disponibilidad'] = 'out of stock'
                metadata['fecha_agotado'] = datetime.now().isoformat()
                metadata['availability'] = 'out of stock'
                
                with open(metadata_file, 'w', encoding='utf-8') as f:
                    json.dump(metadata, f, indent=2, ensure_ascii=False)
                
                actualizados += 1
                
            except Exception as e:
                logger.error(f"Error actualizando {sku}: {e}")
        
        print(f"\n✅ Total: {actualizados} archivos metadata actualizados\n")
    
    def generar_reporte(self):
        """Genera reporte detallado"""
        
        reporte = {
            'fecha_ejecucion': datetime.now().isoformat(),
            'estadisticas': self.stats,
            'agotados': {
                'total': len(self.agotados),
                'skus': sorted(list(self.agotados))
            },
            'reingresados': {
                'total': len(self.reingresados),
                'skus': sorted(list(self.reingresados))
            },
            'nuevos': {
                'total': len(self.nuevos),
                'skus': sorted(list(self.nuevos))
            }
        }
        
        # Guardar reporte
        reporte_file = Config.DATA_DIR / f'reporte_agotados_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
        
        with open(reporte_file, 'w', encoding='utf-8') as f:
            json.dump(reporte, f, indent=2, ensure_ascii=False)
        
        print(f"📄 Reporte guardado: {reporte_file}\n")
        
        return reporte
    
    def mostrar_resumen_detallado(self):
        """Muestra resumen en consola"""
        
        print("="*60)
        print("📊 RESUMEN FINAL")
        print("="*60)
        print(f"SKUs en Droppers: {self.stats['total_skus_droppers']}")
        print(f"SKUs en base local: {self.stats['total_skus_base']}")
        print()
        print(f"🔴 Nuevos agotados: {self.stats['nuevos_agotados']}")
        if self.agotados:
            print("   SKUs:", ', '.join(sorted(list(self.agotados))[:10]))
            if len(self.agotados) > 10:
                print(f"   ... y {len(self.agotados)-10} más")
        print()
        print(f"🟢 Reingresados: {self.stats['reingresados']}")
        if self.reingresados:
            print("   SKUs:", ', '.join(sorted(list(self.reingresados))))
        print()
        print(f"🆕 Productos nuevos: {self.stats['nuevos_productos']}")
        if self.nuevos:
            print("   SKUs:", ', '.join(sorted(list(self.nuevos))[:10]))
            if len(self.nuevos) > 10:
                print(f"   ... y {len(self.nuevos)-10} más")
        print("="*60 + "\n")
        
        print("💡 PRÓXIMOS PASOS:")
        if self.agotados:
            print("   1. Ejecutá: python 11_sincronizar_sqlite.py")
            print("   2. Para actualizar base de datos con agotados")
        if self.nuevos:
            print("   3. Ejecutá: python 01_scraper.py")
            print("   4. Para scrapear productos nuevos")
        print()
    
    def ejecutar(self):
        """Ejecuta el proceso completo"""
        
        print("\n" + "="*60)
        print("🔍 DETECCIÓN ROBUSTA DE AGOTADOS")
        print("="*60 + "\n")
        
        # 1. Login
        if not self.login():
            print("❌ Login fallido\n")
            return
        
        # 2. Scrapear SKUs de Droppers
        self.scrapear_todos_los_skus_droppers()
        
        # 3. Cargar SKUs de base de datos
        self.cargar_skus_base_datos()
        
        # 4. Validar datos
        if not self.validar_datos():
            print("\n⛔ PROCESO ABORTADO POR ERRORES DE VALIDACIÓN\n")
            print("   Revisar los errores y ejecutar de nuevo.\n")
            return
        
        # 5. Detectar cambios
        self.detectar_cambios()
        
        # 6. Preguntar confirmación si hay agotados
        if self.agotados:
            print(f"⚠️  Se marcarán {len(self.agotados)} productos como AGOTADOS.")
            respuesta = input("¿Continuar? (s/n): ")
            if respuesta.strip().lower() != 's':
                print("\n⛔ Proceso cancelado por el usuario\n")
                return
            print()
        
        # 7. Actualizar metadata
        self.actualizar_metadata()
        
        # 8. Generar reporte
        self.generar_reporte()
        
        # 9. Mostrar resumen
        self.mostrar_resumen_detallado()


if __name__ == "__main__":
    try:
        detector = DetectorAgotadosRobusto()
        detector.ejecutar()
    except KeyboardInterrupt:
        print("\n\n⚠️  Proceso interrumpido\n")
    except Exception as e:
        logger.error(f"Error fatal: {e}")
        print(f"\n❌ Error fatal: {e}\n")
