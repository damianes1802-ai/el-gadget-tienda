/* ============================================================
   INSUMOS — ASÍ FUE DECO · ARTÍCULOS, RECETA Y PESO DE ENVÍO

   Es la pantalla por la que existe el sistema: de la receta sale el peso del
   paquete, y de ese peso sale lo que El Gadget le cobra al cliente por el
   envío de Correo Argentino.

   TRES DECISIONES DE PANTALLA

   1. EL PESO SE MUESTRA EN VIVO, Y LO CALCULA EL SERVIDOR. Cada cambio de
      la receta se guarda al instante y el endpoint devuelve la receta nueva
      JUNTO CON el envío recalculado, así que el panel de arriba se actualiza
      con el número autoritativo sin que la interfaz repita la fórmula. Si el
      peso se calculara también acá, algún día los dos números iban a
      discrepar y el que miente sería el de la pantalla — el mismo motivo por
      el que la lógica de campañas de El Gadget vive en un solo lado.

   2. LOS CAMPOS DEL ARTÍCULO (medidas, margen) NO SE GUARDAN SOLOS, porque
      una medida a medio tipear no es una medida. Mientras haya cambios sin
      guardar, el panel de envío queda marcado con un borde punteado y lo
      dice: el número que se ve es el del artículo guardado, no el de lo que
      está en pantalla.

   3. SIN RECETA NO SE MUESTRA NINGÚN PESO. El backend devuelve
      `receta_incompleta: true` y un peso de 0, y un 0 que parece un peso
      hace cotizar un envío gratis. El panel muestra el problema, no el cero.
   ============================================================ */

const Articulos = { texto: '', sinReceta: false, incluirInactivos: false, todos: [] };

async function cargarArticulos() {
  const caja = el('p-articulos');
  caja.innerHTML = `
    <div class="seccion-cabecera">
      <h2>Artículos</h2>
      <button class="btn btn-ch" id="nuevo-articulo">${icono('mas')} Nuevo</button>
    </div>

    <div class="buscador">
      ${icono('lupa', 'lupa')}
      <input type="search" id="buscar-articulo" placeholder="Buscar por nombre o SKU…"
             autocomplete="off" value="${esc(Articulos.texto)}">
      <button class="limpiar oculto" id="limpiar-articulo" aria-label="Limpiar">${icono('cruz')}</button>
    </div>

    <div class="filtros" style="margin-bottom:14px">
      <button class="btn btn-borde btn-ch" id="a-filtro-receta" style="flex:1">Solo sin receta</button>
      <button class="btn btn-borde btn-ch" id="a-filtro-inactivos" style="flex:1">Ver inactivos</button>
    </div>

    <div id="articulos-resumen" class="ayuda" style="margin-bottom:10px"></div>
    <div class="lista doble" id="lista-articulos">${cargando()}</div>`;

  el('nuevo-articulo').addEventListener('click', abrirArticuloNuevo);

  const buscar = el('buscar-articulo');
  const limpiar = el('limpiar-articulo');
  buscar.addEventListener('input', demorar(() => {
    Articulos.texto = buscar.value.trim();
    limpiar.classList.toggle('oculto', !Articulos.texto);
    pintarArticulos();
  }, 160));
  limpiar.addEventListener('click', () => {
    buscar.value = ''; Articulos.texto = '';
    limpiar.classList.add('oculto'); pintarArticulos(); buscar.focus();
  });
  limpiar.classList.toggle('oculto', !Articulos.texto);

  el('a-filtro-receta').addEventListener('click', () => {
    Articulos.sinReceta = !Articulos.sinReceta;
    marcarFiltro('a-filtro-receta', Articulos.sinReceta);
    pintarArticulos();
  });
  el('a-filtro-inactivos').addEventListener('click', async () => {
    Articulos.incluirInactivos = !Articulos.incluirInactivos;
    marcarFiltro('a-filtro-inactivos', Articulos.incluirInactivos);
    await traerArticulos();
    pintarArticulos();
  });
  marcarFiltro('a-filtro-receta', Articulos.sinReceta);
  marcarFiltro('a-filtro-inactivos', Articulos.incluirInactivos);

  try {
    await traerArticulos();
    pintarArticulos();
  } catch (e) {
    if (e instanceof ErrorAuth) { pedirIngreso(e.message); return; }
    el('lista-articulos').innerHTML = errorEnPantalla(e, 'cargarArticulos()');
  }
}

