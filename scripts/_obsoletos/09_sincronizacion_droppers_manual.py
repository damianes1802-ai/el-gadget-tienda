#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MÓDULO DE SINCRONIZACIÓN CON DROPPERS - VERSIÓN MANUAL
Procesa archivo HTML descargado manualmente desde la página de informes
"""

import json
from bs4 import BeautifulSoup
from datetime import datetime
from pathlib import Path
from typing import Dict, List
import re

# Imports locales
import sys
sys.path.append(str(Path(__file__).parent))
from utils.config import Config
from utils.logger import get_logger

logger = get_logger('sincronizacion_droppers_manual')


class SincronizadorDroppersManual:
    """Sincroniza stock y precios desde archivo HTML manual"""
    
    def __init__(self):
        """Inicializa el sincronizador"""
        # Archivo HTML por defecto
        self.html_file = Config.CONFIG_DIR / 'html_informes_droppers.html'
        
        self.cambios_stock = []
        self.cambios_precios = []
        self.productos_nuevos = []  # Lista de productos no encontrados
        
        self.estadisticas = {
            'agotados': 0,
            'reingresados': 0,
            'precios_actualizados': 0,
            'productos_sin_cambios': 0,
            'productos_nuevos': 0,
            'errores': 0
        }
        
        logger.info("Sincronizador manual inicializado")
    
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
            
            # Buscar el div con "Cambios de stock"
            titulo_stock = soup.find(string=lambda text: text and 'Cambios de stock' in text)
            
            if not titulo_stock:
                logger.warning("No se encontró la sección 'Cambios de stock'")
                return []
            
            # Encontrar la tabla siguiente
            container = titulo_stock.find_parent()
            tabla = container.find_next('table')
            
            if not tabla:
                logger.warning("No se encontró tabla de stock")
                return []
            
            # Procesar filas
            filas = tabla.find_all('tr')[1:]  # Saltar header
            
            for fila in filas:
                celdas = fila.find_all('td')
                
                if len(celdas) >= 4:
                    sku = celdas[0].get_text().strip()
                    producto = celdas[1].get_text().strip()
                    estado = celdas[2].get_text().strip()
                    fecha = celdas[3].get_text().strip()
                    
                    cambios.append({
                        'sku': sku,
                        'producto': producto,
                        'estado': estado,
                        'fecha': fecha
                    })
            
            logger.info(f"✅ Extraídos {len(cambios)} cambios de stock")
            return cambios
            
        except Exception as e:
            logger.error(f"Error extrayendo cambios de stock: {e}")
            import traceback
            traceback.print_exc()
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
            
            # Buscar el div con "Cambios de precio"
            titulo_precio = soup.find(string=lambda text: text and 'Cambios de precio' in text)
            
            if not titulo_precio:
                logger.warning("No se encontró la sección 'Cambios de precio'")
                return []
            
            # Encontrar la tabla siguiente
            container = titulo_precio.find_parent()
            tabla = container.find_next('table')
            
            if not tabla:
                logger.warning("No se encontró tabla de precios")
                return []
            
            # Procesar filas
            filas = tabla.find_all('tr')[1:]  # Saltar header
            
            for fila in filas:
                celdas = fila.find_all('td')
                
                if len(celdas) >= 5:
                    sku = celdas[0].get_text().strip()
                    producto = celdas[1].get_text().strip()
                    precio_droppers_text = celdas[2].get_text().strip()
                    precio_sugerido_text = celdas[3].get_text().strip()
                    fecha = celdas[4].get_text().strip()
                    
                    # Limpiar precios (quitar $ y ,)
                    try:
                        # Remover todo excepto dígitos y punto decimal
                        # El formato es: $38500,00 o $38.500,00
                        precio_droppers_limpio = precio_droppers_text.replace('$', '').replace('.', '').replace(',', '.')
                        precio_sugerido_limpio = precio_sugerido_text.replace('$', '').replace('.', '').replace(',', '.')
                        
                        precio_droppers = float(precio_droppers_limpio)
                        precio_sugerido = float(precio_sugerido_limpio)
                        
                        cambios.append({
                            'sku': sku,
                            'producto': producto,
                            'precio_droppers': precio_droppers,
                            'precio_sugerido': precio_sugerido,
                            'fecha': fecha
                        })
                    except ValueError as e:
                        logger.warning(f"Error parseando precio para {sku}: {e}")
            
            logger.info(f"✅ Extraídos {len(cambios)} cambios de precios")
            return cambios
            
        except Exception as e:
            logger.error(f"Error extrayendo cambios de precios: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    def cargar_informes(self):
        """Carga y procesa el archivo HTML"""
        if not self.html_file.exists():
            print(f"\n❌ ERROR: Archivo no encontrado")
            print(f"   Esperado en: {self.html_file}")
            print(f"\n📋 INSTRUCCIONES:")
            print(f"   1. Abre tu navegador")
            print(f"   2. Ve a: https://droppers.com.ar/alerts/customer/index/")
            print(f"   3. Click derecho → 'Guardar como' o Ctrl+S")
            print(f"   4. Guarda el HTML en: {self.html_file}")
            print(f"   5. Ejecuta este script de nuevo")
            return False
        
        print(f"\n📄 Cargando archivo: {self.html_file}")
        
        with open(self.html_file, 'r', encoding='utf-8') as f:
            html = f.read()
        
        print(f"   Tamaño: {len(html):,} bytes")
        
        print("\n🔍 Extrayendo cambios de stock...")
        self.cambios_stock = self.extraer_cambios_stock(html)
        print(f"   ✅ {len(self.cambios_stock)} cambios encontrados")
        
        print("\n🔍 Extrayendo cambios de precios...")
        self.cambios_precios = self.extraer_cambios_precios(html)
        print(f"   ✅ {len(self.cambios_precios)} cambios encontrados")
        
        return True
    
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
            # Intentar cargar metadata
            try:
                metadata = Config.cargar_metadata(sku)
            except:
                # Producto nuevo - no existe en nuestra base de datos
                producto_nombre = cambio_stock.get('producto') if cambio_stock else cambio_precio.get('producto') if cambio_precio else 'Desconocido'
                
                self.productos_nuevos.append({
                    'sku': sku,
                    'producto': producto_nombre,
                    'tiene_cambio_stock': cambio_stock is not None,
                    'tiene_cambio_precio': cambio_precio is not None,
                    'estado': cambio_stock.get('estado') if cambio_stock else None,
                    'precio': cambio_precio.get('precio_droppers') if cambio_precio else None
                })
                
                self.estadisticas['productos_nuevos'] += 1
                logger.warning(f"⚠️  Producto nuevo no encontrado en base de datos: {sku}")
                return False
            
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
        print("🔄 SINCRONIZACIÓN CON DROPPERS (MANUAL)")
        print(f"{'=' * 80}")
        
        # Cargar archivo HTML
        if not self.cargar_informes():
            return
        
        if not self.cambios_stock and not self.cambios_precios:
            print("\n✅ No hay cambios que sincronizar")
            return
        
        # Crear diccionarios por SKU
        stock_por_sku = {c['sku']: c for c in self.cambios_stock}
        precios_por_sku = {c['sku']: c for c in self.cambios_precios}
        
        # Combinar todos los SKUs afectados
        skus_afectados = set(stock_por_sku.keys()) | set(precios_por_sku.keys())
        
        print(f"\n🔄 Actualizando {len(skus_afectados)} productos...")
        print(f"{'─' * 80}")
        
        # Procesar cada SKU
        for i, sku in enumerate(skus_afectados, 1):
            cambio_stock = stock_por_sku.get(sku)
            cambio_precio = precios_por_sku.get(sku)
            
            print(f"[{i}/{len(skus_afectados)}] {sku}...", end=' ')
            
            if self.actualizar_producto(sku, cambio_stock, cambio_precio):
                print("✅")
            else:
                print("⚠️")
        
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
        
        # ESTADÍSTICAS GENERALES
        print(f"\n📈 ESTADÍSTICAS GENERALES:")
        print(f"   Total productos procesados: {self.estadisticas['agotados'] + self.estadisticas['reingresados'] + self.estadisticas['precios_actualizados']}")
        print(f"   ❌ Agotados: {self.estadisticas['agotados']}")
        print(f"   ✅ Reingresados: {self.estadisticas['reingresados']}")
        print(f"   💰 Precios actualizados: {self.estadisticas['precios_actualizados']}")
        
        if self.estadisticas['productos_nuevos'] > 0:
            print(f"   🆕 Productos nuevos detectados: {self.estadisticas['productos_nuevos']}")
        
        if self.estadisticas['errores'] > 0:
            print(f"   ⚠️  Errores: {self.estadisticas['errores']}")
        
        # LISTA DETALLADA: PRODUCTOS AGOTADOS
        agotados = [c for c in self.cambios_stock if 'agotado' in c['estado'].lower()]
        if agotados:
            print(f"\n{'─' * 80}")
            print(f"❌ PRODUCTOS AGOTADOS ({len(agotados)}):")
            print(f"{'─' * 80}")
            print(f"{'SKU':<20} {'Producto':<45} {'Fecha'}")
            print(f"{'─' * 80}")
            
            for cambio in sorted(agotados, key=lambda x: x['sku']):
                sku = cambio['sku'][:20]
                producto = cambio['producto'][:45]
                fecha = cambio['fecha']
                print(f"{sku:<20} {producto:<45} {fecha}")
            
            print(f"\n📋 SKUs para copiar (formato lista):")
            print(f"{'─' * 80}")
            for cambio in sorted(agotados, key=lambda x: x['sku']):
                print(cambio['sku'])
        
        # LISTA DETALLADA: PRODUCTOS REINGRESADOS
        reingresados = [c for c in self.cambios_stock if 'reingresado' in c['estado'].lower() or 'disponible' in c['estado'].lower()]
        if reingresados:
            print(f"\n{'─' * 80}")
            print(f"✅ PRODUCTOS REINGRESADOS ({len(reingresados)}):")
            print(f"{'─' * 80}")
            print(f"{'SKU':<20} {'Producto':<45} {'Fecha'}")
            print(f"{'─' * 80}")
            
            for cambio in sorted(reingresados, key=lambda x: x['sku']):
                sku = cambio['sku'][:20]
                producto = cambio['producto'][:45]
                fecha = cambio['fecha']
                print(f"{sku:<20} {producto:<45} {fecha}")
            
            print(f"\n📋 SKUs para copiar (formato lista):")
            print(f"{'─' * 80}")
            for cambio in sorted(reingresados, key=lambda x: x['sku']):
                print(cambio['sku'])
        
        # LISTA DETALLADA: CAMBIOS DE PRECIO
        if self.cambios_precios:
            # Filtrar solo los que realmente se actualizaron
            precios_actualizados = []
            
            for cambio in self.cambios_precios:
                try:
                    metadata = Config.cargar_metadata(cambio['sku'])
                    # Solo incluir si el precio cambió realmente
                    if metadata.get('precio', 0) != cambio['precio_droppers']:
                        precios_actualizados.append(cambio)
                except:
                    # Producto no existe en metadata, no mostrar
                    pass
            
            if precios_actualizados:
                print(f"\n{'─' * 80}")
                print(f"💰 CAMBIOS DE PRECIO ({len(precios_actualizados)}):")
                print(f"{'─' * 80}")
                
                for cambio in sorted(precios_actualizados, key=lambda x: x['sku']):
                    try:
                        metadata = Config.cargar_metadata(cambio['sku'])
                        
                        sku = cambio['sku']
                        producto = cambio['producto'][:50]
                        
                        # Obtener precios
                        precio_anterior = metadata.get('precio', 0)
                        precio_nuevo = cambio['precio_droppers']
                        precio_venta_anterior = metadata.get('precio_venta', 0)
                        precio_venta_nuevo = self.recalcular_precio_venta(precio_nuevo, metadata)
                        
                        # Calcular cambios
                        cambio_costo = precio_nuevo - precio_anterior
                        pct_costo = (cambio_costo / precio_anterior * 100) if precio_anterior > 0 else 0
                        
                        cambio_venta = precio_venta_nuevo - precio_venta_anterior
                        pct_venta = (cambio_venta / precio_venta_anterior * 100) if precio_venta_anterior > 0 else 0
                        
                        print(f"\n📦 {sku} - {producto}")
                        print(f"   {'─' * 76}")
                        print(f"   PRECIO DE COSTO:")
                        print(f"      Anterior: ${precio_anterior:>12,.0f}")
                        print(f"      Nuevo:    ${precio_nuevo:>12,.0f}")
                        
                        if cambio_costo > 0:
                            print(f"      Cambio:   +${cambio_costo:>11,.0f} ({pct_costo:+.1f}%)")
                        else:
                            print(f"      Cambio:   -${abs(cambio_costo):>11,.0f} ({pct_costo:.1f}%)")
                        
                        print(f"\n   PRECIO DE VENTA (recalculado):")
                        print(f"      Anterior: ${precio_venta_anterior:>12,.0f}")
                        print(f"      Nuevo:    ${precio_venta_nuevo:>12,.0f}")
                        
                        if cambio_venta > 0:
                            print(f"      Cambio:   +${cambio_venta:>11,.0f} ({pct_venta:+.1f}%)")
                        else:
                            print(f"      Cambio:   -${abs(cambio_venta):>11,.0f} ({pct_venta:.1f}%)")
                        
                        # Ganancia
                        ganancia = precio_venta_nuevo - precio_nuevo
                        margen = (ganancia / precio_venta_nuevo * 100) if precio_venta_nuevo > 0 else 0
                        print(f"\n   GANANCIA: ${ganancia:,.0f} ({margen:.1f}%)")
                        
                    except Exception as e:
                        logger.error(f"Error mostrando precio para {cambio['sku']}: {e}")
            else:
                print(f"\n💰 Cambios de precio: Sin actualizaciones reales")
        
        # LISTA DETALLADA: PRODUCTOS NUEVOS
        if self.productos_nuevos:
            print(f"\n{'─' * 80}")
            print(f"🆕 PRODUCTOS NUEVOS NO ENCONTRADOS EN BASE DE DATOS ({len(self.productos_nuevos)}):")
            print(f"{'─' * 80}")
            print(f"{'SKU':<20} {'Producto':<40} {'Info'}")
            print(f"{'─' * 80}")
            
            for prod in sorted(self.productos_nuevos, key=lambda x: x['sku']):
                sku = prod['sku'][:20]
                producto = prod['producto'][:40]
                
                # Construir info
                info_parts = []
                if prod['tiene_cambio_stock']:
                    estado = prod.get('estado', '').lower()
                    if 'agotado' in estado:
                        info_parts.append("Agotado")
                    elif 'reingresado' in estado:
                        info_parts.append("Reingresado")
                
                if prod['tiene_cambio_precio']:
                    precio = prod.get('precio')
                    if precio:
                        info_parts.append(f"Precio: ${precio:,.0f}")
                
                info = " | ".join(info_parts) if info_parts else "Sin info adicional"
                
                print(f"{sku:<20} {producto:<40} {info}")
            
            print(f"\n⚠️  ACCIÓN REQUERIDA:")
            print(f"   Estos productos NO están en tu base de datos.")
            print(f"   Deberías scrapearlos de Droppers para agregarlos al catálogo:")
            print(f"\n   📋 SKUs para scrapear:")
            print(f"   {'─' * 76}")
            for prod in sorted(self.productos_nuevos, key=lambda x: x['sku']):
                print(f"   {prod['sku']}")
        
        print(f"\n{'=' * 80}")
    
    def generar_reporte(self):
        """Genera reporte JSON de la sincronización"""
        fecha = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
        reporte_file = Config.LOGS_DIR / f"reporte_sincronizacion_{fecha}.json"
        
        reporte = {
            'fecha': datetime.now().isoformat(),
            'metodo': 'manual',
            'archivo_html': str(self.html_file),
            'estadisticas': self.estadisticas,
            'cambios_stock': self.cambios_stock,
            'cambios_precios': self.cambios_precios
        }
        
        with open(reporte_file, 'w', encoding='utf-8') as f:
            json.dump(reporte, f, indent=2, ensure_ascii=False)
        
        logger.info(f"📄 Reporte guardado en: {reporte_file}")
        print(f"\n📄 Reporte guardado en: {reporte_file}")


def main():
    """Ejecuta la sincronización manual"""
    sincronizador = SincronizadorDroppersManual()
    sincronizador.sincronizar()


if __name__ == "__main__":
    main()
