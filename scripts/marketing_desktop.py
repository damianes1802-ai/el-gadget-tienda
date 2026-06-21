#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MARKETING EL GADGET — consola de métricas + generador de contenido

Ventana nativa (pywebview) que carga marketing_app/index.html y expone una API
Python (clase Api) vía window.pywebview.api.*. Consume los endpoints admin de
Render para métricas y usa Claude API para generar contenido de Instagram.
"""

import json
import random
import re
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

import anthropic
import requests
import webview

sys.path.append(str(Path(__file__).parent))
from utils.config import Config

API_URL = "https://el-gadget-tienda.onrender.com"
BASE_DIR = Path(__file__).parent.parent
MARKETING_CONFIG_FILE = BASE_DIR / "marketing_app" / "config.json"
CONTENIDOS_DB = BASE_DIR / "marketing_app" / "data" / "contenidos.db"
CLOUDINARY_BASE = "https://res.cloudinary.com/deq2ofluf/image/upload"

# ══════════════════════════════════════════════════════════════════════
# SISTEMA DE SELECCIÓN INTELIGENTE: Persona × Dolor × Ángulo × Layout
# ══════════════════════════════════════════════════════════════════════

PERSONAS = {
    "maria": {
        "nombre": "María", "peso": 35,
        "descripcion": "Mamá urbana 28-42, CABA/GBA, 1-2 hijos, NSE medio-alto",
        "tono": "Cálido, de mamá a mamá. Como una amiga que le cuenta un dato útil.",
        "dolores": [
            {"id": "M1", "cat": "financiero", "texto": "Con la inflación no me alcanza, necesito plata extra sin dejar a los chicos", "trigger": "fin de mes, supermercado", "contenido": "Cálculo real: 3 amigas compran = $X para vos"},
            {"id": "M2", "cat": "emocional", "texto": "Mi casa es un caos y me siento abrumada", "trigger": "llegar a casa después del trabajo", "contenido": "Antes/después con producto + en 10 minutos"},
            {"id": "M3", "cat": "social", "texto": "Ya recomiendo cosas gratis en el grupo de mamás", "trigger": "cuando alguien pregunta dónde compraste", "contenido": "Convertí tus recomendaciones en ingresos"},
            {"id": "M4", "cat": "social", "texto": "No quiero parecer que les vendo a mis amigas", "trigger": "miedo al rechazo", "contenido": "No es vender, es compartir un descuento"},
            {"id": "M5", "cat": "practico", "texto": "Quiero algo flexible que pueda hacer desde casa", "trigger": "falta de tiempo", "contenido": "Sin horarios, sin jefe, desde el celular"},
        ],
        "angulos": [
            {"id": "MA1", "texto": "Tu grupo de mamás es tu mejor negocio", "tipo": "identificacion", "hook_ej": "Ya recomendás todo gratis. ¿Y si cobraras?", "layouts": ["L03", "L04", "R01"]},
            {"id": "MA2", "texto": "Transformación del hogar", "tipo": "aspiracional", "hook_ej": "De caos a revista en 10 minutos", "layouts": ["L02", "L07"]},
            {"id": "MA3", "texto": "Calculá cuánto ganarías", "tipo": "racional", "hook_ej": "3 amigas × $50.000 = $10.500 para vos", "layouts": ["L03", "L01", "R01"]},
            {"id": "MA4", "texto": "Sin ser vendedora", "tipo": "objecion", "hook_ej": "No vendés nada. Compartís un descuento.", "layouts": ["L06", "L04"]},
            {"id": "MA5", "texto": "Mamá multitarea", "tipo": "empatia", "hook_ej": "Mientras los chicos duermen, vos ganás", "layouts": ["L04", "L09"]},
        ],
        "palabras_conectan": ["sin salir de casa", "desde el celular", "mientras los chicos duermen", "tus amigas", "el grupo de mamás", "tu familia", "ahorro", "llegar a fin de mes", "ingreso extra", "sin invertir", "gratis", "fácil"],
        "palabras_prohibidas": ["negocio", "vender", "emprender", "inversión", "multinivel", "red de contactos", "oportunidad única"],
        "hashtags": ["#MamasArgentinas", "#MamaEmprendedora", "#OrganizacionDelHogar", "#VidaDeMama", "#HogarOrganizado", "#IngresoExtra", "#GanarPlataDesdeCasa", "#MamasQueEmprenden", "#ElGadget", "#Argentina"],
    },
    "lucas": {
        "nombre": "Lucas", "peso": 25,
        "descripcion": "Joven urbano 18-34, nativo digital, estudiante o joven profesional",
        "tono": "Directo, sin vueltas. Como un amigo que te cuenta algo que funciona. Nada de gurú.",
        "dolores": [
            {"id": "L1", "cat": "emocional", "texto": "Estoy cansado de laburar para otro y ganar poco", "trigger": "lunes a la mañana", "contenido": "Un ingreso que no depende de tu jefe"},
            {"id": "L2", "cat": "social", "texto": "Mis amigos ganan plata en redes y yo no arranco", "trigger": "ver stories de amigos", "contenido": "El programa recién arranca — entrá ahora"},
            {"id": "L3", "cat": "financiero", "texto": "No tengo plata para invertir en nada", "trigger": "querer emprender sin capital", "contenido": "Registrarte es gratis. En serio."},
            {"id": "L4", "cat": "practico", "texto": "Quiero resultados rápidos, no promesas", "trigger": "ver oportunidades que nunca funcionan", "contenido": "Cálculo con números reales"},
            {"id": "L5", "cat": "practico", "texto": "No sé qué decir al compartir", "trigger": "vergüenza de parecer vendedor", "contenido": "Templates listos, solo pegás y enviás"},
        ],
        "angulos": [
            {"id": "LA1", "texto": "Side hustle real", "tipo": "aspiracional", "hook_ej": "Un side hustle que no te roba el día", "layouts": ["L03", "L09", "R01"]},
            {"id": "LA2", "texto": "Hacé la cuenta", "tipo": "racional", "hook_ej": "1 link = $7.400 de comisión. La matemática es simple.", "layouts": ["L03", "L01", "R01"]},
            {"id": "LA3", "texto": "Escéptico convertido", "tipo": "historia", "hook_ej": "También pensé que era humo. Acá van los números.", "layouts": ["L04", "L06"]},
            {"id": "LA4", "texto": "Antes de que se llene", "tipo": "urgencia", "hook_ej": "El programa recién arranca. Los primeros tienen ventaja.", "layouts": ["L04", "L03"]},
            {"id": "LA5", "texto": "Tu celular ya es tu herramienta", "tipo": "facilidad", "hook_ej": "WhatsApp + tu código = comisiones", "layouts": ["L09", "L01"]},
        ],
        "palabras_conectan": ["side hustle", "ingreso extra", "sin jefe", "rápido", "fácil", "desde el celu", "la matemática es simple", "hacé la cuenta", "sin humo", "real", "transparente"],
        "palabras_prohibidas": ["oportunidad de la vida", "millonario", "libertad financiera", "jefe de tu propio destino"],
        "hashtags": ["#SideHustleArgentina", "#IngresoExtra", "#GanarPlataDesdeCasa", "#EmprenderSinInversion", "#DineroExtra", "#TrabajarDesdeCasa", "#JovenEmprendedor", "#ElGadget", "#Argentina"],
    },
    "ana": {
        "nombre": "Ana", "peso": 15,
        "descripcion": "Profesional 35-50, NSE medio-alto, valora calidad y transparencia",
        "tono": "Adulto, profesional, sin exageraciones. Datos concretos. Respeto a su inteligencia.",
        "dolores": [
            {"id": "A1", "cat": "social", "texto": "Si recomiendo algo malo, quedo yo como la responsable", "trigger": "miedo a quedar mal", "contenido": "Solo recomendá lo que te gusta. Sin obligaciones."},
            {"id": "A2", "cat": "practico", "texto": "No tengo tiempo para otro compromiso", "trigger": "agenda llena", "contenido": "Compartís un link y listo. Sin horarios."},
            {"id": "A3", "cat": "racional", "texto": "Quiero saber exactamente cuánto gano y cuándo cobro", "trigger": "desconfianza de programas", "contenido": "Panel en tiempo real con números claros"},
            {"id": "A4", "cat": "financiero", "texto": "Un ingreso pasivo real, no otro trabajo", "trigger": "fin de mes cómodo pero podría ser mejor", "contenido": "Cobrás por recomendaciones que ya hacés"},
        ],
        "angulos": [
            {"id": "AA1", "texto": "Recomendación genuina", "tipo": "confianza", "hook_ej": "Si te gusta un producto, ¿por qué no cobrar por recomendarlo?", "layouts": ["L04", "L01"]},
            {"id": "AA2", "texto": "Transparencia total", "tipo": "racional", "hook_ej": "Panel en tiempo real. Ves cada venta, cada comisión.", "layouts": ["L01", "L10"]},
            {"id": "AA3", "texto": "Ingreso pasivo real", "tipo": "aspiracional", "hook_ej": "No es otro trabajo. Es cobrar por lo que ya hacés.", "layouts": ["L06", "L03", "R01"]},
            {"id": "AA4", "texto": "Calidad garantizada", "tipo": "confianza", "hook_ej": "10 días de devolución. 6 meses de garantía. MercadoPago.", "layouts": ["L10", "L07"]},
        ],
        "palabras_conectan": ["transparente", "claro", "sin letra chica", "recomendación genuina", "lo que ya hacés", "ingreso pasivo", "sin compromiso", "calidad", "garantía", "confianza"],
        "palabras_prohibidas": ["ganá plata fácil", "sin hacer nada", "oportunidad única", "no te lo pierdas"],
        "hashtags": ["#ProfesionalesArgentina", "#IngresoPasivo", "#HomeOfficeArgentina", "#Productividad", "#TransparenciaTotal", "#NegociosReales", "#EmprenderConCabeza", "#ElGadget", "#Argentina"],
    },
    "sofi": {
        "nombre": "Sofi", "peso": 15,
        "descripcion": "Creadora de contenido 18-45, tiene audiencia, busca monetizar auténticamente",
        "tono": "Natural, como una creadora hablando de una oportunidad real. Sin parecer publicidad.",
        "dolores": [
            {"id": "S1", "cat": "financiero", "texto": "Los programas de afiliados pagan poco y tarde", "trigger": "ver comisiones míseras", "contenido": "7-15% de comisión. Cobro el día 5."},
            {"id": "S2", "cat": "social", "texto": "No quiero perder credibilidad recomendando algo malo", "trigger": "miedo a la audiencia", "contenido": "Productos reales, garantía de 6 meses"},
            {"id": "S3", "cat": "practico", "texto": "Necesito tracking transparente para saber cuánto generé", "trigger": "no saber si funciona", "contenido": "Panel en tiempo real con cada venta"},
            {"id": "S4", "cat": "practico", "texto": "Quiero productos que mi audiencia realmente compre", "trigger": "recomendar y que nadie compre", "contenido": "Productos con descuento = mayor conversión"},
        ],
        "angulos": [
            {"id": "SA1", "texto": "Monetizá tu audiencia", "tipo": "aspiracional", "hook_ej": "Tu audiencia ya te pide recomendaciones. Cobrá por ellas.", "layouts": ["L03", "L07"]},
            {"id": "SA2", "texto": "Comisiones que valen la pena", "tipo": "racional", "hook_ej": "7-15% > lo que pagan la mayoría de programas", "layouts": ["L08", "L03", "R01"]},
            {"id": "SA3", "texto": "Sin contratos", "tipo": "libertad", "hook_ej": "Sin obligaciones de publicación. Tu contenido, tu ritmo.", "layouts": ["L04", "L10"]},
            {"id": "SA4", "texto": "Productos instagrameables", "tipo": "visual", "hook_ej": "Productos que tu audiencia quiere tener", "layouts": ["L07", "L02"]},
        ],
        "palabras_conectan": ["tu audiencia", "monetizar", "tracking", "comisiones transparentes", "sin contratos", "tu contenido", "productos reales", "tu ritmo"],
        "palabras_prohibidas": ["influencer barato", "obligación", "publicar X veces", "contrato"],
        "hashtags": ["#LifestyleArgentina", "#UGCArgentina", "#CreadorasDeContenido", "#MonetizaTuAudiencia", "#AfiliadosInstagram", "#DecoracionHogar", "#AestheticHome", "#ElGadget", "#Argentina"],
    },
    "martin": {
        "nombre": "Martín", "peso": 10,
        "descripcion": "Mayorista/revendedor 30-50, busca margen y variedad",
        "tono": "Directo, con números, orientado al negocio. Mostrá márgenes concretos.",
        "dolores": [
            {"id": "MT1", "cat": "financiero", "texto": "Necesito margen real, no descuentos que no dejan ganancia", "trigger": "calcular márgenes", "contenido": "25% OFF = margen del 40%+ en reventa"},
            {"id": "MT2", "cat": "practico", "texto": "Quiero variedad de productos para ofrecer", "trigger": "catálogo limitado", "contenido": "300+ productos en 10 categorías"},
            {"id": "MT3", "cat": "practico", "texto": "Me importa que el envío sea confiable", "trigger": "reclamos de clientes", "contenido": "Envío a todo el país con tracking"},
        ],
        "angulos": [
            {"id": "MTA1", "texto": "Números claros", "tipo": "racional", "hook_ej": "25% OFF = margen del 40%+ en reventa", "layouts": ["L03", "L08", "R01"]},
            {"id": "MTA2", "texto": "Catálogo amplio", "tipo": "variedad", "hook_ej": "300+ productos en 10 categorías", "layouts": ["L01", "L10"]},
            {"id": "MTA3", "texto": "Confianza logística", "tipo": "confianza", "hook_ej": "Envío a todo el país con tracking", "layouts": ["L10", "L07"]},
        ],
        "palabras_conectan": ["margen", "reventa", "mayorista", "catálogo", "factura", "envío seguro", "precio por mayor"],
        "palabras_prohibidas": ["emprendedor", "influencer", "redes sociales", "viral"],
        "hashtags": ["#MayoristasArgentina", "#Revendedores", "#NegociosArgentina", "#PrecioDeMayor", "#MargenDeGanancia", "#TiendaOnlineArgentina", "#RevenderOnline", "#ElGadget", "#Argentina"],
    },
}

# ── Layouts: mapeo ID → info para prompt y selección ──
LAYOUTS_INFO = {
    "L01": {"nombre": "Bullets numerados", "pilares": ["educativo"], "campos": ["hook", "titulo", "puntos"]},
    "L02": {"nombre": "Antes/después", "pilares": ["educativo", "producto"], "campos": ["hook", "antes_texto", "despues_texto"]},
    "L03": {"nombre": "Número grande + desglose", "pilares": ["motivacional"], "campos": ["hook", "numero_grande", "subtexto", "bullets"]},
    "L04": {"nombre": "Historia + CTA", "pilares": ["motivacional"], "campos": ["hook", "historia_texto"]},
    "L05": {"nombre": "Pregunta + opciones", "pilares": ["engagement"], "campos": ["hook", "pregunta", "opciones"]},
    "L06": {"nombre": "Mito vs realidad", "pilares": ["educativo", "engagement"], "campos": ["hook", "mitos", "realidades"]},
    "L07": {"nombre": "Producto lifestyle", "pilares": ["producto"], "campos": ["hook"]},
    "L08": {"nombre": "Comparativa precios", "pilares": ["producto"], "campos": ["hook", "precio_competencia_label", "precio_propio_label"]},
    "L09": {"nombre": "Paso a paso", "pilares": ["educativo"], "campos": ["hook", "pasos"]},
    "L10": {"nombre": "Checklist", "pilares": ["educativo"], "campos": ["hook", "items_check"]},
    "R01": {"nombre": "Reel 7 slides", "pilares": ["motivacional", "educativo", "producto"], "campos": ["hook", "dolor", "solucion", "numero_grande", "subtexto_proof", "beneficio", "dato_extra"]},
}

# ── Schemas JSON por layout (lo que Claude debe devolver) ──
# cta_type: "guardar" | "compartir" | "comentar" | "link" (para analytics futuro)
_CTA_FIELDS = '"cta":"CTA baja friccion (guardar/compartir/comentar REFERIDO)","cta_type":"guardar|compartir|comentar|link","cta_bar":"texto barra inferior max 50 chars"'
LAYOUT_SCHEMAS = {
    "L01": '{"hook":"frase corta OBLIGATORIO","titulo":"max 6 palabras","puntos":["max 40 chars",...max 5],"caption":"hook+valor+cta","caption_b":"variante B","hashtags":"8-12",'+_CTA_FIELDS+'}',
    "L02": '{"hook":"OBLIGATORIO","antes_texto":"max 60 chars","despues_texto":"max 60 chars","caption":"hook+valor+cta","caption_b":"variante B","hashtags":"8-12",'+_CTA_FIELDS+'}',
    "L03": '{"hook":"OBLIGATORIO","numero_grande":"$X.XXX","subtexto":"max 50 chars","bullets":["max 35 chars",...max 4],"caption":"hook+valor+cta","caption_b":"variante B","hashtags":"8-12",'+_CTA_FIELDS+'}',
    "L04": '{"hook":"OBLIGATORIO","historia_texto":"2-3 oraciones max 200 chars","caption":"hook+valor+cta","caption_b":"variante B","hashtags":"8-12",'+_CTA_FIELDS+'}',
    "L05": '{"hook":"OBLIGATORIO","pregunta":"max 50 chars","opciones":["max 30 chars",...max 4],"caption":"hook+valor+cta","caption_b":"variante B","hashtags":"8-12",'+_CTA_FIELDS+'}',
    "L06": '{"hook":"OBLIGATORIO","mitos":["max 40 chars",...max 3],"realidades":["max 40 chars",...max 3],"caption":"hook+valor+cta","caption_b":"variante B","hashtags":"8-12",'+_CTA_FIELDS+'}',
    "L07": '{"hook":"problema que resuelve OBLIGATORIO","caption":"hook+valor+cta con angulo referido","caption_b":"variante B","hashtags":"8-12",'+_CTA_FIELDS+'}',
    "L08": '{"hook":"OBLIGATORIO","precio_competencia_label":"Titulo corto: $X.XXX (max 20 chars el precio)","precio_propio_label":"Titulo corto: $X.XXX (max 20 chars el precio)","caption":"hook+valor+cta","caption_b":"variante B","hashtags":"8-12",'+_CTA_FIELDS+'}',
    "L09": '{"hook":"OBLIGATORIO","pasos":["max 40 chars",...max 4],"caption":"hook+valor+cta","caption_b":"variante B","hashtags":"8-12",'+_CTA_FIELDS+'}',
    "L10": '{"hook":"OBLIGATORIO","items_check":["max 40 chars",...max 6],"caption":"hook+valor+cta","caption_b":"variante B","hashtags":"8-12",'+_CTA_FIELDS+'}',
    "R01": '{"hook":"pregunta de dolor max 50 chars OBLIGATORIO","dolor":"ampliar el dolor 1 oracion max 80 chars","solucion":"como se resuelve 1-2 oraciones max 100 chars","numero_grande":"$X.XXX numero impactante","subtexto_proof":"contexto del numero max 60 chars","beneficio":"frase emocional corta max 60 chars","dato_extra":"prueba social adicional max 60 chars","cta_text":"CTA max 40 chars con signos","voiceover":"texto complementario para voz en off 3-4 oraciones NO repetir lo que dice el texto visual sino agregar contexto persuasivo","caption":"caption para publicar el reel en IG","hashtags":"5-8",'+_CTA_FIELDS+'}',
}

# ── Mapeo legacy para backward compat del modal individual ──
FORMATOS_LEGACY = {
    "ED-01": {"layout_id": "L01", "tipo": "reel"}, "ED-02": {"layout_id": "L01", "tipo": "carrusel"},
    "ED-03": {"layout_id": "L09", "tipo": "reel"}, "ED-04": {"layout_id": "L10", "tipo": "carrusel"},
    "MO-01": {"layout_id": "L04", "tipo": "reel"}, "MO-02": {"layout_id": "L03", "tipo": "post"},
    "MO-03": {"layout_id": "L03", "tipo": "reel"}, "MO-04": {"layout_id": "L04", "tipo": "story"},
    "EN-01": {"layout_id": "L05", "tipo": "story"}, "EN-02": {"layout_id": "L06", "tipo": "post"},
    "EN-03": {"layout_id": "L05", "tipo": "reel"},
    "PR-01": {"layout_id": "L07", "tipo": "reel"}, "PR-02": {"layout_id": "L07", "tipo": "post"},
    "PR-03": {"layout_id": "L07", "tipo": "reel"}, "PR-04": {"layout_id": "L08", "tipo": "post"},
    "PR-05": {"layout_id": "L08", "tipo": "carrusel"},
}

# ── Pilares y formatos de contenido Instagram (LEGACY — usado por modal individual) ──
# Distribución controlada por PERSONAS[].peso, no por pesos fijos de pilar
PILARES = {
    "educativo":    {"peso": 28, "desc": "Contenido de valor que enseña cómo funciona el programa de referidos y cómo ganar dinero"},
    "motivacional": {"peso": 15, "desc": "Historias de éxito, cálculos de ganancias, inspiración para empezar"},
    "engagement":   {"peso": 28, "desc": "Preguntas, encuestas, interacción con la comunidad"},
    "producto":     {"peso": 29, "desc": "Producto destacado con precio, descuento referido y ángulo de venta"},
}

FORMATOS = {
    # EDUCATIVO (35%) — enseñar sobre el programa
    "ED-01": {"tipo": "reel",     "pilar": "educativo",    "persona": "lucas", "desc": "Tutorial: 'Así funciona el programa de referidos de El Gadget — paso a paso en 30 segundos'"},
    "ED-02": {"tipo": "carrusel", "pilar": "educativo",    "persona": "maria", "desc": "Guía visual: '5 formas de compartir tu código y ganar comisiones' (slide por forma: WA, IG Stories, grupos, link directo, redes)"},
    "ED-03": {"tipo": "reel",     "pilar": "educativo",    "persona": "lucas", "desc": "Tips de venta: '3 errores que comete todo referido nuevo (y cómo evitarlos)'"},
    "ED-04": {"tipo": "carrusel", "pilar": "educativo",    "persona": "ana",   "desc": "FAQ del programa: responder las 5 preguntas más comunes sobre cómo cobrar, cuánto se gana, cómo subir de tier"},

    # MOTIVACIONAL (30%) — inspirar a registrarse
    "MO-01": {"tipo": "reel",     "pilar": "motivacional", "persona": "lucas", "desc": "Storytime: 'Así gano plata extra sin inversión — mi experiencia como referido de El Gadget'"},
    "MO-02": {"tipo": "post",     "pilar": "motivacional", "persona": "maria", "desc": "Cálculo real: 'Si compartís con 10 amigos y 3 compran, ganás $X por mes. Sin invertir un peso.'"},
    "MO-03": {"tipo": "reel",     "pilar": "motivacional", "persona": "lucas", "desc": "Comparación: 'El Gadget vs otros programas de afiliados en Argentina — por qué este conviene más'"},
    "MO-04": {"tipo": "story",    "pilar": "motivacional", "persona": "sofi",  "desc": "Behind the scenes: mostrar el panel de comisiones con números reales (difuminados) y reaccionar"},

    # ENGAGEMENT (20%) — interacción y comunidad
    "EN-01": {"tipo": "story",    "pilar": "engagement",   "persona": "maria", "desc": "Encuesta/Poll: '¿Qué harías con $30.000 extra por mes?' con opciones divertidas"},
    "EN-02": {"tipo": "post",     "pilar": "engagement",   "persona": "lucas", "desc": "Pregunta abierta: '¿Cuál es el producto de El Gadget que más recomendarías? Contanos en comentarios'"},
    "EN-03": {"tipo": "reel",     "pilar": "engagement",   "persona": "maria", "desc": "Challenge: 'Compartí este reel con alguien que necesita un ingreso extra — taggealo'"},

    # PRODUCTO (29%) — showcase con ángulo referido (2 de cada 7 posts)
    "PR-01": {"tipo": "reel",     "pilar": "producto",     "persona": "maria", "desc": "Producto en acción: problema → solución. Mostrá el antes/después. CTA: 'Compartilo con tu código y ganá comisión'"},
    "PR-02": {"tipo": "post",     "pilar": "producto",     "persona": "sofi",  "desc": "Foto producto destacada: nombre, precio público tachado, precio con descuento referido, CTA 'link en bio'"},
    "PR-03": {"tipo": "reel",     "pilar": "producto",     "persona": "lucas", "desc": "Producto viral: 'Este producto está volando — con código referido hasta 20% OFF'. Mostrar el producto y el ahorro"},
    "PR-04": {"tipo": "post",     "pilar": "producto",     "persona": "ana",   "desc": "Review/reseña: opinión honesta del producto con datos (material, medidas, utilidad real). Enfoque profesional"},
    "PR-05": {"tipo": "carrusel", "pilar": "producto",     "persona": "maria", "desc": "Comparativa de valor: precio El Gadget vs precio en otros lados. Mostrar el ahorro + descuento referido adicional"},
}

PERSONAS_DESC = {
    "maria": """PERSONA: María — mamá urbana 25-40 años, CABA/GBA.
