/* ============================================================
   INSUMOS — ASÍ FUE DECO · CATEGORÍAS Y SUBCATEGORÍAS

   ABM simple. La taxonomía dice QUÉ ES el insumo (caireles → de vidrio, de
   acrílico); cómo se CUENTA lo dice el modo de stock, que es un campo
   aparte del insumo. Son dos cosas distintas y por eso no conviven en esta
   lista: un cairel de vidrio comprado por kilo necesita los dos datos, y si
   "por peso" fuera una subcategoría habría que elegir y se perdería uno.

   Ni una categoría ni una subcategoría se borran si tienen insumos adentro:
   el backend devuelve 409 y acá se muestra tal cual, porque la salida es
   reasignar esos insumos, no borrar en cascada.
   ============================================================ */

async function cargarCategorias() {
  const caja = el('p-categorias');
  caja.innerHTML = `
    <div class="seccion-cabecera">
      <h2>Categorías</h2>
      <button class="btn btn-ch" id="nueva-categoria">${icono('mas')} Nueva</button>
    </div>
    <div class="ayuda" style="margin-bottom:14px">
      Agrupan los insumos por lo que son. El orden decide cómo aparecen en las listas.
    </div>
    <div id="lista-categorias">${cargando()}</div>`;

  el('nueva-categoria').addEventListener('click', () => abrirFormCategoria());

  try {
    const categorias = await Cache.categorias(true);
    const lista = el('lista-categorias');

    if (!categorias.length) {
      lista.innerHTML = vacio('Todavía no hay categorías',
        '<div class="ayuda" style="margin-top:6px">Ejemplos para arrancar: caireles, cadenas, argollas, cintas.</div>');
      return;
    }

    lista.innerHTML = categorias.map((c) => `
      <div class="tarjeta">
        <div class="item-fila" style="align-items:center">
          <div class="item-cuerpo">
            <div class="item-nombre">${esc(c.nombre)}</div>
            <div class="item-sub">${fmt(c.insumos)} insumo(s) directos · orden ${fmt(c.orden)}</div>
          </div>
          <div style="display:flex;gap:6px;flex-shrink:0">
            <button class="btn btn-borde btn-ch" data-editar-cat="${c.id}" aria-label="Editar">${icono('lapiz')}</button>
            <button class="btn btn-borde btn-ch" data-borrar-cat="${c.id}" style="color:var(--red)" aria-label="Borrar">${icono('cruz')}</button>
          </div>
        </div>

        ${c.subcategorias.length ? `
          <div style="margin-top:12px;border-top:1px solid var(--gray-100);padding-top:6px">
            ${c.subcategorias.map((s) => `
              <div class="pub-fila">
                <div class="pub-datos">
                  <div class="pub-id" style="font-weight:600">${esc(s.nombre)}</div>
                  <div class="pub-meta">${fmt(s.insumos)} insumo(s) · orden ${fmt(s.orden)}</div>
                </div>
                <button class="btn btn-borde btn-ch" data-editar-sub="${s.id}"
                        data-cat="${c.id}" data-nombre="${esc(s.nombre)}" data-orden="${s.orden}"
                        aria-label="Editar">${icono('lapiz')}</button>
                <button class="btn btn-borde btn-ch" data-borrar-sub="${s.id}"
                        data-nombre="${esc(s.nombre)}" style="color:var(--red)" aria-label="Borrar">${icono('cruz')}</button>
              </div>`).join('')}
          </div>` : ''}

        <button class="btn btn-borde btn-ch btn-bloque" data-nueva-sub="${c.id}" style="margin-top:12px">
          ${icono('mas')} Subcategoría de ${esc(c.nombre)}
        </button>
      </div>`).join('');

    lista.querySelectorAll('[data-editar-cat]').forEach((b) => {
      const c = categorias.find((x) => String(x.id) === b.dataset.editarCat);
      b.addEventListener('click', () => abrirFormCategoria(c));
    });
    lista.querySelectorAll('[data-borrar-cat]').forEach((b) => {
      const c = categorias.find((x) => String(x.id) === b.dataset.borrarCat);
      b.addEventListener('click', () => borrarTaxonomia('categorias', c.id, c.nombre));
    });
    lista.querySelectorAll('[data-nueva-sub]').forEach((b) => {
      b.addEventListener('click', () => abrirFormSubcategoria(Number(b.dataset.nuevaSub), null, categorias));
    });
    lista.querySelectorAll('[data-editar-sub]').forEach((b) => {
      b.addEventListener('click', () => abrirFormSubcategoria(
        Number(b.dataset.cat),
        { id: Number(b.dataset.editarSub), nombre: b.dataset.nombre, orden: Number(b.dataset.orden) },
        categorias));
    });
    lista.querySelectorAll('[data-borrar-sub]').forEach((b) => {
      b.addEventListener('click', () =>
        borrarTaxonomia('subcategorias', Number(b.dataset.borrarSub), b.dataset.nombre));
    });
  } catch (e) {
    if (e instanceof ErrorAuth) { pedirIngreso(e.message); return; }
    el('lista-categorias').innerHTML = errorEnPantalla(e, 'cargarCategorias()');
  }
}

