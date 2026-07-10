/* ============================================================
   EL GADGET — A/B Testing para landings /ganar/

   Asigna variante A o B al azar por visitante (persiste en localStorage).
   Swapea el hero de la landing y tagea los links con utm_content=a|b.
   ============================================================ */

(function() {
  const STORAGE_KEY = 'eg_abtest_variant';
  const page = location.pathname.replace(/\/$/, '');

  // Variantes B por landing (solo el hero cambia)
  const VARIANTS_B = {
    '/ganar/desde-casa': {
      badge: 'Para mamás que ya recomiendan',
      h1: '3 conocidos compran = <span>$5.215 para vos</span>',
      p: 'Cada vez que alguien compra con tu código, vos cobrás comisión. Automático. Sin stock. Sin horarios. El grupo de mamás puede ser tu mejor fuente de ingreso extra.',
      cta: 'Quiero mi código ahora',
    },
    '/ganar/monetizar-redes': {
      badge: 'Ingreso extra real',
      h1: 'WhatsApp + tu código = <span>comisiones todos los meses</span>',
      p: 'No necesitás seguidores. No necesitás experiencia. Le pasás un código de descuento a alguien, compra, y vos cobrás entre 7% y 15%. La matemática es simple.',
      cta: 'Dame mi código',
    },
    '/ganar/marketing-afiliados': {
      badge: 'Para creadoras que quieren cobrar',
      h1: 'Tu audiencia ya te pide recomendaciones.<br><span>¿Por qué no cobrar por ellas?</span>',
      p: 'Comisiones de 7% a 15% con tracking transparente. Sin contratos, sin mínimos de publicación. Productos reales que tu audiencia compra. Cobro el día 5 de cada mes.',
      cta: 'Empezar a monetizar',
    },
    '/ganar/vender-sin-stock': {
      badge: 'Margen real sin riesgo',
      h1: '25% de descuento mayorista.<br><span>Sin comprar stock.</span>',
      p: 'Empezás como referido cobrando comisiones. Cuando acumulás capital, accedés a precio mayorista con factura. Casi 300 productos en 10 categorías con envío seguro a todo el país.',
      cta: 'Empezar sin inversión',
    },
  };

  const variant = VARIANTS_B[page];
  if (!variant) return;

  // Asignar variante por landing (cada landing tiene su propio test)
  const key = STORAGE_KEY + '_' + page.replace(/\//g, '_');
  let assigned = localStorage.getItem(key);
  if (!assigned) {
    assigned = Math.random() < 0.5 ? 'a' : 'b';
    localStorage.setItem(key, assigned);
  }

  if (assigned === 'a') {
    // Variante A: no tocar nada, solo tagear links
    tagLinks('a');
    return;
  }

  // Variante B: swapear hero cuando el DOM esté listo
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function() { applyB(variant); });
  } else {
    applyB(variant);
  }

  function applyB(v) {
    var hero = document.querySelector('.g-hero');
    if (!hero) return;

    var badge = hero.querySelector('.g-badge');
    var h1 = hero.querySelector('h1');
    var p = hero.querySelector('p');
    var cta = hero.querySelector('.btn.btn-accent');

    if (badge && v.badge) badge.textContent = v.badge;
    if (h1 && v.h1) h1.innerHTML = v.h1;
    if (p && v.p) p.innerHTML = v.p;
    if (cta && v.cta) {
      cta.textContent = v.cta;
      // El copy de la variante B promete el código: el CTA tiene que llevar
      // al registro, no al ancla informativa de la variante A.
      var reg = document.getElementById('registro');
      if (reg) {
        cta.setAttribute('href', '#registro');
        cta.onclick = function(ev) {
          ev.preventDefault();
          reg.scrollIntoView({ behavior: 'smooth' });
        };
      }
    }

    tagLinks('b');
  }

  function tagLinks(variant) {
    // Agrega utm_content=a|b a todos los links de registro
    var links = document.querySelectorAll('a[href*="/referidos"]');
    links.forEach(function(a) {
      var href = a.getAttribute('href');
      if (href.indexOf('utm_content=') === -1) {
        var sep = href.indexOf('?') === -1 ? '?' : '&';
        a.setAttribute('href', href + sep + 'utm_content=abtest_' + variant);
      }
    });
  }
})();
