/* ============================================================
   INSUMOS — ASÍ FUE DECO · pantalla de STOCK

   Tres cosas: cargar un ingreso, registrar un conteo de inventario y ver el
   historial de movimientos.

   LA DIFERENCIA ENTRE "INGRESO" Y "CONTEO" ES LA QUE MÁS SE PRESTA A
   CONFUSIÓN, así que las dos pantallas lo dicen con todas las letras:

     · Un INGRESO se SUMA a lo que hay. Entraron 2 kg → el stock sube 2 kg.
     · Un CONTEO reemplaza el total. Conté 2 kg → el stock QUEDA en 2 kg, y
       el sistema asienta la diferencia contra lo que tenía.

   Cargar un conteo creyendo que era un ingreso es la forma más fácil de
   borrar stock sin darse cuenta, y al revés, de duplicarlo.

   El stock nunca se escribe directo: siempre entra un movimiento al libro
   mayor y el backend recalcula el saldo. Es lo que permite reconstruir el
   stock sumando movimientos, y por eso esta pantalla no tiene ningún campo
   que diga "stock".
   ============================================================ */

const Movs = { tipo: '' };

async function cargarStock() {
  const caja = el('p-stock');
  caja.innerHTML = `
    <div class="fila-botones" style="margin-bottom:16px">
      <button class="btn btn-grande" id="s-ingreso">${icono('mas')} Cargar ingreso</button>
      <button class="btn btn-borde btn-grande" id="s-conteo">Conteo de inventario</button>
    </div>

    <div class="ayuda" style="margin-bottom:18px">
      <strong>Ingreso</strong>: se suma a lo que hay (compraste más material).
      <strong>Conteo</strong>: reemplaza el total (contaste lo que hay en el taller y el
      sistema corrige la diferencia).
    </div>

    <div class="seccion-cabecera">
      <h2>Últimos movimientos</h2>
    </div>
    <div class="filtros">
      <select id="s-filtro-tipo" aria-label="Tipo de movimiento">
        <option value="">Todos los tipos</option>
        <option value="ingreso">Ingresos</option>
        <option value="venta">Ventas</option>
        <option value="ajuste">Ajustes</option>
        <option value="merma">Mermas</option>
        <option value="devolucion">Devoluciones</option>
        <option value="inventario_inicial">Inventario inicial</option>
      </select>
    </div>
    <div class="tarjeta" id="s-movimientos">${cargando()}</div>`;

  el('s-ingreso').addEventListener('click', () =>
    elegirInsumo((i) => abrirMovimiento(i), { titulo: '¿A qué insumo le cargás stock?' }));
  el('s-conteo').addEventListener('click', () =>
    elegirInsumo((i) => abrirConteo(i), { titulo: '¿Qué insumo contaste?' }));

  const filtro = el('s-filtro-tipo');
  filtro.value = Movs.tipo;
  filtro.addEventListener('change', () => { Movs.tipo = filtro.value; pintarMovimientosGlobales(); });

  pintarMovimientosGlobales();
}

async function pintarMovimientosGlobales() {
  const caja = el('s-movimientos');
  if (!caja) return;
  caja.innerHTML = cargando();
  try {
    const r = await API.get('/movimientos', { limit: 60, tipo: Movs.tipo || undefined });
    if (!r.movimientos.length) {
      caja.innerHTML = vacio('Todavía no hay movimientos',
        '<div class="ayuda" style="margin-top:6px">El primer movimiento de stock del sistema fija la fecha de corte.</div>');
      return;
    }
    caja.innerHTML = `
      <div class="tabla-marco">
        <table class="tabla">
          <thead><tr>
            <th>Fecha</th><th>Insumo</th><th>Movimiento</th><th style="text-align:right">Cantidad</th>
          </tr></thead>
          <tbody>${r.movimientos.map(filaMovimiento).join('')}</tbody>
        </table>
      </div>
      <div class="ayuda" style="margin-top:10px">
        Mostrando ${r.movimientos.length} de ${fmt(r.total)} movimientos.
      </div>`;
  } catch (e) {
    if (e instanceof ErrorAuth) { pedirIngreso(e.message); return; }
    caja.innerHTML = errorEnPantalla(e, 'pintarMovimientosGlobales()');
  }
}

