# Buyer Personas Profundizados — Base del Sistema de Generación

> Este documento es la fuente de verdad para el sistema multiagente.
> Cada campo se inyecta como variable en los prompts de Claude.

---

## Dolores universales del público El Gadget (Argentina 2026)

| Categoría | Dolor | Intensidad | Aplica a |
|-----------|-------|-----------|----------|
| FINANCIERO | La inflación come el sueldo, no llego a fin de mes | ALTA | María, Lucas, Martín |
| FINANCIERO | No tengo capital para arrancar un negocio propio | ALTA | Lucas, María |
| FINANCIERO | Quiero un ingreso extra pero no quiero otro trabajo de 8hs | ALTA | Ana, María, Lucas |
| PRÁCTICO | Mi casa es chica y no entra nada más | MEDIA | María, Lucas, Sofi |
| PRÁCTICO | No tengo tiempo para ordenar, cocinar, organizar | ALTA | María, Ana |
| PRÁCTICO | Comprar online me da miedo (¿llega bien? ¿es confiable?) | MEDIA | María, Ana |
| EMOCIONAL | Me siento abrumada por el desorden y no sé por dónde empezar | ALTA | María |
| EMOCIONAL | Siento culpa de no tener la casa como "debería" | MEDIA | María, Sofi |
| EMOCIONAL | Estoy cansado de depender de un jefe/sueldo fijo | ALTA | Lucas |
| SOCIAL | Veo casas lindas en Instagram y la mía no se parece | MEDIA | María, Sofi |
| SOCIAL | Mis amigos ganan plata en redes y yo no arranco | ALTA | Lucas |
| SOCIAL | No quiero parecer vendedora con mis amigos | MEDIA | María, Ana |

---

## PERSONA 1: MARÍA (Mamá urbana 28-42)

### Perfil emocional
- Se siente responsable del hogar Y del ingreso familiar
- Culpa constante: "debería tener la casa más ordenada / ganar más / estar más presente"
- Busca validación: cuando una amiga le dice "qué lindo te quedó" siente que lo logró
- Su red social más fuerte: grupo de WhatsApp de mamás del colegio (10-30 personas)

### Dolores ordenados por intensidad
| # | Dolor | Categoría | Trigger | Contenido que lo resuelve |
|---|-------|-----------|---------|--------------------------|
| 1 | "Con la inflación no me alcanza, necesito plata extra sin dejar a los chicos" | Financiero | Fin de mes, supermercado | Cálculo real: "3 amigas compran = $X para vos" |
| 2 | "Mi casa es un caos y me siento abrumada" | Emocional | Llegar a casa después del trabajo | Antes/después con producto + "en 10 minutos" |
| 3 | "Ya recomiendo cosas gratis en el grupo de mamás" | Social | Cuando alguien pregunta "¿dónde compraste?" | "Convertí tus recomendaciones en ingresos" |
| 4 | "No quiero parecer que les vendo a mis amigas" | Social | Miedo al rechazo | "No es vender, es compartir un descuento" |
| 5 | "Quiero algo flexible que pueda hacer desde casa" | Práctico | Falta de tiempo | "Sin horarios, sin jefe, desde el celular" |

### Ángulos de conversión
| Ángulo | Tipo | Ejemplo de hook | Layout recomendado |
|--------|------|----------------|-------------------|
| "Tu grupo de mamás es tu mejor negocio" | Identificación | "Ya recomendás todo gratis. ¿Y si cobraras?" | Texto centrado + cálculo |
| "Transformación del hogar" | Aspiracional | "De caos a revista en 10 minutos" | Antes/después visual |
| "Calculá cuánto ganarías" | Racional | "3 amigas × $50.000 = $10.500 para vos" | Número grande + desglose |
| "Sin ser vendedora" | Objeción | "No vendés nada. Compartís un descuento." | Mito vs realidad |
| "Mamá multitarea" | Empatía | "Mientras los chicos duermen, vos ganás" | Historia + beneficios |

### Palabras que conectan con María
- "sin salir de casa", "desde el celular", "mientras los chicos duermen"
- "tus amigas", "el grupo de mamás", "tu familia"
- "ahorro", "llegar a fin de mes", "ingreso extra"
- "sin invertir", "gratis", "fácil"

### Palabras que la alejan
- "negocio", "vender", "emprender", "inversión"
- "multinivel", "red de contactos", "oportunidad única"
- Lenguaje de gurú, promesas infladas, emojis excesivos

---

## PERSONA 2: LUCAS (Joven urbano 18-34)

### Perfil emocional
- Frustrado con el sistema: "laburo 8hs y no me alcanza para nada"
- Le motiva el estatus pero no lo admite abiertamente
- Consume mucho contenido de "cómo ganar plata" pero no ejecuta
- Su barrera principal: escepticismo ("esto es humo como todo")