PAIN POINTS que debés tocar (elegí 1 por post, NO todos):
- "El sueldo no alcanza y los precios suben cada mes"
- "Quiero algo flexible que pueda hacer desde casa, con los chicos"
- "Mis amigas me piden recomendaciones de productos todo el tiempo"
- "No tengo capital para arrancar un emprendimiento"
- "Ya recomiendo cosas gratis en el grupo de mamás, ¿por qué no cobrar?"
TONO: cálido, de mamá a mamá. Hablale como si fueras una amiga que le cuenta un dato útil, no como vendedor.
ÁNGULOS que funcionan con María: ahorro familiar, practicidad, hijos, organización del hogar, grupos de WhatsApp, ganar sin salir de casa.""",

    "lucas": """PERSONA: Lucas — joven 18-34 años, urbano, nativo digital.
PAIN POINTS que debés tocar (elegí 1 por post, NO todos):
- "Estoy cansado de laburar para otro y ganar poco"
- "Quiero un side hustle que no me consuma todo el día"
- "Mis amigos ganan plata en redes y yo no arranco nunca"
- "No tengo plata para invertir en un negocio"
- "Quiero ganar por mi cuenta, no depender de un sueldo fijo"
TONO: directo, sin vueltas, como un amigo que te cuenta algo que funciona. Nada de "gurú" ni promesas exageradas.
ÁNGULOS que funcionan con Lucas: libertad, independencia, estatus ("mirá cuánto generé"), competencia amistosa, tendencias, resultados rápidos.""",

    "ana": """PERSONA: Ana — profesional 35-50 años, buen poder adquisitivo.