function filaMovimiento(m) {
  const suma = Number(m.cantidad_pantalla) >= 0;
  const detalle = [
    m.articulo ? esc(m.articulo) : '',
    m.origen_canal ? `${esc(nombreCanal(m.origen_canal))} ${esc(m.referencia_externa || '')}` : '',
    m.nota ? esc(m.nota) : '',
  ].filter(Boolean)[0] || '';

  return `<tr>
    <td class="cell-muted" style="white-space:nowrap;font-size:12px">${fmtFecha(m.fecha)}</td>
    <td><strong style="font-weight:600">${esc(m.insumo)}</strong>
      ${detalle ? `<div style="font-size:11px;color:var(--gray-600)">${detalle}</div>` : ''}</td>
    <td><span class="insignia ${m.tipo === 'venta' ? 'roja' : (suma ? 'verde' : 'naranja')}">${esc(nombreTipo(m.tipo))}</span></td>
    <td class="num ${suma ? 'suma' : 'resta'}">
      ${suma ? '+' : ''}${fmtCant(m.cantidad_pantalla)}
      <div style="font-size:10.5px;font-weight:600;color:var(--gray-600)">${esc(m.unidad_pantalla)}</div>
    </td>
  </tr>`;
}

/* ── Movimiento manual (ingreso, merma, ajuste, devolución) ── */

const TIPOS_MANUALES = [
  ['ingreso', 'Ingreso', 'Compraste material: se SUMA al stock.'],
  ['merma', 'Merma', 'Se rompió o se descartó: se RESTA del stock.'],
  ['devolucion', 'Devolución', 'Volvió material: se SUMA al stock.'],
  ['ajuste', 'Ajuste', 'Corrección con signo: escribí un número negativo para restar.'],
];

function abrirMovimiento(insumo, tipoInicial = 'ingreso') {
  const u = unidadDe(insumo);

  const hoja = abrirHoja({
    titulo: 'Cargar movimiento',
    subtitulo: insumo.nombre,
    cuerpo: `
      ${unidadAviso(insumo, { accion: 'Vas a cargar' })}

      <div class="campo">
        <label>Qué movimiento es</label>
        <select id="m-tipo">
          ${TIPOS_MANUALES.map(([v, t]) => `<option value="${v}" ${v === tipoInicial ? 'selected' : ''}>${t}</option>`).join('')}
        </select>
        <div class="pie" id="m-tipo-ayuda"></div>
      </div>

      ${campoCantidad({
        id: 'm-cantidad',
        etiqueta: 'Cantidad',
        unidad: u,
        pie: 'El signo lo pone el tipo de movimiento: una merma cargada en positivo igual resta.',
        autofoco: true,
      })}

      <div class="tarjeta" style="padding:13px;margin-bottom:14px">
        <div class="ayuda">
          Stock de hoy: <strong>${fmtCant(insumo.stock.cantidad_pantalla)} ${esc(unidadTxt(u, insumo.stock.cantidad_pantalla))}</strong>
          ${u === 'kg' ? ` (${fmt(Math.round(insumo.stock.unidades))} unidades)` : ''}
        </div>
        <div class="ayuda" id="m-proyeccion" style="margin-top:4px"></div>
      </div>

      <div class="campo">
        <label for="m-nota">Nota <span class="opt">· opcional</span></label>
        <input type="text" id="m-nota" placeholder="Compra a proveedor, rotura al armar…" autocomplete="off">
      </div>
      <div class="campo">
        <label for="m-usuario">Quién lo carga <span class="opt">· opcional</span></label>
        <input type="text" id="m-usuario" placeholder="Nombre" autocomplete="off">
      </div>`,
    acciones: [
      { texto: 'Cancelar', clase: 'btn-borde', alTocar: (h) => volverAtras(h) },
      { texto: 'Cargar', clase: 'btn', alTocar: (h, b) => guardarMovimiento(insumo, h, b) },
    ],
  });

  const tipo = hoja.cuerpo.querySelector('#m-tipo');
  const ayuda = hoja.cuerpo.querySelector('#m-tipo-ayuda');
  const cantidad = hoja.cuerpo.querySelector('#m-cantidad');
  const proyeccion = hoja.cuerpo.querySelector('#m-proyeccion');

  const refrescar = () => {
    const def = TIPOS_MANUALES.find(([v]) => v === tipo.value);
    ayuda.textContent = def ? def[2] : '';

    // Proyección del saldo: resta de números ya en unidad de pantalla, solo
    // para que se vea a dónde va a quedar el stock antes de confirmar. El
    // número real lo calcula y lo devuelve el backend.
    const n = num(cantidad.value);
    if (!isFinite(n) || n === 0) { proyeccion.innerHTML = ''; return; }
    const signo = tipo.value === 'merma' ? -1 : (tipo.value === 'ajuste' ? 1 : 1);
    const delta = tipo.value === 'ajuste' ? n : Math.abs(n) * signo;
    const final = Number(insumo.stock.cantidad_pantalla) + delta;
    proyeccion.innerHTML = `Va a quedar en <strong>${fmtCant(final)} ${esc(unidadTxt(u, final))}</strong>` +
      (final < 0 ? ' — <strong style="color:var(--red)">en negativo</strong>' : '');
  };

  tipo.addEventListener('change', refrescar);
  cantidad.addEventListener('input', refrescar);
  vincularEquivalencia('m-cantidad', insumo);
  refrescar();
  setTimeout(() => cantidad.focus(), 120);
}