async function traerArticulos() {
  Articulos.todos = await API.get('/articulos',
    Articulos.incluirInactivos ? {} : { activo: true });
}

/** Atajo desde la pantalla de alertas. */
function filtrarArticulosSinReceta() {
  Articulos.sinReceta = true;
  setTimeout(() => {
    marcarFiltro('a-filtro-receta', true);
    pintarArticulos();
  }, 60);
}

function pintarArticulos() {
  const lista = el('lista-articulos');
  if (!lista) return;
  const texto = Articulos.texto.toLowerCase();

  const items = Articulos.todos.filter((a) => {
    if (Articulos.sinReceta && !a.envio.receta_incompleta) return false;
    if (!texto) return true;
    return [a.nombre, a.sku_afd, a.sku_elgadget, a.id_empretienda]
      .filter(Boolean).some((v) => String(v).toLowerCase().includes(texto));
  });

  el('articulos-resumen').textContent = items.length === Articulos.todos.length
    ? `${items.length} artículo${items.length === 1 ? '' : 's'}`
    : `${items.length} de ${Articulos.todos.length} artículos`;

  if (!items.length) {
    lista.innerHTML = vacio(
      Articulos.todos.length ? 'Ningún artículo coincide' : 'Todavía no hay artículos',
      '<div class="ayuda" style="margin-top:6px">Un artículo es lo que se vende: una borla, un servilletero, una guirnalda. Su receta dice qué insumos lleva, y de ahí sale el peso del envío.</div>');
    return;
  }

  lista.innerHTML = items.map(filaArticulo).join('');
  lista.querySelectorAll('[data-articulo]').forEach((b) => {
    b.addEventListener('click', () => abrirFichaArticulo(Number(b.dataset.articulo)));
  });
}

function filaArticulo(a) {
  const falta = a.envio.receta_incompleta;
  const skus = [a.sku_elgadget, a.sku_afd, a.id_empretienda].filter(Boolean).join(' · ');
  return `
    <button class="item ${falta ? 'tibio' : 'ok'} ${a.activo ? '' : 'apagado'}" data-articulo="${a.id}">
      <div class="item-fila">
        <div class="item-cuerpo">
          <div class="item-nombre">${esc(a.nombre)}</div>
          <div class="item-sub">${esc(skus || 'Sin SKU')}</div>
        </div>
        <div class="item-derecha">
          ${falta
            ? '<div class="item-numero" style="font-size:14px;color:var(--orange)">sin peso</div>'
            : `<div class="item-numero">${fmtCant(a.envio.peso_envio_g)}<small> g</small></div>
               <div class="item-sub">${fmtCant(a.envio.largo_envio_cm)}×${fmtCant(a.envio.ancho_envio_cm)}×${fmtCant(a.envio.alto_envio_cm)} cm</div>`}
        </div>
      </div>
      <div class="item-pie">
        ${falta ? '<span class="insignia naranja">Falta la receta</span>'
                : `<span class="insignia verde">${a.envio.insumos_en_receta} insumo(s)</span>`}
        ${a.se_embala_doblado ? '<span class="insignia oscura">Se embala doblado</span>' : ''}
        ${a.activo ? '' : '<span class="insignia">Inactivo</span>'}
      </div>
    </button>`;
}

/* ── Alta de artículo ─────────────────────────────────────────

   Nace sin receta: no se le puede pedir la receta antes de que exista,
   porque las líneas de receta necesitan el id del artículo. Así que el alta
   pide lo mínimo obligatorio y después abre la ficha, que es donde está el
   editor de receta y el peso en vivo. */

