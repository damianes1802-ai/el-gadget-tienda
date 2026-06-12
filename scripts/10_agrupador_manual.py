#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AGRUPADOR MANUAL DE VARIANTES
Permite crear grupos de variantes manualmente con productos rechazados
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Set

# Imports locales
import sys
sys.path.append(str(Path(__file__).parent))
from utils.config import Config
from utils.logger import get_logger

logger = get_logger('agrupador_manual')


class AgrupadorManual:
    """Permite crear variantes manualmente con productos rechazados"""
    
    def __init__(self, archivo_decisiones: Path):
        """Inicializa el agrupador"""
        self.archivo_decisiones = archivo_decisiones
        self.decisiones = None
        self.productos_disponibles = []  # Solo productos rechazados
        self.grupos_manuales = []
        self.cargar_decisiones()
        self.extraer_productos_disponibles()
    
    def cargar_decisiones(self):
        """Carga las decisiones ya tomadas"""
        with open(self.archivo_decisiones, 'r', encoding='utf-8') as f:
            self.decisiones = json.load(f)
        
        logger.info(f"Decisiones cargadas: {len(self.decisiones.get('grupos_confirmados', []))} grupos")
    
    def extraer_productos_disponibles(self):
        """Extrae SKUs de productos rechazados (disponibles para agrupar)"""
        # 1. Obtener todos los SKUs rechazados
        skus_rechazados = set()
        
        for grupo in self.decisiones.get('grupos_confirmados', []):
            if grupo.get('accion') == 'RECHAZADO':
                # Estos son los productos que NO se agruparon
                skus_rechazados.update(grupo.get('skus_tratados_como_individuales', grupo.get('skus', [])))
        
        # 2. Obtener SKUs ya usados en grupos aprobados, modificados Y MANUALES
        skus_ya_usados = set()
        
        for grupo in self.decisiones.get('grupos_confirmados', []):
            accion = grupo.get('accion')
            if accion in ['APROBADO', 'MODIFICADO', 'MANUAL']:
                # Estos productos ya están en grupos
                skus_ya_usados.update(grupo.get('skus', []))
        
        # 3. Productos disponibles = Rechazados - Ya usados
        skus_disponibles = skus_rechazados - skus_ya_usados
        
        logger.info(f"SKUs rechazados: {len(skus_rechazados)}")
        logger.info(f"SKUs ya usados en grupos: {len(skus_ya_usados)}")
        logger.info(f"SKUs disponibles para agrupar: {len(skus_disponibles)}")
        
        # 4. Cargar metadata de productos disponibles
        for sku in skus_disponibles:
            try:
                metadata = Config.cargar_metadata(sku)
                self.productos_disponibles.append({
                    'sku': sku,
                    'titulo': metadata.get('titulo', ''),
                    'precio': metadata.get('precio', 0),
                    'precio_venta': metadata.get('precio_venta', 0)
                })
            except Exception as e:
                logger.warning(f"Error cargando {sku}: {e}")
        
        # Ordenar alfabéticamente por SKU
        self.productos_disponibles.sort(key=lambda x: x['sku'])
        
        logger.info(f"Productos cargados correctamente: {len(self.productos_disponibles)}")
    
    def limpiar_pantalla(self):
        """Limpia la pantalla"""
        os.system('cls' if os.name == 'nt' else 'clear')
    
    def menu_principal(self):
        """Menú principal del agrupador"""
        # Calcular estadísticas
        total_rechazados = sum(
            len(g.get('skus_tratados_como_individuales', g.get('skus', []))) 
            for g in self.decisiones.get('grupos_confirmados', []) 
            if g.get('accion') == 'RECHAZADO'
        )
        
        skus_en_manuales = sum(
            len(g.get('skus', [])) 
            for g in self.decisiones.get('grupos_confirmados', []) 
            if g.get('accion') == 'MANUAL'
        )
        
        while True:
            self.limpiar_pantalla()
            
            print("=" * 80)
            print("✏️  AGRUPADOR MANUAL DE VARIANTES")
            print("=" * 80)
            print(f"\n📊 Productos rechazados originalmente: {total_rechazados}")
            print(f"📦 Ya usados en grupos manuales: {skus_en_manuales}")
            print(f"✅ Disponibles para agrupar: {len(self.productos_disponibles)}")
            print(f"\n🔨 Grupos manuales creados en esta sesión: {len(self.grupos_manuales)}")
            
            print("\n📋 OPCIONES:")
            print("  1️⃣  Ver productos disponibles")
            print("  2️⃣  Crear nuevo grupo de variantes")
            print("  3️⃣  Ver grupos creados (esta sesión)")
            print("  4️⃣  Ver TODOS los grupos manuales (histórico)")
            print("  5️⃣  Eliminar grupo de esta sesión")
            print("  6️⃣  Buscar producto por palabra clave")
            print("  0️⃣  Guardar y salir")
            
            opcion = input("\nSeleccionar opción: ").strip()
            
            if opcion == '1':
                self.ver_productos_disponibles()
            elif opcion == '2':
                self.crear_grupo()
            elif opcion == '3':
                self.ver_grupos_creados()
            elif opcion == '4':
                self.ver_todos_grupos_manuales()
            elif opcion == '5':
                self.eliminar_grupo()
            elif opcion == '6':
                self.buscar_producto()
            elif opcion == '0':
                if self.grupos_manuales:
                    self.guardar_grupos()
                    print(f"\n✅ Se guardaron {len(self.grupos_manuales)} grupos manuales nuevos")
                else:
                    print("\n⚠️  No se crearon grupos nuevos en esta sesión")
                input("\nPresionar Enter para salir...")
                break
            else:
                print("❌ Opción inválida")
                input("Presionar Enter...")
    
    def ver_productos_disponibles(self, pagina: int = 1, por_pagina: int = 20):
        """Muestra productos disponibles paginados"""
        self.limpiar_pantalla()
        
        total = len(self.productos_disponibles)
        total_paginas = (total + por_pagina - 1) // por_pagina
        
        inicio = (pagina - 1) * por_pagina
        fin = min(inicio + por_pagina, total)
        
        print("=" * 80)
        print(f"📋 PRODUCTOS DISPONIBLES (Página {pagina}/{total_paginas})")
        print("=" * 80)
        print(f"\nTotal: {total} productos rechazados")
        print(f"Mostrando: {inicio + 1} - {fin}")
        print("\n" + "─" * 80)
        print(f"{'#':<5} {'SKU':<20} {'Título':<45}")
        print("─" * 80)
        
        for i, prod in enumerate(self.productos_disponibles[inicio:fin], inicio + 1):
            titulo = prod['titulo'][:42] + "..." if len(prod['titulo']) > 45 else prod['titulo']
            print(f"{i:<5} {prod['sku']:<20} {titulo:<45}")
        
        print("\n" + "─" * 80)
        if pagina < total_paginas:
            print(f"[N] Siguiente página | [Enter] Volver")
            opcion = input("Selección: ").upper().strip()
            if opcion == 'N':
                self.ver_productos_disponibles(pagina + 1, por_pagina)
        else:
            input("\nPresionar Enter para volver...")
    
    def crear_grupo(self):
        """Crea un nuevo grupo de variantes manualmente"""
        self.limpiar_pantalla()
        
        print("=" * 80)
        print("➕ CREAR NUEVO GRUPO DE VARIANTES")
        print("=" * 80)
        
        # 1. Nombre del producto base
        print("\n📝 PASO 1: Definir producto base")
        nombre_base = input("Nombre del producto (ej: 'Remera Deportiva'): ").strip()
        
        if not nombre_base:
            print("❌ El nombre no puede estar vacío")
            input("Presionar Enter...")
            return
        
        # 2. Tipo de variante
        print("\n🏷️  PASO 2: Tipo de variante")
        print("  1. Talla/Tamaño")
        print("  2. Color")
        print("  3. Longitud/Medida")
        print("  4. Cantidad/Pack")
        print("  5. Capacidad")
        print("  6. Otro (especificar)")
        
        tipo_opcion = input("\nSeleccionar tipo: ").strip()
        
        tipos_mapa = {
            '1': 'talla',
            '2': 'color',
            '3': 'longitud',
            '4': 'cantidad',
            '5': 'capacidad'
        }
        
        if tipo_opcion == '6':
            tipo_variante = input("Especificar tipo: ").strip()
        else:
            tipo_variante = tipos_mapa.get(tipo_opcion, 'otro')
        
        # 3. Seleccionar productos
        print("\n📦 PASO 3: Seleccionar productos")
        print("\nProductos disponibles:")
        print("─" * 80)
        
        # Mostrar productos con búsqueda opcional
        palabra_busqueda = input("Filtrar por palabra (Enter para ver todos): ").strip().lower()
        
        productos_filtrados = []
        if palabra_busqueda:
            productos_filtrados = [
                p for p in self.productos_disponibles 
                if palabra_busqueda in p['sku'].lower() or palabra_busqueda in p['titulo'].lower()
            ]
        else:
            productos_filtrados = self.productos_disponibles[:50]  # Primeros 50
        
        if not productos_filtrados:
            print("\n⚠️  No se encontraron productos")
            input("Presionar Enter...")
            return
        
        print(f"\n{'#':<5} {'SKU':<20} {'Título':<45}")
        print("─" * 80)
        for i, prod in enumerate(productos_filtrados, 1):
            titulo = prod['titulo'][:42] + "..." if len(prod['titulo']) > 45 else prod['titulo']
            print(f"{i:<5} {prod['sku']:<20} {titulo:<45}")
        
        print("\n" + "─" * 80)
        print("Ingrese los números de productos a INCLUIR")
        print("(separados por comas, ej: 1,3,5,7)")
        print("O rangos: 1-5,8,10-12")
        
        seleccion = input("\nProductos a incluir: ").strip()
        
        if not seleccion:
            print("❌ Debe seleccionar al menos 2 productos")
            input("Presionar Enter...")
            return
        
        # Parsear selección
        indices_seleccionados = self._parsear_seleccion(seleccion)
        
        productos_seleccionados = []
        for idx in indices_seleccionados:
            if 1 <= idx <= len(productos_filtrados):
                productos_seleccionados.append(productos_filtrados[idx - 1])
        
        if len(productos_seleccionados) < 2:
            print("\n❌ Debe seleccionar al menos 2 productos para formar un grupo")
            input("Presionar Enter...")
            return
        
        # 4. Definir valores de variante para cada producto
        print("\n🔤 PASO 4: Definir valores de variante")
        print("─" * 80)
        
        valores_variantes = {}
        
        for prod in productos_seleccionados:
            print(f"\n📝 {prod['sku']} - {prod['titulo'][:50]}")
            valor = input(f"   Valor de {tipo_variante} (ej: S, Rojo, 90cm): ").strip()
            valores_variantes[prod['sku']] = valor if valor else '?'
        
        # 5. Confirmar y crear grupo
        self.limpiar_pantalla()
        print("=" * 80)
        print("📋 CONFIRMACIÓN DE GRUPO")
        print("=" * 80)
        print(f"\n📦 Producto base: {nombre_base}")
        print(f"🏷️  Tipo de variante: {tipo_variante}")
        print(f"📊 Total productos: {len(productos_seleccionados)}")
        print("\nProductos incluidos:")
        print("─" * 80)
        
        for prod in productos_seleccionados:
            valor = valores_variantes.get(prod['sku'], '?')
            print(f"  • {prod['sku']} → {valor}")
        
        print("\n" + "─" * 80)
        confirmar = input("\n¿Crear este grupo? (s/n): ").lower()
        
        if confirmar == 's':
            # Generar ID único
            grupo_id = f"manual_{len(self.grupos_manuales) + 1:03d}"
            
            nuevo_grupo = {
                'id_grupo': grupo_id,
                'accion': 'MANUAL',
                'producto_base': nombre_base,
                'atributo_variante': tipo_variante,
                'skus': [p['sku'] for p in productos_seleccionados],
                'valores_variantes': valores_variantes,
                'fecha_creacion': datetime.now().isoformat(),
                'origen': 'agrupacion_manual'
            }
            
            self.grupos_manuales.append(nuevo_grupo)
            
            # Remover productos usados de disponibles
            skus_usados = set(p['sku'] for p in productos_seleccionados)
            self.productos_disponibles = [
                p for p in self.productos_disponibles 
                if p['sku'] not in skus_usados
            ]
            
            print(f"\n✅ Grupo '{grupo_id}' creado correctamente")
            logger.info(f"Grupo manual creado: {grupo_id} - {nombre_base}")
        else:
            print("\n❌ Grupo cancelado")
        
        input("\nPresionar Enter para continuar...")
    
    def _parsear_seleccion(self, seleccion: str) -> List[int]:
        """
        Parsea una selección tipo '1,3,5-8,10'
        
        Returns:
            list: Lista de índices
        """
        indices = []
        
        partes = seleccion.split(',')
        for parte in partes:
            parte = parte.strip()
            
            if '-' in parte:
                # Rango
                try:
                    inicio, fin = parte.split('-')
                    indices.extend(range(int(inicio), int(fin) + 1))
                except ValueError:
                    pass
            else:
                # Número único
                try:
                    indices.append(int(parte))
                except ValueError:
                    pass
        
        return sorted(set(indices))
    
    def ver_grupos_creados(self):
        """Muestra los grupos creados manualmente EN ESTA SESIÓN"""
        self.limpiar_pantalla()
        
        print("=" * 80)
        print(f"📦 GRUPOS CREADOS EN ESTA SESIÓN ({len(self.grupos_manuales)})")
        print("=" * 80)
        
        if not self.grupos_manuales:
            print("\n⚠️  No hay grupos creados todavía en esta sesión")
            input("\nPresionar Enter...")
            return
        
        for i, grupo in enumerate(self.grupos_manuales, 1):
            print(f"\n{i}. {grupo.get('producto_base', 'N/A')}")
            print(f"   ID: {grupo.get('id_grupo')}")
            print(f"   Tipo: {grupo.get('atributo_variante')}")
            print(f"   Productos: {len(grupo.get('skus', []))}")
            print(f"   SKUs: {', '.join(grupo.get('skus', []))}")
        
        input("\n\nPresionar Enter para volver...")
    
    def ver_todos_grupos_manuales(self):
        """Muestra TODOS los grupos manuales (incluyendo sesiones anteriores)"""
        self.limpiar_pantalla()
        
        # Obtener todos los grupos manuales del archivo
        grupos_manuales_totales = [
            g for g in self.decisiones.get('grupos_confirmados', [])
            if g.get('accion') == 'MANUAL'
        ]
        
        print("=" * 80)
        print(f"📚 TODOS LOS GRUPOS MANUALES - HISTÓRICO ({len(grupos_manuales_totales)})")
        print("=" * 80)
        
        if not grupos_manuales_totales:
            print("\n⚠️  No hay grupos manuales en el archivo")
            input("\nPresionar Enter...")
            return
        
        print(f"\nMostrando {len(grupos_manuales_totales)} grupos manuales:")
        print("─" * 80)
        
        for i, grupo in enumerate(grupos_manuales_totales, 1):
            fecha = grupo.get('fecha_creacion', 'N/A')
            # Extraer solo la fecha
            if 'T' in fecha:
                fecha = fecha.split('T')[0]
            
            print(f"\n{i}. {grupo.get('producto_base', 'N/A')}")
            print(f"   ID: {grupo.get('id_grupo')}")
            print(f"   Tipo: {grupo.get('atributo_variante')}")
            print(f"   Productos: {len(grupo.get('skus', []))}")
            print(f"   Fecha: {fecha}")
            print(f"   SKUs: {', '.join(grupo.get('skus', [])[:3])}", end='')
            if len(grupo.get('skus', [])) > 3:
                print(f" ... (+{len(grupo['skus']) - 3} más)")
            else:
                print()
        
        print("\n" + "─" * 80)
        print(f"💡 Estos productos YA NO están disponibles para agrupar")
        
        input("\n\nPresionar Enter para volver...")
    
    def editar_grupo(self):
        """Edita un grupo existente"""
        if not self.grupos_manuales:
            print("\n⚠️  No hay grupos para editar")
            input("Presionar Enter...")
            return
        
        self.ver_grupos_creados()
        
        try:
            num = int(input("\n¿Qué grupo editar? (número): ")) - 1
            if 0 <= num < len(self.grupos_manuales):
                # Por ahora solo permitir eliminar productos
                print("\n⚠️  Función de edición en desarrollo")
                print("   Use la opción de eliminar grupo y crear uno nuevo")
            else:
                print("❌ Número inválido")
        except ValueError:
            print("❌ Entrada inválida")
        
        input("\nPresionar Enter...")
    
    def eliminar_grupo(self):
        """Elimina un grupo creado"""
        if not self.grupos_manuales:
            print("\n⚠️  No hay grupos para eliminar")
            input("Presionar Enter...")
            return
        
        self.ver_grupos_creados()
        
        try:
            num = int(input("\n¿Qué grupo eliminar? (número): ")) - 1
            if 0 <= num < len(self.grupos_manuales):
                grupo = self.grupos_manuales[num]
                
                confirmar = input(f"\n⚠️  ¿Eliminar '{grupo.get('producto_base')}'? (s/n): ").lower()
                
                if confirmar == 's':
                    # Devolver productos a disponibles
                    for sku in grupo.get('skus', []):
                        try:
                            metadata = Config.cargar_metadata(sku)
                            self.productos_disponibles.append({
                                'sku': sku,
                                'titulo': metadata.get('titulo', ''),
                                'precio': metadata.get('precio', 0),
                                'precio_venta': metadata.get('precio_venta', 0)
                            })
                        except:
                            pass
                    
                    self.productos_disponibles.sort(key=lambda x: x['sku'])
                    self.grupos_manuales.pop(num)
                    
                    print("\n✅ Grupo eliminado")
                else:
                    print("\nCancelado")
            else:
                print("❌ Número inválido")
        except ValueError:
            print("❌ Entrada inválida")
        
        input("\nPresionar Enter...")
    
    def buscar_producto(self):
        """Busca productos por palabra clave"""
        self.limpiar_pantalla()
        
        print("=" * 80)
        print("🔍 BUSCAR PRODUCTO")
        print("=" * 80)
        
        palabra = input("\n🔑 Palabra clave: ").strip().lower()
        
        if not palabra:
            return
        
        encontrados = [
            p for p in self.productos_disponibles 
            if palabra in p['sku'].lower() or palabra in p['titulo'].lower()
        ]
        
        if not encontrados:
            print(f"\n⚠️  No se encontraron productos con '{palabra}'")
        else:
            print(f"\n📋 Productos encontrados ({len(encontrados)}):")
            print("─" * 80)
            print(f"{'SKU':<20} {'Título':<50}")
            print("─" * 80)
            
            for prod in encontrados[:20]:
                titulo = prod['titulo'][:47] + "..." if len(prod['titulo']) > 50 else prod['titulo']
                print(f"{prod['sku']:<20} {titulo:<50}")
            
            if len(encontrados) > 20:
                print(f"\n... y {len(encontrados) - 20} más")
        
        input("\n\nPresionar Enter...")
    
    def guardar_grupos(self):
        """Guarda los grupos manuales creados ACTUALIZANDO el archivo existente"""
        if not self.grupos_manuales:
            return
        
        # Agregar grupos manuales a las decisiones existentes
        for grupo in self.grupos_manuales:
            self.decisiones['grupos_confirmados'].append(grupo)
        
        # Recalcular contadores
        aprobados = sum(1 for g in self.decisiones['grupos_confirmados'] if g['accion'] == 'APROBADO')
        rechazados = sum(1 for g in self.decisiones['grupos_confirmados'] if g['accion'] == 'RECHAZADO')
        modificados = sum(1 for g in self.decisiones['grupos_confirmados'] if g['accion'] == 'MODIFICADO')
        manuales = sum(1 for g in self.decisiones['grupos_confirmados'] if g['accion'] == 'MANUAL')
        
        self.decisiones['aprobados'] = aprobados
        self.decisiones['rechazados'] = rechazados
        self.decisiones['modificados'] = modificados
        self.decisiones['grupos_manuales'] = manuales
        self.decisiones['fecha_ultima_modificacion'] = datetime.now().isoformat()
        
        # IMPORTANTE: Actualizar el MISMO archivo (no crear uno nuevo)
        # Esto permite que al volver a abrir, los productos ya usados no aparezcan
        with open(self.archivo_decisiones, 'w', encoding='utf-8') as f:
            json.dump(self.decisiones, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Grupos guardados (archivo actualizado): {self.archivo_decisiones}")
        print(f"\n💾 Archivo actualizado:")
        print(f"   {self.archivo_decisiones}")
        print(f"\n📊 Contadores actualizados:")
        print(f"   ✅ Aprobados: {aprobados}")
        print(f"   ❌ Rechazados: {rechazados}")
        print(f"   ✏️  Modificados: {modificados}")
        print(f"   🔨 Manuales: {manuales}")
        print(f"\n🎯 TOTAL GRUPOS DE VARIANTES: {aprobados + modificados + manuales}")


def main():
    """Ejecuta el agrupador manual"""
    print("=" * 80)
    print("✏️  AGRUPADOR MANUAL DE VARIANTES")
    print("=" * 80)
    
    # Buscar archivo de decisiones más reciente
    archivos_decisiones = sorted(
        Config.GRUPOS_VARIANTES_DIR.glob("variantes_*.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True
    )
    
    if not archivos_decisiones:
        print("\n⚠️  No se encontraron archivos de decisiones")
        print("   Ejecutar primero: python 08_revisor_variantes.py")
        return
    
    archivo = archivos_decisiones[0]
    print(f"\n📄 Archivo de decisiones: {archivo.name}")
    
    confirmar = input("\n¿Usar este archivo? (s/n): ").lower()
    if confirmar != 's':
        print("Operación cancelada")
        return
    
    agrupador = AgrupadorManual(archivo)
    
    if not agrupador.productos_disponibles:
        print("\n⚠️  No hay productos rechazados disponibles para agrupar")
        print("   Todos los productos ya están en grupos o fueron aprobados")
        input("\nPresionar Enter...")
        return
    
    agrupador.menu_principal()


if __name__ == "__main__":
    main()