async function guardarMovimiento(insumo, hoja, boton) {
  const q = (sel) => hoja.cuerpo.querySelector(sel);
  const cantidad = num(q('#m-cantidad').value);
  const tipo = q('#m-tipo').value;

  if (!isFinite(cantidad) || cantidad === 0) {
    globo('Escribí una cantidad distinta de cero.', 'mal');
    q('#m-cantidad').focus();
    return;
  }

  boton.disabled = true;
  boton.textContent = 'Cargando…';
  try {
    const r = await API.post('/movimientos', {
      insumo_id: insumo.id,
      cantidad,
      tipo,
      nota: q('#m-nota').value.trim() || null,
      usuario: q('#m-usuario').value.trim() || null,
    });
    Cache.invalidar('insumos');
    volverAtras(hoja);
    mostrarResultadoDeStock(insumo, r, nombreTipo(tipo) + ' cargado');
  } catch (e) {
    globo('No se pudo cargar: ' + e.message, 'mal');
  } finally {
    boton.disabled = false;
    boton.textContent = 'Cargar';
  }
}

/* ── Conteo de inventario ─────────────────────────────────── */

function abrirConteo(insumo) {
  const u = unidadDe(insumo);

  const hoja = abrirHoja({
    titulo: 'Conteo de inventario',
    subtitulo: insumo.nombre,
    cuerpo: `
      <div class="aviso atencion">
        <strong>Esto reemplaza el total, no suma</strong>
        Escribí <strong>cuánto hay en total</strong> después de contarlo. El sistema calcula
        la diferencia contra lo que tenía registrado y asienta esa diferencia.
        Si lo que querés es sumar material que entró, cerrá esto y usá
        <strong>Cargar ingreso</strong>.
      </div>

      ${unidadAviso(insumo, { accion: 'Contá y escribí el total' })}

      ${campoCantidad({
        id: 'c-cantidad',
        etiqueta: `Total contado`,
        unidad: u,
        valor: '',
        autofoco: true,
      })}

      <div class="tarjeta" style="padding:13px;margin-bottom:14px">
        <div class="ayuda">
          El sistema tiene registrado:
          <strong>${fmtCant(insumo.stock.cantidad_pantalla)} ${esc(unidadTxt(u, insumo.stock.cantidad_pantalla))}</strong>
        </div>
        <div class="ayuda" id="c-diferencia" style="margin-top:4px"></div>
      </div>

      <div class="campo">
        <label for="c-nota">Nota <span class="opt">· opcional</span></label>
        <input type="text" id="c-nota" placeholder="Conteo del 27/10" autocomplete="off">
      </div>
      <div class="campo">
        <label for="c-usuario">Quién contó <span class="opt">· opcional</span></label>
        <input type="text" id="c-usuario" placeholder="Nombre" autocomplete="off">
      </div>`,
    acciones: [
      { texto: 'Cancelar', clase: 'btn-borde', alTocar: (h) => volverAtras(h) },
      { texto: 'Registrar conteo', clase: 'btn', alTocar: (h, b) => guardarConteo(insumo, h, b) },
    ],
  });

  const campo = hoja.cuerpo.querySelector('#c-cantidad');
  const diferencia = hoja.cuerpo.querySelector('#c-diferencia');

  const refrescar = () => {
    const n = num(campo.value);
    if (!isFinite(n)) { diferencia.innerHTML = ''; return; }
    const delta = n - Number(insumo.stock.cantidad_pantalla);
    if (Math.abs(delta) < 1e-9) {
      diferencia.innerHTML = 'Coincide con lo registrado: no se va a asentar ningún movimiento.';
      return;
    }
    diferencia.innerHTML = `Se va a asentar un movimiento de
      <strong style="color:${delta > 0 ? 'var(--green-ok)' : 'var(--red)'}">
      ${delta > 0 ? '+' : ''}${fmtCant(delta)} ${esc(unidadTxt(u, delta))}</strong>.`;
  };

  campo.addEventListener('input', refrescar);
  vincularEquivalencia('c-cantidad', insumo);
  setTimeout(() => campo.focus(), 120);
}

