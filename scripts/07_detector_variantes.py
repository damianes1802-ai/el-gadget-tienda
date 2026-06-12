#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DETECTOR DE VARIANTES
Analiza productos y detecta automáticamente variantes basándose en similitudes
"""

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple
from difflib import SequenceMatcher
from collections import defaultdict

# Imports locales
import sys
sys.path.append(str(Path(__file__).parent))
from utils.config import Config
from utils.logger import get_logger, LoggerManager

logger = get_logger('detector_variantes')


class DetectorVariantes:
    """Detecta variantes de productos automáticamente"""
    
    def __init__(self):
        """Inicializa el detector"""
        self.productos = []
        self.grupos_sugeridos = []
        self.patrones_detectados = defaultdict(int)
        
        # Patrones de variantes conocidos
        self.patrones = {
            'talles': r'\b(xs|s|m|l|xl|xxl|xxxl)\b',
            'numeros_talle': r'\b(talle\s)?(\d{2,3})\b',
            'longitud': r'\b(\d+)\s?(cm|mm|m|mt|metros?)\b',
            'cantidad': r'(pack\s?x?|x\s?)?(\d+)\s?(unidades?|u|uni|pack)?',
            'colores_cortos': r'\b(ne|bl|ro|az|ve|am|gr|be|ce|fu|li|tu|vi|ma|na|ros)\b',
            'colores_largos': r'\b(negro|blanco|rojo|azul|verde|amarillo|naranja|rosa|violeta|gris|marron|beige|celeste|fucsia|lila|turquesa)\b',
            'capacidad': r'\b(\d+)\s?(gb|mb|tb|l|lt|litros?)\b',
            'version': r'\b(v\d+|version\s?\d+|modelo\s?\d+)\b',
            'sufijos_numericos': r'[-_]\d+$',
            'pack_multiple': r'x\s?(\d+)'
        }
        
        logger.info("Detector de variantes inicializado")
    
    def cargar_productos(self):
        """Carga todos los productos scrapeados"""
        skus = Config.listar_productos()
        
        if not skus:
            logger.warning("No hay productos para analizar")
            return
        
        logger.info(f"Cargando {len(skus)} productos...")
        
        for sku in skus:
            try:
                metadata = Config.cargar_metadata(sku)
                self.productos.append({
                    'sku': sku,
                    'titulo': metadata.get('titulo', ''),
                    'precio': metadata.get('precio', 0),
                    'precio_venta': metadata.get('precio_venta', 0),
                    'descripcion': metadata.get('descripcion', '')
                })
            except Exception as e:
                logger.warning(f"Error cargando {sku}: {e}")
        
        logger.info(f"✅ {len(self.productos)} productos cargados")
    
    def normalizar_texto(self, texto: str) -> str:
        """
        Normaliza un texto para comparación
        
        Args:
            texto: Texto a normalizar
        
        Returns:
            str: Texto normalizado
        """
        # Convertir a minúsculas
        texto = texto.lower()
        
        # Remover caracteres especiales pero mantener espacios y guiones
        texto = re.sub(r'[^\w\s\-]', '', texto)
        
        # Normalizar espacios
        texto = ' '.join(texto.split())
        
        return texto
    
    def extraer_base_titulo(self, titulo: str) -> Tuple[str, Dict]:
        """
        Extrae la base del título sin las variantes
        
        Args:
            titulo: Título completo del producto
        
        Returns:
            tuple: (titulo_base, variantes_detectadas)
        """
        titulo_norm = self.normalizar_texto(titulo)
        variantes_detectadas = {}
        
        # Detectar cada tipo de variante
        for tipo, patron in self.patrones.items():
            matches = re.findall(patron, titulo_norm, re.IGNORECASE)
            if matches:
                variantes_detectadas[tipo] = matches
                self.patrones_detectados[tipo] += 1
        
        # Crear título base removiendo las variantes
        titulo_base = titulo_norm
        
        # Remover patrones detectados
        for tipo, matches in variantes_detectadas.items():
            for match in matches:
                if isinstance(match, tuple):
                    for m in match:
                        if m:
                            titulo_base = titulo_base.replace(str(m), '')
                else:
                    titulo_base = titulo_base.replace(str(match), '')
        
        # Limpiar espacios múltiples y guiones sueltos
        titulo_base = re.sub(r'\s+', ' ', titulo_base)
        titulo_base = re.sub(r'\s*-\s*$', '', titulo_base)
        titulo_base = titulo_base.strip()
        
        return titulo_base, variantes_detectadas
    
    def calcular_similitud(self, texto1: str, texto2: str) -> float:
        """
        Calcula similitud entre dos textos
        
        Args:
            texto1: Primer texto
            texto2: Segundo texto
        
        Returns:
            float: Similitud (0-1)
        """
        return SequenceMatcher(None, texto1, texto2).ratio()
    
    def detectar_variante_por_sku(self, sku1: str, sku2: str) -> bool:
        """
        Detecta si dos SKUs son variantes por patrón
        
        Args:
            sku1: Primer SKU
            sku2: Segundo SKU
        
        Returns:
            bool: True si parecen ser variantes
        """
        # Extraer parte alfanumérica base
        base1 = re.sub(r'[-_][a-z0-9]+$', '', sku1.lower())
        base2 = re.sub(r'[-_][a-z0-9]+$', '', sku2.lower())
        
        # Si las bases coinciden, son variantes
        if base1 == base2 and base1 != '' and sku1 != sku2:
            return True
        
        # Detectar patrones como DL1183-S, DL1183-M
        pattern = r'^([a-z]+\d+)'
        match1 = re.match(pattern, sku1.lower())
        match2 = re.match(pattern, sku2.lower())
        
        if match1 and match2:
            if match1.group(1) == match2.group(1):
                return True
        
        return False
    
    def agrupar_por_similitud(self) -> List[Dict]:
        """
        Agrupa productos por similitud de título
        
        Returns:
            list: Lista de grupos sugeridos
        """
        logger.info("Analizando similitudes entre productos...")
        
        grupos = []
        procesados = set()
        
        for i, prod1 in enumerate(self.productos):
            if prod1['sku'] in procesados:
                continue
            
            # Extraer base del título
            base1, var1 = self.extraer_base_titulo(prod1['titulo'])
            
            # Buscar productos similares
            grupo = {
                'producto_base': base1,
                'productos': [prod1],
                'variantes_detectadas': {},
                'confianza': 1.0
            }
            
            for j, prod2 in enumerate(self.productos[i+1:], i+1):
                if prod2['sku'] in procesados:
                    continue
                
                # Extraer base del segundo producto
                base2, var2 = self.extraer_base_titulo(prod2['titulo'])
                
                # Calcular similitud
                similitud_titulo = self.calcular_similitud(base1, base2)
                similitud_sku = self.detectar_variante_por_sku(
                    prod1['sku'], 
                    prod2['sku']
                )
                
                # Si hay alta similitud o SKUs relacionados
                if similitud_titulo >= 0.80 or similitud_sku:
                    grupo['productos'].append(prod2)
                    procesados.add(prod2['sku'])
                    
                    # Registrar tipo de variante
                    for tipo, matches in var2.items():
                        if tipo not in grupo['variantes_detectadas']:
                            grupo['variantes_detectadas'][tipo] = []
                        grupo['variantes_detectadas'][tipo].extend(matches)
            
            # Si hay más de 1 producto en el grupo, es una variante
            if len(grupo['productos']) > 1:
                procesados.add(prod1['sku'])
                
                # Calcular confianza basada en cantidad de variantes y similitud
                if grupo['variantes_detectadas']:
                    grupo['confianza'] = 0.95
                else:
                    grupo['confianza'] = 0.75
                
                grupos.append(grupo)
                
                logger.info(
                    f"Grupo detectado: {base1} "
                    f"({len(grupo['productos'])} variantes, "
                    f"confianza: {grupo['confianza']:.0%})"
                )
        
        return grupos
    
    def identificar_tipo_variante(self, grupo: Dict) -> str:
        """
        Identifica el tipo principal de variante de un grupo
        
        Args:
            grupo: Grupo de productos
        
        Returns:
            str: Tipo de variante identificado
        """
        variantes = grupo.get('variantes_detectadas', {})
        
        if not variantes:
            return 'indeterminado'
        
        # Contar ocurrencias por tipo
        tipos_count = {tipo: len(matches) for tipo, matches in variantes.items()}
        
        # Devolver el tipo más frecuente
        tipo_principal = max(tipos_count, key=tipos_count.get)
        
        # Mapear a nombres más amigables
        mapeo = {
            'talles': 'talle',
            'colores_cortos': 'color',
            'colores_largos': 'color',
            'longitud': 'longitud',
            'cantidad': 'cantidad',
            'capacidad': 'capacidad',
            'version': 'versión'
        }
        
        return mapeo.get(tipo_principal, tipo_principal)
    
    def extraer_valor_variante(self, producto: Dict, tipo_variante: str) -> str:
        """
        Extrae el valor específico de la variante
        
        Args:
            producto: Datos del producto
            tipo_variante: Tipo de variante
        
        Returns:
            str: Valor de la variante
        """
        titulo = producto['titulo']
        sku = producto['sku']
        
        # Buscar en el título
        titulo_norm = self.normalizar_texto(titulo)
        
        # Intentar extraer del SKU primero (más confiable)
        sufijo_sku = re.search(r'[-_]([a-z0-9]+)$', sku.lower())
        if sufijo_sku:
            return sufijo_sku.group(1).upper()
        
        # Si no, buscar en el título según el tipo
        if tipo_variante in ['talle', 'talles']:
            match = re.search(self.patrones['talles'], titulo_norm, re.IGNORECASE)
            if match:
                return match.group(1).upper()
        
        elif tipo_variante == 'color':
            # Buscar colores cortos primero
            match = re.search(self.patrones['colores_cortos'], titulo_norm, re.IGNORECASE)
            if match:
                return match.group(1).upper()
            
            # Luego colores largos
            match = re.search(self.patrones['colores_largos'], titulo_norm, re.IGNORECASE)
            if match:
                return match.group(1).capitalize()
        
        elif tipo_variante == 'longitud':
            match = re.search(self.patrones['longitud'], titulo_norm, re.IGNORECASE)
            if match:
                return f"{match.group(1)}{match.group(2)}"
        
        elif tipo_variante == 'cantidad':
            match = re.search(self.patrones['pack_multiple'], titulo_norm, re.IGNORECASE)
            if match:
                return f"x{match.group(1)}"
        
        return '?'
    
    def generar_sugerencias(self) -> Dict:
        """
        Genera archivo de sugerencias de variantes
        
        Returns:
            dict: Sugerencias generadas
        """
        LoggerManager.log_inicio_proceso(
            logger, 
            "Detección de Variantes",
            len(self.productos)
        )
        
        # Agrupar productos
        grupos = self.agrupar_por_similitud()
        
        # Generar sugerencias estructuradas
        sugerencias = {
            'fecha_analisis': datetime.now().isoformat(),
            'total_productos_analizados': len(self.productos),
            'grupos_sugeridos': len(grupos),
            'productos_sin_variantes': len(self.productos) - sum(len(g['productos']) for g in grupos),
            'patrones_detectados': dict(self.patrones_detectados),
            'sugerencias': []
        }
        
        for i, grupo in enumerate(grupos, 1):
            tipo_variante = self.identificar_tipo_variante(grupo)
            
            sugerencia = {
                'id_sugerencia': f"sugerencia_{i:03d}",
                'confianza': grupo['confianza'],
                'producto_base_detectado': grupo['producto_base'],
                'atributo_variante_detectado': tipo_variante,
                'total_variantes': len(grupo['productos']),
                'productos': [],
                'estado': 'PENDIENTE_REVISION'
            }
            
            for prod in grupo['productos']:
                valor_variante = self.extraer_valor_variante(prod, tipo_variante)
                
                sugerencia['productos'].append({
                    'sku': prod['sku'],
                    'titulo': prod['titulo'],
                    'valor_variante': valor_variante,
                    'precio_costo': prod['precio'],
                    'precio_venta': prod.get('precio_venta', 0)
                })
            
            # Determinar acción sugerida
            if sugerencia['confianza'] >= 0.90:
                sugerencia['accion_sugerida'] = 'AGRUPAR'
            elif sugerencia['confianza'] >= 0.75:
                sugerencia['accion_sugerida'] = 'REVISAR_MANUAL'
            else:
                sugerencia['accion_sugerida'] = 'POSIBLE_FALSO_POSITIVO'
            
            sugerencias['sugerencias'].append(sugerencia)
        
        LoggerManager.log_fin_proceso(
            logger,
            "Detección de Variantes",
            len(grupos),
            0
        )
        
        return sugerencias
    
    def guardar_sugerencias(self, sugerencias: Dict) -> Path:
        """
        Guarda las sugerencias en un archivo JSON
        
        Args:
            sugerencias: Sugerencias generadas
        
        Returns:
            Path: Ruta al archivo guardado
        """
        fecha = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
        archivo = Config.GRUPOS_VARIANTES_DIR / f"sugerencias_variantes_{fecha}.json"
        
        with open(archivo, 'w', encoding='utf-8') as f:
            json.dump(sugerencias, f, indent=2, ensure_ascii=False)
        
        logger.info(f"📄 Sugerencias guardadas en: {archivo}")
        
        return archivo
    
    def mostrar_resumen(self, sugerencias: Dict):
        """
        Muestra un resumen de las sugerencias
        
        Args:
            sugerencias: Sugerencias generadas
        """
        print(f"\n{'=' * 80}")
        print("📊 RESUMEN DE DETECCIÓN DE VARIANTES")
        print(f"{'=' * 80}")
        print(f"\nTotal productos analizados: {sugerencias['total_productos_analizados']}")
        print(f"Grupos de variantes detectados: {sugerencias['grupos_sugeridos']}")
        print(f"Productos únicos (sin variantes): {sugerencias['productos_sin_variantes']}")
        
        if sugerencias['patrones_detectados']:
            print(f"\n📋 Patrones detectados:")
            for patron, count in sorted(
                sugerencias['patrones_detectados'].items(), 
                key=lambda x: x[1], 
                reverse=True
            ):
                print(f"   • {patron}: {count} ocurrencias")
        
        print(f"\n{'─' * 80}")
        print(f"PRIMEROS 5 GRUPOS DETECTADOS:")
        print(f"{'─' * 80}")
        
        for i, sug in enumerate(sugerencias['sugerencias'][:5], 1):
            confianza_emoji = "✅" if sug['confianza'] >= 0.90 else "⚠️"
            print(f"\n{i}. {confianza_emoji} {sug['producto_base_detectado']}")
            print(f"   Tipo: {sug['atributo_variante_detectado']}")
            print(f"   Variantes: {sug['total_variantes']}")
            print(f"   Confianza: {sug['confianza']:.0%}")
            print(f"   SKUs: {', '.join([p['sku'] for p in sug['productos'][:3]])}", end='')
            if len(sug['productos']) > 3:
                print(f" ... (+{len(sug['productos']) - 3} más)")
            else:
                print()
        
        if len(sugerencias['sugerencias']) > 5:
            print(f"\n... y {len(sugerencias['sugerencias']) - 5} grupos más")
        
        print(f"\n{'=' * 80}")
        print(f"📄 Siguiente paso: Revisar sugerencias con el módulo interactivo")
        print(f"   python 08_revisor_variantes.py")
        print(f"{'=' * 80}")


def main():
    """Ejecuta el detector de variantes"""
    print("=" * 80)
    print("🔍 DETECTOR DE VARIANTES")
    print("=" * 80)
    
    detector = DetectorVariantes()
    
    # Cargar productos
    detector.cargar_productos()
    
    if not detector.productos:
        print("\n⚠️  No hay productos para analizar")
        print("   Ejecutar primero: python 01_scraper.py")
        return
    
    print(f"\n📊 Analizando {len(detector.productos)} productos...")
    print("   Esto puede tardar unos segundos...\n")
    
    # Generar sugerencias
    sugerencias = detector.generar_sugerencias()
    
    # Guardar sugerencias
    archivo = detector.guardar_sugerencias(sugerencias)
    
    # Mostrar resumen
    detector.mostrar_resumen(sugerencias)


if __name__ == "__main__":
    main()