function abrirArticuloNuevo() {
  const hoja = abrirHoja({
    titulo: 'Nuevo artículo',
    cuerpo: `
      <div class="campo">
        <label for="na-nombre">Nombre</label>
        <input type="text" id="na-nombre" placeholder="Guirnalda de caireles 2 m"
               autocomplete="off" autofocus>
      </div>

      <div class="campo">
        <label>Medidas reales del producto <span class="opt">· las tres, obligatorias</span></label>
        <div class="rejilla-3">
          <div class="campo"><label for="na-largo" style="font-size:11px">Largo mm</label>
            <input type="text" id="na-largo" inputmode="decimal" placeholder="2000"></div>
          <div class="campo"><label for="na-ancho" style="font-size:11px">Ancho mm</label>
            <input type="text" id="na-ancho" inputmode="decimal" placeholder="60"></div>
          <div class="campo"><label for="na-alto" style="font-size:11px">Alto mm</label>
            <input type="text" id="na-alto" inputmode="decimal" placeholder="20"></div>
        </div>
        <div class="pie">
          Las tres hacen falta: Correo Argentino cotiza con peso volumétrico y con topes de
          tamaño, y con dos medidas no se puede cotizar. Son las del producto estirado; si se
          embala doblado, eso se carga aparte en la ficha.
        </div>
      </div>

      <div class="ayuda">
        El artículo nace sin receta. Después de crearlo se abre su ficha, que es donde se
        cargan los insumos y aparece el peso de envío.
      </div>`,
    acciones: [
      { texto: 'Cancelar', clase: 'btn-borde', alTocar: (h) => volverAtras(h) },
      { texto: 'Crear', clase: 'btn', alTocar: (h, b) => crearArticulo(h, b) },
    ],
  });
  setTimeout(() => hoja.cuerpo.querySelector('#na-nombre').focus(), 100);
}

async function crearArticulo(hoja, boton) {
  const q = (sel) => hoja.cuerpo.querySelector(sel);
  const nombre = q('#na-nombre').value.trim();
  const largo = num(q('#na-largo').value);
  const ancho = num(q('#na-ancho').value);
  const alto = num(q('#na-alto').value);

  if (!nombre) { globo('Falta el nombre.', 'mal'); q('#na-nombre').focus(); return; }
  for (const [valor, campo] of [[largo, '#na-largo'], [ancho, '#na-ancho'], [alto, '#na-alto']]) {
    if (!isFinite(valor) || valor <= 0) {
      globo('Las tres medidas son obligatorias y mayores que cero.', 'mal');
      q(campo).focus();
      return;
    }
  }

  boton.disabled = true;
  boton.textContent = 'Creando…';
  try {
    const a = await API.post('/articulos', {
      nombre, largo_real_mm: largo, ancho_real_mm: ancho, alto_real_mm: alto,
    });
    Cache.invalidar('articulos');
    volverAtras(hoja);
    recargarPantalla();
    abrirFichaArticulo(a.id);
    globo('Artículo creado. Ahora cargale la receta.');
  } catch (e) {
    globo('No se pudo crear: ' + e.message, 'mal');
  } finally {
    boton.disabled = false;
    boton.textContent = 'Crear';
  }
}

/* ── Ficha de artículo: datos + receta + publicaciones ────── */

