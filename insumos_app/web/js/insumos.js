/* ============================================================
   INSUMOS — ASÍ FUE DECO · pantalla de INSUMOS

   Listado buscable, alta y edición, y la ficha de un insumo (desde donde se
   llega a cargar stock y a ver su historial).

   DOS DECISIONES DE PANTALLA QUE IMPORTAN

   1. El modo de stock se elige con dos botones grandes y de color distinto,
      no con un `<select>` donde "peso" y "unidad" se ven iguales. Y cada vez
      que se pide un número de stock, la unidad va al lado del campo y en un
      bloque arriba. Un insumo mal contado no se nota hasta que falta
      material, así que la pantalla tiene que hacer imposible la confusión,
      no solo documentarla.

   2. La búsqueda y el filtrado son del lado del navegador. La lista se trae
      una vez y se filtra mientras se tipea: en el taller, con el celular y
      mala señal, una consulta por tecla hace que buscar un cairel sea
      esperar. La lista se recarga sola cada vez que algo la modifica.
   ============================================================ */

const Insumos = {
  todos: [],
  texto: '',
  categoria: '',
  subcategoria: '',
  soloAlerta: false,
  incluirInactivos: false,
};

async function cargarInsumos() {
  const caja = el('p-insumos');
  caja.innerHTML = `
    <div class="seccion-cabecera">
      <h2>Insumos</h2>
      <button class="btn btn-ch" id="nuevo-insumo">${icono('mas')} Nuevo</button>
    </div>

    <div class="buscador">
      ${icono('lupa', 'lupa')}
      <input type="search" id="buscar-insumo" placeholder="Buscar un insumo…"
             autocomplete="off" enterkeyhint="search" value="${esc(Insumos.texto)}">
      <button class="limpiar oculto" id="limpiar-insumo" aria-label="Limpiar">${icono('cruz')}</button>
    </div>

    <div class="filtros">
      <select id="filtro-categoria" aria-label="Categoría"><option value="">Toda categoría</option></select>
      <select id="filtro-subcategoria" aria-label="Subcategoría"><option value="">Toda subcategoría</option></select>
    </div>

    <div class="filtros" style="margin-bottom:14px">
      <button class="btn btn-borde btn-ch" id="filtro-alerta" style="flex:1">Solo los que faltan</button>
      <button class="btn btn-borde btn-ch" id="filtro-inactivos" style="flex:1">Ver inactivos</button>
    </div>

    <div id="insumos-resumen" class="ayuda" style="margin-bottom:10px"></div>
    <div class="lista doble" id="lista-insumos">${cargando()}</div>`;

  el('nuevo-insumo').addEventListener('click', () => abrirFormInsumo(null));

  const buscar = el('buscar-insumo');
  const limpiar = el('limpiar-insumo');
  const alTipear = demorar(() => {
    Insumos.texto = buscar.value.trim();
    limpiar.classList.toggle('oculto', !Insumos.texto);
    pintarInsumos();
  }, 160);
  buscar.addEventListener('input', alTipear);
  limpiar.addEventListener('click', () => {
    buscar.value = ''; Insumos.texto = '';
    limpiar.classList.add('oculto'); pintarInsumos(); buscar.focus();
  });
  limpiar.classList.toggle('oculto', !Insumos.texto);

  el('filtro-categoria').addEventListener('change', (e) => {
    Insumos.categoria = e.target.value;
    Insumos.subcategoria = '';
    llenarSubcategorias();
    pintarInsumos();
  });
  el('filtro-subcategoria').addEventListener('change', (e) => {
    Insumos.subcategoria = e.target.value;
    pintarInsumos();
  });
  el('filtro-alerta').addEventListener('click', () => {
    Insumos.soloAlerta = !Insumos.soloAlerta;
    marcarFiltro('filtro-alerta', Insumos.soloAlerta);
    pintarInsumos();
  });
  el('filtro-inactivos').addEventListener('click', async () => {
    Insumos.incluirInactivos = !Insumos.incluirInactivos;
    marcarFiltro('filtro-inactivos', Insumos.incluirInactivos);
    await traerInsumos();
    pintarInsumos();
  });
  marcarFiltro('filtro-alerta', Insumos.soloAlerta);
  marcarFiltro('filtro-inactivos', Insumos.incluirInactivos);

  try {
    await Promise.all([traerInsumos(), llenarCategoriasFiltro()]);
    pintarInsumos();
  } catch (e) {
    if (e instanceof ErrorAuth) { pedirIngreso(e.message); return; }
    el('lista-insumos').innerHTML = errorEnPantalla(e, 'cargarInsumos()');
  }
}

