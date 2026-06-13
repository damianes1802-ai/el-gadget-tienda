#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Crea un usuario de prueba de MercadoPago (comprador) para probar el flujo
de checkout completo sin usar dinero real.

Usa el Access Token de prueba configurado en config/.env (MP_ACCESS_TOKEN_TEST).
"""
import sys
from pathlib import Path

import requests

sys.path.append(str(Path(__file__).parent))
from utils.config import Config

env = Config.cargar_env()
ACCESS_TOKEN = env.get('MP_ACCESS_TOKEN_TEST', '')

if not ACCESS_TOKEN:
    raise SystemExit("Falta MP_ACCESS_TOKEN_TEST en config/.env")

response = requests.post(
    "https://api.mercadopago.com/users/test",
    headers={
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json"
    },
    json={"site_id": "MLA"}
)

data = response.json()
print(f"Status: {response.status_code}")
print(f"Respuesta: {data}")

if response.status_code == 201:
    print("\n✅ Usuario de prueba creado:")
    print(f"   Email:      {data.get('email')}")
    print(f"   Password:   {data.get('password')}")
    print(f"   Nickname:   {data.get('nickname')}")
