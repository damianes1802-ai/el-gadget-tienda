# -*- coding: utf-8 -*-
"""Configuración SEO de páginas de categoría y colección.

Title/H1/meta/intro/secciones/FAQ salen del research de Keyword Planner
(SEO-KEYWORDS/MAPA-KEYWORDS.md — regla: una keyword primaria = una URL).
Las 'secciones' (H2 + párrafo) cubren las keywords SECUNDARIAS de cada grupo;
solo se usan términos que el inventario puede satisfacer honestamente.
"""
import re
import unicodedata


def slug_categoria(nombre: str) -> str:
    s = unicodedata.normalize('NFKD', nombre or 'general').encode('ascii', 'ignore').decode()
    s = re.sub(r'[^a-z0-9]+', '-', s.lower()).strip('-')
    return s or 'general'


CATEGORIAS_SEO = {
    'bazar-y-cocina': {
        'title': 'Botellas Térmicas, Vasos y Bazar de Cocina | El Gadget',
        'h1': 'Artículos de bazar y cocina',
        'meta': 'Utensilios de cocina, ralladores, escurridores y accesorios de bazar con envío a todo el país. Pagá seguro con Mercado Pago y recibilo en tu casa.',
        'intro': 'Todo lo que hace más fácil la cocina de todos los días: utensilios prácticos, escurridores de platos y accesorios de bazar elegidos por su relación precio-calidad. Comprás online, pagás seguro con Mercado Pago y te lo enviamos a todo el país.',
        'secciones': [
            ('Escurridores de platos y orden en la mesada',
             'Un buen escurridor de platos cambia la mesada: tenemos desde el secaplatos rack de 3 niveles regulable hasta el organizador escurridor extraíble que se adhiere donde lo necesites. Suman lugar de secado sin ocupar media cocina y se llevan bien con cocinas chicas.'),
            ('Utensilios de cocina que se usan de verdad',
             'Nada de cajones llenos de cosas que no se usan: filtros de bacha, cepillos flexibles para copas y botellas, organizadores colgantes para tazas y utensilios de cocina pensados para el uso diario. Cada producto tiene fotos reales, medidas y descripción completa en su ficha.'),
        ],
        'faqs': [('¿Qué escurridor de platos me conviene si tengo poca mesada?',
                  'El organizador escurridor adhesivo extraíble no apoya en la mesada, y el secaplatos rack de 3 niveles aprovecha la altura: en el espacio de un plato secás vajilla completa.'),
                 ('¿Hacen envíos de artículos de bazar a todo el país?',
                  'Sí, enviamos a toda la Argentina. El costo se calcula en el checkout según tu código postal y recibís el seguimiento por email.'),
                 ('¿Qué medios de pago aceptan?',
                  'Mercado Pago: tarjetas de crédito, débito y dinero en cuenta. El pago es 100% seguro y la factura llega a tu email.')],
    },
    'accesorios-para-mascotas': {
        'title': 'Alfombras Absorbentes y Collares para Mascotas | El Gadget',
        'h1': 'Accesorios para mascotas',
        'meta': 'Accesorios para mascotas: alfombras absorbentes, comederos, cepillos y más para perros y gatos. Envío a todo el país y pago seguro con Mercado Pago.',
        'intro': 'Accesorios pensados para que convivir con tu perro o gato sea más limpio y simple: alfombras absorbentes de diatomita, comederos y bebederos portátiles, cepillos y guantes para el pelo. Envío a toda la Argentina.',
        'secciones': [
            ('Alfombras para el comedero de perros y gatos',
             'La zona del comedero es la más difícil de mantener seca. Las alfombras absorbentes de diatomita secan el agua al instante y las de base impermeable contienen las migas y salpicaduras: piso limpio sin secar dos veces por día.'),
            ('Paseo, viaje y cuidado del pelo',
             'Para salir de casa: bebederos y comederos portátiles que se pliegan y van a cualquier lado. Para adentro: guantes y cepillos que sacan el pelo suelto de tu perro o gato antes de que termine en el sillón.'),
            ('Comedero para perros: la dupla con la alfombra',
             'El mejor setup para el comedero de tu perro es la dupla comedero + alfombra absorbente: el comedero portátil con bebedero para las salidas y los viajes, y la alfombra de diatomita abajo para que el agua que chorrea desaparezca al instante. Piso seco, zona delimitada y limpieza de 10 segundos.'),
        ],
        'faqs': [('¿Las alfombras para mascotas sirven para perros y gatos?',
                  'Sí. Las alfombras absorbentes de diatomita secan patitas y derrames al instante y funcionan igual de bien bajo el comedero de un perro o de un gato.'),
                 ('¿Puedo cambiar un producto si no le queda bien a mi mascota?',
                  'Tenés cambios hasta 10 días después de recibirlo. Escribinos por WhatsApp y lo resolvemos.')],
    },
    'deco': {
        'title': 'Lámparas, Luces LED y Decoración para el Hogar | El Gadget',
        'h1': 'Artículos de decoración',
        'meta': 'Deco para tu casa: adornos, espejos, detalles luminosos y objetos con onda para renovar ambientes. Comprá online con envío a todo el país.',
        'intro': 'Detalles que cambian un ambiente sin gastar de más: objetos decorativos, espejos y piezas con personalidad para el living, la habitación o tu escritorio.',
        'secciones': [
            ('Espejos decorativos y detalles con luz',
             'Un espejo decorativo agranda visualmente cualquier ambiente, y una lámpara con efecto espejado infinito lo transforma de noche. Si buscás iluminación completa, mirá la sección de <a href="/coleccion/lamparas-y-luces-led/">lámparas y luces LED</a>: veladores, lámparas de escritorio y luces para la habitación.'),
            ('Deco hogar que se anima',
             'Piezas divertidas que escapan de lo genérico: lámparas con formas, colores que suman personalidad y objetos que quedan bien en el estante y mejor en las fotos. Deco pensada para regalar (o regalarte).'),
            ('Decoración de living: tres movidas seguras',
             'Para renovar la decoración del living sin equivocarte: un espejo decorativo que multiplique la luz (cuanto más chico el ambiente, más rinde), un punto de luz cálida a la altura de los ojos, y un solo objeto protagonista que hable de vos. Tres cambios, cero obras, y el living parece otro.'),
        ],
        'faqs': [('¿Cómo llegan los productos de decoración?',
                  'Embalados para viajar seguros, con envío a todo el país y seguimiento por email. Si algo llega dañado, lo reponemos.'),
                 ('¿Qué me conviene para renovar un ambiente con poco presupuesto?',
                  'Luz y espejos: un velador LED cálido más un espejo decorativo cambian el clima de una habitación por menos de lo que cuesta pintar.')],
    },
    'bano-y-limpieza': {
        'title': 'Escobillas y Accesorios de Baño y Limpieza | El Gadget',
        'h1': 'Accesorios de baño y limpieza',
        'meta': 'Accesorios de baño: alfombras antideslizantes, jaboneras, estantes y artículos de limpieza prácticos. Envío a todo el país y pago con Mercado Pago.',
        'intro': 'Accesorios de baño que suman seguridad y orden: alfombras antideslizantes con piedra pómez, jaboneras, estantes y soluciones de limpieza que simplifican la rutina. Todo con envío a domicilio en Argentina.',
        'secciones': [
            ('Seguridad en la ducha: alfombras antideslizantes',
             'La alfombrilla antideslizante con piedra pómez cumple doble función: agarre firme bajo la ducha y exfoliación mientras te bañás. Base con sopapas, lavable y de secado rápido.'),
            ('Orden y limpieza sin esfuerzo',
             'Jaboneras que drenan solas, estantes que suman lugar donde no había y artículos de limpieza que resuelven rápido. Si buscás organizadores para todos los ambientes, tenemos una <a href="/coleccion/organizadores/">sección completa de organizadores</a>.'),
        ],
        'faqs': [('¿Las alfombras de baño son antideslizantes de verdad?',
                  'Sí, tienen base con sopapas y las de piedra pómez además exfolian. Son lavables y de secado rápido.'),
                 ('¿Los accesorios de baño necesitan instalación?',
                  'No: casi todos son adhesivos, con sopapas o apoyados. Nada de agujerear azulejos ni llamar a nadie.')],
    },
    'articulos-infantiles': {
        'title': 'Bodys de Bebé, Útiles y Regalos para Chicos | El Gadget',
        'h1': 'Artículos infantiles',
        'meta': 'Juguetes didácticos, accesorios para bebés y regalos para chicos de todas las edades. Comprá online con envío a todo el país y pago seguro.',
        'intro': 'Regalos para chicos que no fallan: juguetes didácticos, accesorios para bebés y cosas divertidas para el jardín o la escuela. Ideal si buscás un regalo de cumpleaños práctico y original.',
        'secciones': [
            ('Juguetes didácticos para jugar y aprender',
             'Juguetes que entretienen sin pantalla: pop-its, anotadores mágicos y juegos que desarrollan la motricidad fina. Los favoritos para el aula, el viaje en auto y la sala de espera.'),
            ('Para bebés: cambiadores, baberos y más',
             'Lo práctico del día a día con un bebé: cambiadores acolchonados, baberos de algodón suave y accesorios pensados para que la rutina sea más simple. Materiales lavables y seguros, detallados en cada ficha.'),
        ],
        'faqs': [('¿Sirven como regalo de cumpleaños?',
                  'Totalmente: son regalos prácticos y originales. Si el que recibe quiere otro color o modelo, tiene cambios hasta 10 días.'),
                 ('¿Los juguetes son seguros para bebés?',
                  'Cada ficha de producto indica la edad recomendada y los materiales. Ante cualquier duda, escribinos por WhatsApp antes de comprar.')],
    },
    'accesorios-de-moda': {
        'title': 'Blusas, Bandoleras y Carteras de Mujer | El Gadget',
        'h1': 'Bandoleras, carteras y accesorios de moda',
        'meta': 'Bandoleras de mujer, carteras, riñoneras y accesorios de moda para todos los días. Comprá online con envío a todo el país y cambios hasta 10 días.',
        'intro': 'Bandoleras tejidas, carteras y riñoneras elegidas para acompañarte todos los días: livianas, cómodas y con onda. Renovate sin gastar una fortuna, con envío a toda la Argentina y cambios sin vueltas.',
        'secciones': [
            ('Bandoleras de mujer: tejidas, transparentes y urbanas',
             'La bandolera es el accesorio que resuelve: manos libres, lo esencial a mano y estilo sin esfuerzo. Tenemos tejidas al crochet para el verano, transparentes de PVC para eventos y urbanas para todos los días.'),
            ('Riñoneras y carteras para cada plan',
             'Una riñonera de mujer para salir liviana, una cartera con más lugar para el día largo. Elegí por tamaño y estilo en las fichas: medidas exactas, fotos reales y detalle de compartimentos.'),
            ('Carteras de mujer: cómo elegir la tuya',
             'Para elegir una cartera de mujer que uses de verdad, pensá en tu día típico: si cargás poco, una bandolera compacta te libera; si llevás la vida encima, buscá compartimentos y cierre seguro. Los materiales tejidos son los livianos del verano; el PVC transparente es el permitido de los eventos. Todas con cambios hasta 10 días.'),
        ],
        'faqs': [('¿Qué diferencia hay entre bandolera y riñonera?',
                  'La bandolera se cruza al pecho y cuelga al costado; la riñonera se ajusta a la cintura o cruzada. Las dos liberan las manos: es cuestión de estilo.'),
                 ('¿Puedo cambiar una cartera si no me convence?',
                  'Sí, tenés cambios hasta 10 días desde que la recibís. Escribinos por WhatsApp y lo coordinamos.')],
    },
    'verano': {
        'title': 'Bikinis, Mallas e Inflables de Pileta | El Gadget',
        'h1': 'Artículos de verano',
        'meta': 'Accesorios de pileta, juegos de agua y todo para el verano argentino. Mirá también nuestras mallas e inflables. Envío a todo el país.',
        'intro': 'El verano se disfruta equipado: accesorios de pileta, juegos de agua y todo lo que hace mejores los días de calor.',
        'secciones': [
            ('Mallas y trajes de baño',
             'Enterizas, bikinis y vedetinas para el verano: mirá la <a href="/coleccion/mallas-y-trajes-de-bano/">colección completa de mallas y trajes de baño</a> con talles y cambios hasta 10 días.'),
            ('Inflables y juegos de pileta',
             'De los flotadores gigantes para las fotos a los inflables seguros para bebés: la <a href="/coleccion/inflables-para-pileta/">sección de inflables para pileta</a> tiene el verano resuelto.'),
        ],
        'faqs': [('¿Llegan a tiempo para las vacaciones?',
                  'Los envíos demoran según tu zona (se calcula en el checkout). Te recomendamos comprar con unos días de anticipación en temporada alta.')],
    },
    'home': {
        'title': 'Macetas y Artículos Decorativos para el Hogar | El Gadget',
        'h1': 'Artículos para el hogar',
        'meta': 'Cosas para la casa que resuelven: artículos para el hogar prácticos y con buen diseño. Comprá online con envío a todo el país y pago seguro.',
        'intro': 'Artículos para el hogar que usás todos los días: soluciones prácticas, con buen diseño y precios razonables. La casa que funciona mejor se arma con detalles bien elegidos.',
        'secciones': [
            ('Cosas para la casa que resuelven problemas reales',
             'Cada producto de esta sección entró al catálogo por resolver algo concreto: humedad, desorden, falta de espacio o de luz. Sin chiches que juntan polvo: cosas para el hogar que se usan.'),
            ('¿Buscás ordenar? Organizadores para cada ambiente',
             'Si el problema es el espacio, la respuesta está en la <a href="/coleccion/organizadores/">sección de organizadores</a>: cocina, baño, placard y hasta el baúl del auto.'),
        ],
        'faqs': [('¿Tienen local físico?',
                  'Somos una tienda online: así mantenemos mejores precios. Comprás desde casa, pagás con Mercado Pago y te lo enviamos a todo el país.'),
                 ('¿Cómo sé si el producto es del tamaño que necesito?',
                  'Todas las fichas tienen medidas exactas y fotos reales. Y si igual no era lo que esperabas, tenés cambios hasta 10 días.')],
    },
    'estetica-y-belleza': {
        'title': 'Accesorios de Belleza y Estética | El Gadget',
        'h1': 'Accesorios de belleza y estética',
        'meta': 'Accesorios de belleza y cuidado personal para tu rutina diaria. Comprá online con envío a todo el país y pago seguro con Mercado Pago.',
        'intro': 'Pequeños aliados para tu rutina de cuidado personal: accesorios de belleza prácticos que hacen más simple el día a día.',
        'secciones': [
            ('Cuidado personal sin vueltas',
             'Accesorios elegidos por útiles: herramientas simples que mejoran la rutina de cuidado sin gastar en aparatología. Cada ficha detalla materiales y modo de uso.'),
        ],
        'faqs': [('¿Los accesorios de belleza tienen garantía?',
                  'Sí: si algo llega fallado lo reponemos, y tenés cambios hasta 10 días desde la entrega. Escribinos por WhatsApp y lo resolvemos.')],
    },
    'fitness': {
        'title': 'Accesorios Fitness para Entrenar en Casa | El Gadget',
        'h1': 'Accesorios fitness',
        'meta': 'Accesorios fitness y elementos para entrenar en casa. Comprá online con envío a todo el país y pago seguro con Mercado Pago.',
        'intro': 'Elementos simples para moverte en casa: accesorios fitness prácticos para sumar actividad sin ir al gimnasio.',
        'secciones': [
            ('Entrenar en casa con poco equipamiento',
             'No hace falta un gimnasio en el living: con pocos elementos bien elegidos podés armar una rutina en casa. Esta sección crece con cada actualización del catálogo.'),
        ],
        'faqs': [('¿Sirven para principiantes?',
                  'Sí: son elementos de entrada, ideales para arrancar en casa. En cada ficha vas a encontrar medidas, materiales y sugerencias de uso.')],
    },
    'electronica': {
        'title': 'Relojes Infantiles y Gadgets Electrónicos | El Gadget',
        'h1': 'Gadgets y accesorios electrónicos',
        'meta': 'Accesorios electrónicos y gadgets útiles para tu día a día. Comprá online con envío a todo el país y pago seguro con Mercado Pago.',
        'intro': 'Gadgets electrónicos elegidos por útiles: tecnología simple que resuelve cosas concretas del día a día.',
        'secciones': [
            ('Gadgets que se ganan el lugar',
             'Acá no entra cualquier chiche: cada gadget electrónico del catálogo resuelve algo puntual — luz donde no llega la instalación, carga donde no hay enchufe, comodidad donde había vueltas. Sección chica pero elegida.'),
        ],
        'faqs': [('¿Los gadgets electrónicos tienen garantía?',
                  'Sí: si llega fallado lo reponemos sin costo, y tenés 10 días de cambios. Los detalles de alimentación (USB, pilas) están en cada ficha.')],
    },
    'ofertas': {
        'title': 'Ofertas en Artículos para el Hogar y más | El Gadget',
        'h1': 'Ofertas de la semana',
        'meta': 'Las mejores ofertas de El Gadget: artículos para el hogar, deco, cocina y más con descuentos reales. Stock limitado, envío a todo el país.',
        'intro': 'Los precios más afilados del catálogo, en un solo lugar. Descuentos reales sobre productos que ya conocés, mientras dure el stock.',
        'secciones': [
            ('Cómo funcionan las ofertas',
             'Los productos de esta sección tienen precio rebajado de verdad — sin inflar antes para "rebajar" después. El stock es el que se ve: cuando se termina, la oferta desaparece del catálogo.'),
        ],
        'faqs': [('¿Las ofertas se combinan con códigos de descuento?',
                  'No se acumulan: el sistema aplica automáticamente el que más te convenga entre la oferta y tu código. Nunca pagás de más.'),
                 ('¿Cuánto duran las ofertas?',
                  'Hasta agotar stock o hasta el fin de la campaña vigente. Si algo te interesa, no lo dejes pasar: el catálogo se actualiza todos los días.')],
    },
    'nuevos-ingresos': {
        'title': 'Novedades — Últimos ingresos de la tienda | El Gadget',
        'h1': 'Novedades y últimos ingresos',
        'meta': 'Lo último que llegó a El Gadget: novedades en hogar, deco, cocina y más. Sé el primero en verlas, con envío a todo el país.',
        'intro': 'Lo más nuevo del catálogo, recién llegado. Esta sección se renueva todo el tiempo: si algo te gusta, no lo pienses de más.',
        'secciones': [],
        'faqs': [('¿Cada cuánto entran productos nuevos?',
                  'El catálogo se actualiza todos los días de forma automática: precios, stock y productos nuevos. Esta sección muestra los últimos ingresos.')],
    },
}