function marcarFiltro(id, activo) {
  const b = el(id);
  if (!b) return;
  b.classList.toggle('btn-borde', !activo);
  b.classList.toggle('btn-oscuro', activo);
}

async function traerInsumos() {
  Insumos.todos = await API.get('/insumos',
    Insumos.incluirInactivos ? {} : { activo: true });
}

async function llenarCategoriasFiltro() {
  const categorias = await Cache.categorias();
  const sel = el('filtro-categoria');
  if (!sel) return;
  sel.innerHTML = '<option value="">Toda categoría</option>' +
    categorias.map((c) => `<option value="${c.id}">${esc(c.nombre)} (${c.insumos})</option>`).join('');
  sel.value = Insumos.categoria;
  llenarSubcategorias();
}

async function llenarSubcategorias() {
  const sel = el('filtro-subcategoria');
  if (!sel) return;
  const categorias = await Cache.categorias();
  const cat = categorias.find((c) => String(c.id) === String(Insumos.categoria));
  const subs = cat ? cat.subcategorias : [];
  sel.innerHTML = '<option value="">Toda subcategoría</option>' +
    subs.map((s) => `<option value="${s.id}">${esc(s.nombre)} (${s.insumos})</option>`).join('');
  sel.value = Insumos.subcategoria;
  sel.disabled = !subs.length;
}

function insumosFiltrados() {
  const texto = Insumos.texto.toLowerCase();
  return Insumos.todos.filter((i) => {
    if (texto && !(
      String(i.nombre).toLowerCase().includes(texto) ||
      String(i.categoria || '').toLowerCase().includes(texto) ||
      String(i.subcategoria || '').toLowerCase().includes(texto))) return false;
    if (Insumos.categoria && String(i.categoria_id) !== String(Insumos.categoria)) return false;
    if (Insumos.subcategoria && String(i.subcategoria_id) !== String(Insumos.subcategoria)) return false;
    if (Insumos.soloAlerta && !i.en_alerta) return false;
    return true;
  });
}

function pintarInsumos() {
  const lista = el('lista-insumos');
  if (!lista) return;
  const items = insumosFiltrados();

  el('insumos-resumen').textContent = items.length === Insumos.todos.length
    ? `${items.length} insumo${items.length === 1 ? '' : 's'}`
    : `${items.length} de ${Insumos.todos.length} insumos`;

  if (!items.length) {
    lista.innerHTML = vacio(
      Insumos.todos.length ? 'Ningún insumo coincide' : 'Todavía no hay insumos cargados',
      Insumos.todos.length
        ? '<div class="ayuda" style="margin-top:6px">Probá con menos letras o limpiá los filtros.</div>'
        : '<div class="ayuda" style="margin-top:6px">Empezá por las categorías (caireles, cadenas, cintas…) y después cargá los insumos.</div>');
    return;
  }

  lista.innerHTML = items.map(filaInsumo).join('');
  lista.querySelectorAll('[data-insumo]').forEach((b) => {
    b.addEventListener('click', () => abrirFichaInsumo(Number(b.dataset.insumo)));
  });
}

