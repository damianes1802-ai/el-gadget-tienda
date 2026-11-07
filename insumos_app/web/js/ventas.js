/* ============================================================
   INSUMOS — ASÍ FUE DECO · VENTAS MANUALES

   Para los canales que no se sincronizan solos: una venta por WhatsApp, una
   mayorista, una de Empretienda. Se elige el artículo y la cantidad, y
   descuenta por el mismo motor que las ventas de Mercado Libre — no hay un
   camino "de carga manual" con sus propias reglas.

   DOS COSAS QUE LA PANTALLA EXPLICA PORQUE SE PREGUNTAN SIEMPRE

   1. EL IDENTIFICADOR NO ES DECORACIÓN: es la clave que evita descontar dos
      veces la misma venta. Se propone uno con la fecha y la hora, y se puede
      reemplazar por el número de pedido real. Cargar dos veces el mismo
      identificador no descuenta dos veces, y eso es a propósito.

   2. UNA VENTA ES TODO O NADA. Si un artículo de la venta no tiene receta,
      no se descuenta NINGUNO: la venta queda pendiente, entera, con sus
      ítems guardados, y se cierra sola cuando se carga la receta que
      faltaba. Descontar la mitad obligaría a recordar qué parte ya se
      descontó para no duplicar al reprocesar.
   ============================================================ */

const CANALES_VENTA_UI = [
  ['manual', 'Venta manual (WhatsApp, mayorista, local)'],
  ['empretienda', 'Empretienda'],
  ['elgadget', 'El Gadget'],
  ['ml', 'Mercado Libre'],
];

let lineasDeVenta = [];

async function cargarVentas() {
  const caja = el('p-ventas');
  lineasDeVenta = [];

  const hoy = new Date();
  const iso = `${hoy.getFullYear()}-${String(hoy.getMonth() + 1).padStart(2, '0')}-${String(hoy.getDate()).padStart(2, '0')}`;

  caja.innerHTML = `
    <div class="tarjeta">
      <div class="bloque-titulo">Cargar una venta</div>
      <div class="ayuda">
        Descuenta de una vez todos los insumos de la receta de cada artículo vendido.
      </div>

      <div style="margin-top:14px">
        <div class="campo">
          <label for="v-canal">Canal</label>
          <select id="v-canal">
            ${CANALES_VENTA_UI.map(([v, t]) => `<option value="${v}">${t}</option>`).join('')}
          </select>
          <div class="pie" id="v-canal-ayuda"></div>
        </div>

        <!-- Sin columnas: el identificador es largo y en un celular angosto
             quedaba cortado justo donde hay que leerlo entero. -->
        <div class="campo">
          <label for="v-id">Identificador de la venta</label>
          <input type="text" id="v-id" value="${esc(idVentaManual())}" autocomplete="off">
        </div>
        <div class="campo">
          <label for="v-fecha">Fecha de la venta</label>
          <input type="date" id="v-fecha" value="${iso}">
        </div>
        <div class="ayuda" style="margin-bottom:14px">
          El identificador es lo que evita descontar dos veces la misma venta: si cargás dos
          veces el mismo, el sistema lo detecta y no descuenta de nuevo. Si la venta tiene un
          número de pedido, ponelo acá. Una venta con fecha anterior a la
          <strong>fecha de corte</strong> no descuenta nada, y el sistema lo avisa.
        </div>

        <div class="bloque-titulo" style="margin-bottom:8px">Artículos vendidos</div>
        <div id="v-lineas"></div>
        <button class="btn btn-borde btn-bloque" id="v-agregar" style="margin-top:10px">
          ${icono('mas')} Agregar artículo
        </button>

        <div class="campo" style="margin-top:14px">
          <label for="v-nota">Nota <span class="opt">· opcional</span></label>
          <input type="text" id="v-nota" placeholder="Pedido de Laura por WhatsApp" autocomplete="off">
        </div>
        <div class="campo">
          <label for="v-usuario">Quién la carga <span class="opt">· opcional</span></label>
          <input type="text" id="v-usuario" placeholder="Nombre" autocomplete="off">
        </div>

        <button class="btn btn-grande btn-bloque" id="v-procesar">Descontar stock</button>
      </div>
    </div>

    <div class="seccion-cabecera">
      <h2>Últimas ventas</h2>
    </div>
    <div id="v-ultimas">${cargando()}</div>`;

  const canal = el('v-canal');
  const ayudaCanal = el('v-canal-ayuda');
  const refrescarAyuda = () => {
    ayudaCanal.innerHTML = (canal.value === 'ml' || canal.value === 'elgadget')
      ? 'Este canal se va a sincronizar solo. Si la cargás a mano, usá el <strong>número de orden real</strong>: así, cuando la sincronización traiga esa orden, el sistema la reconoce y no descuenta dos veces.'
      : 'Este canal no se sincroniza: las ventas se cargan desde acá.';
  };
  canal.addEventListener('change', refrescarAyuda);
  refrescarAyuda();

  el('v-agregar').addEventListener('click', () =>
    elegirArticulo((a) => {
      lineasDeVenta.push({ articulo: a, cantidad: 1 });
      pintarLineasDeVenta();
    }));
  el('v-procesar').addEventListener('click', (e) => procesarVentaManual(e.currentTarget));

  pintarLineasDeVenta();
  pintarUltimasVentas();
}

