#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MAPEADOR DE CATEGORÍAS POST-SCRAPING - FASE 2
Asigna categorías a productos ya scrapeados

ESTRATEGIA:
1. Lee categorías desde config/categorias_droppers.json
2. Por cada categoría: extrae URLs de productos  
3. Obtiene SKU de cada URL (con CACHÉ para evitar duplicados)
4. Actualiza metadata con categorías
5. Aplica sistema de prioridades

OPTIMIZACIONES:
✅ Caché de SKUs (no visita el mismo producto 2 veces)
✅ Paralelización (8 productos simultáneos)
✅ Sistema de prioridades integrado

AUTOR: Sistema Ecommerce Automation
FECHA: 2026-03-16
VERSION: 1.0
"""

import json
import time
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import defaultdict
import sys

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from dotenv import load_dotenv
import os

sys.path.append(str(Path(__file__).parent))
from utils.logger import get_logger
from utils.config import Config

logger = get_logger('mapear_categorias')
load_dotenv(Config.CONFIG_DIR / '.env')


class MapeadorCategorias:
    """Mapea categorías a productos ya scrapeados"""
    
    CATEGORIAS_CONFIG_FILE = Config.CONFIG_DIR / "categorias_droppers.json"
    
    def __init__(self):
        self.session = self._crear_sesion()
        self.base_url = "https://droppers.com.ar"
        
        # Credenciales
        self.email = os.getenv('DROPPERS_EMAIL') or os.getenv('DROPPERS_USER')
        self.password = os.getenv('DROPPERS_PASSWORD') or os.getenv('DROPPERS_PASS')
        
        if not self.email or not self.password:
            raise ValueError("❌ Faltan credenciales de Droppers en .env")
        
        # Cargar categorías con prioridades
        self.categorias = self._cargar_categorias()
        self.prioridades = self._cargar_prioridades()
        
        # CACHÉ: {url: sku}
        self.cache_sku = {}
        
        # Mapa: {sku: [categorias]}
        self.mapa_categorias = defaultdict(list)
        
        # Estadísticas
        self.stats = {
            'categorias_procesadas': 0,
            'productos_visitados': 0,
            'productos_cache': 0,
            'productos_actualizados': 0,
            'tiempo_inicio': time.time()
        }
        
        self.max_workers = 8
        
        logger.info("Mapeador de Categorías inicializado")
    
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
    
    def _cargar_categorias(self) -> Dict[str, Dict]:
        """Carga categorías desde JSON ordenadas por prioridad"""
        try:
            with open(self.CATEGORIAS_CONFIG_FILE, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            categorias_activas = {}
            for nombre, datos in config.get('categorias', {}).items():
                if datos.get('activa', True):
                    categorias_activas[nombre] = {
                        'url': datos['url'],
                        'prioridad': datos.get('prioridad', 50)
                    }
            
            # Ordenar por prioridad
            categorias_ordenadas = dict(
                sorted(categorias_activas.items(), key=lambda x: x[1]['prioridad'])
            )
            
            logger.info(f"✅ Cargadas {len(categorias_ordenadas)} categorías activas")
            return categorias_ordenadas
            
        except FileNotFoundError:
            logger.error(f"No se encontró {self.CATEGORIAS_CONFIG_FILE}")
            return {}
    
    def _cargar_prioridades(self) -> Dict[str, int]:
        """Carga mapa de prioridades"""
        return {nombre: datos['prioridad'] for nombre, datos in self.categorias.items()}
    
    def login(self) -> bool:
        """Login en Droppers"""
        logger.info("Iniciando login en Droppers...")
        
        try:
            resp = self.session.get(f"{self.base_url}/customer/account/login/", timeout=30)
            soup = BeautifulSoup(resp.content, 'html.parser')
            form_key_input = soup.find('input', {'name': 'form_key'})
            
            if not form_key_input:
                logger.error("No se encontró form_key")
                return False
            
            form_key = form_key_input.get('value')
            
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
    
    def extraer_urls_de_categoria(self, categoria_url: str, max_paginas: int = 20) -> List[str]:
        """Extrae URLs de productos de una categoría"""
        urls = set()
        pagina = 1
        
        while pagina <= max_paginas:
            try:
                if pagina == 1:
                    url = categoria_url
                else:
                    if '?' in categoria_url:
                        url = f"{categoria_url}&p={pagina}"
                    else:
                        url = f"{categoria_url}?p={pagina}"
                
                resp = self.session.get(url, timeout=30)
                soup = BeautifulSoup(resp.content, 'html.parser')
                
                enlaces = soup.select('a.product-item-link')
                
                if not enlaces:
                    break
                
                for enlace in enlaces:
                    href = enlace.get('href')
                    if href:
                        urls.add(href)
                
                siguiente = soup.select_one('a.action.next')
                if not siguiente:
                    break
                
                pagina += 1
                time.sleep(0.5)
                
            except Exception as e:
                logger.error(f"Error extrayendo URLs de categoría página {pagina}: {e}")
                break
        
        return list(urls)
    
    def extraer_sku_de_url(self, url: str) -> Optional[str]:
        """Extrae SKU de una URL (con caché)"""
        # Verificar caché
        if url in self.cache_sku:
            self.stats['productos_cache'] += 1
            return self.cache_sku[url]
        
        # No está en caché: visitar
        try:
            resp = self.session.get(url, timeout=30)
            resp.raise_for_status()
            
            soup = BeautifulSoup(resp.content, 'html.parser')
            sku_element = soup.select_one('[itemprop="sku"]')
            
            if not sku_element:
                logger.warning(f"No se encontró SKU en: {url}")
                return None
            
            sku = sku_element.text.strip()
            
            # Guardar en caché
            self.cache_sku[url] = sku
            self.stats['productos_visitados'] += 1
            
            return sku
            
        except Exception as e:
            logger.error(f"Error extrayendo SKU de {url}: {e}")
            return None
    
    def procesar_categoria(self, categoria_nombre: str, categoria_url: str) -> int:
        """Procesa una categoría"""
        print(f"\nProcesando: {categoria_nombre} (prioridad: {self.prioridades[categoria_nombre]})")
        
        # Extraer URLs
        urls = self.extraer_urls_de_categoria(categoria_url)
        print(f"  Productos encontrados: {len(urls)}")
        
        if not urls:
            print(f"  Sin productos en listado")
            return 0
        
        # Extraer SKUs en paralelo
        skus_asignados = 0
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {executor.submit(self.extraer_sku_de_url, url): url for url in urls}
            
            for future in as_completed(futures):
                try:
                    sku = future.result()
                    
                    if sku:
                        if categoria_nombre not in self.mapa_categorias[sku]:
                            self.mapa_categorias[sku].append(categoria_nombre)
                            skus_asignados += 1
                        
                except Exception as e:
                    logger.error(f"Error procesando URL: {e}")
                
                time.sleep(0.05)
        
        print(f"  {skus_asignados} productos asignados")
        return skus_asignados
    
    def aplicar_prioridades_y_actualizar(self) -> int:
        """Aplica prioridades y actualiza metadata"""
        print("\nAplicando sistema de prioridades...")
        
        productos_actualizados = 0
        
        for sku, categorias in self.mapa_categorias.items():
            try:
                metadata = Config.cargar_metadata(sku)
                
                if not metadata:
                    logger.warning(f"No se encontró metadata para SKU: {sku}")
                    continue
                
                # Categoría principal = menor prioridad (más importante)
                categoria_principal = min(
                    categorias,
                    key=lambda c: self.prioridades.get(c, 999)
                )
                
                categorias_secundarias = [c for c in categorias if c != categoria_principal]
                
                # Actualizar metadata
                metadata['todas_las_categorias'] = categorias
                metadata['categoria_principal'] = categoria_principal
                metadata['categoria'] = categoria_principal
                metadata['categorias_secundarias'] = categorias_secundarias
                metadata['total_categorias'] = len(categorias)
                metadata['categorias_asignadas'] = True
                metadata['fecha_mapeo_categorias'] = datetime.now().isoformat()
                
                # Quitar nota de pendiente
                metadata.pop('categorias_pendientes', None)
                metadata.pop('nota', None)
                
                Config.guardar_metadata(sku, metadata)
                productos_actualizados += 1
                
            except Exception as e:
                logger.error(f"Error actualizando {sku}: {e}")
        
        print(f"{productos_actualizados} productos actualizados")
        return productos_actualizados
    
    def ejecutar(self) -> Dict:
        """Ejecuta el mapeo completo"""
        print("\n" + "="*80)
        print("FASE 2: MAPEO DE CATEGORIAS POST-SCRAPING")
        print("="*80)
        print(f"\nCategorías a procesar: {len(self.categorias)}")
        for nombre, datos in self.categorias.items():
            print(f"  - {nombre} (prioridad: {datos['prioridad']})")
        print("="*80)
        
        # Procesar cada categoría
        for categoria_nombre, categoria_datos in self.categorias.items():
            self.procesar_categoria(categoria_nombre, categoria_datos['url'])
            self.stats['categorias_procesadas'] += 1
        
        # Aplicar prioridades
        productos_actualizados = self.aplicar_prioridades_y_actualizar()
        self.stats['productos_actualizados'] = productos_actualizados
        
        tiempo_total = time.time() - self.stats['tiempo_inicio']
        
        return {
            'categorias_procesadas': self.stats['categorias_procesadas'],
            'productos_visitados': self.stats['productos_visitados'],
            'productos_cache': self.stats['productos_cache'],
            'productos_actualizados': self.stats['productos_actualizados'],
            'total_productos_con_categoria': len(self.mapa_categorias),
            'tiempo_total_segundos': tiempo_total,
            'tiempo_total_minutos': tiempo_total / 60,
            'distribucion_categorias': {
                cat: len([sku for sku, cats in self.mapa_categorias.items() if cat in cats])
                for cat in self.categorias.keys()
            }
        }
    
    def generar_reporte(self, estadisticas: Dict) -> Path:
        """Genera reporte JSON"""
        fecha = datetime.now().strftime('%Y%m%d_%H%M%S')
        reporte_file = Config.DATA_DIR / f'reporte_fase2_categorias_{fecha}.json'
        
        with open(reporte_file, 'w', encoding='utf-8') as f:
            json.dump(estadisticas, f, indent=2, ensure_ascii=False)
        
        logger.info(f"📄 Reporte guardado: {reporte_file}")
        return reporte_file


def main():
    """Función principal - ejecuta automáticamente desde .bat"""
    print("\n" + "="*80)
    print("MAPEADOR DE CATEGORIAS - FASE 2")
    print("="*80)
    print("\nAsigna categorías a productos scrapeados en FASE 1")
    print("="*80 + "\n")
    
    # Inicializar
    mapeador = MapeadorCategorias()
    
    # Login
    if not mapeador.login():
        print("\nERROR: Login fallido. Verificar credenciales en .env")
        sys.exit(1)
    
    # Ejecutar automáticamente (sin confirmación)
    inicio = time.time()
    estadisticas = mapeador.ejecutar()
    tiempo_total = time.time() - inicio
    
    # Reporte
    reporte = mapeador.generar_reporte(estadisticas)
    
    # Resumen
    print("\n" + "="*80)
    print("RESUMEN FASE 2 - CATEGORIAS ASIGNADAS")
    print("="*80)
    print(f"\nTiempo total: {tiempo_total/60:.1f} minutos ({tiempo_total:.0f} segundos)")
    print(f"\nCategorías procesadas: {estadisticas['categorias_procesadas']}")
    print(f"\nProductos:")
    print(f"  - Visitados (nuevos): {estadisticas['productos_visitados']}")
    print(f"  - Desde cache: {estadisticas['productos_cache']}")
    print(f"  - Con categoría: {estadisticas['total_productos_con_categoria']}")
    print(f"  - Actualizados: {estadisticas['productos_actualizados']}")
    
    print(f"\nDistribucion de categorías:")
    for cat, cantidad in estadisticas['distribucion_categorias'].items():
        prioridad = mapeador.prioridades.get(cat, 0)
        print(f"  - {cat}: {cantidad} productos (prioridad: {prioridad})")
    
    print(f"\nEficiencia del cache:")
    total_ops = estadisticas['productos_visitados'] + estadisticas['productos_cache']
    if total_ops > 0:
        cache_rate = (estadisticas['productos_cache'] / total_ops) * 100
        print(f"  - {cache_rate:.1f}% hits (evito {estadisticas['productos_cache']} visitas)")
    
    print(f"\nReporte: {reporte}")
    print("\n" + "="*80)
    print("FASE 2 COMPLETADA - Categorías asignadas correctamente")
    print("="*80 + "\n")


if __name__ == "__main__":
    main()
