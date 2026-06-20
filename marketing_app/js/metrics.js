/* ============================================================
   MARKETING EL GADGET — motor de métricas (puro, sin DOM)
   ============================================================ */

function attrSource(orden, referidosCodigos, descuentosMap) {
  const code = (orden.descuento_codigo || '').toUpperCase();
  if (!code) return 'organico';
  if (referidosCodigos.has(code)) return 'referido';
  const desc = descuentosMap[code];
  if (desc && desc.valor === 25 && desc.tipo === 'porcentaje') return 'mayorista';
  if (desc) return 'promo';
  return 'organico';
}

function buildLookups(referidos, descuentos) {
  const referidosCodigos = new Set((referidos || []).map(r => (r.codigo || '').toUpperCase()));
  const descuentosMap = {};
  (descuentos || []).forEach(d => {
    if (d.codigo) descuentosMap[d.codigo.toUpperCase()] = d;
  });
  return { referidosCodigos, descuentosMap };
}

function enrichOrdenes(ordenes, referidos, descuentos) {
  const { referidosCodigos, descuentosMap } = buildLookups(referidos, descuentos);
  return (ordenes || [])
    .filter(o => o.estado_pago === 'approved')
    .map(o => ({
      ...o,
      _source: attrSource(o, referidosCodigos, descuentosMap),
      _fecha: o.fecha ? new Date(o.fecha.includes('T') ? o.fecha : o.fecha.replace(' ', 'T')) : null,
      _mes: o.fecha ? o.fecha.substring(0, 7) : null,
    }));
}

function filterPeriod(ordenes, period) {
  const now = new Date();
  const startOfDay = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  let cutoff;
  switch (period) {
    case 'today': cutoff = startOfDay; break;
    case '7d': cutoff = new Date(now - 7 * 86400000); break;
    case '30d': cutoff = new Date(now - 30 * 86400000); break;
    case '90d': cutoff = new Date(now - 90 * 86400000); break;
    case 'ytd': cutoff = new Date(now.getFullYear(), 0, 1); break;
    default: return ordenes;
  }
  return ordenes.filter(o => o._fecha && o._fecha >= cutoff);
}

function calcRevenue(ordenes) {
  return ordenes.reduce((s, o) => s + (o.total || 0), 0);
}

function calcAOV(ordenes) {
  return ordenes.length > 0 ? calcRevenue(ordenes) / ordenes.length : 0;
}

function calcRevenueBySource(ordenes) {
  const result = { referido: 0, organico: 0, promo: 0, mayorista: 0 };
  ordenes.forEach(o => { result[o._source] = (result[o._source] || 0) + (o.total || 0); });
  return result;
}

function calcCountBySource(ordenes) {
  const result = { referido: 0, organico: 0, promo: 0, mayorista: 0 };
  ordenes.forEach(o => { result[o._source] = (result[o._source] || 0) + 1; });
  return result;
}

function calcRevenueByMonth(ordenes, months = 12) {
  const byMonth = {};
  ordenes.forEach(o => {
    if (!o._mes) return;
    if (!byMonth[o._mes]) byMonth[o._mes] = { referido: 0, organico: 0, promo: 0, mayorista: 0, total: 0 };
    byMonth[o._mes][o._source] += o.total || 0;
    byMonth[o._mes].total += o.total || 0;
  });
  const keys = Object.keys(byMonth).sort().slice(-months);
  return keys.map(k => ({ mes: k, ...byMonth[k] }));
}

function calcCurrentMonth(ordenes) {
  const now = new Date();
  const mes = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`;
  return ordenes.filter(o => o._mes === mes);
}

function calcPreviousMonth(ordenes) {
  const now = new Date();
  const prev = new Date(now.getFullYear(), now.getMonth() - 1, 1);
  const mes = `${prev.getFullYear()}-${String(prev.getMonth() + 1).padStart(2, '0')}`;
  return ordenes.filter(o => o._mes === mes);
}

function calcRepeatRate(clientes) {
  if (!clientes || !clientes.length) return 0;
  const repeat = clientes.filter(c => (c.cantidad_ordenes || 0) > 1).length;
  return (repeat / clientes.length) * 100;
}

function calcActiveReferidos(referidos) {
  return (referidos || []).filter(r => r.activo).length;
}

function calcReferidoRevenue(ordenes) {
  return calcRevenue(ordenes.filter(o => o._source === 'referido'));
}

function calcTopReferidos(referidos, n = 5) {
  return [...(referidos || [])]
    .filter(r => r.activo)
    .sort((a, b) => (b.comision_total || 0) - (a.comision_total || 0))
    .slice(0, n);
}

function calcTopProductos(estadisticas, n = 5) {
  return ((estadisticas || {}).top_productos || []).slice(0, n);
}

function calcSparkline(ordenes, months = 6) {
  const byMonth = calcRevenueByMonth(ordenes, months);
  return byMonth.map(m => m.total);
}

function calcReferidoTier(referido) {
  const pct = referido.porcentaje || referido.comision_porcentaje || 7;
  if (pct >= 15) return 'top';
  if (pct >= 11) return 'activo';
  return 'base';
}

function calcRevenueByZona(ordenes) {
  const result = {};
  ordenes.forEach(o => {
    const zona = o.zona_envio || 'sin_zona';
    result[zona] = (result[zona] || 0) + (o.total || 0);
  });
  return result;
}

function calcRevenueByDayOfWeek(ordenes) {
  const days = ['Dom', 'Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb'];
  const result = days.map(d => ({ day: d, total: 0, count: 0 }));
  ordenes.forEach(o => {
    if (!o._fecha) return;
    const idx = o._fecha.getDay();
    result[idx].total += o.total || 0;
    result[idx].count++;
  });
  return result;
}