function filaInsumo(i) {
  const u = unidadDe(i);
  const negativo = i.stock.unidades < 0;
  const clase = negativo ? 'negativo' : (i.en_alerta ? 'alerta' : 'ok');
  const ruta = [i.categoria, i.subcategoria].filter(Boolean).join(' · ') || 'Sin categoría';

  return `
    <button class="item ${clase} ${i.activo ? '' : 'apagado'}" data-insumo="${i.id}">
      <div class="item-fila">
        <div class="item-cuerpo">
          <div class="item-nombre">${esc(i.nombre)}</div>
          <div class="item-sub">${esc(ruta)}</div>
        </div>
        <div class="item-derecha">
          <div class="item-numero" style="${negativo ? 'color:var(--red)' : ''}">
            ${fmtCant(i.stock.cantidad_pantalla)}<small> ${esc(unidadTxt(u, i.stock.cantidad_pantalla))}</small>
          </div>
          ${u === 'kg' ? `<div class="item-sub">${fmt(Math.round(i.stock.unidades))} u.</div>` : ''}
        </div>
      </div>
      <div class="item-pie">
        ${chipUnidad(i)}
        ${i.activo ? '' : '<span class="insignia">Inactivo</span>'}
        ${negativo ? '<span class="insignia roja">En negativo</span>'
          : (i.en_alerta ? '<span class="insignia ambar">Hay que reponer</span>' : '')}
        ${i.costos ? `<span class="insignia">${fmtPesos(i.costos.costo_por_unidad)} / u.</span>` : ''}
      </div>
    </button>`;
}

/* ── Ficha de un insumo ───────────────────────────────────── */

async function abrirFichaInsumo(id) {
  const hoja = abrirHoja({ titulo: 'Insumo', cuerpo: cargando() });
  try {
    const i = await API.get(`/insumos/${id}`);
    const u = unidadDe(i);
    const negativo = i.stock.unidades < 0;

    hoja.cuerpo.innerHTML = `
      <div class="tarjeta">
        <h2 style="font-size:17px;margin-bottom:8px">${esc(i.nombre)}</h2>
        <div class="item-pie" style="margin-top:0;margin-bottom:12px">
          ${chipUnidad(i)}
          ${i.activo ? '' : '<span class="insignia">Inactivo</span>'}
          ${i.categoria ? `<span class="insignia">${esc(i.categoria)}</span>` : ''}
          ${i.subcategoria ? `<span class="insignia">${esc(i.subcategoria)}</span>` : ''}
        </div>

        <div style="display:flex;align-items:baseline;gap:10px;flex-wrap:wrap">
          <div style="font-family:'Space Grotesk',sans-serif;font-size:34px;font-weight:700;line-height:1;${negativo ? 'color:var(--red)' : ''}">
            ${fmtCant(i.stock.cantidad_pantalla)}<span style="font-size:16px"> ${esc(unidadTxt(u, i.stock.cantidad_pantalla))}</span>
          </div>
          <div class="ayuda">
            ${u === 'kg'
              ? `= ${fmt(Math.round(i.stock.unidades))} unidades`
              : `= ${fmtCant(i.stock.kg)} kg`}
          </div>
        </div>
        ${negativo ? `<div class="aviso malo" style="margin-top:12px">
            <strong>El stock está en negativo</strong>
            Se vendió material que no estaba cargado. El sistema asentó esas ventas igual
            (rechazarlas sería perder el dato) — se corrige con un conteo de inventario.
          </div>` : ''}
        ${i.en_alerta && !negativo ? `<div class="aviso atencion" style="margin-top:12px">
            <strong>Por debajo del umbral</strong>
            Avisar cuando queden ${fmtCant(i.alerta_cuando_queden)} ${esc(unidadTxt(u, i.alerta_cuando_queden))}.
          </div>` : ''}

        <div class="fila-botones" style="margin-top:14px">
          <button class="btn" id="f-ingreso">${icono('mas')} Cargar ingreso</button>
          <button class="btn btn-borde" id="f-conteo">Conteo de inventario</button>
        </div>
        <div class="fila-botones" style="margin-top:10px">
          <button class="btn btn-borde" id="f-historial">${icono('historial')} Movimientos</button>
          <button class="btn btn-borde" id="f-editar">${icono('lapiz')} Editar</button>
        </div>
      </div>

      <div class="tarjeta">
        <div class="bloque-titulo">Datos</div>
        <table class="tabla" style="min-width:0">
          <tr><td>Peso por unidad</td><td class="num">${fmtCant(i.peso_unitario_g)} g</td></tr>
          <tr><td>Avisar cuando queden</td><td class="num">${fmtCant(i.alerta_cuando_queden)} ${esc(unidadTxt(u, i.alerta_cuando_queden))}</td></tr>
          ${i.costos ? `
            <tr><td>Costo por unidad</td><td class="num">${fmtPesos(i.costos.costo_por_unidad)}</td></tr>
            <tr><td>Costo por 100 g</td><td class="num">${fmtPesos(i.costos.costo_por_100g)}</td></tr>
            <tr><td>Costo por kilo</td><td class="num">${fmtPesos(i.costos.costo_por_kg)}</td></tr>`
          : '<tr><td colspan="2" class="ayuda">Sin costo cargado</td></tr>'}
          ${(i.largo_mm || i.ancho_mm || i.alto_mm) ? `
            <tr><td>Medidas por unidad</td><td class="num">
              ${fmtCant(i.largo_mm || 0)} × ${fmtCant(i.ancho_mm || 0)} × ${fmtCant(i.alto_mm || 0)} mm
            </td></tr>` : ''}
        </table>
      </div>

      <div class="tarjeta">
        <div class="bloque-titulo">En qué artículos entra</div>
        ${i.usado_en.length ? `
          <table class="tabla" style="min-width:0">
            ${i.usado_en.map((a) => `<tr>
              <td>${esc(a.nombre)}</td>
              <td class="num">${fmtCant(a.cantidad)} u.</td>
            </tr>`).join('')}
          </table>
          <div class="ayuda" style="margin-top:10px">
            Las cantidades de una receta están siempre en <strong>unidades</strong>, también
            para un insumo que se cuenta por peso: la receta dice "lleva 3 caireles".
          </div>`
        : `<div class="ayuda">En ninguno todavía. Un artículo sin este insumo en su receta
             no suma su peso al envío.</div>`}
      </div>

      <button class="btn btn-borde btn-bloque" id="f-desactivar" style="color:var(--red)">
        ${i.activo ? 'Desactivar insumo' : 'Volver a activar'}
      </button>`;

    el('f-ingreso').addEventListener('click', () => abrirMovimiento(i));
    el('f-conteo').addEventListener('click', () => abrirConteo(i));
    el('f-historial').addEventListener('click', () => abrirMovimientosDeInsumo(i));
    el('f-editar').addEventListener('click', () => abrirFormInsumo(i));
    el('f-desactivar').addEventListener('click', () => cambiarActivoInsumo(i, hoja));
  } catch (e) {
    hoja.cuerpo.innerHTML = errorEnPantalla(e);
  }
}

