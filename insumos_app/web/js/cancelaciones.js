/* ============================================================
   INSUMOS — ASÍ FUE DECO · CANCELAR UNA VENTA

   Cancelar devuelve al stock lo que esa venta descontó. Es lo que corresponde
   cuando una orden se cae en Mercado Libre o cuando Mercado Pago reporta un
   pago reintegrado.

   LO QUE LA PANTALLA TIENE QUE DEJAR CLARO, PORQUE ES LA DECISIÓN CENTRAL
   DEL BACKEND: se revierten LOS MOVIMIENTOS QUE REALMENTE SE HICIERON, no se
   recalcula la receta. Si entre la venta y la cancelación alguien editó la
   receta del artículo, recalcular devolvería una cantidad distinta de la que
   se descontó y el stock quedaría mal sin que nada falle.

   Tres comportamientos que la pantalla anticipa en vez de sorprender con
   ellos:

   · Cancelar dos veces no devuelve dos veces.
   · Una venta que nunca descontó (le faltaba la receta o el mapeo, o era
     anterior a la fecha de corte) se marca cancelada sin movimientos.
   · `cancelada` es terminal: sale de la cola de pendientes y no puede volver
     a descontar por ningún camino.
   ============================================================ */

const Cancelaciones = { canal: '', estado: 'procesada' };

async function cargarCancelaciones() {
  const caja = el('p-cancelaciones');
  caja.innerHTML = `
    <div class="tarjeta">
      <div class="bloque-titulo">Buscar una venta</div>
      <div class="ayuda">Por su identificador, si lo tenés a mano.</div>
      <div class="rejilla-2" style="margin-top:14px;margin-bottom:12px">
        <div class="campo">
          <label for="cn-canal">Canal</label>
          <select id="cn-canal">
            ${CANALES_VENTA_UI.map(([v, t]) => `<option value="${v}">${esc(nombreCanal(v))}</option>`).join('')}
          </select>
        </div>
        <div class="campo">
          <label for="cn-id">Identificador</label>
          <input type="text" id="cn-id" placeholder="2000001" autocomplete="off" enterkeyhint="search">
        </div>
      </div>
      <button class="btn btn-bloque" id="cn-buscar">${icono('lupa')} Buscar</button>
    </div>

    <div class="seccion-cabecera">
      <h2>Ventas registradas</h2>
    </div>
    <div class="filtros">
      <select id="cn-filtro-canal" aria-label="Canal">
        <option value="">Todos los canales</option>
        ${CANALES_VENTA_UI.map(([v]) => `<option value="${v}">${esc(nombreCanal(v))}</option>`).join('')}
      </select>
      <select id="cn-filtro-estado" aria-label="Estado">
        <option value="">Todos los estados</option>
        <option value="procesada">Procesadas</option>
        <option value="pendiente_receta">Falta la receta</option>
        <option value="pendiente_mapeo">Falta la publicación</option>
        <option value="ignorada_fecha_corte">Anteriores al corte</option>
        <option value="cancelada">Canceladas</option>
      </select>
    </div>
    <div id="cn-lista">${cargando()}</div>`;

  el('cn-buscar').addEventListener('click', buscarVentaPorId);
  el('cn-id').addEventListener('keydown', (e) => { if (e.key === 'Enter') buscarVentaPorId(); });

  const fc = el('cn-filtro-canal');
  const fe = el('cn-filtro-estado');
  fc.value = Cancelaciones.canal;
  fe.value = Cancelaciones.estado;
  fc.addEventListener('change', () => { Cancelaciones.canal = fc.value; pintarVentasCancelables(); });
  fe.addEventListener('change', () => { Cancelaciones.estado = fe.value; pintarVentasCancelables(); });

  pintarVentasCancelables();
}

