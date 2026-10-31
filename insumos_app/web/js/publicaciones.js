/* ============================================================
   INSUMOS — ASÍ FUE DECO · PUBLICACIONES (mapeo de canal)

   Qué publicación de qué canal corresponde a qué artículo. Sin esto, una
   venta de Mercado Libre no sabe qué descontar y queda pendiente.

   UN ARTÍCULO PUEDE TENER VARIAS PUBLICACIONES, Y ES UN CASO REAL: el socio
   tiene productos publicados más de una vez en la misma cuenta de Mercado
   Libre, con ventas en las dos. Por eso esto es una LISTA con un botón de
   agregar y uno de quitar por fila, y no un campo único: un campo único
   obligaría a elegir cuál de las dos publicaciones registrar, y las ventas
   de la otra quedarían sin descontar.

   La asimetría del backend es deliberada y la pantalla la explica: varias
   publicaciones pueden apuntar al mismo artículo, pero una publicación no
   puede apuntar a dos artículos (devuelve 409), porque una venta no sabría
   cuál de los dos descontar.

   PRECEDENCIA DE VARIANTES. Una fila sin variante es un COMODÍN que cubre
   todas; una fila con variante le gana al comodín para esa variante. Cargar
   las dos es legítimo pero confunde, así que `POST /api/mapeos` devuelve
   `avisos` explicando quién gana y acá se muestran enteros.
   ============================================================ */

const CANALES_MAPEABLES = [
  ['ml', 'Mercado Libre'],
  ['elgadget', 'El Gadget'],
  ['empretienda', 'Empretienda'],
];

/* ── Dentro de la ficha de un artículo ────────────────────── */

function pintarPublicacionesDeArticulo(hoja, a) {
  const caja = hoja.cuerpo.querySelector('#ar-publicaciones');
  const mapeos = a.mapeos || [];

  caja.innerHTML = `
    <div class="bloque-titulo">Publicaciones</div>
    <div class="ayuda">
      Una fila por publicación. <strong>Un artículo puede tener varias</strong> — incluso dos
      en la misma cuenta de Mercado Libre: las ventas de las dos descuentan stock de este
      artículo.
    </div>

    <div id="ar-pub-lista" style="margin-top:12px">
      ${mapeos.length ? mapeos.map(filaPublicacion).join('') : `
        <div class="aviso neutro" style="margin-bottom:0">
          <strong>Sin publicaciones mapeadas</strong>
          Para Mercado Libre el mapeo es obligatorio: su <code>item_id</code> no se parece a
          ningún SKU. El Gadget y Empretienda tienen respaldo por SKU, así que ahí el mapeo
          es opcional.
        </div>`}
    </div>

    <div class="pub-alta">
      <div class="campo">
        <label for="pub-canal">Canal</label>
        <select id="pub-canal">
          ${CANALES_MAPEABLES.map(([v, t]) => `<option value="${v}">${t}</option>`).join('')}
        </select>
      </div>
      <div class="campo">
        <label for="pub-id">ID de la publicación</label>
        <input type="text" id="pub-id" placeholder="MLA1234567890" autocomplete="off">
        <div class="pie">
          Es el id de la <strong>publicación</strong> (el <code>item_id</code> de Mercado
          Libre), no el de una orden. En El Gadget y Empretienda, el SKU.
        </div>
      </div>
      <div class="campo">
        <label for="pub-variacion">Variación <span class="opt">· opcional</span></label>
        <input type="text" id="pub-variacion" placeholder="Vacío = cubre todas las variantes" autocomplete="off">
        <div class="pie">
          Dejalo vacío para un <strong>comodín</strong> que cubra todas las variantes de esa
          publicación. Cargá una fila por variante solo si las variantes son artículos
          distintos (otro color con otros insumos, por ejemplo).
        </div>
      </div>
      <button class="btn btn-bloque" id="pub-agregar">${icono('mas')} Agregar publicación</button>
    </div>`;

  caja.querySelectorAll('[data-quitar-pub]').forEach((b) => {
    b.addEventListener('click', () => quitarPublicacion(
      Number(b.dataset.quitarPub), b.dataset.descripcion, () => recargarPublicacionesDe(hoja, a)));
  });
  caja.querySelector('#pub-agregar').addEventListener('click', (e) =>
    agregarPublicacion(hoja, a, e.currentTarget));
}