function abrirFormCategoria(categoria) {
  const c = categoria || {};
  const hoja = abrirHoja({
    titulo: categoria ? 'Editar categoría' : 'Nueva categoría',
    cuerpo: `
      <div class="campo">
        <label for="cat-nombre">Nombre</label>
        <input type="text" id="cat-nombre" value="${esc(c.nombre || '')}"
               placeholder="Caireles" autocomplete="off" autofocus>
      </div>
      <div class="campo">
        <label for="cat-orden">Orden en la lista</label>
        <input type="text" id="cat-orden" inputmode="numeric" value="${esc(c.orden || 0)}">
        <div class="pie">Menor primero. Con el mismo número, alfabético.</div>
      </div>`,
    acciones: [
      { texto: 'Cancelar', clase: 'btn-borde', alTocar: (h) => volverAtras(h) },
      {
        texto: 'Guardar',
        clase: 'btn',
        alTocar: async (h, b) => {
          const nombre = h.cuerpo.querySelector('#cat-nombre').value.trim();
          if (!nombre) { globo('Falta el nombre.', 'mal'); return; }
          const datos = { nombre, orden: Math.trunc(num(h.cuerpo.querySelector('#cat-orden').value) || 0) };
          b.disabled = true;
          try {
            if (categoria) await API.put(`/categorias/${categoria.id}`, datos);
            else await API.post('/categorias', datos);
            Cache.invalidar('categorias');
            volverAtras(h);
            globo(categoria ? 'Categoría actualizada.' : 'Categoría creada.');
            recargarPantalla();
          } catch (e) {
            globo('No se pudo guardar: ' + e.message, 'mal');
          } finally { b.disabled = false; }
        },
      },
    ],
  });
  setTimeout(() => hoja.cuerpo.querySelector('#cat-nombre').focus(), 100);
}

function abrirFormSubcategoria(categoriaId, subcategoria, categorias) {
  const s = subcategoria || {};
  const hoja = abrirHoja({
    titulo: subcategoria ? 'Editar subcategoría' : 'Nueva subcategoría',
    cuerpo: `
      <div class="campo">
        <label for="sub-categoria">Categoría</label>
        <select id="sub-categoria">
          ${categorias.map((c) => `<option value="${c.id}" ${String(c.id) === String(categoriaId) ? 'selected' : ''}>${esc(c.nombre)}</option>`).join('')}
        </select>
      </div>
      <div class="campo">
        <label for="sub-nombre">Nombre</label>
        <input type="text" id="sub-nombre" value="${esc(s.nombre || '')}"
               placeholder="De vidrio" autocomplete="off">
      </div>
      <div class="campo">
        <label for="sub-orden">Orden en la lista</label>
        <input type="text" id="sub-orden" inputmode="numeric" value="${esc(s.orden || 0)}">
      </div>`,
    acciones: [
      { texto: 'Cancelar', clase: 'btn-borde', alTocar: (h) => volverAtras(h) },
      {
        texto: 'Guardar',
        clase: 'btn',
        alTocar: async (h, b) => {
          const nombre = h.cuerpo.querySelector('#sub-nombre').value.trim();
          if (!nombre) { globo('Falta el nombre.', 'mal'); return; }
          const datos = {
            categoria_id: Number(h.cuerpo.querySelector('#sub-categoria').value),
            nombre,
            orden: Math.trunc(num(h.cuerpo.querySelector('#sub-orden').value) || 0),
          };
          b.disabled = true;
          try {
            if (subcategoria) await API.put(`/subcategorias/${subcategoria.id}`, datos);
            else await API.post('/subcategorias', datos);
            Cache.invalidar('categorias');
            volverAtras(h);
            globo(subcategoria ? 'Subcategoría actualizada.' : 'Subcategoría creada.');
            recargarPantalla();
          } catch (e) {
            globo('No se pudo guardar: ' + e.message, 'mal');
          } finally { b.disabled = false; }
        },
      },
    ],
  });
  setTimeout(() => hoja.cuerpo.querySelector('#sub-nombre').focus(), 100);
}

async function borrarTaxonomia(recurso, id, nombre) {
  const esCategoria = recurso === 'categorias';
  if (!await confirmar(
    `Se borra <strong>${esc(nombre)}</strong>. ` +
    (esCategoria
      ? 'Si tiene insumos (en ella o en sus subcategorías), el sistema no la borra y te lo avisa: hay que reasignar esos insumos primero.'
      : 'Si tiene insumos, el sistema no la borra y te lo avisa.'),
    { titulo: esCategoria ? '¿Borrar la categoría?' : '¿Borrar la subcategoría?', textoSi: 'Borrar' })) return;

  try {
    await API.borrar(`/${recurso}/${id}`);
    Cache.invalidar('categorias');
    globo('Borrada.');
    recargarPantalla();
  } catch (e) {
    // El 409 del backend explica cuántos insumos lo impiden: se muestra
    // completo en una hoja porque es información útil, no un error a tapar.
    abrirHoja({
      titulo: 'No se puede borrar',
      cuerpo: `<div class="aviso atencion"><strong>${esc(nombre)}</strong>${esc(e.message)}</div>
        <div class="ayuda">Reasigná esos insumos a otra categoría desde la pantalla de
        Insumos y volvé a intentar.</div>`,
      acciones: [{ texto: 'Entendido', clase: 'btn', alTocar: (h) => volverAtras(h) }],
    });
  }
}
