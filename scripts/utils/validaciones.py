#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VALIDACIONES DE PRODUCTOS
Verifica que los datos extraídos sean correctos
"""

import re
from typing import Dict, List, Tuple

class ValidadorProducto:
    """Valida datos de productos scrapeados"""
    
    @staticmethod
    def validar_sku(sku: str) -> Tuple[bool, str]:
        """
        Valida que el SKU sea correcto
        
        Returns:
            (bool, str): (es_valido, mensaje_error)
        """
        if not sku:
            return False, "SKU vacío"
        
        if len(sku) < 3:
            return False, f"SKU muy corto: '{sku}'"
        
        # SKUs de Droppers suelen ser formato: DL#### o similar
        if not re.match(r'^[A-Z0-9\-_]+$', sku, re.IGNORECASE):
            return False, f"SKU con caracteres inválidos: '{sku}'"
        
        return True, ""
    
    @staticmethod
    def validar_titulo(titulo: str) -> Tuple[bool, str]:
        """Valida que el título sea correcto"""
        if not titulo:
            return False, "Título vacío"
        
        if len(titulo) < 5:
            return False, f"Título muy corto: '{titulo}'"
        
        if len(titulo) > 200:
            return False, f"Título muy largo ({len(titulo)} caracteres)"
        
        return True, ""
    
    @staticmethod
    def validar_precio(precio: int) -> Tuple[bool, str]:
        """Valida que el precio sea correcto"""
        if precio is None:
            return False, "Precio es None"
        
        if not isinstance(precio, (int, float)):
            return False, f"Precio debe ser numérico, recibido: {type(precio)}"
        
        if precio <= 0:
            return False, f"Precio debe ser positivo: {precio}"
        
        if precio > 10000000:  # 10 millones
            return False, f"Precio sospechosamente alto: {precio}"
        
        return True, ""
    
    @staticmethod
    def validar_descripcion(descripcion: str) -> Tuple[bool, str]:
        """Valida que la descripción sea correcta"""
        if not descripcion:
            return False, "Descripción vacía"
        
        if len(descripcion) < 10:
            return False, f"Descripción muy corta: '{descripcion}'"
        
        return True, ""
    
    @staticmethod
    def validar_imagenes(imagenes: List[str]) -> Tuple[bool, str]:
        """Valida que las imágenes sean correctas"""
        if not imagenes:
            return False, "No hay imágenes"
        
        if not isinstance(imagenes, list):
            return False, f"Imágenes debe ser una lista, recibido: {type(imagenes)}"
        
        # Validar que sean URLs
        for i, img in enumerate(imagenes):
            if not img.startswith('http'):
                return False, f"Imagen {i+1} no es URL válida: '{img}'"
        
        return True, ""
    
    @staticmethod
    def validar_producto_completo(datos: Dict) -> Dict:
        """
        Valida un producto completo
        
        Args:
            datos (dict): Diccionario con datos del producto
        
        Returns:
            dict: {
                'valido': bool,
                'errores': list,
                'advertencias': list
            }
        """
        errores = []
        advertencias = []
        
        # Validar SKU (obligatorio)
        if 'sku' in datos:
            valido, msg = ValidadorProducto.validar_sku(datos['sku'])
            if not valido:
                errores.append(f"SKU: {msg}")
        else:
            errores.append("SKU: Campo faltante")
        
        # Validar título (obligatorio)
        if 'titulo' in datos:
            valido, msg = ValidadorProducto.validar_titulo(datos['titulo'])
            if not valido:
                errores.append(f"Título: {msg}")
        else:
            errores.append("Título: Campo faltante")
        
        # Validar precio (obligatorio)
        if 'precio' in datos:
            valido, msg = ValidadorProducto.validar_precio(datos['precio'])
            if not valido:
                errores.append(f"Precio: {msg}")
        else:
            errores.append("Precio: Campo faltante")
        
        # Validar descripción (obligatorio)
        if 'descripcion' in datos:
            valido, msg = ValidadorProducto.validar_descripcion(datos['descripcion'])
            if not valido:
                # Descripción corta es advertencia, no error
                advertencias.append(f"Descripción: {msg}")
        else:
            advertencias.append("Descripción: Campo faltante")
        
        # Validar imágenes (obligatorio)
        if 'imagenes' in datos:
            valido, msg = ValidadorProducto.validar_imagenes(datos['imagenes'])
            if not valido:
                errores.append(f"Imágenes: {msg}")
        else:
            errores.append("Imágenes: Campo faltante")
        
        # Validar URL original (opcional pero recomendado)
        if 'url_original' not in datos:
            advertencias.append("URL original: Campo faltante")
        
        return {
            'valido': len(errores) == 0,
            'errores': errores,
            'advertencias': advertencias
        }


if __name__ == "__main__":
    # Tests
    print("=" * 80)
    print("TESTS DE VALIDACIÓN")
    print("=" * 80)
    
    # Test 1: Producto válido
    producto_ok = {
        'sku': 'DL1091',
        'titulo': 'Atrapa Pelos para Laundry x4',
        'precio': 1870,
        'descripcion': 'Atrapa pelos para laundry. Pack x4 unidades.',
        'imagenes': ['https://droppers.com.ar/media/img1.jpg'],
        'url_original': 'https://droppers.com.ar/producto.html'
    }
    
    resultado = ValidadorProducto.validar_producto_completo(producto_ok)
    print(f"\n✅ Test 1 - Producto válido:")
    print(f"   Válido: {resultado['valido']}")
    print(f"   Errores: {resultado['errores']}")
    print(f"   Advertencias: {resultado['advertencias']}")
    
    # Test 2: Producto con errores
    producto_mal = {
        'sku': 'DL',  # SKU muy corto
        'titulo': 'ABC',  # Título muy corto
        'precio': -100,  # Precio negativo
        'descripcion': 'Corta',  # Descripción muy corta
        'imagenes': []  # Sin imágenes
    }
    
    resultado = ValidadorProducto.validar_producto_completo(producto_mal)
    print(f"\n❌ Test 2 - Producto con errores:")
    print(f"   Válido: {resultado['valido']}")
    print(f"   Errores:")
    for error in resultado['errores']:
        print(f"     - {error}")
    
    print("\n" + "=" * 80)
