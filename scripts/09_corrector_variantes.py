#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CORRECTOR DE DECISIONES DE VARIANTES
Permite modificar decisiones ya tomadas (cambiar aprobado/rechazado)
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List

# Imports locales
import sys
sys.path.append(str(Path(__file__).parent))
from utils.config import Config
from utils.logger import get_logger

logger = get_logger('corrector_variantes')


class CorrectorDecisiones:
    """Permite corregir decisiones de variantes ya tomadas"""
    
    def __init__(self, archivo_decisiones: Path):
        """Inicializa el corrector"""
        self.archivo_decisiones = archivo_decisiones
        self.decisiones = None
        self.cambios_realizados = 0
        self.cargar_decisiones()
    
    def cargar_decisiones(self):
        """Carga las decisiones desde el archivo"""
        with open(self.archivo_decisiones, 'r', encoding='utf-8') as f:
            self.decisiones = json.load(f)
        
        logger.info(f"Decisiones cargadas: {len(self.decisiones.get('grupos_confirmados', []))} grupos")
    
    def guardar_decisiones(self):
        """Guarda las decisiones modificadas"""
        # Actualizar contadores
        aprobados = sum(1 for g in self.decisiones['grupos_confirmados'] if g['accion'] == 'APROBADO')
        rechazados = sum(1 for g in self.decisiones['grupos_confirmados'] if g['accion'] == 'RECHAZADO')
        modificados = sum(1 for g in self.decisiones['grupos_confirmados'] if g['accion'] == 'MODIFICADO')
        
        self.decisiones['aprobados'] = aprobados
        self.decisiones['rechazados'] = rechazados
        self.decisiones['modificados'] = modificados
        self.decisiones['fecha_ultima_modificacion'] = datetime.now().isoformat()
        
        # Guardar con nuevo nombre
        fecha = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
        nuevo_archivo = Config.GRUPOS_VARIANTES_DIR / f"variantes_confirmadas_corregido_{fecha}.json"
        
        with open(nuevo_archivo, 'w', encoding='utf-8') as f:
            json.dump(self.decisiones, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Decisiones corregidas guardadas en: {nuevo_archivo}")
        print(f"\n💾 Decisiones corregidas guardadas en:")
        print(f"   {nuevo_archivo}")
    
    def limpiar_pantalla(self):
        """Limpia la pantalla"""
        os.system('cls' if os.name == 'nt' else 'clear')
    
    def mostrar_resumen(self):
        """Muestra un resumen de las decisiones actuales"""
        grupos = self.decisiones.get('grupos_confirmados', [])
        
        aprobados = [g for g in grupos if g['accion'] == 'APROBADO']
        rechazados = [g for g in grupos if g['accion'] == 'RECHAZADO']
        modificados = [g for g in grupos if g['accion'] == 'MODIFICADO']
        manuales = [g for g in grupos if g['accion'] == 'MANUAL']
        
        print("\n" + "=" * 80)
        print("📊 RESUMEN DE DECISIONES ACTUALES")
        print("=" * 80)
        print(f"\nTotal grupos: {len(grupos)}")
        print(f"✅ Aprobados: {len(aprobados)}")
        print(f"❌ Rechazados: {len(rechazados)}")
        print(f"✏️  Modificados: {len(modificados)}")
        print(f"🔨 Manuales: {len(manuales)}")
        print(f"\n🎯 Total grupos de variantes: {len(aprobados) + len(modificados) + len(manuales)}")
        print("=" * 80)
    
    def menu_principal(self):
        """Menú principal del corrector"""
        while True:
            self.limpiar_pantalla()
            self.mostrar_resumen()
            
            print("\n📋 OPCIONES:")
            print("  1️⃣  Ver grupos APROBADOS")
            print("  2️⃣  Ver grupos RECHAZADOS")
            print("  3️⃣  Ver grupos MANUALES")
            print("  4️⃣  Cambiar decisión de un grupo específico")
            print("  5️⃣  Buscar grupo por palabra clave")
            print("  6️⃣  Eliminar un grupo de las decisiones")
            print("  0️⃣  Guardar cambios y salir")
            
            opcion = input("\nSeleccionar opción: ").strip()
            
            if opcion == '1':
                self.ver_grupos_por_tipo('APROBADO')
            elif opcion == '2':
                self.ver_grupos_por_tipo('RECHAZADO')
            elif opcion == '3':
                self.ver_grupos_por_tipo('MANUAL')
            elif opcion == '4':
                self.cambiar_decision()
            elif opcion == '5':
                self.buscar_grupo()
            elif opcion == '6':
                self.eliminar_grupo()
            elif opcion == '0':
                if self.cambios_realizados > 0:
                    self.guardar_decisiones()
                    print(f"\n✅ Se guardaron {self.cambios_realizados} cambios")
                else:
                    print("\n⚠️  No se realizaron cambios")
                input("\nPresionar Enter para salir...")
                break
            else:
                print("❌ Opción inválida")
                input("Presionar Enter...")
    
    def ver_grupos_por_tipo(self, tipo: str):
        """Muestra grupos filtrados por tipo de acción"""
        grupos = [g for g in self.decisiones['grupos_confirmados'] if g['accion'] == tipo]
        
        self.limpiar_pantalla()
        
        # Emoji según tipo
        emoji_mapa = {
            'APROBADO': '✅',
            'RECHAZADO': '❌',
            'MODIFICADO': '✏️',
            'MANUAL': '🔨'
        }
        emoji = emoji_mapa.get(tipo, '❓')
        
        print("=" * 80)
        print(f"{emoji} GRUPOS {tipo}S ({len(grupos)} total)")
        print("=" * 80)
        
        if not grupos:
            print("\n⚠️  No hay grupos con este estado")
            input("\nPresionar Enter para volver...")
            return
        
        for i, grupo in enumerate(grupos, 1):
            # Mostrar fecha de creación para grupos manuales
            fecha_info = ""
            if tipo == 'MANUAL':
                fecha = grupo.get('fecha_creacion', grupo.get('fecha_confirmacion', 'N/A'))
                if 'T' in fecha:
                    fecha = fecha.split('T')[0]
                fecha_info = f" (creado: {fecha})"
            
            print(f"\n{i}. {grupo.get('producto_base', 'Sin nombre')}{fecha_info}")
            print(f"   ID: {grupo.get('id_grupo', 'N/A')}")
            print(f"   Tipo: {grupo.get('atributo_variante', 'N/A')}")
            print(f"   Productos: {len(grupo.get('skus', []))}")
            
            # Mostrar valores de variantes para grupos manuales
            if tipo == 'MANUAL' and grupo.get('valores_variantes'):
                print(f"   Variantes:")
                valores = grupo.get('valores_variantes', {})
                skus = grupo.get('skus', [])[:3]  # Primeros 3
                for sku in skus:
                    valor = valores.get(sku, '?')
                    print(f"      • {sku} → {valor}")
                if len(grupo.get('skus', [])) > 3:
                    print(f"      ... (+{len(grupo['skus']) - 3} más)")
            else:
                print(f"   SKUs: {', '.join(grupo.get('skus', [])[:3])}", end='')
                if len(grupo.get('skus', [])) > 3:
                    print(f" ... (+{len(grupo['skus']) - 3} más)")
                else:
                    print()
        
        print("\n" + "─" * 80)
        print("¿Cambiar alguno de estos grupos?")
        print("  [Número] para cambiar")
        print("  [Enter] para volver")
        
        seleccion = input("\nSelección: ").strip()
        
        if seleccion.isdigit():
            idx = int(seleccion) - 1
            if 0 <= idx < len(grupos):
                self._cambiar_decision_grupo(grupos[idx])
    
    def cambiar_decision(self):
        """Cambia la decisión de un grupo específico"""
        self.limpiar_pantalla()
        print("=" * 80)
        print("🔄 CAMBIAR DECISIÓN DE UN GRUPO")
        print("=" * 80)
        
        id_grupo = input("\n🔑 Ingrese el ID del grupo (ej: grupo_001): ").strip()
        
        # Buscar el grupo
        grupo = None
        for g in self.decisiones['grupos_confirmados']:
            if g.get('id_grupo') == id_grupo:
                grupo = g
                break
        
        if not grupo:
            print(f"\n❌ No se encontró el grupo '{id_grupo}'")
            input("Presionar Enter...")
            return
        
        self._cambiar_decision_grupo(grupo)
    
    def _cambiar_decision_grupo(self, grupo: Dict):
        """Cambia la decisión de un grupo específico"""
        self.limpiar_pantalla()
        
        es_manual = grupo.get('accion') == 'MANUAL'
        
        print("=" * 80)
        print(f"🔄 CAMBIAR DECISIÓN: {grupo.get('producto_base', 'N/A')}")
        print("=" * 80)
        
        print(f"\n📝 ID: {grupo.get('id_grupo')}")
        print(f"🏷️  Tipo: {grupo.get('atributo_variante', 'N/A')}")
        print(f"📊 Productos: {len(grupo.get('skus', []))}")
        print(f"\n✅ Estado actual: {grupo.get('accion')}")
        
        if es_manual:
            print(f"🔨 Origen: Creado manualmente")
            fecha = grupo.get('fecha_creacion', 'N/A')
            if 'T' in fecha:
                fecha = fecha.split('T')[0]
            print(f"📅 Fecha: {fecha}")
        
        print(f"\n📋 SKUs en este grupo:")
        
        if es_manual and grupo.get('valores_variantes'):
            # Mostrar con valores de variante
            valores = grupo.get('valores_variantes', {})
            for sku in grupo.get('skus', []):
                valor = valores.get(sku, '?')
                print(f"   • {sku} → {valor}")
        else:
            # Mostrar solo SKUs
            for sku in grupo.get('skus', []):
                variante = grupo.get('valores_variantes', {}).get(sku, '?')
                print(f"   • {sku} → {variante}")
        
        print("\n" + "─" * 80)
        print("¿Cambiar a qué estado?")
        print("  [A] APROBADO")
        print("  [R] RECHAZADO")
        print("  [M] MODIFICADO")
        if not es_manual:
            print("  [X] MANUAL (convertir a manual)")
        print("  [E] Eliminar este grupo")
        print("  [C] Cancelar")
        
        opcion = input("\nSelección: ").upper().strip()
        
        if opcion == 'A':
            grupo['accion'] = 'APROBADO'
            print("\n✅ Cambiado a APROBADO")
            self.cambios_realizados += 1
        elif opcion == 'R':
            grupo['accion'] = 'RECHAZADO'
            # Si era manual, agregar campo para tratarlos como individuales
            if es_manual:
                grupo['skus_tratados_como_individuales'] = grupo.get('skus', [])
            print("\n❌ Cambiado a RECHAZADO")
            self.cambios_realizados += 1
        elif opcion == 'M':
            grupo['accion'] = 'MODIFICADO'
            print("\n✏️  Cambiado a MODIFICADO")
            self.cambios_realizados += 1
        elif opcion == 'X' and not es_manual:
            grupo['accion'] = 'MANUAL'
            # Agregar campos de grupo manual si no existen
            if 'fecha_creacion' not in grupo:
                grupo['fecha_creacion'] = datetime.now().isoformat()
            if 'origen' not in grupo:
                grupo['origen'] = 'convertido_desde_' + grupo.get('accion', 'aprobado').lower()
            print("\n🔨 Convertido a MANUAL")
            self.cambios_realizados += 1
        elif opcion == 'E':
            confirmar = input("\n⚠️  ¿Eliminar este grupo? (s/n): ").lower()
            if confirmar == 's':
                self.decisiones['grupos_confirmados'].remove(grupo)
                print("\n🗑️  Grupo eliminado")
                self.cambios_realizados += 1
        elif opcion == 'C':
            print("\nCancelado")
        else:
            print("\n❌ Opción inválida")
        
        input("\nPresionar Enter para continuar...")
    
    def buscar_grupo(self):
        """Busca grupos por palabra clave"""
        self.limpiar_pantalla()
        print("=" * 80)
        print("🔍 BUSCAR GRUPO")
        print("=" * 80)
        
        palabra = input("\n🔑 Palabra clave (en el nombre del producto): ").strip().lower()
        
        if not palabra:
            return
        
        # Buscar grupos que contengan la palabra
        grupos_encontrados = []
        for grupo in self.decisiones['grupos_confirmados']:
            producto_base = grupo.get('producto_base', '').lower()
            if palabra in producto_base:
                grupos_encontrados.append(grupo)
        
        if not grupos_encontrados:
            print(f"\n⚠️  No se encontraron grupos con '{palabra}'")
            input("Presionar Enter...")
            return
        
        print(f"\n📋 Grupos encontrados ({len(grupos_encontrados)}):")
        print("─" * 80)
        
        for i, grupo in enumerate(grupos_encontrados, 1):
            estado_emoji = {
                'APROBADO': '✅',
                'RECHAZADO': '❌',
                'MODIFICADO': '✏️'
            }.get(grupo.get('accion'), '❓')
            
            print(f"\n{i}. {estado_emoji} {grupo.get('producto_base', 'N/A')}")
            print(f"   ID: {grupo.get('id_grupo')}")
            print(f"   Estado: {grupo.get('accion')}")
            print(f"   SKUs: {', '.join(grupo.get('skus', [])[:3])}", end='')
            if len(grupo.get('skus', [])) > 3:
                print(f" ... (+{len(grupo['skus']) - 3} más)")
            else:
                print()
        
        print("\n" + "─" * 80)
        print("¿Modificar alguno?")
        print("  [Número] para cambiar")
        print("  [Enter] para volver")
        
        seleccion = input("\nSelección: ").strip()
        
        if seleccion.isdigit():
            idx = int(seleccion) - 1
            if 0 <= idx < len(grupos_encontrados):
                self._cambiar_decision_grupo(grupos_encontrados[idx])
    
    def eliminar_grupo(self):
        """Elimina un grupo de las decisiones"""
        self.limpiar_pantalla()
        print("=" * 80)
        print("🗑️  ELIMINAR GRUPO")
        print("=" * 80)
        
        id_grupo = input("\n🔑 ID del grupo a eliminar: ").strip()
        
        # Buscar el grupo
        grupo = None
        for g in self.decisiones['grupos_confirmados']:
            if g.get('id_grupo') == id_grupo:
                grupo = g
                break
        
        if not grupo:
            print(f"\n❌ No se encontró el grupo '{id_grupo}'")
            input("Presionar Enter...")
            return
        
        print(f"\n📝 Grupo: {grupo.get('producto_base')}")
        print(f"   SKUs: {', '.join(grupo.get('skus', []))}")
        
        confirmar = input("\n⚠️  ¿Confirmar eliminación? (s/n): ").lower()
        
        if confirmar == 's':
            self.decisiones['grupos_confirmados'].remove(grupo)
            print("\n✅ Grupo eliminado")
            self.cambios_realizados += 1
        else:
            print("\nCancelado")
        
        input("\nPresionar Enter...")


def main():
    """Ejecuta el corrector"""
    print("=" * 80)
    print("🔧 CORRECTOR DE DECISIONES DE VARIANTES")
    print("=" * 80)
    
    # Buscar archivos de decisiones (variantes_confirmadas_* Y variantes_con_manuales_*)
    archivos_confirmadas = list(Config.GRUPOS_VARIANTES_DIR.glob("variantes_confirmadas_*.json"))
    archivos_manuales = list(Config.GRUPOS_VARIANTES_DIR.glob("variantes_con_manuales_*.json"))
    
    # Combinar y ordenar por fecha de modificación
    todos_archivos = archivos_confirmadas + archivos_manuales
    archivos_decisiones = sorted(
        todos_archivos,
        key=lambda p: p.stat().st_mtime,
        reverse=True
    )
    
    if not archivos_decisiones:
        print("\n⚠️  No se encontraron archivos de decisiones")
        print("   Ejecutar primero: python 08_revisor_variantes.py")
        return
    
    archivo = archivos_decisiones[0]
    print(f"\n📄 Archivo más reciente: {archivo.name}")
    print(f"   Fecha: {datetime.fromtimestamp(archivo.stat().st_mtime).strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Mostrar info del archivo
    with open(archivo, 'r', encoding='utf-8') as f:
        datos = json.load(f)
        total = len(datos.get('grupos_confirmados', []))
        aprobados = sum(1 for g in datos['grupos_confirmados'] if g['accion'] == 'APROBADO')
        rechazados = sum(1 for g in datos['grupos_confirmados'] if g['accion'] == 'RECHAZADO')
        manuales = sum(1 for g in datos['grupos_confirmados'] if g['accion'] == 'MANUAL')
        
        print(f"\n📊 Contenido del archivo:")
        print(f"   Total grupos: {total}")
        print(f"   ✅ Aprobados: {aprobados}")
        print(f"   ❌ Rechazados: {rechazados}")
        print(f"   🔨 Manuales: {manuales}")
    
    confirmar = input("\n¿Usar este archivo? (s/n): ").lower()
    if confirmar != 's':
        print("Operación cancelada")
        return
    
    corrector = CorrectorDecisiones(archivo)
    corrector.menu_principal()


if __name__ == "__main__":
    main()
