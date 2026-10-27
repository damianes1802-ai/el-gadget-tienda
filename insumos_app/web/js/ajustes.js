/* ============================================================
   INSUMOS — ASÍ FUE DECO · AJUSTES Y AUDITORÍA

   Las dos únicas claves de configuración que se editan y la comprobación de
   la invariante del sistema.

   LA FECHA DE CORTE ES LA PALANCA MÁS PELIGROSA DE ACÁ. Se fija sola con la
   primera carga de stock —es, por definición, la fecha de ese inventario— y
   decide qué ventas descuentan: nada anterior a esa fecha se descuenta.
   Moverla hacia atrás hace que ventas viejas empiecen a descontar de un
   inventario que no las contemplaba; moverla hacia adelante deja ventas
   reales sin descontar. Por eso se pide confirmación explicando las dos
   consecuencias, en vez de guardarla como un campo cualquiera.

   LA AUDITORÍA compara, insumo por insumo, el stock contra la suma de sus
   movimientos. Es la forma de comprobar sin abrir la base que
   `stock == Σ movimientos`. Si alguna fila no cuadra, hay un camino de
   escritura que se salteó el libro mayor, y eso es un bug a buscar, no un
   número a corregir a mano.
   ============================================================ */

async function cargarAjustes() {
  const caja = el('p-ajustes');
  caja.innerHTML = cargando();

  try {
    const [config, salud] = await Promise.all([
      API.get('/config'),
      fetch(RAIZ + '/salud').then((r) => r.json()),
    ]);

    caja.innerHTML = `
      <div class="tarjeta">
        <div class="bloque-titulo">Fecha de corte</div>
        <div class="ayuda">
          Las ventas anteriores a esta fecha <strong>no descuentan stock</strong>. Se fijó
          sola con la primera carga de inventario.
        </div>
        <div style="font-family:'Space Grotesk',sans-serif;font-size:24px;font-weight:700;margin:12px 0">
          ${config.fecha_corte ? fmtDia(config.fecha_corte) : 'Sin fijar'}
        </div>
        ${config.fecha_corte ? '' : `<div class="aviso atencion">
          <strong>Todavía no hay fecha de corte</strong>
          Se va a fijar sola con la primera carga de stock. Sin corte, una sincronización de
          Mercado Libre traería el historial completo de ventas y lo descontaría de un
          inventario que recién se está cargando.
        </div>`}
        <div class="campo">
          <label for="aj-corte">Corregirla</label>
          <input type="date" id="aj-corte" value="${esc(config.fecha_corte || '')}">
          <div class="pie">
            Usala si el inventario físico se contó en otra fecha que el día en que se cargó.
          </div>
        </div>
        <button class="btn btn-borde btn-bloque" id="aj-guardar-corte">Guardar fecha de corte</button>
      </div>

      <div class="tarjeta">
        <div class="bloque-titulo">Margen de embalaje por defecto</div>
        <div class="ayuda">
          El factor con el que nacen los artículos nuevos. Se aplica a cada dimensión y al
          peso. Cada artículo puede tener el suyo.
        </div>
        <div class="aviso atencion" style="margin-top:12px">
          <strong>1,05 por dimensión infla el VOLUMEN 15,8 %, no 5 %</strong>
          Porque 1,05³ = 1,158. Si la intención es que el paquete ocupe un 5 % más de
          volumen, el factor es <strong>1,016</strong>. Importa porque Correo Argentino cobra
          por peso volumétrico cuando el paquete es liviano y voluminoso, que es exactamente
          el caso de una guirnalda: ahí el margen es una decisión de precio.
        </div>
        <div class="campo">
          <label for="aj-margen">Margen</label>
          <input type="text" id="aj-margen" inputmode="decimal"
                 value="${esc(String(config.margen_embalaje_default || '1.05').replace('.', ','))}">
          <div class="pie">Cambiarlo no toca los artículos que ya existen.</div>
        </div>
        <button class="btn btn-borde btn-bloque" id="aj-guardar-margen">Guardar margen</button>
      </div>

      <div class="tarjeta">
        <div class="bloque-titulo">Auditoría del stock</div>
        <div class="ayuda">
          Compara el stock de cada insumo contra la suma de sus movimientos. Si algo no
          cuadra, el stock se escribió por un camino que no pasó por el libro mayor.
        </div>
        <button class="btn btn-borde btn-bloque" id="aj-auditar" style="margin-top:12px">
          Comprobar ahora
        </button>
        <div id="aj-auditoria" style="margin-top:12px"></div>
      </div>

      <div class="tarjeta">
        <div class="bloque-titulo">Estado del sistema</div>
        <table class="tabla" style="min-width:0">
          <tr><td>Versión de la API</td><td class="num">${esc(salud.version)}</td></tr>
          <tr><td>Insumos</td><td class="num">${fmt(salud.insumos)}</td></tr>
          <tr><td>Artículos</td><td class="num">${fmt(salud.articulos)}</td></tr>
          <tr><td>Ventas pendientes</td><td class="num">${fmt(salud.ventas_pendientes)}</td></tr>
          <tr><td>Esquema de la base</td><td class="num">v${esc(config.schema_version || '?')}</td></tr>
          <tr><td>Autenticación</td><td class="num">${API.pideClave ? 'con clave' : 'abierta'}</td></tr>
        </table>
        ${API.pideClave ? '' : `<div class="aviso atencion" style="margin-top:12px">
          <strong>La API está respondiendo sin autenticación</strong>
          <code>INSUMOS_PASSWORD</code> no está configurado. Para desarrollo está bien; antes
          de exponer esto a internet hay que configurarlo. La pantalla de ingreso ya está
          lista: cuando la variable exista, la aplicación pide la clave sola.
        </div>`}
        ${API.pideClave ? `<button class="btn btn-borde btn-bloque" id="aj-salir" style="margin-top:12px">
          ${icono('salir')} Cerrar sesión en este dispositivo
        </button>` : ''}
      </div>`;

    el('aj-guardar-corte').addEventListener('click', (e) => guardarFechaCorte(e.currentTarget, config));
    el('aj-guardar-margen').addEventListener('click', (e) => guardarMargen(e.currentTarget));
    el('aj-auditar').addEventListener('click', auditarStock);
    const salir = el('aj-salir');
    if (salir) salir.addEventListener('click', cerrarSesion);
  } catch (e) {
    if (e instanceof ErrorAuth) { pedirIngreso(e.message); return; }
    caja.innerHTML = errorEnPantalla(e, 'cargarAjustes()');
  }
}