COLECCIONES_SEO = {
    'mallas-y-trajes-de-bano': {
        'match': r'malla|traje de ba[ñn]o|bikini|enteriza|tankini|trikini|vedetina',
        'excluir': r'silla|respaldo|escritorio|oficina',
        'grupos': [('enterizas', 'Mallas enterizas', r'enteriza'),
                   ('bikinis', 'Bikinis y vedetinas', r'bikini|vedetina|tiro alto'),
                   ('mas', 'Más mallas y trajes de baño', r'.')],
        'title': 'Mallas y Trajes de Baño de Mujer — Enterizas y bikinis | El Gadget',
        'h1': 'Mallas y trajes de baño',
        'meta': 'Mallas de mujer, enterizas, bikinis y tankinis para este verano. Comprá tu traje de baño online con envío a todo el país y cambios hasta 10 días.',
        'intro': 'Mallas de mujer para todos los estilos: enterizas que estilizan, bikinis clásicas y vedetinas con onda. Elegí tu talle, pagá seguro con Mercado Pago y recibila en tu casa — con cambios hasta 10 días por si el talle no es el ideal.',
        'secciones': [
            ('Mallas enterizas: las que más estilizan',
             'La malla enteriza vuelve todos los veranos por una razón: estiliza, contiene y se banca la pileta y el mar. Tenemos lisas y estampadas — desde el clásico negro hasta lunares y colores vivos.'),
            ('Bikinis y vedetinas',
             'Bikini de tiro alto para las que quieren cobertura con estilo retro, vedetinas con tiras para atar para regular el calce, y clásicas de siempre. Cada ficha tiene la tabla de talles y fotos reales del producto.'),
            ('Bikini de tiro alto: la tendencia que se quedó',
             'La bikini de tiro alto volvió del archivo retro y se quedó por una razón práctica: cubre el abdomen sin resignar diseño, banca el movimiento y favorece a todos los cuerpos. Combinala con top clásico o con mangas tipo vedetina para un look de playa con identidad propia.'),
        ],
        'faqs': [('¿Qué pasa si no me queda bien el talle de la malla?',
                  'Tenés cambios hasta 10 días después de recibirla. Escribinos por WhatsApp y coordinamos el cambio de talle sin vueltas.'),
                 ('¿Qué malla estiliza más?',
                  'Las enterizas de color liso u oscuras son las que más estilizan; la bikini de tiro alto es el punto medio: cobertura en el abdomen sin resignar diseño.'),
                 ('¿Cómo cuido la malla para que dure?',
                  'Enjuagala con agua dulce después de la pileta (el cloro degrada la lycra), lavala a mano y secala a la sombra. Con esos tres hábitos te dura varias temporadas.')],
    },
    'lamparas-y-luces-led': {
        'match': r'lampara|l[áa]mpara|velador|luz led|luces|guirnalda|luminos',
        'excluir': r'silla|respaldo',
        'grupos': [('veladores', 'Veladores LED', r'velador'),
                   ('lamparas', 'Lámparas de mesa y escritorio', r'lampara|l[áa]mpara'),
                   ('luces', 'Luces y guirnaldas LED', r'.')],
        'title': 'Lámparas LED y Veladores — Luces para tu casa | El Gadget',
        'h1': 'Lámparas LED, veladores y luces',
        'meta': 'Lámparas LED, veladores para mesa de luz y luces decorativas para la habitación. Iluminá tu casa con onda: envío a todo el país y pago seguro.',
        'intro': 'Luces que hacen ambiente: lámparas LED de diseño, veladores para la mesa de luz y luces decorativas para la habitación o el escritorio. Bajo consumo, mucha personalidad.',
        'secciones': [
            ('Veladores para la mesa de luz',
             'Un velador LED da la luz justa para leer o dejar de compañía, sin encandilar. Los de efecto infinito espejado suman deco de día y magia de noche — los favoritos para habitaciones infantiles y juveniles.'),
            ('Luces LED para la habitación y el escritorio',
             'Las luces LED recargables con sensor resuelven la alacena, el pasillo o el placard sin instalación; la lámpara de escritorio con ventilador USB y reloj es el 3-en-1 del home office. Todo bajo consumo, detallado en cada ficha.'),
        ],
        'faqs': [('¿Los veladores LED consumen mucha electricidad?',
                  'No: la tecnología LED consume una fracción de una lámpara tradicional. Podés dejarlos encendidos como luz de compañía sin preocuparte por la factura.'),
                 ('¿Las lámparas vienen con la fuente o pilas incluidas?',
                  'Cada ficha de producto lo detalla. La mayoría funciona con USB o pilas comunes; lo que incluye la caja está siempre especificado.'),
                 ('¿Qué luz conviene para una habitación infantil?',
                  'Un velador de luz cálida con forma divertida: acompaña a la noche sin desvelar. Los modelos con efecto infinito son los que más piden los chicos.')],
    },
    'organizadores': {
        'match': r'organizador|organizadora|cajonera|zapatero|perchero|colgante de puerta',
        'grupos': [('cocina', 'Organizadores de cocina', r'cocina|escurridor|taza|colgante'),
                   ('bano', 'Organizadores de baño', r'ba[ñn]o|ducha|bacha'),
                   ('placard', 'Placard y zapateros', r'zapatero|cajonera|placard|ropa'),
                   ('auto', 'Para el auto y los viajes', r'auto|ba[úu]l|viaje|valija'),
                   ('mas', 'Más organizadores', r'.')],
        'title': 'Organizadores para el Hogar — Cocina, baño, auto y más | El Gadget',
        'h1': 'Organizadores para el hogar',
        'meta': 'Organizadores de cocina, baño, placard, zapatero y auto: soluciones para ganar espacio y encontrar todo. Envío a todo el país y pago seguro.',
        'intro': 'Ganale espacio a tu casa: organizadores de cocina, baño, placard y hasta para el baúl del auto. Cada cosa en su lugar, sin renovar muebles ni gastar de más.',
        'secciones': [
            ('Zapatero y placard: el orden que se ve',
             'El zapatero abatible de 3 puertas guarda el calzado de toda la familia en el espacio de un cuadro: ideal para recibidores y espacios chicos. Sumale cajoneras con ruedas y el placard respira.'),
            ('Organizador de cocina, baño y auto',
             'Colgantes que aprovechan la altura en la cocina, organizadores adhesivos para el baño y el bolso organizador plegable que ordena el baúl del auto de una vez. Medidas exactas en cada ficha para que compres seguro.'),
            ('Organizador de zapatos: del caos al recibidor',
             'El organizador de zapatos más buscado es el zapatero de recibidor: recibe el calzado en la entrada y evita que migre por toda la casa. El abatible de 3 puertas funciona como mueble de apoyo además de guardar pares de toda la familia — y con 20cm de profundidad entra donde un mueble común no. Para dentro del placard, las cajoneras apilables mantienen los pares visibles y sin polvo.'),
        ],
        'faqs': [('¿Qué organizador me conviene para espacios chicos?',
                  'Los plegables y los colgantes de puerta rinden mucho en espacios chicos: suman lugares de guardado sin ocupar piso ni requerir instalación.'),
                 ('¿El zapatero necesita armado?',
                  'Viene con instrucciones y el armado es simple, sin herramientas raras. En la ficha del producto están las medidas exactas para confirmar que entra en tu espacio.')],
    },
    'vasos-y-botellas-termicas': {
        'match': r'vaso t[ée]rm|botella t[ée]rm|termo|vaso.*(stanley|starbucks|doble pared)',
        'grupos': [('vasos', 'Vasos térmicos', r'vaso'),
                   ('botellas', 'Botellas térmicas y termos', r'.')],
        'title': 'Vasos Térmicos y Botellas Térmicas — Frío y calor por horas | El Gadget',
        'h1': 'Vasos y botellas térmicas',
        'meta': 'Vasos térmicos y botellas térmicas que mantienen tu bebida fría o caliente por horas. Para el mate, el café o el gym. Envío a todo el país.',
        'intro': 'Tu bebida a la temperatura justa, horas después: vasos térmicos para el café o la cerveza y botellas térmicas para el agua del día, el mate o el gym. Acero inoxidable y doble pared de verdad.',
        'secciones': [
            ('Vasos térmicos: del café de la mañana a la cerveza del sábado',
             'El tumbler térmico de 1200ml con agarre y sorbete rebatible banca el día entero, del primer café a la última recarga. Para llevar, la botella térmica de acero de 400ml entra en cualquier bolso y la de 1000ml te cubre la jornada completa.'),
            ('Botellas térmicas para llevar',
             'La botella térmica de acero mantiene el agua fría en el gym o la facultad, y las infantiles de 760ml van al cole y vuelven. Doble pared real: frío por horas, calor también.'),
            ('¿Buscás un vaso térmico grande?',
             'El tumbler de 1200ml con agarre es el más pedido del catálogo: doble pared aislante, tapa hermética a rosca, sorbete rebatible y manija desmontable para llevarlo a donde vayas. Si lo tuyo es hidratarte durante el día, la botella de agua térmica cumple el mismo trabajo en formato para llevar: agua fría de la mañana al final de la jornada, sin transpirar la mochila.'),
        ],
        'faqs': [('¿Cuántas horas mantiene la temperatura un vaso térmico?',
                  'Depende del modelo: los de acero de doble pared mantienen el frío hasta 6-12 horas y el calor 4-6. Cada ficha de producto especifica el rendimiento.'),
                 ('¿Se pueden lavar en el lavavajillas?',
                  'Recomendamos lavarlos a mano para cuidar el vacío térmico y los sellos de la tapa. Es un minuto y duran años.'),
                 ('¿Vaso térmico o botella térmica: cuál me conviene?',
                  'Para tomar mientras trabajás o manejás, el vaso con tapa y agarre. Para transportar e hidratarte durante el día, la botella con cierre hermético.')],
    },
    'inflables-para-pileta': {
        'match': r'inflable|flotador|colchoneta',
        'grupos': [('gigantes', 'Inflables gigantes y flotadores', r'gigante|flotador|tuc[áa]n|cisne|unicornio'),
                   ('chicos', 'Para los más chicos', r'beb[ée]|infantil|ni[ñn]|chico'),
                   ('mas', 'Más inflables', r'.')],
        'title': 'Inflables para Pileta — Flotadores y gigantes de verano | El Gadget',
        'h1': 'Inflables para pileta',
        'meta': 'Inflables para pileta: flotadores gigantes y modelos seguros para bebés. El verano más divertido, con envío a todo el país.',
        'intro': 'La pileta se disfruta el doble con un buen inflable: flotadores gigantes para las fotos del verano y modelos seguros para los más chicos.',
        'secciones': [
            ('Flotadores gigantes: los protagonistas del verano',
             'El tucán de 2 metros, el cisne gigante y el unicornio con glitter: inflables para pileta tamaño XL que se vuelven la foto del verano. Vinilo resistente y válvulas reforzadas para que duren más de una temporada.'),
            ('Inflables para bebés y chicos',
             'Los flotadores infantiles con asiento contenedor dan seguridad para las primeras piletas — siempre con un adulto al lado. La edad y el peso recomendado están en cada ficha.'),
        ],
        'faqs': [('¿Los inflables para bebés son seguros?',
                  'Los modelos infantiles tienen asiento contenedor y están pensados para usarse siempre con un adulto al lado. La edad recomendada figura en cada ficha.'),
                 ('¿Cómo guardo el inflable para que dure?',
                  'Desinflalo por completo, secalo a la sombra y guardalo plegado lejos del sol. El vinilo agradece: te dura varias temporadas.')],
    },
}


