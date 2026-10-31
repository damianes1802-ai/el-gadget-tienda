/* ============================================================
   INSUMOS — ASÍ FUE DECO · arranque, navegación y caché

   Una sola página con nueve pantallas. En el celular se navega con la barra
   de pestañas de abajo (cuatro pantallas de uso diario más "Más"); en
   escritorio, con el menú lateral, que muestra las nueve.

   La primera pantalla es ALERTAS a propósito: lo primero que alguien tiene
   que ver al entrar es qué insumo está por faltar.
   ============================================================ */

const PANTALLAS = [
  { id: 'alertas', titulo: 'Alertas', sub: 'Qué insumos están por faltar', icono: 'campana', tab: 'Alertas', cargar: () => cargarAlertas() },
  { id: 'insumos', titulo: 'Insumos', sub: 'Catálogo, alta y edición', icono: 'caja', tab: 'Insumos', cargar: () => cargarInsumos() },
  { id: 'stock', titulo: 'Stock', sub: 'Ingresos, conteos e historial', icono: 'balanza', tab: 'Stock', cargar: () => cargarStock() },
  { id: 'articulos', titulo: 'Artículos', sub: 'Receta y peso de envío', icono: 'etiqueta', tab: 'Artículos', cargar: () => cargarArticulos() },
  { id: 'categorias', titulo: 'Categorías', sub: 'Categorías y subcategorías', icono: 'carpeta', cargar: () => cargarCategorias() },
  { id: 'publicaciones', titulo: 'Publicaciones', sub: 'Qué publicación es qué artículo', icono: 'enlace', cargar: () => cargarPublicaciones() },
  { id: 'ventas', titulo: 'Ventas manuales', sub: 'Descontar el stock de una venta', icono: 'carro', cargar: () => cargarVentas() },
  { id: 'cancelaciones', titulo: 'Cancelar una venta', sub: 'Buscar y devolver el stock', icono: 'deshacer', cargar: () => cargarCancelaciones() },
  { id: 'ajustes', titulo: 'Ajustes', sub: 'Fecha de corte, margen y auditoría', icono: 'tuerca', cargar: () => cargarAjustes() },
];

let pantallaActual = 'alertas';

/* ── Caché de listas que se usan en varias pantallas ──────────

   El selector de insumos de una receta y el de artículos de una venta se
   abren muchas veces seguidas; pedir la lista completa en cada apertura es
   plata de Render y segundos de espera en un celular con mala señal. Se
   guarda en memoria y se invalida a mano cada vez que algo la cambia: nunca
   se deja envejecer sola, porque una lista de insumos vieja hace elegir un
   insumo que ya no está. */

const Cache = {
  _insumos: null,
  _articulos: null,
  _categorias: null,

  async insumos(recargar = false) {
    if (recargar || !this._insumos) this._insumos = await API.get('/insumos', { activo: true });
    return this._insumos;
  },
  async articulos(recargar = false) {
    if (recargar || !this._articulos) this._articulos = await API.get('/articulos', { activo: true });
    return this._articulos;
  },
  async categorias(recargar = false) {
    if (recargar || !this._categorias) this._categorias = await API.get('/categorias');
    return this._categorias;
  },
  invalidar(...claves) {
    claves.forEach((c) => { this['_' + c] = null; });
  },
};

/* ── Navegación ───────────────────────────────────────────── */

function irA(id, { forzar = false } = {}) {
  const pantalla = PANTALLAS.find((p) => p.id === id);
  if (!pantalla) return;
  cerrarTodasLasHojas();

  const cambia = pantallaActual !== id;
  pantallaActual = id;

  document.querySelectorAll('.pantalla').forEach((s) => s.classList.remove('activa'));
  el('p-' + id).classList.add('activa');
  el('top-titulo').textContent = pantalla.titulo;
  el('top-sub').textContent = pantalla.sub;
  el('vista').scrollTop = 0;

  document.querySelectorAll('#tabbar .tab').forEach((b) => {
    b.classList.toggle('activa', b.dataset.pantalla === id ||
      (b.dataset.pantalla === 'mas' && !PANTALLAS.find((p) => p.id === id).tab));
  });
  document.querySelectorAll('#lateral-nav button').forEach((b) => {
    b.classList.toggle('activa', b.dataset.pantalla === id);
  });

  if (cambia || forzar) pantalla.cargar();
}