async function guardarFechaCorte(boton, config) {
  const valor = el('aj-corte').value;
  if (!valor) { globo('Elegí una fecha.', 'mal'); return; }
  if (valor === config.fecha_corte) { globo('Es la misma fecha que ya estaba.'); return; }

  const mueveAtras = config.fecha_corte && valor < config.fecha_corte;
  if (!await confirmar(
    `La fecha de corte pasa de <strong>${config.fecha_corte ? fmtDia(config.fecha_corte) : 'sin fijar'}</strong> ` +
    `a <strong>${fmtDia(valor)}</strong>.<br><br>` +
    (mueveAtras
      ? 'Moverla hacia <strong>atrás</strong> hace que ventas más viejas empiecen a descontar de un inventario que no las contemplaba: el stock puede irse a negativo.'
      : 'Moverla hacia <strong>adelante</strong> deja ventas reales sin descontar: el stock va a quedar sobreestimado.') +
    '<br><br>Las ventas ya procesadas no se tocan: el corte decide solo lo que venga.',
    { titulo: '¿Cambiar la fecha de corte?', textoSi: 'Cambiarla' })) return;

  boton.disabled = true;
  try {
    await API.put('/config/fecha_corte', { valor });
    globo('Fecha de corte actualizada.');
    recargarPantalla();
  } catch (e) {
    globo('No se pudo guardar: ' + e.message, 'mal');
  } finally { boton.disabled = false; }
}

async function guardarMargen(boton) {
  const valor = num(el('aj-margen').value);
  if (!isFinite(valor) || valor < 1) {
    globo('El margen tiene que ser un número mayor o igual a 1.', 'mal');
    return;
  }
  boton.disabled = true;
  try {
    await API.put('/config/margen_embalaje_default', { valor: String(valor) });
    globo('Margen por defecto actualizado. No cambia los artículos que ya existen.');
    recargarPantalla();
  } catch (e) {
    globo('No se pudo guardar: ' + e.message, 'mal');
  } finally { boton.disabled = false; }
}

async function auditarStock() {
  const caja = el('aj-auditoria');
  caja.innerHTML = cargando('Sumando el libro mayor…');
  try {
    const r = await API.get('/auditoria/stock');
    if (r.cuadra) {
      caja.innerHTML = `<div class="aviso bueno" style="margin-bottom:0">
        <strong>Cuadra</strong>
        Los ${fmt(r.total_insumos)} insumos tienen un stock igual a la suma de sus
        movimientos. La invariante del sistema se cumple.
      </div>`;
      return;
    }
    caja.innerHTML = `
      <div class="aviso malo">
        <strong>${fmt(r.descuadres.length)} insumo(s) no cuadran</strong>
        Esto no se arregla con un ajuste: significa que algo escribió el stock sin pasar por
        el libro mayor, y hay que encontrar ese camino. Avisá antes de tocar nada.
      </div>
      <div class="tabla-marco">
        <table class="tabla">
          <thead><tr><th>Insumo</th><th style="text-align:right">Stock</th><th style="text-align:right">Σ movimientos</th></tr></thead>
          <tbody>${r.descuadres.map((d) => `<tr>
            <td>${esc(d.nombre)}</td>
            <td class="num">${fmtCant(d.stock_unidades)}</td>
            <td class="num resta">${fmtCant(d.suma_movimientos)}</td>
          </tr>`).join('')}</tbody>
        </table>
      </div>`;
  } catch (e) {
    caja.innerHTML = errorEnPantalla(e);
  }
}