# ============================================================================
# FAMILIAS DE PRODUCTO POR CATEGORIA (title / H1 / meta / intro dinamicos)
# ----------------------------------------------------------------------------
# El stock de Droppers rota: una categoria que hoy es botellas termicas en dos
# meses puede ser escurridores. Un title escrito a mano queda viejo sin que
# nadie lo note. Aca cada categoria declara sus familias posibles como
# (regex sobre el nombre del producto, frase humana). El generador asigna cada
# producto en stock a la PRIMERA familia que matchea (ordenarlas de especifica
# a generica), cuenta, y arma title/H1/meta/intro con las mas presentes.
# Frases de UN concepto (sin " y "), en Title Case porque van al <title>.
# Para agregar una familia nueva: una linea.
# ============================================================================
FAMILIAS = {
    'bazar-y-cocina': [
        (r'vaso|tumbler|jarro', 'Vasos Térmicos'),
        (r't[ée]rmic', 'Botellas Térmicas'),
        (r'botella.*(deportiv|entrenar|gym|hidrataci[oó]n diaria)', 'Botellas Deportivas'),
        (r'botella.*(infantil|ni[ñn]|chicos|kawaii|osito|escuela|cole)', 'Botellas Infantiles'),
        (r'botella', 'Botellas de Agua'),
        (r'escurridor|secaplatos', 'Escurridores de Platos'),
        (r'organizador', 'Organizadores de Cocina'),
        (r'dispenser', 'Dispensers de Jabón'),
        (r'utensil|rallador|cepillo|filtro|cuchill|tabla|pelador|molde', 'Utensilios de Cocina'),
    ],
    'accesorios-de-moda': [
        (r'blusa|camisa', 'Blusas'),
        (r'ri[ñn]onera', 'Riñoneras'),
        (r'bandolera|mini bag', 'Bandoleras'),
        (r'cartera|sobre', 'Carteras'),
        (r'mochila', 'Mochilas'),
        (r'portacosm|neceser', 'Portacosméticos'),
        (r'gorro|piluso|beanie', 'Gorros'),
        (r'poncho|bufanda|mant[oó]n|guante', 'Ponchos y Bufandas'),
    ],
    'articulos-infantiles': [
        (r'\bbody', 'Bodys de Bebé'),
        (r'botella', 'Botellas Infantiles'),
        (r'l[aá]piz|lapicera|bol[ií]grafo|sacapuntas|resaltador|sticker|anotador|cuaderno', 'Útiles Escolares'),
        (r'mochila|bandolerita', 'Mochilas Infantiles'),
        (r'bloques|juguete|armar|rompecabezas|puzzle', 'Juguetes para Armar'),
        (r'\bmedia', 'Medias Divertidas'),
        (r'inflable|flotador', 'Flotadores'),
        (r'pelela|orinal|repelente|pulsera|chupete|babero', 'Accesorios para Bebés'),
    ],
    'verano': [
        (r'bikini|vedetina', 'Bikinis'),
        (r'malla|enteriza|traje de ba', 'Mallas Enterizas'),
        (r'inflable|flotador', 'Inflables de Pileta'),
        (r'lentes|anteojo', 'Anteojos de Sol'),
        (r'sombrero|gorra|visera', 'Sombreros'),
    ],
    'deco': [
        (r'velador', 'Veladores'),
        (r'l[aá]mpara', 'Lámparas LED'),
        (r'tira de luz|tira de luces|luces|guirnalda', 'Tiras de Luces'),
        (r'maceta', 'Macetas'),
        (r'cuadro|espejo|reloj de pared', 'Cuadros y Espejos'),
    ],
    'accesorios-para-mascotas': [
        (r'alfombra', 'Alfombras Absorbentes'),
        (r'collar', 'Collares Isabelinos'),
        (r'cepillo|guante', 'Cepillos'),
        (r'comedero|bebedero', 'Comederos'),
        (r'correa|arn[eé]s', 'Correas'),
    ],
    'home': [
        (r'maceta', 'Macetas Decorativas'),
        (r'l[aá]mpara|velador', 'Lámparas de Escritorio'),
        (r'organizador|estante', 'Organizadores'),
        (r'borde|protector|adhesivo|cinta', 'Protectores para Muebles'),
        (r'vela', 'Velas de Cumpleaños'),
    ],
    'estetica-y-belleza': [
        (r'dilatador|ronquido', 'Dilatadores Nasales Antirronquidos'),
        (r'tap[oó]n', 'Tapones Anti Ruido'),
        (r'depila|strip|cera', 'Accesorios de Depilación'),
        (r'masaje|facial|rodillo|mascarilla', 'Cuidado Facial'),
    ],
    'bano-y-limpieza': [
        (r'escobilla', 'Escobillas de Baño'),
        (r'destapaca|desag[uü]e|ca[ñn]er', 'Destapacaños'),
        (r'sacapelusa|rodillo', 'Rodillos Sacapelusas'),
        (r'organizador|soporte|ducha|toallero|jabonera', 'Organizadores de Baño'),
        (r'trapo|esponja|limpia', 'Artículos de Limpieza'),
    ],
    'electronica': [
        (r'reloj', 'Relojes Infantiles'),
        (r'micr[oó]fono', 'Micrófonos para Celular'),
        (r'auricular|parlante', 'Auriculares'),
        (r'cargador|cable|soporte', 'Accesorios para Celular'),
    ],
    'fitness': [
        (r'mand[ií]bula|mewing', 'Ejercitadores de Mandíbula'),
        (r'botella', 'Botellas Deportivas'),
        (r'postura|faja|lumbar', 'Correctores de Postura'),
        (r'banda|el[aá]stic|pesa|mancuerna|soga', 'Bandas y Pesas'),
    ],
    # 'ofertas' y 'nuevos-ingresos' son mezclas: conservan su title estatico.
}

