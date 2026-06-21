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
  const reels = _contenidos.filter(c => c._is_reel).length;
  const posts = _contenidos.filter(c => !c._is_reel).length;

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
      <div class="stat-label">Posts</div>
      <div class="stat-value">${posts}</div>
    </div>
    <div class="stat-card">
      <div class="stat-label">Reels</div>
      <div class="stat-value" style="color:#E84393">${reels}</div>
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

    let brandedPreview = '';
    if (isCarousel && mediaUrl) {
      try {
        const slides = JSON.parse(mediaUrl);
        if (slides.length > 0) {
          const sliderId = `slider-${c.id}`;
          const slideImgs = slides.map((s, idx) =>
            `<img src="${s}" alt="Slide ${idx + 1}" class="carousel-slide ${idx === 0 ? 'active' : ''}" data-idx="${idx}" style="${idx === 0 ? '' : 'display:none'}">`
          ).join('');
          brandedPreview = `<div class="contenido-card-preview carousel-container" id="${sliderId}">
            ${slideImgs}
            <button class="carousel-arrow carousel-prev" onclick="carouselNav('${sliderId}', -1)">‹</button>
            <button class="carousel-arrow carousel-next" onclick="carouselNav('${sliderId}', 1)">›</button>
            <div class="carousel-dots">${slides.map((_, idx) =>
              `<span class="carousel-dot ${idx === 0 ? 'active' : ''}" onclick="carouselGo('${sliderId}', ${idx})"></span>`
            ).join('')}</div>
            <div class="carousel-counter">${slides.length} slides</div>
          </div>`;
        }
      } catch (e) {}
    } else if (c._is_reel && mediaUrl) {
      if (mediaUrl.startsWith('data:video')) {
        brandedPreview = `<div class="contenido-card-preview" style="background:#000;border-radius:12px;overflow:hidden;cursor:pointer" onclick="abrirReelPreview(this.querySelector('video').src)">
          <video src="${mediaUrl}" style="width:100%;display:block;border-radius:12px" preload="metadata"></video>
          <div style="position:absolute;inset:0;display:flex;align-items:center;justify-content:center;pointer-events:none">
            <div style="width:56px;height:56px;border-radius:50%;background:rgba(0,0,0,0.6);display:flex;align-items:center;justify-content:center;font-size:24px;color:#fff">▶</div>
          </div>
        </div>`;
      } else {
        brandedPreview = `<div class="contenido-card-preview" style="background:#000;display:flex;align-items:center;justify-content:center;min-height:200px;border-radius:12px">
          <div style="text-align:center;color:#fff">
            <div style="font-size:48px;margin-bottom:8px">🎬</div>
            <div style="font-size:13px;opacity:0.7">Reel generado</div>
          </div>
        </div>`;
      }
    } else if (mediaUrl) {
      brandedPreview = `<div class="contenido-card-preview"><img src="${escapeHtml(mediaUrl)}" alt="Preview" loading="lazy"></div>`;
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
      toast(`${n} Reel${n !== 1 ? 's' : ''} generado${n !== 1 ? 's' : ''} con voz + música`, 'success');
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

function abrirReelPreview(filePath) {
  let modal = document.getElementById('reel-preview-modal');
  if (!modal) {
    modal = document.createElement('div');
    modal.id = 'reel-preview-modal';
    modal.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,0.85);z-index:9999;display:flex;align-items:center;justify-content:center;cursor:pointer';
    modal.onclick = function() { this.remove(); };
    modal.innerHTML = `<div style="position:relative;max-height:90vh;max-width:90vw" onclick="event.stopPropagation()">
      <video id="reel-video-player" controls autoplay style="max-height:85vh;max-width:100%;border-radius:16px;box-shadow:0 8px 40px rgba(0,0,0,0.5)"></video>
      <button onclick="this.closest('#reel-preview-modal').remove()" style="position:absolute;top:-12px;right:-12px;width:32px;height:32px;border-radius:50%;background:#fff;border:none;font-size:18px;cursor:pointer;font-weight:700;box-shadow:0 2px 8px rgba(0,0,0,0.3)">✕</button>
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
        <button onclick="document.getElementById('publicar-modal').remove()" style="background:none;border:none;font-size:24px;cursor:pointer;color:var(--gray-600)">✕</button>
      </div>

      <div style="background:var(--cream);border-radius:12px;padding:16px;margin-bottom:16px">
        <div style="font-size:12px;font-weight:600;color:var(--gray-600);text-transform:uppercase;letter-spacing:0.5px;margin-bottom:8px">
          ${isReel ? 'Paso 1: Descargá el video' : 'Paso 1: Descargá la imagen'}
        </div>
        <button onclick="descargarMedia(${id})" class="btn btn-accent" style="width:100%;font-size:14px">
          ${isReel ? 'Descargar Reel (.mp4)' : 'Descargar imagen (.jpg)'}
        </button>
      </div>

      <div style="background:var(--cream);border-radius:12px;padding:16px;margin-bottom:16px">
        <div style="font-size:12px;font-weight:600;color:var(--gray-600);text-transform:uppercase;letter-spacing:0.5px;margin-bottom:8px">
          Paso 2: Copiá el caption
        </div>
        <textarea id="publicar-caption" readonly style="width:100%;min-height:120px;border:1.5px solid #e5e7eb;border-radius:8px;padding:12px;font-size:13px;font-family:inherit;resize:vertical;box-sizing:border-box;color:var(--ink)">${caption.replace(/</g,'&lt;')}</textarea>
        <button onclick="copiarCaption()" class="btn btn-outline" style="width:100%;margin-top:8px;font-size:14px">Copiar caption + hashtags</button>
      </div>

      <div style="background:var(--cream);border-radius:12px;padding:16px;margin-bottom:16px">
        <div style="font-size:12px;font-weight:600;color:var(--gray-600);text-transform:uppercase;letter-spacing:0.5px;margin-bottom:8px">
          Paso 3: Subilo a Instagram
        </div>
        <p style="font-size:13px;color:var(--gray-600);margin:0;line-height:1.6">
          ${isReel ? 'Abrí Instagram → + → Reel → seleccioná el video → pegá el caption → Publicar' : 'Abrí Instagram → + → Post → seleccioná la imagen → pegá el caption → Publicar'}
        </p>
      </div>

      <button onclick="marcarPublicado(${id})" class="btn" style="width:100%;background:#8B5CF6;color:#fff;font-size:14px;padding:12px">
        Ya lo publiqué — marcar como publicado
      </button>
    </div>
  `;
  modal.onclick = function() { this.remove(); };
  document.body.appendChild(modal);
}

function descargarMedia(id) {
  const c = _contenidos.find(x => x.id === id);
  if (!c || !c.media_url) return;

  const a = document.createElement('a');
  a.href = c.media_url;
  a.download = c._is_reel ? `reel_${id}.mp4` : `post_${id}.jpg`;
  a.click();
  toast('Descarga iniciada', 'success');
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

document.getElementById('contenidos-filtro')?.addEventListener('change', (e) => {
  _filtroEstado = e.target.value;
  _fetchContenidos();
});
