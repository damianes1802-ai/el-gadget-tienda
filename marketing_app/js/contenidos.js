/* ============================================================
   MARKETING EL GADGET — Contenido (generador IA + aprobación)
   ============================================================ */

let _contenidos = [];
let _filtroEstado = 'todos';
let _filtroPersona = 'todos';
let _filtroTipo = 'todos';

function exportContenidosCSV() {
  if (!_contenidos.length) { toast('No hay datos para exportar', 'error'); return; }

  const headers = ['id', 'tipo', 'formato', 'persona', 'layout_id', 'estado', 'hook', 'caption', 'hashtags', 'producto_sku', 'producto_nombre', 'media_type', 'creado_at', 'aprobado_at', 'publicado_at', 'views', 'saves', 'shares', 'reach'];
  const rows = _contenidos.map(c => {
    let mediaType = 'imagen';
    if (c._is_reel) mediaType = 'reel';
    else if (c._is_carousel || (c.media_url || '').startsWith('[')) mediaType = 'carrusel';
    return [
      c.id || '',
      c.tipo || '',
      c.formato || '',
      c.persona || '',
      c.layout_id || '',
      c.estado || '',
      c.hook || '',
      c.caption || '',
      c.hashtags || '',
      c.producto_sku || c.sku || '',
      c.producto_nombre || '',
      mediaType,
      csvFormatDate(c.created_at || c.creado_at || ''),
      csvFormatDate(c.aprobado_at || ''),
      csvFormatDate(c.publicado_at || ''),
      c.views || 0,
      c.saves || 0,
      c.shares || 0,
      c.reach || 0,
    ];
  });

  downloadCSV(`elgadget_contenidos_${csvDateNow()}.csv`, headers, rows);
}

