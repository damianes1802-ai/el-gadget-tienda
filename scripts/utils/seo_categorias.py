# -*- coding: utf-8 -*-
"""Configuración SEO de páginas de categoría y colección.

Los title/H1/meta/intro/FAQ salen del research de Keyword Planner
(SEO-KEYWORDS/MAPA-KEYWORDS.md — regla: una keyword primaria = una URL).
Las colecciones agrupan familias de producto con volumen alto que cruzan
categorías; el matcher es un regex sobre el nombre del producto.
"""
import re
import unicodedata


def slug_categoria(nombre: str) -> str:
    s = unicodedata.normalize('NFKD', nombre or 'general').encode('ascii', 'ignore').decode()
    s = re.sub(r'[^a-z0-9]+', '-', s.lower()).strip('-')
    return s or 'general'


# ── CATEGORÍAS (1:1 con el catálogo) ──
# kw primaria en title+h1+meta; secundarias en intro/FAQ.
CATEGORIAS_SEO = {
    'bazar-y-cocina': {
        'title': 'Artículos de Bazar y Cocina — Utensilios y accesorios | El Gadget',
        'h1': 'Artículos de bazar y cocina',
        'meta': 'Utensilios de cocina, ralladores, escurridores y accesorios de bazar con envío a todo el país. Pagá seguro con Mercado Pago y recibilo en tu casa.',
        'intro': 'Todo lo que hace más fácil la cocina de todos los días: utensilios prácticos, ralladores, escurridores de platos y accesorios de bazar elegidos por su relación precio-calidad. Comprás online, pagás seguro con Mercado Pago y te lo enviamos a todo el país.',
        'faqs': [('¿Hacen envíos de artículos de bazar a todo el país?',
                  'Sí, enviamos a toda la Argentina. El costo de envío se calcula en el checkout según tu código postal y recibís el seguimiento por email.'),
                 ('¿Qué medios de pago aceptan?',
                  'Mercado Pago: tarjetas de crédito, débito y dinero en cuenta. El pago es 100% seguro y la factura llega a tu email.')],
    },
    'accesorios-para-mascotas': {
        'title': 'Accesorios para Mascotas — Alfombras, comederos y más | El Gadget',
        'h1': 'Accesorios para mascotas',
        'meta': 'Accesorios para mascotas: alfombras absorbentes, comederos, cepillos y más para perros y gatos. Envío a todo el país y pago seguro con Mercado Pago.',
        'intro': 'Accesorios pensados para que convivir con tu perro o gato sea más limpio y simple: alfombras absorbentes de diatomita, comederos y bebederos portátiles, cepillos y guantes para el pelo. Envío a toda la Argentina.',
        'faqs': [('¿Las alfombras para mascotas sirven para perros y gatos?',
                  'Sí. Las alfombras absorbentes de diatomita secan patitas y derrames al instante y funcionan igual de bien bajo el comedero de un perro o de un gato.'),
                 ('¿Puedo cambiar un producto si no le queda bien a mi mascota?',
                  'Tenés cambios hasta 10 días después de recibirlo. Escribinos por WhatsApp y lo resolvemos.')],
    },
    'deco': {
        'title': 'Artículos de Decoración para el Hogar — Deco online | El Gadget',
        'h1': 'Artículos de decoración',
        'meta': 'Deco para tu casa: adornos, espejos, detalles luminosos y objetos con onda para renovar ambientes. Comprá online con envío a todo el país.',
        'intro': 'Detalles que cambian un ambiente sin gastar de más: objetos decorativos, espejos y piezas con personalidad para el living, la habitación o tu escritorio. Si buscás lámparas y luces LED, tenemos una sección completa dedicada.',
        'faqs': [('¿Cómo llegan los productos de decoración?',
                  'Embalados para viajar seguros, con envío a todo el país y seguimiento por email. Si algo llega dañado, lo reponemos.')],
    },
    'bano-y-limpieza': {
        'title': 'Accesorios de Baño y Limpieza — Organizá tu baño | El Gadget',
        'h1': 'Accesorios de baño y limpieza',
        'meta': 'Accesorios de baño: alfombras antideslizantes, cepillos, soportes y artículos de limpieza prácticos. Envío a todo el país y pago con Mercado Pago.',
        'intro': 'Accesorios de baño que suman seguridad y orden: alfombras antideslizantes con piedra pómez, cepillos y soluciones de limpieza que simplifican la rutina. Todo con envío a domicilio en Argentina.',
        'faqs': [('¿Las alfombras de baño son antideslizantes de verdad?',
                  'Sí, tienen base antideslizante y las de piedra pómez además exfolian. Son lavables y de secado rápido.')],
    },
    'articulos-infantiles': {
        'title': 'Artículos Infantiles — Juguetes didácticos y regalos para chicos | El Gadget',
        'h1': 'Artículos infantiles',
        'meta': 'Juguetes didácticos, accesorios para bebés y regalos para chicos de todas las edades. Comprá online con envío a todo el país y pago seguro.',
        'intro': 'Regalos para chicos que no fallan: juguetes didácticos, accesorios para bebés y cosas divertidas para el jardín o la escuela. Ideal si buscás un regalo de cumpleaños práctico y original.',
        'faqs': [('¿Sirven como regalo de cumpleaños?',
                  'Totalmente: son regalos prácticos y originales. Si el que recibe quiere otro color o modelo, tiene cambios hasta 10 días.'),
                 ('¿Los juguetes son seguros para bebés?',
                  'Cada ficha de producto indica la edad recomendada y los materiales. Ante cualquier duda, escribinos por WhatsApp antes de comprar.')],
    },
    'accesorios-de-moda': {
        'title': 'Bandoleras y Carteras de Mujer — Accesorios de moda | El Gadget',
        'h1': 'Bandoleras, carteras y accesorios de moda',
        'meta': 'Bandoleras de mujer, carteras, riñoneras y accesorios de moda para todos los días. Comprá online con envío a todo el país y cambios hasta 10 días.',
        'intro': 'Bandoleras tejidas, carteras y riñoneras elegidas para acompañarte todos los días: livianas, cómodas y con onda. Renovate sin gastar una fortuna, con envío a toda la Argentina y cambios sin vueltas.',
        'faqs': [('¿Qué diferencia hay entre bandolera y riñonera?',
                  'La bandolera se cruza al pecho y cuelga al costado; la riñonera se ajusta a la cintura o cruzada. Las dos liberan las manos: es cuestión de estilo.')],
    },
    'verano': {
        'title': 'Artículos de Verano — Accesorios de pileta y playa | El Gadget',
        'h1': 'Artículos de verano',
        'meta': 'Accesorios de pileta, juegos de agua y todo para el verano argentino. Mirá también nuestras mallas e inflables. Envío a todo el país.',
        'intro': 'El verano se disfruta equipado: accesorios de pileta, juegos de agua y todo lo que hace mejores los días de calor. Tenemos secciones dedicadas de mallas y trajes de baño y de inflables para pileta.',
        'faqs': [('¿Llegan a tiempo para las vacaciones?',
                  'Los envíos demoran según tu zona (se calcula en el checkout). Te recomendamos comprar con unos días de anticipación en temporada alta.')],
    },
    'home': {
        'title': 'Artículos para el Hogar — Cosas útiles para tu casa | El Gadget',
        'h1': 'Artículos para el hogar',
        'meta': 'Cosas para la casa que resuelven: artículos para el hogar prácticos y con buen diseño. Comprá online con envío a todo el país y pago seguro.',
        'intro': 'Artículos para el hogar que usás todos los días: soluciones prácticas, con buen diseño y precios razonables. La casa que funciona mejor se arma con detalles bien elegidos.',
        'faqs': [('¿Tienen local físico?',
                  'Somos una tienda online: así mantenemos mejores precios. Comprás desde casa, pagás con Mercado Pago y te lo enviamos a todo el país.')],
    },
    'estetica-y-belleza': {
        'title': 'Accesorios de Belleza y Estética | El Gadget',
        'h1': 'Accesorios de belleza y estética',
        'meta': 'Accesorios de belleza y cuidado personal para tu rutina diaria. Comprá online con envío a todo el país y pago seguro con Mercado Pago.',
        'intro': 'Pequeños aliados para tu rutina de cuidado personal: accesorios de belleza prácticos que hacen más simple el día a día.',
        'faqs': [],
    },
    'fitness': {
        'title': 'Accesorios Fitness para Entrenar en Casa | El Gadget',
        'h1': 'Accesorios fitness',
        'meta': 'Accesorios fitness y elementos para entrenar en casa. Comprá online con envío a todo el país y pago seguro con Mercado Pago.',
        'intro': 'Elementos simples para moverte en casa: accesorios fitness prácticos para sumar actividad sin ir al gimnasio.',
        'faqs': [],
    },
    'electronica': {
        'title': 'Gadgets y Accesorios Electrónicos | El Gadget',
        'h1': 'Gadgets y accesorios electrónicos',
        'meta': 'Accesorios electrónicos y gadgets útiles para tu día a día. Comprá online con envío a todo el país y pago seguro con Mercado Pago.',
        'intro': 'Gadgets electrónicos elegidos por útiles: tecnología simple que resuelve cosas concretas del día a día.',
        'faqs': [],
    },
    'ofertas': {
        'title': 'Ofertas en Artículos para el Hogar y más | El Gadget',
        'h1': 'Ofertas de la semana',
        'meta': 'Las mejores ofertas de El Gadget: artículos para el hogar, deco, cocina y más con descuentos reales. Stock limitado, envío a todo el país.',
        'intro': 'Los precios más afilados del catálogo, en un solo lugar. Descuentos reales sobre productos que ya conocés, mientras dure el stock.',
        'faqs': [],
    },
    'nuevos-ingresos': {
        'title': 'Novedades — Últimos ingresos de la tienda | El Gadget',
        'h1': 'Novedades y últimos ingresos',
        'meta': 'Lo último que llegó a El Gadget: novedades en hogar, deco, cocina y más. Sé el primero en verlas, con envío a todo el país.',
        'intro': 'Lo más nuevo del catálogo, recién llegado. Esta sección se renueva todo el tiempo: si algo te gusta, no lo pienses de más.',
        'faqs': [],
    },
}

