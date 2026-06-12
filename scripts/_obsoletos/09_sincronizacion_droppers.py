#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MÓDULO DE SINCRONIZACIÓN CON DROPPERS
Actualiza stock y precios basándose en los informes de Droppers
"""

import json
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple
from dotenv import load_dotenv
import os
import re

# Imports locales
import sys
sys.path.append(str(Path(__file__).parent))
from utils.config import Config
from utils.logger import get_logger

logger = get_logger('sincronizacion_droppers')


class SincronizadorDroppers:
    """Sincroniza stock y precios con informes de Droppers"""
    
    URL_LOGIN = "https://droppers.com.ar/customer/account/login/"
    URL_LOGIN_POST = "https://droppers.com.ar/customer/account/loginPost/"
    URL_INFORMES = "https://droppers.com.ar/alerts/customer/index/"
    
    def __init__(self):
        """Inicializa el sincronizador"""
        # Cargar credenciales
        load_dotenv(Config.CONFIG_DIR / '.env')
        self.user = os.getenv('DROPPERS_USER')
        self.password = os.getenv('DROPPERS_PASS')
        
        if not self.user or not self.password:
            raise ValueError(
                "Credenciales de Droppers no encontradas en .env\n"
                "Agregar DROPPERS_USER y DROPPERS_PASS"
            )
        
        # Configurar sesión con headers
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'es-ES,es;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        })
        
        self.cambios_stock = []
        self.cambios_precios = []
        
        self.estadisticas = {
            'agotados': 0,
            'reingresados': 0,
            'precios_actualizados': 0,
            'productos_sin_cambios': 0,
            'errores': 0
        }
        
        logger.info("Sincronizador de Droppers inicializado")
    
    def login(self) -> bool:
        """
        Realiza login en Droppers
        
        Returns:
            bool: True si login exitoso
        """
        try:
            print("\n🔐 Conectando a Droppers...")
            
            # Obtener página de login para el form_key
            response = self.session.get(self.URL_LOGIN)
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Buscar form_key
            form_key_input = soup.find('input', {'name': 'form_key'})
            form_key = form_key_input['value'] if form_key_input else None
            
            # Datos de login
            login_data = {
                'login[username]': self.user,
                'login[password]': self.password,
                'send': ''
            }
            
            if form_key:
                login_data['form_key'] = form_key
            
            # Realizar login
            response = self.session.post(self.URL_LOGIN_POST, data=login_data)
            
            # Verificar si el login fue exitoso
            if 'customer/account' in response.url or 'Mi cuenta' in response.text:
                logger.info("✅ Login exitoso")
                print("✅ Login exitoso")
                return True
            else:
                logger.error("❌ Login fallido")
                print("❌ Login fallido - Verificar credenciales")
                return False
                
        except Exception as e:
            logger.error(f"Error en login: {e}")
            print(f"❌ Error en login: {e}")
            return False
    
    def extraer_cambios_stock(self, html: str) -> List[Dict]:
        """
        Extrae cambios de stock del HTML
        
        Args:
            html: HTML de la página de informes
        
        Returns:
            list: Lista de cambios de stock
        """
        try:
            soup = BeautifulSoup(html, 'html.parser')
            cambios = []
            
            # Buscar la tabla de cambios de stock
            # La tabla tiene el header "Cambios de stock de los últimos 10 días"
            tablas = soup.find_all('table')
            
            for tabla in tablas:
                # Verificar si es la tabla de stock
                header_anterior = tabla.find_previous('h3')
                if header_anterior and 'stock' in header_anterior.text.lower():
                    
                    filas = tabla.find_all('tr')[1:]  # Saltar header
                    
                    for fila in filas:
                        celdas = fila.find_all('td')
                        if len(celdas) >= 4:
                            sku = celdas[0].text.strip()
                            producto = celdas[1].text.strip()
                            estado = celdas[2].text.strip()
                            fecha = celdas[3].text.strip()
                            
                            cambios.append({
                                'sku': sku,
                                'producto': producto,
                                'estado': estado,  # "Agotado" o "Reingresado"
                                'fecha': fecha
                            })
            
            logger.info(f"✅ Extraídos {len(cambios)} cambios de stock")
            return cambios
            
        except Exception as e:
            logger.error(f"Error extrayendo cambios de stock: {e}")
            return []
    
    def extraer_cambios_precios(self, html: str) -> List[Dict]:
        """
        Extrae cambios de precios del HTML
        
        Args:
            html: HTML de la página de informes
        
        Returns:
            list: Lista de cambios de precios
        """
        try:
            soup = BeautifulSoup(html, 'html.parser')
            cambios = []
            
            # Buscar la tabla de cambios de precios
            tablas = soup.find_all('table')
            
            for tabla in tablas:
                # Verificar si es la tabla de precios
                header_anterior = tabla.find_previous('h3')
                if header_anterior and 'precio' in header_anterior.text.lower():
                    
                    filas = tabla.find_all('tr')[1:]  # Saltar header
                    
                    for fila in filas:
                        celdas = fila.find_all('td')
                        if len(celdas) >= 5:
                            sku = celdas[0].text.strip()
                            producto = celdas[1].text.strip()
                            precio_droppers = celdas[2].text.strip()
                            precio_sugerido = celdas[3].text.strip()
                            fecha = celdas[4].text.strip()
                            
                            # Limpiar precios (quitar $ y ,)
                            precio_droppers = float(
                                re.sub(r'[^\d.]', '', precio_droppers.replace(',', ''))
                            )
                            precio_sugerido = float(
                                re.sub(r'[^\d.]', '', precio_sugerido.replace(',', ''))
                            )
                            
                            cambios.append({
                                'sku': sku,
                                'producto': producto,
                                'precio_droppers': precio_droppers,
                                'precio_sugerido': precio_sugerido,
                                'fecha': fecha
                            })
            
            logger.info(f"✅ Extraídos {len(cambios)} cambios de precios")
            return cambios
            
        except Exception as e:
            logger.error(f"Error extrayendo cambios de precios: {e}")
            return []
    
    def obtener_informes(self) -> Tuple[List[Dict], List[Dict]]:
        """
        Obtiene informes de cambios desde Droppers
        
        Returns:
            tuple: (cambios_stock, cambios_precios)
        """
        try:
            print("\n📊 Obteniendo informes de Droppers...")
            print(f"   URL: {self.URL_INFORMES}")
            
            response = self.session.get(self.URL_INFORMES, allow_redirects=True)
            
            print(f"   Status: {response.status_code}")
            print(f"   URL final: {response.url}")
            
            logger.info(f"Status code: {response.status_code}")
            logger.info(f"URL final: {response.url}")
            
            # Guardar HTML SIEMPRE (incluso si hay error)
            debug_file = Config.LOGS_DIR / "droppers_response_debug.html"
            with open(debug_file, 'w', encoding='utf-8') as f:
                f.write(response.text)
            print(f"   📄 Respuesta guardada en: {debug_file}")
            logger.info(f"HTML guardado en: {debug_file}")
            
            if response.status_code == 403:
                print("\n❌ ERROR 403: Acceso denegado")
                print("\n🔍 VERIFICAR:")
                print("   1. Abre navegador y haz login en Droppers")
                print("   2. Ve a: https://droppers.com.ar/alerts/customer/index/")
                print("   3. ¿Puedes ver la página?")
                print(f"\n💡 Revisa el HTML guardado en:")
                print(f"   {debug_file}")
                print("   (Busca si dice 'acceso denegado' o similar)")
                logger.error("Acceso denegado (403) a página de informes")
                return [], []
            
            if response.status_code != 200:
                logger.error(f"Error obteniendo informes: {response.status_code}")
                print(f"\n❌ Error HTTP {response.status_code}")
                return [], []
            
            html = response.text
            
            # Extraer cambios
            cambios_stock = self.extraer_cambios_stock(html)
            cambios_precios = self.extraer_cambios_precios(html)
            
            self.cambios_stock = cambios_stock
            self.cambios_precios = cambios_precios
            
            print(f"✅ {len(cambios_stock)} cambios de stock")
            print(f"✅ {len(cambios_precios)} cambios de precios")
            
            if len(cambios_stock) == 0 and len(cambios_precios) == 0:
                print(f"\n💡 No se encontraron cambios. Revisa el HTML en:")
                print(f"   {debug_file}")
                print("   (Busca las tablas manualmente)")
            
            return cambios_stock, cambios_precios
            
        except Exception as e:
            logger.error(f"Error obteniendo informes: {e}")
            print(f"❌ Error: {e}")
            import traceback
            traceback.print_exc()
            return [], []
    
    def recalcular_precio_venta(self, precio_costo: float, metadata: Dict) -> float:
        """
        Recalcula precio de venta basándose en el nuevo precio de costo
        
        Args:
            precio_costo: Nuevo precio de costo
            metadata: Metadata del producto con calculo_precio anterior
        
        Returns:
            float: Nuevo precio de venta
        """
        # Usar el mismo cálculo que el módulo de precios
        calculo_anterior = metadata.get('calculo_precio', {})
        
        # Obtener parámetros del cálculo anterior
        cargos_fijos = calculo_anterior.get('cargos_fijos', 6500)
        margen_porcentaje = calculo_anterior.get('margen_porcentaje', 50)
        
        # Recalcular
        subtotal = precio_costo + cargos_fijos
        precio_con_margen = subtotal * (1 + margen_porcentaje / 100)
        
        # Redondear al múltiplo de 500 superior
        multiplo = 500
        resto = precio_con_margen % multiplo
        if resto == 0:
            precio_final = precio_con_margen
        else:
            precio_final = precio_con_margen + (multiplo - resto)
        
        return precio_final
    
    def actualizar_producto(self, sku: str, cambio_stock: Dict = None, cambio_precio: Dict = None) -> bool:
        """
        Actualiza metadata de un producto
        
        Args:
            sku: SKU del producto
            cambio_stock: Datos del cambio de stock (opcional)
            cambio_precio: Datos del cambio de precio (opcional)
        
        Returns:
            bool: True si se actualizó correctamente
        """
        try:
            # Cargar metadata
            metadata = Config.cargar_metadata(sku)
            
            cambios_realizados = []
            
            # Actualizar stock
            if cambio_stock:
                estado = cambio_stock['estado'].lower()
                
                if 'agotado' in estado:
                    metadata['stock'] = 0
                    cambios_realizados.append('stock=0 (agotado)')
                    self.estadisticas['agotados'] += 1
                elif 'reingresado' in estado or 'disponible' in estado:
                    metadata['stock'] = 10  # Stock genérico
                    cambios_realizados.append('stock=10 (reingresado)')
                    self.estadisticas['reingresados'] += 1
            
            # Actualizar precio
            if cambio_precio:
                precio_nuevo = cambio_precio['precio_droppers']
                precio_anterior = metadata.get('precio', 0)
                
                if precio_nuevo != precio_anterior:
                    metadata['precio'] = precio_nuevo
                    
                    # Recalcular precio de venta
                    precio_venta_nuevo = self.recalcular_precio_venta(precio_nuevo, metadata)
                    precio_venta_anterior = metadata.get('precio_venta', 0)
                    
                    metadata['precio_venta'] = precio_venta_nuevo
                    
                    # Actualizar calculo_precio
                    if 'calculo_precio' in metadata:
                        metadata['calculo_precio']['precio_costo'] = precio_nuevo
                        metadata['calculo_precio']['precio_final'] = precio_venta_nuevo
                        metadata['calculo_precio']['ganancia_neta'] = precio_venta_nuevo - precio_nuevo
                    
                    cambios_realizados.append(
                        f'precio: ${precio_anterior:,.0f} → ${precio_nuevo:,.0f}'
                    )
                    cambios_realizados.append(
                        f'precio_venta: ${precio_venta_anterior:,.0f} → ${precio_venta_nuevo:,.0f}'
                    )
                    
                    self.estadisticas['precios_actualizados'] += 1
            
            if cambios_realizados:
                # Agregar fecha de actualización
                metadata['fecha_sincronizacion_droppers'] = datetime.now().isoformat()
                
                # Guardar
                Config.guardar_metadata(sku, metadata)
                
                logger.info(f"✅ {sku}: {', '.join(cambios_realizados)}")
                return True
            else:
                self.estadisticas['productos_sin_cambios'] += 1
                return False
                
        except Exception as e:
            logger.error(f"Error actualizando {sku}: {e}")
            self.estadisticas['errores'] += 1
            return False
    
    def sincronizar(self):
        """Ejecuta la sincronización completa"""
        print(f"\n{'=' * 80}")
        print("🔄 SINCRONIZACIÓN CON DROPPERS")
        print(f"{'=' * 80}")
        
        # Login
        if not self.login():
            print("\n❌ No se pudo conectar a Droppers")
            return
        
        # Obtener informes
        cambios_stock, cambios_precios = self.obtener_informes()
        
        if not cambios_stock and not cambios_precios:
            print("\n✅ No hay cambios que sincronizar")
            return
        
        # Crear diccionarios por SKU
        stock_por_sku = {c['sku']: c for c in cambios_stock}
        precios_por_sku = {c['sku']: c for c in cambios_precios}
        
        # Combinar todos los SKUs afectados
        skus_afectados = set(stock_por_sku.keys()) | set(precios_por_sku.keys())
        
        print(f"\n🔄 Actualizando {len(skus_afectados)} productos...")
        print(f"{'─' * 80}")
        
        # Procesar cada SKU
        for sku in skus_afectados:
            cambio_stock = stock_por_sku.get(sku)
            cambio_precio = precios_por_sku.get(sku)
            
            self.actualizar_producto(sku, cambio_stock, cambio_precio)
        
        # Mostrar resumen
        self.mostrar_resumen()
        
        # Generar reporte
        self.generar_reporte()
        
        # Avisar sobre Google Sheets
        print(f"\n{'─' * 80}")
        print("⚠️  IMPORTANTE: Ejecutar ahora:")
        print("   python 06_google_sheets_oauth.py")
        print("   Para actualizar Google Sheets y Facebook Catalog")
        print(f"{'=' * 80}")
    
    def mostrar_resumen(self):
        """Muestra resumen de la sincronización"""
        print(f"\n{'=' * 80}")
        print("📊 RESUMEN DE SINCRONIZACIÓN")
        print(f"{'=' * 80}")
        
        print(f"\n📦 Cambios de stock:")
        print(f"   ❌ Agotados: {self.estadisticas['agotados']}")
        print(f"   ✅ Reingresados: {self.estadisticas['reingresados']}")
        
        print(f"\n💰 Cambios de precio:")
        print(f"   📝 Actualizados: {self.estadisticas['precios_actualizados']}")
        
        if self.estadisticas['errores'] > 0:
            print(f"\n⚠️  Errores: {self.estadisticas['errores']}")
        
        # Listar SKUs agotados para copiar
        if self.estadisticas['agotados'] > 0:
            print(f"\n{'─' * 80}")
            print("📋 SKUs AGOTADOS (copiar para Facebook Marketplace):")
            print(f"{'─' * 80}")
            
            for cambio in self.cambios_stock:
                if 'agotado' in cambio['estado'].lower():
                    print(cambio['sku'])
    
    def generar_reporte(self):
        """Genera reporte JSON de la sincronización"""
        fecha = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
        reporte_file = Config.LOGS_DIR / f"reporte_sincronizacion_{fecha}.json"
        
        reporte = {
            'fecha': datetime.now().isoformat(),
            'estadisticas': self.estadisticas,
            'cambios_stock': self.cambios_stock,
            'cambios_precios': self.cambios_precios
        }
        
        with open(reporte_file, 'w', encoding='utf-8') as f:
            json.dump(reporte, f, indent=2, ensure_ascii=False)
        
        logger.info(f"📄 Reporte guardado en: {reporte_file}")
        print(f"\n📄 Reporte guardado en: {reporte_file}")


def main():
    """Ejecuta la sincronización"""
    sincronizador = SincronizadorDroppers()
    sincronizador.sincronizar()


if __name__ == "__main__":
    main()