async function loadContenidos() {
  await _fetchContenidos();
  loadElevenLabsCredits();
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

// ── Métricas de producción (Change 1) ──

function _renderStats() {
  const el = document.getElementById('contenidos-stats');
  if (!el) return;

  const total = _contenidos.length;
  const borradores = _contenidos.filter(c => c.estado === 'borrador').length;
  const aprobados = _contenidos.filter(c => c.estado === 'aprobado').length;
  const publicados = _contenidos.filter(c => c.estado === 'publicado').length;
  const reels = _contenidos.filter(c => c._is_reel).length;
  const posts = _contenidos.filter(c => !c._is_reel).length;

  // This week's production: items created in the last 7 days
  const now = new Date();
  const weekAgo = new Date(now.getFullYear(), now.getMonth(), now.getDate() - 7);
  const thisWeek = _contenidos.filter(c => {
    if (!c.created_at) return false;
    const d = new Date(c.created_at.includes('T') || c.created_at.includes('Z')
      ? c.created_at : c.created_at.replace(' ', 'T'));
    return d >= weekAgo;
  }).length;

  // Posts vs Reels breakdown bar
  const totalForBar = posts + reels || 1;
  const postsPct = Math.round((posts / totalForBar) * 100);
  const reelsPct = 100 - postsPct;

  el.className = 'produccion-dashboard';
  el.innerHTML = `
    <div class="stat-card">
      <div class="stat-label">Total generados</div>
      <div class="stat-value">${total}</div>
      <div class="stat-sub">todo el tiempo</div>
    </div>
    <div class="stat-card">
      <div class="stat-label">Borradores pendientes</div>
      <div class="stat-value" style="color:var(--accent-deep)">${borradores}</div>
    </div>
    <div class="stat-card">
      <div class="stat-label">Aprobados listos</div>
      <div class="stat-value" style="color:var(--green-ok)">${aprobados}</div>
    </div>
    <div class="stat-card">
      <div class="stat-label">Publicados</div>
      <div class="stat-value" style="color:var(--purple)">${publicados}</div>
    </div>
    <div class="stat-card">
      <div class="stat-label">Posts vs Reels</div>
      <div class="produccion-breakdown">
        <span class="produccion-bar-label">${posts}</span>
        <div class="produccion-bar">
          <div class="produccion-bar-posts" style="width:${postsPct}%"></div>
          <div class="produccion-bar-reels" style="width:${reelsPct}%"></div>
        </div>
        <span class="produccion-bar-label">${reels}</span>
      </div>
      <div class="stat-sub" style="margin-top:4px">
        <span style="color:var(--accent-deep)">Posts</span> /
        <span style="color:#E84393">Reels</span>
      </div>
    </div>
    <div class="stat-card">
      <div class="stat-label">Esta semana</div>
      <div class="stat-value" style="color:var(--ink)">${thisWeek}</div>
      <div class="stat-sub">generados (7 dias)</div>
    </div>
  `;
}

// ── Render cards con filtrado (Change 3: persona + tipo) ──

function _getFilteredContenidos() {
  return _contenidos.filter(c => {
    // Persona filter
    if (_filtroPersona !== 'todos') {
      const persona = (c.persona || '').toLowerCase();
      if (persona !== _filtroPersona) return false;
    }
    // Tipo filter
    if (_filtroTipo !== 'todos') {
      if (_filtroTipo === 'reel') {
        if (!c._is_reel) return false;
      } else if (_filtroTipo === 'carrusel') {
        const mediaUrl = c.media_url || '';
        const isCarousel = c._is_carousel || mediaUrl.startsWith('[');
        if (!isCarousel || c._is_reel) return false;
      } else if (_filtroTipo === 'post') {
        const mediaUrl = c.media_url || '';
        const isCarousel = c._is_carousel || mediaUrl.startsWith('[');
        if (c._is_reel || isCarousel) return false;
      }
    }
    return true;
  });
}

function _renderCards() {
  const grid = document.getElementById('contenidos-grid');
  if (!grid) return;

  const filtered = _getFilteredContenidos();

  if (!filtered.length) {
    const msg = (_contenidos.length === 0)
      ? 'No hay contenido generado. Hace click en "Generar lote" para empezar.'
      : 'No hay contenido que coincida con los filtros seleccionados.';
    grid.innerHTML = '<div class="chart-empty" style="grid-column:1/-1">' + msg + '</div>';
    return;
  }

  grid.innerHTML = filtered.map(c => {
    const fmt = c.formato || '';
    const tipo = (c.tipo || '').toUpperCase();
    const persona = (c.persona || '').charAt(0).toUpperCase() + (c.persona || '').slice(1);
    const img = c.producto_imagen || '';
    const mediaUrl = c.media_url || '';
    const isCarousel = c._is_carousel || (mediaUrl.startsWith('['));
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

    const btnPublicar = c.estado === 'aprobado' ? `
      <button class="btn btn-sm" style="background:#8B5CF6;color:#fff" onclick="publicarManual(${c.id})">Publicar</button>
    ` : '';

    const acciones = c.estado === 'borrador' ? `
      <button class="btn btn-sm" style="background:var(--green-ok);color:#fff" onclick="aprobarContenido(${c.id})">Aprobar</button>
      <button class="btn btn-outline btn-sm" onclick="abrirEdicion(${c.id})">Editar</button>
      <button class="btn btn-sm" style="background:var(--red);color:#fff" onclick="rechazarContenido(${c.id})">Rechazar</button>
    ` : c.estado === 'aprobado' ? `
      ${btnPublicar}
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

    // Preview area with click to open modal (Change 2)
    let brandedPreview = '';
    if (isCarousel && mediaUrl) {
      try {
        const slides = JSON.parse(mediaUrl);
        if (slides.length > 0) {
          const sliderId = `slider-${c.id}`;
          const slideImgs = slides.map((s, idx) =>
            `<img src="${s}" alt="Slide ${idx + 1}" class="carousel-slide ${idx === 0 ? 'active' : ''}" data-idx="${idx}" style="${idx === 0 ? '' : 'display:none'}">`
          ).join('');
          brandedPreview = `<div class="contenido-card-preview carousel-container" id="${sliderId}" onclick="abrirPreview(${c.id})" style="cursor:pointer">
            ${slideImgs}
            <button class="carousel-arrow carousel-prev" onclick="event.stopPropagation();carouselNav('${sliderId}', -1)">&#8249;</button>
            <button class="carousel-arrow carousel-next" onclick="event.stopPropagation();carouselNav('${sliderId}', 1)">&#8250;</button>
            <div class="carousel-dots">${slides.map((_, idx) =>
              `<span class="carousel-dot ${idx === 0 ? 'active' : ''}" onclick="event.stopPropagation();carouselGo('${sliderId}', ${idx})"></span>`
            ).join('')}</div>
            <div class="carousel-counter">${slides.length} slides</div>
          </div>`;
        }
      } catch (e) {}
    } else if (c._is_reel && mediaUrl) {
      if (mediaUrl.startsWith('data:video')) {
        brandedPreview = `<div class="contenido-card-preview" style="background:#000;border-radius:12px;overflow:hidden;cursor:pointer" onclick="abrirPreview(${c.id})">
          <video src="${mediaUrl}" style="width:100%;display:block;border-radius:12px" preload="metadata"></video>
          <div style="position:absolute;inset:0;display:flex;align-items:center;justify-content:center;pointer-events:none">
            <div style="width:56px;height:56px;border-radius:50%;background:rgba(0,0,0,0.6);display:flex;align-items:center;justify-content:center;font-size:24px;color:#fff">&#9654;</div>
          </div>
        </div>`;
      } else {
        brandedPreview = `<div class="contenido-card-preview" style="background:#000;display:flex;align-items:center;justify-content:center;min-height:200px;border-radius:12px;cursor:pointer" onclick="abrirPreview(${c.id})">
          <div style="text-align:center;color:#fff">
            <div style="font-size:48px;margin-bottom:8px">&#127916;</div>
            <div style="font-size:13px;opacity:0.7">Reel generado</div>
          </div>
        </div>`;
      }
    } else if (mediaUrl) {
      brandedPreview = `<div class="contenido-card-preview" onclick="abrirPreview(${c.id})" style="cursor:pointer"><img src="${escapeHtml(mediaUrl)}" alt="Preview" loading="lazy"></div>`;
    }

    return `
      <div class="contenido-card">
        ${brandedPreview}
        <div class="contenido-card-header">
          <img src="${escapeHtml(img)}" alt="" class="contenido-card-img" onerror="this.style.display='none'">
          <div class="contenido-card-meta">
            <div style="display:flex;gap:6px;flex-wrap:wrap;align-items:center">
              ${c._is_reel ? '<span class="badge" style="background:#E84393;color:#fff">REEL</span>' : ''}
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

// ── Preview modal unificado (Change 2) ──

function abrirPreview(id) {
  const c = _contenidos.find(x => x.id === id);
  if (!c) return;

  const mediaUrl = c.media_url || '';
  const isCarousel = c._is_carousel || mediaUrl.startsWith('[');
  const persona = (c.persona || '').charAt(0).toUpperCase() + (c.persona || '').slice(1);
  const formato = c.formato || '';
  const tipo = (c.tipo || '').toUpperCase();

  const estadoBadge = {
    borrador: '<span class="badge badge-yellow">Borrador</span>',
    aprobado: '<span class="badge badge-green">Aprobado</span>',
    rechazado: '<span class="badge badge-red">Rechazado</span>',
    publicado: '<span class="badge badge-purple">Publicado</span>',
  }[c.estado] || '<span class="badge badge-gray">' + escapeHtml(c.estado) + '</span>';

  // Build media section
  let mediaHtml = '';
  if (isCarousel && mediaUrl) {
    try {
      const slides = JSON.parse(mediaUrl);
      if (slides.length > 0) {
        const sliderId = 'preview-slider';
        const slideImgs = slides.map((s, idx) =>
          `<img src="${s}" alt="Slide ${idx + 1}" class="carousel-slide ${idx === 0 ? 'active' : ''}" data-idx="${idx}" style="${idx === 0 ? '' : 'display:none'}">`
        ).join('');
        mediaHtml = `<div class="preview-media-wrap preview-carousel-container" id="${sliderId}">
          ${slideImgs}
          <button class="carousel-arrow carousel-prev" onclick="carouselNav('${sliderId}', -1)">&#8249;</button>
          <button class="carousel-arrow carousel-next" onclick="carouselNav('${sliderId}', 1)">&#8250;</button>
          <div class="carousel-dots">${slides.map((_, idx) =>
            `<span class="carousel-dot ${idx === 0 ? 'active' : ''}" onclick="carouselGo('${sliderId}', ${idx})"></span>`
          ).join('')}</div>
          <div class="carousel-counter">${slides.length} slides</div>
        </div>`;
      }
    } catch (e) {}
  } else if (c._is_reel && mediaUrl) {
    if (mediaUrl.startsWith('data:video')) {
      mediaHtml = `<div class="preview-media-wrap" style="background:#000">
        <video src="${mediaUrl}" controls autoplay style="width:100%;display:block;max-height:65vh"></video>
      </div>`;
    } else {
      mediaHtml = `<div class="preview-media-wrap" style="background:#000;display:flex;align-items:center;justify-content:center;min-height:200px">
        <div style="text-align:center;color:#fff">
          <div style="font-size:48px;margin-bottom:8px">&#127916;</div>
          <div style="font-size:13px;opacity:0.7">Reel generado (sin archivo de video)</div>
        </div>
      </div>`;
    }
  } else if (mediaUrl) {
    mediaHtml = `<div class="preview-media-wrap">
      <img src="${escapeHtml(mediaUrl)}" alt="Preview">
    </div>`;
  }

  // Build caption section with copy buttons
  const captionA = c.caption || '';
  const captionB = c.caption_variante_b || '';
  const hook = c.hook || '';
  const cta = c.cta || '';
  const hashtags = c.hashtags || '';

  const body = document.getElementById('preview-body');
  if (!body) return;

  body.innerHTML = `
    ${mediaHtml}
    <div class="preview-badges">
      ${c._is_reel ? '<span class="badge" style="background:#E84393;color:#fff">REEL</span>' : ''}
      ${isCarousel && !c._is_reel ? '<span class="badge" style="background:var(--ink);color:#fff">CARRUSEL</span>' : ''}
      <span class="badge badge-accent">${escapeHtml(formato)}</span>
      <span class="badge badge-ink">${escapeHtml(tipo)}</span>
      <span class="badge badge-blue">${escapeHtml(persona)}</span>
      ${estadoBadge}
    </div>
    <div class="preview-captions">
      <div class="preview-caption-col">
        <div class="preview-caption-header">
          <div class="contenido-label">Caption A</div>
          <button class="preview-caption-copy" onclick="copiarTextoPreview(this, 'caption-a')">Copiar</button>
        </div>
        <div class="preview-caption-text" id="preview-caption-a">${escapeHtml(captionA)}</div>
      </div>
      <div class="preview-caption-col">
        <div class="preview-caption-header">
          <div class="contenido-label">Caption B</div>
          <button class="preview-caption-copy" onclick="copiarTextoPreview(this, 'caption-b')">Copiar</button>
        </div>
        <div class="preview-caption-text" id="preview-caption-b">${escapeHtml(captionB)}</div>
      </div>
    </div>
    <div class="preview-details">
      <div class="contenido-section">
        <div class="contenido-label">Hook</div>
        <div class="contenido-text">${escapeHtml(hook)}</div>
      </div>
      <div class="contenido-section">
        <div class="contenido-label">CTA</div>
        <div class="contenido-text">${escapeHtml(cta)}</div>
      </div>
      <div class="contenido-section">
        <div class="contenido-label">Hashtags</div>
        <div class="contenido-text" style="font-size:11.5px;color:var(--gray-600)">${escapeHtml(hashtags)}</div>
      </div>
    </div>
  `;

  // Set title
  const titleEl = document.getElementById('preview-title');
  if (titleEl) titleEl.textContent = c.producto_nombre || 'Vista previa';

  openModal('modal-preview-overlay');
}

function copiarTextoPreview(btn, elId) {
  const el = document.getElementById('preview-' + elId);
  if (!el) return;
  navigator.clipboard.writeText(el.textContent).then(() => {
    const original = btn.textContent;
    btn.textContent = 'Copiado';
    btn.style.borderColor = 'var(--green-ok)';
    btn.style.color = 'var(--green-ok)';
    setTimeout(() => {
      btn.textContent = original;
      btn.style.borderColor = '';
      btn.style.color = '';
    }, 1500);
  }).catch(() => {
    toast('Error copiando texto', 'error');
  });
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
  if (!sku) { toast('Selecciona un producto', 'error'); return; }

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

// ── Reels ──

async function generarLoteReels() {
  const btn = document.getElementById('btn-generar-reels');
  if (!btn) return;
  const originalText = btn.textContent;
  btn.disabled = true;
  btn.textContent = 'Generando Reels...';
  btn.style.opacity = '0.6';
  toast('Generando 3 Reels con IA + voz en off. Esto tarda ~2 minutos...', 'info');

  try {
    const result = await apiCall('generar_lote_reels', 3);
    if (result && result.error) {
      toast('Error: ' + result.error, 'error');
    } else {
      const n = result.generados || 0;
      toast(`${n} Reel${n !== 1 ? 's' : ''} generado${n !== 1 ? 's' : ''} con voz + musica`, 'success');
      if (result.errores && result.errores.length > 0) {
        toast('Errores: ' + result.errores.join(', '), 'error');
      }
      _fetchContenidos();
    }
  } catch (e) {
    toast('Error generando Reels: ' + e.message, 'error');
  } finally {
    btn.disabled = false;
    btn.textContent = originalText;
    btn.style.opacity = '1';
  }
}

// Legacy function — kept for backwards compatibility, now delegates to unified preview
function abrirReelPreview(filePath) {
  // Find reel by media_url matching
  const c = _contenidos.find(x => x.media_url === filePath);
  if (c) {
    abrirPreview(c.id);
  } else {
    // Fallback: open a simple video modal for unknown sources
    let modal = document.getElementById('reel-preview-modal');
    if (!modal) {
      modal = document.createElement('div');
      modal.id = 'reel-preview-modal';
      modal.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,0.85);z-index:9999;display:flex;align-items:center;justify-content:center;cursor:pointer';
      modal.onclick = function() { this.remove(); };
      modal.innerHTML = `<div style="position:relative;max-height:90vh;max-width:90vw" onclick="event.stopPropagation()">
        <video id="reel-video-player" controls autoplay style="max-height:85vh;max-width:100%;border-radius:16px;box-shadow:0 8px 40px rgba(0,0,0,0.5)"></video>
        <button onclick="this.closest('#reel-preview-modal').remove()" style="position:absolute;top:-12px;right:-12px;width:32px;height:32px;border-radius:50%;background:#fff;border:none;font-size:18px;cursor:pointer;font-weight:700;box-shadow:0 2px 8px rgba(0,0,0,0.3)">&times;</button>
      </div>`;
      document.body.appendChild(modal);
    } else {
      modal.style.display = 'flex';
    }
    const video = document.getElementById('reel-video-player');
    if (video) {
      video.src = filePath;
      video.play();
    }
  }
}

// ── Publicar manual ──

function publicarManual(id) {
  const c = _contenidos.find(x => x.id === id);
  if (!c) return;

  const caption = (c.caption || '') + '\n\n' + (c.hashtags || '');
  const mediaUrl = c.media_url || '';
  const isReel = c._is_reel || false;

  let modal = document.getElementById('publicar-modal');
  if (modal) modal.remove();

  modal = document.createElement('div');
  modal.id = 'publicar-modal';
  modal.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,0.7);z-index:9999;display:flex;align-items:center;justify-content:center;padding:20px';
  modal.innerHTML = `
    <div style="background:#fff;border-radius:20px;max-width:520px;width:100%;max-height:90vh;overflow-y:auto;padding:28px" onclick="event.stopPropagation()">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:20px">
        <h2 style="margin:0;font-size:20px;color:var(--ink)">Publicar en Instagram</h2>
        <button onclick="document.getElementById('publicar-modal').remove()" style="background:none;border:none;font-size:24px;cursor:pointer;color:var(--gray-600)">&times;</button>
      </div>

      <div style="background:var(--cream);border-radius:12px;padding:16px;margin-bottom:16px">
        <div style="font-size:12px;font-weight:600;color:var(--gray-600);text-transform:uppercase;letter-spacing:0.5px;margin-bottom:8px">
          Paso 1: Copia la ubicacion del archivo
        </div>
        <button onclick="descargarMedia(${id})" class="btn btn-accent" style="width:100%;font-size:14px">
          Copiar directorio
        </button>
      </div>

      <div style="background:var(--cream);border-radius:12px;padding:16px;margin-bottom:16px">
        <div style="font-size:12px;font-weight:600;color:var(--gray-600);text-transform:uppercase;letter-spacing:0.5px;margin-bottom:8px">
          Paso 2: Copia el caption
        </div>
        <textarea id="publicar-caption" readonly style="width:100%;min-height:120px;border:1.5px solid #e5e7eb;border-radius:8px;padding:12px;font-size:13px;font-family:inherit;resize:vertical;box-sizing:border-box;color:var(--ink)">${caption.replace(/</g,'&lt;')}</textarea>
        <button onclick="copiarCaption()" class="btn btn-outline" style="width:100%;margin-top:8px;font-size:14px">Copiar caption + hashtags</button>
      </div>

      <div style="background:var(--cream);border-radius:12px;padding:16px;margin-bottom:16px">
        <div style="font-size:12px;font-weight:600;color:var(--gray-600);text-transform:uppercase;letter-spacing:0.5px;margin-bottom:8px">
          Paso 3: Subilo a Instagram
        </div>
        <p style="font-size:13px;color:var(--gray-600);margin:0;line-height:1.6">
          ${isReel ? 'Abri Instagram &rarr; + &rarr; Reel &rarr; selecciona el video &rarr; pega el caption &rarr; Publicar' : 'Abri Instagram &rarr; + &rarr; Post &rarr; selecciona la imagen &rarr; pega el caption &rarr; Publicar'}
        </p>
      </div>

      <button onclick="marcarPublicado(${id})" class="btn" style="width:100%;background:#8B5CF6;color:#fff;font-size:14px;padding:12px">
        Ya lo publique — marcar como publicado
      </button>
    </div>
  `;
  modal.onclick = function() { this.remove(); };
  document.body.appendChild(modal);
}

function descargarMedia(id) {
  const c = _contenidos.find(x => x.id === id);
  if (!c) return;

  const path = c._original_path || c.media_url || '';
  if (path) {
    navigator.clipboard.writeText(path).then(() => {
      toast('Directorio copiado al portapapeles', 'success');
    }).catch(() => {
      toast('Error copiando directorio', 'error');
    });
  }
}

function copiarCaption() {
  const textarea = document.getElementById('publicar-caption');
  if (!textarea) return;
  navigator.clipboard.writeText(textarea.value).then(() => {
    toast('Caption + hashtags copiados', 'success');
  });
}

async function marcarPublicado(id) {
  try {
    await apiCall('marcar_publicado', id);
    toast('Marcado como publicado', 'success');
    document.getElementById('publicar-modal')?.remove();
    _fetchContenidos();
  } catch (e) {
    toast('Error: ' + e.message, 'error');
  }
}

// ── ElevenLabs credits ──

async function loadElevenLabsCredits() {
  try {
    const data = await apiCall('get_elevenlabs_credits');
    const textEl = document.getElementById('el-credits-text');
    const barEl = document.getElementById('el-credits-bar');
    if (!textEl || !barEl) return;
    if (data && data.error) {
      textEl.textContent = 'Voz IA: ' + data.error;
      barEl.style.width = '0%';
    } else if (data && data.limit) {
      const pct = Math.round((data.remaining / data.limit) * 100);
      textEl.textContent = `Voz IA: ${data.remaining.toLocaleString()} / ${data.limit.toLocaleString()}`;
      barEl.style.width = pct + '%';
      barEl.style.background = pct < 15 ? 'var(--red)' : pct < 40 ? 'var(--accent)' : 'var(--green-ok)';
    }
  } catch (e) {
    const textEl = document.getElementById('el-credits-text');
    if (textEl) textEl.textContent = 'Voz IA: sin datos';
  }
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

// ── Carousel navigation ──
function carouselNav(sliderId, dir) {
  const container = document.getElementById(sliderId);
  if (!container) return;
  const slides = container.querySelectorAll('.carousel-slide');
  const dots = container.querySelectorAll('.carousel-dot');
  let current = [...slides].findIndex(s => s.classList.contains('active'));
  slides[current].classList.remove('active');
  slides[current].style.display = 'none';
  if (dots[current]) dots[current].classList.remove('active');
  current = (current + dir + slides.length) % slides.length;
  slides[current].classList.add('active');
  slides[current].style.display = 'block';
  if (dots[current]) dots[current].classList.add('active');
}

function carouselGo(sliderId, idx) {
  const container = document.getElementById(sliderId);
  if (!container) return;
  container.querySelectorAll('.carousel-slide').forEach((s, i) => {
    s.classList.toggle('active', i === idx);
    s.style.display = i === idx ? 'block' : 'none';
  });
  container.querySelectorAll('.carousel-dot').forEach((d, i) => d.classList.toggle('active', i === idx));
}

// ── Filtros (Change 3: estado + persona + tipo) ──

document.getElementById('contenidos-filtro')?.addEventListener('change', (e) => {
  _filtroEstado = e.target.value;
  _fetchContenidos();
});

document.getElementById('contenidos-filtro-persona')?.addEventListener('change', (e) => {
  _filtroPersona = e.target.value;
  _renderStats();
  _renderCards();
});

document.getElementById('contenidos-filtro-tipo')?.addEventListener('change', (e) => {
  _filtroTipo = e.target.value;
  _renderStats();
  _renderCards();
});