async function guardarConteo(insumo, hoja, boton) {
  const q = (sel) => hoja.cuerpo.querySelector(sel);
  const cantidad = num(q('#c-cantidad').value);

  if (!isFinite(cantidad) || cantidad < 0) {
    globo('Escribí el total contado (0 o más).', 'mal');
    q('#c-cantidad').focus();
    return;
  }

  boton.disabled = true;
  boton.textContent = 'Registrando…';
  try {
    const r = await API.post(`/insumos/${insumo.id}/stock`, {
      cantidad,
      nota: q('#c-nota').value.trim() || null,
      usuario: q('#c-usuario').value.trim() || null,
    });
    Cache.invalidar('insumos');
    volverAtras(hoja);
    if (r.sin_cambios) {
      globo('El conteo coincidía: no hizo falta ningún movimiento.');
      recargarPantalla();
    } else {
      mostrarResultadoDeStock(insumo, r, 'Conteo registrado');
    }
  } catch (e) {
    globo('No se pudo registrar: ' + e.message, 'mal');
  } finally {
    boton.disabled = false;
    boton.textContent = 'Registrar conteo';
  }
}

/* ── Resultado de una escritura de stock ──────────────────────

   Se muestra en una hoja y no en un aviso al pasar porque trae dos cosas
   que hay que leer: las alertas que se cruzaron con este movimiento y, la
   primera vez, el hecho de que se acaba de FIJAR LA FECHA DE CORTE, que
   decide qué ventas se van a descontar de ahora en más. */