# ── COLECCIONES (familias cross-categoría justificadas por volumen + inventario) ──
COLECCIONES_SEO = {
    'mallas-y-trajes-de-bano': {
        'match': r'malla|traje de ba[ñn]o|bikini|enteriza|tankini|trikini|vedetina',
        'title': 'Mallas y Trajes de Baño de Mujer — Enterizas y bikinis | El Gadget',
        'h1': 'Mallas y trajes de baño',
        'meta': 'Mallas de mujer, enterizas, bikinis y tankinis para este verano. Comprá tu traje de baño online con envío a todo el país y cambios hasta 10 días.',
        'intro': 'Mallas de mujer para todos los estilos: enterizas que estilizan, bikinis clásicas y tankinis cómodas. Elegí tu talle, pagá seguro con Mercado Pago y recibila en tu casa — con cambios hasta 10 días por si el talle no es el ideal.',
        'faqs': [('¿Qué pasa si no me queda bien el talle de la malla?',
                  'Tenés cambios hasta 10 días después de recibirla. Escribinos por WhatsApp y coordinamos el cambio de talle sin vueltas.'),
                 ('¿Qué diferencia hay entre enteriza y tankini?',
                  'La enteriza es de una sola pieza; el tankini es de dos piezas pero con top largo que cubre el abdomen. Los dos dan más cobertura que una bikini clásica.')],
    },
    'lamparas-y-luces-led': {
        'match': r'lampara|l[áa]mpara|velador|luz led|luces|guirnalda|luminos',
        'title': 'Lámparas LED y Veladores — Luces para tu casa | El Gadget',
        'h1': 'Lámparas LED, veladores y luces',
        'meta': 'Lámparas LED, veladores para mesa de luz y luces decorativas para la habitación. Iluminá tu casa con onda: envío a todo el país y pago seguro.',
        'intro': 'Luces que hacen ambiente: lámparas LED de diseño, veladores para la mesa de luz y luces decorativas para la habitación o el escritorio. Bajo consumo, mucha personalidad.',
        'faqs': [('¿Los veladores LED consumen mucha electricidad?',
                  'No: la tecnología LED consume una fracción de una lámpara tradicional. Podés dejarlos encendidos como luz de compañía sin preocuparte por la factura.'),
                 ('¿Las lámparas vienen con la fuente o pilas incluidas?',
                  'Cada ficha de producto lo detalla. La mayoría funciona con USB o pilas comunes; lo que incluye la caja está siempre especificado.')],
    },
    'organizadores': {
        'match': r'organizador|organizadora|cajonera|zapatero|perchero|colgante de puerta',
        'title': 'Organizadores para el Hogar — Cocina, baño, auto y más | El Gadget',
        'h1': 'Organizadores para el hogar',
        'meta': 'Organizadores de cocina, baño, placard, valija y auto: soluciones para ganar espacio y encontrar todo. Envío a todo el país y pago seguro.',
        'intro': 'Ganale espacio a tu casa: organizadores de cocina, baño, placard, valija y hasta para el baúl del auto. Cada cosa en su lugar, sin renovar muebles ni gastar de más.',
        'faqs': [('¿Qué organizador me conviene para espacios chicos?',
                  'Los plegables y los colgantes de puerta rinden mucho en espacios chicos: suman lugares de guardado sin ocupar piso ni requerir instalación.')],
    },
    'vasos-y-botellas-termicas': {
        'match': r'vaso t[ée]rm|botella t[ée]rm|termo|vaso.*(stanley|starbucks|doble pared)',
        'title': 'Vasos Térmicos y Botellas Térmicas — Frío y calor por horas | El Gadget',
        'h1': 'Vasos y botellas térmicas',
        'meta': 'Vasos térmicos y botellas térmicas que mantienen tu bebida fría o caliente por horas. Para el mate, el café o el gym. Envío a todo el país.',
        'intro': 'Tu bebida a la temperatura justa, horas después: vasos térmicos para el café o la cerveza y botellas térmicas para el agua del día, el mate o el gym. Acero inoxidable y doble pared de verdad.',
        'faqs': [('¿Cuántas horas mantiene la temperatura un vaso térmico?',
                  'Depende del modelo: los de acero de doble pared mantienen el frío hasta 6-12 horas y el calor 4-6. Cada ficha de producto especifica el rendimiento.'),
                 ('¿Se pueden lavar en el lavavajillas?',
                  'Recomendamos lavarlos a mano para cuidar el vacío térmico y los sellos de la tapa. Es un minuto y duran años.')],
    },
    'inflables-para-pileta': {
        'match': r'inflable|flotador|colchoneta',
        'title': 'Inflables para Pileta — Flotadores y gigantes de verano | El Gadget',
        'h1': 'Inflables para pileta',
        'meta': 'Inflables para pileta: flotadores gigantes, colchonetas y modelos para bebés. El verano más divertido, con envío a todo el país.',
        'intro': 'La pileta se disfruta el doble con un buen inflable: flotadores gigantes para las fotos del verano, colchonetas para flotar sin apuro y modelos seguros para los más chicos.',
        'faqs': [('¿Los inflables para bebés son seguros?',
                  'Los modelos infantiles tienen asiento contenedor y están pensados para usarse siempre con un adulto al lado. La edad recomendada figura en cada ficha.')],
    },
}