async function cambiarActivoInsumo(insumo, hoja) {
  if (insumo.activo) {
    if (!await confirmar(
      'Un insumo con movimientos o recetas no se borra, se <strong>desactiva</strong>: ' +
      'borrarlo dejaría al libro mayor sin poder explicar movimientos que existen. ' +
      'Deja de aparecer en las listas pero su historia queda intacta.',
      { titulo: '¿Desactivar el insumo?', textoSi: 'Desactivar' })) return;
    try {
      const r = await API.borrar(`/insumos/${insumo.id}`);
      globo(r.borrado ? 'Insumo borrado (no tenía historia).' : 'Insumo desactivado.');
      Cache.invalidar('insumos', 'categorias');
      volverAtras(hoja);
      recargarPantalla();
    } catch (e) { globo('No se pudo: ' + e.message, 'mal'); }
  } else {
    try {
      await API.put(`/insumos/${insumo.id}`, { activo: true });
      globo('Insumo activado de nuevo.');
      Cache.invalidar('insumos');
      volverAtras(hoja);
      recargarPantalla();
    } catch (e) { globo('No se pudo: ' + e.message, 'mal'); }
  }
}

/* ── Alta y edición ──────────────────────────────────────── */

async function abrirFormInsumo(insumo) {
  const editando = !!insumo;
  const categorias = await Cache.categorias().catch(() => []);

  const hoja = abrirHoja({
    titulo: editando ? 'Editar insumo' : 'Nuevo insumo',
    subtitulo: editando ? insumo.nombre : '',
    cuerpo: formularioInsumoHTML(insumo, categorias, editando),
    acciones: [
      { texto: 'Cancelar', clase: 'btn-borde', alTocar: (h) => volverAtras(h) },
      { texto: 'Guardar', clase: 'btn', id: 'guardar-insumo', alTocar: (h, b) => guardarInsumo(insumo, h, b) },
    ],
  });

  // El modo de stock cambia la unidad de dos campos (el umbral y la carga
  // inicial). Se repinta al instante: que el formulario muestre "kg" cuando
  // ya elegiste "por unidad" es justo el error que esto evita.
  hoja.cuerpo.querySelectorAll('input[name=modo]').forEach((r) => {
    r.addEventListener('change', () => {
      hoja.cuerpo.querySelectorAll('.opcion').forEach((o) =>
        o.classList.toggle('elegida', o.querySelector('input').checked));
      refrescarUnidadesDelForm(hoja);
    });
  });
  hoja.cuerpo.querySelector('#f-categoria').addEventListener('change', () =>
    llenarSubcategoriaForm(hoja, categorias));
  hoja.cuerpo.querySelectorAll('.casilla input[type=checkbox]').forEach(marcarCasilla);

  llenarSubcategoriaForm(hoja, categorias, insumo && insumo.subcategoria_id);
  refrescarUnidadesDelForm(hoja);
}