async function abrirFichaArticulo(id) {
  const hoja = abrirHoja({ titulo: 'Artículo', cuerpo: cargando() });
  try {
    const a = await API.get(`/articulos/${id}`);
    hoja.el.querySelector('.hoja-top h2').innerHTML =
      `${esc(a.nombre)}<br><span style="font-size:11.5px;font-weight:600;color:var(--gray-600)">Receta, medidas y peso de envío</span>`;

    hoja.cuerpo.innerHTML = `
      <div id="ar-envio">${panelEnvio(a.envio)}</div>

      <div class="tarjeta">
        <div class="bloque-titulo">Receta</div>
        <div class="ayuda">
          Qué insumos lleva y cuántas <strong>unidades</strong> de cada uno. Se guarda al
          instante y el peso de arriba se actualiza con cada cambio.
        </div>
        <div id="ar-receta" style="margin-top:12px"></div>
        <button class="btn btn-borde btn-bloque" id="ar-agregar" style="margin-top:12px">
          ${icono('mas')} Agregar insumo
        </button>
      </div>

      <div class="tarjeta" id="ar-publicaciones"></div>

      <div class="tarjeta">
        <div class="bloque-titulo">Datos del artículo</div>
        <div class="ayuda">Estos campos se guardan con el botón de abajo.</div>
        <div id="ar-form" style="margin-top:14px"></div>
        <button class="btn btn-bloque" id="ar-guardar" style="margin-top:4px">Guardar datos</button>
      </div>

      <button class="btn btn-borde btn-bloque" id="ar-desactivar" style="color:var(--red)">
        ${a.activo ? 'Desactivar artículo' : 'Volver a activar'}
      </button>`;

    hoja.cuerpo.querySelector('#ar-form').innerHTML = formularioArticuloHTML(a);
    pintarReceta(hoja, a);
    pintarPublicacionesDeArticulo(hoja, a);
    engancharFormularioArticulo(hoja, a);

    hoja.cuerpo.querySelector('#ar-agregar').addEventListener('click', () => {
      const yaEstan = (a.receta || []).map((r) => r.insumo_id);
      elegirInsumo((insumo) => agregarLineaReceta(hoja, a, insumo), {
        titulo: 'Agregar a la receta',
        excluir: yaEstan,
      });
    });
    hoja.cuerpo.querySelector('#ar-guardar').addEventListener('click', (e) =>
      guardarDatosArticulo(hoja, a, e.currentTarget));
    hoja.cuerpo.querySelector('#ar-desactivar').addEventListener('click', () =>
      cambiarActivoArticulo(a, hoja));
  } catch (e) {
    hoja.cuerpo.innerHTML = errorEnPantalla(e);
  }
}

