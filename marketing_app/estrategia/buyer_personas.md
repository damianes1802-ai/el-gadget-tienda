# Buyer Personas — El Gadget

## Contexto del mercado (Argentina 2026)

- 25 millones de compradores online activos
- 6 de cada 10 compran al menos 1 vez por mes
- 71% de las compras se hacen desde celular
- Comprador promedio: 25-44 años, compara precios, lee reviews
- 70% dice que el precio es lo más importante al comprar online
- Mercado Libre lanzó su programa de afiliados (hasta 15%) — validación de que el modelo funciona
- TikTok tiene mayor alcance orgánico para cuentas nuevas; Instagram convierte mejor con comunidad existente

---

## Persona 1: COMPRADORA FINAL — "Laura"

### Demografía
- **Edad**: 28-42 años
- **Género**: Mujer (75% de las compras en categorías hogar/moda/niños)
- **Ubicación**: CABA, GBA, ciudades grandes del interior
- **Ingreso**: Medio — busca buena relación calidad/precio
- **Dispositivo**: Celular (casi exclusivo)

### Psicografía
- Busca soluciones prácticas para el hogar y la familia
- Le importa la opinión de otros (reviews, recomendaciones de amigas)
- Compra por impulso cuando ve una oferta o un producto que resuelve un problema cotidiano
- Desconfía de tiendas que no conoce — necesita prueba social
- Comparte productos con amigas por WhatsApp cuando encuentra algo bueno

### Pain points
- "No quiero pagar de más pero tampoco quiero algo malo"
- "¿Llegará bien? ¿Es confiable esta tienda?"
- "No tengo tiempo de ir a buscar — necesito que me lo manden"
- "¿Tiene garantía? ¿Qué pasa si no me gusta?"

### Journey de compra
1. Ve un producto en WhatsApp (link de amiga/referido) o en redes sociales
2. Entra al link, mira fotos y precio
3. Busca en Google el nombre del producto para comparar
4. Vuelve a la tienda si el precio es competitivo
5. Lee la descripción y la política de devoluciones
6. Agrega al carrito, aplica código de descuento si tiene
7. Paga con MercadoPago (cuotas o débito)

### Métricas que la representan
| Métrica | Cómo medirla | Fuente |
|---------|-------------|--------|
| Tasa de conversión | Visitas vs compras | GA4 + Backend |
| AOV (ticket promedio) | Total / cantidad de órdenes | Backend |
| Tasa de recompra | Clientes con >1 orden / total clientes | Backend |
| Fuente de adquisición | UTM source del primer contacto | UTM tracking |
| Tiempo hasta la compra | Fecha primera visita vs fecha compra | GA4 |
| Tasa de uso de código referido | Órdenes con descuento_codigo / total órdenes | Backend |
| Tasa de abandono de carrito | Carritos creados vs pagados | MercadoPago + Backend |

### Contenido que la convierte

| Tipo | Canal | Formato | Ejemplo | Por qué funciona |
|------|-------|---------|---------|------------------|
| Problema → Solución | Instagram/TikTok | Video 15-30s | "¿Tu placard es un caos? Mirá cómo quedó con este organizador" | Identifica su dolor y muestra resultado |
| Antes/Después | Instagram Stories | Foto doble | Placard desordenado → ordenado con producto | Contraste visual genera deseo |
| Testimonio real | WhatsApp/IG | Captura de chat | "Me llegó ayer y ya lo armé, una masa" | Prueba social de gente como ella |
| Precio + descuento | WhatsApp | Texto + link | "Este organizador está $X con mi código tenés 15% OFF" | Urgencia + ahorro concreto |
| Comparación de valor | Email | HTML con imágenes | "En ML está $X, acá $Y con envío gratis" | Justifica la compra racional |
| Unboxing | TikTok/IG Reels | Video 30-60s | Abrir el paquete, mostrar calidad real | Reduce miedo de "¿será bueno?" |
| FAQ visual | IG Stories/Carrusel | Slides 4-6 | "¿Envían a mi provincia? ¿Tiene garantía?" | Elimina objeciones |

---

## Persona 2: REFERIDO POTENCIAL — "Nico"