function formularioInsumoHTML(insumo, categorias, editando) {
  const i = insumo || {};
  const modo = i.modo_stock || 'unidad';

  return `
    <div class="campo">
      <label for="f-nombre">Nombre del insumo</label>
      <input type="text" id="f-nombre" value="${esc(i.nombre || '')}"
             placeholder="Cairel de vidrio 20 mm transparente" autocomplete="off">
    </div>

    <div class="campo">
      <label>¿Cómo se cuenta este insumo?</label>
      <div class="opciones">
        <label class="opcion kg ${modo === 'peso' ? 'elegida' : ''}">
          <input type="radio" name="modo" value="peso" ${modo === 'peso' ? 'checked' : ''}>
          <b>POR PESO</b>
          <span>Se compra y se cuenta en kilos. El stock se carga en kg.</span>
        </label>
        <label class="opcion unidad ${modo === 'unidad' ? 'elegida' : ''}">
          <input type="radio" name="modo" value="unidad" ${modo === 'unidad' ? 'checked' : ''}>
          <b>POR UNIDAD</b>
          <span>Se cuenta de a uno. El stock se carga en unidades.</span>
        </label>
      </div>
      <div class="pie">
        Esto decide en qué unidad te va a pedir el número toda la aplicación. No es lo
        mismo que la categoría: un cairel <em>de vidrio</em> puede comprarse por peso.
      </div>
    </div>

    <div id="f-unidad-aviso"></div>

    <div class="campo">
      <label for="f-peso">Peso de UNA unidad <span class="opt">· obligatorio</span></label>
      <div class="campo-numero">
        <input type="text" id="f-peso" inputmode="decimal" autocomplete="off"
               value="${i.peso_unitario_g !== undefined && i.peso_unitario_g !== null ? esc(i.peso_unitario_g) : ''}" placeholder="2,5">
        <span class="sufijo">gramos</span>
      </div>
      <div class="pie">
        Hace falta <strong>siempre</strong>, también si el insumo se cuenta por peso: es el
        puente entre los kilos que se compran y las unidades que pide la receta, y sin él no
        hay peso de envío. Pesá 100 unidades en la balanza y dividí por 100.
      </div>
    </div>

    <div class="rejilla-2" style="margin-bottom:14px">
      <div class="campo">
        <label for="f-categoria">Categoría</label>
        <select id="f-categoria">
          <option value="">Sin categoría</option>
          ${categorias.map((c) => `<option value="${c.id}" ${String(c.id) === String(i.categoria_id) ? 'selected' : ''}>${esc(c.nombre)}</option>`).join('')}
        </select>
      </div>
      <div class="campo">
        <label for="f-subcategoria">Subcategoría</label>
        <select id="f-subcategoria"><option value="">Sin subcategoría</option></select>
      </div>
    </div>

    <div class="campo">
      <label for="f-umbral">Avisar cuando queden</label>
      <div class="campo-numero" id="f-umbral-caja">
        <input type="text" id="f-umbral" inputmode="decimal" autocomplete="off"
               value="${esc(i.alerta_cuando_queden !== undefined && i.alerta_cuando_queden !== null ? i.alerta_cuando_queden : 0)}" placeholder="0">
        <span class="sufijo" id="f-umbral-sufijo">unidades</span>
      </div>
      <div class="pie">En 0 no avisa nunca por stock bajo. Un stock negativo se avisa igual.</div>
    </div>

    <div class="rejilla-2" style="margin-bottom:14px">
      <div class="campo">
        <label for="f-costo">Costo de compra <span class="opt">· opcional</span></label>
        <input type="text" id="f-costo" inputmode="decimal" autocomplete="off"
               value="${i.costo_compra !== undefined && i.costo_compra !== null ? esc(i.costo_compra) : ''}" placeholder="12000">
      </div>
      <div class="campo">
        <label for="f-unidad-compra">Ese costo es por</label>
        <select id="f-unidad-compra">
          <option value="">—</option>
          <option value="kg" ${i.unidad_compra === 'kg' ? 'selected' : ''}>kilo</option>
          <option value="unidad" ${i.unidad_compra === 'unidad' ? 'selected' : ''}>unidad</option>
        </select>
      </div>
    </div>

    <div class="campo">
      <label>Medidas de una unidad <span class="opt">· opcionales, aproximadas</span></label>
      <div class="rejilla-3">
        <div class="campo"><label for="f-largo" style="font-size:11px">Largo mm</label>
          <input type="text" id="f-largo" inputmode="decimal" value="${i.largo_mm !== null && i.largo_mm !== undefined ? esc(i.largo_mm) : ''}" placeholder="—"></div>
        <div class="campo"><label for="f-ancho" style="font-size:11px">Ancho mm</label>
          <input type="text" id="f-ancho" inputmode="decimal" value="${i.ancho_mm !== null && i.ancho_mm !== undefined ? esc(i.ancho_mm) : ''}" placeholder="—"></div>
        <div class="campo"><label for="f-alto" style="font-size:11px">Alto mm</label>
          <input type="text" id="f-alto" inputmode="decimal" value="${i.alto_mm !== null && i.alto_mm !== undefined ? esc(i.alto_mm) : ''}" placeholder="—"></div>
      </div>
    </div>

    ${editando ? '' : `
      <div class="campo">
        <label for="f-inicial">Stock que hay hoy <span class="opt">· opcional</span></label>
        <div class="campo-numero" id="f-inicial-caja">
          <input type="text" id="f-inicial" inputmode="decimal" autocomplete="off" placeholder="0">
          <span class="sufijo" id="f-inicial-sufijo">unidades</span>
        </div>
        <div class="equivale" id="f-inicial-equivale"></div>
        <div class="pie">
          Entra como movimiento de <strong>inventario inicial</strong>, no como un número
          escrito a mano: el libro mayor explica también el primer dato. Ojo que la primera
          carga de stock del sistema <strong>fija la fecha de corte</strong>, y las ventas
          anteriores a esa fecha no se descuentan.
        </div>
      </div>`}

    ${editando ? `
      <label class="casilla">
        <input type="checkbox" id="f-activo" ${insumo.activo ? 'checked' : ''}>
        <span class="casilla-texto"><b>Insumo activo</b>
          <span>Los inactivos no aparecen en las listas ni en las alertas.</span></span>
      </label>` : ''}

    <div class="ayuda" style="margin-top:14px">
      El stock no se edita acá: cambia solo con un movimiento (un ingreso, una merma, un
      conteo o una venta). Es lo que permite reconstruirlo sumando el libro mayor.
    </div>`;
}