function formularioArticuloHTML(a) {
  return `
    <div class="campo">
      <label for="ar-nombre">Nombre</label>
      <input type="text" id="ar-nombre" value="${esc(a.nombre)}" autocomplete="off">
    </div>

    <div class="campo">
      <label>Medidas reales del producto <span class="opt">· en mm</span></label>
      <div class="rejilla-3">
        <div class="campo"><label for="ar-largo" style="font-size:11px">Largo</label>
          <input type="text" id="ar-largo" inputmode="decimal" value="${esc(a.largo_real_mm)}"></div>
        <div class="campo"><label for="ar-ancho" style="font-size:11px">Ancho</label>
          <input type="text" id="ar-ancho" inputmode="decimal" value="${esc(a.ancho_real_mm)}"></div>
        <div class="campo"><label for="ar-alto" style="font-size:11px">Alto</label>
          <input type="text" id="ar-alto" inputmode="decimal" value="${esc(a.alto_real_mm)}"></div>
      </div>
      <div class="pie">Las del producto como es, estirado. Sirven para la ficha y para el cliente.</div>
    </div>

    <label class="casilla" id="ar-doblado-caja" style="margin-bottom:14px">
      <input type="checkbox" id="ar-doblado" ${a.se_embala_doblado ? 'checked' : ''}>
      <span class="casilla-texto">
        <b>SE EMBALA DOBLADO</b>
        <span>Marcalo si el paquete no tiene las medidas del producto: una guirnalda de 2 m
        doblada en cinco viaja en un cuadrado de 25×25. El envío se cotiza con las medidas
        del paquete, no con las del producto.</span>
      </span>
    </label>

    <div class="campo ${a.se_embala_doblado ? '' : 'oculto'}" id="ar-emb">
      <label>Medidas del paquete doblado <span class="opt">· las tres, en mm</span></label>
      <div class="rejilla-3">
        <div class="campo"><label for="ar-elargo" style="font-size:11px">Largo</label>
          <input type="text" id="ar-elargo" inputmode="decimal" value="${a.largo_emb_mm !== null && a.largo_emb_mm !== undefined ? esc(a.largo_emb_mm) : ''}" placeholder="250"></div>
        <div class="campo"><label for="ar-eancho" style="font-size:11px">Ancho</label>
          <input type="text" id="ar-eancho" inputmode="decimal" value="${a.ancho_emb_mm !== null && a.ancho_emb_mm !== undefined ? esc(a.ancho_emb_mm) : ''}" placeholder="250"></div>
        <div class="campo"><label for="ar-ealto" style="font-size:11px">Alto</label>
          <input type="text" id="ar-ealto" inputmode="decimal" value="${a.alto_emb_mm !== null && a.alto_emb_mm !== undefined ? esc(a.alto_emb_mm) : ''}" placeholder="60"></div>
      </div>
      <div class="pie">Mientras esté marcada la casilla, estas tres son las que cotizan el envío.</div>
    </div>

    <div class="rejilla-2" style="margin-bottom:14px">
      <div class="campo">
        <label for="ar-sku-eg">SKU El Gadget</label>
        <input type="text" id="ar-sku-eg" value="${esc(a.sku_elgadget || '')}" placeholder="AFD-21" autocomplete="off">
      </div>
      <div class="campo">
        <label for="ar-sku-afd">SKU Así Fue Deco</label>
        <input type="text" id="ar-sku-afd" value="${esc(a.sku_afd || '')}" placeholder="GUIR-2M" autocomplete="off">
      </div>
    </div>

    <div class="rejilla-2" style="margin-bottom:14px">
      <div class="campo">
        <label for="ar-empre">ID Empretienda</label>
        <input type="text" id="ar-empre" value="${esc(a.id_empretienda || '')}" autocomplete="off">
      </div>
      <div class="campo">
        <label for="ar-margen">Margen de embalaje</label>
        <input type="text" id="ar-margen" inputmode="decimal" value="${esc(a.margen_embalaje)}">
      </div>
    </div>

    <div class="ayuda" style="margin-bottom:14px">
      El margen se aplica a cada dimensión y al peso. Ojo que
      <strong>1,05 por dimensión infla el volumen 15,8 %</strong>, no 5 % (1,05³ = 1,158);
      el factor que da 5 % de volumen es 1,016. Importa porque Correo cobra por peso
      volumétrico cuando el paquete es liviano y voluminoso, que es el caso de una guirnalda.
      <button class="btn btn-borde btn-ch" id="ar-simular" style="margin-top:8px">
        Simular con otro margen
      </button>
    </div>

    <div class="campo">
      <label for="ar-sku-eg-nota" style="font-weight:500;color:var(--gray-600);font-size:11.5px">
        El SKU de El Gadget es lo que usa el cotizador del checkout
        (<code>GET /api/envio?sku_elgadget=…</code>). Sin ese SKU cargado, el checkout no
        encuentra el peso de este artículo.
      </label>
    </div>`;
}

function engancharFormularioArticulo(hoja, a) {
  const q = (sel) => hoja.cuerpo.querySelector(sel);
  const doblado = q('#ar-doblado');

  marcarCasilla(doblado);
  doblado.addEventListener('change', () => {
    q('#ar-emb').classList.toggle('oculto', !doblado.checked);
    marcarPendiente(hoja, a);
  });

  // Cualquier cambio de un campo que afecte el envío marca el panel como
  // "pendiente de guardar": el número de arriba es el del artículo guardado,
  // no el de lo que hay escrito en pantalla.
  ['#ar-largo', '#ar-ancho', '#ar-alto', '#ar-elargo', '#ar-eancho', '#ar-ealto', '#ar-margen']
    .forEach((sel) => {
      const campo = q(sel);
      if (campo) campo.addEventListener('input', () => marcarPendiente(hoja, a));
    });

  q('#ar-simular').addEventListener('click', () => simularMargen(a));
}

function marcarPendiente(hoja, a) {
  const panel = hoja.cuerpo.querySelector('#ar-envio');
  if (panel.querySelector('.pendiente-guardar')) return;
  panel.innerHTML = panelEnvio(a.envio, { pendienteGuardar: true }) +
    `<div class="aviso atencion" style="margin-top:-6px">
       <strong>Tocaste medidas o margen y todavía no guardaste</strong>
       El peso y las medidas de arriba son los del artículo <strong>guardado</strong>.
       Guardá los datos para recalcularlos.
     </div>`;
}