function pintarLineasDeVenta() {
  const caja = el('v-lineas');
  if (!caja) return;

  if (!lineasDeVenta.length) {
    caja.innerHTML = `<div class="aviso neutro" style="margin-bottom:0">
      Agregá al menos un artículo.</div>`;
    return;
  }

  caja.innerHTML = lineasDeVenta.map((l, i) => `
    <div class="receta-fila">
      <div class="receta-nombre">
        <b>${esc(l.articulo.nombre)}</b>
        <span>${l.articulo.envio.receta_incompleta
          ? '<strong style="color:var(--orange)">sin receta: no va a descontar</strong>'
          : `${l.articulo.envio.insumos_en_receta} insumo(s) por unidad`}</span>
      </div>
      <div class="receta-cant">
        <input type="text" inputmode="decimal" value="${esc(l.cantidad)}"
               data-linea-venta="${i}" aria-label="Cantidad vendida">
      </div>
      <button class="receta-quitar" data-quitar-linea="${i}" aria-label="Quitar">${icono('menos')}</button>
    </div>`).join('');

  const sinReceta = lineasDeVenta.filter((l) => l.articulo.envio.receta_incompleta);
  if (sinReceta.length) {
    caja.innerHTML += `<div class="aviso atencion" style="margin-top:12px">
      <strong>Hay ${sinReceta.length} artículo(s) sin receta</strong>
      La venta se va a registrar igual, pero <strong>no va a descontar nada de nada</strong>
      —tampoco de los otros artículos— hasta que cargues esa receta. Queda en la lista de
      pendientes y se cierra con un reproceso.
    </div>`;
  }

  caja.querySelectorAll('[data-linea-venta]').forEach((input) => {
    input.addEventListener('input', () => {
      const n = num(input.value);
      lineasDeVenta[Number(input.dataset.lineaVenta)].cantidad = isFinite(n) ? n : 0;
    });
  });
  caja.querySelectorAll('[data-quitar-linea]').forEach((b) => {
    b.addEventListener('click', () => {
      lineasDeVenta.splice(Number(b.dataset.quitarLinea), 1);
      pintarLineasDeVenta();
    });
  });
}

async function procesarVentaManual(boton) {
  const idExterno = el('v-id').value.trim();
  if (!idExterno) { globo('Falta el identificador de la venta.', 'mal'); return; }
  if (!lineasDeVenta.length) { globo('Agregá al menos un artículo.', 'mal'); return; }
  if (lineasDeVenta.some((l) => !isFinite(l.cantidad) || l.cantidad <= 0)) {
    globo('Todas las cantidades tienen que ser mayores que cero.', 'mal');
    return;
  }

  const resumen = lineasDeVenta
    .map((l) => `${fmtCant(l.cantidad)} × ${esc(l.articulo.nombre)}`).join('<br>');
  if (!await confirmar(
    `Se va a descontar el stock de:<br><br>${resumen}<br><br>` +
    `Identificador: <strong>${esc(idExterno)}</strong>. Si ya cargaste esta venta con el ` +
    'mismo identificador, el sistema no la vuelve a descontar.',
    { titulo: '¿Descontar el stock?', textoSi: 'Descontar', peligro: false })) return;

  boton.disabled = true;
  boton.textContent = 'Descontando…';
  try {
    const r = await API.post('/ventas', {
      canal: el('v-canal').value,
      id_externo: idExterno,
      fecha_venta: el('v-fecha').value || null,
      nota: el('v-nota').value.trim() || null,
      usuario: el('v-usuario').value.trim() || null,
      items: lineasDeVenta.map((l) => ({ articulo_id: l.articulo.id, cantidad: l.cantidad })),
    });

    Cache.invalidar('insumos');
    mostrarResultadoDeVenta(r);
    lineasDeVenta = [];
    el('v-id').value = idVentaManual();
    el('v-nota').value = '';
    pintarLineasDeVenta();
    pintarUltimasVentas();
    refrescarInsignias();
  } catch (e) {
    globo('No se pudo procesar: ' + e.message, 'mal');
  } finally {
    boton.disabled = false;
    boton.textContent = 'Descontar stock';
  }
}