function filaPublicacion(m) {
  const descripcion = `${nombreCanal(m.canal)} · ${m.id_externo}` +
    (m.variacion_externa ? ` · ${m.variacion_externa}` : '');
  return `
    <div class="pub-fila">
      <div class="pub-datos">
        <div class="pub-id">${esc(m.id_externo)}</div>
        <div class="pub-meta">
          ${esc(nombreCanal(m.canal))} ·
          ${m.variacion_externa
            ? `variación <strong>${esc(m.variacion_externa)}</strong>`
            : 'comodín: cubre todas las variantes'}
        </div>
      </div>
      <button class="receta-quitar" data-quitar-pub="${m.id}"
              data-descripcion="${esc(descripcion)}" aria-label="Quitar publicación">
        ${icono('menos')}
      </button>
    </div>`;
}

async function recargarPublicacionesDe(hoja, a) {
  try {
    a.mapeos = await API.get('/mapeos', { articulo_id: a.id });
    pintarPublicacionesDeArticulo(hoja, a);
  } catch (e) {
    globo('No se pudo recargar la lista: ' + e.message, 'mal');
  }
}

async function agregarPublicacion(hoja, a, boton) {
  const q = (sel) => hoja.cuerpo.querySelector(sel);
  const idExterno = q('#pub-id').value.trim();
  if (!idExterno) { globo('Falta el ID de la publicación.', 'mal'); q('#pub-id').focus(); return; }

  boton.disabled = true;
  try {
    const r = await API.post('/mapeos', {
      articulo_id: a.id,
      canal: q('#pub-canal').value,
      id_externo: idExterno,
      variacion_externa: q('#pub-variacion').value.trim(),
    });
    await recargarPublicacionesDe(hoja, a);

    if (r.avisos && r.avisos.length) {
      abrirHoja({
        titulo: 'Publicación agregada',
        cuerpo: listaAvisos(r.avisos) + `<div class="ayuda">
          Está bien tener las dos filas: la precedencia está definida y gana la específica
          para su variante. El aviso es para que sepas cuál gana.</div>`,
        acciones: [{ texto: 'Entendido', clase: 'btn', alTocar: (h) => volverAtras(h) }],
      });
    } else {
      globo('Publicación agregada.');
    }
  } catch (e) {
    // El 409 más probable: esa publicación ya apunta a otro artículo.
    abrirHoja({
      titulo: 'No se pudo agregar',
      cuerpo: `<div class="aviso malo"><strong>${esc(idExterno)}</strong>${esc(e.message)}</div>
        <div class="ayuda">
          Si esa publicación ya está mapeada a otro artículo, el sistema no la deja apuntar a
          dos: una venta no sabría cuál descontar. Quitá el mapeo del otro artículo o revisá
          el ID. Lo que sí se puede es lo inverso: <strong>varias publicaciones hacia este
          mismo artículo</strong>.
        </div>`,
      acciones: [{ texto: 'Entendido', clase: 'btn', alTocar: (h) => volverAtras(h) }],
    });
  } finally {
    boton.disabled = false;
  }
}

async function quitarPublicacion(mapeoId, descripcion, alTerminar) {
  if (!await confirmar(
    `Se desvincula <strong>${esc(descripcion)}</strong>. Las ventas que lleguen por esa ` +
    'publicación van a quedar <strong>pendientes de mapeo</strong> y no van a descontar ' +
    'stock hasta que se vuelva a mapear. Lo ya descontado no se toca.',
    { titulo: '¿Quitar la publicación?', textoSi: 'Quitar' })) return;

  try {
    await API.borrar(`/mapeos/${mapeoId}`);
    globo('Publicación desvinculada.');
    if (alTerminar) await alTerminar();
  } catch (e) {
    globo('No se pudo quitar: ' + e.message, 'mal');
  }
}