async function guardarDatosArticulo(hoja, a, boton) {
  const q = (sel) => hoja.cuerpo.querySelector(sel);
  const nombre = q('#ar-nombre').value.trim();
  if (!nombre) { globo('Falta el nombre.', 'mal'); return; }

  const medida = (sel) => num(q(sel).value);
  const reales = [medida('#ar-largo'), medida('#ar-ancho'), medida('#ar-alto')];
  if (reales.some((v) => !isFinite(v) || v <= 0)) {
    globo('Las tres medidas reales son obligatorias y mayores que cero.', 'mal');
    return;
  }

  const doblado = q('#ar-doblado').checked;
  const embaladas = [medida('#ar-elargo'), medida('#ar-eancho'), medida('#ar-ealto')];
  if (doblado && embaladas.some((v) => !isFinite(v) || v <= 0)) {
    globo('Si se embala doblado, hacen falta las tres medidas del paquete.', 'mal');
    q('#ar-elargo').focus();
    return;
  }

  const margen = num(q('#ar-margen').value);
  if (!isFinite(margen) || margen < 1) {
    globo('El margen de embalaje tiene que ser 1 o más.', 'mal');
    return;
  }

  boton.disabled = true;
  boton.textContent = 'Guardando…';
  try {
    const actualizado = await API.put(`/articulos/${a.id}`, {
      nombre,
      largo_real_mm: reales[0], ancho_real_mm: reales[1], alto_real_mm: reales[2],
      se_embala_doblado: doblado,
      largo_emb_mm: doblado ? embaladas[0] : null,
      ancho_emb_mm: doblado ? embaladas[1] : null,
      alto_emb_mm: doblado ? embaladas[2] : null,
      sku_elgadget: q('#ar-sku-eg').value.trim() || null,
      sku_afd: q('#ar-sku-afd').value.trim() || null,
      id_empretienda: q('#ar-empre').value.trim() || null,
      margen_embalaje: margen,
    });

    Object.assign(a, actualizado);
    hoja.cuerpo.querySelector('#ar-envio').innerHTML = panelEnvio(a.envio);
    Cache.invalidar('articulos');
    globo('Datos guardados. El peso de envío se recalculó.');
    recargarPantalla();
  } catch (e) {
    globo('No se pudo guardar: ' + e.message, 'mal');
  } finally {
    boton.disabled = false;
    boton.textContent = 'Guardar datos';
  }
}

async function cambiarActivoArticulo(a, hoja) {
  if (a.activo) {
    if (!await confirmar(
      'Si el artículo tiene ventas no se borra, se <strong>desactiva</strong>: los movimientos ' +
      'de esas ventas apuntan a él y borrarlo dejaría al libro mayor sin poder explicarlos.',
      { titulo: '¿Desactivar el artículo?', textoSi: 'Desactivar' })) return;
    try {
      const r = await API.borrar(`/articulos/${a.id}`);
      globo(r.borrado ? 'Artículo borrado (nunca se vendió).' : 'Artículo desactivado.');
      Cache.invalidar('articulos');
      volverAtras(hoja);
      recargarPantalla();
    } catch (e) { globo('No se pudo: ' + e.message, 'mal'); }
  } else {
    try {
      await API.put(`/articulos/${a.id}`, { activo: true });
      globo('Artículo activado de nuevo.');
      Cache.invalidar('articulos');
      volverAtras(hoja);
      recargarPantalla();
    } catch (e) { globo('No se pudo: ' + e.message, 'mal'); }
  }
}

/* ── Editor de receta ─────────────────────────────────────────

   Cada línea se guarda sola y la respuesta trae el envío recalculado. Por
   eso el peso de arriba es siempre el del servidor, nunca una cuenta hecha
   acá. */

/** `GET /articulos/{id}` y los endpoints de receta devuelven la misma receta
    con dos nombres distintos para "el insumo está activo". Se normaliza una
    sola vez, acá, en vez de que cada función lo adivine. */