# Como cierra el title de cada categoria. Dos formas:
#   ' para X'  -> sufijo pegado:            "Bandoleras, Blusas y Carteras de Mujer"
#   'X'        -> ultimo termino de la lista: "Botellas Térmicas, Vasos y Bazar de Cocina"
# Sin entrada: el title son solo las familias ("Escobillas de Baño y Destapacaños").
FAMILIAS_CIERRE = {
    'bazar-y-cocina': 'Bazar de Cocina',
    'accesorios-de-moda': ' de Mujer',
    'articulos-infantiles': 'Regalos para Chicos',
    'deco': ' para Decorar',
    'accesorios-para-mascotas': ' para Mascotas',
    'home': ' para el Hogar',
    'fitness': ' para Entrenar en Casa',
}

# Secciones y FAQs que describen un producto concreto: solo se renderizan si
# algun producto en stock matchea el regex (clave = titulo de la seccion o
# pregunta de la FAQ). Las que no figuran aca son genericas y salen siempre.
SOLO_SI = {
    'bazar-y-cocina': {
        'Escurridores de platos y orden en la mesada': r'escurridor|secaplatos',
        'Utensilios de cocina que se usan de verdad': r'filtro|cepillo|organizador|utensil|rallador',
        '¿Qué escurridor de platos me conviene si tengo poca mesada?': r'escurridor|secaplatos',
    },
    'accesorios-para-mascotas': {
        'Alfombras para el comedero de perros y gatos': r'alfombra',
        'Paseo, viaje y cuidado del pelo': r'comedero|bebedero|cepillo|guante',
        'Comedero para perros: la dupla con la alfombra': r'comedero',
        '¿Las alfombras para mascotas sirven para perros y gatos?': r'alfombra',
    },
    'deco': {
        'Espejos decorativos y detalles con luz': r'espejos?',
        'Decoración de living: tres movidas seguras': r'espejo',
        '¿Qué me conviene para renovar un ambiente con poco presupuesto?': r'espejo',
    },
    'bano-y-limpieza': {
        'Seguridad en la ducha: alfombras antideslizantes': r'alfombr',
        'Orden y limpieza sin esfuerzo': r'jabonera|estante|organizador|limpia|escobilla',
        '¿Las alfombras de baño son antideslizantes de verdad?': r'alfombr',
    },
    'articulos-infantiles': {
        'Juguetes didácticos para jugar y aprender': r'pop it|anotador|juguete|bloques|armar',
        'Para bebés: cambiadores, baberos y más': r'cambiador|babero',
        '¿Los juguetes son seguros para bebés?': r'juguete|bloques|armar',
    },
    'accesorios-de-moda': {
        'Bandoleras de mujer: tejidas, transparentes y urbanas': r'bandolera',
        'Riñoneras y carteras para cada plan': r'ri[ñn]onera',
        'Carteras de mujer: cómo elegir la tuya': r'cartera|bandolera',
        '¿Qué diferencia hay entre bandolera y riñonera?': r'ri[ñn]onera',
        '¿Puedo cambiar una cartera si no me convence?': r'cartera|bandolera',
    },
    'verano': {
        'Mallas y trajes de baño': r'malla|bikini|enteriza|vedetina',
        'Inflables y juegos de pileta': r'inflable|flotador',
    },
}