function llenarSubcategoriaForm(hoja, categorias, preseleccion) {
  const catSel = hoja.cuerpo.querySelector('#f-categoria');
  const subSel = hoja.cuerpo.querySelector('#f-subcategoria');
  const cat = categorias.find((c) => String(c.id) === String(catSel.value));
  const subs = cat ? cat.subcategorias : [];
  subSel.innerHTML = '<option value="">Sin subcategoría</option>' +
    subs.map((s) => `<option value="${s.id}" ${String(s.id) === String(preseleccion) ? 'selected' : ''}>${esc(s.nombre)}</option>`).join('');
  subSel.disabled = !subs.length;
}

function refrescarUnidadesDelForm(hoja) {
  const modo = hoja.cuerpo.querySelector('input[name=modo]:checked').value;
  const esKg = modo === 'peso';
  const unidad = esKg ? 'kg' : 'unidades';

  hoja.cuerpo.querySelector('#f-umbral-sufijo').textContent = unidad;
  const cajaUmbral = hoja.cuerpo.querySelector('#f-umbral-caja');
  cajaUmbral.className = 'campo-numero ' + (esKg ? 'kg' : 'unidad');

  const cajaInicial = hoja.cuerpo.querySelector('#f-inicial-caja');
  if (cajaInicial) {
    hoja.cuerpo.querySelector('#f-inicial-sufijo').textContent = unidad;
    cajaInicial.className = 'campo-numero ' + (esKg ? 'kg' : 'unidad');
  }

  hoja.cuerpo.querySelector('#f-unidad-aviso').innerHTML = unidadAviso(
    { modo_stock: modo, peso_unitario_g: num(hoja.cuerpo.querySelector('#f-peso').value) || 0 },
    { accion: 'El stock de este insumo se carga' });

  // La equivalencia viva del stock inicial, para que un "2" que iban a ser
  // unidades se delate como "2 kg ≈ 800 unidades" antes de guardar.
  const inicial = hoja.cuerpo.querySelector('#f-inicial');
  const peso = hoja.cuerpo.querySelector('#f-peso');
  if (inicial) {
    const salida = hoja.cuerpo.querySelector('#f-inicial-equivale');
    const pintar = () => {
      salida.innerHTML = equivalenciaAproximada(num(inicial.value),
        { modo_stock: modo, peso_unitario_g: num(peso.value) || 0 });
    };
    inicial.oninput = pintar;
    peso.oninput = () => { pintar(); refrescarAvisoPeso(hoja, modo); };
    pintar();
  } else {
    peso.oninput = () => refrescarAvisoPeso(hoja, modo);
  }
}

