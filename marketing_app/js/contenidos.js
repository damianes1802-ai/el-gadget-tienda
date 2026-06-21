/* ============================================================
   MARKETING EL GADGET — Contenido (generador IA + aprobación)
   ============================================================ */

let _contenidos = [];
let _filtroEstado = 'todos';

async function loadContenidos() {
  await _fetchContenidos();
}

async function _fetchContenidos() {
  try {
    const data = await apiCall('get_contenidos', _filtroEstado);
    _contenidos = Array.isArray(data) ? data : [];
  } catch (e) {
    _contenidos = [];
  }
  _renderStats();
  _renderCards();
}

function _renderStats() {
  const borradores = _contenidos.filter(c => c.estado === 'borrador').length;
  const aprobados = _contenidos.filter(c => c.estado === 'aprobado').length;
  const rechazados = _contenidos.filter(c => c.estado === 'rechazado').length;
  const total = _contenidos.length;

  const el = document.getElementById('contenidos-stats');
  if (!el) return;
  el.innerHTML = `
    <div class="stat-card">
      <div class="stat-label">Borradores</div>
      <div class="stat-value">${borradores}</div>
    </div>
    <div class="stat-card">
      <div class="stat-label">Aprobados</div>
      <div class="stat-value" style="color:var(--green-ok)">${aprobados}</div>
    </div>
    <div class="stat-card">
      <div class="stat-label">Rechazados</div>
      <div class="stat-value" style="color:var(--red)">${rechazados}</div>
    </div>
    <div class="stat-card">
      <div class="stat-label">Total generados</div>
      <div class="stat-value">${total}</div>
    </div>
  `;
}

function _renderCards() {
  const grid = document.getElementById('contenidos-grid');
  if (!grid) return;

  if (!_contenidos.length) {
    grid.innerHTML = '<div class="chart-empty" style="grid-column:1/-1">No hay contenido generado. Hacé click en "Generar lote" para empezar.</div>';
    return;
  }

  grid.innerHTML = _contenidos.map(c => {
    const fmt = c.formato || '';
    const tipo = (c.tipo || '').toUpperCase();
    const persona = (c.persona || '').charAt(0).toUpperCase() + (c.persona || '').slice(1);
    const img = c.producto_imagen || '';
    let mediaUrl = c.media_url || '';
    if (mediaUrl && !mediaUrl.startsWith('http')) {
      mediaUrl = 'file:///' + mediaUrl.replace(/\\/g, '/');
    }
    const nombre = escapeHtml(c.producto_nombre || '');
    const precio = formatPrice(c.producto_precio || 0);
    const captionA = escapeHtml(c.caption || '');
    const captionB = escapeHtml(c.caption_variante_b || '');
    const hashtags = escapeHtml(c.hashtags || '');
    const hook = escapeHtml(c.hook || '');
    const cta = escapeHtml(c.cta || '');

    const estadoBadge = {
      borrador: '<span class="badge badge-yellow">Borrador</span>',
      aprobado: '<span class="badge badge-green">Aprobado</span>',
      rechazado: '<span class="badge badge-red">Rechazado</span>',
      publicado: '<span class="badge badge-purple">Publicado</span>',
    }[c.estado] || '<span class="badge badge-gray">' + escapeHtml(c.estado) + '</span>';

    const acciones = c.estado === 'borrador' ? `
      <button class="btn btn-sm" style="background:var(--green-ok);color:#fff" onclick="aprobarContenido(${c.id})">Aprobar</button>
      <button class="btn btn-outline btn-sm" onclick="abrirEdicion(${c.id})">Editar</button>
      <button class="btn btn-sm" style="background:var(--red);color:#fff" onclick="rechazarContenido(${c.id})">Rechazar</button>
    ` : c.estado === 'aprobado' ? `
      <button class="btn btn-outline btn-sm" onclick="abrirEdicion(${c.id})">Editar</button>
      <button class="btn btn-sm" style="background:var(--red-pale);color:var(--red)" onclick="rechazarContenido(${c.id})">Rechazar</button>
    ` : `
      <button class="btn btn-outline btn-sm" onclick="aprobarContenido(${c.id})">Restaurar</button>
      <button class="btn btn-sm" style="background:var(--red-pale);color:var(--red)" onclick="eliminarContenido(${c.id})">Eliminar</button>
    `;

    let score = '';
    if (c.score_esperado) {
      try {
        const s = JSON.parse(c.score_esperado);
        score = `<div class="contenido-metricas">Reach: ${s.reach_min}-${s.reach_max} · Engagement: ${s.eng_min}-${s.eng_max}%</div>`;
      } catch (e) {}
    }

    const brandedPreview = mediaUrl
      ? `<div class="contenido-card-preview"><img src="${escapeHtml(mediaUrl)}" alt="Preview branded" loading="lazy"></div>`
      : '';

    return `
      <div class="contenido-card">
        ${brandedPreview}
        <div class="contenido-card-header">
          <img src="${escapeHtml(img)}" alt="" class="contenido-card-img" onerror="this.style.display='none'">
          <div class="contenido-card-meta">
            <div style="display:flex;gap:6px;flex-wrap:wrap;align-items:center">
              <span class="badge badge-accent">${fmt}</span>
              <span class="badge badge-ink">${tipo}</span>
              <span class="badge badge-blue">${persona}</span>
              ${estadoBadge}
            </div>
            <div class="contenido-card-producto">${nombre}</div>
            <div class="contenido-card-precio">${precio}</div>
          </div>
        </div>
        <div class="contenido-card-body">
          <div class="contenido-section">
            <div class="contenido-label">Caption A</div>
            <div class="contenido-text">${captionA}</div>
          </div>
          <div class="contenido-section">
            <div class="contenido-label">Caption B</div>
            <div class="contenido-text">${captionB}</div>
          </div>
          <div class="contenido-row">
            <div class="contenido-section" style="flex:1">
              <div class="contenido-label">Hook</div>
              <div class="contenido-text">${hook}</div>
            </div>
            <div class="contenido-section" style="flex:1">
              <div class="contenido-label">CTA</div>
              <div class="contenido-text">${cta}</div>
            </div>
          </div>
          <div class="contenido-section">
            <div class="contenido-label">Hashtags</div>
            <div class="contenido-text" style="font-size:11.5px;color:var(--gray-600)">${hashtags}</div>
          </div>
          ${score}
        </div>
        <div class="contenido-card-footer">${acciones}</div>
      </div>
    `;
  }).join('');
}

