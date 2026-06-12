#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VALIDADOR DE SINCRONIZACIÓN SQLite
Compara resultados entre versión original y optimizada

AUTOR: Sistema Ecommerce Automation
FECHA: 2026-03-04
"""

import sqlite3
import sys
from pathlib import Path
from datetime import datetime

sys.path.append(str(Path(__file__).parent))
from utils.config import Config


class ValidadorSQLite:
    """Valida que la sincronización fue correcta"""
    
    def __init__(self, db_path=None):
        if db_path is None:
            db_path = Config.DATA_DIR / 'catalogo.db'
        
        self.db_path = db_path
        self.errores = []
        self.advertencias = []
        self.conn = None
    
    def conectar(self):
        """Conecta a la DB"""
        try:
            self.conn = sqlite3.connect(self.db_path)
            self.conn.row_factory = sqlite3.Row
            return True
        except Exception as e:
            print(f"❌ Error conectando: {e}")
            return False
    
    def validar_estructura(self):
        """Valida que existan todas las tablas"""
        print("\n🔍 Validando estructura...")
        
        cursor = self.conn.cursor()
        
        tablas_requeridas = [
            'productos',
            'clientes',
            'ordenes',
            'orden_items',
            'historial_precios'
        ]
        
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tablas_existentes = [row[0] for row in cursor.fetchall()]
        
        for tabla in tablas_requeridas:
            if tabla in tablas_existentes:
                print(f"  ✅ Tabla '{tabla}' existe")
            else:
                error = f"Falta tabla '{tabla}'"
                print(f"  ❌ {error}")
                self.errores.append(error)
        
        return len(self.errores) == 0
    
    def validar_productos(self):
        """Valida datos de productos"""
        print("\n🔍 Validando productos...")
        
        cursor = self.conn.cursor()
        
        # 1. Total productos
        cursor.execute("SELECT COUNT(*) as total FROM productos")
        total = cursor.fetchone()['total']
        print(f"  📦 Total productos: {total}")
        
        if total == 0:
            self.errores.append("DB sin productos")
            return False
        
        if total < 50:
            self.advertencias.append(f"Pocos productos ({total})")
        
        # 2. Productos con precio
        cursor.execute("SELECT COUNT(*) as total FROM productos WHERE precio_venta > 0")
        con_precio = cursor.fetchone()['total']
        print(f"  💰 Con precio: {con_precio}")
        
        if con_precio < total * 0.9:
            self.advertencias.append(f"{total - con_precio} productos sin precio")
        
        # 3. Productos con imágenes
        cursor.execute("SELECT COUNT(*) as total FROM productos WHERE imagen_principal != ''")
        con_imagenes = cursor.fetchone()['total']
        print(f"  🖼️  Con imágenes: {con_imagenes}")
        
        if con_imagenes < total * 0.8:
            self.advertencias.append(f"{total - con_imagenes} productos sin imagen")
        
        # 4. Productos con categoría
        cursor.execute("SELECT COUNT(*) as total FROM productos WHERE categoria != '' AND categoria IS NOT NULL")
        con_categoria = cursor.fetchone()['total']
        print(f"  📁 Con categoría: {con_categoria}")
        
        if con_categoria < total * 0.5:
            self.advertencias.append(f"{total - con_categoria} productos sin categoría")
        
        # 5. Rango de precios
        cursor.execute("SELECT MIN(precio_venta) as min, MAX(precio_venta) as max FROM productos WHERE precio_venta > 0")
        row = cursor.fetchone()
        print(f"  💵 Rango precios: ${row['min']:,.0f} - ${row['max']:,.0f}")
        
        if row['min'] < 100:
            self.advertencias.append(f"Precio mínimo sospechoso (${row['min']})")
        
        return True
    
    def validar_integridad(self):
        """Valida integridad referencial"""
        print("\n🔍 Validando integridad...")
        
        cursor = self.conn.cursor()
        
        # Verificar que no haya SKUs duplicados
        cursor.execute("""
            SELECT sku, COUNT(*) as count 
            FROM productos 
            GROUP BY sku 
            HAVING count > 1
        """)
        duplicados = cursor.fetchall()
        
        if duplicados:
            for dup in duplicados:
                error = f"SKU duplicado: {dup['sku']} ({dup['count']} veces)"
                print(f"  ❌ {error}")
                self.errores.append(error)
        else:
            print("  ✅ Sin SKUs duplicados")
        
        return len(duplicados) == 0
    
    def comparar_con_metadata(self):
        """Compara DB con archivos metadata.json"""
        print("\n🔍 Comparando DB vs metadata...")
        
        # SKUs en metadata
        productos_dir = Config.PRODUCTOS_DIR
        skus_metadata = set()
        skus_disponibles = set()
        
        for carpeta in productos_dir.iterdir():
            if not carpeta.is_dir():
                continue
            
            metadata_file = carpeta / 'metadata.json'
            if not metadata_file.exists():
                continue
            
            import json
            try:
                with open(metadata_file, 'r', encoding='utf-8') as f:
                    metadata = json.load(f)
                
                sku = metadata.get('sku', carpeta.name)
                skus_metadata.add(sku)
                
                # Verificar disponibilidad
                disponibilidad = metadata.get('disponibilidad', 'in stock')
                if disponibilidad != 'out of stock':
                    # Verificar precio
                    precio_venta = metadata.get('precio_venta', 0)
                    if precio_venta > 0:
                        skus_disponibles.add(sku)
            
            except Exception as e:
                pass
        
        # SKUs en DB
        cursor = self.conn.cursor()
        cursor.execute("SELECT sku FROM productos")
        skus_db = set(row[0] for row in cursor.fetchall())
        
        print(f"  📦 Metadata: {len(skus_metadata)} productos")
        print(f"  📦 Disponibles con precio: {len(skus_disponibles)} productos")
        print(f"  💾 Base de datos: {len(skus_db)} productos")
        
        # Comparar
        solo_metadata = skus_disponibles - skus_db
        solo_db = skus_db - skus_disponibles
        
        if solo_metadata:
            adv = f"{len(solo_metadata)} productos en metadata pero no en DB"
            print(f"  ⚠️  {adv}")
            self.advertencias.append(adv)
            
            if len(solo_metadata) <= 5:
                print(f"      SKUs: {', '.join(list(solo_metadata)[:5])}")
        
        if solo_db:
            adv = f"{len(solo_db)} productos en DB pero no en metadata disponible"
            print(f"  ⚠️  {adv}")
            self.advertencias.append(adv)
        
        if not solo_metadata and not solo_db:
            print("  ✅ Metadata y DB coinciden perfectamente")
        
        return True
    
    def ejecutar_validacion_completa(self):
        """Ejecuta todas las validaciones"""
        print("\n" + "=" * 80)
        print("🔍 VALIDACIÓN DE SINCRONIZACIÓN SQLite")
        print("=" * 80)
        print(f"DB: {self.db_path}")
        print(f"Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        if not self.conectar():
            return False
        
        # Ejecutar validaciones
        self.validar_estructura()
        self.validar_productos()
        self.validar_integridad()
        self.comparar_con_metadata()
        
        # Resumen
        print("\n" + "=" * 80)
        print("📊 RESULTADO DE VALIDACIÓN")
        print("=" * 80)
        
        if self.errores:
            print(f"\n❌ ERRORES ({len(self.errores)}):")
            for error in self.errores:
                print(f"  • {error}")
        
        if self.advertencias:
            print(f"\n⚠️  ADVERTENCIAS ({len(self.advertencias)}):")
            for adv in self.advertencias[:10]:
                print(f"  • {adv}")
            if len(self.advertencias) > 10:
                print(f"  ... y {len(self.advertencias) - 10} más")
        
        if not self.errores and not self.advertencias:
            print("\n✅ VALIDACIÓN EXITOSA - Sin errores ni advertencias")
        elif not self.errores:
            print("\n✅ VALIDACIÓN EXITOSA - Solo advertencias menores")
        else:
            print("\n❌ VALIDACIÓN FALLIDA - Requiere corrección")
        
        print("=" * 80 + "\n")
        
        self.conn.close()
        
        return len(self.errores) == 0


def main():
    """Ejecuta validación"""
    validador = ValidadorSQLite()
    exitoso = validador.ejecutar_validacion_completa()
    
    return 0 if exitoso else 1


if __name__ == "__main__":
    sys.exit(main())