/** El resultado se muestra en una hoja y no en un aviso al pasar: el estado
    de la venta decide si el stock se descontó o no, y eso hay que leerlo. */
function mostrarResultadoDeVenta(r) {
  const explicaciones = {
    procesada: ['bueno', 'Se descontó el stock',
      'Los insumos de la receta de cada artículo ya salieron del stock.'],
    pendiente_receta: ['atencion', 'Registrada, pero NO descontó stock',
      'Falta la receta de algún artículo. La venta quedó guardada entera con sus ítems: cargá la receta y reprocesá desde Alertas.'],
    pendiente_mapeo: ['atencion', 'Registrada, pero NO descontó stock',
      'No se pudo resolver a qué artículo corresponde algún ítem. Cargá la publicación en la ficha del artículo y reprocesá.'],
    ignorada_fecha_corte: ['neutro', 'No se descontó: es anterior a la fecha de corte',
      'La fecha de corte es el arranque del inventario. Si esta venta sí tiene que descontar, corregí la fecha de corte en Ajustes.'],
    cancelada: ['malo', 'Esa venta está cancelada',
      'Una venta cancelada no vuelve a descontar por ningún camino.'],
  };
  const [tipo, titulo, detalle] = explicaciones[r.estado] ||
    ['neutro', `Estado: ${r.estado}`, ''];

  abrirHoja({
    titulo: 'Resultado de la venta',
    subtitulo: `${nombreCanal(r.canal)} · ${r.id_externo}`,
    cuerpo: `
      <div class="aviso ${tipo}">
        <strong>${esc(titulo)}</strong>${esc(detalle)}
      </div>

      ${r.ya_estaba_procesada ? `<div class="aviso neutro">
        <strong>Ya estaba registrada</strong>
        No se descontó nada de nuevo: es la protección contra descontar dos veces la misma
        venta.
      </div>` : ''}

      ${r.articulos && r.articulos.length ? `
        <div class="tarjeta">
          <div class="bloque-titulo">Artículos</div>
          <table class="tabla" style="min-width:0">
            ${r.articulos.map((a) => `<tr>
              <td>${esc(a.nombre || ('Artículo ' + a.articulo_id))}</td>
              <td class="num">${fmtCant(a.cantidad)}</td>
            </tr>`).join('')}
          </table>
        </div>` : ''}

      ${r.movimientos && r.movimientos.length ? `
        <div class="tarjeta">
          <div class="bloque-titulo">Insumos que salieron del stock</div>
          <div class="tabla-marco">
            <table class="tabla">
              <thead><tr><th>Insumo</th><th style="text-align:right">Salió</th><th style="text-align:right">Queda</th></tr></thead>
              <tbody>${r.movimientos.map((m) => `<tr>
                <td>${esc(m.insumo)}</td>
                <td class="num resta">${fmtCant(m.cantidad_unidades)} u.</td>
                <td class="num">${fmtCant(m.stock_resultante.cantidad_pantalla)}
                  ${esc(unidadTxt(m.stock_resultante.unidad_pantalla, m.stock_resultante.cantidad_pantalla))}</td>
              </tr>`).join('')}</tbody>
            </table>
          </div>
        </div>` : ''}

      ${bloqueAlertas(r.alertas)}
      ${listaAvisos(r.avisos)}`,
    acciones: [{ texto: 'Listo', clase: 'btn', alTocar: (h) => volverAtras(h) }],
  });
}

