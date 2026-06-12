#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
APLICADOR DE VARIANTES
Actualiza metadata.json con campos de agrupación (item_group_id, variante_atributo, variante_valor)
"""

import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List

# Imports locales
import sys
sys.path.append(str(Path(__file__).parent))
from utils.config import Config
from utils.logger import get_logger

logger = get_logger('aplicador_variantes')


class AplicadorVariantes:
    """Aplica campos de variantes a los metadata.json"""
    
    def __init__(self, archivo_variantes: Path):
        """
        Inicializa el aplicador
        
        Args:
            archivo_variantes: Path al archivo de variantes confirmadas
        """
        self.archivo_variantes = archivo_variantes
        self.grupos = []
        
        self.estadisticas = {
            'grupos_procesados': 0,
            'productos_actualizados': 0,
            'productos_individuales': 0,
            'errores': 0
        }
        
        self.cargar_variantes()
        logger.info("Aplicador de variantes inicializado")
    
    def cargar_variantes(self):
        """Carga grupos de variantes desde el archivo"""
        with open(self.archivo_variantes, 'r', encoding='utf-8') as f:
            datos = json.load(f)
        
        grupos_confirmados = datos.get('grupos_confirmados', [])
        
        # Solo grupos aprobados y manuales
        for grupo in grupos_confirmados:
            if grupo.get('accion') in ['APROBADO', 'MANUAL', 'MODIFICADO']:
                self.grupos.append({
                    'id_grupo': grupo.get('id_grupo'),
                    'nombre': grupo.get('producto_base', 'Grupo'),
                    'tipo_variante': grupo.get('atributo_variante', 'variante'),
                    'skus': grupo.get('skus', []),
                    'valores_variantes': grupo.get('valores_variantes', {})
                })
        
        logger.info(f"✅ Cargados {len(self.grupos)} grupos de variantes")
    
    def generar_item_group_id(self, grupo: Dict, indice: int) -> str:
        """
        Genera un item_group_id único para el grupo
        
        Args:
            grupo: Datos del grupo
            indice: Índice del grupo
        
        Returns:
            str: item_group_id único
        """
        # Usar el id_grupo existente si está disponible
        if grupo.get('id_grupo'):
            return grupo['id_grupo']
        
        # Si no, generar uno basado en el índice
        return f"grupo_{indice:03d}"
    
    def extraer_producto_base(self, titulo: str, tipo_variante: str) -> str:
        """
        Extrae el nombre del producto base (sin referencia a la variante)
        
        Args:
            titulo: Título completo del producto
            tipo_variante: Tipo de variante (color, talla, etc.)
        
        Returns:
            str: Nombre del producto base
        """
        # Por ahora retornar el título tal cual
        # En una versión más sofisticada, podría limpiar referencias a colores, tallas, etc.
        return titulo
    
    def obtener_valor_variante(self, sku: str, grupo: Dict) -> str:
        """
        Obtiene el valor de la variante para un SKU
        
        Args:
            sku: SKU del producto
            grupo: Datos del grupo
        
        Returns:
            str: Valor de la variante
        """
        valores = grupo.get('valores_variantes', {})
        
        # Si hay un valor definido, usarlo
        if sku in valores and valores[sku]:
            valor = valores[sku]
            # Si es '?' o inválido, extraer del SKU
            if valor == '?' or not valor.strip():
                # Intentar extraer sufijo del SKU
                import re
                match = re.search(r'-([A-Z0-9]+)$', sku)
                if match:
                    return match.group(1)
                return sku
            return valor
        
        # Si no hay valor, intentar extraer del SKU
        import re
        match = re.search(r'-([A-Z0-9]+)$', sku)
        if match:
            return match.group(1)
        
        return sku
    
    def aplicar_variante_a_producto(self, sku: str, item_group_id: str, 
                                    tipo_variante: str, valor_variante: str,
                                    nombre_base: str) -> bool:
        """
        Aplica campos de variante a un producto específico
        
        Args:
            sku: SKU del producto
            item_group_id: ID del grupo
            tipo_variante: Tipo de variante
            valor_variante: Valor de la variante
            nombre_base: Nombre base del producto
        
        Returns:
            bool: True si se actualizó correctamente
        """
        try:
            # Cargar metadata existente
            metadata = Config.cargar_metadata(sku)
            
            # Agregar/actualizar campos de variante
            metadata['item_group_id'] = item_group_id
            metadata['variante_atributo'] = tipo_variante
            metadata['variante_valor'] = valor_variante
            metadata['producto_base'] = nombre_base
            metadata['es_variante'] = True
            metadata['fecha_actualizacion_variantes'] = datetime.now().isoformat()
            
            # Guardar metadata actualizado
            Config.guardar_metadata(sku, metadata)
            
            logger.debug(f"  ✅ {sku} → group:{item_group_id}, {tipo_variante}:{valor_variante}")
            
            return True
            
        except Exception as e:
            logger.error(f"  ❌ Error actualizando {sku}: {e}")
            return False
    
    def marcar_producto_individual(self, sku: str) -> bool:
        """
        Marca un producto como individual (sin variantes)
        
        Args:
            sku: SKU del producto
        
        Returns:
            bool: True si se actualizó correctamente
        """
        try:
            metadata = Config.cargar_metadata(sku)
            
            # Marcar como producto individual
            metadata['es_variante'] = False
            metadata['item_group_id'] = sku  # Puede usar su propio SKU como ID
            metadata['fecha_actualizacion_variantes'] = datetime.now().isoformat()
            
            Config.guardar_metadata(sku, metadata)
            
            return True
            
        except Exception as e:
            logger.error(f"Error marcando producto individual {sku}: {e}")
            return False
    
    def procesar_grupo(self, grupo: Dict, indice: int, total: int):
        """
        Procesa un grupo de variantes
        
        Args:
            grupo: Datos del grupo
            indice: Índice del grupo (1-based)
            total: Total de grupos
        """
        logger.info(f"[{indice}/{total}] {grupo['nombre']}")
        print(f"[{indice}/{total}] {grupo['nombre']}")
        
        # Generar item_group_id
        item_group_id = self.generar_item_group_id(grupo, indice)
        
        # Tipo de variante
        tipo_variante = grupo.get('tipo_variante', 'variante')
        
        # Nombre base del producto
        nombre_base = grupo['nombre']
        
        logger.info(f"  ID: {item_group_id}")
        logger.info(f"  Tipo: {tipo_variante}")
        logger.info(f"  Variantes: {len(grupo['skus'])}")
        
        # Procesar cada SKU del grupo
        actualizados = 0
        for sku in grupo['skus']:
            valor_variante = self.obtener_valor_variante(sku, grupo)
            
            if self.aplicar_variante_a_producto(
                sku, item_group_id, tipo_variante, 
                valor_variante, nombre_base
            ):
                actualizados += 1
                self.estadisticas['productos_actualizados'] += 1
            else:
                self.estadisticas['errores'] += 1
        
        logger.info(f"  ✅ {actualizados}/{len(grupo['skus'])} productos actualizados")
        print(f"  ✅ {actualizados}/{len(grupo['skus'])} actualizados")
        
        self.estadisticas['grupos_procesados'] += 1
    
    def procesar_productos_individuales(self):
        """Procesa productos que NO están en grupos de variantes"""
        # Obtener todos los SKUs
        todos_skus = set(Config.listar_productos())
        
        # Obtener SKUs en grupos
        skus_en_grupos = set()
        for grupo in self.grupos:
            skus_en_grupos.update(grupo['skus'])
        
        # Productos individuales
        skus_individuales = todos_skus - skus_en_grupos
        
        if not skus_individuales:
            logger.info("No hay productos individuales para marcar")
            return
        
        logger.info(f"Marcando {len(skus_individuales)} productos individuales...")
        print(f"\n📄 Marcando {len(skus_individuales)} productos individuales...")
        
        for sku in skus_individuales:
            if self.marcar_producto_individual(sku):
                self.estadisticas['productos_individuales'] += 1
        
        logger.info(f"✅ {self.estadisticas['productos_individuales']} productos individuales marcados")
        print(f"✅ {self.estadisticas['productos_individuales']} marcados")
    
    def aplicar_todas(self):
        """Aplica variantes a todos los grupos"""
        if not self.grupos:
            print("\n⚠️  No hay grupos para procesar")
            return
        
        print(f"\n{'=' * 80}")
        print(f"🔗 APLICANDO VARIANTES A {len(self.grupos)} GRUPOS")
        print(f"{'=' * 80}\n")
        
        # Procesar grupos
        for i, grupo in enumerate(self.grupos, 1):
            try:
                self.procesar_grupo(grupo, i, len(self.grupos))
            except Exception as e:
                logger.error(f"Error procesando grupo {grupo.get('id_grupo')}: {e}")
                print(f"❌ Error en grupo {i}")
                self.estadisticas['errores'] += 1
        
        # Procesar productos individuales
        self.procesar_productos_individuales()
        
        # Mostrar resumen
        self.mostrar_resumen()
        self.generar_reporte()
    
    def mostrar_resumen(self):
        """Muestra resumen de la aplicación"""
        print(f"\n{'=' * 80}")
        print("📊 RESUMEN DE APLICACIÓN")
        print(f"{'=' * 80}")
        print(f"\n✅ Grupos procesados: {self.estadisticas['grupos_procesados']}")
        print(f"🔗 Productos con variantes: {self.estadisticas['productos_actualizados']}")
        print(f"📄 Productos individuales: {self.estadisticas['productos_individuales']}")
        
        total_procesados = (
            self.estadisticas['productos_actualizados'] + 
            self.estadisticas['productos_individuales']
        )
        print(f"\n📦 Total productos actualizados: {total_procesados}")
        
        if self.estadisticas['errores'] > 0:
            print(f"\n❌ Errores: {self.estadisticas['errores']}")
        
        print(f"\n{'=' * 80}")
        print("\n💡 Campos agregados a metadata.json:")
        print("   • item_group_id")
        print("   • variante_atributo")
        print("   • variante_valor")
        print("   • producto_base")
        print("   • es_variante")
        print(f"{'=' * 80}")
    
    def generar_reporte(self):
        """Genera reporte JSON"""
        fecha = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
        reporte_file = Config.LOGS_DIR / f"reporte_aplicacion_variantes_{fecha}.json"
        
        # Crear resumen por grupo
        resumen_grupos = []
        for grupo in self.grupos:
            resumen_grupos.append({
                'item_group_id': self.generar_item_group_id(grupo, 0),
                'nombre': grupo['nombre'],
                'tipo_variante': grupo['tipo_variante'],
                'cantidad_variantes': len(grupo['skus']),
                'skus': grupo['skus']
            })
        
        reporte = {
            'fecha': datetime.now().isoformat(),
            'archivo_variantes': str(self.archivo_variantes),
            'estadisticas': self.estadisticas,
            'grupos_procesados': resumen_grupos
        }
        
        with open(reporte_file, 'w', encoding='utf-8') as f:
            json.dump(reporte, f, indent=2, ensure_ascii=False)
        
        print(f"\n📄 Reporte: {reporte_file}")
        logger.info(f"Reporte guardado: {reporte_file}")
    
    def verificar_aplicacion(self):
        """Verifica que la aplicación se realizó correctamente"""
        print(f"\n{'─' * 80}")
        print("🔍 VERIFICACIÓN:")
        print(f"{'─' * 80}")
        
        # Verificar algunos productos al azar
        verificados = 0
        con_variante = 0
        
        for grupo in self.grupos[:3]:  # Primeros 3 grupos
            for sku in grupo['skus'][:2]:  # Primeros 2 SKUs de cada grupo
                try:
                    metadata = Config.cargar_metadata(sku)
                    
                    if 'item_group_id' in metadata and 'variante_atributo' in metadata:
                        con_variante += 1
                        print(f"✅ {sku}: group={metadata['item_group_id']}, "
                              f"{metadata['variante_atributo']}={metadata['variante_valor']}")
                    else:
                        print(f"⚠️  {sku}: Campos de variante NO encontrados")
                    
                    verificados += 1
                    
                except Exception as e:
                    print(f"❌ {sku}: Error - {e}")
        
        print(f"\n✅ Verificados: {verificados}, Con variantes: {con_variante}")
        print(f"{'─' * 80}")


def main():
    """Ejecuta el aplicador"""
    print("=" * 80)
    print("🔗 APLICADOR DE VARIANTES")
    print("=" * 80)
    
    # Buscar archivo de variantes
    archivos_variantes = sorted(
        Config.GRUPOS_VARIANTES_DIR.glob("variantes_*.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True
    )
    
    if not archivos_variantes:
        print("\n❌ No se encontró archivo de variantes")
        print("   Ejecutar primero: python 08_revisor_variantes.py")
        return
    
    archivo = archivos_variantes[0]
    print(f"\n📄 Archivo de variantes: {archivo.name}")
    
    # Cargar para mostrar info
    with open(archivo, 'r', encoding='utf-8') as f:
        datos = json.load(f)
    
    grupos_validos = [
        g for g in datos.get('grupos_confirmados', [])
        if g.get('accion') in ['APROBADO', 'MANUAL', 'MODIFICADO']
    ]
    
    print(f"📊 Grupos a procesar: {len(grupos_validos)}")
    
    # Calcular total de productos
    total_productos = Config.listar_productos()
    skus_en_grupos = set()
    for g in grupos_validos:
        skus_en_grupos.update(g.get('skus', []))
    
    productos_individuales = len(total_productos) - len(skus_en_grupos)
    
    print(f"📦 Productos en grupos: {len(skus_en_grupos)}")
    print(f"📄 Productos individuales: {productos_individuales}")
    
    print(f"\n{'─' * 80}")
    print("⚠️  IMPORTANTE:")
    print("   • Esto modificará los archivos metadata.json")
    print("   • Se agregarán campos: item_group_id, variante_atributo, variante_valor")
    print("   • Es reversible (se puede quitar después)")
    print(f"{'─' * 80}")
    
    confirmar = input("\n¿Aplicar variantes? (s/n): ").lower()
    
    if confirmar == 's':
        aplicador = AplicadorVariantes(archivo)
        aplicador.aplicar_todas()
        aplicador.verificar_aplicacion()
    else:
        print("\nAplicación cancelada")


if __name__ == "__main__":
    main()