### Demografía
- **Edad**: 22-38 años
- **Género**: Mixto (leve mayoría femenina)
- **Ubicación**: Todo el país (online)
- **Ingreso**: Bajo a medio — busca ingresos extra
- **Ocupación**: Empleado, freelancer, estudiante, ama de casa, emprendedor sin capital

### Psicografía
- Busca formas de ganar dinero sin inversión inicial
- Activo en WhatsApp y/o redes sociales
- Tiene una red de contactos (familia, amigos, grupos de WA, seguidores de IG)
- Es escéptico de las promesas de "dinero fácil" — necesita ver que es real
- Valora la transparencia: quiere saber exactamente cuánto va a ganar
- Le motiva más la prueba de ingresos reales que las promesas

### Pain points
- "No tengo plata para invertir en un negocio"
- "¿Realmente se puede ganar o es una estafa?"
- "No sé cómo vender ni tengo experiencia"
- "¿Cuánto necesito vender para que valga la pena?"
- "No quiero quedar como spammer con mis amigos"

### Journey de registro
1. Ve contenido sobre el programa (artículo SEO /ganar/*, redes, boca a boca)
2. Lee la landing /referidos — necesita: prueba social, números claros, cero riesgo
3. Se pregunta "¿cuánto puedo ganar realísticamente?"
4. Se registra (formulario simple: nombre, email, teléfono, DNI)
5. Recibe su código y ve el panel de referido
6. Comparte con 2-3 personas cercanas como "test"
7. Si ve resultados (comisión acreditada), escala su esfuerzo
8. Si no ve resultados en 2-3 semanas, abandona

### Métricas que lo representan
| Métrica | Cómo medirla | Fuente |
|---------|-------------|--------|
| Registros de referidos / mes | Nuevos registros en tabla referidos | Backend |
| Tasa de activación | Referidos con ≥1 venta / total registrados | Backend |
| Tiempo hasta primera venta | Fecha registro vs fecha primer comisión | Backend |
| Ventas por referido activo / mes | Promedio de ventas mensuales por referido | Backend |
| Revenue por referido | Ventas totales / referidos activos | Backend |
| Tasa de churn | Referidos sin venta en 60 días / total | Backend |
| Fuente de registro del referido | UTM del registro | UTM tracking |
| Productos más compartidos | Links con ?ref= + UTM producto_share | UTM tracking |

### Contenido que lo convierte

| Tipo | Canal | Formato | Ejemplo | Por qué funciona |
|------|-------|---------|---------|------------------|
| Calculadora de ganancias | Landing web | Interactivo | "Si compartís con 10 amigos y 2 compran $15.000, ganás $2.100/mes" | Hace tangible la oportunidad |
| Caso de éxito real | IG/TikTok/Email | Testimonio video/texto | "Soy referido hace 2 meses y ya cobré $X" | Prueba social de que funciona |
| Paso a paso | WhatsApp/Blog | Guía corta | "3 pasos para empezar a ganar: registrate, compartí, cobrá" | Reduce barrera de entrada |
| Templates listos | Panel mi_cuenta | Mensajes pre-armados | "Copiar mensaje para WhatsApp → pegar → enviar" | Elimina la dificultad de "no sé qué decir" |
| Comparación con competencia | Blog SEO | Artículo | "El Gadget vs MercadoLibre Afiliados: ¿cuál conviene?" | Posiciona ventajas competitivas |
| Contenido educativo | Email nurturing | Secuencia 3-5 emails | "Día 1: Tu código listo / Día 3: 5 tips para compartir / Día 7: ¿Ya cobraste?" | Acompaña y evita abandono temprano |
| Notificación de logro | Push/Email | Alerta automática | "¡Tu primer referido compró! Ganaste $X" | Dopamina → refuerza comportamiento |

---

## Persona 3: MAYORISTA — "Martín"

### Demografía
- **Edad**: 30-50 años
- **Género**: Mixto
- **Ubicación**: Todo el país (más interior — reventa local)
- **Ingreso**: Medio — revende como actividad principal o secundaria
- **Ocupación**: Comerciante local, vendedor de feria, revendedor online

### Psicografía
- Piensa en márgenes: "¿cuánto gano por unidad?"
- Compra en cantidad, no productos individuales
- Necesita precio competitivo + variedad de productos
- Valora la previsibilidad: que el producto llegue y sea igual a la foto
- Menos sensible al marketing emocional, más al racional (números, márgenes)

### Pain points
- "¿El 25% OFF es real o el precio público ya está inflado?"
- "¿Puedo pedir variedad o tengo que comprar todo igual?"
- "¿Los envíos son confiables para cantidad?"
- "Necesito factura para mi negocio"

### Métricas que lo representan
| Métrica | Cómo medirla | Fuente |
|---------|-------------|--------|
| AOV mayorista | Ticket promedio de órdenes con código MAY* | Backend |
| Frecuencia de compra | Órdenes por mayorista por mes | Backend |
| Productos más pedidos por mayoristas | Items en órdenes mayoristas | Backend |
| Tasa de recompra mayorista | Mayoristas con >1 orden / total | Backend |
| Revenue mayorista / mes | Sum de órdenes con código mayorista | Backend |

### Contenido que lo convierte
| Tipo | Canal | Formato | Ejemplo |
|------|-------|---------|---------|
| Catálogo con márgenes | Email/PDF | Tabla de precios | "Comprás a $X, vendés a $Y, tu ganancia: $Z" |
| Productos nuevos | Email automático | Newsletter semanal | "3 productos nuevos esta semana con margen de 40%+" |
| Stock alert | Email/WhatsApp | Notificación | "Se agotó X, ya volvió: aprovechá antes de que se acabe" |

---

## Matriz de contenido por persona × canal × etapa del embudo

### TOFU (Atracción — no nos conocen)

| Persona | Canal | Contenido | Frecuencia |
|---------|-------|-----------|------------|
| Laura | TikTok/IG Reels | Videos problema→solución con productos | 4-5/semana |
| Laura | Google (SEO) | Artículos "mejor organizador de placard 2026" | 2/mes |
| Nico | Google (SEO) | Artículos /ganar/* "ganar dinero desde casa" | Ya existen 4 |
| Nico | TikTok/IG | "Así gano plata recomendando productos" | 2-3/semana |
| Nico | Facebook Groups | Posts en grupos de "trabajos" / "ingresos extra" | 3/semana |

### MOFU (Consideración — nos conocen, evalúan)

| Persona | Canal | Contenido | Frecuencia |
|---------|-------|-----------|------------|
| Laura | Email | Productos recomendados basados en lo que vio | Automático |
| Laura | WhatsApp (referido) | Link de producto con descuento | Orgánico vía referidos |
| Nico | Email nurturing | Secuencia post-registro (3-5 emails) | Automático |
| Nico | Landing /referidos | FAQ + calculadora + testimonios | Estático (mejorable) |
| Martín | Email | Catálogo con márgenes actualizado | 1/semana |

### BOFU (Conversión — listos para actuar)

| Persona | Canal | Contenido | Frecuencia |
|---------|-------|-----------|------------|
| Laura | Email/WhatsApp | Código de descuento + urgencia | Puntual |
| Laura | Checkout | Banner "10% OFF aplicado" | Automático |
| Nico | Panel mi_cuenta | Templates de share listos + stats | Siempre disponible |
| Nico | Email | "¡Felicitaciones! Tu primer referido compró" | Automático |
| Martín | Email | "Productos nuevos con margen 45%+" | Automático |

---

## KPIs del sistema de contenido

### Métricas de PRODUCCIÓN
- Piezas de contenido generadas / semana
- Tiempo de generación por pieza (target: <2 min con IA)
- Variaciones por producto (target: 3 por producto por canal)

### Métricas de DISTRIBUCIÓN
- Posts publicados / semana por canal
- Emails enviados / semana
- Templates de WhatsApp disponibles por producto

### Métricas de RENDIMIENTO
- CTR por tipo de contenido
- Conversiones por pieza de contenido (UTM tracking)
- Revenue atribuido por canal
- Costo por adquisición por canal (hoy $0 en orgánico)
- Engagement rate por formato (video vs imagen vs texto)

### Métricas de OPTIMIZACIÓN
- Mejor hora de publicación por canal
- Formato con mayor conversión
- Producto con mayor "compartibilidad"
- A/B winner rate (qué % de variantes B supera a la A)
