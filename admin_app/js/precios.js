/* ============================================================
   PANEL EL GADGET — Configuración de precios (perfil "default")
   ============================================================ */

let precioCargos = [];

async function loadPrecios() {
  try {
    const config = await apiCall('get_precios_config');
    const perfil = (config.perfiles_precio || {}).default || {};

    document.getElementById('precios-margen').value = perfil.margen_porcentaje ?? 50;

    const redondeo = perfil.redondeo || {};
    document.getElementById('precios-redondeo-activo').checked = !!redondeo.activo;
    document.getElementById('precios-redondeo-multiplo').value = redondeo.multiplo ?? 500;

    precioCargos = (perfil.cargos_fijos || []).map(c => ({ ...c }));
    renderCargos();
    actualizarPreview();
  } catch (e) {
    toast('Error al cargar la configuración de precios: ' + e.message, 'error');
  }
}

function renderCargos() {
  const cont = document.getElementById('precios-cargos');
  if (!precioCargos.length) {
    cont.innerHTML = '<p style="font-size:12px;color:var(--gray-600)">Sin cargos fijos configurados.</p>';
    return;
  }

  cont.innerHTML = precioCargos.map((c, i) => `
    <div class="cargo-row">
      <div class="field field-nombre">
        <label>Nombre</label>
        <input type="text" value="${escapeHtml(c.nombre || '')}" data-idx="${i}" data-field="nombre" onchange="actualizarCargo(this)">
      </div>
      <div class="field field-valor">
        <label>Valor ($)</label>
        <input type="number" value="${c.valor ?? 0}" step="50" data-idx="${i}" data-field="valor" onchange="actualizarCargo(this)" oninput="actualizarCargo(this)">
      </div>
      <div class="field-activo">
        <label><input type="checkbox" ${c.activo !== false ? 'checked' : ''} data-idx="${i}" data-field="activo" onchange="actualizarCargo(this)"> Activo</label>
      </div>
      <button class="btn btn-danger btn-sm btn-quitar" onclick="quitarCargo(${i})">Quitar</button>
    </div>
  `).join('');
}

function actualizarCargo(input) {
  const idx = parseInt(input.dataset.idx, 10);
  const field = input.dataset.field;
  if (field === 'activo') {
    precioCargos[idx].activo = input.checked;
  } else if (field === 'valor') {
    precioCargos[idx].valor = parseFloat(input.value) || 0;
  } else {
    precioCargos[idx][field] = input.value;
  }
  actualizarPreview();
}

function quitarCargo(idx) {
  precioCargos.splice(idx, 1);
  renderCargos();
  actualizarPreview();
}

document.getElementById('btn-agregar-cargo').addEventListener('click', () => {
  precioCargos.push({
    id: 'cargo_' + Date.now(),
    nombre: 'Nuevo cargo',
    valor: 0,
    activo: true,
    notas: '',
  });
  renderCargos();
  actualizarPreview();
});

['precios-margen', 'precios-redondeo-activo', 'precios-redondeo-multiplo', 'precios-preview-costo'].forEach(id => {
  document.getElementById(id).addEventListener('input', actualizarPreview);
});

// ── Cálculo (mismo algoritmo que scripts/04_calculo_precios.py) ──
function redondearComercial(precio, multiplo) {
  if (!multiplo) return precio;
  const resto = precio % multiplo;
  if (resto === 0) return precio;
  return precio + (multiplo - resto);
}

function calcularPrecioVenta(precioCosto, perfil) {
  const cargosActivos = (perfil.cargos_fijos || []).filter(c => c.activo !== false);
  const totalCargos = cargosActivos.reduce((sum, c) => sum + (parseFloat(c.valor) || 0), 0);
  const subtotal = precioCosto + totalCargos;
  const margen = parseFloat(perfil.margen_porcentaje) || 0;
  const precioConMargen = subtotal * (1 + margen / 100);

  let precioFinal = precioConMargen;
  const redondeo = perfil.redondeo || {};
  if (redondeo.activo) {
    precioFinal = redondearComercial(precioConMargen, parseFloat(redondeo.multiplo) || 500);
  }

  return {
    precioCosto, totalCargos, cargosActivos, subtotal, margen,
    precioConMargen, precioFinal, gananciaNeta: precioFinal - precioCosto,
  };
}

function leerPerfilFormulario() {
  return {
    margen_porcentaje: parseFloat(document.getElementById('precios-margen').value) || 0,
    cargos_fijos: precioCargos,
    redondeo: {
      activo: document.getElementById('precios-redondeo-activo').checked,
      multiplo: parseFloat(document.getElementById('precios-redondeo-multiplo').value) || 500,
      direccion: 'arriba',
    },
  };
}

function actualizarPreview() {
  const costo = parseFloat(document.getElementById('precios-preview-costo').value) || 0;
  const perfil = leerPerfilFormulario();
  const r = calcularPrecioVenta(costo, perfil);

  const desglose = r.cargosActivos.map(c =>
    `<div class="label">${escapeHtml(c.nombre || '')}</div><div class="value">${formatPrice(c.valor)}</div>`
  ).join('');

  document.getElementById('precios-preview-resultado').innerHTML = `
    <div class="label">Precio de costo</div><div class="value">${formatPrice(r.precioCosto)}</div>
    ${desglose}
    <div class="label">Subtotal (costo + cargos)</div><div class="value">${formatPrice(r.subtotal)}</div>
    <div class="label">Margen aplicado</div><div class="value">${r.margen}%</div>
    <div class="label">Precio con margen</div><div class="value">${formatPrice(r.precioConMargen)}</div>
    <div class="total-row">
      <div class="label">Precio final de venta</div><div class="value accent">${formatPrice(r.precioFinal)}</div>
    </div>
    <div class="total-row">
      <div class="label">Ganancia neta</div><div class="value">${formatPrice(r.gananciaNeta)}</div>
    </div>
  `;
}

// ── Guardar ──
document.getElementById('btn-guardar-precios').addEventListener('click', async () => {
  const perfil = leerPerfilFormulario();
  try {
    await apiCall('guardar_precios_config', perfil);
    toast('Configuración guardada. Iniciando redeploy…', 'success');
    const r = await apiCall('trigger_redeploy');
    if (r && r.error) {
      toast('Redeploy: ' + r.error, 'error');
    } else {
      toast('Redeploy en curso (~5 min). Los precios se actualizarán automáticamente.', 'success');
    }
  } catch (e) {
    toast('Error al guardar: ' + e.message, 'error');
  }
});