async function pintarVentasCancelables() {
  const caja = el('cn-lista');
  if (!caja) return;
  caja.innerHTML = cargando();
  try {
    const r = await API.get('/ventas', {
      canal: Cancelaciones.canal || undefined,
      estado: Cancelaciones.estado || undefined,
      limit: 40,
    });
    if (!r.ventas.length) {
      caja.innerHTML = vacio('No hay ventas con esos filtros');
      return;
    }
    caja.innerHTML = `
      <div class="lista doble">${r.ventas.map(filaVenta).join('')}</div>
      <div class="ayuda" style="margin-top:10px">
        ${r.ventas.length} de ${fmt(r.total)} ventas.
      </div>`;
    caja.querySelectorAll('[data-venta]').forEach((b) => {
      b.addEventListener('click', () => abrirFichaVenta(b.dataset.canal, b.dataset.venta));
    });
  } catch (e) {
    if (e instanceof ErrorAuth) { pedirIngreso(e.message); return; }
    caja.innerHTML = errorEnPantalla(e, 'pintarVentasCancelables()');
  }
}

async function buscarVentaPorId() {
  const canal = el('cn-canal').value;
  const idExterno = el('cn-id').value.trim();
  if (!idExterno) { globo('Escribí el identificador.', 'mal'); return; }

  try {
    await API.get(`/ventas/${encodeURIComponent(canal)}/${encodeURIComponent(idExterno)}`);
    abrirFichaVenta(canal, idExterno);
  } catch (e) {
    // No encontrarla es un caso con salida propia, no un error a secas:
    // registrar la cancelación de una orden que nunca vimos PROTEGE el stock.
    abrirHoja({
      titulo: 'No hay ninguna venta así',
      cuerpo: `
        <div class="aviso atencion">
          <strong>${esc(nombreCanal(canal))} · ${esc(idExterno)}</strong>
          Este sistema no tiene registrada esa venta. Revisá el identificador.
        </div>
        <div class="ayuda">
          Si <strong>sabés</strong> que esa orden existió y se canceló en el canal, podés
          dejar constancia igual. No hay stock que devolver, pero la constancia
          <strong>protege el stock</strong>: si más adelante una sincronización atrasada
          trajera esa orden como venta nueva, el registro la frena y no descuenta algo que
          ya estaba cancelado.
        </div>`,
      acciones: [
        { texto: 'Cerrar', clase: 'btn-borde', alTocar: (h) => volverAtras(h) },
        {
          texto: 'Dejar constancia',
          clase: 'btn-borde',
          alTocar: (h) => { volverAtras(h); cancelarVenta(canal, idExterno, { registrarSiNoExiste: true }); },
        },
      ],
    });
  }
}

/* ── Ficha de una venta ───────────────────────────────────── */

