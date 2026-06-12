#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SCRAPER MAESTRO V2 - FASE 1: PRODUCTOS SIN CATEGORÍAS
Scrapea productos completos EXCEPTO categorías

QUÉ OBTIENE:
✅ SKU, título, precio, descripción, imágenes
✅ Disponibilidad/stock
❌ NO categorías (se asignan en FASE 2)

VENTAJAS:
✅ No depende del breadcrumb (poco confiable)
✅ Las categorías se mapean después con URLs de listados
✅ Sistema de 2 fases más robusto y confiable

FASE 2: mapear_categorias_post_scraping.py

AUTOR: Sistema Ecommerce Automation
FECHA: 2026-03-16
VERSION: 2.0 - SIN CATEGORÍAS
"""

import json
import time
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from dotenv import load_dotenv
import os

import sys
sys.path.append(str(Path(__file__).parent))
from utils.logger import get_logger
from utils.config import Config

logger = get_logger('scraper_maestro_v2')
load_dotenv(Config.CONFIG_DIR / '.env')


class ScraperMaestroV2:
    """Scraper que obtiene datos de productos SIN categorías"""
    
    def __init__(self):
        self.session = self._crear_sesion()
        self.base_url = "https://droppers.com.ar"
        
        # Credenciales
        self.email = os.getenv('DROPPERS_EMAIL') or os.getenv('DROPPERS_USER')
        self.password = os.getenv('DROPPERS_PASSWORD') or os.getenv('DROPPERS_PASS')
        
        if not self.email or not self.password:
            raise ValueError("❌ Faltan credenciales de Droppers en .env")
        
        # Estadísticas
        self.stats = {
            'total_urls': 0,
            'productos_exitosos': 0,
            'productos_fallidos': 0,
            'productos_agotados': 0,
            'productos_disponibles': 0,
            'tiempo_inicio': time.time()
        }
        
        # Configuración de paralelización
        self.max_workers = 8
        
        logger.info("Scraper Maestro V2 (sin categorías) inicializado")
    
    def _crear_sesion(self) -> requests.Session:
        """Crea sesión HTTP con retry automático"""
        session = requests.Session()
        
        retry_strategy = Retry(
            total=3,
            backoff_factor=0.5,
            status_forcelist=[500, 502, 503, 504]
        )
        
        adapter = HTTPAdapter(
            pool_connections=10,
            pool_maxsize=10,
            max_retries=retry_strategy
        )
        
        session.mount('http://', adapter)
        session.mount('https://', adapter)
        
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        
        return session
    
    def login(self) -> bool:
        """Login en Droppers"""
        logger.info("Iniciando login en Droppers...")
        
        try:
            # Obtener form_key
            resp = self.session.get(f"{self.base_url}/customer/account/login/", timeout=30)
            soup = BeautifulSoup(resp.content, 'html.parser')
            form_key_input = soup.find('input', {'name': 'form_key'})
            
            if not form_key_input:
                logger.error("No se encontró form_key")
                return False
            
            form_key = form_key_input.get('value')
            
            # Login
            login_data = {
                'form_key': form_key,
                'login[username]': self.email,
                'login[password]': self.password,
                'send': ''
            }
            
            resp = self.session.post(
                f"{self.base_url}/customer/account/loginPost/",
                data=login_data,
                timeout=30,
                allow_redirects=True
            )
            
            if 'customer/account' in resp.url or resp.status_code == 200:
                logger.info("✅ Login exitoso")
                return True
            else:
                logger.error("❌ Login fallido")
                return False
                
        except Exception as e:
            logger.error(f"Error en login: {e}")
            return False
    
    def extraer_urls_productos(self, max_paginas: int = 50) -> List[str]:
        """Extrae URLs de todos los productos del catálogo"""
        logger.info("Extrayendo URLs de productos...")
        
        urls_productos = set()
        pagina_actual = 1
        
        while pagina_actual <= max_paginas:
            try:
                if pagina_actual == 1:
                    url = f"{self.base_url}/productos.html"
                else:
                    url = f"{self.base_url}/productos.html?p={pagina_actual}"
                
                logger.info(f"Página {pagina_actual}...")
                
                resp = self.session.get(url, timeout=30)
                soup = BeautifulSoup(resp.content, 'html.parser')
                
                # Buscar enlaces de productos
                enlaces = soup.select('a.product-item-link')
                
                if not enlaces:
                    logger.info(f"No hay más productos en página {pagina_actual}")
                    break
                
                for enlace in enlaces:
                    href = enlace.get('href')
                    if href and href not in urls_productos:
                        urls_productos.add(href)
                
                logger.info(f"  ✅ {len(enlaces)} productos encontrados")
                
                # Verificar si hay página siguiente
                siguiente = soup.select_one('a.action.next')
                if not siguiente:
                    break
                
                pagina_actual += 1
                time.sleep(1)
                
            except Exception as e:
                logger.error(f"Error en página {pagina_actual}: {e}")
                break
        
        logger.info(f"✅ Total URLs extraídas: {len(urls_productos)}")
        return list(urls_productos)
    
    def extraer_producto_sin_categorias(self, url: str) -> Optional[Dict]:
        """
        Extrae datos de producto SIN categorías
        
        Returns:
            dict: Producto completo (sin categorías) o None si falla
        """
        try:
            resp = self.session.get(url, timeout=30)
            resp.raise_for_status()
            
            html = resp.text
            soup = BeautifulSoup(html, 'html.parser')
            
            # ============================================================
            # 1. SKU (OBLIGATORIO)
            # ============================================================
            
            sku_element = soup.select_one('[itemprop="sku"]')
            if not sku_element:
                logger.warning(f"No se encontró SKU en: {url}")
                return None
            
            sku = sku_element.text.strip()
            
            # ============================================================
            # 2. DATOS BÁSICOS
            # ============================================================
            
            # Título
            titulo_meta = soup.find('meta', {'name': 'title'})
            titulo = titulo_meta.get('content', '').strip() if titulo_meta else ''
            
            # Precio
            precio_pattern = r'"price":\s*(\d+)'
            precio_match = re.search(precio_pattern, html)
            precio = int(precio_match.group(1)) if precio_match else 0
            
            # Descripción
            desc_element = soup.select_one('.product.attribute.description .value')
            descripcion = desc_element.get_text(separator='\n', strip=True) if desc_element else ''
            
            # Imágenes
            imagenes_pattern = r'"url":"(https?://[^"]+\.jpg)"'
            imagenes_matches = re.findall(imagenes_pattern, html)
            imagenes = []
            for img_url in imagenes_matches:
                url_limpia = img_url.replace('\\/', '/')
                if 'droppers.com.ar/media/catalog/product' in url_limpia:
                    imagenes.append(url_limpia)
            
            # ============================================================
            # 3. DISPONIBILIDAD/STOCK
            # ============================================================
            
            disponibilidad = "in stock"
            
            # Método 1: Buscar texto "Agotado"
            if re.search(r'agotado|out of stock|sin stock', html, re.IGNORECASE):
                disponibilidad = "out of stock"
            
            # Método 2: Botón deshabilitado
            add_to_cart = soup.select_one('#product-addtocart-button')
            if add_to_cart and add_to_cart.get('disabled'):
                disponibilidad = "out of stock"
            
            # Método 3: Clase "unavailable"
            if soup.select_one('.stock.unavailable'):
                disponibilidad = "out of stock"
            
            # ============================================================
            # 4. CONSTRUIR PRODUCTO (SIN CATEGORÍAS)
            # ============================================================
            
            producto = {
                # Datos básicos
                'sku': sku,
                'titulo': titulo,
                'precio': precio,
                'descripcion': descripcion,
                'imagenes': imagenes,
                'cantidad_imagenes': len(imagenes),
                
                # Disponibilidad
                'disponibilidad': disponibilidad,
                'availability': disponibilidad,
                
                # Metadata
                'url_original': url,
                'fecha_scraping': datetime.now().isoformat(),
                'scrapeado_con': 'scraper_maestro_v2_sin_categorias',
                
                # Nota importante
                'categorias_pendientes': True,
                'nota': 'Categorías se asignarán en FASE 2 con mapear_categorias_post_scraping.py'
            }
            
            return producto
            
        except Exception as e:
            logger.error(f"Error extrayendo producto {url}: {e}")
            return None
    
    def scrapear_producto_wrapper(self, url: str) -> Tuple[bool, Optional[Dict]]:
        """Wrapper para paralelización"""
        producto = self.extraer_producto_sin_categorias(url)
        
        if producto:
            try:
                # Guardar metadata
                Config.guardar_metadata(producto['sku'], producto)
                
                # Actualizar stats
                if producto['disponibilidad'] == 'out of stock':
                    self.stats['productos_agotados'] += 1
                else:
                    self.stats['productos_disponibles'] += 1
                
                return (True, producto)
            except Exception as e:
                logger.error(f"Error guardando {producto.get('sku')}: {e}")
                return (False, None)
        else:
            return (False, None)
    
    def scrapear_catalogo_completo(self, urls: List[str]) -> Dict:
        """Scrapea todo el catálogo en paralelo"""
        total = len(urls)
        self.stats['total_urls'] = total
        
        print("\n" + "="*80)
        print(f"FASE 1: SCRAPEANDO {total} PRODUCTOS (SIN CATEGORIAS)")
        print("="*80)
        print("\nObteniendo:")
        print("  - SKU, titulo, precio, descripcion, imagenes")
        print("  - Disponibilidad/stock")
        print("  - NO categorias (se asignan en FASE 2)")
        print("="*80 + "\n")
        
        productos_exitosos = []
        productos_fallidos = []
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {executor.submit(self.scrapear_producto_wrapper, url): url for url in urls}
            
            for i, future in enumerate(as_completed(futures), 1):
                url = futures[future]
                
                try:
                    exitoso, producto = future.result()
                    
                    if exitoso:
                        productos_exitosos.append(producto['sku'])
                        self.stats['productos_exitosos'] += 1
                        
                        # Progress cada 10 productos
                        if i % 10 == 0 or i == total:
                            elapsed = time.time() - self.stats['tiempo_inicio']
                            productos_por_min = (i / elapsed) * 60 if elapsed > 0 else 0
                            tiempo_restante = ((total - i) / productos_por_min) if productos_por_min > 0 else 0
                            
                            print(f"[{i}/{total}] SKU: {producto['sku']} | "
                                  f"Velocidad: {productos_por_min:.1f} prod/min | "
                                  f"Restante: {tiempo_restante:.1f} min")
                    else:
                        productos_fallidos.append(url)
                        self.stats['productos_fallidos'] += 1
                        
                except Exception as e:
                    logger.error(f"Error procesando {url}: {e}")
                    productos_fallidos.append(url)
                    self.stats['productos_fallidos'] += 1
                
                # Rate limiting
                time.sleep(0.1)
        
        tiempo_total = time.time() - self.stats['tiempo_inicio']
        
        return {
            'total': total,
            'exitosos': len(productos_exitosos),
            'fallidos': len(productos_fallidos),
            'disponibles': self.stats['productos_disponibles'],
            'agotados': self.stats['productos_agotados'],
            'tiempo_total_segundos': tiempo_total,
            'tiempo_total_minutos': tiempo_total / 60,
            'productos_exitosos': productos_exitosos,
            'productos_fallidos': productos_fallidos
        }
    
    def generar_reporte(self, estadisticas: Dict) -> Path:
        """Genera reporte JSON del scraping"""
        fecha = datetime.now().strftime('%Y%m%d_%H%M%S')
        reporte_file = Config.DATA_DIR / f'reporte_fase1_productos_{fecha}.json'
        
        with open(reporte_file, 'w', encoding='utf-8') as f:
            json.dump(estadisticas, f, indent=2, ensure_ascii=False)
        
        logger.info(f"📄 Reporte guardado: {reporte_file}")
        return reporte_file


def main():
    """Función principal"""
    print("\n" + "="*80)
    print("SCRAPER MAESTRO V2 - FASE 1: PRODUCTOS SIN CATEGORIAS")
    print("="*80)
    print("\nEste scraper obtiene:")
    print("  - SKU, titulo, precio, descripcion, imagenes")
    print("  - Disponibilidad/stock")
    print("\nNO obtiene:")
    print("  - Categorias (se asignan en FASE 2)")
    print("\nPor que 2 fases:")
    print("  - El breadcrumb no es confiable")
    print("  - FASE 2 mapea categorias desde listados de categorias")
    print("  - Mas preciso y robusto")
    print("="*80 + "\n")
    
    # Inicializar
    scraper = ScraperMaestroV2()
    
    # Login
    if not scraper.login():
        print("\n❌ Login fallido. Verificar credenciales en .env")
        return
    
    # Extraer URLs
    print("\nExtrayendo URLs del catálogo...")
    urls_productos = scraper.extraer_urls_productos()
    
    if not urls_productos:
        print("\n⚠️  No se encontraron productos para scrapear")
        return
    
    # Ejecutar automáticamente desde .bat
    print(f"\nSe van a scrapear {len(urls_productos)} productos")
    print("Ejecutando automáticamente...")
    
    # Scrapear
    inicio = time.time()
    estadisticas = scraper.scrapear_catalogo_completo(urls_productos)
    tiempo_total = time.time() - inicio
    
    # Reporte
    reporte = scraper.generar_reporte(estadisticas)
    
    # Resumen
    print("\n" + "="*80)
    print("RESUMEN FASE 1 - PRODUCTOS SIN CATEGORIAS")
    print("="*80)
    print(f"\nTiempo total: {tiempo_total/60:.1f} minutos ({tiempo_total:.0f} segundos)")
    print(f"\nProductos procesados: {estadisticas['total']}")
    print(f"  - Exitosos: {estadisticas['exitosos']}")
    print(f"  - Fallidos: {estadisticas['fallidos']}")
    print(f"\nEstado:")
    print(f"  - Disponibles: {estadisticas['disponibles']}")
    print(f"  - Agotados: {estadisticas['agotados']}")
    print(f"\nVelocidad: {estadisticas['exitosos']/(tiempo_total/60):.1f} productos/minuto")
    print(f"\nReporte: {reporte}")
    print("="*80 + "\n")
    
    print("FASE 1 COMPLETADA")
    print("\nProximos pasos:")
    print("  1. python mapear_categorias_post_scraping.py  (FASE 2)")
    print("  2. python 02_descargar_imagenes_OPTIMIZADO.py --solo-faltantes")
    print("  3. python 03_subir_imagenes_cloudinary.py")
    print("  4. python 04_calculo_precios.py")
    print("  5. python asignar_categoria_ofertas.py")
    print("  6. python 11_sincronizar_sqlite.py")
    print("  7. python 06_sincronizar_google_sheets_OPTIMIZADO.py")


if __name__ == "__main__":
    main()
