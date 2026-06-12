#!/usr/bin/env python3
import requests

ACCESS_TOKEN = "APP_USR-1230705344766467-030219-80cae3acb054199b4ca1cc434e285bea-3239677654"

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