function refrescarAvisoPeso(hoja, modo) {
  hoja.cuerpo.querySelector('#f-unidad-aviso').innerHTML = unidadAviso(
    { modo_stock: modo, peso_unitario_g: num(hoja.cuerpo.querySelector('#f-peso').value) || 0 },
    { accion: 'El stock de este insumo se carga' });
}

async function guardarInsumo(insumo, hoja, boton) {
  const q = (sel) => hoja.cuerpo.querySelector(sel);
  const nombre = q('#f-nombre').value.trim();
  const modo = q('input[name=modo]:checked').value;
  const peso = num(q('#f-peso').value);

  if (!nombre) { globo('Falta el nombre del insumo.', 'mal'); q('#f-nombre').focus(); return; }
  if (!isFinite(peso) || peso <= 0) {
    globo('El peso de una unidad es obligatorio y mayor que cero.', 'mal');
    q('#f-peso').focus();
    return;
  }

  const opcional = (sel) => {
    const v = num(q(sel).value);
    return isFinite(v) ? v : null;
  };

  const datos = {
    nombre,
    modo_stock: modo,
    peso_unitario_g: peso,
    categoria_id: q('#f-categoria').value ? Number(q('#f-categoria').value) : null,
    subcategoria_id: q('#f-subcategoria').value ? Number(q('#f-subcategoria').value) : null,
    alerta_cuando_queden: isFinite(num(q('#f-umbral').value)) ? num(q('#f-umbral').value) : 0,
    costo_compra: opcional('#f-costo'),
    unidad_compra: q('#f-unidad-compra').value || null,
    largo_mm: opcional('#f-largo'),
    ancho_mm: opcional('#f-ancho'),
    alto_mm: opcional('#f-alto'),
  };

  if (datos.costo_compra !== null && !datos.unidad_compra) {
    globo('Decí si ese costo es por kilo o por unidad.', 'mal');
    q('#f-unidad-compra').focus();
    return;
  }

  boton.disabled = true;
  boton.textContent = 'Guardando…';
  try {
    let r;
    if (insumo) {
      datos.activo = q('#f-activo').checked;
      r = await API.put(`/insumos/${insumo.id}`, datos);
    } else {
      const inicial = num(q('#f-inicial').value);
      if (isFinite(inicial) && inicial !== 0) datos.stock_inicial = inicial;
      r = await API.post('/insumos', datos);
    }

    Cache.invalidar('insumos', 'categorias');
    volverAtras(hoja);
    recargarPantalla();

    if (r.avisos && r.avisos.length) {
      abrirHoja({
        titulo: 'Guardado, con un aviso',
        cuerpo: listaAvisos(r.avisos),
        acciones: [{ texto: 'Entendido', clase: 'btn', alTocar: (h) => volverAtras(h) }],
      });
    } else {
      globo(insumo ? 'Insumo actualizado.' : 'Insumo creado.');
    }
  } catch (e) {
    globo('No se pudo guardar: ' + e.message, 'mal');
  } finally {
    boton.disabled = false;
    boton.textContent = 'Guardar';
  }
}

