/* ============================================================
   INSUMOS — ASÍ FUE DECO · utilidades compartidas

   Formato en es-AR, escapado, hojas (los paneles que suben desde abajo),
   avisos flotantes y los dos componentes que se repiten en todas las
   pantallas: el aviso de unidad de stock y el panel de envío.

   NO HAY REGLAS DE NEGOCIO ACÁ, y es a propósito. El peso de envío, el
   consumo de una receta, las conversiones de stock y las alertas los calcula
   el backend (`calculos.py` / `stock.py`) y esta interfaz solo muestra lo que
   le devuelve, por el mismo motivo por el que la lógica de campañas de El
   Gadget vive en un único `utils/campanas.py`: si el número se calculara en
   los dos lados, algún día iban a discrepar y el que miente sería el de la
   pantalla.

   La única excepción está marcada como tal: `equivalenciaAproximada()`, que
   es presentación —el mismo puente kilos ↔ unidades que hace
   `calculos.desde_unidades`— y existe para que un error de magnitud se vea
   ANTES de guardar. Nada de lo que calcula se envía al servidor.
   ============================================================ */

/* ── Texto ───────────────────────────────────────────────────── */

function esc(valor) {
  if (valor === null || valor === undefined) return '';
  return String(valor)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

/* ── Números ──────────────────────────────────────────────────

   Los campos numéricos son <input type="text" inputmode="decimal"> y no
   type="number" a propósito: en es-AR se escribe "2,5" con coma, y un
   type="number" con coma devuelve cadena vacía SIN avisar. Un decimal que
   desaparece en silencio es exactamente el error que este sistema no se
   puede permitir, así que el parseo es explícito y acepta las dos formas. */

function num(valor) {
  if (valor === null || valor === undefined) return NaN;
  const limpio = String(valor).trim().replace(/\s/g, '').replace(',', '.');
  if (limpio === '') return NaN;
  return Number(limpio);
}

function fmt(valor, decimales = 0) {
  const n = Number(valor);
  if (!isFinite(n)) return '—';
  return n.toLocaleString('es-AR', {
    minimumFractionDigits: decimales,
    maximumFractionDigits: decimales,
  });
}

/** Cantidad con hasta 3 decimales, sin ceros de relleno al final. */
function fmtCant(valor) {
  const n = Number(valor);
  if (!isFinite(n)) return '—';
  const decimales = Number.isInteger(n) ? 0 : (Math.abs(n) < 1 ? 3 : 2);
  return n.toLocaleString('es-AR', { maximumFractionDigits: decimales, minimumFractionDigits: 0 });
}

function fmtPesos(valor) {
  const n = Number(valor);
  if (!isFinite(n) || valor === null || valor === undefined) return '—';
  return '$' + n.toLocaleString('es-AR', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function fmtFecha(valor) {
  if (!valor) return '—';
  const texto = String(valor).trim();

  // Una fecha sola ("2026-10-27") la interpreta JavaScript como MEDIANOCHE
  // UTC, que en Argentina es el día anterior a las 21:00. Este backend guarda
  // las fechas en hora local ART justamente para que el día calendario no se
  // corra, así que acá no se puede desarmar eso: sin hora, se muestra solo el
  // día, y ya.
  if (/^\d{4}-\d{2}-\d{2}$/.test(texto)) return fmtDia(texto);

  const d = new Date(texto.includes('T') ? texto : texto.replace(' ', 'T'));
  if (isNaN(d.getTime())) return texto;
  return d.toLocaleDateString('es-AR', { day: '2-digit', month: '2-digit', year: '2-digit' }) +
    ' ' + d.toLocaleTimeString('es-AR', { hour: '2-digit', minute: '2-digit' });
}

function fmtDia(valor) {
  if (!valor) return '—';
  // Siempre con hora, para que lo lea como local: una fecha pelada se
  // interpretaría como medianoche UTC y acá se vería el día anterior.
  const texto = String(valor).trim().replace(' ', 'T');
  const d = new Date(texto.includes('T') ? texto : texto + 'T00:00:00');
  if (isNaN(d.getTime())) return String(valor);
  return d.toLocaleDateString('es-AR', { day: '2-digit', month: '2-digit', year: 'numeric' });
}

/* ── Etiquetas del dominio ───────────────────────────────────── */

/** La unidad como se escribe al lado de un número concreto.

    "Avisar cuando queden 30 unidad" se lee como un error de carga, y en una
    pantalla cuyo trabajo es que nadie dude de la unidad, eso no da igual. */
function unidadTxt(unidad, cantidad) {
  if (unidad === 'kg') return 'kg';
  return Math.abs(Number(cantidad)) === 1 ? 'unidad' : 'unidades';
}

function unidadDe(insumo) {
  if (!insumo) return 'unidad';
  return insumo.unidad_pantalla || (insumo.modo_stock === 'peso' ? 'kg' : 'unidad');
}

function chipUnidad(insumo) {
  const u = unidadDe(insumo);
  return `<span class="chip-unidad ${u === 'kg' ? 'kg' : 'unidad'}">${u === 'kg' ? 'por peso · kg' : 'por unidad'}</span>`;
}

const CANALES = {
  ml: 'Mercado Libre',
  elgadget: 'El Gadget',
  empretienda: 'Empretienda',
  manual: 'Venta manual',
};
function nombreCanal(canal) { return CANALES[canal] || canal || '—'; }

const TIPOS_MOV = {
  inventario_inicial: 'Inventario inicial',
  ingreso: 'Ingreso',
  venta: 'Venta',
  ajuste: 'Ajuste',
  merma: 'Merma',
  devolucion: 'Devolución',
};
function nombreTipo(tipo) { return TIPOS_MOV[tipo] || tipo || '—'; }

const ESTADOS_VENTA = {
  procesada: ['verde', 'Procesada'],
  pendiente_receta: ['naranja', 'Falta la receta'],
  pendiente_mapeo: ['naranja', 'Falta la publicación'],
  ignorada_fecha_corte: ['', 'Anterior al corte'],
  cancelada: ['roja', 'Cancelada'],
  error: ['roja', 'Error'],
};
function insigniaEstado(estado) {
  const [clase, texto] = ESTADOS_VENTA[estado] || ['', estado || '—'];
  return `<span class="insignia ${clase}">${esc(texto)}</span>`;
}

/* ── Iconos ──────────────────────────────────────────────────── */

const ICONOS = {
  campana: '<path d="M18 8a6 6 0 1 0-12 0c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.7 21a2 2 0 0 1-3.4 0"/>',
  caja: '<path d="M21 8l-9-5-9 5 9 5 9-5z"/><path d="M3 8v8l9 5 9-5V8"/><path d="M12 13v8"/>',
  balanza: '<path d="M12 3v18"/><path d="M5 7h14"/><path d="M5 7l-3 7h6z"/><path d="M19 7l-3 7h6z"/>',
  etiqueta: '<path d="M20.59 13.41 11 3.83A2 2 0 0 0 9.59 3.2L4 3v5.59c0 .53.21 1.04.59 1.41l9.59 9.59a2 2 0 0 0 2.82 0l3.59-3.59a2 2 0 0 0 0-2.59z"/><circle cx="7.5" cy="7.5" r="1.5"/>',
  carpeta: '<path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>',
  enlace: '<path d="M10 13a5 5 0 0 0 7.07 0l2-2A5 5 0 0 0 12 4l-1 1"/><path d="M14 11a5 5 0 0 0-7.07 0l-2 2A5 5 0 0 0 12 20l1-1"/>',
  carro: '<circle cx="9" cy="20" r="1.6"/><circle cx="18" cy="20" r="1.6"/><path d="M2 3h2.5l2.6 11.3A2 2 0 0 0 9 16h9.4a2 2 0 0 0 2-1.6L22 7H5"/>',
  deshacer: '<path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/>',
  tuerca: '<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 1 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.6 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 1 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.6 1.65 1.65 0 0 0 10 3.09V3a2 2 0 1 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9v0a1.65 1.65 0 0 0 1.51 1H21a2 2 0 1 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/>',
  mas: '<path d="M12 5v14M5 12h14"/>',
  menos: '<path d="M5 12h14"/>',
  cruz: '<path d="M18 6 6 18M6 6l12 12"/>',
  lupa: '<circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/>',
  refrescar: '<path d="M21 12a9 9 0 1 1-2.64-6.36L21 8"/><path d="M21 3v5h-5"/>',
  mas_puntos: '<circle cx="5" cy="12" r="1.7"/><circle cx="12" cy="12" r="1.7"/><circle cx="19" cy="12" r="1.7"/>',
  lapiz: '<path d="M12 20h9"/><path d="M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4z"/>',
  historial: '<path d="M12 8v4l3 2"/><circle cx="12" cy="12" r="9"/>',
  salir: '<path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><path d="m16 17 5-5-5-5"/><path d="M21 12H9"/>',
};

function icono(nombre, clase = '') {
  const cuerpo = ICONOS[nombre] || '';
  return `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
    stroke-linecap="round" stroke-linejoin="round" class="${clase}" aria-hidden="true">${cuerpo}</svg>`;
}

/* ── Aviso flotante ──────────────────────────────────────────── */

let _globoReloj = null;

function globo(mensaje, tipo = 'bien') {
  const el = document.getElementById('globo');
  el.textContent = mensaje;
  el.className = 'globo visible ' + (tipo === 'mal' ? 'mal' : tipo === 'bien' ? 'bien' : '');
  clearTimeout(_globoReloj);
  _globoReloj = setTimeout(() => el.classList.remove('visible'), tipo === 'mal' ? 5200 : 3200);
}

/* ── Hojas (paneles que suben desde abajo) ────────────────────

   Pila, no una sola: el editor de artículo abre el buscador de insumos
   encima, y con un único panel habría que cerrar el de abajo y perder lo
   que se estaba escribiendo.

   Cada hoja empuja una entrada de historial para que el botón "atrás" de
   Android cierre el panel en vez de salir de la aplicación. Por eso mismo
   las pantallas NO usan el hash: así el historial lo usan solo las hojas y
   los dos no se pisan. */

const _hojas = [];

function abrirHoja({ titulo, subtitulo = '', cuerpo = '', acciones = [], alCerrar = null }) {
  const velo = document.createElement('div');
  velo.className = 'velo abierta';
  velo.style.zIndex = String(60 + _hojas.length * 2);
  velo.innerHTML = `
    <section class="hoja" role="dialog" aria-modal="true" aria-label="${esc(titulo)}">
      <header class="hoja-top">
        <h2>${esc(titulo)}${subtitulo ? `<br><span style="font-size:11.5px;font-weight:600;color:var(--gray-600)">${esc(subtitulo)}</span>` : ''}</h2>
        <button class="cerrar-hoja" data-cerrar aria-label="Cerrar">${icono('cruz')}</button>
      </header>
      <div class="hoja-cuerpo"></div>
      ${acciones.length ? '<footer class="hoja-pie"></footer>' : ''}
    </section>`;

  const cuerpoEl = velo.querySelector('.hoja-cuerpo');
  if (typeof cuerpo === 'string') cuerpoEl.innerHTML = cuerpo;
  else if (cuerpo) cuerpoEl.appendChild(cuerpo);

  const pie = velo.querySelector('.hoja-pie');
  const handle = { el: velo, cuerpo: cuerpoEl, cerrar: () => cerrarHoja(handle), alCerrar };

  if (pie) {
    acciones.forEach((accion) => {
      const btn = document.createElement('button');
      btn.className = 'btn ' + (accion.clase || 'btn-borde');
      btn.textContent = accion.texto;
      if (accion.id) btn.id = accion.id;
      btn.addEventListener('click', () => accion.alTocar(handle, btn));
      pie.appendChild(btn);
    });
  }

  velo.querySelector('[data-cerrar]').addEventListener('click', () => volverAtras(handle));
  velo.addEventListener('click', (e) => { if (e.target === velo) volverAtras(handle); });

  document.getElementById('hojas').appendChild(velo);
  _hojas.push(handle);
  ponerMarcador();
  return handle;
}

/* EL HISTORIAL Y LAS HOJAS: UNA SOLA ENTRADA, Y NUNCA UN `history.back()`
   PROPIO.

   La idea es que el botón "atrás" de Android cierre el panel en vez de salir
   de la aplicación. El camino obvio —una entrada por hoja, y `history.back()`
   al cerrarla con un botón— no funciona: `back()` es asincrónico, así que un
   flujo que cierra una hoja y abre otra enseguida (guardar y mostrar el
   resultado) hace el `pushState` de la nueva ANTES de que llegue el
   `popstate` de la vieja. Ese push pisa la entrada que el back iba a
   consumir, y el back termina yéndose una entrada de más: la primera prueba
   se llevó la página entera por delante.

   Acá hay UNA entrada mientras haya hojas abiertas, y la pone solo esta
   función. Cerrar con un botón no toca el historial. Si la entrada quedó
   puesta y ya no hay hojas, la próxima apertura la reusa, así que no se
   acumulan: el costo máximo es un "atrás" que no hace nada visible. */

let _marcadorPuesto = false;

function ponerMarcador() {
  if (_marcadorPuesto) return;
  history.pushState({ hojas: true }, '');
  _marcadorPuesto = true;
}

/** Cierra una hoja desde la interfaz (un botón, la cruz, el fondo).

    No toca el historial a propósito; el porqué está arriba, en
    `ponerMarcador()`. Existe como función aparte de `cerrarHoja()` porque
    todas las pantallas la llaman y así el día que esto cambie, cambia en un
    solo lugar. */
function volverAtras(handle) {
  cerrarHoja(handle);
}

function cerrarHoja(handle) {
  const h = handle || _hojas[_hojas.length - 1];
  if (!h) return;
  const i = _hojas.indexOf(h);
  if (i >= 0) _hojas.splice(i, 1);
  h.el.remove();
  if (h.alCerrar) h.alCerrar();
}

function cerrarTodasLasHojas() {
  while (_hojas.length) cerrarHoja(_hojas[_hojas.length - 1]);
}

/** El "atrás" del navegador cierra la hoja de arriba. Si quedan más abajo,
    se vuelve a poner la entrada para que el próximo "atrás" cierre esa. */
window.addEventListener('popstate', () => {
  _marcadorPuesto = false;
  if (!_hojas.length) return;
  cerrarHoja(_hojas[_hojas.length - 1]);
  if (_hojas.length) ponerMarcador();
});

document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape' && _hojas.length) volverAtras(_hojas[_hojas.length - 1]);
});

/** Confirmación. Devuelve una promesa con true/false. */
function confirmar(texto, { titulo = '¿Confirmás?', textoSi = 'Sí, dale', peligro = true } = {}) {
  return new Promise((resolver) => {
    let decidido = false;
    const hoja = abrirHoja({
      titulo,
      cuerpo: `<p style="font-size:14px;line-height:1.55">${texto}</p>`,
      acciones: [
        { texto: 'Cancelar', clase: 'btn-borde', alTocar: () => volverAtras(hoja) },
        {
          texto: textoSi,
          clase: peligro ? 'btn-malo' : 'btn',
          alTocar: () => { decidido = true; resolver(true); volverAtras(hoja); },
        },
      ],
      alCerrar: () => { if (!decidido) resolver(false); },
    });
  });
}

/* ── El aviso de unidad: la pieza que evita el error caro ─────

   Un insumo se cuenta por peso o por unidad. Si alguien carga "2" creyendo
   kilos cuando el insumo está en unidades, el stock queda mal y no se nota
   hasta que falta material. Así que en toda pantalla que pida un número de
   stock, este bloque dice en qué unidad lo está pidiendo, grande y con
   color propio por modo. */

function unidadAviso(insumo, { accion = 'Vas a cargar' } = {}) {
  const u = unidadDe(insumo);
  const esKg = u === 'kg';
  const peso = Number(insumo.peso_unitario_g) || 0;
  const nota = esKg
    ? `Este insumo se compra y se cuenta <strong>por peso</strong>. Escribí el número en KILOS, no en unidades ni en gramos. Referencia: 1 unidad pesa ${fmtCant(peso)} g.`
    : `Este insumo se cuenta <strong>de a uno</strong>. Escribí CUÁNTAS UNIDADES, no el peso. Referencia: cada unidad pesa ${fmtCant(peso)} g.`;
  return `
    <div class="unidad-aviso ${esKg ? 'kg' : 'unidad'}">
      <span class="ojo">${esc(accion)} en</span>
      <span class="grande">${esKg ? 'KILOS (kg)' : 'UNIDADES'}</span>
      <span class="nota">${nota}</span>
    </div>`;
}

/** Campo numérico con la unidad pegada y el teclado decimal del celular. */
function campoCantidad({ id, etiqueta, unidad, valor = '', pie = '', autofoco = false }) {
  const clase = unidad === 'kg' ? 'kg' : unidad === 'unidad' ? 'unidad' : '';
  const sufijo = unidad === 'kg' ? 'kg' : unidad === 'unidad' ? 'unidades' : unidad;
  return `
    <div class="campo">
      <label for="${id}">${esc(etiqueta)}</label>
      <div class="campo-numero ${clase}">
        <input type="text" id="${id}" inputmode="decimal" autocomplete="off"
               value="${esc(valor)}" placeholder="0" ${autofoco ? 'autofocus' : ''}>
        <span class="sufijo">${esc(sufijo)}</span>
      </div>
      <div class="equivale" id="${id}-equivale"></div>
      ${pie ? `<div class="pie">${pie}</div>` : ''}
    </div>`;
}

/* PRESENTACIÓN, NO REGLA DE NEGOCIO. Mismo puente que
   `calculos.desde_unidades` / `a_unidades`, calculado acá solo para mostrar
   una equivalencia mientras se escribe: quien iba a cargar "2" creyendo
   kilos ve "2 kg ≈ 800 unidades" y se da cuenta antes de guardar. El número
   que se manda al servidor es siempre el que se tipeó, en la unidad del modo
   de stock; la conversión real la hace el backend. */
function equivalenciaAproximada(cantidad, insumo) {
  const peso = Number(insumo.peso_unitario_g) || 0;
  if (!isFinite(cantidad) || cantidad === 0 || peso <= 0) return '';
  if (unidadDe(insumo) === 'kg') {
    const unidades = (cantidad * 1000) / peso;
    return `${fmtCant(cantidad)} kg ≈ <b>${fmt(Math.round(unidades))} unidades</b>`;
  }
  const kg = (cantidad * peso) / 1000;
  return `${fmt(cantidad)} unidades ≈ <b>${fmtCant(kg)} kg</b>`;
}

/** Engancha la equivalencia viva a un campo creado con campoCantidad(). */
function vincularEquivalencia(id, insumo) {
  const input = document.getElementById(id);
  const salida = document.getElementById(id + '-equivale');
  if (!input || !salida) return;
  const pintar = () => { salida.innerHTML = equivalenciaAproximada(num(input.value), insumo); };
  input.addEventListener('input', pintar);
  pintar();
}

/* ── Panel de envío ──────────────────────────────────────────

   `receta_incompleta` significa que el peso NO sirve para cotizar: sin
   receta la suma da 0, y un 0 que parece un peso hace cotizar un envío
   gratis. Así que cuando viene en true acá no se muestra ningún número de
   peso: se muestra el problema. */

function panelEnvio(envio, { pendienteGuardar = false } = {}) {
  if (!envio) return '';

  const medidas = `
    <div class="envio-medidas">
      <div class="envio-dato">Largo<b>${fmtCant(envio.largo_envio_cm)} cm</b></div>
      <div class="envio-dato">Ancho<b>${fmtCant(envio.ancho_envio_cm)} cm</b></div>
      <div class="envio-dato">Alto<b>${fmtCant(envio.alto_envio_cm)} cm</b></div>
      <div class="envio-dato">Volumen<b>${fmt(envio.volumen_cm3, 0)} cm³</b></div>
    </div>`;

  const notaMargen = `Margen de embalaje ${fmtCant(envio.margen_embalaje)} por dimensión` +
    (Number(envio.margen_embalaje) > 1
      ? ` — infla el volumen ${fmt((Math.pow(Number(envio.margen_embalaje), 3) - 1) * 100, 1)} %, no ${fmt((Number(envio.margen_embalaje) - 1) * 100, 1)} %.`
      : '.') +
    (envio.se_embala_doblado
      ? ' Las medidas salen del paquete <strong>doblado</strong>, no del producto estirado.'
      : '');

  if (envio.receta_incompleta) {
    return `
      <div class="envio falta ${pendienteGuardar ? 'pendiente-guardar' : ''}">
        <div class="ojo">Peso de envío</div>
        <div class="envio-sin">Falta la receta: todavía no hay peso.</div>
        <div class="envio-nota">
          Sin insumos cargados la suma da <strong>0 g</strong>, y ese cero no es un peso:
          cotizar con él sería cobrar un envío que no existe. Cargá la receta de abajo y
          el peso aparece solo.
        </div>
        ${medidas}
        <div class="envio-nota">Las medidas sí valen (salen del artículo). ${notaMargen}</div>
      </div>`;
  }

  return `
    <div class="envio ${pendienteGuardar ? 'pendiente-guardar' : ''}">
      <div class="ojo">Peso del paquete embalado</div>
      <div class="envio-peso">${fmtCant(envio.peso_envio_g)}<small> g</small></div>
      <div class="envio-kg">
        ${fmtCant(envio.peso_envio_kg)} kg · insumos ${fmtCant(envio.peso_insumos_g)} g
        + embalaje · ${envio.insumos_en_receta} insumo${envio.insumos_en_receta === 1 ? '' : 's'} en la receta
      </div>
      ${medidas}
      <div class="envio-nota">${notaMargen}</div>
    </div>`;
}

/* ── Varios ──────────────────────────────────────────────────── */

function el(id) { return document.getElementById(id); }

function cargando(texto = 'Cargando…') {
  return `<div class="cargando"><div class="girador"></div>${esc(texto)}</div>`;
}

function vacio(titulo, detalle = '') {
  return `<div class="vacio"><div class="vacio-titulo">${esc(titulo)}</div>${detalle}</div>`;
}

function errorEnPantalla(e, reintentar = '') {
  return `<div class="aviso malo"><strong>No se pudo cargar</strong>${esc(e && e.message || e)}
    ${reintentar ? `<div style="margin-top:10px"><button class="btn btn-borde btn-ch" onclick="${reintentar}">Reintentar</button></div>` : ''}</div>`;
}

/** Lista de avisos que devuelven varios endpoints (`avisos`). */
function listaAvisos(avisos, tipo = 'atencion') {
  if (!avisos || !avisos.length) return '';
  return `<div class="aviso ${tipo}"><strong>Tené en cuenta</strong>
    <ul>${avisos.map((a) => `<li>${esc(a)}</li>`).join('')}</ul></div>`;
}

/** Bloque de alertas tal como las devuelven las respuestas de escritura. */
function bloqueAlertas(alertas) {
  if (!alertas || !alertas.length) return '';
  const negativos = alertas.filter((a) => a.stock_negativo);
  const filas = alertas.map((a) => {
    const marca = a.stock_negativo ? ' · EN NEGATIVO' : (a.recien_cruzado ? ' · recién cruzó el umbral' : '');
    return `<li><strong style="display:inline">${esc(a.nombre)}</strong>: quedan
      ${fmtCant(a.stock_pantalla)} ${esc(unidadTxt(a.unidad, a.stock_pantalla))}
      (umbral ${fmtCant(a.umbral_pantalla)})${marca}</li>`;
  }).join('');
  return `<div class="aviso ${negativos.length ? 'malo' : 'atencion'}">
    <strong>${negativos.length ? 'Stock en negativo' : 'Stock bajo'}</strong>
    <ul>${filas}</ul></div>`;
}

/** Debounce simple, para los buscadores. */
function demorar(fn, ms = 260) {
  let reloj = null;
  return (...args) => {
    clearTimeout(reloj);
    reloj = setTimeout(() => fn(...args), ms);
  };
}

/** Identificador estable para una venta manual, visible y editable. */
function idVentaManual() {
  const d = new Date();
  const p = (n) => String(n).padStart(2, '0');
  return `manual-${d.getFullYear()}${p(d.getMonth() + 1)}${p(d.getDate())}-${p(d.getHours())}${p(d.getMinutes())}${p(d.getSeconds())}`;
}