### Dolores ordenados por intensidad
| # | Dolor | Categoría | Trigger | Contenido que lo resuelve |
|---|-------|-----------|---------|--------------------------|
| 1 | "Estoy cansado de laburar para otro y ganar poco" | Emocional | Lunes a la mañana | "Un ingreso que no depende de tu jefe" |
| 2 | "Mis amigos ganan plata en redes y yo no arranco" | Social | Ver stories de amigos | "El programa recién arranca — entrá ahora" |
| 3 | "No tengo plata para invertir en nada" | Financiero | Querer emprender sin capital | "Registrarte es gratis. En serio." |
| 4 | "Quiero resultados rápidos, no promesas" | Práctico | Ver "oportunidades" que nunca funcionan | Cálculo con números reales |
| 5 | "No sé qué decir al compartir" | Práctico | Vergüenza de parecer vendedor | "Templates listos, solo pegás y enviás" |

### Ángulos de conversión
| Ángulo | Tipo | Ejemplo de hook | Layout recomendado |
|--------|------|----------------|-------------------|
| "Side hustle real" | Aspiracional | "Un side hustle que no te roba el día" | Número grande + pasos |
| "Hacé la cuenta" | Racional | "1 link = $7.400 de comisión. La matemática es simple." | Cálculo desglosado |
| "Escéptico convertido" | Historia | "También pensé que era humo. Acá van los números." | Storytelling + datos |
| "Antes de que se llene" | Urgencia | "El programa recién arranca. Los primeros tienen ventaja." | Urgencia + CTA |
| "Tu celular ya es tu herramienta" | Facilidad | "WhatsApp + tu código = comisiones" | Paso a paso minimalista |

### Palabras que conectan con Lucas
- "side hustle", "ingreso extra", "sin jefe"
- "rápido", "fácil", "desde el celu"
- "la matemática es simple", "hacé la cuenta"
- "sin humo", "real", "transparente"

### Palabras que lo alejan
- "oportunidad de la vida", "millonario", "libertad financiera"
- Promesas exageradas, lenguaje MLM
- Demasiado texto, posts aburridos

---

## PERSONA 3: ANA (Profesional 35-50)

### Perfil emocional
- Su reputación profesional es sagrada — no la arriesga por nada
- Solo recomienda lo que probó personalmente y le pareció excelente
- No necesita el dinero urgentemente, pero un extra siempre suma
- Valora la transparencia total: quiere ver números, tracking, reglas claras

### Dolores ordenados por intensidad
| # | Dolor | Categoría | Trigger | Contenido que lo resuelve |
|---|-------|-----------|---------|--------------------------|
| 1 | "Si recomiendo algo malo, quedo yo como la responsable" | Social | Miedo a quedar mal | "Solo recomendá lo que te gusta. Sin obligaciones." |
| 2 | "No tengo tiempo para otro compromiso" | Práctico | Agenda llena | "Compartís un link y listo. Sin horarios." |
| 3 | "Quiero saber exactamente cuánto gano y cuándo cobro" | Racional | Desconfianza de "programas" | Mostrar el panel real con números claros |
| 4 | "Un ingreso pasivo real, no otro trabajo" | Financiero | Fin de mes cómodo pero podría ser mejor | "Ingreso pasivo: cobrás por recomendaciones que ya hacés" |

### Ángulos de conversión
| Ángulo | Tipo | Ejemplo de hook | Layout recomendado |
|--------|------|----------------|-------------------|
| "Recomendación genuina" | Confianza | "Si te gusta un producto, ¿por qué no cobrar por recomendarlo?" | Texto limpio, profesional |
| "Transparencia total" | Racional | "Panel en tiempo real. Ves cada venta, cada comisión." | Screenshot del panel + datos |
| "Ingreso pasivo real" | Aspiracional | "No es otro trabajo. Es cobrar por lo que ya hacés." | Comparación: gratis vs cobrar |
| "Calidad garantizada" | Confianza | "10 días de devolución. 6 meses de garantía. MercadoPago." | Trust badges prominentes |

### Palabras que conectan con Ana
- "transparente", "claro", "sin letra chica"
- "recomendación genuina", "lo que ya hacés"
- "ingreso pasivo", "sin compromiso"
- "calidad", "garantía", "confianza"

### Palabras que la alejan
- "ganá plata fácil", "sin hacer nada"
- Emojis excesivos, diseño amateur
- Promesas de montos específicos

---

## PERSONA 4: SOFI (Creadora de contenido 18-45)

### Perfil emocional
- Su audiencia es su activo más valioso — no la arriesga con marcas truchas
- Busca marcas que le permitan crear contenido auténtico, no guionado
- Le importa que el producto sea "instagrameable" y que su audiencia lo quiera
- Quiere flexibilidad: sin contratos, sin obligaciones de cantidad