function normalizarReceta(items) {
  return (items || []).map((r) => ({
    insumo_id: r.insumo_id,
    nombre: r.nombre,
    cantidad: Number(r.cantidad),
    peso_unitario_g: Number(r.peso_unitario_g),
    modo_stock: r.modo_stock,
    activo: r.insumo_activo !== undefined ? r.insumo_activo : !!r.activo,
  }));
}

function pintarReceta(hoja, a) {
  const caja = hoja.cuerpo.querySelector('#ar-receta');
  const receta = normalizarReceta(a.receta);

  if (!receta.length) {
    caja.innerHTML = `
      <div class="aviso atencion" style="margin-bottom:0">
        <strong>La receta está vacía</strong>
        Sin insumos no hay peso de envío. Agregá cuántas unidades de cada insumo lleva un
        artículo terminado.
      </div>`;
    return;
  }

  caja.innerHTML = receta.map((r) => `
    <div class="receta-fila" data-linea="${r.insumo_id}">
      <div class="receta-nombre">
        <b>${esc(r.nombre)}${r.activo ? '' : ' (insumo inactivo)'}</b>
        <span>${fmtCant(r.peso_unitario_g)} g c/u · aporta ${fmtCant(r.cantidad * r.peso_unitario_g)} g</span>
      </div>
      <div class="receta-cant">
        <input type="text" inputmode="decimal" value="${esc(r.cantidad)}"
               data-cantidad="${r.insumo_id}" aria-label="Unidades de ${esc(r.nombre)}">
      </div>
      <button class="receta-quitar" data-quitar="${r.insumo_id}"
              aria-label="Quitar ${esc(r.nombre)}">${icono('menos')}</button>
    </div>`).join('') + `
    <div class="receta-total">
      <span>Peso de los insumos</span>
      <span>${fmtCant(a.envio.peso_insumos_g)} g</span>
    </div>
    <div class="ayuda" style="margin-top:8px">
      Las cantidades van en <strong>unidades</strong>, también para un insumo que se cuenta
      por peso: "lleva 3 caireles", no "7,5 gramos de caireles". Es lo que hace que
      descontar stock sea una resta sin conversiones.
    </div>`;

  caja.querySelectorAll('[data-cantidad]').forEach((input) => {
    const guardar = demorar(() => guardarLineaReceta(hoja, a, Number(input.dataset.cantidad), input), 550);
    input.addEventListener('input', guardar);
    input.addEventListener('blur', () =>
      guardarLineaReceta(hoja, a, Number(input.dataset.cantidad), input));
  });
  caja.querySelectorAll('[data-quitar]').forEach((b) => {
    b.addEventListener('click', () => quitarLineaReceta(hoja, a, Number(b.dataset.quitar)));
  });
}

function aplicarRespuestaDeReceta(hoja, a, respuesta) {
  a.receta = normalizarReceta(respuesta.items);
  a.envio = respuesta.envio;
  hoja.cuerpo.querySelector('#ar-envio').innerHTML = panelEnvio(a.envio);
  pintarReceta(hoja, a);
  Cache.invalidar('articulos');
}

async function agregarLineaReceta(hoja, a, insumo) {
  if (!insumo) return;
  try {
    const r = await API.post(`/articulos/${a.id}/receta`, { insumo_id: insumo.id, cantidad: 1 });
    aplicarRespuestaDeReceta(hoja, a, r);
    globo(`${insumo.nombre}: 1 unidad. Ajustá la cantidad si lleva más.`);
    recargarPantalla();
  } catch (e) {
    globo('No se pudo agregar: ' + e.message, 'mal');
  }
}

