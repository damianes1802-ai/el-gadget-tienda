#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MÓDULO DE CÁLCULO DE PRECIOS
Aplica la configuración de precios a todos los productos scrapeados
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List
import math

# Imports locales
import sys
sys.path.append(str(Path(__file__).parent))
from utils.config import Config
from utils.logger import get_logger, LoggerManager

logger = get_logger('calculo_precios')


class CalculadorPrecios:
    """Calcula precios de venta basándose en la configuración"""
    
    def __init__(self):
        """Inicializa el calculador"""
        self.config_file = Config.PRECIOS_DIR / "config_precios_v2.json"
        self.cargar_configuracion()
        self.productos_procesados = []
        self.estadisticas = {
            'total': 0,
            'exitosos': 0,
            'fallidos': 0,
            'precio_min': float('inf'),
            'precio_max': 0,
            'precio_promedio': 0
        }
    
    def cargar_configuracion(self):
        """Carga la configuración de precios"""
        if not self.config_file.exists():
            logger.error(f"Archivo de configuración no encontrado: {self.config_file}")
            raise FileNotFoundError(
                f"Debe configurar precios primero. "
                f"Ejecutar: python config_precios_interactivo.py"
            )
        
        with open(self.config_file, 'r', encoding='utf-8') as f:
            self.config = json.load(f)
        
        logger.info("Configuración de precios cargada correctamente")
    
    def obtener_perfil_activo(self, sku: str, titulo: str, precio_costo: float) -> Dict:
        """
        Obtiene el perfil de precio aplicable para un producto
        
        Args:
            sku: SKU del producto
            titulo: Título del producto
            precio_costo: Precio de costo
        
        Returns:
            dict: Perfil de precio a aplicar
        """
        perfiles = self.config.get('perfiles_precio', {})
        
        # Por ahora, usar el perfil 'default'
        # En el futuro se pueden aplicar reglas de asignación
        perfil_id = 'default'
        
        # TODO: Implementar reglas de asignación automática
        # Ejemplo:
        # - Si precio_costo > 10000 → perfil 'premium'
        # - Si 'Oferta' in titulo → perfil 'oferta'
        # - etc.
        
        perfil = perfiles.get(perfil_id, perfiles.get('default'))
        
        if not perfil:
            logger.warning(f"No se encontró perfil para {sku}, usando configuración base")
            perfil = self._perfil_base()
        
        return perfil
    
    def _perfil_base(self) -> Dict:
        """Retorna un perfil base por defecto"""
        return {
            "nombre": "Base",
            "cargos_fijos": [],
            "margen_porcentaje": 50,
            "redondeo": {
                "activo": True,
                "multiplo": 500
            }
        }
    
    def calcular_precio_venta(self, precio_costo: float, perfil: Dict) -> Dict:
        """
        Calcula el precio de venta basándose en el perfil
        
        Args:
            precio_costo: Precio de costo del producto
            perfil: Perfil de precio a aplicar
        
        Returns:
            dict: Desglose del cálculo
        """
        # 1. Sumar cargos fijos activos
        cargos_activos = [c for c in perfil.get('cargos_fijos', []) if c.get('activo', True)]
        total_cargos = sum(c.get('valor', 0) for c in cargos_activos)
        
        # 2. Subtotal
        subtotal = precio_costo + total_cargos
        
        # 3. Aplicar margen
        margen_porcentaje = perfil.get('margen_porcentaje', 50)
        precio_con_margen = subtotal * (1 + margen_porcentaje / 100)
        
        # 4. Redondear
        redondeo = perfil.get('redondeo', {})
        if redondeo.get('activo', True):
            multiplo = redondeo.get('multiplo', 500)
            precio_final = self._redondear_comercial(precio_con_margen, multiplo)
        else:
            precio_final = precio_con_margen
        
        return {
            'precio_costo': precio_costo,
            'cargos_fijos': total_cargos,
            'desglose_cargos': [
                {
                    'nombre': c.get('nombre'),
                    'valor': c.get('valor')
                }
                for c in cargos_activos
            ],
            'subtotal': subtotal,
            'margen_porcentaje': margen_porcentaje,
            'precio_con_margen': precio_con_margen,
            'precio_final': precio_final,
            'ganancia_neta': precio_final - precio_costo,
            'perfil_aplicado': perfil.get('nombre', 'Sin nombre')
        }
    
    def _redondear_comercial(self, precio: float, multiplo: int) -> float:
        """
        Redondea un precio al múltiplo superior
        
        Args:
            precio: Precio a redondear
            multiplo: Múltiplo de redondeo (ej: 500)
        
        Returns:
            float: Precio redondeado
        """
        resto = precio % multiplo
        if resto == 0:
            return precio
        return precio + (multiplo - resto)
    
    def procesar_producto(self, sku: str) -> bool:
        """
        Procesa un producto y le calcula el precio de venta
        
        Args:
            sku: SKU del producto
        
        Returns:
            bool: True si se procesó correctamente
        """
        try:
            # Cargar metadata
            metadata = Config.cargar_metadata(sku)
            
            # Obtener perfil aplicable
            perfil = self.obtener_perfil_activo(
                sku,
                metadata.get('titulo', ''),
                metadata.get('precio', 0)
            )
            
            # Calcular precio
            calculo = self.calcular_precio_venta(metadata.get('precio', 0), perfil)
            
            # Actualizar metadata
            metadata['calculo_precio'] = calculo
            metadata['precio_venta'] = calculo['precio_final']
            metadata['fecha_calculo_precio'] = datetime.now().isoformat()
            
            # Guardar
            Config.guardar_metadata(sku, metadata)
            
            # Actualizar estadísticas
            self.estadisticas['exitosos'] += 1
            precio_final = calculo['precio_final']
            self.estadisticas['precio_min'] = min(self.estadisticas['precio_min'], precio_final)
            self.estadisticas['precio_max'] = max(self.estadisticas['precio_max'], precio_final)
            
            self.productos_procesados.append({
                'sku': sku,
                'titulo': metadata.get('titulo', '')[:50],
                'precio_costo': calculo['precio_costo'],
                'precio_venta': precio_final
            })
            
            logger.info(f"✅ {sku}: ${calculo['precio_costo']:,.0f} → ${precio_final:,.0f}")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Error procesando {sku}: {e}")
            self.estadisticas['fallidos'] += 1
            return False
    
    def procesar_todos(self):
        """Procesa todos los productos"""
        skus = Config.listar_productos()
        
        if not skus:
            logger.warning("No hay productos para procesar")
            print("\n⚠️  No se encontraron productos scrapeados")
            print("   Ejecutar primero: python 01_scraper.py")
            return
        
        self.estadisticas['total'] = len(skus)
        
        LoggerManager.log_inicio_proceso(logger, "Cálculo de Precios", len(skus))
        
        print(f"\n{'=' * 80}")
        print(f"💰 CALCULANDO PRECIOS PARA {len(skus)} PRODUCTOS")
        print(f"{'=' * 80}\n")
        
        for i, sku in enumerate(skus, 1):
            print(f"Procesando {i}/{len(skus)}: {sku}...", end=' ')
            if self.procesar_producto(sku):
                print("✅")
            else:
                print("❌")
        
        # Calcular precio promedio
        if self.productos_procesados:
            suma_precios = sum(p['precio_venta'] for p in self.productos_procesados)
            self.estadisticas['precio_promedio'] = suma_precios / len(self.productos_procesados)
        
        LoggerManager.log_fin_proceso(
            logger,
            "Cálculo de Precios",
            self.estadisticas['exitosos'],
            self.estadisticas['fallidos']
        )
        
        self.mostrar_resumen()
        self.generar_reporte()
    
    def mostrar_resumen(self):
        """Muestra un resumen de estadísticas"""
        print(f"\n{'=' * 80}")
        print("📊 RESUMEN DEL CÁLCULO DE PRECIOS")
        print(f"{'=' * 80}")
        print(f"\nTotal productos: {self.estadisticas['total']}")
        print(f"✅ Exitosos: {self.estadisticas['exitosos']}")
        print(f"❌ Fallidos: {self.estadisticas['fallidos']}")
        
        if self.estadisticas['exitosos'] > 0:
            print(f"\n💵 Rango de precios:")
            print(f"   Mínimo: ${self.estadisticas['precio_min']:,.0f}")
            print(f"   Máximo: ${self.estadisticas['precio_max']:,.0f}")
            print(f"   Promedio: ${self.estadisticas['precio_promedio']:,.0f}")
            
            # Mostrar algunos ejemplos
            print(f"\n📋 Ejemplos (primeros 10):")
            print(f"{'─' * 80}")
            print(f"{'SKU':<15} {'Título':<35} {'Costo':>12} {'Venta':>12}")
            print(f"{'─' * 80}")
            
            for producto in self.productos_procesados[:10]:
                print(
                    f"{producto['sku']:<15} "
                    f"{producto['titulo']:<35} "
                    f"${producto['precio_costo']:>10,.0f} "
                    f"${producto['precio_venta']:>10,.0f}"
                )
        
        print(f"{'=' * 80}")
    
    def generar_reporte(self):
        """Genera un reporte JSON con todos los resultados"""
        fecha = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
        reporte_file = Config.LOGS_DIR / f"reporte_precios_{fecha}.json"
        
        reporte = {
            'fecha': datetime.now().isoformat(),
            'configuracion_usada': self.config_file.name,
            'estadisticas': self.estadisticas,
            'productos': self.productos_procesados
        }
        
        with open(reporte_file, 'w', encoding='utf-8') as f:
            json.dump(reporte, f, indent=2, ensure_ascii=False)
        
        logger.info(f"📄 Reporte guardado en: {reporte_file}")
        print(f"\n📄 Reporte guardado en: {reporte_file}")