PAIN POINTS que debés tocar (elegí 1 por post, NO todos):
- "Si un producto me gusta, lo recomiendo naturalmente a colegas y familia"
- "No necesito otro trabajo, pero un ingreso extra no viene mal"
- "Solo recomiendo cosas que yo misma probé y me gustaron"
- "No quiero quemar mi reputación profesional con algo trucho"
- "Valoro la transparencia y saber exactamente cuánto gano"
TONO: adulto, profesional, sin exageraciones. Datos concretos, sin emojis excesivos. Hablale con respeto a su inteligencia.
ÁNGULOS que funcionan con Ana: calidad del producto, confianza, transparencia del programa, números concretos, recomendación genuina.""",

    "sofi": """PERSONA: Sofi — creadora de contenido 18-45 años, tiene audiencia.
PAIN POINTS que debés tocar (elegí 1 por post, NO todos):
- "Busco marcas que paguen bien y sean transparentes con el tracking"
- "No quiero recomendar algo malo y perder credibilidad"
- "Necesito productos instagrameables que mi audiencia quiera comprar"
- "Quiero flexibilidad, no contratos ni obligaciones de publicación"
- "Los programas de afiliados suelen pagar poco y tarde"
TONO: natural, como una creadora hablando de una oportunidad real. Sin parecer publicidad.
ÁNGULOS que funcionan con Sofi: monetización de audiencia, productos reales para mostrar, comisiones competitivas, tracking transparente.""",

    "martin": """PERSONA: Martín — revendedor/mayorista 30-50 años.