async function guardarLineaReceta(hoja, a, insumoId, input) {
  const cantidad = num(input.value);
  const actual = (a.receta || []).find((r) => r.insumo_id === insumoId);
  if (!actual) return;
  if (!isFinite(cantidad) || cantidad === Number(actual.cantidad)) return;

  if (cantidad <= 0) {
    // El backend rechaza una cantidad de cero o negativa, y tiene razón: una
    // línea en cero no es una receta, es una línea que hay que quitar.
    input.value = actual.cantidad;
    globo('Una cantidad en cero no vale: usá el botón de quitar.', 'mal');
    return;
  }

  try {
    const r = await API.post(`/articulos/${a.id}/receta`, { insumo_id: insumoId, cantidad });
    aplicarRespuestaDeReceta(hoja, a, r);
  } catch (e) {
    input.value = actual.cantidad;
    globo('No se pudo guardar la cantidad: ' + e.message, 'mal');
  }
}

async function quitarLineaReceta(hoja, a, insumoId) {
  const linea = (a.receta || []).find((r) => r.insumo_id === insumoId);
  if (!await confirmar(
    `Se saca <strong>${esc(linea ? linea.nombre : 'el insumo')}</strong> de la receta. ` +
    'No cambia nada de lo ya descontado: una receta nueva afecta las ventas que vengan, ' +
    'no las que ya se asentaron.',
    { titulo: '¿Quitar de la receta?', textoSi: 'Quitar' })) return;

  try {
    const r = await API.borrar(`/articulos/${a.id}/receta/${insumoId}`);
    aplicarRespuestaDeReceta(hoja, a, r);
    globo('Insumo quitado de la receta.');
    recargarPantalla();
  } catch (e) {
    globo('No se pudo quitar: ' + e.message, 'mal');
  }
}

/* ── Simulador de margen ──────────────────────────────────────

   `GET /api/articulos/{id}/envio?margen=` recalcula sin guardar nada. Sirve
   para ver si el margen cambia de escalón de peso aforado antes de decidir. */

function simularMargen(a) {
  const hoja = abrirHoja({
    titulo: 'Simular otro margen',
    subtitulo: a.nombre,
    cuerpo: `
      <div class="ayuda" style="margin-bottom:14px">
        Compara el envío con otro factor de embalaje <strong>sin guardar nada</strong>.
        Correo cobra por peso volumétrico, así que el margen es una decisión de precio:
        1,05 por dimensión infla el volumen 15,8 %, y 1,016 lo infla 5 %.
      </div>
      <div class="campo">
        <label for="sim-margen">Margen a probar</label>
        <input type="text" id="sim-margen" inputmode="decimal" value="1,016">
        <div class="pie">El artículo tiene guardado ${fmtCant(a.margen_embalaje)}.</div>
      </div>
      <div class="fila-botones" style="margin-bottom:14px">
        <button class="btn btn-borde btn-ch" data-probar="1">1,00 (sin margen)</button>
        <button class="btn btn-borde btn-ch" data-probar="1.016">1,016</button>
        <button class="btn btn-borde btn-ch" data-probar="1.05">1,05</button>
      </div>
      <div id="sim-resultado"></div>`,
    acciones: [{ texto: 'Cerrar', clase: 'btn-borde', alTocar: (h) => volverAtras(h) }],
  });

  const campo = hoja.cuerpo.querySelector('#sim-margen');
  const salida = hoja.cuerpo.querySelector('#sim-resultado');

  const probar = async () => {
    const margen = num(campo.value);
    if (!isFinite(margen) || margen < 1) {
      salida.innerHTML = '<div class="aviso malo">El margen tiene que ser 1 o más.</div>';
      return;
    }
    salida.innerHTML = cargando('Calculando…');
    try {
      const envio = await API.get(`/articulos/${a.id}/envio`, { margen });
      salida.innerHTML = panelEnvio(envio) + `
        <div class="ayuda">
          Guardado en el artículo: ${fmtCant(a.envio.peso_envio_g)} g y
          ${fmt(a.envio.volumen_cm3, 0)} cm³. Esta simulación no cambió nada.
        </div>`;
    } catch (e) {
      salida.innerHTML = errorEnPantalla(e);
    }
  };

  campo.addEventListener('input', demorar(probar, 400));
  hoja.cuerpo.querySelectorAll('[data-probar]').forEach((b) => {
    b.addEventListener('click', () => {
      campo.value = String(b.dataset.probar).replace('.', ',');
      probar();
    });
  });
  probar();
}