function recargarPantalla() {
  const pantalla = PANTALLAS.find((p) => p.id === pantallaActual);
  if (pantalla) pantalla.cargar();
  refrescarInsignias();
}

function menuMas() {
  const sueltas = PANTALLAS.filter((p) => !p.tab);
  const hoja = abrirHoja({
    titulo: 'Más pantallas',
    cuerpo: `<div class="lista">${sueltas.map((p) => `
      <button class="item" data-ir="${p.id}">
        <div class="item-fila">
          <div class="item-cuerpo">
            <div class="item-nombre">${esc(p.titulo)}</div>
            <div class="item-sub">${esc(p.sub)}</div>
          </div>
        </div>
      </button>`).join('')}
      <button class="item" data-salir style="margin-top:6px">
        <div class="item-fila">
          <div class="item-cuerpo">
            <div class="item-nombre">Cerrar sesión</div>
            <div class="item-sub">Olvida la clave en este dispositivo</div>
          </div>
        </div>
      </button>
    </div>`,
  });
  hoja.cuerpo.querySelectorAll('[data-ir]').forEach((b) => {
    b.addEventListener('click', () => { volverAtras(hoja); irA(b.dataset.ir); });
  });
  hoja.cuerpo.querySelector('[data-salir]').addEventListener('click', () => {
    volverAtras(hoja);
    cerrarSesion();
  });
}

function armarNavegacion() {
  const tabbar = el('tabbar');
  const conTab = PANTALLAS.filter((p) => p.tab);
  tabbar.innerHTML = conTab.map((p) => `
    <button class="tab ${p.id === 'alertas' ? 'activa' : ''}" data-pantalla="${p.id}">
      ${icono(p.icono)}<span>${esc(p.tab)}</span>
      ${p.id === 'alertas' ? '<span class="tab-globo oculto" id="globo-alertas">0</span>' : ''}
    </button>`).join('') + `
    <button class="tab" data-pantalla="mas">${icono('mas_puntos')}<span>Más</span></button>`;

  tabbar.querySelectorAll('.tab').forEach((b) => {
    b.addEventListener('click', () => {
      if (b.dataset.pantalla === 'mas') menuMas();
      else irA(b.dataset.pantalla);
    });
  });

  el('lateral-nav').innerHTML = PANTALLAS.map((p) => `
    <button data-pantalla="${p.id}" class="${p.id === 'alertas' ? 'activa' : ''}">
      ${icono(p.icono)}<span>${esc(p.titulo)}</span>
      ${p.id === 'alertas' ? '<span class="globo-nav oculto" id="globo-alertas-lateral">0</span>' : ''}
    </button>`).join('');
  el('lateral-nav').querySelectorAll('button').forEach((b) => {
    b.addEventListener('click', () => irA(b.dataset.pantalla));
  });

  el('btn-refrescar').innerHTML = icono('refrescar');
  el('btn-refrescar').addEventListener('click', recargarPantalla);
}

/* ── Insignia de alertas ───────────────────────────────────── */

async function refrescarInsignias() {
  try {
    const [alertas, salud] = await Promise.all([
      API.get('/alertas'),
      fetch(RAIZ + '/salud').then((r) => r.json()).catch(() => null),
    ]);
    const total = (alertas.total || 0) + (salud && salud.ventas_pendientes || 0);
    [el('globo-alertas'), el('globo-alertas-lateral')].forEach((g) => {
      if (!g) return;
      g.textContent = total > 99 ? '99+' : String(total);
      g.classList.toggle('oculto', total === 0);
    });
    if (salud) {
      el('lateral-pie').innerHTML =
        `${fmt(salud.insumos)} insumos · ${fmt(salud.articulos)} artículos<br>` +
        `Corte: ${salud.fecha_corte ? fmtDia(salud.fecha_corte) : 'sin fijar'}`;
    }
  } catch (e) {
    if (e instanceof ErrorAuth) pedirIngreso();
  }
}