// ── Acciones ──

async function generarLote() {
  const btn = document.getElementById('btn-generar-lote');
  if (!btn) return;
  btn.disabled = true;
  btn.textContent = 'Generando (puede tardar ~30s)...';
  try {
    const result = await apiCall('generar_lote', 5);
    if (result && result.error) {
      toast('Error: ' + result.error, 'error');
    } else {
      toast(`${result.generados || 0} piezas generadas`, 'success');
    }
  } catch (e) {
    toast('Error al generar: ' + e.message, 'error');
  } finally {
    btn.disabled = false;
    btn.textContent = 'Generar lote (5)';
    _fetchContenidos();
  }
}

async function generarIndividual() {
  const sku = document.getElementById('gen-producto-select').value;
  const formato = document.getElementById('gen-formato-select').value;
  const persona = document.getElementById('gen-persona-select').value;
  if (!sku) { toast('Seleccioná un producto', 'error'); return; }

  const productos = Array.isArray(_cache.productos) ? _cache.productos : [];
  const producto = productos.find(p => p.sku === sku);
  if (!producto) { toast('Producto no encontrado', 'error'); return; }

  const btn = document.getElementById('btn-generar-individual');
  btn.disabled = true;
  btn.textContent = 'Generando...';
  try {
    const result = await apiCall('generar_contenido', producto, formato, persona);
    if (result && result.error) {
      toast('Error: ' + result.error, 'error');
    } else {
      toast('Contenido generado', 'success');
      closeModal('modal-generar-overlay');
    }
  } catch (e) {
    toast('Error: ' + e.message, 'error');
  } finally {
    btn.disabled = false;
    btn.textContent = 'Generar';
    _fetchContenidos();
  }
}

async function aprobarContenido(id) {
  await apiCall('aprobar_contenido', id);
  toast('Contenido aprobado', 'success');
  _fetchContenidos();
}

async function rechazarContenido(id) {
  await apiCall('rechazar_contenido', id);
  toast('Contenido rechazado', 'error');
  _fetchContenidos();
}

async function eliminarContenido(id) {
  await apiCall('eliminar_contenido', id);
  toast('Contenido eliminado', 'success');
  _fetchContenidos();
}

function abrirEdicion(id) {
  const c = _contenidos.find(x => x.id === id);
  if (!c) return;
  document.getElementById('edit-contenido-id').value = id;
  document.getElementById('edit-caption').value = c.caption || '';
  document.getElementById('edit-caption-b').value = c.caption_variante_b || '';
  document.getElementById('edit-hashtags').value = c.hashtags || '';
  document.getElementById('edit-hook').value = c.hook || '';
  document.getElementById('edit-cta').value = c.cta || '';
  document.getElementById('edit-notas').value = c.notas_owner || '';
  openModal('modal-editar-contenido-overlay');
}

async function guardarEdicion() {
  const id = parseInt(document.getElementById('edit-contenido-id').value);
  const cambios = {
    caption: document.getElementById('edit-caption').value,
    caption_variante_b: document.getElementById('edit-caption-b').value,
    hashtags: document.getElementById('edit-hashtags').value,
    hook: document.getElementById('edit-hook').value,
    cta: document.getElementById('edit-cta').value,
    notas_owner: document.getElementById('edit-notas').value,
  };
  await apiCall('editar_contenido', id, cambios);
  closeModal('modal-editar-contenido-overlay');
  toast('Contenido actualizado', 'success');
  _fetchContenidos();
}

function abrirModalGenerar() {
  const sel = document.getElementById('gen-producto-select');
  if (sel && sel.options.length <= 1) {
    const productos = Array.isArray(_cache.productos) ? _cache.productos : [];
    const conStock = productos.filter(p => p.stock > 0).sort((a, b) => (b.precio_venta || 0) - (a.precio_venta || 0));
    conStock.forEach(p => {
      const o = document.createElement('option');
      o.value = p.sku;
      o.textContent = `${p.nombre} - ${formatPrice(p.precio_venta)}`;
      sel.appendChild(o);
    });
  }
  openModal('modal-generar-overlay');
}

// ── Modal helpers ──
function openModal(id) { document.getElementById(id).classList.add('show'); }
function closeModal(id) { document.getElementById(id).classList.remove('show'); }

document.addEventListener('click', (e) => {
  if (e.target.classList && e.target.classList.contains('modal-overlay')) {
    e.target.classList.remove('show');
  }
  const closeId = e.target.getAttribute && e.target.getAttribute('data-close');
  if (closeId) closeModal(closeId);
});

// ── Filtro ──
document.getElementById('contenidos-filtro')?.addEventListener('change', (e) => {
  _filtroEstado = e.target.value;
  _fetchContenidos();
});