PAIN POINTS que debés tocar (elegí 1 por post, NO todos):
- "Necesito margen real, no descuentos que no dejan ganancia"
- "Quiero variedad de productos para ofrecer a mis clientes"
- "Me importa que el envío sea confiable y llegue bien"
- "Necesito factura para mi negocio"
TONO: directo, con números, orientado al negocio. Mostrá márgenes concretos.
ÁNGULOS que funcionan con Martín: 25% OFF, márgenes de reventa, variedad de catálogo, envío confiable.""",
}

SYSTEM_PROMPT_NEW = """Sos el community manager de El Gadget, tienda online argentina. Publicás desde la CUENTA OFICIAL en Instagram.

OBJETIVO: que cada post genere REGISTROS de referidos, no solo likes. Todo el contenido debe empujar hacia la acción.
Programa: registro gratis, comisión 7-15%, descuento comprador 10-20%, cobro día 5. URL: elgadget.com.ar/referidos

PRINCIPIOS DE CONVERSIÓN (aplicá siempre):
1. HOOK en <3 segundos: dolor específico, pregunta fuerte, o dato impactante. OBLIGATORIO.
2. VALOR en el cuerpo: transformación real, cálculo concreto, prueba social, o storytelling breve.
3. CTA de BAJA FRICCIÓN al final. Tipos de CTA (elegí uno por post):
   - "Guardá este post para cuando lo necesites" (genera saves, señal #1 del algoritmo)
   - "Mandáselo a alguien que necesita plata extra" (genera DM shares, señal #2)
   - "Comentá REFERIDO y te mandamos el link" (genera comentarios + DMs)
   - "Link en bio → elgadget.com.ar/referidos" (directo pero menor conversión)
4. PRUEBA SOCIAL siempre que sea posible: números reales del programa, cálculos verificables.
5. NO PAREZCAS VENDEDOR: enfocate en "compartir descuento" y "recomendar lo que funciona".

REGLAS DE TONO:
- Español argentino (vos/voseo). Cercano, directo, sin exagerar.
- NUNCA menciones "Droppers". Precios siempre reales.
- NUNCA nombres a la persona target (no digas "María", "Lucas"). Son perfiles internos.
- Máximo 2 emojis por caption. No empieces con emoji.
- Storytelling desde cuenta oficial: escenarios relatables, datos reales, NO historias inventadas.
- Cada post = UN SOLO dolor + UN SOLO ángulo. No listes todos los beneficios.
- Variá estructura y arranque. No repitas patrones.
- PREGUNTAS SIEMPRE con ¿? (ej: "¿Ya recomendás productos gratis?"). NUNCA sin signos de apertura.

ESTRUCTURA DEL CAPTION (seguí este orden):
1. Hook (primera línea, detiene el scroll)
2. Desarrollo (2-4 oraciones con valor real)
3. CTA (última línea, baja fricción)
4. Hashtags al final (5-8 hashtags, mezcla: 1-2 broad + 3-4 nicho + 1-2 branded + 1 geográfico)

El prompt del usuario indica el schema JSON exacto. Respondé SOLO con ese JSON, sin markdown."""

# Legacy SYSTEM_PROMPT (mantener para backward compat con modal individual)
SYSTEM_PROMPT = """Sos el community manager de El Gadget, una tienda online argentina. Publicás desde la CUENTA OFICIAL de El Gadget en Instagram.

OBJETIVO: conseguir referidos para el programa de comisiones + mostrar productos.

DATOS DEL PROGRAMA:
- Registro gratis, sin inversión, sin stock, sin envíos
- Comisión: 7% (base), 11% (5+ ventas/mes), 15% (15+ ventas/mes)
- Descuento para quien compra: 10-20% según monto
- Cobro el día 5 de cada mes · URL: elgadget.com.ar/referidos

REGLAS DE STORYTELLING (MUY IMPORTANTE):
- Publicás desde la cuenta de EL GADGET, NO desde una persona. No digas "yo gané" ni "me pasó".
- Usá escenarios relatables: "Imaginá que...", "¿Te pasó que...?", "Hay quienes ya..."
- Usá datos reales del programa (te los paso en el prompt) para dar credibilidad
- Mostrá situaciones cotidianas: el grupo de mamás, la charla con amigos, el scroll en el celu
- NUNCA inventes testimonios ni reviews de personas específicas
- No hagas promesas de ingresos específicos salvo que uses cálculos verificables
- Cada post debe tener UN SOLO ángulo/pain point, no listar todos los beneficios

REGLAS DE HOOKS (OBLIGATORIO):
- SIEMPRE generá un hook. Nunca lo dejes vacío.
- El hook son las primeras palabras que detienen el scroll. Debe generar curiosidad o identificación.
- Buenos hooks: preguntas que la persona se hace, datos sorprendentes, situaciones que identifican
- MAL: "Te cuento cómo funciona" (aburrido), "¿Sabías que...?" (sobreusado)
- BIEN: "El grupo de mamás puede ser tu mejor fuente de ingresos", "3 compras de tus amigos = $10.000 en tu bolsillo"

REGLAS DE VARIEDAD:
- NO repitas la misma estructura. Variá entre: pregunta, afirmación impactante, dato numérico, situación cotidiana
- NO uses siempre "Sin inversión, sin stock, sin envíos" como lista. Integralo naturalmente en la historia
- Variá los CTAs: "link en bio", "registrate gratis", "conocé el programa", "empezá hoy"
- NO empieces todos los captions igual. Variá el arranque.

REGLAS DE TONO:
- Español argentino (vos/voseo): "mirá", "registrate", "compartí"
- Cercano y directo, sin exagerar. NO uses lenguaje de "gurú" ni promesas infladas
- NUNCA menciones "Droppers" ni ningún proveedor
- Precios siempre reales y actuales
- Emojis: máximo 2-3 por caption, nunca al inicio de cada línea
- NO hagas listas con emoji al principio de cada punto (❌ "📱 Registrate / 💰 Ganá / 📦 Sin stock")

HASHTAGS (8-12 por post, mezcla populares + nicho):
PROGRAMA: #referidoselgadget #ganardinero #ingresosextra #comisiones #dineroextra #negocioonline
ARGENTINA: #emprendedoresargentinos #tiendaonlineargentina #compraonline #ofertasargentina
HOGAR: #organizaciondelhogar #decoracion #hogarorganizado #ordenencasa #ideasparaelhogar
MODA: #modaargentina #accesorios #tendencias #moda2026
MAMÁS: #mamasargentinas #mamaemprendedora #vidademama #cosasdemama
TECH: #gadgets #tecnologia #productosvirales #tiktokfinds

Respondé SOLAMENTE con un objeto JSON válido (sin texto adicional, sin markdown).
Los campos varían según el pilar de contenido indicado en el prompt del usuario:

TODOS los pilares DEBEN incluir "hook" (NUNCA vacío). El hook es la frase corta que detiene el scroll.

PILAR EDUCATIVO:
{"hook": "frase que detiene el scroll (OBLIGATORIO)", "titulo": "título corto (máx 6 palabras)", "puntos": ["punto 1 (MÁXIMO 40 chars)", "punto 2", ...max 5], "caption": "texto para IG", "caption_b": "variante B", "hashtags": "8-12 hashtags", "cta": "CTA final", "cta_bar": "texto corto para barra inferior"}
Puntos MÁXIMO 40 caracteres. Ej: "Mandalo por WhatsApp", NO "WhatsApp directo: mandá tu código a una amiga"

PILAR MOTIVACIONAL:
{"hook": "frase que detiene el scroll (OBLIGATORIO)", "numero_grande": "$X.XXX (número impactante)", "subtexto": "qué representa (máx 50 chars)", "bullets": ["beneficio (máx 35 chars)", ...max 4], "caption": "texto para IG", "caption_b": "variante B", "hashtags": "8-12 hashtags", "cta": "CTA final", "cta_bar": "texto para barra inferior"}

PILAR ENGAGEMENT:
{"hook": "frase que detiene el scroll (OBLIGATORIO)", "pregunta": "pregunta (máx 50 chars)", "opciones": ["opción (máx 30 chars)", ...max 4], "caption": "texto para IG", "caption_b": "variante B", "hashtags": "8-12 hashtags", "cta": "CTA final", "cta_bar": "texto para barra inferior"}

PILAR PRODUCTO:
{"hook": "frase sobre el PROBLEMA que resuelve el producto (OBLIGATORIO)", "caption": "texto para IG con ángulo de referido", "caption_b": "variante B", "hashtags": "8-12 hashtags", "cta": "CTA final", "cta_bar": "texto para barra inferior"}"""


class Api:
    def __init__(self):
        env = Config.cargar_env()
        self.admin_password = env.get('ADMIN_PASSWORD', 'admin2024')
        self.anthropic_key = env.get('ANTHROPIC_API_KEY', '')
        self._init_contenidos_db()

    def _init_contenidos_db(self):
        CONTENIDOS_DB.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(CONTENIDOS_DB))
        conn.execute("""
            CREATE TABLE IF NOT EXISTS contenidos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tipo TEXT NOT NULL,
                formato TEXT NOT NULL,
                persona TEXT NOT NULL,
                producto_sku TEXT,
                producto_nombre TEXT,
                producto_precio REAL,
                producto_imagen TEXT,
                caption TEXT NOT NULL,
                caption_variante_b TEXT,
                hashtags TEXT,
                hook TEXT,
                cta TEXT,
                estado TEXT DEFAULT 'borrador',
                media_url TEXT,
                score_esperado TEXT,
                score_real TEXT,
                notas_owner TEXT,
                creado_at TEXT DEFAULT (datetime('now')),
                aprobado_at TEXT,
                publicado_at TEXT
            )
        """)
        conn.commit()
        # Migration: columnas nuevas para selección inteligente
        for col, tipo in [("dolor_id", "TEXT"), ("angulo_id", "TEXT"), ("layout_id", "TEXT"), ("contexto_fingerprint", "TEXT")]:
            try:
                conn.execute(f"ALTER TABLE contenidos ADD COLUMN {col} {tipo}")
            except sqlite3.OperationalError:
                pass
        conn.commit()
        # Migration: columnas para reels y métricas de IG
        for col, tipo in [
            ("media_type", "TEXT DEFAULT 'image'"),
            ("reel_duration", "REAL"),
            ("voiceover_url", "TEXT"),
            ("ig_post_id", "TEXT"),
            ("ig_permalink", "TEXT"),
            ("views", "INTEGER DEFAULT 0"),
            ("saves", "INTEGER DEFAULT 0"),
            ("shares", "INTEGER DEFAULT 0"),
            ("comments_count", "INTEGER DEFAULT 0"),
            ("reach", "INTEGER DEFAULT 0"),
        ]:
            try:
                conn.execute(f"ALTER TABLE contenidos ADD COLUMN {col} {tipo}")
            except sqlite3.OperationalError:
                pass
        conn.commit()
        conn.close()

    def _contenidos_db(self):
        conn = sqlite3.connect(str(CONTENIDOS_DB))
        conn.row_factory = sqlite3.Row
        return conn

    def _get_historial(self, limit=15):
        """Obtiene historial reciente para evitar repeticiones."""
        try:
            conn = self._contenidos_db()
            rows = conn.execute(
                "SELECT persona, dolor_id, angulo_id, layout_id, producto_sku FROM contenidos ORDER BY creado_at DESC LIMIT ?",
                (limit,)
            ).fetchall()
            conn.close()
            return [dict(r) for r in rows]
        except Exception:
            return []

    def _seleccionar_contexto(self, historial=None, forzar_pilar=None):
        """Selección inteligente: persona → dolor → ángulo → layout → pilar"""
        if historial is None:
            historial = self._get_historial(20)

        personas_recientes = [h.get("persona") for h in historial[:6] if h.get("persona")]
        dolores_usados = {h.get("dolor_id") for h in historial if h.get("dolor_id")}
        angulos_usados = {h.get("angulo_id") for h in historial[:10] if h.get("angulo_id")}

        # 1. Persona ponderada con penalización gradual
        pool = []
        for key, p in PERSONAS.items():
            peso = p["peso"]
            penalizacion = personas_recientes.count(key)
            peso = max(1, peso - penalizacion * 4)
            pool.extend([key] * peso)
        persona_key = random.choice(pool)
        persona = PERSONAS[persona_key]

        # 2. Dolor: evitar usados, fallback a menos recientes
        dolores_disp = [d for d in persona["dolores"] if d["id"] not in dolores_usados]
        if not dolores_disp:
            dolores_disp = persona["dolores"]
        dolor = random.choice(dolores_disp)

        # 3. Ángulo: evitar usados recientemente
        angulos_disp = [a for a in persona["angulos"] if a["id"] not in angulos_usados]
        if not angulos_disp:
            angulos_disp = persona["angulos"]
        angulo = random.choice(angulos_disp)

        # 4. Layout: de los compatibles del ángulo, priorizando alta conversión
        HIGH_CONVERSION = {"L02", "L03", "L06", "L08"}
        layouts_posibles = angulo.get("layouts", [])
        if forzar_pilar and layouts_posibles:
            layouts_posibles = [lid for lid in layouts_posibles if forzar_pilar in LAYOUTS_INFO.get(lid, {}).get("pilares", [])]
        if not layouts_posibles:
            layouts_posibles = angulo.get("layouts", list(LAYOUTS_INFO.keys())[:3])
        # Dar 2x peso a layouts de alta conversión
        pool_layouts = []
        for lid in layouts_posibles:
            pool_layouts.append(lid)
            if lid in HIGH_CONVERSION:
                pool_layouts.append(lid)
        layout_id = random.choice(pool_layouts)
        layout_info = LAYOUTS_INFO.get(layout_id, {})

        # 5. Pilar y tipo derivados
        pilar = layout_info.get("pilares", ["educativo"])[0]
        tipo = "post"
        if layout_id in ("L01", "L06", "L08", "L09", "L10"):
            tipo = random.choice(["carrusel", "post"])
        elif layout_id in ("L02", "L04", "L07"):
            tipo = random.choice(["reel", "post"])

        formato = f"{layout_id}-{persona_key[:3].upper()}"
        fingerprint = f"{persona_key}|{dolor['id']}|{angulo['id']}|{layout_id}"

        print(f"[MKT] {persona['nombre']:8s} {dolor['id']:4s} ({dolor['cat']:10s}) {angulo['id']:4s} {layout_id} {pilar}")

        return {
            "persona_key": persona_key, "persona": persona,
            "dolor": dolor, "angulo": angulo,
            "layout_id": layout_id, "layout_info": layout_info,
            "pilar": pilar, "tipo": tipo,
            "formato": formato, "fingerprint": fingerprint,
        }

    def _headers(self):
        return {"X-Admin-Password": self.admin_password}

    def _get(self, path, params=None):
        try:
            resp = requests.get(f"{API_URL}{path}", params=params, headers=self._headers(), timeout=60)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            return {"error": str(e)}

    # ── Data fetching (métricas) ──

    def get_estadisticas(self):
        return self._get("/api/estadisticas")

    def get_all_ordenes(self):
        return self._get("/api/ordenes", params={"limit": 200})

    def get_referidos(self):
        return self._get("/api/admin/referidos")

    def get_clientes(self):
        return self._get("/api/clientes")

    def get_usuarios(self):
        return self._get("/api/admin/usuarios")

    def get_descuentos(self):
        return self._get("/api/admin/descuentos")

    def get_productos(self):
        return self._get("/api/productos", params={"limit": 1000, "incluir_agotados": "true"})

    # ── Config local ──

    def get_marketing_config(self):
        try:
            if MARKETING_CONFIG_FILE.exists():
                return json.loads(MARKETING_CONFIG_FILE.read_text(encoding="utf-8"))
            return {}
        except Exception as e:
            return {"error": str(e)}

    def guardar_marketing_config(self, config):
        try:
            MARKETING_CONFIG_FILE.write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")
            return {"ok": True}
        except Exception as e:
            return {"error": str(e)}

    def check_connection(self):
        import time
        t0 = time.time()
        result = self._get("/api/estadisticas")
        latency = round((time.time() - t0) * 1000)
        if "error" in result:
            return {"ok": False, "error": result["error"], "latency_ms": latency}
        return {"ok": True, "latency_ms": latency}

    # ── Content Generator (Claude API) ──

    def _parse_json_response(self, text):
        cleaned = re.sub(r'^```(?:json)?\s*', '', text.strip())
        cleaned = re.sub(r'\s*```$', '', cleaned)
        return json.loads(cleaned)

    def generar_contenido(self, producto, formato=None, persona=None, contexto=None):
        try:
            if not self.anthropic_key:
                return {"error": "ANTHROPIC_API_KEY no configurada"}

            nombre = producto.get("nombre", "Producto")
            precio = producto.get("precio_venta", 0)
            desc = producto.get("descripcion", "")[:200]
            cat = producto.get("categoria", "")

            # ── PATH NUEVO: selección inteligente via contexto ──
            if contexto:
                ctx = contexto
                pilar = ctx["pilar"]
                layout_id = ctx["layout_id"]
                dolor = ctx["dolor"]
                angulo = ctx["angulo"]
                persona_data = ctx["persona"]
                persona = ctx["persona_key"]
                formato = ctx["formato"]

                # Anti-duplicados por fingerprint
                try:
                    conn_dup = self._contenidos_db()
                    dup = conn_dup.execute(
                        "SELECT id FROM contenidos WHERE contexto_fingerprint = ? AND producto_sku = ? AND estado = 'aprobado'",
                        (ctx.get("fingerprint", ""), producto.get("sku", ""))
                    ).fetchone()
                    conn_dup.close()
                    if dup:
                        return {"error": f"Duplicado: {ctx.get('fingerprint', '')}"}
                except Exception:
                    pass

                # Stats reales
                stats_line = ""
                try:
                    refs = self.get_referidos()
                    if isinstance(refs, list) and refs:
                        activos = len([r for r in refs if r.get("activo")])
                        total_com = sum(r.get("comision_total", 0) for r in refs)
                        stats_line = f"\nDATOS REALES: {activos} referidos activos, ${total_com:,.0f} comisiones generadas."
                except Exception:
                    pass

                # Few-shot
                few_shot = ""
                try:
                    conn_fs = self._contenidos_db()
                    aprobados = conn_fs.execute("SELECT caption FROM contenidos WHERE estado='aprobado' ORDER BY aprobado_at DESC LIMIT 2").fetchall()
                    conn_fs.close()
                    if aprobados:
                        few_shot = "\nEJEMPLOS DE TONO (NO copies):\n" + "\n".join(f"- \"{r['caption'][:150]}\"" for r in aprobados)
                except Exception:
                    pass

                schema = LAYOUT_SCHEMAS.get(layout_id, LAYOUT_SCHEMAS["L01"])

                user_prompt = f"""Genera contenido para Instagram. Cuenta OFICIAL de El Gadget.

LAYOUT: {layout_id} — {ctx['layout_info'].get('nombre', '')}
PILAR: {pilar.upper()}

PERSONA: {persona_data['nombre']} — {persona_data.get('descripcion', '')}
TONO: {persona_data.get('tono', '')}

DOLOR ESPECÍFICO (basa TODO el post en este dolor):
"{dolor['texto']}"
Categoría: {dolor['cat']} | Trigger: {dolor['trigger']}
Contenido recomendado: {dolor['contenido']}

ÁNGULO DE CONVERSIÓN:
"{angulo['texto']}" (tipo: {angulo['tipo']})
Hook ejemplo (inspirate, NO copies): "{angulo['hook_ej']}"

PALABRAS QUE CONECTAN (USÁ ESTAS): {', '.join(persona_data.get('palabras_conectan', [])[:8])}
PALABRAS PROHIBIDAS (NUNCA USES): {', '.join(persona_data.get('palabras_prohibidas', [])[:5])}
HASHTAGS PARA ESTA PERSONA (elegí 5-8, mezclá con 1-2 branded #ElGadget #ReferidosElGadget): {' '.join(persona_data.get('hashtags', []))}
{stats_line}{few_shot}

Producto (contexto, usalo especialmente si el layout es L07/L08):
- {nombre} · ${precio:,.0f} · {cat}
- Con referido 10% OFF: ${round(precio*0.90):,.0f} · 20% OFF: ${round(precio*0.80):,.0f}

CHECKLIST (verificá internamente antes de responder):
- Hook fuerte en <3 palabras? Si no, reescribilo.
- Toca el dolor específico? No otro.
- Tiene prueba social o cálculo real? Si no, agregalo.
- CTA claro y de baja fricción? (guardar/compartir/comentar, NO "comprá ya")
- Invita a guardar o compartir por DM? (señales #1 y #2 del algoritmo)
- Usa palabras que conectan? Evita las prohibidas?
- Caption sigue estructura Hook → Valor → CTA?
- TODAS las preguntas tienen ¿? (NUNCA "Ya recomendás..." sin ¿?)
- Hashtags: 5-8, incluyen branded + nicho de esta persona?

RESPONDÉ SOLO con este JSON exacto (sin markdown):
{schema}"""

                sys_prompt = SYSTEM_PROMPT_NEW

            # ── PATH LEGACY: formato string del modal individual ──
            else:
                if not formato:
                    return {"error": "Se requiere formato o contexto"}
                fmt = FORMATOS.get(formato)
                if not fmt:
                    legacy = FORMATOS_LEGACY.get(formato)
                    if legacy:
                        layout_id = legacy["layout_id"]
                        pilar = LAYOUTS_INFO.get(layout_id, {}).get("pilares", ["educativo"])[0]
                        fmt = {"tipo": legacy["tipo"], "pilar": pilar, "persona": persona or "maria", "desc": formato}
                    else:
                        return {"error": f"Formato {formato} no existe"}

                pilar = fmt.get("pilar", "producto")
                layout_id = None
                persona = persona or fmt.get("persona", "maria")

                user_prompt = f"""Genera contenido para Instagram. Cuenta OFICIAL de El Gadget.
PILAR: {pilar.upper()} | Formato: {formato}
Producto: {nombre} · ${precio:,.0f} · {cat} · {desc}
Hook OBLIGATORIO. Máximo 2 emojis. Respondé SOLO JSON."""

                sys_prompt = SYSTEM_PROMPT

            client = anthropic.Anthropic(api_key=self.anthropic_key)
            response = client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=1024,
                system=[{"type": "text", "text": sys_prompt, "cache_control": {"type": "ephemeral"}}],
                messages=[{"role": "user", "content": user_prompt}]
            )

            data = self._parse_json_response(response.content[0].text)

            conn = self._contenidos_db()
            cursor = conn.cursor()

            from image_composer import compose_image, compose_carousel
            import time as _time
            ts = int(_time.time())
            try:
                tipo_actual = contexto["tipo"] if contexto else (fmt.get("tipo") if fmt else "post")
                if tipo_actual == "carrusel" and data.get("puntos"):
                    paths = compose_carousel(
                        persona=persona, pilar=pilar,
                        hook=data.get("hook", ""),
                        titulo=data.get("titulo", ""),
                        puntos=data.get("puntos"),
                        cta_bar=data.get("cta_bar", ""),
                        output_prefix=f"{formato}_{producto.get('sku', '')}_{ts}",
                        producto_nombre=nombre, producto_precio=precio,
                        producto_imagen_url=producto.get("imagen_principal", ""),
                    )
                    branded_url = json.dumps(paths)
                else:
                    branded_url = compose_image(
                        producto_nombre=nombre,
                        producto_precio=precio,
                        producto_imagen_url=producto.get("imagen_principal", ""),
                        persona=persona, pilar=pilar, formato=formato,
                        layout_id=layout_id,
                        hook=data.get("hook", ""),
                        output_filename=f"{formato}_{producto.get('sku', '')}_{ts}.jpg",
                        titulo=data.get("titulo", ""),
                        puntos=data.get("puntos"),
                        numero_grande=data.get("numero_grande", ""),
                        subtexto=data.get("subtexto", ""),
                        bullets=data.get("bullets"),
                        pregunta=data.get("pregunta", ""),
                        opciones=data.get("opciones"),
                        cta_bar=data.get("cta_bar", ""),
                        emoji=data.get("emoji", ""),
                        antes_texto=data.get("antes_texto", ""),
                        despues_texto=data.get("despues_texto", ""),
                        historia_texto=data.get("historia_texto", ""),
                        mitos=data.get("mitos"),
                        realidades=data.get("realidades"),
                        precio_competencia_label=data.get("precio_competencia_label", ""),
                        precio_propio_label=data.get("precio_propio_label", ""),
                        pasos=data.get("pasos"),
                        items_check=data.get("items_check"),
                    )
            except Exception as img_err:
                print(f"[MKT] ERROR imagen: {img_err}")
                branded_url = producto.get("imagen_principal", "")

            # Extraer IDs del contexto si existe
            dolor_id = contexto["dolor"]["id"] if contexto else None
            angulo_id = contexto["angulo"]["id"] if contexto else None
            ctx_layout_id = layout_id
            ctx_fingerprint = contexto.get("fingerprint") if contexto else None
            tipo_post = contexto["tipo"] if contexto else (fmt.get("tipo") if fmt else "post")

            cursor.execute("""
                INSERT INTO contenidos (tipo, formato, persona, producto_sku, producto_nombre,
                    producto_precio, producto_imagen, caption, caption_variante_b,
                    hashtags, hook, cta, media_url, score_esperado,
                    dolor_id, angulo_id, layout_id, contexto_fingerprint)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                tipo_post, formato, persona,
                producto.get("sku", ""),
                nombre, precio,
                producto.get("imagen_principal", ""),
                data.get("caption", ""),
                data.get("caption_b", ""),
                data.get("hashtags", ""),
                data.get("hook", ""),
                data.get("cta", ""),
                branded_url,
                json.dumps({"reach_min": 500, "reach_max": 2000, "eng_min": 3, "eng_max": 5}),
                dolor_id, angulo_id, ctx_layout_id, ctx_fingerprint,
            ))
            conn.commit()
            contenido_id = cursor.lastrowid

            cursor.execute("SELECT * FROM contenidos WHERE id = ?", (contenido_id,))
            result = dict(cursor.fetchone())
            conn.close()
            return result

        except json.JSONDecodeError as e:
            return {"error": f"Error parseando respuesta de Claude: {e}"}
        except Exception as e:
            return {"error": str(e)}

    def generar_reel(self, producto, contexto):
        """Genera un Reel usando Claude API + reel_composer."""
        try:
            if not self.anthropic_key:
                return {"error": "ANTHROPIC_API_KEY no configurada"}

            nombre = producto.get("nombre", "Producto")
            precio = producto.get("precio_venta", 0)
            cat = producto.get("categoria", "")

            ctx = contexto
            layout_id = ctx["layout_id"]  # Should be R01
            dolor = ctx["dolor"]
            angulo = ctx["angulo"]
            persona_data = ctx["persona"]
            persona = ctx["persona_key"]
            formato = ctx["formato"]

            # Anti-duplicados por fingerprint
            try:
                conn_dup = self._contenidos_db()
                dup = conn_dup.execute(
                    "SELECT id FROM contenidos WHERE contexto_fingerprint = ? AND producto_sku = ? AND estado = 'aprobado'",
                    (ctx.get("fingerprint", ""), producto.get("sku", ""))
                ).fetchone()
                conn_dup.close()
                if dup:
                    return {"error": f"Duplicado: {ctx.get('fingerprint', '')}"}
            except Exception:
                pass

            # Stats reales
            stats_line = ""
            try:
                refs = self.get_referidos()
                if isinstance(refs, list) and refs:
                    activos = len([r for r in refs if r.get("activo")])
                    total_com = sum(r.get("comision_total", 0) for r in refs)
                    stats_line = f"\nDATOS REALES: {activos} referidos activos, ${total_com:,.0f} comisiones generadas."
            except Exception:
                pass

            # Few-shot
            few_shot = ""
            try:
                conn_fs = self._contenidos_db()
                aprobados = conn_fs.execute("SELECT caption FROM contenidos WHERE estado='aprobado' ORDER BY aprobado_at DESC LIMIT 2").fetchall()
                conn_fs.close()
                if aprobados:
                    few_shot = "\nEJEMPLOS DE TONO (NO copies):\n" + "\n".join(f"- \"{r['caption'][:150]}\"" for r in aprobados)
            except Exception:
                pass

            schema = LAYOUT_SCHEMAS["R01"]

            user_prompt = f"""Genera contenido para un REEL de Instagram (video vertical 9:16, 20-25 segundos). Cuenta OFICIAL de El Gadget.

LAYOUT: R01 — Reel 7 slides
PILAR: {ctx['layout_info'].get('pilares', ['motivacional'])[0].upper()}

PERSONA: {persona_data['nombre']} — {persona_data.get('descripcion', '')}
TONO: {persona_data.get('tono', '')}

DOLOR ESPECÍFICO (basa TODO el reel en este dolor):
"{dolor['texto']}"
Categoría: {dolor['cat']} | Trigger: {dolor['trigger']}
Contenido recomendado: {dolor['contenido']}

ÁNGULO DE CONVERSIÓN:
"{angulo['texto']}" (tipo: {angulo['tipo']})
Hook ejemplo (inspirate, NO copies): "{angulo['hook_ej']}"

PALABRAS QUE CONECTAN (USÁ ESTAS): {', '.join(persona_data.get('palabras_conectan', [])[:8])}
PALABRAS PROHIBIDAS (NUNCA USES): {', '.join(persona_data.get('palabras_prohibidas', [])[:5])}
HASHTAGS PARA ESTA PERSONA (elegí 5-8, mezclá con 1-2 branded #ElGadget #ReferidosElGadget): {' '.join(persona_data.get('hashtags', []))}
{stats_line}{few_shot}

Producto (contexto):
- {nombre} · ${precio:,.0f} · {cat}
- Con referido 10% OFF: ${round(precio*0.90):,.0f} · 20% OFF: ${round(precio*0.80):,.0f}

ESTRUCTURA DEL REEL (7 slides, 20-25 seg total):
1. Hook (2-3s) — pregunta de dolor que frena el scroll
2. Dolor (2s) — ampliar el dolor, que se identifiquen
3. Solución (3s) — cómo se resuelve
4. Prueba (3.5s) — número grande impactante con contexto
5. Beneficio (2.5s) — frase emocional
6. Social proof (2s) — dato extra de confianza
7. CTA (4s) — llamado a la acción claro

El voiceover debe COMPLEMENTAR el texto visual, NO repetirlo. Agregar contexto persuasivo adicional.

CHECKLIST:
- Hook fuerte que frene el scroll?
- Toca el dolor específico?
- Tiene prueba social o cálculo real?
- CTA claro y de baja fricción?
- Voiceover complementa sin repetir?
- TODAS las preguntas tienen ¿?
- Hashtags: 5-8, incluyen branded + nicho?

RESPONDÉ SOLO con este JSON exacto (sin markdown):
{schema}"""

            client = anthropic.Anthropic(api_key=self.anthropic_key)
            response = client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=1024,
                system=[{"type": "text", "text": SYSTEM_PROMPT_NEW, "cache_control": {"type": "ephemeral"}}],
                messages=[{"role": "user", "content": user_prompt}]
            )

            data = self._parse_json_response(response.content[0].text)

            # Compose the reel video
            from reel_composer import compose_reel
            import time as _time
            ts = int(_time.time())

            reel_path = compose_reel(
                persona=persona,
                hook=data.get("hook", ""),
                dolor=data.get("dolor", ""),
                solucion=data.get("solucion", ""),
                numero_grande=data.get("numero_grande", ""),
                subtexto_proof=data.get("subtexto_proof", ""),
                beneficio=data.get("beneficio", ""),
                dato_extra=data.get("dato_extra", ""),
                cta_text=data.get("cta_text", ""),
                voiceover_text=data.get("voiceover", ""),
                output_filename=f"R01_{producto.get('sku', '')}_{ts}.mp4",
            )

            # Save to DB
            dolor_id = ctx["dolor"]["id"]
            angulo_id = ctx["angulo"]["id"]
            ctx_fingerprint = ctx.get("fingerprint")

            conn = self._contenidos_db()
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO contenidos (tipo, formato, persona, producto_sku, producto_nombre,
                    producto_precio, producto_imagen, caption, caption_variante_b,
                    hashtags, hook, cta, media_url, score_esperado,
                    dolor_id, angulo_id, layout_id, contexto_fingerprint,
                    media_type, voiceover_url)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                "reel", formato, persona,
                producto.get("sku", ""),
                nombre, precio,
                producto.get("imagen_principal", ""),
                data.get("caption", ""),
                None,
                data.get("hashtags", ""),
                data.get("hook", ""),
                data.get("cta", ""),
                reel_path,
                json.dumps({"reach_min": 1000, "reach_max": 5000, "eng_min": 4, "eng_max": 8}),
                dolor_id, angulo_id, layout_id, ctx_fingerprint,
                "reel",
                None,  # voiceover_url — populated if TTS is added later
            ))
            conn.commit()
            contenido_id = cursor.lastrowid

            cursor.execute("SELECT * FROM contenidos WHERE id = ?", (contenido_id,))
            result = dict(cursor.fetchone())
            conn.close()
            return result

        except json.JSONDecodeError as e:
            return {"error": f"Error parseando respuesta de Claude: {e}"}
        except Exception as e:
            return {"error": str(e)}

    def generar_lote_reels(self, cantidad=3):
        """Genera un lote de Reels usando selección inteligente con layout R01."""
        try:
            productos_raw = self.get_productos()
            if isinstance(productos_raw, dict) and "error" in productos_raw:
                return {"error": productos_raw["error"]}

            productos = [p for p in productos_raw if p.get("stock", 0) > 0 and p.get("precio_venta", 0) > 0]
            random.shuffle(productos)
            prods_top = []
            cat_count = {}
            for p in productos:
                cat = p.get("categoria", "General")
                if cat_count.get(cat, 0) >= 2:
                    continue
                prods_top.append(p)
                cat_count[cat] = cat_count.get(cat, 0) + 1
                if len(prods_top) >= cantidad * 2:
                    break

            historial = self._get_historial(20)
            resultados = []
            errores = []
            fingerprints_lote = set()

            for i in range(cantidad):
                prod = prods_top[i % len(prods_top)] if prods_top else {}

                for intento in range(3):
                    try:
                        ctx = self._seleccionar_contexto(historial)

                        # Force layout to R01 for reels
                        ctx["layout_id"] = "R01"
                        ctx["layout_info"] = LAYOUTS_INFO["R01"]
                        ctx["tipo"] = "reel"
                        ctx["formato"] = f"R01-{ctx['persona_key'][:3].upper()}"
                        ctx["fingerprint"] = f"{ctx['persona_key']}|{ctx['dolor']['id']}|{ctx['angulo']['id']}|R01"

                        fp = f"{ctx.get('fingerprint', '')}|{prod.get('sku', '')}"
                        if fp in fingerprints_lote:
                            continue
                        result = self.generar_reel(prod, contexto=ctx)
                        if isinstance(result, dict) and "error" in result:
                            if intento == 2:
                                errores.append(f"R01: {result['error']}")
                        else:
                            resultados.append(result)
                            fingerprints_lote.add(fp)
                            historial.insert(0, {"persona": ctx["persona_key"], "dolor_id": ctx["dolor"]["id"], "angulo_id": ctx["angulo"]["id"], "layout_id": "R01"})
                            break
                    except Exception as e:
                        if intento == 2:
                            errores.append(f"R01: {e}")

            return {"ok": True, "generados": len(resultados), "contenidos": resultados, "errores": errores}

        except Exception as e:
            return {"error": str(e)}

    def generar_lote(self, cantidad=5):
        try:
            productos_raw = self.get_productos()
            if isinstance(productos_raw, dict) and "error" in productos_raw:
                return {"error": productos_raw["error"]}

            productos = [p for p in productos_raw if p.get("stock", 0) > 0 and p.get("precio_venta", 0) > 0]
            random.shuffle(productos)
            prods_top = []
            cat_count = {}
            for p in productos:
                cat = p.get("categoria", "General")
                if cat_count.get(cat, 0) >= 2:
                    continue
                prods_top.append(p)
                cat_count[cat] = cat_count.get(cat, 0) + 1
                if len(prods_top) >= cantidad * 2:
                    break

            # Selección inteligente — cada pieza usa _seleccionar_contexto
            historial = self._get_historial(20)
            resultados = []
            errores = []
            fingerprints_lote = set()

            for i in range(cantidad):
                prod = prods_top[i % len(prods_top)] if prods_top else {}

                for intento in range(3):
                    try:
                        ctx = self._seleccionar_contexto(historial)

                        # Evitar duplicados dentro del mismo lote
                        fp = f"{ctx.get('fingerprint', '')}|{prod.get('sku', '')}"
                        if fp in fingerprints_lote:
                            continue
                        result = self.generar_contenido(prod, contexto=ctx)
                        if isinstance(result, dict) and "error" in result:
                            if intento == 2:
                                errores.append(f"{ctx['layout_id']}: {result['error']}")
                        else:
                            resultados.append(result)
                            fingerprints_lote.add(fp)
                            historial.insert(0, {"persona": ctx["persona_key"], "dolor_id": ctx["dolor"]["id"], "angulo_id": ctx["angulo"]["id"], "layout_id": ctx["layout_id"]})
                            break
                    except Exception as e:
                        if intento == 2:
                            errores.append(f"{ctx.get('layout_id', '?')}: {e}")

            return {"ok": True, "generados": len(resultados), "contenidos": resultados, "errores": errores}

        except Exception as e:
            return {"error": str(e)}

    # ── CRUD contenidos ──

    def get_contenidos(self, estado=None):
        try:
            import base64
            conn = self._contenidos_db()
            if estado and estado != 'todos':
                rows = conn.execute("SELECT * FROM contenidos WHERE estado = ? ORDER BY creado_at DESC", (estado,)).fetchall()
            else:
                rows = conn.execute("SELECT * FROM contenidos ORDER BY creado_at DESC").fetchall()
            result = []
            for r in rows:
                d = dict(r)
                media = d.get("media_url", "")
                if media and media.startswith("["):
                    try:
                        paths = json.loads(media)
                        b64_list = []
                        for mp in paths:
                            p = Path(mp)
                            if p.exists():
                                b64_list.append(f"data:image/jpeg;base64,{base64.b64encode(p.read_bytes()).decode()}")
                        d["media_url"] = json.dumps(b64_list)
                        d["_is_carousel"] = True
                    except Exception:
                        d["media_url"] = ""
                elif media and media.endswith(".mp4"):
                    # Reels: keep path as-is (too large for base64)
                    d["_is_reel"] = True
                elif media and not media.startswith("http") and not media.startswith("data:"):
                    p = Path(media)
                    if p.exists():
                        b64 = base64.b64encode(p.read_bytes()).decode()
                        d["media_url"] = f"data:image/jpeg;base64,{b64}"
                    else:
                        d["media_url"] = ""
                result.append(d)
            conn.close()
            return result
        except Exception as e:
            return {"error": str(e)}

    def aprobar_contenido(self, contenido_id):
        try:
            conn = self._contenidos_db()
            conn.execute("UPDATE contenidos SET estado = 'aprobado', aprobado_at = datetime('now') WHERE id = ?", (contenido_id,))
            conn.commit()
            conn.close()
            return {"ok": True}
        except Exception as e:
            return {"error": str(e)}

    def rechazar_contenido(self, contenido_id):
        try:
            conn = self._contenidos_db()
            conn.execute("UPDATE contenidos SET estado = 'rechazado' WHERE id = ?", (contenido_id,))
            conn.commit()
            conn.close()
            return {"ok": True}
        except Exception as e:
            return {"error": str(e)}

    def editar_contenido(self, contenido_id, cambios):
        try:
            campos_ok = {'caption', 'caption_variante_b', 'hashtags', 'hook', 'cta', 'notas_owner'}
            sets = []
            vals = []
            for k, v in cambios.items():
                if k in campos_ok:
                    sets.append(f"{k} = ?")
                    vals.append(v)
            if not sets:
                return {"error": "Sin cambios válidos"}
            vals.append(contenido_id)
            conn = self._contenidos_db()
            conn.execute(f"UPDATE contenidos SET {', '.join(sets)} WHERE id = ?", vals)
            conn.commit()
            conn.close()
            return {"ok": True}
        except Exception as e:
            return {"error": str(e)}

    def eliminar_contenido(self, contenido_id):
        try:
            conn = self._contenidos_db()
            conn.execute("DELETE FROM contenidos WHERE id = ?", (contenido_id,))
            conn.commit()
            conn.close()
            return {"ok": True}
        except Exception as e:
            return {"error": str(e)}


def main():
    index_path = BASE_DIR / "marketing_app" / "index.html"
    icon_path = BASE_DIR / "marketing_app" / "assets" / "icon.ico"

    webview.create_window(
        "El Gadget — Marketing",
        str(index_path),
        js_api=Api(),
        width=1400,
        height=900,
        min_size=(1100, 700),
    )
    webview.start(icon=str(icon_path) if icon_path.exists() else None)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        log_dir = BASE_DIR / "logs"
        log_dir.mkdir(exist_ok=True)
        (log_dir / "marketing_desktop_error.log").write_text(
            f"{e.__class__.__name__}: {e}", encoding="utf-8"
        )
        import ctypes
        ctypes.windll.user32.MessageBoxW(0, f"Error al iniciar Marketing El Gadget:\n\n{e}", "Error", 0x10)
