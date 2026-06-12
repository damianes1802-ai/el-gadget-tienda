#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
REVISOR DE VARIANTES - MODO INTERACTIVO
Permite revisar y aprobar/rechazar sugerencias de agrupación
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

logger = get_logger('revisor_variantes')


class RevisorVariantes:
    """Revisor interactivo de sugerencias de variantes"""
    
    def __init__(self, archivo_sugerencias: Path):
        """
        Inicializa el revisor
        
        Args:
            archivo_sugerencias: Ruta al archivo de sugerencias
        """
        self.archivo_sugerencias = archivo_sugerencias
        self.sugerencias = None
        self.decisiones = {
            'fecha_revision': datetime.now().isoformat(),
            'total_grupos_revisados': 0,
            'aprobados': 0,
            'rechazados': 0,
            'modificados': 0,
            'grupos_confirmados': []
        }
        self.cargar_sugerencias()
    
    def cargar_sugerencias(self):
        """Carga las sugerencias desde el archivo"""
        with open(self.archivo_sugerencias, 'r', encoding='utf-8') as f:
            self.sugerencias = json.load(f)
        
        logger.info(f"Sugerencias cargadas: {len(self.sugerencias.get('sugerencias', []))} grupos")
    
    def limpiar_pantalla(self):
        """Limpia la pantalla de la consola"""
        os.system('cls' if os.name == 'nt' else 'clear')
    
    def mostrar_grupo(self, grupo: Dict, numero: int, total: int):
        """
        Muestra un grupo de variantes para revisión
        
        Args:
            grupo: Datos del grupo
            numero: Número del grupo actual
            total: Total de grupos
        """
        self.limpiar_pantalla()
        
        confianza = grupo.get('confianza', 0)
        emoji_confianza = "✅" if confianza >= 0.90 else "⚠️" if confianza >= 0.75 else "❓"
        
        print("=" * 80)
        print(f"GRUPO {numero}/{total} - {emoji_confianza} Confianza: {confianza:.0%}")
        print("=" * 80)
        
        print(f"\n📦 Producto base: {grupo.get('producto_base_detectado', 'N/A')}")
        print(f"🏷️  Tipo de variante: {grupo.get('atributo_variante_detectado', 'N/A')}")
        print(f"📊 Total variantes: {grupo.get('total_variantes', 0)}")
        print(f"💡 Acción sugerida: {grupo.get('accion_sugerida', 'N/A')}")
        
        print(f"\n{'─' * 80}")
        print("PRODUCTOS EN ESTE GRUPO:")
        print(f"{'─' * 80}")
        print(f"{'#':<4} {'SKU':<20} {'Variante':<12} {'Precio Costo':>12} {'Precio Venta':>12}")
        print(f"{'─' * 80}")
        
        for i, prod in enumerate(grupo.get('productos', []), 1):
            print(
                f"{i:<4} "
                f"{prod['sku']:<20} "
                f"{prod.get('valor_variante', '?'):<12} "
                f"${prod.get('precio_costo', 0):>10,.0f} "
                f"${prod.get('precio_venta', 0):>10,.0f}"
            )
        
        # Mostrar títulos completos (primeros 3)
        print(f"\n📝 Títulos completos (primeros 3):")
        for i, prod in enumerate(grupo.get('productos', [])[:3], 1):
            titulo = prod.get('titulo', '')
            if len(titulo) > 70:
                titulo = titulo[:67] + "..."
            print(f"   {i}. {titulo}")
        
        if len(grupo.get('productos', [])) > 3:
            print(f"   ... y {len(grupo['productos']) - 3} más")
        
        print(f"\n{'=' * 80}")
    
    def revisar_grupos(self):
        """Revisa todos los grupos interactivamente"""
        grupos = self.sugerencias.get('sugerencias', [])
        
        if not grupos:
            print("\n⚠️  No hay grupos para revisar")
            return
        
        print(f"\n📋 Total de grupos a revisar: {len(grupos)}")
        input("\nPresionar Enter para comenzar...")
        
        for i, grupo in enumerate(grupos, 1):
            self.mostrar_grupo(grupo, i, len(grupos))
            
            # Opciones
            print("\n🔍 OPCIONES:")
            print("  [A] Aprobar este grupo (agrupar como variantes)")
            print("  [R] Rechazar (NO son variantes)")
            print("  [M] Modificar (quitar/agregar productos)")
            print("  [S] Saltar (revisar después)")
            print("  [V] Ver descripción de un producto")
            print("  [Q] Guardar y salir")
            
            while True:
                opcion = input("\nSeleccionar opción: ").upper().strip()
                
                if opcion == 'A':
                    self._aprobar_grupo(grupo)
                    break
                elif opcion == 'R':
                    self._rechazar_grupo(grupo)
                    break
                elif opcion == 'M':
                    self._modificar_grupo(grupo)
                    break
                elif opcion == 'S':
                    print("⏭️  Grupo saltado")
                    input("Presionar Enter para continuar...")
                    break
                elif opcion == 'V':
                    self._ver_descripcion(grupo)
                elif opcion == 'Q':
                    self._guardar_decisiones()
                    return
                else:
                    print("❌ Opción inválida")
        
        # Guardar al final
        self._guardar_decisiones()
        self._mostrar_resumen_final()
    
    def _aprobar_grupo(self, grupo: Dict):
        """Aprueba un grupo de variantes"""
        grupo_confirmado = {
            'id_grupo': grupo['id_sugerencia'].replace('sugerencia', 'grupo'),
            'accion': 'APROBADO',
            'producto_base': grupo['producto_base_detectado'],
            'atributo_variante': grupo['atributo_variante_detectado'],
            'skus': [p['sku'] for p in grupo['productos']],
            'valores_variantes': {
                p['sku']: p.get('valor_variante', '?') 
                for p in grupo['productos']
            },
            'fecha_confirmacion': datetime.now().isoformat(),
            'confianza_original': grupo['confianza']
        }
        
        self.decisiones['grupos_confirmados'].append(grupo_confirmado)
        self.decisiones['aprobados'] += 1
        self.decisiones['total_grupos_revisados'] += 1
        
        print("\n✅ Grupo APROBADO")
        logger.info(f"Grupo aprobado: {grupo['id_sugerencia']}")
        input("Presionar Enter para continuar...")
    
    def _rechazar_grupo(self, grupo: Dict):
        """Rechaza un grupo de variantes"""
        razon = input("\n¿Razón del rechazo? (opcional): ").strip()
        
        grupo_rechazado = {
            'id_grupo': grupo['id_sugerencia'],
            'accion': 'RECHAZADO',
            'razon': razon if razon else 'Son productos diferentes',
            'skus_tratados_como_individuales': [p['sku'] for p in grupo['productos']],
            'fecha_confirmacion': datetime.now().isoformat()
        }
        
        self.decisiones['grupos_confirmados'].append(grupo_rechazado)
        self.decisiones['rechazados'] += 1
        self.decisiones['total_grupos_revisados'] += 1
        
        print("\n❌ Grupo RECHAZADO")
        logger.info(f"Grupo rechazado: {grupo['id_sugerencia']}")
        input("Presionar Enter para continuar...")
    
    def _modificar_grupo(self, grupo: Dict):
        """Permite modificar un grupo de variantes"""
        print("\n✏️  MODO MODIFICACIÓN")
        print("─" * 80)
        
        # Mostrar productos numerados
        print("\nProductos actuales:")
        for i, prod in enumerate(grupo['productos'], 1):
            print(f"  {i}. {prod['sku']} - {prod.get('valor_variante', '?')}")
        
        print("\nIngrese los números de productos a MANTENER")
        print("(separados por comas, ej: 1,2,4)")
        print("O presione Enter para cancelar")
        
        seleccion = input("\nProductos a mantener: ").strip()
        
        if not seleccion:
            print("Modificación cancelada")
            input("Presionar Enter para continuar...")
            return
        
        try:
            indices = [int(x.strip()) - 1 for x in seleccion.split(',')]
            productos_mantener = [
                grupo['productos'][i] for i in indices 
                if 0 <= i < len(grupo['productos'])
            ]
            
            if len(productos_mantener) < 2:
                print("\n❌ Debe mantener al menos 2 productos para formar un grupo")
                input("Presionar Enter...")
                return
            
            grupo_modificado = {
                'id_grupo': grupo['id_sugerencia'].replace('sugerencia', 'grupo'),
                'accion': 'MODIFICADO',
                'producto_base': grupo['producto_base_detectado'],
                'atributo_variante': grupo['atributo_variante_detectado'],
                'skus': [p['sku'] for p in productos_mantener],
                'valores_variantes': {
                    p['sku']: p.get('valor_variante', '?') 
                    for p in productos_mantener
                },
                'skus_removidos': [
                    p['sku'] for p in grupo['productos'] 
                    if p not in productos_mantener
                ],
                'fecha_confirmacion': datetime.now().isoformat(),
                'nota_modificacion': f"Reducido de {len(grupo['productos'])} a {len(productos_mantener)} productos"
            }
            
            self.decisiones['grupos_confirmados'].append(grupo_modificado)
            self.decisiones['modificados'] += 1
            self.decisiones['total_grupos_revisados'] += 1
            
            print(f"\n✅ Grupo MODIFICADO ({len(productos_mantener)} productos mantenidos)")
            logger.info(f"Grupo modificado: {grupo['id_sugerencia']}")
            
        except (ValueError, IndexError) as e:
            print(f"\n❌ Error en la selección: {e}")
        
        input("Presionar Enter para continuar...")
    
    def _ver_descripcion(self, grupo: Dict):
        """Muestra la descripción completa de un producto"""
        print("\n" + "─" * 80)
        for i, prod in enumerate(grupo['productos'], 1):
            print(f"{i}. {prod['sku']}")
        
        try:
            num = int(input("\n¿Qué producto ver? (número): ")) - 1
            if 0 <= num < len(grupo['productos']):
                sku = grupo['productos'][num]['sku']
                metadata = Config.cargar_metadata(sku)
                
                print("\n" + "=" * 80)
                print(f"PRODUCTO: {sku}")
                print("=" * 80)
                print(f"\n📝 Título: {metadata.get('titulo', 'N/A')}")
                print(f"\n📄 Descripción:")
                print(metadata.get('descripcion', 'Sin descripción')[:500])
                print("\n" + "=" * 80)
            else:
                print("❌ Número inválido")
        except (ValueError, Exception) as e:
            print(f"❌ Error: {e}")
        
        input("\nPresionar Enter para volver...")
    
    def _guardar_decisiones(self):
        """Guarda las decisiones tomadas"""
        fecha = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
        archivo = Config.GRUPOS_VARIANTES_DIR / f"variantes_confirmadas_{fecha}.json"
        
        with open(archivo, 'w', encoding='utf-8') as f:
            json.dump(self.decisiones, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Decisiones guardadas en: {archivo}")
        print(f"\n💾 Decisiones guardadas en:")
        print(f"   {archivo}")
    
    def _mostrar_resumen_final(self):
        """Muestra un resumen de las decisiones tomadas"""
        print("\n" + "=" * 80)
        print("📊 RESUMEN DE REVISIÓN")
        print("=" * 80)
        print(f"\nTotal grupos revisados: {self.decisiones['total_grupos_revisados']}")
        print(f"✅ Aprobados: {self.decisiones['aprobados']}")
        print(f"❌ Rechazados: {self.decisiones['rechazados']}")
        print(f"✏️  Modificados: {self.decisiones['modificados']}")
        
        pendientes = (
            len(self.sugerencias.get('sugerencias', [])) - 
            self.decisiones['total_grupos_revisados']
        )
        
        if pendientes > 0:
            print(f"⏭️  Pendientes: {pendientes}")
        
        print("\n" + "=" * 80)
        print("📄 Siguiente paso: Aplicar variantes confirmadas")
        print("   python 09_aplicar_variantes.py")
        print("=" * 80)


def main():
    """Ejecuta el revisor de variantes"""
    print("=" * 80)
    print("🔍 REVISOR DE VARIANTES")
    print("=" * 80)
    
    # Buscar el archivo de sugerencias más reciente
    archivos_sugerencias = sorted(
        Config.GRUPOS_VARIANTES_DIR.glob("sugerencias_variantes_*.json"),
        reverse=True
    )
    
    if not archivos_sugerencias:
        print("\n⚠️  No se encontraron archivos de sugerencias")
        print("   Ejecutar primero: python 07_detector_variantes.py")
        return
    
    archivo = archivos_sugerencias[0]
    print(f"\n📄 Usando archivo: {archivo.name}")
    print(f"   Fecha: {archivo.stat().st_mtime}")
    
    confirmar = input("\n¿Continuar con este archivo? (s/n): ").lower()
    if confirmar != 's':
        print("Operación cancelada")
        return
    
    revisor = RevisorVariantes(archivo)
    revisor.revisar_grupos()


if __name__ == "__main__":
    main()
