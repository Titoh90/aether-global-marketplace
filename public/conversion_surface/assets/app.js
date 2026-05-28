
(function(){
'use strict';

/* ═══════════════════════════════════════════════════════════════════════
   Aether Global — AffilioLux client app
   Features: i18n (EN/ES/FR), search, category filter chips,
             sort, IntersectionObserver lazy loading, bottom nav
   ═══════════════════════════════════════════════════════════════════════ */

// ── Data ─────────────────────────────────────────────────────────────────────

var DATA       = JSON.parse(document.getElementById('products-data').textContent);
var I18N       = JSON.parse(document.getElementById('translations-data').textContent);
var PRODUCTS   = DATA.products   || [];
var CATEGORIES = DATA.categories || [];

// ── State ─────────────────────────────────────────────────────────────────────

var App = {
  lang:      _detectLang(),
  category:  'all',
  query:     '',
  sort:      'default',
  activeNav: 'shop',

  t: function(key) {
    return (I18N[this.lang] && I18N[this.lang][key])
      || (I18N['en'] && I18N['en'][key])
      || key;
  },

  reset: function() {
    this.category  = 'all';
    this.query     = '';
    this.sort      = 'default';
    this.activeNav = 'shop';
    var sortSel = document.getElementById('sort-select');
    if (sortSel) sortSel.value = 'default';
    var input = document.getElementById('search-input');
    if (input) input.value = '';
    var clear = document.getElementById('search-clear');
    if (clear) clear.classList.add('hidden');
    _updateNavUI('shop');
    this.render();
    window.scrollTo({top: 0, behavior: 'smooth'});
  },

  setLang: function(lang) {
    this.lang = lang;
    _saveLang(lang);
    var display = document.getElementById('lang-display');
    if (display) display.textContent = lang.toUpperCase();
    this.render();
  },

  clearSearch: function() {
    this.query = '';
    var input = document.getElementById('search-input');
    if (input) input.value = '';
    var clear = document.getElementById('search-clear');
    if (clear) clear.classList.add('hidden');
    this.render();
  },

  filterCategory: function(cat) {
    this.category = cat;
    this.render();
  },

  setSort: function(val) {
    this.sort = val;
    this.render();
  },

  navShop: function() {
    this.activeNav = 'shop';
    this.category  = 'all';
    this.query     = '';
    _updateNavUI('shop');
    this.render();
    window.scrollTo({top: 0, behavior: 'smooth'});
  },

  navTrends: function() {
    this.activeNav = 'trends';
    this.category  = 'all';
    this.query     = '';
    _updateNavUI('trends');
    this.render();
    window.scrollTo({top: 0, behavior: 'smooth'});
  },

  navSaved: function() {
    this.activeNav = 'saved';
    _updateNavUI('saved');
    this.render();
  },

  getFilteredProducts: function() {
    var prods = PRODUCTS.slice();

    // Trending nav: only show trending-tagged products
    if (this.activeNav === 'trends') {
      prods = prods.filter(function(p) {
        return p.tags && p.tags.indexOf('trending') !== -1;
      });
    }

    if (this.category !== 'all') {
      prods = prods.filter(function(p) { return p.category === App.category; });
    }

    if (this.query) {
      var q = this.query.toLowerCase();
      prods = prods.filter(function(p) {
        return (p.title    || '').toLowerCase().indexOf(q) !== -1
            || (p.category || '').toLowerCase().indexOf(q) !== -1
            || ((p.description && (p.description[App.lang] || p.description['en'])) || '').toLowerCase().indexOf(q) !== -1;
      });
    }

    switch (this.sort) {
      case 'trending':
        prods.sort(function(a, b) {
          return (b.tags && b.tags.indexOf('trending') !== -1 ? 1 : 0)
               - (a.tags && a.tags.indexOf('trending') !== -1 ? 1 : 0);
        });
        break;
      case 'bestseller':
        prods.sort(function(a, b) {
          return (b.tags && b.tags.indexOf('bestseller') !== -1 ? 1 : 0)
               - (a.tags && a.tags.indexOf('bestseller') !== -1 ? 1 : 0);
        });
        break;
      case 'rating':
        prods.sort(function(a, b) { return (b.rating || 0) - (a.rating || 0); });
        break;
      case 'price-low':
        prods.sort(function(a, b) { return (a.price || 0) - (b.price || 0); });
        break;
      case 'price-high':
        prods.sort(function(a, b) { return (b.price || 0) - (a.price || 0); });
        break;
    }

    return prods;
  },

  render: function() {
    _updateI18nText();
    _renderCategories();
    _renderProducts();
  },
};

// ── Nav UI ────────────────────────────────────────────────────────────────────

function _updateNavUI(active) {
  ['shop', 'trends', 'saved', 'account'].forEach(function(id) {
    var btn = document.getElementById('nav-' + id);
    if (!btn) return;
    if (id === active) {
      btn.className = 'flex flex-col items-center justify-center px-4 py-1 rounded-xl text-xs bg-primary-container text-on-primary-container transition-all active:scale-90';
    } else {
      btn.className = 'flex flex-col items-center justify-center px-4 py-1 rounded-xl text-xs text-secondary transition-all active:scale-90';
    }
  });
}

// ── i18n text updates ─────────────────────────────────────────────────────────

function _updateI18nText() {
  var pageTitle    = document.getElementById('page-title');
  var pageSubtitle = document.getElementById('page-subtitle');
  var footerDisc   = document.getElementById('footer-disclaimer');
  var noResText    = document.getElementById('no-results-text');

  if (pageTitle)    pageTitle.textContent    = App.t('pageTitle');
  if (pageSubtitle) pageSubtitle.textContent = App.t('pageSubtitle');
  if (footerDisc)   footerDisc.textContent   = App.t('footerDisclaimer');
  if (noResText)    noResText.textContent    = App.t('noResults');

  // Nav labels
  ['shop','trends','saved','account'].forEach(function(id) {
    var el = document.getElementById('nav-' + id + '-label');
    if (el) el.textContent = App.t('nav' + id.charAt(0).toUpperCase() + id.slice(1));
  });

  // Sort options
  var sortSel = document.getElementById('sort-select');
  if (sortSel) {
    var opts = sortSel.querySelectorAll('option');
    var labels = [App.t('sortDefault'), App.t('sortTrending'), App.t('sortBestseller'), App.t('sortRating'), App.t('sortPriceLow'), App.t('sortPriceHigh')];
    opts.forEach(function(opt, i) { if (labels[i]) opt.textContent = labels[i]; });
  }

  // Search placeholder
  var input = document.getElementById('search-input');
  if (input) input.placeholder = App.t('searchPlaceholder') || 'Search products...';
}

// ── Category filter chips ─────────────────────────────────────────────────────

function _renderCategories() {
  var bar = document.getElementById('filter-bar');
  if (!bar) return;

  var ON  = 'px-4 py-1.5 rounded-full text-xs font-semibold shrink-0 border transition-all bg-primary-container text-on-primary-container border-transparent';
  var OFF = 'px-4 py-1.5 rounded-full text-xs font-semibold shrink-0 border transition-all bg-surface-container-lowest text-on-surface border-outline-variant';

  var chips = '';
  chips += '<button class="' + (App.category === 'all' ? ON : OFF) + '" onclick="App.filterCategory(\'all\')">'
         + _escHtml(App.t('allCategories')) + '</button>';

  CATEGORIES.forEach(function(cat) {
    chips += '<button class="' + (App.category === cat ? ON : OFF) + '" '
           + 'onclick="App.filterCategory(\'' + _escAttr(cat) + '\')">'
           + _escHtml(cat) + '</button>';
  });

  bar.innerHTML = chips;
}

// ── Product rendering ─────────────────────────────────────────────────────────

function _renderProducts() {
  var grid      = document.getElementById('product-grid');
  var countEl   = document.getElementById('products-count');
  var noResults = document.getElementById('no-results');
  if (!grid) return;

  var filtered = App.getFilteredProducts();

  if (countEl) {
    countEl.textContent = filtered.length + ' ' + App.t('productsFound');
  }

  if (filtered.length === 0) {
    grid.innerHTML = '';
    if (noResults) noResults.classList.remove('hidden');
    return;
  }

  if (noResults) noResults.classList.add('hidden');

  var html = '';
  filtered.forEach(function(p, idx) {
    html += _renderCard(p, idx);
  });
  grid.innerHTML = html;

  _setupLazyImages();
}

function _renderCard(p, idx) {
  var url      = _escAttr(p.affiliateUrl || '#');
  var urlRaw   = p.affiliateUrl || '#';
  var title    = _escHtml(p.title || '');
  var category = _escHtml(p.category || '');
  var price    = p.price ? '$' + p.price.toFixed(2) : '';
  var imgSrc   = _escAttr(p.image || '');
  var delay    = (Math.min(idx, 10) * 0.04).toFixed(2);

  // Badge
  var badge = '';
  if (p.tags && p.tags.indexOf('trending') !== -1) {
    badge = '<div class="absolute top-3 left-3 bg-primary-container text-on-primary-container px-2 py-0.5 rounded text-xs font-semibold uppercase tracking-wider">'
          + _escHtml(App.t('trendingLabel')) + '</div>';
  } else if (p.tags && p.tags.indexOf('bestseller') !== -1) {
    badge = '<div class="absolute top-3 left-3 bg-surface-container-highest text-on-surface px-2 py-0.5 rounded text-xs font-semibold uppercase tracking-wider border border-outline-variant">'
          + _escHtml(App.t('bestseller')) + '</div>';
  } else if (p.tags && p.tags.indexOf('limited') !== -1) {
    badge = '<div class="absolute top-3 left-3 bg-error-container text-on-error-container px-2 py-0.5 rounded text-xs font-semibold uppercase tracking-wider">'
          + _escHtml(App.t('limitedOffer')) + '</div>';
  }

  // Star rating
  var ratingHtml = '';
  if (p.rating && p.rating > 0) {
    var stars = '';
    for (var i = 0; i < 5; i++) {
      var fill = i < Math.round(p.rating) ? '1' : '0';
      stars += '<span class="material-symbols-outlined text-primary-container" style="font-size:14px;font-variation-settings:\'FILL\' ' + fill + '">star</span>';
    }
    var reviewStr = p.reviews ? ' (' + p.reviews.toLocaleString() + ')' : '';
    ratingHtml = '<div class="flex items-center gap-0.5 mt-1">'
               + stars
               + '<span class="text-xs text-secondary ml-1">' + p.rating.toFixed(1) + _escHtml(reviewStr) + '</span>'
               + '</div>';
  }

  return '<article class="product-card bg-surface-container-lowest rounded-xl shadow-sm overflow-hidden flex flex-col animate-in" '
       + 'style="animation-delay:' + delay + 's">'

       // Image area — clicking opens affiliate link
       + '<div class="relative w-full aspect-square bg-surface-container-low cursor-pointer" '
       + 'onclick="window.open(\'' + url + '\',\'_blank\')">'
       + '<img data-src="' + imgSrc + '" alt="' + title + '" '
       + 'class="card-img w-full h-full object-contain mix-blend-multiply p-4" onerror="this.hidden=true">'
       + badge
       + '</div>'

       // Card body
       + '<div class="p-4 flex flex-col gap-1">'
       + '<div class="text-xs font-semibold text-on-surface-variant uppercase tracking-wider">' + category + '</div>'
       + '<h3 class="text-sm font-medium text-on-surface line-clamp-2 leading-snug">' + title + '</h3>'
       + ratingHtml
       + '<div class="flex justify-between items-end mt-3">'
       + (price ? '<div class="text-xl font-semibold text-on-surface">' + _escHtml(price) + '</div>' : '<div></div>')
       + '<a href="' + url + '" target="_blank" rel="noopener noreferrer sponsored" '
       + 'class="bg-primary-container text-on-primary-container hover:bg-tertiary-container active:scale-95 transition-all px-4 py-2 rounded-lg text-xs font-semibold flex items-center gap-1 shadow-sm">'
       + '<span class="material-symbols-outlined" style="font-size:16px">shopping_cart</span>'
       + _escHtml(App.t('buyOnAmazon'))
       + '</a>'
       + '</div>'
       + '</div>'

       + '</article>';
}

// ── Lazy Loading ──────────────────────────────────────────────────────────────

var _observer = null;

function _setupLazyImages() {
  if (_observer) _observer.disconnect();

  if ('IntersectionObserver' in window) {
    _observer = new IntersectionObserver(function(entries) {
      entries.forEach(function(entry) {
        if (!entry.isIntersecting) return;
        var img = entry.target;
        var src = img.getAttribute('data-src');
        // Use getAttribute('src') — NOT img.src (DOM property always returns absolute URL)
        if (src && !img.getAttribute('src')) {
          img.src = src;
        }
        img.classList.add('loaded');
        _observer.unobserve(img);
      });
    }, { rootMargin: '300px' });

    document.querySelectorAll('.card-img').forEach(function(img) {
      _observer.observe(img);
    });
  } else {
    // Fallback: load all immediately
    document.querySelectorAll('.card-img').forEach(function(img) {
      var src = img.getAttribute('data-src');
      if (src && !img.getAttribute('src')) img.src = src;
      img.classList.add('loaded');
    });
  }
}

// ── Search ────────────────────────────────────────────────────────────────────

function _setupSearch() {
  var toggle    = document.getElementById('search-toggle');
  var searchBar = document.getElementById('search-bar');
  var input     = document.getElementById('search-input');
  var clear     = document.getElementById('search-clear');

  if (toggle && searchBar) {
    toggle.addEventListener('click', function() {
      searchBar.classList.toggle('hidden');
      if (!searchBar.classList.contains('hidden') && input) {
        input.focus();
      }
    });
  }

  if (input) {
    var debounce;
    input.addEventListener('input', function() {
      if (clear) clear.classList.toggle('hidden', input.value.length === 0);
      clearTimeout(debounce);
      debounce = setTimeout(function() {
        App.query = input.value.trim();
        App.render();
      }, 220);
    });

    input.addEventListener('keydown', function(e) {
      if (e.key === 'Escape') {
        if (searchBar) searchBar.classList.add('hidden');
        input.value = '';
        App.clearSearch();
      }
    });
  }

  if (clear) {
    clear.addEventListener('click', function() {
      App.clearSearch();
    });
  }
}

// ── Sort ──────────────────────────────────────────────────────────────────────

function _setupSort() {
  var sel = document.getElementById('sort-select');
  if (sel) {
    sel.addEventListener('change', function() {
      App.setSort(sel.value);
    });
  }
}

// ── Language ──────────────────────────────────────────────────────────────────

var _LANGS = ['en', 'es', 'fr'];

function _setupLang() {
  var btn = document.getElementById('lang-cycle');
  if (!btn) return;
  btn.addEventListener('click', function() {
    var idx  = _LANGS.indexOf(App.lang);
    var next = _LANGS[(idx + 1) % _LANGS.length];
    App.setLang(next);
  });
}

function _detectLang() {
  try {
    var stored = localStorage.getItem('aether_lang');
    if (stored && I18N[stored]) return stored;
  } catch(e) {}
  var nav = (navigator.language || navigator.userLanguage || 'en').split('-')[0].toLowerCase();
  return I18N[nav] ? nav : 'en';
}

function _saveLang(lang) {
  try { localStorage.setItem('aether_lang', lang); } catch(e) {}
}

// ── Brand link ────────────────────────────────────────────────────────────────

function _setupBrandLink() {
  var link = document.getElementById('brand-link');
  if (link) {
    link.addEventListener('click', function(e) {
      e.preventDefault();
      App.reset();
    });
  }
}

// ── Utilities ─────────────────────────────────────────────────────────────────

function _escHtml(s) {
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function _escAttr(s) {
  return String(s)
    .replace(/&/g,  '&amp;')
    .replace(/"/g,  '&quot;')
    .replace(/'/g,  '&#39;')
    .replace(/</g,  '&lt;')
    .replace(/>/g,  '&gt;');
}

// ── Init ──────────────────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', function() {
  var display = document.getElementById('lang-display');
  if (display) display.textContent = App.lang.toUpperCase();

  _setupSearch();
  _setupSort();
  _setupLang();
  _setupBrandLink();
  App.render();
});

window.App = App;

})();
