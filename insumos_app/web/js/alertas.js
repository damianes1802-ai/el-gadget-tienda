/* ============================================================
   INSUMOS — ASÍ FUE DECO · pantalla de ALERTAS

   Es la pantalla con la que abre la aplicación, porque es la única que
   contesta la pregunta con la que alguien entra: ¿qué me está por faltar?

   Muestra cuatro cosas, en orden de qué tan mal está cada una:

   1. Insumos en NEGATIVO: se vendió material que no estaba cargado. El
      backend asienta esas ventas igual —rechazarlas sería perder el dato
      real— y avisa; se arregla con un conteo.
   2. Insumos en o por debajo de su umbral.
   3. Ventas pendientes: mientras haya, el stock está SOBREESTIMADO, porque
      esas ventas no descontaron nada. Se cierran con un reproceso una vez
      cargada la receta o la publicación que faltaba.
   4. Artículos sin receta: no tienen peso de envío, así que no se pueden
      cotizar. Es, literalmente, para lo que existe este sistema.
   ============================================================ */

async function cargarAlertas() {
  const caja = el('p-alertas');
  caja.innerHTML = cargando('Buscando lo que falta…');

  try {
    const [alertas, salud, sinReceta, auditoria] = await Promise.all([
      API.get('/alertas'),
      fetch(RAIZ + '/salud').then((r) => r.json()),
      API.get('/articulos', { activo: true, sin_receta: true }),
      API.get('/auditoria/stock'),
    ]);

    const negativos = alertas.alertas.filter((a) => a.stock_negativo);
    const bajos = alertas.alertas.filter((a) => !a.stock_negativo);
    const pendientes = salud.ventas_pendientes || 0;

    caja.innerHTML = `
      <div class="cifras">
        <div class="cifra ${negativos.length ? 'mala' : 'bien'}">
          <div class="cifra-valor">${fmt(negativos.length)}</div>
          <div class="cifra-rotulo">En negativo</div>
        </div>
        <div class="cifra ${bajos.length ? 'mala' : 'bien'}">
          <div class="cifra-valor">${fmt(bajos.length)}</div>
          <div class="cifra-rotulo">Stock bajo</div>
        </div>
        <div class="cifra ${pendientes ? 'mala' : 'bien'}">
          <div class="cifra-valor">${fmt(pendientes)}</div>
          <div class="cifra-rotulo">Ventas pendientes</div>
        </div>
        <div class="cifra ${sinReceta.length ? 'mala' : 'bien'}">
          <div class="cifra-valor">${fmt(sinReceta.length)}</div>
          <div class="cifra-rotulo">Sin receta</div>
        </div>
      </div>

      ${auditoria.cuadra ? '' : `
        <div class="aviso malo">
          <strong>El stock no cuadra con el libro mayor</strong>
          ${fmt(auditoria.descuadres.length)} insumo(s) tienen un stock distinto de la suma
          de sus movimientos. Eso significa que algo escribió el stock sin pasar por un
          movimiento. Mirá el detalle en Ajustes → Auditoría.
        </div>`}

      ${pendientes ? `
        <div class="aviso atencion">
          <strong>Hay ${fmt(pendientes)} venta(s) que todavía no descontaron stock</strong>
          Les falta la receta del artículo o la publicación mapeada. Mientras sigan así, el
          stock que ves está <strong>sobreestimado</strong>.
          <div style="margin-top:10px;display:flex;gap:8px;flex-wrap:wrap">
            <button class="btn btn-borde btn-ch" id="ver-pendientes">Ver cuáles</button>
            <button class="btn btn-ch" id="reprocesar-todo">Reprocesar todas</button>
          </div>
        </div>` : ''}

      ${sinReceta.length ? `
        <div class="aviso atencion">
          <strong>${fmt(sinReceta.length)} artículo(s) sin receta</strong>
          Sin receta no hay peso, y sin peso no se puede cotizar el envío.
          <ul>${sinReceta.slice(0, 6).map((a) =>
            `<li>${esc(a.nombre)}</li>`).join('')}
            ${sinReceta.length > 6 ? `<li>…y ${fmt(sinReceta.length - 6)} más</li>` : ''}
          </ul>
          <div style="margin-top:10px">
            <button class="btn btn-borde btn-ch" id="ir-sin-receta">Cargar recetas</button>
          </div>
        </div>` : ''}

      <div class="seccion-cabecera">
        <h2>Insumos para reponer</h2>
      </div>
      <div class="lista doble" id="lista-alertas"></div>`;

    const lista = el('lista-alertas');
    if (!alertas.alertas.length) {
      lista.innerHTML = vacio('Ningún insumo por debajo del umbral',
        '<div class="ayuda" style="margin-top:6px">Si recién estás cargando el catálogo, acordate de ponerle a cada insumo su "avisar cuando queden": sin umbral no hay aviso.</div>');
    } else {
      lista.innerHTML = [...negativos, ...bajos].map(filaAlerta).join('');
      lista.querySelectorAll('[data-insumo]').forEach((b) => {
        b.addEventListener('click', () => abrirFichaInsumo(Number(b.dataset.insumo)));
      });
    }

    const engancharse = (id, fn) => { const b = el(id); if (b) b.addEventListener('click', fn); };
    engancharse('ver-pendientes', verVentasPendientes);
    engancharse('reprocesar-todo', reprocesarPendientes);
    engancharse('ir-sin-receta', () => { irA('articulos'); filtrarArticulosSinReceta(); });
  } catch (e) {
    if (e instanceof ErrorAuth) { pedirIngreso(e.message); return; }
    caja.innerHTML = errorEnPantalla(e, 'cargarAlertas()');
  }
}

