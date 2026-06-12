#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VERSIÓN DEBUG EXTREMO - Captura todo para diagnóstico
"""

import json
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
import os

# Configuración básica
SCRIPT_DIR = Path(__file__).parent
CONFIG_DIR = SCRIPT_DIR.parent / "config"
LOGS_DIR = SCRIPT_DIR.parent / "logs"

# Crear directorio de logs si no existe
LOGS_DIR.mkdir(exist_ok=True)

print("=" * 80)
print("🔍 DIAGNÓSTICO DROPPERS - MODO DEBUG EXTREMO")
print("=" * 80)

# Cargar credenciales
print("\n1️⃣ Cargando credenciales...")
env_file = CONFIG_DIR / '.env'
print(f"   Archivo .env: {env_file}")
print(f"   ¿Existe? {env_file.exists()}")

load_dotenv(env_file)
user = os.getenv('DROPPERS_USER')
password = os.getenv('DROPPERS_PASS')

print(f"   Usuario: {user[:20] if user else 'NO ENCONTRADO'}...")
print(f"   Password: {'***' if password else 'NO ENCONTRADA'}")

if not user or not password:
    print("\n❌ ERROR: Credenciales no encontradas en .env")
    exit(1)

# Crear sesión
print("\n2️⃣ Creando sesión HTTP...")
session = requests.Session()
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'es-ES,es;q=0.9',
})
print("   ✅ Sesión creada")

# LOGIN
print("\n3️⃣ Realizando login...")
URL_LOGIN = "https://droppers.com.ar/customer/account/login/"
print(f"   URL: {URL_LOGIN}")

try:
    # Obtener página de login
    print("   Obteniendo página de login...")
    response = session.get(URL_LOGIN)
    print(f"   Status: {response.status_code}")
    
    # Guardar HTML de login
    login_html_file = LOGS_DIR / "debug_login_page.html"
    with open(login_html_file, 'w', encoding='utf-8') as f:
        f.write(response.text)
    print(f"   📄 HTML guardado: {login_html_file}")
    
    # Buscar form_key
    soup = BeautifulSoup(response.text, 'html.parser')
    form_key_input = soup.find('input', {'name': 'form_key'})
    form_key = form_key_input['value'] if form_key_input else None
    print(f"   form_key: {form_key[:20] if form_key else 'NO ENCONTRADO'}...")
    
    # Preparar datos de login
    login_data = {
        'login[username]': user,
        'login[password]': password,
        'send': ''
    }
    if form_key:
        login_data['form_key'] = form_key
    
    print("   Enviando credenciales...")
    response = session.post(URL_LOGIN, data=login_data, allow_redirects=True)
    print(f"   Status: {response.status_code}")
    print(f"   URL final: {response.url}")
    
    # Guardar respuesta de login
    login_response_file = LOGS_DIR / "debug_login_response.html"
    with open(login_response_file, 'w', encoding='utf-8') as f:
        f.write(response.text)
    print(f"   📄 Respuesta guardada: {login_response_file}")
    
    # Verificar login
    if 'customer/account' in response.url or 'Mi cuenta' in response.text or 'My Account' in response.text:
        print("   ✅ Login EXITOSO")
        login_exitoso = True
    else:
        print("   ❌ Login FALLIDO")
        print(f"   Busca 'error' o 'incorrect' en: {login_response_file}")
        login_exitoso = False
        
except Exception as e:
    print(f"   ❌ ERROR en login: {e}")
    import traceback
    traceback.print_exc()
    login_exitoso = False

if not login_exitoso:
    print("\n❌ No se pudo hacer login. Revisa los archivos HTML guardados.")
    exit(1)

# ACCEDER A INFORMES
print("\n4️⃣ Accediendo a página de informes...")
URL_INFORMES = "https://droppers.com.ar/alerts/customer/index/"
print(f"   URL: {URL_INFORMES}")

try:
    print("   Solicitando página...")
    response = session.get(URL_INFORMES, allow_redirects=True)
    print(f"   Status: {response.status_code}")
    print(f"   URL final: {response.url}")
    print(f"   Content-Length: {len(response.text)} bytes")
    
    # Guardar SIEMPRE el HTML
    informes_html_file = LOGS_DIR / "debug_informes_page.html"
    with open(informes_html_file, 'w', encoding='utf-8') as f:
        f.write(response.text)
    print(f"   📄 HTML guardado: {informes_html_file}")
    
    # Guardar headers
    headers_file = LOGS_DIR / "debug_response_headers.txt"
    with open(headers_file, 'w', encoding='utf-8') as f:
        f.write(f"Status Code: {response.status_code}\n")
        f.write(f"URL: {response.url}\n\n")
        f.write("Headers:\n")
        for key, value in response.headers.items():
            f.write(f"{key}: {value}\n")
    print(f"   📄 Headers guardados: {headers_file}")
    
    if response.status_code == 403:
        print("\n❌ ERROR 403: Acceso Denegado")
        print(f"\n🔍 DIAGNÓSTICO:")
        print(f"   1. Abre este archivo en tu navegador:")
        print(f"      {informes_html_file}")
        print(f"   2. Busca mensajes de error o 'acceso denegado'")
        print(f"   3. O envíame el archivo para analizarlo")
        
    elif response.status_code == 200:
        print("   ✅ Página cargada exitosamente")
        
        # Buscar tablas
        soup = BeautifulSoup(response.text, 'html.parser')
        tablas = soup.find_all('table')
        print(f"   📊 Tablas encontradas: {len(tablas)}")
        
        # Buscar encabezados con "stock" o "precio"
        encabezados_stock = soup.find_all(string=lambda text: text and 'stock' in text.lower())
        encabezados_precio = soup.find_all(string=lambda text: text and 'precio' in text.lower())
        
        print(f"   🏷️  Menciones de 'stock': {len(encabezados_stock)}")
        print(f"   🏷️  Menciones de 'precio': {len(encabezados_precio)}")
        
        if len(tablas) > 0:
            print("\n   📋 Estructura de tablas:")
            for i, tabla in enumerate(tablas, 1):
                filas = tabla.find_all('tr')
                print(f"      Tabla {i}: {len(filas)} filas")
        else:
            print("   ⚠️  NO se encontraron tablas")
            print(f"   Revisa manualmente: {informes_html_file}")
    else:
        print(f"   ⚠️  Status inesperado: {response.status_code}")
        
except Exception as e:
    print(f"   ❌ ERROR accediendo a informes: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 80)
print("🎯 RESUMEN DE ARCHIVOS GENERADOS:")
print("=" * 80)
print(f"1. {LOGS_DIR / 'debug_login_page.html'}")
print(f"2. {LOGS_DIR / 'debug_login_response.html'}")
print(f"3. {LOGS_DIR / 'debug_informes_page.html'}")
print(f"4. {LOGS_DIR / 'debug_response_headers.txt'}")
print("\n💡 Abre el archivo #3 en tu navegador para ver qué muestra Droppers")
print("   O envíamelo para que lo analice")
print("=" * 80)