async function abrirFichaVenta(canal, idExterno) {
  const hoja = abrirHoja({
    titulo: 'Venta',
    subtitulo: `${nombreCanal(canal)} · ${idExterno}`,
    cuerpo: cargando(),
  });

  try {
    const v = await API.get(`/ventas/${encodeURIComponent(canal)}/${encodeURIComponent(idExterno)}`);
    let items = [];
    try { items = JSON.parse(v.items_json || '[]'); } catch (e) { items = []; }

    const cancelada = v.estado === 'cancelada';
    const descontoAlgo = (v.movimientos || []).some((m) => m.tipo === 'venta');

    hoja.cuerpo.innerHTML = `
      <div class="tarjeta">
        <div class="item-pie" style="margin-top:0;margin-bottom:12px">
          ${insigniaEstado(v.estado)}
          ${v.estado_previo ? `<span class="insignia">Antes de cancelar: ${esc(v.estado_previo)}</span>` : ''}
        </div>
        <table class="tabla" style="min-width:0">
          <tr><td>Canal</td><td class="num">${esc(nombreCanal(v.canal))}</td></tr>
          <tr><td>Identificador</td><td class="num">${esc(v.id_externo)}</td></tr>
          <tr><td>Fecha de la venta</td><td class="num">${v.fecha_venta ? fmtFecha(v.fecha_venta) : '—'}</td></tr>
          <tr><td>Procesada el</td><td class="num">${fmtFecha(v.fecha_proceso)}</td></tr>
          ${v.fecha_cancelacion ? `<tr><td>Cancelada el</td><td class="num">${fmtFecha(v.fecha_cancelacion)}</td></tr>` : ''}
        </table>
        ${v.detalle ? `<div class="ayuda" style="margin-top:10px">${esc(v.detalle)}</div>` : ''}
      </div>

      ${items.length ? `
        <div class="tarjeta">
          <div class="bloque-titulo">Ítems de la venta</div>
          <table class="tabla" style="min-width:0">
            ${items.map((it) => `<tr>
              <td>${it.articulo_id
                    ? `Artículo #${esc(it.articulo_id)}`
                    : esc(it.id_externo_item || '—')}
                  ${it.variacion_externa ? `<div style="font-size:11px;color:var(--gray-600)">variación ${esc(it.variacion_externa)}</div>` : ''}</td>
              <td class="num">${fmtCant(it.cantidad)}</td>
            </tr>`).join('')}
          </table>
        </div>` : ''}

      <div class="tarjeta">
        <div class="bloque-titulo">Movimientos de stock que generó</div>
        ${(v.movimientos || []).length ? `
          <div class="tabla-marco">
            <table class="tabla">
              <thead><tr><th>Insumo</th><th>Tipo</th><th style="text-align:right">Unidades</th></tr></thead>
              <tbody>${v.movimientos.map((m) => {
                const suma = Number(m.cantidad_unidades) >= 0;
                return `<tr>
                  <td>${esc(m.insumo)}${m.articulo ? `<div style="font-size:11px;color:var(--gray-600)">${esc(m.articulo)}</div>` : ''}</td>
                  <td><span class="insignia ${suma ? 'verde' : 'roja'}">${esc(nombreTipo(m.tipo))}</span></td>
                  <td class="num ${suma ? 'suma' : 'resta'}">${suma ? '+' : ''}${fmtCant(m.cantidad_unidades)}</td>
                </tr>`;
              }).join('')}</tbody>
            </table>
          </div>
          ${cancelada ? `<div class="ayuda" style="margin-top:10px">
            Las filas de <strong>devolución</strong> son la restitución: cada una es el
            opuesto exacto de un consumo de esta venta.</div>` : ''}`
        : `<div class="ayuda">Ninguno: esta venta nunca descontó stock.</div>`}
      </div>

      ${cancelada ? `
        <div class="aviso neutro">
          <strong>Ya está cancelada</strong>
          Y es terminal: no puede volver a descontar stock por ningún camino, ni por un
          reproceso ni si el canal reenvía la orden.
        </div>`
      : `
        <div class="aviso atencion">
          <strong>Qué pasa si la cancelás</strong>
          ${descontoAlgo
            ? 'Se devuelve al stock <strong>exactamente lo que esta venta descontó</strong>, leído del libro mayor. No se recalcula la receta: si cambió desde la venta, recalcular devolvería una cantidad distinta de la descontada.'
            : 'Esta venta no descontó nada, así que no hay nada que devolver. Queda marcada como cancelada y <strong>sale de la cola de pendientes</strong>, para que no pueda descontar más adelante.'}
        </div>
        <button class="btn btn-malo btn-bloque btn-grande" id="cn-cancelar">
          ${descontoAlgo ? 'Cancelar y devolver el stock' : 'Marcar como cancelada'}
        </button>`}`;

    const boton = hoja.cuerpo.querySelector('#cn-cancelar');
    if (boton) {
      boton.addEventListener('click', () => {
        volverAtras(hoja);
        pedirMotivoYCancelar(canal, idExterno, descontoAlgo);
      });
    }
  } catch (e) {
    hoja.cuerpo.innerHTML = errorEnPantalla(e);
  }
}

function pedirMotivoYCancelar(canal, idExterno, descontoAlgo) {
  const hoja = abrirHoja({
    titulo: '¿Cancelar la venta?',
    subtitulo: `${nombreCanal(canal)} · ${idExterno}`,
    cuerpo: `
      <div class="aviso ${descontoAlgo ? 'atencion' : 'neutro'}">
        <strong>${descontoAlgo
          ? 'Se va a devolver al stock lo que esta venta descontó'
          : 'Esta venta no descontó stock: no hay nada que devolver'}</strong>
        Cancelar dos veces no devuelve dos veces, así que si no estás seguro de haberlo hecho
        ya, podés volver a intentarlo sin riesgo.
      </div>
      <div class="campo">
        <label for="cn-motivo">Motivo <span class="opt">· opcional, queda en el libro mayor</span></label>
        <input type="text" id="cn-motivo" placeholder="Cancelada en Mercado Libre" autocomplete="off">
      </div>
      <div class="campo">
        <label for="cn-usuario">Quién la cancela <span class="opt">· opcional</span></label>
        <input type="text" id="cn-usuario" placeholder="Nombre" autocomplete="off">
      </div>`,
    acciones: [
      { texto: 'No cancelar', clase: 'btn-borde', alTocar: (h) => volverAtras(h) },
      {
        texto: 'Sí, cancelar',
        clase: 'btn-malo',
        alTocar: (h, b) => {
          const motivo = h.cuerpo.querySelector('#cn-motivo').value.trim() || null;
          const usuario = h.cuerpo.querySelector('#cn-usuario').value.trim() || null;
          b.disabled = true;
          volverAtras(h);
          cancelarVenta(canal, idExterno, { motivo, usuario });
        },
      },
    ],
  });
  setTimeout(() => hoja.cuerpo.querySelector('#cn-motivo').focus(), 100);
}

async function cancelarVenta(canal, idExterno, { motivo = null, usuario = null, registrarSiNoExiste = false } = {}) {
  try {
    const r = await API.post(
      `/ventas/${encodeURIComponent(canal)}/${encodeURIComponent(idExterno)}/cancelar`,
      { motivo, usuario, registrar_si_no_existe: registrarSiNoExiste });

    Cache.invalidar('insumos');
    mostrarResultadoDeCancelacion(r);
    recargarPantalla();
  } catch (e) {
    globo('No se pudo cancelar: ' + e.message, 'mal');
  }
}

function mostrarResultadoDeCancelacion(r) {
  abrirHoja({
    titulo: 'Venta cancelada',
    subtitulo: `${nombreCanal(r.canal)} · ${r.id_externo}`,
    cuerpo: `
      <div class="aviso ${r.restituyo_stock ? 'bueno' : 'neutro'}">
        <strong>${r.restituyo_stock
          ? `Se devolvieron ${r.movimientos.length} movimiento(s) al stock`
          : (r.ya_estaba_cancelada ? 'Ya estaba cancelada' : 'Cancelada sin devolver stock')}</strong>
        ${r.restituyo_stock
          ? 'Cada devolución es el opuesto exacto de un consumo de esta venta, leído del libro mayor.'
          : (r.ya_estaba_cancelada
            ? 'No se devolvió nada de nuevo: cancelar dos veces no restituye dos veces.'
            : 'Esta venta no había descontado nada, así que no había nada que devolver.')}
      </div>

      ${r.estado_previo ? `<div class="ayuda" style="margin-bottom:12px">
        Antes de cancelarse estaba en estado <strong>${esc(r.estado_previo)}</strong>.
      </div>` : ''}

      ${r.movimientos && r.movimientos.length ? `
        <div class="tarjeta">
          <div class="bloque-titulo">Lo que volvió al stock</div>
          <div class="tabla-marco">
            <table class="tabla">
              <thead><tr><th>Insumo</th><th style="text-align:right">Volvió</th><th style="text-align:right">Queda</th></tr></thead>
              <tbody>${r.movimientos.map((m) => `<tr>
                <td>${esc(m.insumo)}</td>
                <td class="num suma">+${fmtCant(m.cantidad_unidades)} u.</td>
                <td class="num">${fmtCant(m.stock_resultante.cantidad_pantalla)}
                  ${esc(unidadTxt(m.stock_resultante.unidad_pantalla, m.stock_resultante.cantidad_pantalla))}</td>
              </tr>`).join('')}</tbody>
            </table>
          </div>
        </div>` : ''}

      ${bloqueAlertas(r.alertas)}
      ${listaAvisos(r.avisos, 'neutro')}`,
    acciones: [{ texto: 'Listo', clase: 'btn', alTocar: (h) => volverAtras(h) }],
  });
}