TITLE_MAX = 60  # sin el " | El Gadget"


def _unir(frases):
    """'A, B y C' — con 'e' antes de una palabra que empieza con i/hi."""
    frases = [f for f in frases if f]
    if not frases:
        return ''
    if len(frases) == 1:
        return frases[0]
    ult = frases[-1]
    conj = ' e ' if ult.lower().startswith(('i', 'hi')) else ' y '
    return ', '.join(frases[:-1]) + conj + ult


def _minus(frase):
    """Pasa una frase de familia a minúsculas conservando siglas (LED, USB)."""
    return ' '.join(w if w.isupper() and len(w) <= 4 else w.lower() for w in frase.split())


def _agrupar(frases):
    """Junta familias que comparten la primera palabra para no repetirla en
    el title: 'Botellas Infantiles' + 'Botellas Térmicas' -> 'Botellas
    Infantiles y Térmicas'. Máximo 2 por cabeza; una tercera se descarta."""
    grupos = []
    for f in frases:
        cab = f.split()[0]
        g = next((g for g in grupos if g[0] == cab), None)
        if g is None:
            grupos.append([cab, [f]])
        elif len(g[1]) < 2:
            g[1].append(f)
    out = []
    for cab, fs in grupos:
        if len(fs) == 1:
            out.append(fs[0])
            continue
        resto = fs[1].split(' ', 1)[1] if ' ' in fs[1] else fs[1]
        conj = 'e' if resto.lower().startswith(('i', 'hi')) else 'y'
        out.append(f"{fs[0]} {conj} {resto}")
    return out


