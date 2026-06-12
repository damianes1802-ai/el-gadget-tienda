#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SCRAPER DE DROPPERS.COM.AR
Extrae productos desde Droppers y guarda en estructura local
"""

import re
import time
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from bs4 import BeautifulSoup
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Imports locales
import sys
sys.path.append(str(Path(__file__).parent))
from utils.logger import get_logger, LoggerManager
from utils.validaciones import ValidadorProducto
from utils.config import Config

# Logger para este módulo
logger = get_logger('scraper')


class DroppersScraper:
    """Scraper para extraer productos de Droppers.com.ar"""
    
    def __init__(self):
        """Inicializa el scraper con configuración"""
        self.config = Config.get_scraping_config()
        self.session = self._crear_sesion()
        self.productos_exitosos = []
        self.productos_fallidos = []
        
        logger.info("Scraper inicializado correctamente")
    
    def _crear_sesion(self) -> requests.Session:
        """
        Crea una sesión con reintentos automáticos
        
        Returns:
            requests.Session: Sesión configurada
        """
        session = requests.Session()
        
        # Configurar reintentos
        retry_strategy = Retry(
            total=self.config['rate_limiting']['max_reintentos'],
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        
        # User agent
        session.headers.update({
            'User-Agent': self.config['rate_limiting']['user_agent']
        })
        
        return session
    
    def login(self, username: str, password: str) -> bool:
        """
        Realiza login en Droppers
        
        Args:
            username (str): Email de usuario
            password (str): Contraseña
        
        Returns:
            bool: True si login exitoso
        """
        logger.info(f"Intentando login con usuario: {username}")
        
        try:
            # 1. Obtener página de login para extraer form_key
            login_url = self.config['login']['url']
            response = self.session.get(login_url, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Extraer form_key
            form_key_input = soup.find('input', {'name': 'form_key'})
            if not form_key_input:
                logger.error("No se pudo encontrar el form_key en la página de login")
                return False
            
            form_key = form_key_input.get('value')
            logger.debug(f"form_key extraído: {form_key}")
            
            # 2. Enviar formulario de login
            login_data = {
                'form_key': form_key,
                self.config['login']['campos']['username']: username,
                self.config['login']['campos']['password']: password
            }
            
            post_url = self.config['login']['form_action']
            response = self.session.post(post_url, data=login_data, timeout=30)
            response.raise_for_status()
            
            # 3. Verificar si el login fue exitoso
            for indicator in self.config['login']['success_indicators']:
                if indicator in response.text:
                    logger.info("✅ Login exitoso")
                    return True
            
            logger.error("❌ Login fallido - No se encontraron indicadores de éxito")
            return False
            
        except Exception as e:
            logger.exception(f"Error durante el login: {e}")
            return False
    
    def extraer_urls_productos(self, max_paginas: int = None) -> List[str]:
        """
        Extrae URLs de todos los productos del listado
        
        Args:
            max_paginas (int): Número máximo de páginas a scrapear (None = todas)
        
        Returns:
            list: Lista de URLs de productos
        """
        logger.info("Extrayendo URLs de productos del listado...")
        
        urls_productos = []
        pagina_actual = 1
        max_pag = max_paginas or self.config['listado_productos']['paginacion']['max_paginas']
        
        while pagina_actual <= max_pag:
            logger.info(f"Procesando página {pagina_actual}...")
            
            # Construir URL de la página
            if pagina_actual == 1:
                url = self.config['listado_productos']['url_base']
            else:
                url = self.config['listado_productos']['paginacion']['url_pattern'].format(
                    numero_pagina=pagina_actual
                )
            
            try:
                response = self.session.get(url, timeout=30)
                response.raise_for_status()
                
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Extraer enlaces de productos
                selector = self.config['listado_productos']['selectores']['enlaces_productos']
                enlaces = soup.select(selector)
                
                if not enlaces:
                    logger.info(f"No se encontraron más productos en página {pagina_actual}")
                    break
                
                # Extraer URLs
                for enlace in enlaces:
                    href = enlace.get('href')
                    if href and href not in urls_productos:
                        urls_productos.append(href)
                
                logger.info(f"✅ Página {pagina_actual}: {len(enlaces)} productos encontrados")
                
                # Verificar si hay página siguiente
                if not soup.select_one(self.config['listado_productos']['paginacion']['selector_siguiente']):
                    logger.info("No hay más páginas disponibles")
                    break
                
                pagina_actual += 1
                
                # Rate limiting entre páginas
                time.sleep(self.config['rate_limiting']['delay_entre_paginas_segundos'])
                
            except Exception as e:
                logger.error(f"Error procesando página {pagina_actual}: {e}")
                break
        
        logger.info(f"✅ Total URLs extraídas: {len(urls_productos)}")
        return urls_productos
    
    def extraer_producto(self, url: str) -> Optional[Dict]:
        """
        Extrae datos de un producto individual
        
        Args:
            url (str): URL del producto
        
        Returns:
            dict: Datos del producto o None si falla
        """
        logger.debug(f"Extrayendo producto: {url}")
        
        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            
            html = response.text
            soup = BeautifulSoup(html, 'html.parser')
            
            # 1. Extraer SKU
            sku_element = soup.select_one(
                self.config['producto_individual']['selectores_html']['sku']['selector']
            )
            if not sku_element:
                logger.error(f"No se encontró SKU en: {url}")
                return None
            
            sku = sku_element.text.strip()
            
            # 2. Extraer título
            titulo_meta = soup.find('meta', {'name': 'title'})
            titulo = titulo_meta.get('content', '').strip() if titulo_meta else None
            
            # 3. Extraer precio (numérico desde JSON)
            precio_pattern = self.config['producto_individual']['extraccion_json']['precio_numerico']['patron_regex']
            precio_match = re.search(precio_pattern, html)
            precio = int(precio_match.group(1)) if precio_match else None
            
            # 4. Extraer descripción
            desc_selector = self.config['producto_individual']['selectores_html']['descripcion']['selector']
            desc_element = soup.select_one(desc_selector)
            descripcion = ""
            if desc_element:
                # Limpiar HTML interno
                descripcion = desc_element.get_text(separator='\n', strip=True)
                # Limpiar tags <p> extras
                descripcion = descripcion.replace('<p>', '\n').replace('</p>', '')
            
            # 5. Extraer imágenes (desde JSON embebido)
            imagenes_pattern = self.config['producto_individual']['extraccion_json']['imagenes']['patron_regex']
            imagenes_matches = re.findall(imagenes_pattern, html)
            
            # Limpiar URLs (reemplazar \/ por /)
            imagenes = []
            for img_url in imagenes_matches:
                url_limpia = img_url.replace('\\/', '/')
                # Filtrar solo imágenes de Droppers
                if 'droppers.com.ar/media/catalog/product' in url_limpia:
                    imagenes.append(url_limpia)
            
            # Construir diccionario de datos
            producto = {
                'sku': sku,
                'titulo': titulo,
                'precio': precio,
                'descripcion': descripcion,
                'imagenes': imagenes,
                'url_original': url,
                'fecha_scraping': datetime.now().isoformat(),
                'cantidad_imagenes': len(imagenes)
            }
            
            return producto
            
        except Exception as e:
            logger.exception(f"Error extrayendo producto {url}: {e}")
            return None
    
    def guardar_producto(self, producto: Dict) -> bool:
        """
        Guarda un producto en la estructura de archivos
        
        Args:
            producto (dict): Datos del producto
        
        Returns:
            bool: True si se guardó exitosamente
        """
        sku = producto['sku']
        
        try:
            # Validar producto antes de guardar
            validacion = ValidadorProducto.validar_producto_completo(producto)
            
            if not validacion['valido']:
                logger.error(f"Producto {sku} no pasó validación:")
                for error in validacion['errores']:
                    logger.error(f"  - {error}")
                return False
            
            # Advertencias (no impiden guardar)
            for advertencia in validacion['advertencias']:
                logger.warning(f"  ⚠️  {advertencia}")
            
            # Guardar metadata
            Config.guardar_metadata(sku, producto)
            logger.info(f"✅ Producto {sku} guardado correctamente")
            
            return True
            
        except Exception as e:
            logger.exception(f"Error guardando producto {sku}: {e}")
            return False
    
    def scrapear_productos(self, urls: List[str], max_productos: int = None) -> Dict:
        """
        Scrapea múltiples productos
        
        Args:
            urls (list): Lista de URLs de productos
            max_productos (int): Máximo de productos a scrapear (None = todos)
        
        Returns:
            dict: Estadísticas del scraping
        """
        total = len(urls)
        if max_productos:
            total = min(total, max_productos)
            urls = urls[:max_productos]
        
        LoggerManager.log_inicio_proceso(logger, "Scraping de Productos", total)
        
        exitosos = 0
        fallidos = 0
        
        for i, url in enumerate(urls, 1):
            logger.info(f"Procesando {i}/{total}: {url}")
            
            # Extraer producto
            producto = self.extraer_producto(url)
            
            if producto:
                # Guardar producto
                if self.guardar_producto(producto):
                    exitosos += 1
                    self.productos_exitosos.append(producto['sku'])
                else:
                    fallidos += 1
                    self.productos_fallidos.append(url)
            else:
                fallidos += 1
                self.productos_fallidos.append(url)
            
            # Rate limiting entre productos
            if i < total:
                time.sleep(self.config['rate_limiting']['delay_entre_productos_segundos'])
        
        LoggerManager.log_fin_proceso(logger, "Scraping de Productos", exitosos, fallidos)
        
        return {
            'total': total,
            'exitosos': exitosos,
            'fallidos': fallidos,
            'skus_exitosos': self.productos_exitosos,
            'urls_fallidas': self.productos_fallidos
        }
    
    def generar_reporte(self, estadisticas: Dict) -> str:
        """
        Genera un reporte del scraping
        
        Args:
            estadisticas (dict): Estadísticas del scraping
        
        Returns:
            str: Ruta al archivo de reporte
        """
        fecha = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
        reporte_file = Config.LOGS_DIR / f"reporte_scraping_{fecha}.json"
        
        with open(reporte_file, 'w', encoding='utf-8') as f:
            json.dump(estadisticas, f, indent=2, ensure_ascii=False)
        
        logger.info(f"📄 Reporte guardado en: {reporte_file}")
        return str(reporte_file)


def main():
    """Función principal para ejecutar el scraper"""
    print("=" * 80)
    print("🔍 SCRAPER DE DROPPERS.COM.AR")
    print("=" * 80)
    
    # Inicializar scraper
    scraper = DroppersScraper()
    
    # Obtener credenciales
    try:
        credenciales = Config.get_credenciales_droppers()
    except ValueError as e:
        logger.error(f"Error: {e}")
        print(f"\n❌ {e}")
        print(f"   Editar archivo: {Config.ENV_FILE}")
        return
    
    # Login
    if not scraper.login(credenciales['username'], credenciales['password']):
        logger.error("No se pudo realizar el login")
        print("\n❌ Login fallido. Verificar credenciales.")
        return
    
    # Preguntar modo de operación
    print("\n📋 Modo de operación:")
    print("  1. Scrapear TODO el catálogo")
    print("  2. Scrapear solo X páginas")
    print("  3. Scrapear URLs específicas")
    
    modo = input("\nSeleccionar (1/2/3): ").strip()
    
    urls_productos = []
    
    if modo == "1":
        urls_productos = scraper.extraer_urls_productos()
    elif modo == "2":
        max_pag = int(input("¿Cuántas páginas? "))
        urls_productos = scraper.extraer_urls_productos(max_paginas=max_pag)
    elif modo == "3":
        print("Ingresar URLs (una por línea, línea vacía para terminar):")
        while True:
            url = input().strip()
            if not url:
                break
            urls_productos.append(url)
    else:
        print("Opción inválida")
        return
    
    if not urls_productos:
        print("\n⚠️  No se encontraron productos para scrapear")
        return
    
    # Confirmar
    print(f"\n📊 Se van a scrapear {len(urls_productos)} productos")
    confirmar = input("¿Continuar? (s/n): ").strip().lower()
    
    if confirmar != 's':
        print("Operación cancelada")
        return
    
    # Scrapear
    estadisticas = scraper.scrapear_productos(urls_productos)
    
    # Generar reporte
    reporte = scraper.generar_reporte(estadisticas)
    
    # Resumen
    print("\n" + "=" * 80)
    print("📊 RESUMEN DEL SCRAPING")
    print("=" * 80)
    print(f"Total procesados: {estadisticas['total']}")
    print(f"✅ Exitosos: {estadisticas['exitosos']}")
    print(f"❌ Fallidos: {estadisticas['fallidos']}")
    print(f"\n📄 Reporte: {reporte}")
    print("=" * 80)


if __name__ == "__main__":
    main()