### Dolores ordenados por intensidad
| # | Dolor | Categoría | Trigger | Contenido que lo resuelve |
|---|-------|-----------|---------|--------------------------|
| 1 | "Los programas de afiliados pagan poco y tarde" | Financiero | Ver comisiones míseras | "7-15% de comisión. Cobro el día 5." |
| 2 | "No quiero perder credibilidad recomendando algo malo" | Social | Miedo a la audiencia | "Productos reales, garantía de 6 meses" |
| 3 | "Necesito tracking transparente para saber cuánto generé" | Práctico | No saber si funciona | "Panel en tiempo real con cada venta" |
| 4 | "Quiero productos que mi audiencia realmente compre" | Práctico | Recomendar y que nadie compre | "Productos con descuento = mayor conversión" |

### Ángulos de conversión
| Ángulo | Tipo | Ejemplo de hook | Layout recomendado |
|--------|------|----------------|-------------------|
| "Monetizá tu audiencia" | Aspiracional | "Tu audiencia ya te pide recomendaciones. Cobrá por ellas." | Lifestyle + números |
| "Comisiones que valen la pena" | Racional | "7-15% > lo que pagan la mayoría de programas" | Comparativa |
| "Sin contratos" | Libertad | "Sin obligaciones de publicación. Tu contenido, tu ritmo." | Texto limpio |
| "Productos instagrameables" | Visual | "Productos que tu audiencia quiere tener" | Grid de productos |

---

## PERSONA 5: MARTÍN (Mayorista/Revendedor 30-50)

### Dolores y ángulos (simplificado — menor prioridad)
| Dolor | Ángulo | Hook |
|-------|--------|------|
| "Necesito margen real" | Números claros | "25% OFF = margen del 40%+ en reventa" |
| "Quiero variedad" | Catálogo amplio | "300+ productos en 10 categorías" |
| "Envío confiable" | Confianza | "Envío a todo el país con tracking" |

---

## Matriz de selección: Persona × Dolor × Ángulo × Layout

### Layouts disponibles (a implementar)

| ID | Layout | Descripción visual | Pilares que lo usan |
|----|--------|--------------------|---------------------|
| L01 | Título + bullets numerados | Cards numeradas con texto corto | Educativo |
| L02 | Antes/después | 2 zonas (izq desordenado, der ordenado) | Educativo, Producto |
| L03 | Número grande + desglose | Cifra enorme + subtexto + beneficios | Motivacional |
| L04 | Historia + CTA | Texto tipo storytelling centrado + URL | Motivacional |
| L05 | Pregunta + opciones | Encuesta visual A/B/C/D | Engagement |
| L06 | Mito vs realidad | 2 columnas: ❌ mito / ✅ realidad | Educativo, Engagement |
| L07 | Producto lifestyle | Foto grande + hook + precio tachado/descuento | Producto |
| L08 | Comparativa precios | "En ML $X — en El Gadget $Y" | Producto |
| L09 | Paso a paso | 3 pasos circulares horizontales | Educativo |
| L10 | Checklist | ✓ hecho / ○ pendiente | Educativo |

### Cómo funciona la selección

```
1. Se elige una PERSONA (rotación o ponderación)
2. Se elige un DOLOR de esa persona (sin repetir el último usado)
3. Se elige un ÁNGULO compatible con ese dolor
4. Se elige un LAYOUT compatible con ese ángulo
5. Se inyecta todo en el prompt de Claude
6. Claude genera el contenido adaptado
7. Pillow renderiza con el layout elegido + paleta de la persona
```

### Ejemplo de generación inteligente

```
Persona: María
Dolor elegido: "Ya recomiendo cosas gratis en el grupo de mamás"
Ángulo: "Convertí tus recomendaciones en ingresos"
Layout: L03 (Número grande + desglose)
Pilar: Motivacional

→ Claude genera:
  numero_grande: "$10.500"
  subtexto: "si 3 amigas compran $50.000 con tu código"
  bullets: ["Te registrás gratis", "Compartís tu código", "Ellas compran con descuento", "Vos cobrás comisión"]
  hook: "Ya recomendás productos gratis. ¿Y si cobraras?"
  caption: "Cada vez que una amiga te pregunta..."

→ Pillow renderiza con paleta María (cream cálido) + layout L03
```

---

## Variables del sistema para prompts

Estas variables se inyectan dinámicamente en el prompt de Claude:

```python
{
    "persona_nombre": "María",
    "persona_dolor": "Ya recomiendo cosas gratis en el grupo de mamás",
    "persona_dolor_categoria": "social",
    "persona_angulo": "Convertí tus recomendaciones en ingresos",
    "persona_hook_ejemplo": "Ya recomendás productos gratis. ¿Y si cobraras?",
    "persona_palabras_que_conectan": ["tus amigas", "grupo de mamás", "ingreso extra"],
    "persona_palabras_prohibidas": ["negocio", "multinivel", "oportunidad única"],
    "layout_tipo": "L03",
    "layout_campos_requeridos": ["numero_grande", "subtexto", "bullets", "hook"],
    "pilar": "motivacional",
    "producto": { ... },
    "stats_reales": { ... },
}
```