async function pintarUltimasVentas() {
  const caja = el('v-ultimas');
  if (!caja) return;
  try {
    const r = await API.get('/ventas', { limit: 15 });
    if (!r.ventas.length) {
      caja.innerHTML = vacio('Todavía no se registró ninguna venta');
      return;
    }
    caja.innerHTML = `<div class="lista">${r.ventas.map(filaVenta).join('')}</div>`;
    caja.querySelectorAll('[data-venta]').forEach((b) => {
      b.addEventListener('click', () => abrirFichaVenta(b.dataset.canal, b.dataset.venta));
    });
  } catch (e) {
    if (e instanceof ErrorAuth) { pedirIngreso(e.message); return; }
    caja.innerHTML = errorEnPantalla(e, 'pintarUltimasVentas()');
  }
}

function filaVenta(v) {
  return `
    <button class="item ${v.estado === 'procesada' ? 'ok' : (v.estado === 'cancelada' ? 'negativo' : 'tibio')}"
            data-venta="${esc(v.id_externo)}" data-canal="${esc(v.canal)}">
      <div class="item-fila">
        <div class="item-cuerpo">
          <div class="item-nombre">${esc(v.id_externo)}</div>
          <div class="item-sub">${esc(nombreCanal(v.canal))} · ${v.fecha_venta ? fmtDia(v.fecha_venta) : 'sin fecha'}</div>
        </div>
      </div>
      <div class="item-pie">${insigniaEstado(v.estado)}
        ${v.estado_previo ? `<span class="insignia">Antes: ${esc(v.estado_previo)}</span>` : ''}
      </div>
    </button>`;
}

/* ── Selector de artículo ─────────────────────────────────── */

async function elegirArticulo(alElegir, { titulo = 'Elegir artículo' } = {}) {
  const hoja = abrirHoja({ titulo, cuerpo: cargando() });
  let articulos = [];
  try {
    articulos = await Cache.articulos();
  } catch (e) {
    hoja.cuerpo.innerHTML = errorEnPantalla(e);
    return;
  }

  hoja.cuerpo.innerHTML = `
    <div class="buscador">
      ${icono('lupa', 'lupa')}
      <input type="search" id="sa-buscar" placeholder="Buscar por nombre o SKU…" autocomplete="off">
    </div>
    <div class="lista" id="sa-lista"></div>`;

  const lista = hoja.cuerpo.querySelector('#sa-lista');
  const campo = hoja.cuerpo.querySelector('#sa-buscar');

  const pintar = () => {
    const texto = campo.value.trim().toLowerCase();
    const items = articulos.filter((a) => !texto ||
      [a.nombre, a.sku_afd, a.sku_elgadget, a.id_empretienda]
        .filter(Boolean).some((v) => String(v).toLowerCase().includes(texto)));

    if (!items.length) {
      lista.innerHTML = vacio(articulos.length ? 'Ninguno coincide' : 'No hay artículos activos');
      return;
    }
    lista.innerHTML = items.map((a) => `
      <button class="item ${a.envio.receta_incompleta ? 'tibio' : 'ok'}" data-elegir="${a.id}">
        <div class="item-fila">
          <div class="item-cuerpo">
            <div class="item-nombre">${esc(a.nombre)}</div>
            <div class="item-sub">${esc([a.sku_elgadget, a.sku_afd].filter(Boolean).join(' · ') || 'Sin SKU')}</div>
          </div>
          <div class="item-derecha">
            ${a.envio.receta_incompleta
              ? '<span class="insignia naranja">Sin receta</span>'
              : `<div class="item-numero" style="font-size:15px">${fmtCant(a.envio.peso_envio_g)}<small> g</small></div>`}
          </div>
        </div>
      </button>`).join('');

    lista.querySelectorAll('[data-elegir]').forEach((b) => {
      b.addEventListener('click', () => {
        const elegido = articulos.find((a) => a.id === Number(b.dataset.elegir));
        volverAtras(hoja);
        alElegir(elegido);
      });
    });
  };

  campo.addEventListener('input', demorar(pintar, 120));
  pintar();
  setTimeout(() => campo.focus(), 80);
}
