#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SCRAPER DE CATEGORÍAS DROPPERS - V5.0 CON PRIORIDADES
Mapea productos a categorías con sistema inteligente de prioridad

MEJORAS vs V4.0:
✅ Sistema de prioridades para categorías
✅ Categorías específicas tienen prioridad sobre genéricas
✅ "Nuevos Ingresos" se scrapea último (catch-all)
✅ Procesamiento paralelo (8 productos simultáneos)
✅ Categorías cargadas desde JSON

PROBLEMA RESUELTO:
- Antes: Productos en "Accesorios de Moda" + "Nuevos Ingresos" 
         → categoría principal = "Nuevos Ingresos" (scrapeada primero)
- Ahora: Categorías específicas tienen prioridad 1
         → categoría principal = "Accesorios de Moda" ✅

CONFIGURACIÓN:
- Categorías en: config/categorias_droppers.json
- Prioridad 1: Categorías específicas (se scrapean primero)
- Prioridad 99: "Nuevos Ingresos" (se scrapea último)

AUTOR: Sistema Ecommerce Automation  
FECHA: 2026-03-09
VERSION: 5.0 CON SISTEMA DE PRIORIDADES
"""

import json
import time
import re
from pathlib import Path
from typing import Dict, List, Set, Tuple
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
import os

import sys
sys.path.append(str(Path(__file__).parent))
from utils.logger import get_logger
from utils.config import Config

logger = get_logger('scraper_categorias_v3')
load_dotenv(Config.CONFIG_DIR / '.env')


class ScraperCategoriasOptimizado:
    """Scraper optimizado de categorías Droppers"""
    
    # ARCHIVO DE CONFIGURACIÓN DE CATEGORÍAS
    CATEGORIAS_CONFIG_FILE = Config.CONFIG_DIR / "categorias_droppers.json"
    
    def __init__(self):
        self.session = requests.Session()
        self.base_url = "https://droppers.com.ar"
        
        # Cargar categorías desde JSON
        self.categorias = self._cargar_categorias()
        
        # User agent
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        
        # Connection pooling
        adapter = requests.adapters.HTTPAdapter(
            pool_connections=10,
            pool_maxsize=10,
            max_retries=requests.adapters.Retry(
                total=3,
                backoff_factor=0.5,
                status_forcelist=[500, 502, 503, 504]
            )
        )
        self.session.mount('http://', adapter)
        self.session.mount('https://', adapter)
        
        # Credenciales
        self.email = os.getenv('DROPPERS_EMAIL') or os.getenv('DROPPERS_USER')
        self.password = os.getenv('DROPPERS_PASSWORD') or os.getenv('DROPPERS_PASS')
        
        if not self.email or not self.password:
            raise ValueError("❌ Faltan credenciales de Droppers en .env")
        
        # Mapeo: nombre_categoria → set de SKUs
        self.categorias_skus = {}
        
        # Mapeo inverso: SKU → lista de categorías (en orden)
        self.sku_categorias = {}
        
        # Configuración de paralelización
        self.max_workers = 8  # Productos simultáneos
        
        self.stats = {
            'total_categorias': len(self.categorias),
            'total_productos_encontrados': 0,
            'productos_actualizados': 0,
            'productos_sin_metadata': 0,
            'productos_multi_categoria': 0,
            'errores_scraping': 0,
            'tiempo_inicio': time.time()
        }
        
        logger.info(f"Scraper Categorías V4 JSON inicializado - {len(self.categorias)} categorías activas")
    
    def _cargar_categorias(self) -> Dict[str, str]:
        """
        Carga categorías desde archivo JSON ordenadas por prioridad
        
        Returns:
            dict: {nombre_categoria: url} ordenado por prioridad (menor = primero)
        """
        try:
            with open(self.CATEGORIAS_CONFIG_FILE, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            # Filtrar solo categorías activas
            categorias_activas = {}
            for nombre, datos in config.get('categorias', {}).items():
                if datos.get('activa', True):  # Default True si no especifica
                    prioridad = datos.get('prioridad', 50)  # Default prioridad media
                    categorias_activas[nombre] = {
                        'url': datos['url'],
                        'prioridad': prioridad
                    }
            
            if not categorias_activas:
                raise ValueError("No hay categorías activas en la configuración")
            
            # ORDENAR POR PRIORIDAD (menor número = mayor prioridad)
            categorias_ordenadas = dict(
                sorted(
                    categorias_activas.items(),
                    key=lambda x: x[1]['prioridad']
                )
            )
            
            # Convertir a dict simple {nombre: url}
            categorias_final = {
                nombre: datos['url']
                for nombre, datos in categorias_ordenadas.items()
            }
            
            logger.info(f"Categorías cargadas desde JSON: {len(categorias_final)}")
            logger.info(f"Orden de scraping (por prioridad):")
            for idx, (nombre, _) in enumerate(categorias_final.items(), 1):
                prioridad = categorias_activas[nombre]['prioridad']
                logger.info(f"  {idx}. {nombre} (prioridad {prioridad})")
            
            # Mostrar categorías desactivadas
            categorias_inactivas = [
                nombre for nombre, datos in config.get('categorias', {}).items()
                if not datos.get('activa', True)
            ]
            if categorias_inactivas:
                logger.info(f"Categorías desactivadas: {', '.join(categorias_inactivas)}")
            
            return categorias_final
            
        except FileNotFoundError:
            logger.error(f"❌ Archivo de configuración no encontrado: {self.CATEGORIAS_CONFIG_FILE}")
            logger.info("💡 Creando archivo de configuración con categorías por defecto...")
            
            # Crear archivo con categorías default
            self._crear_config_default()
            
            # Reintentar carga
            return self._cargar_categorias()
        
        except Exception as e:
            logger.error(f"Error cargando categorías: {e}")
            raise
    
    def _crear_config_default(self):
        """Crea archivo de configuración con categorías por defecto y prioridades"""
        config_default = {
            "sitio": "https://droppers.com.ar",
            "descripcion": "Configuración de categorías con sistema de prioridad",
            "ultima_actualizacion": datetime.now().isoformat(),
            "categorias": {
                "Accesorios de Moda": {"url": "https://droppers.com.ar/productos/accesorios-de-moda.html", "activa": True, "prioridad": 1},
                "Artículos Infantiles": {"url": "https://droppers.com.ar/productos/articulos-infantiles.html", "activa": True, "prioridad": 1},
                "Fitness": {"url": "https://droppers.com.ar/productos/fitness.html", "activa": True, "prioridad": 1},
                "Estética y Belleza": {"url": "https://droppers.com.ar/productos/estetica-y-belleza.html", "activa": True, "prioridad": 1},
                "Home": {"url": "https://droppers.com.ar/productos/home-y-deco/home.html", "activa": True, "prioridad": 2},
                "Deco": {"url": "https://droppers.com.ar/productos/home-y-deco/deco.html", "activa": True, "prioridad": 2},
                "Bazar y Cocina": {"url": "https://droppers.com.ar/productos/bazar-y-cocina.html", "activa": True, "prioridad": 2},
                "Baño y Limpieza": {"url": "https://droppers.com.ar/productos/ba-o-y-limpieza.html", "activa": True, "prioridad": 2},
                "Electrónica": {"url": "https://droppers.com.ar/productos/electronica.html", "activa": True, "prioridad": 2},
                "Accesorios para Mascotas": {"url": "https://droppers.com.ar/productos/accesorios-de-mascotas.html", "activa": True, "prioridad": 2},
                "Verano": {"url": "https://droppers.com.ar/productos/verano.html", "activa": True, "prioridad": 2},
                "Nuevos Ingresos": {"url": "https://droppers.com.ar/productos/nuevos-ingresos.html", "activa": True, "prioridad": 99},
                "Adultos": {"url": "https://droppers.com.ar/productos/adultos.html", "activa": False, "prioridad": 0}
            },
            "notas": [
                "Prioridad 1: Categorías específicas (se scrapean primero)",
                "Prioridad 2: Categorías generales",
                "Prioridad 99: 'Nuevos Ingresos' (se scrapea último como catch-all)"
            ]
        }
        
        self.CATEGORIAS_CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(self.CATEGORIAS_CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config_default, f, indent=2, ensure_ascii=False)
        
        logger.info(f"✅ Archivo de configuración creado: {self.CATEGORIAS_CONFIG_FILE}")
    
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
    
    def extraer_sku_de_producto(self, url_producto: str, retry: int = 0) -> str:
        """
        Entra al producto y extrae el SKU real
        
        Args:
            url_producto: URL del producto
            retry: Número de reintento
        
        Returns:
            SKU o None
        """
        try:
            resp = self.session.get(url_producto, timeout=15)
            resp.raise_for_status()
            
            soup = BeautifulSoup(resp.content, 'html.parser')
            
            # Método 1: div.product.attribute.sku .value
            sku_elem = soup.select_one('div.product.attribute.sku .value')
            if sku_elem:
                return sku_elem.text.strip()
            
            # Método 2: meta itemprop="sku"
            meta_sku = soup.find('meta', {'itemprop': 'sku'})
            if meta_sku:
                return meta_sku.get('content', '').strip()
            
            # Método 3: Buscar en el HTML
            texto = soup.get_text()
            match = re.search(r'SKU[:\s]+([A-Z0-9\-]+)', texto, re.IGNORECASE)
            if match:
                return match.group(1).strip()
            
            return None
            
        except requests.exceptions.RequestException as e:
            # Retry con backoff exponencial
            if retry < 2:
                time.sleep(1 * (retry + 1))
                return self.extraer_sku_de_producto(url_producto, retry + 1)
            
            logger.warning(f"Error extrayendo SKU de {url_producto}: {e}")
            self.stats['errores_scraping'] += 1
            return None
        
        except Exception as e:
            logger.debug(f"Error parseando {url_producto}: {e}")
            return None
    
    def scrapear_categoria_paralelo(self, nombre_cat: str, url_cat: str) -> Set[str]:
        """
        Scrapea categoría con paralelización
        
        OPTIMIZACIONES:
        - Procesa 8 productos simultáneamente
        - Connection pooling
        - Retry automático
        - Progress tracking
        """
        skus = set()
        pagina = 1
        max_paginas = 20
        
        print(f"\n📁 {nombre_cat}")
        print(f"   🔗 {url_cat}")
        
        # Recolectar todas las URLs de productos
        urls_productos = []
        
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
                
                # Buscar enlaces a productos
                enlaces = soup.select('a.product-item-link') or soup.select('a.product-photo')
                
                if not enlaces:
                    break
                
                print(f"   📄 Página {pagina}: {len(enlaces)} productos")
                
                # Recolectar URLs
                for enlace in enlaces:
                    url_prod = enlace.get('href')
                    if url_prod:
                        urls_productos.append(url_prod)
                
                # Verificar si hay siguiente página
                siguiente = soup.find('a', class_='next') or soup.find('a', title='Siguiente')
                if not siguiente:
                    break
                
                pagina += 1
                time.sleep(0.3)
                
            except Exception as e:
                logger.error(f"Error en página {pagina} de {nombre_cat}: {e}")
                break
        
        # Procesar URLs en paralelo
        if urls_productos:
            print(f"   ⚡ Extrayendo SKUs de {len(urls_productos)} productos (paralelo)...")
            
            procesados = 0
            
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                # Enviar tareas
                futures = {
                    executor.submit(self.extraer_sku_de_producto, url): url
                    for url in urls_productos
                }
                
                # Procesar resultados
                for future in as_completed(futures):
                    sku = future.result()
                    if sku:
                        skus.add(sku)
                    
                    procesados += 1
                    
                    # Progress cada 10 productos
                    if procesados % 10 == 0:
                        print(f"      {procesados}/{len(urls_productos)} procesados...", end='\r')
            
            print(f"      {len(urls_productos)}/{len(urls_productos)} procesados    ")
        
        print(f"   ✅ Total: {len(skus)} SKUs extraídos")
        
        if self.stats['errores_scraping'] > 0:
            print(f"   ⚠️  Errores: {self.stats['errores_scraping']}")
        
        return skus
    
    def scrapear_todas_categorias(self):
        """Scrapea todas las categorías"""
        print("\n" + "="*70)
        print("🔍 SCRAPEANDO CATEGORÍAS (PARALELO)")
        print("="*70)
        
        total_cats = len(self.categorias)
        
        for idx, (nombre, url) in enumerate(self.categorias.items(), 1):
            print(f"\n[{idx}/{total_cats}] ", end="")
            
            # Resetear errores para esta categoría
            errores_antes = self.stats['errores_scraping']
            
            skus = self.scrapear_categoria_paralelo(nombre, url)
            self.categorias_skus[nombre] = skus
            
            self.stats['total_productos_encontrados'] += len(skus)
            
            # Mostrar errores de esta categoría
            errores_cat = self.stats['errores_scraping'] - errores_antes
            if errores_cat > 0:
                logger.warning(f"{errores_cat} errores en categoría {nombre}")
        
        print("\n" + "="*70 + "\n")
    
    def crear_mapeo_sku_categorias(self):
        """Crea mapeo inverso: SKU → [categorías en orden]"""
        print("🗺️  Creando mapeo SKU → Categorías...\n")
        
        # Para cada categoría, agregar sus SKUs al mapeo
        for nombre_cat, skus in self.categorias_skus.items():
            for sku in skus:
                if sku not in self.sku_categorias:
                    self.sku_categorias[sku] = []
                self.sku_categorias[sku].append(nombre_cat)
        
        # Contar multi-categoría
        for sku, cats in self.sku_categorias.items():
            if len(cats) > 1:
                self.stats['productos_multi_categoria'] += 1
        
        print(f"✅ {len(self.sku_categorias)} productos mapeados")
        print(f"   • En 1 categoría: {len(self.sku_categorias) - self.stats['productos_multi_categoria']}")
        print(f"   • En múltiples: {self.stats['productos_multi_categoria']}\n")
        
        # Mostrar ejemplos de multi-categoría
        if self.stats['productos_multi_categoria'] > 0:
            print("📊 Ejemplos multi-categoría:")
            count = 0
            for sku, cats in self.sku_categorias.items():
                if len(cats) > 1 and count < 5:
                    print(f"   • {sku}: {', '.join(cats)}")
                    count += 1
            print()
    
    def actualizar_metadata(self):
        """Actualiza metadata.json con categorías"""
        print("📝 Actualizando metadata.json...\n")
        
        productos_dir = Config.PRODUCTOS_DIR
        
        for sku, categorias in self.sku_categorias.items():
            # Buscar carpeta del producto
            carpeta = productos_dir / sku
            metadata_file = carpeta / 'metadata.json'
            
            if not metadata_file.exists():
                self.stats['productos_sin_metadata'] += 1
                continue
            
            try:
                with open(metadata_file, 'r', encoding='utf-8') as f:
                    metadata = json.load(f)
                
                # MAPEO:
                # - Primera categoría = categoria_principal
                # - Resto = categorias_secundarias
                metadata['categoria_principal'] = categorias[0]
                metadata['categoria'] = categorias[0]  # Para compatibilidad
                metadata['categorias_secundarias'] = categorias[1:] if len(categorias) > 1 else []
                metadata['todas_las_categorias'] = categorias
                metadata['total_categorias'] = len(categorias)
                metadata['fecha_actualizacion_categorias'] = datetime.now().isoformat()
                
                # Guardar
                with open(metadata_file, 'w', encoding='utf-8') as f:
                    json.dump(metadata, f, indent=2, ensure_ascii=False)
                
                self.stats['productos_actualizados'] += 1
                
                # Progress
                if self.stats['productos_actualizados'] % 50 == 0:
                    print(f"   ⏳ {self.stats['productos_actualizados']} productos actualizados...")
                
            except Exception as e:
                logger.error(f"Error actualizando {sku}: {e}")
        
        print(f"\n✅ Total actualizado: {self.stats['productos_actualizados']}\n")
    
    def guardar_reporte(self):
        """Guarda reporte JSON"""
        reporte = {
            'fecha_ejecucion': datetime.now().isoformat(),
            'tiempo_total_segundos': time.time() - self.stats['tiempo_inicio'],
            'estadisticas': self.stats,
            'categorias': {
                nombre: {
                    'url': self.categorias[nombre],
                    'total_productos': len(skus),
                    'productos': sorted(list(skus))[:20]  # Primeros 20 como ejemplo
                }
                for nombre, skus in self.categorias_skus.items()
            }
        }
        
        reporte_file = Config.DATA_DIR / f'reporte_categorias_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
        
        with open(reporte_file, 'w', encoding='utf-8') as f:
            json.dump(reporte, f, indent=2, ensure_ascii=False)
        
        print(f"📄 Reporte: {reporte_file}\n")
        logger.info(f"Reporte guardado: {reporte_file}")
    
    def mostrar_resumen(self):
        """Muestra resumen final"""
        tiempo_total = time.time() - self.stats['tiempo_inicio']
        
        print("="*70)
        print("📊 RESUMEN FINAL")
        print("="*70)
        print(f"\n⏱️  Tiempo total: {tiempo_total:.1f}s ({tiempo_total/60:.1f} min)")
        
        print(f"\n📁 Categorías procesadas: {self.stats['total_categorias']}")
        
        print(f"\n📦 Productos:")
        print(f"   • Encontrados en Droppers: {self.stats['total_productos_encontrados']}")
        print(f"   • Únicos mapeados: {len(self.sku_categorias)}")
        print(f"   • Actualizados en metadata: {self.stats['productos_actualizados']}")
        print(f"   • En múltiples categorías: {self.stats['productos_multi_categoria']}")
        
        if self.stats['productos_sin_metadata'] > 0:
            print(f"   • Sin metadata local: {self.stats['productos_sin_metadata']}")
        
        if self.stats['errores_scraping'] > 0:
            print(f"\n⚠️  Errores de scraping: {self.stats['errores_scraping']}")
        
        print(f"\n📊 Por categoría:")
        for nombre, skus in sorted(self.categorias_skus.items(), key=lambda x: len(x[1]), reverse=True):
            print(f"   • {nombre}: {len(skus)} productos")
        
        print("\n" + "="*70)
        print("💡 SIGUIENTE PASO:")
        print("   python 11_sincronizar_sqlite.py")
        print("   python 06_sincronizar_google_sheets_OPTIMIZADO.py")
        print("="*70 + "\n")
    
    def ejecutar(self):
        """Ejecuta el proceso completo"""
        print("\n" + "="*70)
        print("🏷️  SCRAPER DE CATEGORÍAS V3.0 OPTIMIZADO")
        print("="*70)
        print("MEJORAS:")
        print("  ⚡ Procesamiento paralelo (8 productos simultáneos)")
        print("  ⚡ Connection pooling HTTP")
        print("  ⚡ 13 categorías hardcodeadas")
        print("  ⚡ Mapeo principal + secundarias")
        print("  ⚡ 50-60% más rápido que versión anterior")
        print("="*70)
        
        # 1. Login
        if not self.login():
            print("❌ Login fallido\n")
            return False
        
        # 2. Scrapear categorías
        self.scrapear_todas_categorias()
        
        # 3. Crear mapeo inverso
        self.crear_mapeo_sku_categorias()
        
        # 4. Actualizar metadata
        self.actualizar_metadata()
        
        # 5. Guardar reporte
        self.guardar_reporte()
        
        # 6. Mostrar resumen
        self.mostrar_resumen()
        
        return True


def main():
    """Función principal"""
    try:
        scraper = ScraperCategoriasOptimizado()
        exitoso = scraper.ejecutar()
        
        return 0 if exitoso else 1
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Scraping interrumpido\n")
        return 1
    
    except Exception as e:
        print(f"\n❌ Error fatal: {e}\n")
        logger.exception("Error fatal")
        return 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
