/* ============================================================
   INSUMOS — ASÍ FUE DECO · cliente HTTP

   Esta es una aplicación WEB, no el shell de escritorio de `admin_app/`:
   habla por `fetch()` contra la misma FastAPI que la sirve, no por
   `window.pywebview.api`.

   LA URL DE LA API NO SE CONFIGURA, SE DEDUCE.
   La interfaz se sirve desde `/app/` de la misma app, así que la API está
   siempre al lado, en `/api`. Nunca hay una variable con la URL: en El
   Gadget un `API_URL` vacío en el CI dejó 534 corridas de nurturing en verde
   sin hacer nada, y un `SITE_URL` viejo publicó meses de URLs rotas en el
   catálogo de WhatsApp. Acá no hay nada que quede desactualizado.

   AUTENTICACIÓN
   El backend pide el header `X-Insumos-Password` cuando `INSUMOS_PASSWORD`
   está configurado, y responde ABIERTO cuando no. Hoy no está configurado.
   Esta capa manda el header siempre que tenga una credencial guardada, así
   que el día que se configure la variable la interfaz funciona sin tocar una
   línea: `GET /` dice si hace falta, y un 401 en cualquier llamada vuelve a
   pedirla.
   ============================================================ */

/** Raíz del servidor: lo que hay antes de `/app`. Soporta que mañana todo
    esto viva bajo un prefijo sin cambiar nada. */
const RAIZ = location.pathname.replace(/\/app(\/.*)?$/, '');
const BASE = RAIZ + '/api';

const GUARDA = 'insumos_clave';

/** Error de credencial. Se distingue del resto para que la aplicación
    muestre la pantalla de ingreso en vez de un cartel rojo cualquiera. */
class ErrorAuth extends Error {}

const API = {
  credencial: null,
  /** true cuando el backend tiene `INSUMOS_PASSWORD` configurado. */
  pideClave: false,

  /* ── Credencial ─────────────────────────────────────────── */

  recordarGuardada() {
    try {
      this.credencial = localStorage.getItem(GUARDA) || sessionStorage.getItem(GUARDA) || null;
    } catch (e) {
      // Modo privado o almacenamiento bloqueado: se sigue sin recordar nada.
      this.credencial = null;
    }
    return this.credencial;
  },

  guardarCredencial(clave, recordar) {
    this.credencial = clave || null;
    try {
      sessionStorage.removeItem(GUARDA);
      localStorage.removeItem(GUARDA);
      if (clave) (recordar ? localStorage : sessionStorage).setItem(GUARDA, clave);
    } catch (e) { /* sin almacenamiento: vale para esta pestaña nomás */ }
  },

  olvidarCredencial() { this.guardarCredencial(null, false); },

  /* ── Estado del servidor (endpoint abierto) ──────────────── */

  /** `GET /` no pide credencial y dice si la API está abierta o cerrada. */
  async estado() {
    const r = await fetch(RAIZ + '/', { headers: { Accept: 'application/json' } });
    if (!r.ok) throw new Error(`El servidor respondió ${r.status}`);
    const datos = await r.json();
    this.pideClave = datos.autenticacion === 'X-Insumos-Password';
    return datos;
  },

  /** Prueba la credencial contra un endpoint protegido y liviano. */
  async probarCredencial(clave) {
    const r = await fetch(BASE + '/config', {
      headers: Object.assign({ Accept: 'application/json' },
        clave ? { 'X-Insumos-Password': clave } : {}),
    });
    if (r.status === 401) return false;
    if (!r.ok) throw new Error(`El servidor respondió ${r.status}`);
    return true;
  },

  /* ── Llamadas ───────────────────────────────────────────── */

  async pedir(ruta, { metodo = 'GET', cuerpo = null, params = null } = {}) {
    let url = BASE + ruta;
    if (params) {
      const qs = new URLSearchParams();
      Object.entries(params).forEach(([k, v]) => {
        if (v !== null && v !== undefined && v !== '') qs.append(k, v);
      });
      const texto = qs.toString();
      if (texto) url += '?' + texto;
    }

    const cabeceras = { Accept: 'application/json' };
    if (this.credencial) cabeceras['X-Insumos-Password'] = this.credencial;
    if (cuerpo !== null) cabeceras['Content-Type'] = 'application/json';

    let r;
    try {
      r = await fetch(url, {
        method: metodo,
        headers: cabeceras,
        body: cuerpo !== null ? JSON.stringify(cuerpo) : undefined,
      });
    } catch (e) {
      throw new Error('No se pudo contactar al servidor. ¿Está corriendo la API?');
    }

    if (r.status === 401) {
      this.olvidarCredencial();
      throw new ErrorAuth('La credencial no es válida o venció.');
    }

    let datos = null;
    const tipo = r.headers.get('content-type') || '';
    if (tipo.includes('application/json')) {
      try { datos = await r.json(); } catch (e) { datos = null; }
    }

    if (!r.ok) throw new Error(mensajeDeError(datos, r.status));
    return datos;
  },

  get(ruta, params) { return this.pedir(ruta, { params }); },
  post(ruta, cuerpo, params) { return this.pedir(ruta, { metodo: 'POST', cuerpo: cuerpo || {}, params }); },
  put(ruta, cuerpo) { return this.pedir(ruta, { metodo: 'PUT', cuerpo: cuerpo || {} }); },
  borrar(ruta) { return this.pedir(ruta, { metodo: 'DELETE' }); },
};

/** Traduce el error del backend a algo legible.

    FastAPI devuelve `detail` como texto cuando lo lanza el código y como
    lista de objetos cuando lo rechaza la validación de pydantic; si se
    muestra tal cual, en pantalla aparece "[object Object]". */
function mensajeDeError(datos, status) {
  const detalle = datos && datos.detail;
  if (typeof detalle === 'string' && detalle) return detalle;
  if (Array.isArray(detalle) && detalle.length) {
    return detalle.map((d) => {
      const campo = Array.isArray(d.loc) ? d.loc.filter((p) => p !== 'body').join('.') : '';
      return (campo ? campo + ': ' : '') + (d.msg || 'dato inválido');
    }).join(' · ');
  }
  if (status === 404) return 'No se encontró lo que se buscaba.';
  if (status === 409) return 'El dato choca con una restricción del sistema.';
  return `Error ${status} del servidor.`;
}