/* ── Selector reutilizable ────────────────────────────────────

   Lo usan el editor de receta y la pantalla de stock. Filtra en el
   navegador sobre la lista ya traída: buscar un insumo entre doscientos
   tiene que ser instantáneo, no un viaje al servidor por cada tecla. */

async function elegirInsumo(alElegir, { titulo = 'Elegir insumo', excluir = [] } = {}) {
  const hoja = abrirHoja({ titulo, cuerpo: cargando() });
  let insumos = [];
  try {
    insumos = (await Cache.insumos()).filter((i) => !excluir.includes(i.id));
  } catch (e) {
    hoja.cuerpo.innerHTML = errorEnPantalla(e);
    return;
  }

  hoja.cuerpo.innerHTML = `
    <div class="buscador">
      ${icono('lupa', 'lupa')}
      <input type="search" id="sel-buscar" placeholder="Buscar un insumo…" autocomplete="off">
    </div>
    <div class="lista" id="sel-lista"></div>`;

  const lista = hoja.cuerpo.querySelector('#sel-lista');
  const campo = hoja.cuerpo.querySelector('#sel-buscar');

  const pintar = () => {
    const texto = campo.value.trim().toLowerCase();
    const items = insumos.filter((i) => !texto ||
      String(i.nombre).toLowerCase().includes(texto) ||
      String(i.categoria || '').toLowerCase().includes(texto));

    if (!items.length) {
      lista.innerHTML = vacio(insumos.length ? 'Ninguno coincide' : 'No hay insumos activos');
      return;
    }
    lista.innerHTML = items.map((i) => `
      <button class="item" data-elegir="${i.id}">
        <div class="item-fila">
          <div class="item-cuerpo">
            <div class="item-nombre">${esc(i.nombre)}</div>
            <div class="item-sub">${esc([i.categoria, i.subcategoria].filter(Boolean).join(' · ') || 'Sin categoría')}</div>
          </div>
          <div class="item-derecha">
            <div class="item-numero">${fmtCant(i.stock.cantidad_pantalla)}<small> ${esc(unidadTxt(unidadDe(i), i.stock.cantidad_pantalla))}</small></div>
            <div class="item-sub">${fmtCant(i.peso_unitario_g)} g c/u</div>
          </div>
        </div>
      </button>`).join('');

    lista.querySelectorAll('[data-elegir]').forEach((b) => {
      b.addEventListener('click', () => {
        const elegido = insumos.find((i) => i.id === Number(b.dataset.elegir));
        volverAtras(hoja);
        alElegir(elegido);
      });
    });
  };

  campo.addEventListener('input', demorar(pintar, 120));
  pintar();
  setTimeout(() => campo.focus(), 80);
}
