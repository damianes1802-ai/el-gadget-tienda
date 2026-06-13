/* ============================================================
   EL GADGET — Carrito compartido (localStorage)
   Item: { sku, nombre, precio, imagen, cantidad, color, talle }
   ============================================================ */

const CARRITO_KEY = 'carrito';

function getCarrito() {
  return JSON.parse(localStorage.getItem(CARRITO_KEY) || '[]');
}

function guardarCarrito(carrito) {
  localStorage.setItem(CARRITO_KEY, JSON.stringify(carrito));
}

function cartCount(carrito) {
  return carrito.reduce((s, i) => s + i.cantidad, 0);
}

function cartTotal(carrito) {
  return carrito.reduce((s, i) => s + i.precio * i.cantidad, 0);
}

function formatPrice(val) {
  const n = parseFloat(val) || 0;
  return '$' + n.toLocaleString('es-AR', { maximumFractionDigits: 0 });
}

/**
 * Refresca el badge del header y la barra inferior de carrito
 * en cualquier página que incluya esos elementos (#cartBadge, #cartBar,
 * #cartBarCount, #cartBarTotal). Devuelve el carrito actual.
 */
function actualizarCarritoUI() {
  const carrito = getCarrito();
  const count = cartCount(carrito);
  const total = cartTotal(carrito);

  const badge = document.getElementById('cartBadge');
  if (badge) badge.textContent = count;

  const bar = document.getElementById('cartBar');
  const barCount = document.getElementById('cartBarCount');
  const barTotal = document.getElementById('cartBarTotal');
  if (barCount) barCount.textContent = count;
  if (barTotal) barTotal.textContent = formatPrice(total);
  if (bar) bar.classList.toggle('show', count > 0);

  return carrito;
}

/**
 * Agrega un producto al carrito (o incrementa su cantidad si ya existe,
 * matcheando por SKU). item: { sku, nombre, precio, imagen, cantidad, color, talle }
 * Cada página define su propio "agregarAlCarrito(...)" (con la firma que
 * necesite) que internamente llama a esta función de bajo nivel.
 */
function addCartItem(item) {
  const carrito = getCarrito();
  const existente = carrito.find(i => i.sku === item.sku);
  if (existente) {
    existente.cantidad += item.cantidad || 1;
  } else {
    carrito.push({
      sku: item.sku,
      nombre: item.nombre,
      precio: item.precio,
      imagen: item.imagen || '',
      color: item.color || '',
      talle: item.talle || '',
      cantidad: item.cantidad || 1
    });
  }
  guardarCarrito(carrito);
  actualizarCarritoUI();
  return carrito;
}

function showToast(msg) {
  const t = document.getElementById('toast');
  if (!t) return;
  t.textContent = msg;
  t.classList.add('show');
  clearTimeout(t._timer);
  t._timer = setTimeout(() => t.classList.remove('show'), 2200);
}

document.addEventListener('DOMContentLoaded', actualizarCarritoUI);