/* ── Ingreso ───────────────────────────────────────────────── */

function pedirIngreso(mensaje = '') {
  el('arranque').classList.add('listo');
  el('ingreso').classList.add('abierto');
  el('ingreso-error').innerHTML = mensaje
    ? `<div class="aviso malo"><strong>No se pudo entrar</strong>${esc(mensaje)}</div>` : '';
  const campo = el('ingreso-clave');
  campo.value = '';
  setTimeout(() => campo.focus(), 60);
}

async function intentarIngreso() {
  const boton = el('ingreso-entrar');
  const clave = el('ingreso-clave').value;
  if (!clave) { globo('Escribí la clave', 'mal'); return; }

  boton.disabled = true;
  boton.textContent = 'Verificando…';
  try {
    const vale = await API.probarCredencial(clave);
    if (!vale) {
      el('ingreso-error').innerHTML =
        '<div class="aviso malo"><strong>Clave incorrecta</strong>Probá de nuevo.</div>';
      el('ingreso-clave').value = '';
      el('ingreso-clave').focus();
      return;
    }
    API.guardarCredencial(clave, el('ingreso-recordar').checked);
    el('ingreso').classList.remove('abierto');
    arrancarAplicacion();
  } catch (e) {
    el('ingreso-error').innerHTML =
      `<div class="aviso malo"><strong>No se pudo verificar</strong>${esc(e.message)}</div>`;
  } finally {
    boton.disabled = false;
    boton.textContent = 'Entrar';
  }
}

async function cerrarSesion() {
  if (!API.pideClave) {
    globo('La API está abierta: no hay sesión que cerrar.', 'mal');
    return;
  }
  if (!await confirmar('Vas a tener que escribir la clave de nuevo para entrar.',
    { titulo: '¿Cerrar sesión?', textoSi: 'Cerrar sesión' })) return;
  API.olvidarCredencial();
  pedirIngreso();
}

/* ── Arranque ──────────────────────────────────────────────── */

function arrancarAplicacion() {
  el('arranque').classList.add('listo');
  irA('alertas', { forzar: true });
  refrescarInsignias();
}

async function arrancar() {
  armarNavegacion();
  el('ingreso-entrar').addEventListener('click', intentarIngreso);
  el('ingreso-clave').addEventListener('keydown', (e) => {
    if (e.key === 'Enter') intentarIngreso();
  });
  // Marca visual de la casilla sin depender de :has(), que no está en todos
  // los navegadores viejos de Android.
  document.querySelectorAll('.casilla input[type=checkbox]').forEach(marcarCasilla);

  // El historial lo usan solo las hojas (las pantallas no van al hash), así
  // que la entrada raíz se marca una vez y "atrás" cierra paneles sin tocar
  // la navegación entre pantallas.
  history.replaceState({ raiz: true }, '');

  API.recordarGuardada();

  try {
    await API.estado();
  } catch (e) {
    el('arranque').innerHTML =
      `<div style="max-width:380px"><div class="aviso malo"><strong>No se pudo contactar al servidor</strong>
      ${esc(e.message)}<div style="margin-top:10px">Verificá que la API esté corriendo
      (<code>python -m insumos_app.api</code>) y recargá la página.</div></div></div>`;
    return;
  }

  if (!API.pideClave) {
    // La API está abierta (INSUMOS_PASSWORD sin configurar): se entra directo.
    API.olvidarCredencial();
    arrancarAplicacion();
    return;
  }

  if (API.credencial && await API.probarCredencial(API.credencial).catch(() => false)) {
    arrancarAplicacion();
  } else {
    API.olvidarCredencial();
    pedirIngreso();
  }
}

/** Refleja el estado de un checkbox en su contenedor `.casilla`. */
function marcarCasilla(input) {
  const caja = input.closest('.casilla');
  if (!caja) return;
  const pintar = () => caja.classList.toggle('marcada', input.checked);
  input.addEventListener('change', pintar);
  pintar();
}

document.addEventListener('DOMContentLoaded', arrancar);
