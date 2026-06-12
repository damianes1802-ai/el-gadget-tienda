#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GESTOR DE CONFIGURACIÓN DE PRECIOS - MODO INTERACTIVO
Permite editar cargos, márgenes y perfiles de precio desde la consola
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any

# Imports locales
import sys
sys.path.append(str(Path(__file__).parent))
from utils.config import Config
from utils.logger import get_logger

logger = get_logger('config_precios')


class GestorConfiguracionPrecios:
    """Gestor interactivo de configuración de precios"""
    
    def __init__(self):
        """Inicializa el gestor"""
        self.config_file = Config.PRECIOS_DIR / "config_precios_v2.json"
        self.cargar_configuracion()
    
    def cargar_configuracion(self):
        """Carga la configuración actual"""
        if self.config_file.exists():
            with open(self.config_file, 'r', encoding='utf-8') as f:
                self.config = json.load(f)
        else:
            logger.warning("Archivo de configuración no encontrado, creando uno nuevo")
            self.config = self._crear_config_inicial()
            self.guardar_configuracion()
    
    def guardar_configuracion(self):
        """Guarda la configuración actual"""
        # Actualizar fecha
        self.config['fecha_actualizacion'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        with open(self.config_file, 'w', encoding='utf-8') as f:
            json.dump(self.config, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Configuración guardada en: {self.config_file}")
    
    def _crear_config_inicial(self) -> Dict:
        """Crea configuración inicial por defecto"""
        return {
            "version": "2.0",
            "fecha_actualizacion": datetime.now().strftime('%Y-%m-%d'),
            "moneda": "ARS",
            "perfiles_precio": {
                "default": {
                    "nombre": "Estándar",
                    "descripcion": "Configuración por defecto",
                    "activo": True,
                    "cargos_fijos": [],
                    "margen_porcentaje": 50,
                    "redondeo": {
                        "activo": True,
                        "multiplo": 500,
                        "direccion": "arriba"
                    }
                }
            },
            "reglas_asignacion": {},
            "historial_cambios": []
        }
    
    def registrar_cambio(self, descripcion: str, perfil: str = None):
        """Registra un cambio en el historial"""
        cambio = {
            "fecha": datetime.now().isoformat(),
            "usuario": "consola",
            "cambio": descripcion
        }
        if perfil:
            cambio["perfil_modificado"] = perfil
        
        if "historial_cambios" not in self.config:
            self.config["historial_cambios"] = []
        
        self.config["historial_cambios"].append(cambio)
    
    # =========================================================================
    # MENÚ PRINCIPAL
    # =========================================================================
    
    def menu_principal(self):
        """Muestra el menú principal"""
        while True:
            self._limpiar_pantalla()
            print("=" * 80)
            print("💰 GESTOR DE CONFIGURACIÓN DE PRECIOS")
            print("=" * 80)
            print(f"\nArchivo: {self.config_file}")
            print(f"Última actualización: {self.config.get('fecha_actualizacion', 'N/A')}")
            print(f"Moneda: {self.config.get('moneda', 'ARS')}\n")
            
            print("1️⃣  Ver perfiles de precio")
            print("2️⃣  Crear nuevo perfil")
            print("3️⃣  Editar perfil existente")
            print("4️⃣  Activar/Desactivar perfil")
            print("5️⃣  Gestionar cargos (agregar/editar/eliminar)")
            print("6️⃣  Cambiar márgenes de ganancia")
            print("7️⃣  Configurar redondeo")
            print("8️⃣  Ver historial de cambios")
            print("9️⃣  Simular cálculo de precio")
            print("0️⃣  Guardar y salir")
            
            opcion = input("\nSeleccionar opción: ").strip()
            
            if opcion == "1":
                self.ver_perfiles()
            elif opcion == "2":
                self.crear_perfil()
            elif opcion == "3":
                self.editar_perfil()
            elif opcion == "4":
                self.activar_desactivar_perfil()
            elif opcion == "5":
                self.gestionar_cargos()
            elif opcion == "6":
                self.cambiar_margenes()
            elif opcion == "7":
                self.configurar_redondeo()
            elif opcion == "8":
                self.ver_historial()
            elif opcion == "9":
                self.simular_calculo()
            elif opcion == "0":
                self.guardar_configuracion()
                print("\n✅ Configuración guardada. ¡Hasta luego!")
                break
            else:
                print("\n❌ Opción inválida")
                input("\nPresionar Enter para continuar...")
    
    # =========================================================================
    # VER PERFILES
    # =========================================================================
    
    def ver_perfiles(self):
        """Muestra todos los perfiles de precio"""
        self._limpiar_pantalla()
        print("=" * 80)
        print("📊 PERFILES DE PRECIO")
        print("=" * 80)
        
        perfiles = self.config.get('perfiles_precio', {})
        
        if not perfiles:
            print("\n⚠️  No hay perfiles configurados")
        else:
            for key, perfil in perfiles.items():
                estado = "✅ ACTIVO" if perfil.get('activo', False) else "⭕ INACTIVO"
                print(f"\n{'─' * 80}")
                print(f"🔑 ID: {key}")
                print(f"📝 Nombre: {perfil.get('nombre', 'Sin nombre')}")
                print(f"📄 Descripción: {perfil.get('descripcion', 'Sin descripción')}")
                print(f"🎯 Estado: {estado}")
                print(f"💵 Margen: {perfil.get('margen_porcentaje', 0)}%")
                
                # Cargos
                cargos = perfil.get('cargos_fijos', [])
                if cargos:
                    print(f"\n💰 Cargos fijos:")
                    total_cargos = 0
                    for cargo in cargos:
                        if cargo.get('activo', True):
                            valor = cargo.get('valor', 0)
                            total_cargos += valor
                            print(f"   • {cargo.get('nombre', 'Sin nombre')}: ${valor:,.0f}")
                    print(f"   {'─' * 40}")
                    print(f"   TOTAL CARGOS: ${total_cargos:,.0f}")
                
                # Redondeo
                redondeo = perfil.get('redondeo', {})
                if redondeo.get('activo', False):
                    print(f"\n🔄 Redondeo: Múltiplo de {redondeo.get('multiplo', 500)}")
        
        input("\n\nPresionar Enter para volver...")
    
    # =========================================================================
    # GESTIONAR CARGOS
    # =========================================================================
    
    def gestionar_cargos(self):
        """Menú de gestión de cargos"""
        while True:
            self._limpiar_pantalla()
            print("=" * 80)
            print("💰 GESTIÓN DE CARGOS")
            print("=" * 80)
            
            # Seleccionar perfil
            perfil_id = self._seleccionar_perfil()
            if not perfil_id:
                break
            
            perfil = self.config['perfiles_precio'][perfil_id]
            
            print(f"\n📝 Perfil: {perfil.get('nombre', perfil_id)}")
            print("\n1️⃣  Ver cargos actuales")
            print("2️⃣  Agregar nuevo cargo")
            print("3️⃣  Editar cargo existente")
            print("4️⃣  Eliminar cargo")
            print("5️⃣  Activar/Desactivar cargo")
            print("0️⃣  Volver")
            
            opcion = input("\nSeleccionar opción: ").strip()
            
            if opcion == "1":
                self._ver_cargos(perfil_id)
            elif opcion == "2":
                self._agregar_cargo(perfil_id)
            elif opcion == "3":
                self._editar_cargo(perfil_id)
            elif opcion == "4":
                self._eliminar_cargo(perfil_id)
            elif opcion == "5":
                self._toggle_cargo(perfil_id)
            elif opcion == "0":
                break
    
    def _ver_cargos(self, perfil_id: str):
        """Muestra los cargos de un perfil"""
        perfil = self.config['perfiles_precio'][perfil_id]
        cargos = perfil.get('cargos_fijos', [])
        
        print("\n" + "─" * 80)
        print("CARGOS ACTUALES:")
        print("─" * 80)
        
        if not cargos:
            print("⚠️  No hay cargos configurados")
        else:
            total_activos = 0
            for i, cargo in enumerate(cargos, 1):
                estado = "✅" if cargo.get('activo', True) else "⭕"
                valor = cargo.get('valor', 0)
                print(f"\n{i}. {estado} {cargo.get('nombre', 'Sin nombre')}")
                print(f"   Valor: ${valor:,.0f}")
                print(f"   Notas: {cargo.get('notas', 'Sin notas')}")
                
                if cargo.get('activo', True):
                    total_activos += valor
            
            print(f"\n{'─' * 80}")
            print(f"💵 TOTAL CARGOS ACTIVOS: ${total_activos:,.0f}")
        
        input("\n\nPresionar Enter para continuar...")
    
    def _agregar_cargo(self, perfil_id: str):
        """Agrega un nuevo cargo al perfil"""
        print("\n" + "─" * 80)
        print("AGREGAR NUEVO CARGO")
        print("─" * 80)
        
        nombre = input("\n📝 Nombre del cargo: ").strip()
        if not nombre:
            print("❌ El nombre no puede estar vacío")
            input("Presionar Enter...")
            return
        
        try:
            valor = float(input("💵 Valor del cargo: $").strip())
        except ValueError:
            print("❌ Valor inválido")
            input("Presionar Enter...")
            return
        
        notas = input("📄 Notas (opcional): ").strip()
        
        # Generar ID único
        perfil = self.config['perfiles_precio'][perfil_id]
        if 'cargos_fijos' not in perfil:
            perfil['cargos_fijos'] = []
        
        cargo_id = f"cargo_{len(perfil['cargos_fijos']) + 1:03d}"
        
        nuevo_cargo = {
            "id": cargo_id,
            "nombre": nombre,
            "valor": valor,
            "activo": True,
            "notas": notas if notas else "Sin notas"
        }
        
        perfil['cargos_fijos'].append(nuevo_cargo)
        
        self.registrar_cambio(f"Cargo agregado: {nombre} (${valor:,.0f})", perfil_id)
        
        print(f"\n✅ Cargo '{nombre}' agregado correctamente")
        input("\nPresionar Enter para continuar...")
    
    def _editar_cargo(self, perfil_id: str):
        """Edita un cargo existente"""
        perfil = self.config['perfiles_precio'][perfil_id]
        cargos = perfil.get('cargos_fijos', [])
        
        if not cargos:
            print("\n⚠️  No hay cargos para editar")
            input("Presionar Enter...")
            return
        
        self._ver_cargos(perfil_id)
        
        try:
            idx = int(input("\n¿Qué cargo editar? (número): ")) - 1
            if idx < 0 or idx >= len(cargos):
                raise ValueError
        except ValueError:
            print("❌ Número inválido")
            input("Presionar Enter...")
            return
        
        cargo = cargos[idx]
        
        print(f"\n📝 Editando: {cargo.get('nombre')}")
        print("(Dejar vacío para mantener valor actual)")
        
        nuevo_nombre = input(f"\nNombre [{cargo.get('nombre')}]: ").strip()
        if nuevo_nombre:
            cargo['nombre'] = nuevo_nombre
        
        nuevo_valor = input(f"Valor [${cargo.get('valor'):,.0f}]: ").strip()
        if nuevo_valor:
            try:
                cargo['valor'] = float(nuevo_valor)
            except ValueError:
                print("❌ Valor inválido, manteniendo el anterior")
        
        nuevas_notas = input(f"Notas [{cargo.get('notas')}]: ").strip()
        if nuevas_notas:
            cargo['notas'] = nuevas_notas
        
        self.registrar_cambio(f"Cargo editado: {cargo.get('nombre')}", perfil_id)
        
        print("\n✅ Cargo actualizado correctamente")
        input("\nPresionar Enter para continuar...")
    
    def _eliminar_cargo(self, perfil_id: str):
        """Elimina un cargo"""
        perfil = self.config['perfiles_precio'][perfil_id]
        cargos = perfil.get('cargos_fijos', [])
        
        if not cargos:
            print("\n⚠️  No hay cargos para eliminar")
            input("Presionar Enter...")
            return
        
        self._ver_cargos(perfil_id)
        
        try:
            idx = int(input("\n¿Qué cargo eliminar? (número): ")) - 1
            if idx < 0 or idx >= len(cargos):
                raise ValueError
        except ValueError:
            print("❌ Número inválido")
            input("Presionar Enter...")
            return
        
        cargo = cargos[idx]
        confirmar = input(f"\n⚠️  ¿Eliminar '{cargo.get('nombre')}'? (s/n): ").lower()
        
        if confirmar == 's':
            nombre_eliminado = cargo.get('nombre')
            cargos.pop(idx)
            self.registrar_cambio(f"Cargo eliminado: {nombre_eliminado}", perfil_id)
            print("\n✅ Cargo eliminado")
        else:
            print("\n❌ Operación cancelada")
        
        input("\nPresionar Enter para continuar...")
    
    def _toggle_cargo(self, perfil_id: str):
        """Activa/desactiva un cargo"""
        perfil = self.config['perfiles_precio'][perfil_id]
        cargos = perfil.get('cargos_fijos', [])
        
        if not cargos:
            print("\n⚠️  No hay cargos")
            input("Presionar Enter...")
            return
        
        self._ver_cargos(perfil_id)
        
        try:
            idx = int(input("\n¿Qué cargo activar/desactivar? (número): ")) - 1
            if idx < 0 or idx >= len(cargos):
                raise ValueError
        except ValueError:
            print("❌ Número inválido")
            input("Presionar Enter...")
            return
        
        cargo = cargos[idx]
        cargo['activo'] = not cargo.get('activo', True)
        
        estado = "activado" if cargo['activo'] else "desactivado"
        self.registrar_cambio(f"Cargo {estado}: {cargo.get('nombre')}", perfil_id)
        
        print(f"\n✅ Cargo {estado}")
        input("\nPresionar Enter para continuar...")
    
    # =========================================================================
    # UTILIDADES
    # =========================================================================
    
    def _seleccionar_perfil(self) -> str:
        """Permite seleccionar un perfil"""
        perfiles = self.config.get('perfiles_precio', {})
        
        if not perfiles:
            print("\n⚠️  No hay perfiles configurados")
            input("Presionar Enter...")
            return None
        
        print("\nPerfiles disponibles:")
        lista_perfiles = list(perfiles.items())
        for i, (key, perfil) in enumerate(lista_perfiles, 1):
            print(f"{i}. {perfil.get('nombre', key)}")
        
        try:
            idx = int(input("\nSeleccionar perfil (número): ")) - 1
            if idx < 0 or idx >= len(lista_perfiles):
                raise ValueError
            return lista_perfiles[idx][0]
        except ValueError:
            print("❌ Número inválido")
            input("Presionar Enter...")
            return None
    
    def _limpiar_pantalla(self):
        """Limpia la pantalla de la consola"""
        os.system('cls' if os.name == 'nt' else 'clear')
    
    def simular_calculo(self):
        """Simula el cálculo de precio para un producto"""
        print("\n" + "=" * 80)
        print("🧮 SIMULADOR DE CÁLCULO DE PRECIO")
        print("=" * 80)
        
        perfil_id = self._seleccionar_perfil()
        if not perfil_id:
            return
        
        perfil = self.config['perfiles_precio'][perfil_id]
        
        try:
            precio_costo = float(input("\n💵 Ingrese precio de costo: $").strip())
        except ValueError:
            print("❌ Valor inválido")
            input("Presionar Enter...")
            return
        
        # Calcular
        cargos_activos = sum(c['valor'] for c in perfil.get('cargos_fijos', []) if c.get('activo', True))
        subtotal = precio_costo + cargos_activos
        margen = perfil.get('margen_porcentaje', 50)
        precio_con_margen = subtotal * (1 + margen / 100)
        
        # Redondeo
        redondeo = perfil.get('redondeo', {})
        if redondeo.get('activo', True):
            multiplo = redondeo.get('multiplo', 500)
            resto = precio_con_margen % multiplo
            if resto > 0:
                precio_final = precio_con_margen + (multiplo - resto)
            else:
                precio_final = precio_con_margen
        else:
            precio_final = precio_con_margen
        
        # Mostrar resultados
        print("\n" + "─" * 80)
        print("CÁLCULO DETALLADO:")
        print("─" * 80)
        print(f"\n1. Precio costo: ${precio_costo:,.2f}")
        print(f"2. + Cargos fijos: ${cargos_activos:,.2f}")
        print(f"   {'─' * 40}")
        print(f"   Subtotal: ${subtotal:,.2f}")
        print(f"\n3. × Margen {margen}%: ${precio_con_margen:,.2f}")
        print(f"4. Redondeo (múltiplo de {redondeo.get('multiplo', 500)}): ${precio_final:,.2f}")
        print(f"\n{'═' * 80}")
        print(f"💰 PRECIO FINAL DE VENTA: ${precio_final:,.0f}")
        print(f"{'═' * 80}")
        
        ganancia = precio_final - precio_costo
        porcentaje_ganancia = (ganancia / precio_costo) * 100
        
        print(f"\n📊 Ganancia neta: ${ganancia:,.0f} ({porcentaje_ganancia:.1f}%)")
        
        input("\n\nPresionar Enter para continuar...")
    
    def cambiar_margenes(self):
        """Cambia el margen de ganancia de un perfil"""
        perfil_id = self._seleccionar_perfil()
        if not perfil_id:
            return
        
        perfil = self.config['perfiles_precio'][perfil_id]
        margen_actual = perfil.get('margen_porcentaje', 50)
        
        print(f"\n📊 Margen actual: {margen_actual}%")
        
        try:
            nuevo_margen = float(input("Nuevo margen %: ").strip())
            perfil['margen_porcentaje'] = nuevo_margen
            self.registrar_cambio(f"Margen cambiado de {margen_actual}% a {nuevo_margen}%", perfil_id)
            print(f"\n✅ Margen actualizado a {nuevo_margen}%")
        except ValueError:
            print("❌ Valor inválido")
        
        input("\nPresionar Enter...")
    
    def configurar_redondeo(self):
        """Configura el redondeo de precios"""
        perfil_id = self._seleccionar_perfil()
        if not perfil_id:
            return
        
        perfil = self.config['perfiles_precio'][perfil_id]
        redondeo = perfil.get('redondeo', {})
        
        print(f"\n🔄 Configuración actual:")
        print(f"   Activo: {redondeo.get('activo', True)}")
        print(f"   Múltiplo: {redondeo.get('multiplo', 500)}")
        
        activar = input("\n¿Activar redondeo? (s/n): ").lower()
        redondeo['activo'] = activar == 's'
        
        if redondeo['activo']:
            try:
                multiplo = int(input("Múltiplo de redondeo: "))
                redondeo['multiplo'] = multiplo
            except ValueError:
                print("❌ Valor inválido, manteniendo anterior")
        
        perfil['redondeo'] = redondeo
        self.registrar_cambio(f"Redondeo configurado: {redondeo}", perfil_id)
        print("\n✅ Redondeo actualizado")
        input("\nPresionar Enter...")
    
    def crear_perfil(self):
        """Crea un nuevo perfil de precios"""
        print("\n" + "=" * 80)
        print("➕ CREAR NUEVO PERFIL")
        print("=" * 80)
        
        perfil_id = input("\n🔑 ID del perfil (ej: 'premium', 'oferta'): ").strip().lower()
        if not perfil_id:
            print("❌ El ID no puede estar vacío")
            input("Presionar Enter...")
            return
        
        if perfil_id in self.config.get('perfiles_precio', {}):
            print(f"❌ Ya existe un perfil con ID '{perfil_id}'")
            input("Presionar Enter...")
            return
        
        nombre = input("📝 Nombre del perfil: ").strip()
        descripcion = input("📄 Descripción: ").strip()
        
        try:
            margen = float(input("💵 Margen de ganancia (%): ").strip())
        except ValueError:
            margen = 50
        
        nuevo_perfil = {
            "nombre": nombre,
            "descripcion": descripcion,
            "activo": False,
            "cargos_fijos": [],
            "margen_porcentaje": margen,
            "redondeo": {
                "activo": True,
                "multiplo": 500,
                "direccion": "arriba"
            }
        }
        
        if 'perfiles_precio' not in self.config:
            self.config['perfiles_precio'] = {}
        
        self.config['perfiles_precio'][perfil_id] = nuevo_perfil
        self.registrar_cambio(f"Perfil creado: {nombre}", perfil_id)
        
        print(f"\n✅ Perfil '{nombre}' creado correctamente")
        print("   (Está INACTIVO por defecto, podés activarlo desde el menú)")
        input("\nPresionar Enter...")
    
    def editar_perfil(self):
        """Edita un perfil existente"""
        perfil_id = self._seleccionar_perfil()
        if not perfil_id:
            return
        
        perfil = self.config['perfiles_precio'][perfil_id]
        
        print(f"\n📝 Editando perfil: {perfil.get('nombre')}")
        print("(Dejar vacío para mantener valor actual)")
        
        nuevo_nombre = input(f"\nNombre [{perfil.get('nombre')}]: ").strip()
        if nuevo_nombre:
            perfil['nombre'] = nuevo_nombre
        
        nueva_desc = input(f"Descripción [{perfil.get('descripcion')}]: ").strip()
        if nueva_desc:
            perfil['descripcion'] = nueva_desc
        
        self.registrar_cambio(f"Perfil editado: {perfil.get('nombre')}", perfil_id)
        print("\n✅ Perfil actualizado")
        input("\nPresionar Enter...")
    
    def activar_desactivar_perfil(self):
        """Activa o desactiva un perfil"""
        perfil_id = self._seleccionar_perfil()
        if not perfil_id:
            return
        
        perfil = self.config['perfiles_precio'][perfil_id]
        perfil['activo'] = not perfil.get('activo', False)
        
        estado = "activado" if perfil['activo'] else "desactivado"
        self.registrar_cambio(f"Perfil {estado}", perfil_id)
        
        print(f"\n✅ Perfil {estado}")
        input("\nPresionar Enter...")
    
    def ver_historial(self):
        """Muestra el historial de cambios"""
        print("\n" + "=" * 80)
        print("📜 HISTORIAL DE CAMBIOS")
        print("=" * 80)
        
        historial = self.config.get('historial_cambios', [])
        
        if not historial:
            print("\n⚠️  No hay cambios registrados")
        else:
            for i, cambio in enumerate(reversed(historial[-20:]), 1):
                print(f"\n{i}. {cambio.get('fecha', 'Sin fecha')}")
                print(f"   Usuario: {cambio.get('usuario', 'N/A')}")
                print(f"   Cambio: {cambio.get('cambio', 'Sin descripción')}")
                if 'perfil_modificado' in cambio:
                    print(f"   Perfil: {cambio['perfil_modificado']}")
        
        input("\n\nPresionar Enter para volver...")


def main():
    """Ejecuta el gestor de configuración"""
    gestor = GestorConfiguracionPrecios()
    gestor.menu_principal()


if __name__ == "__main__":
    main()