function filaAlerta(a) {
  return `
    <button class="item ${a.stock_negativo ? 'negativo' : 'alerta'}" data-insumo="${a.insumo_id}">
      <div class="item-fila">
        <div class="item-cuerpo">
          <div class="item-nombre">${esc(a.nombre)}</div>
          <div class="item-sub">Avisar cuando queden ${fmtCant(a.umbral_pantalla)} ${esc(unidadTxt(a.unidad, a.umbral_pantalla))}</div>
        </div>
        <div class="item-derecha">
          <div class="item-numero" style="${a.stock_negativo ? 'color:var(--red)' : ''}">
            ${fmtCant(a.stock_pantalla)}<small> ${esc(unidadTxt(a.unidad, a.stock_pantalla))}</small>
          </div>
        </div>
      </div>
      <div class="item-pie">
        ${a.stock_negativo
          ? '<span class="insignia roja">En negativo: se vendió sin stock cargado</span>'
          : '<span class="insignia ambar">Hay que reponer</span>'}
      </div>
    </button>`;
}

/* ── Ventas pendientes ────────────────────────────────────── */

async function verVentasPendientes() {
  const hoja = abrirHoja({
    titulo: 'Ventas que no descontaron',
    subtitulo: 'Les falta la receta o la publicación',
    cuerpo: cargando(),
    acciones: [
      { texto: 'Cerrar', clase: 'btn-borde', alTocar: (h) => volverAtras(h) },
      {
        texto: 'Reprocesar todas',
        clase: 'btn',
        alTocar: (h) => { volverAtras(h); reprocesarPendientes(); },
      },
    ],
  });

  try {
    const pendientes = await API.get('/ventas/pendientes');
    if (!pendientes.length) {
      hoja.cuerpo.innerHTML = vacio('No quedan ventas pendientes');
      return;
    }
    hoja.cuerpo.innerHTML = `
      <div class="ayuda" style="margin-bottom:12px">
        Una venta con un ítem sin receta <strong>no descuenta ningún ítem</strong>: queda
        entera acá hasta que se pueda asentar completa. Cargá lo que falta y reprocesá.
      </div>
      <div class="lista">${pendientes.map((v) => `
        <div class="item" style="cursor:default">
          <div class="item-fila">
            <div class="item-cuerpo">
              <div class="item-nombre">${esc(nombreCanal(v.canal))} · ${esc(v.id_externo)}</div>
              <div class="item-sub">${v.fecha_venta ? fmtFecha(v.fecha_venta) : 'sin fecha'}</div>
            </div>
          </div>
          <div class="item-pie">${insigniaEstado(v.estado)}</div>
          ${v.detalle ? `<div class="ayuda" style="margin-top:8px">${esc(v.detalle)}</div>` : ''}
        </div>`).join('')}</div>`;
  } catch (e) {
    hoja.cuerpo.innerHTML = errorEnPantalla(e);
  }
}

async function reprocesarPendientes() {
  if (!await confirmar(
    'Se vuelven a intentar todas las ventas pendientes. Las que ya tengan su receta y su ' +
    'publicación cargadas van a descontar stock ahora. Una venta ya procesada no se ' +
    'descuenta dos veces: eso lo garantiza el sistema.',
    { titulo: '¿Reprocesar pendientes?', textoSi: 'Reprocesar', peligro: false })) return;

  try {
    const r = await API.post('/ventas/pendientes/reprocesar');
    const procesadas = r.resumen && r.resumen.procesada || 0;
    globo(procesadas
      ? `${procesadas} venta(s) descontaron stock.`
      : 'Ninguna pudo descontar todavía: sigue faltando la receta o la publicación.',
      procesadas ? 'bien' : 'mal');
    Cache.invalidar('insumos');
    recargarPantalla();
  } catch (e) {
    globo('No se pudo reprocesar: ' + e.message, 'mal');
  }
}