function mostrarResultadoDeStock(insumo, r, titulo) {
  const u = unidadDe(insumo);
  abrirHoja({
    titulo,
    subtitulo: insumo.nombre,
    cuerpo: `
      <div class="tarjeta" style="text-align:center">
        <div class="ayuda">Stock ahora</div>
        <div style="font-family:'Space Grotesk',sans-serif;font-size:36px;font-weight:700;line-height:1.1;
                    ${r.stock.unidades < 0 ? 'color:var(--red)' : ''}">
          ${fmtCant(r.stock.cantidad_pantalla)}<span style="font-size:16px"> ${esc(unidadTxt(u, r.stock.cantidad_pantalla))}</span>
        </div>
        <div class="ayuda" style="margin-top:4px">
          ${u === 'kg' ? `${fmt(Math.round(r.stock.unidades))} unidades` : `${fmtCant(r.stock.kg)} kg`}
        </div>
      </div>

      ${r.fecha_corte_fijada ? `
        <div class="aviso atencion">
          <strong>Se fijó la fecha de corte: ${fmtDia(r.fecha_corte_fijada)}</strong>
          Era la primera carga de stock del sistema, así que esa fecha queda como el
          arranque del inventario: <strong>ninguna venta anterior a hoy va a descontar
          stock</strong>. Si el inventario que estás cargando es de otra fecha, corregila
          en Ajustes.
        </div>` : ''}

      ${bloqueAlertas(r.alertas)}

      <div class="ayuda">
        Quedó asentado en el libro mayor como movimiento
        ${r.movimiento_id ? `#${r.movimiento_id}` : ''}
        ${r.tipo ? `de tipo <strong>${esc(nombreTipo(r.tipo))}</strong>` : ''}.
        El stock no se escribe a mano: se recalcula sumando los movimientos.
      </div>`,
    acciones: [
      { texto: 'Listo', clase: 'btn', alTocar: (h) => { volverAtras(h); recargarPantalla(); } },
    ],
    alCerrar: () => recargarPantalla(),
  });
}

/* ── Historial de un insumo ───────────────────────────────── */

async function abrirMovimientosDeInsumo(insumo) {
  const hoja = abrirHoja({
    titulo: 'Movimientos',
    subtitulo: insumo.nombre,
    cuerpo: cargando(),
  });

  try {
    const r = await API.get(`/insumos/${insumo.id}/movimientos`, { limit: 200 });
    if (!r.movimientos.length) {
      hoja.cuerpo.innerHTML = vacio('Este insumo todavía no tiene movimientos');
      return;
    }
    hoja.cuerpo.innerHTML = `
      <div class="ayuda" style="margin-bottom:12px">
        El saldo de la última fila es el stock actual: ${fmtCant(r.stock.cantidad_pantalla)}
        ${esc(unidadTxt(r.unidad_pantalla, r.stock.cantidad_pantalla))}. La columna "saldo" es la suma de todo lo anterior, así que
        cualquier número se puede explicar leyendo hacia arriba.
      </div>
      <div class="tabla-marco">
        <table class="tabla">
          <thead><tr>
            <th>Fecha</th><th>Movimiento</th>
            <th style="text-align:right">Cantidad</th><th style="text-align:right">Saldo</th>
          </tr></thead>
          <tbody>${r.movimientos.map((m) => {
            const suma = Number(m.cantidad_pantalla) >= 0;
            const detalle = [
              m.articulo ? `Artículo: ${esc(m.articulo)}` : '',
              m.origen_canal ? `${esc(nombreCanal(m.origen_canal))} ${esc(m.referencia_externa || '')}` : '',
              m.nota ? esc(m.nota) : '',
              m.usuario ? `por ${esc(m.usuario)}` : '',
            ].filter(Boolean).join(' · ');
            return `<tr>
              <td style="white-space:nowrap;font-size:12px">${fmtFecha(m.fecha)}</td>
              <td><span class="insignia ${m.tipo === 'venta' ? 'roja' : (suma ? 'verde' : 'naranja')}">${esc(nombreTipo(m.tipo))}</span>
                ${detalle ? `<div style="font-size:11px;color:var(--gray-600);margin-top:3px">${detalle}</div>` : ''}</td>
              <td class="num ${suma ? 'suma' : 'resta'}">${suma ? '+' : ''}${fmtCant(m.cantidad_pantalla)}</td>
              <td class="num">${fmtCant(m.saldo_pantalla)}</td>
            </tr>`;
          }).join('')}</tbody>
        </table>
      </div>
      <div class="ayuda" style="margin-top:10px">
        ${r.movimientos.length} de ${fmt(r.total)} movimientos, del más nuevo al más viejo.
      </div>`;
  } catch (e) {
    hoja.cuerpo.innerHTML = errorEnPantalla(e);
  }
}