def main():
    """Ejecuta el cálculo de precios"""
    print("=" * 80)
    print("💰 MÓDULO DE CÁLCULO DE PRECIOS")
    print("=" * 80)
    
    calculador = CalculadorPrecios()
    
    # Mostrar configuración actual
    perfiles = calculador.config.get('perfiles_precio', {})
    perfil_default = perfiles.get('default', {})
    
    print(f"\n📋 Configuración actual:")
    print(f"   Perfil: {perfil_default.get('nombre', 'N/A')}")
    print(f"   Margen: {perfil_default.get('margen_porcentaje', 0)}%")
    
    cargos = perfil_default.get('cargos_fijos', [])
    if cargos:
        total_cargos = sum(c['valor'] for c in cargos if c.get('activo', True))
        print(f"   Cargos fijos: ${total_cargos:,.0f}")
    
    redondeo = perfil_default.get('redondeo', {})
    if redondeo.get('activo'):
        print(f"   Redondeo: Múltiplo de {redondeo.get('multiplo', 500)}")
    
    print(f"\n{'─' * 80}")
    confirmar = input("\n¿Procesar todos los productos? (s/n): ").lower()

    if confirmar == 's':
        calculador.procesar_todos()
    else:
        print("\nOperación cancelada")


if __name__ == "__main__":
    main()