def _armar(elegidas, cierre):
    """Title sin marca a partir de las familias elegidas + el cierre."""
    if cierre.startswith(' '):
        return _unir(elegidas) + cierre
    titulo = _unir(elegidas + [cierre]) if cierre else _unir(elegidas)
    # "Botellas Infantiles y Térmicas y Bazar de Cocina" -> coma en el grupo
    if len(elegidas) == 1 and cierre and ' y ' in elegidas[0]:
        titulo = elegidas[0].replace(' y ', ', ', 1) + titulo[len(elegidas[0]):]
    return titulo


def familias_presentes(slug, productos):
    """[(frase, cantidad)] de las familias con stock, de mayor a menor.
    Cada producto cuenta para la primera familia que matchea su nombre."""
    familias = FAMILIAS.get(slug) or []
    conteo = [0] * len(familias)
    for p in productos:
        nombre = p.get('nombre') or ''
        for i, (rx, _) in enumerate(familias):
            if re.search(rx, nombre, re.I):
                conteo[i] += 1
                break
    orden = sorted((-n, i) for i, n in enumerate(conteo) if n)
    return [(familias[i][1], -n) for n, i in orden]


def resolver_categoria(slug, cfg, productos):
    """Devuelve una copia de cfg con title/h1/meta/intro derivados del stock
    real, y con secciones/faqs filtradas por `solo_si` (tercer elemento
    opcional: regex que algun producto en stock tiene que matchear para que
    la seccion/FAQ se renderice). Sin FAMILIAS o sin matches, deja el copy
    estatico tal cual."""
    nuevo = dict(cfg)
    nombres = [(p.get('nombre') or '') for p in productos]

    def filtrar(items):
        out = []
        for it in items or []:
            rx = it[2] if len(it) >= 3 else SOLO_SI.get(slug, {}).get(it[0])
            if rx and not any(re.search(rx, n, re.I) for n in nombres):
                continue
            out.append(tuple(it[:2]))
        return out
    nuevo['secciones'] = filtrar(cfg.get('secciones'))
    nuevo['faqs'] = filtrar(cfg.get('faqs'))

    presentes = familias_presentes(slug, productos)
    if not presentes:
        return nuevo
    cierre = FAMILIAS_CIERRE.get(slug, '')
    elegidas = _agrupar([f for f, _ in presentes])[:3]
    # recortar familias hasta que el title entre en 60 caracteres
    while len(elegidas) > 1 and len(_armar(elegidas, cierre)) > TITLE_MAX:
        elegidas.pop()
    titulo = _armar(elegidas, cierre)
    frase_min = _unir([_minus(f) for f in elegidas])
    total = len(nombres)
    plural = 's' if total != 1 else ''
    nuevo['title'] = f"{titulo} | El Gadget"
    nuevo['h1'] = titulo
    nuevo['meta'] = (f"Comprá {_minus(titulo)} online con envío a todo el país. "
                     f"{total} producto{plural} con fotos reales, pagás seguro con Mercado Pago y lo recibís en tu casa.")
    nuevo['intro'] = (f"Hoy tenemos {total} producto{plural} en esta categoría, sobre todo {frase_min}, "
                      "elegidos por su relación precio-calidad y con fotos reales en cada ficha. "
                      "Comprás online, pagás seguro con Mercado Pago y te lo enviamos a todo el país.")
    return nuevo