/* ── Pantalla propia: todas las publicaciones ─────────────── */

const Publicaciones = { canal: '' };

async function cargarPublicaciones() {
  const caja = el('p-publicaciones');
  caja.innerHTML = `
    <div class="ayuda" style="margin-bottom:12px">
      Vista completa de los mapeos. Para agregar o quitar, entrá al artículo: las
      publicaciones se administran en su ficha, donde se ve a qué artículo pertenecen.
    </div>
    <div class="filtros">
      <select id="pub-filtro-canal" aria-label="Canal">
        <option value="">Todos los canales</option>
        ${CANALES_MAPEABLES.map(([v, t]) => `<option value="${v}">${t}</option>`).join('')}
      </select>
    </div>
    <div id="lista-publicaciones">${cargando()}</div>`;

  const filtro = el('pub-filtro-canal');
  filtro.value = Publicaciones.canal;
  filtro.addEventListener('change', () => {
    Publicaciones.canal = filtro.value;
    pintarListaPublicaciones();
  });

  pintarListaPublicaciones();
}

async function pintarListaPublicaciones() {
  const caja = el('lista-publicaciones');
  if (!caja) return;
  caja.innerHTML = cargando();

  try {
    const mapeos = await API.get('/mapeos', { canal: Publicaciones.canal || undefined });
    if (!mapeos.length) {
      caja.innerHTML = vacio('Sin publicaciones mapeadas',
        '<div class="ayuda" style="margin-top:6px">Entrá a un artículo y agregale sus publicaciones.</div>');
      return;
    }

    // Agrupadas por artículo: así se ve de un saque cuáles tienen más de una
    // publicación, que es el caso que hay que poder leer sin esfuerzo.
    const porArticulo = new Map();
    mapeos.forEach((m) => {
      if (!porArticulo.has(m.articulo_id)) porArticulo.set(m.articulo_id, []);
      porArticulo.get(m.articulo_id).push(m);
    });

    const bloques = [...porArticulo.entries()].map(([articuloId, filas]) => `
      <div class="tarjeta">
        <div class="item-fila" style="align-items:center;margin-bottom:8px">
          <div class="item-cuerpo">
            <div class="item-nombre">${esc(filas[0].articulo)}</div>
            <div class="item-sub">${filas.length} publicación(es)</div>
          </div>
          <button class="btn btn-borde btn-ch" data-ver-articulo="${articuloId}">Abrir</button>
        </div>
        ${filas.map((m) => `
          <div class="pub-fila">
            <div class="pub-datos">
              <div class="pub-id">${esc(m.id_externo)}</div>
              <div class="pub-meta">
                ${esc(nombreCanal(m.canal))} ·
                ${m.variacion_externa
                  ? `variación <strong>${esc(m.variacion_externa)}</strong>`
                  : 'comodín: todas las variantes'}
              </div>
            </div>
          </div>`).join('')}
      </div>`).join('');

    const conVarias = [...porArticulo.values()].filter((f) => f.length > 1).length;
    caja.innerHTML = `
      ${conVarias ? `<div class="aviso bueno">
        <strong>${conVarias} artículo(s) tienen más de una publicación</strong>
        Es lo esperado: un producto publicado dos veces en la misma cuenta descuenta stock
        por las dos, porque la idempotencia es por orden y no por publicación.
      </div>` : ''}
      ${bloques}`;

    caja.querySelectorAll('[data-ver-articulo]').forEach((b) => {
      b.addEventListener('click', () => abrirFichaArticulo(Number(b.dataset.verArticulo)));
    });
  } catch (e) {
    if (e instanceof ErrorAuth) { pedirIngreso(e.message); return; }
    caja.innerHTML = errorEnPantalla(e, 'pintarListaPublicaciones()');
  }
}
