#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ANALIZADOR DE SIMILITUD PARA VARIANTES
Detecta patrones y calcula similitud entre títulos de productos
"""

import re
from typing import Dict, List, Tuple, Optional
from difflib import SequenceMatcher


class AnalizadorSimilitud:
    """Analiza similitud entre productos para detectar variantes"""
    
    # Patrones de variantes conocidos
    PATRONES = {
        'tallas': {
            'regex': r'\b(xxs|xs|s|m|l|xl|xxl|xxxl)\b',
            'palabras_clave': ['talle', 'talla', 'size', 'tamaño'],
            'ejemplos': ['S', 'M', 'L', 'XL']
        },
        'tallas_numericas': {
            'regex': r'\b(talle\s*)?(\d{1,3})\b',
            'palabras_clave': ['talle'],
            'ejemplos': ['38', '40', '42']
        },
        'longitud': {
            'regex': r'\b(\d+(?:\.\d+)?)\s?(cm|mm|m|mt|metros?)\b',
            'palabras_clave': ['largo', 'longitud', 'medida', 'altura'],
            'ejemplos': ['90cm', '160cm', '200cm', '1.5m']
        },
        'cantidad': {
            'regex': r'(?:pack\s?x?|x)?\s?(\d+)\s?(?:unidades?|uni|u|pcs?|piezas?)',
            'palabras_clave': ['pack', 'unidad', 'unidades', 'set'],
            'ejemplos': ['Pack x4', 'x2 unidades', '3 piezas']
        },
        'pack_simple': {
            'regex': r'(?:pack|set|combo)\s?x?(\d+)',
            'palabras_clave': ['pack', 'set', 'combo'],
            'ejemplos': ['Pack x4', 'Set x2']
        },
        'capacidad': {
            'regex': r'\b(\d+)\s?(gb|mb|tb|ml|l|cc|litros?)\b',
            'palabras_clave': ['capacidad', 'memoria'],
            'ejemplos': ['64GB', '128GB', '500ml', '2L']
        },
        'colores': {
            'lista': [
                'negro', 'ne', 'black', 'bl',
                'blanco', 'white',
                'rojo', 'ro', 'red',
                'azul', 'az', 'blue',
                'verde', 've', 'green', 'gr',
                'amarillo', 'am', 'yellow',
                'naranja', 'na', 'orange',
                'rosa', 'ros', 'pink',
                'violeta', 'vi', 'purple',
                'gris', 'grey', 'gray',
                'marron', 'ma', 'brown', 'br',
                'celeste', 'ce', 'cyan',
                'fucsia', 'fu', 'fuchsia',
                'lima', 'li', 'lime',
                'turquesa', 'tu', 'tur', 'turquoise',
                'beige', 'be',
                'plateado', 'pl', 'silver',
                'dorado', 'do', 'gold',
                'cobre', 'co', 'copper'
            ],
            'palabras_clave': ['color'],
            'regex': None  # Se construye dinámicamente
        },
        'modelos': {
            'regex': r'\b(modelo|mod|version|ver|v)\s?(\d+|[a-z])\b',
            'palabras_clave': ['modelo', 'version'],
            'ejemplos': ['Modelo 1', 'V2', 'Ver A']
        }
    }
    
    def __init__(self):
        """Inicializa el analizador"""
        # Construir regex de colores dinámicamente
        colores = self.PATRONES['colores']['lista']
        self.PATRONES['colores']['regex'] = r'\b(' + '|'.join(colores) + r')\b'
    
    @staticmethod
    def calcular_similitud(texto1: str, texto2: str) -> float:
        """
        Calcula similitud entre dos textos (0.0 a 1.0)
        
        Args:
            texto1: Primer texto
            texto2: Segundo texto
        
        Returns:
            float: Similitud (0.0 = diferentes, 1.0 = idénticos)
        """
        return SequenceMatcher(None, texto1.lower(), texto2.lower()).ratio()
    
    def normalizar_titulo(self, titulo: str) -> str:
        """
        Normaliza un título eliminando variantes
        
        Args:
            titulo: Título original
        
        Returns:
            str: Título normalizado (sin variantes)
        """
        titulo_norm = titulo.lower()
        
        # Eliminar patrones de variantes conocidos
        for patron_nombre, patron_info in self.PATRONES.items():
            if patron_info.get('regex'):
                titulo_norm = re.sub(patron_info['regex'], '', titulo_norm, flags=re.IGNORECASE)
        
        # Limpiar espacios múltiples
        titulo_norm = re.sub(r'\s+', ' ', titulo_norm).strip()
        
        return titulo_norm
    
    def detectar_patron_variante(self, titulo: str) -> Dict[str, any]:
        """
        Detecta qué tipo de variante tiene un producto
        
        Args:
            titulo: Título del producto
        
        Returns:
            dict: {
                'tipo': str,  # 'tallas', 'colores', etc.
                'valor': str,  # 'M', 'Rojo', etc.
                'confianza': float  # 0.0 a 1.0
            }
        """
        detecciones = []
        
        # Buscar tallas
        match = re.search(self.PATRONES['tallas']['regex'], titulo, re.IGNORECASE)
        if match:
            detecciones.append({
                'tipo': 'tallas',
                'valor': match.group(1).upper(),
                'confianza': 0.9,
                'posicion': match.start()
            })
        
        # Buscar colores
        match = re.search(self.PATRONES['colores']['regex'], titulo, re.IGNORECASE)
        if match:
            detecciones.append({
                'tipo': 'colores',
                'valor': match.group(1).title(),
                'confianza': 0.85,
                'posicion': match.start()
            })
        
        # Buscar longitud
        match = re.search(self.PATRONES['longitud']['regex'], titulo, re.IGNORECASE)
        if match:
            valor = f"{match.group(1)}{match.group(2)}"
            detecciones.append({
                'tipo': 'longitud',
                'valor': valor,
                'confianza': 0.9,
                'posicion': match.start()
            })
        
        # Buscar cantidad/pack
        match = re.search(self.PATRONES['pack_simple']['regex'], titulo, re.IGNORECASE)
        if match:
            detecciones.append({
                'tipo': 'cantidad',
                'valor': f"Pack x{match.group(1)}",
                'confianza': 0.85,
                'posicion': match.start()
            })
        
        # Buscar capacidad
        match = re.search(self.PATRONES['capacidad']['regex'], titulo, re.IGNORECASE)
        if match:
            valor = f"{match.group(1)}{match.group(2).upper()}"
            detecciones.append({
                'tipo': 'capacidad',
                'valor': valor,
                'confianza': 0.9,
                'posicion': match.start()
            })
        
        # Retornar la detección con mayor confianza
        if detecciones:
            # Ordenar por confianza
            detecciones.sort(key=lambda x: x['confianza'], reverse=True)
            return detecciones[0]
        
        return {
            'tipo': None,
            'valor': None,
            'confianza': 0.0
        }
    
    def extraer_variante_de_sku(self, sku: str) -> Optional[str]:
        """
        Intenta extraer información de variante del SKU
        
        Args:
            sku: SKU del producto
        
        Returns:
            str: Variante detectada o None
        """
        # Patrones comunes en SKUs
        patrones_sku = [
            r'-([SMLX]{1,3})$',  # DL1183-S, DL1183-XL
            r'-(\d+X\d+)$',  # DL1254-2X1
            r'-([A-Z]{2,4})$',  # 600003-CE, 600003-BLUE
            r'X(\d+)$',  # BWH0057-4-BRX4
        ]
        
        for patron in patrones_sku:
            match = re.search(patron, sku, re.IGNORECASE)
            if match:
                return match.group(1)
        
        return None
    
    def comparar_productos(self, prod1: Dict, prod2: Dict) -> Dict:
        """
        Compara dos productos para determinar si son variantes
        
        Args:
            prod1: Primer producto {sku, titulo, precio}
            prod2: Segundo producto {sku, titulo, precio}
        
        Returns:
            dict: {
                'son_variantes': bool,
                'similitud_titulo': float,
                'tipo_variante': str,
                'confianza': float
            }
        """
        # Normalizar títulos
        titulo1_norm = self.normalizar_titulo(prod1['titulo'])
        titulo2_norm = self.normalizar_titulo(prod2['titulo'])
        
        # Calcular similitud de títulos normalizados
        similitud = self.calcular_similitud(titulo1_norm, titulo2_norm)
        
        # Detectar patrones en títulos originales
        patron1 = self.detectar_patron_variante(prod1['titulo'])
        patron2 = self.detectar_patron_variante(prod2['titulo'])
        
        # Criterios para considerar variantes
        umbral_similitud = 0.80
        son_variantes = False
        tipo_variante = None
        confianza = 0.0
        
        # Caso 1: Títulos muy similares Y patrones detectados
        if similitud >= umbral_similitud:
            if patron1['tipo'] == patron2['tipo'] and patron1['tipo'] is not None:
                if patron1['valor'] != patron2['valor']:
                    son_variantes = True
                    tipo_variante = patron1['tipo']
                    confianza = min(similitud, patron1['confianza'])
        
        # Caso 2: SKUs similares
        if not son_variantes:
            # Extraer base del SKU (antes del último guión)
            sku1_base = re.sub(r'-[^-]+$', '', prod1['sku'])
            sku2_base = re.sub(r'-[^-]+$', '', prod2['sku'])
            
            if sku1_base == sku2_base and sku1_base != prod1['sku']:
                son_variantes = True
                tipo_variante = 'sku_pattern'
                confianza = 0.95
        
        return {
            'son_variantes': son_variantes,
            'similitud_titulo': similitud,
            'tipo_variante': tipo_variante,
            'confianza': confianza,
            'patron1': patron1,
            'patron2': patron2
        }
    
    def agrupar_productos_similares(self, productos: List[Dict], umbral: float = 0.80) -> List[List[Dict]]:
        """
        Agrupa productos similares en clusters
        
        Args:
            productos: Lista de productos
            umbral: Umbral de similitud mínimo
        
        Returns:
            list: Lista de grupos de productos
        """
        grupos = []
        procesados = set()
        
        for i, prod1 in enumerate(productos):
            if prod1['sku'] in procesados:
                continue
            
            grupo = [prod1]
            procesados.add(prod1['sku'])
            
            for j, prod2 in enumerate(productos[i+1:], i+1):
                if prod2['sku'] in procesados:
                    continue
                
                comparacion = self.comparar_productos(prod1, prod2)
                
                if comparacion['son_variantes']:
                    grupo.append(prod2)
                    procesados.add(prod2['sku'])
            
            # Solo agregar si hay más de un producto en el grupo
            if len(grupo) > 1:
                grupos.append(grupo)
        
        return grupos


if __name__ == "__main__":
    # Tests
    analizador = AnalizadorSimilitud()
    
    print("=" * 80)
    print("TESTS DEL ANALIZADOR DE SIMILITUD")
    print("=" * 80)
    
    # Test 1: Detección de patrones
    print("\n1. DETECCIÓN DE PATRONES:")
    titulos_test = [
        "Remera Deportiva Talle M",
        "Pinza Destapa Cañerías 90cm",
        "Atrapa Pelos Pack x4",
        "Consola R36S 64GB",
        "Guante Color Rojo"
    ]
    
    for titulo in titulos_test:
        patron = analizador.detectar_patron_variante(titulo)
        print(f"\n   '{titulo}'")
        print(f"   → Tipo: {patron['tipo']}, Valor: {patron['valor']}, Confianza: {patron['confianza']}")
    
    # Test 2: Comparación de productos
    print("\n\n2. COMPARACIÓN DE PRODUCTOS:")
    
    prod1 = {'sku': 'DL1183-S', 'titulo': 'Remera Deportiva Talle S', 'precio': 5000}
    prod2 = {'sku': 'DL1183-M', 'titulo': 'Remera Deportiva Talle M', 'precio': 5000}
    
    comparacion = analizador.comparar_productos(prod1, prod2)
    
    print(f"\n   Producto 1: {prod1['titulo']}")
    print(f"   Producto 2: {prod2['titulo']}")
    print(f"   → Son variantes: {comparacion['son_variantes']}")
    print(f"   → Similitud: {comparacion['similitud_titulo']:.2f}")
    print(f"   → Tipo: {comparacion['tipo_variante']}")
    print(f"   → Confianza: {comparacion['confianza']:.2f}")
    
    print("\n" + "=" * 80)
