/* ============================================================
   MARKETING EL GADGET — gráficos CSS/SVG
   ============================================================ */

const CHART_COLORS = {
  referido: '#FFC700',
  organico: '#14151A',
  promo: '#7A3FC4',
  mayorista: '#2E8B57',
  default: '#D1D5DB',
};

function renderTrendCard(container, { label, value, delta, sparkData, sub }) {
  const deltaHtml = delta
    ? `<span class="delta ${delta.cls}">${escapeHtml(delta.text)}</span>`
    : '';
  const sparkHtml = sparkData && sparkData.length > 1
    ? renderSparklineSVG(sparkData, 80, 28)
    : '';
  const subHtml = sub ? `<div class="stat-sub">${escapeHtml(sub)}</div>` : '';
  container.innerHTML = `
    <div class="stat-label">${escapeHtml(label)}</div>
    <div class="stat-row">
      <div class="stat-value">${value}</div>
      ${deltaHtml}
    </div>
    ${sparkHtml}
    ${subHtml}
  `;
}

function renderSparklineSVG(values, w = 80, h = 28) {
  if (!values || values.length < 2) return '';
  const max = Math.max(...values) || 1;
  const min = Math.min(...values);
  const range = max - min || 1;
  const step = w / (values.length - 1);
  const points = values.map((v, i) => `${(i * step).toFixed(1)},${(h - 2 - ((v - min) / range) * (h - 4)).toFixed(1)}`).join(' ');
  return `<svg class="sparkline" width="${w}" height="${h}" viewBox="0 0 ${w} ${h}"><polyline fill="none" stroke="var(--accent)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" points="${points}"/></svg>`;
}

function renderBarChart(container, data, { labelKey = 'mes', stacked = false, sources = ['referido', 'organico', 'promo', 'mayorista'] } = {}) {
  if (!data || !data.length) { container.innerHTML = '<div class="chart-empty">Sin datos</div>'; return; }

  const maxVal = stacked
    ? Math.max(...data.map(d => sources.reduce((s, k) => s + (d[k] || 0), 0)))
    : Math.max(...data.map(d => d.total || 0));

  if (maxVal === 0) { container.innerHTML = '<div class="chart-empty">Sin datos</div>'; return; }

  const barsHtml = data.map(d => {
    const label = (d[labelKey] || '').replace(/^\d{4}-/, '');
    if (stacked) {
      const segments = sources.map(s => {
        const val = d[s] || 0;
        const pct = (val / maxVal) * 100;
        return pct > 0 ? `<div class="bar-seg" style="height:${pct.toFixed(1)}%;background:${CHART_COLORS[s] || CHART_COLORS.default}" title="${s}: ${formatPrice(val)}"></div>` : '';
      }).join('');
      return `<div class="bar-col"><div class="bar-stack">${segments}</div><div class="bar-label">${escapeHtml(label)}</div></div>`;
    }
    const pct = ((d.total || 0) / maxVal) * 100;
    return `<div class="bar-col"><div class="bar" style="height:${pct.toFixed(1)}%"></div><div class="bar-label">${escapeHtml(label)}</div></div>`;
  }).join('');

  const legendHtml = stacked
    ? `<div class="chart-legend">${sources.map(s => `<span class="legend-item"><span class="legend-dot" style="background:${CHART_COLORS[s]}"></span>${s}</span>`).join('')}</div>`
    : '';

  container.innerHTML = `<div class="bar-chart">${barsHtml}</div>${legendHtml}`;
}

function renderDonut(container, segments, { size = 140, strokeWidth = 24 } = {}) {
  const total = segments.reduce((s, seg) => s + seg.value, 0);
  if (total === 0) { container.innerHTML = '<div class="chart-empty">Sin datos</div>'; return; }

  const r = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * r;
  let offset = 0;

  const arcs = segments.map(seg => {
    const pct = seg.value / total;
    const dashLen = pct * circumference;
    const dashOffset = -offset;
    offset += dashLen;
    return `<circle cx="${size / 2}" cy="${size / 2}" r="${r}" fill="none"
      stroke="${seg.color || CHART_COLORS.default}" stroke-width="${strokeWidth}"
      stroke-dasharray="${dashLen.toFixed(2)} ${(circumference - dashLen).toFixed(2)}"
      stroke-dashoffset="${dashOffset.toFixed(2)}" />`;
  }).join('');

  const legendHtml = segments.map(seg => {
    const pct = ((seg.value / total) * 100).toFixed(1);
    return `<div class="donut-legend-item">
      <span class="legend-dot" style="background:${seg.color}"></span>
      <span>${escapeHtml(seg.label)}</span>
      <strong>${formatPrice(seg.value)}</strong>
      <span class="donut-pct">${pct}%</span>
    </div>`;
  }).join('');

  container.innerHTML = `
    <div class="donut-wrap">
      <svg width="${size}" height="${size}" class="donut-svg">
        <circle cx="${size / 2}" cy="${size / 2}" r="${r}" fill="none" stroke="#e5e7eb" stroke-width="${strokeWidth}" />
        ${arcs}
      </svg>
      <div class="donut-center">${formatPrice(total)}</div>
    </div>
    <div class="donut-legend">${legendHtml}</div>
  `;
}

function renderHBarChart(container, items, { maxItems = 10, valueKey = 'value', labelKey = 'label', colorKey = null } = {}) {
  const data = items.slice(0, maxItems);
  if (!data.length) { container.innerHTML = '<div class="chart-empty">Sin datos</div>'; return; }
  const maxVal = Math.max(...data.map(d => d[valueKey] || 0)) || 1;

  container.innerHTML = data.map((d, i) => {
    const pct = ((d[valueKey] || 0) / maxVal) * 100;
    const color = colorKey ? (d[colorKey] || CHART_COLORS.default) : 'var(--accent)';
    return `<div class="hbar-row">
      <span class="hbar-rank">${i + 1}</span>
      <span class="hbar-label">${escapeHtml(d[labelKey])}</span>
      <div class="hbar-track"><div class="hbar-fill" style="width:${pct.toFixed(1)}%;background:${color}"></div></div>
      <span class="hbar-value">${formatPrice(d[valueKey])}</span>
    </div>`;
  }).join('');
}
