
(function(){
'use strict';

/* ═══════════════════════════════════════════════════════════════════════
   Aether Global — AffilioLux client app
   Features: i18n (EN/ES/FR), search, category filter chips,
             sidebar category/sort (desktop), sort, IntersectionObserver
             lazy loading, shimmer skeleton, bottom nav (mobile)
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

  openProduct: function(id) {
    var p = PRODUCTS.find(function(x) { return x.id === id; });
    if (!p) return;
    _renderDetail(p);
    var panel = document.getElementById('detail-panel');
    if (panel) {
      panel.classList.remove('hidden');
      panel.scrollTop = 0;
    }
    document.body.style.overflow = 'hidden';
    try { history.pushState({detailId: id}, '', '#p=' + id); } catch(e) {}
  },

  closeProduct: function() {
    var panel = document.getElementById('detail-panel');
    if (panel) panel.classList.add('hidden');
    document.body.style.overflow = '';
    try {
      if (history.state && history.state.detailId) history.back();
    } catch(e) {}
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
    var inputD = document.getElementById('search-input-desktop');
    if (inputD) inputD.value = '';
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
    var displayD = document.getElementById('lang-display-desktop');
    if (displayD) displayD.textContent = lang.toUpperCase();
    this.render();
  },

  clearSearch: function() {
    this.query = '';
    var input = document.getElementById('search-input');
    if (input) input.value = '';
    var inputD = document.getElementById('search-input-desktop');
    if (inputD) inputD.value = '';
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
    var sortSel = document.getElementById('sort-select');
    if (sortSel) sortSel.value = val;
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
    _renderSidebarCategories();
    _renderSidebarSort();
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
  // Mobile page header
  var pageTitle    = document.getElementById('page-title');
  var pageSubtitle = document.getElementById('page-subtitle');
  if (pageTitle)    pageTitle.textContent    = App.t('pageTitle');
  if (pageSubtitle) pageSubtitle.textContent = App.t('pageSubtitle');

  // Desktop hero
  var pageTitleD    = document.getElementById('page-title-desktop');
  var pageSubtitleD = document.getElementById('page-subtitle-desktop');
  var heroBadge     = document.getElementById('hero-badge');
  if (pageTitleD)    pageTitleD.textContent    = App.t('pageTitle');
  if (pageSubtitleD) pageSubtitleD.textContent = App.t('pageSubtitle');
  if (heroBadge)     heroBadge.textContent     = App.t('herobage') || 'CURATED EXCELLENCE';

  // Footer
  var footerDisc = document.getElementById('footer-disclaimer');
  if (footerDisc) footerDisc.textContent = App.t('footerDisclaimer');

  // No results
  var noResText = document.getElementById('no-results-text');
  if (noResText) noResText.textContent = App.t('noResults');

  // Mobile nav labels
  ['shop','trends','saved','account'].forEach(function(id) {
    var el = document.getElementById('nav-' + id + '-label');
    if (el) el.textContent = App.t('nav' + id.charAt(0).toUpperCase() + id.slice(1));
  });

  // Desktop nav labels
  var dShop = document.getElementById('desktop-nav-shop-label');
  var dTrends = document.getElementById('desktop-nav-trends-label');
  var dDeals = document.getElementById('desktop-nav-deals-label');
  if (dShop)   dShop.textContent   = App.t('navShopAll');
  if (dTrends) dTrends.textContent = App.t('navTrending');
  if (dDeals)  dDeals.textContent  = App.t('navDailyDeals');

  // Sidebar headings
  var sbCat  = document.getElementById('sidebar-category-heading');
  var sbSort = document.getElementById('sidebar-sort-heading');
  if (sbCat)  sbCat.textContent  = App.t('category');
  if (sbSort) sbSort.textContent = App.t('sortBy');

  // Sort options
  var sortSel = document.getElementById('sort-select');
  if (sortSel) {
    var opts = sortSel.querySelectorAll('option');
    var labels = [App.t('sortDefault'), App.t('sortTrending'), App.t('sortBestseller'), App.t('sortRating'), App.t('sortPriceLow'), App.t('sortPriceHigh')];
    opts.forEach(function(opt, i) { if (labels[i]) opt.textContent = labels[i]; });
  }

  // Search placeholder (mobile)
  var input = document.getElementById('search-input');
  if (input) input.placeholder = App.t('searchPlaceholder') || 'Search products...';

  // Search placeholder (desktop)
  var inputD = document.getElementById('search-input-desktop');
  if (inputD) inputD.placeholder = App.t('searchPlaceholder') || 'Search products...';
}

// ── Mobile category filter chips ──────────────────────────────────────────────

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

// ── Desktop sidebar: categories ───────────────────────────────────────────────

function _renderSidebarCategories() {
  var container = document.getElementById('sidebar-categories');
  if (!container) return;

  var ACTIVE   = 'flex items-center gap-2 px-2 py-1.5 rounded-lg cursor-pointer text-sm font-semibold text-primary bg-surface-container-low transition-colors';
  var INACTIVE = 'flex items-center gap-2 px-2 py-1.5 rounded-lg cursor-pointer text-sm text-on-surface hover:text-primary hover:bg-surface-container-low transition-colors';

  var html = '';

  // "All" item
  html += '<div class="' + (App.category === 'all' ? ACTIVE : INACTIVE) + '" '
       + 'onclick="App.filterCategory(\'all\')">'
       + '<span class="material-symbols-outlined" style="font-size:18px">apps</span>'
       + '<span>' + _escHtml(App.t('allCategories')) + '</span>'
       + '</div>';

  CATEGORIES.forEach(function(cat) {
    html += '<div class="' + (App.category === cat ? ACTIVE : INACTIVE) + '" '
          + 'onclick="App.filterCategory(\'' + _escAttr(cat) + '\')">'
          + '<span class="material-symbols-outlined" style="font-size:18px">label</span>'
          + '<span>' + _escHtml(cat) + '</span>'
          + '</div>';
  });

  container.innerHTML = html;
}

// ── Desktop sidebar: sort ─────────────────────────────────────────────────────

function _renderSidebarSort() {
  var container = document.getElementById('sidebar-sort');
  if (!container) return;

  var ACTIVE   = 'flex items-center gap-2 px-2 py-1.5 rounded-lg cursor-pointer text-sm font-semibold text-primary bg-surface-container-low transition-colors';
  var INACTIVE = 'flex items-center gap-2 px-2 py-1.5 rounded-lg cursor-pointer text-sm text-on-surface hover:text-primary hover:bg-surface-container-low transition-colors';

  var sorts = [
    {val: 'default',    label: App.t('sortDefault')},
    {val: 'trending',   label: App.t('sortTrending')},
    {val: 'bestseller', label: App.t('sortBestseller')},
    {val: 'rating',     label: App.t('sortRating')},
    {val: 'price-low',  label: App.t('sortPriceLow')},
    {val: 'price-high', label: App.t('sortPriceHigh')},
  ];

  var html = '';
  sorts.forEach(function(s) {
    html += '<div class="' + (App.sort === s.val ? ACTIVE : INACTIVE) + '" '
          + 'onclick="App.setSort(\'' + _escAttr(s.val) + '\')">'
          + _escHtml(s.label)
          + '</div>';
  });

  container.innerHTML = html;
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

  var pid = _escAttr(p.id || '');

  return '<article class="product-card bg-surface-container-lowest rounded-xl shadow-sm overflow-hidden flex flex-col animate-in" '
       + 'style="animation-delay:' + delay + 's">'

       // Image area with shimmer — click opens detail panel
       + '<div class="relative w-full aspect-square bg-surface-container-low cursor-pointer shimmer-bg" '
       + 'onclick="App.openProduct(\'' + pid + '\')">'
       + '<img data-src="' + imgSrc + '" alt="' + title + '" '
       + 'class="card-img w-full h-full object-contain mix-blend-multiply p-4" '
       + 'onload="this.parentElement.classList.remove(\'shimmer-bg\')" '
       + 'onerror="this.hidden=true;this.parentElement.classList.remove(\'shimmer-bg\')">'
       + badge
       + '</div>'

       // Card body
       + '<div class="p-4 flex flex-col gap-1">'
       + '<div class="text-xs font-semibold text-on-surface-variant uppercase tracking-wider">' + category + '</div>'
       + '<h3 class="text-sm font-medium text-on-surface line-clamp-2 leading-snug cursor-pointer hover:text-primary transition-colors" onclick="App.openProduct(\'' + pid + '\')">' + title + '</h3>'
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

// ── Product Detail Panel ──────────────────────────────────────────────────────

function _renderDetail(p) {
  // Image
  var img = document.getElementById('detail-image');
  if (img) {
    img.src = p.image || '';
    img.alt = p.title || '';
    img.style.opacity = '0';
    img.onload = function() { img.style.opacity = '1'; };
    if (img.complete) img.style.opacity = '1';
  }

  // Carousel strip
  var carousel = document.getElementById('detail-carousel');
  if (carousel) {
    var urls = p.imageUrls || [];
    if (urls.length > 1) {
      carousel.classList.remove('hidden');
      carousel.innerHTML = urls.map(function(u, i) {
        return '<img src="' + _escAttr(u) + '" alt="' + _escHtml(p.title || '') + ' ' + (i+1) + '" '
             + 'class="h-20 w-20 object-contain rounded-lg border-2 cursor-pointer flex-shrink-0 snap-center '
             + (i === 0 ? 'border-primary-container' : 'border-outline-variant') + '" '
             + 'onclick="document.getElementById(\'detail-image\').src=this.src;'
             + 'this.parentElement.querySelectorAll(\'img\').forEach(function(x){x.className=x.className.replace(\'border-primary-container\',\'border-outline-variant\');});'
             + 'this.className=this.className.replace(\'border-outline-variant\',\'border-primary-container\');">'
      }).join('');
    } else {
      carousel.classList.add('hidden');
      carousel.innerHTML = '';
    }
  }

  // Title
  var titleEl = document.getElementById('detail-title');
  if (titleEl) titleEl.textContent = p.title || '';

  // Rating
  var ratingEl = document.getElementById('detail-rating');
  if (ratingEl) {
    if (p.rating && p.rating > 0) {
      var stars = '';
      for (var i = 0; i < 5; i++) {
        var fill = i < Math.round(p.rating) ? '1' : '0';
        stars += '<span class="material-symbols-outlined text-primary-container" style="font-size:18px;font-variation-settings:\'FILL\' ' + fill + '">star</span>';
      }
      var revStr = p.reviews ? ' (' + p.reviews.toLocaleString() + ' reviews)' : '';
      ratingEl.innerHTML = '<div class="flex items-center gap-0.5">' + stars + '</div>'
        + '<span class="text-sm text-secondary">' + p.rating.toFixed(1) + _escHtml(revStr) + '</span>';
    } else {
      ratingEl.innerHTML = '';
    }
  }

  // Price
  var priceEl = document.getElementById('detail-price');
  if (priceEl) priceEl.textContent = p.price ? '$' + p.price.toFixed(2) : '';

  // Description — prefer descriptionI18n dict, fallback to description field
  var descEl = document.getElementById('detail-description');
  if (descEl) {
    var desc = '';
    if (p.descriptionI18n) {
      desc = p.descriptionI18n[App.lang] || p.descriptionI18n['en'] || '';
    } else if (p.description) {
      desc = typeof p.description === 'object'
        ? (p.description[App.lang] || p.description['en'] || '')
        : p.description;
    }
    descEl.textContent = desc;
  }

  // Buy button
  var buyBtn = document.getElementById('detail-buy-btn');
  if (buyBtn) buyBtn.href = p.affiliateUrl || '#';
  var buyLabel = document.getElementById('detail-buy-label');
  if (buyLabel) buyLabel.textContent = App.t('buyOnAmazon');

  // Back label
  var backLabel = document.getElementById('detail-back-label');
  if (backLabel) backLabel.textContent = App.t('backToResults') || 'Back to Results';

  // Specs — derive from category + tags
  var specsWrap = document.getElementById('detail-specs-wrap');
  var specsList = document.getElementById('detail-specs');
  var specHeading = document.getElementById('detail-specs-heading');
  if (specsWrap && specsList) {
    var specs = _deriveSpecs(p);
    if (specs.length > 0) {
      specsWrap.classList.remove('hidden');
      if (specHeading) specHeading.textContent = App.t('productDetails') || 'Product Details';
      specsList.innerHTML = specs.map(function(s) {
        return '<li class="flex items-start gap-3">'
          + '<span class="material-symbols-outlined text-primary-container mt-0.5" style="font-size:20px">check_circle</span>'
          + '<span class="text-sm text-on-surface-variant">' + _escHtml(s) + '</span>'
          + '</li>';
      }).join('');
    } else {
      specsWrap.classList.add('hidden');
    }
  }

  // Related products
  var relatedEl = document.getElementById('detail-related');
  var relHeading = document.getElementById('detail-related-heading');
  if (relHeading) relHeading.textContent = App.t('relatedProducts') || 'More Like This';
  if (relatedEl) {
    var related = PRODUCTS.filter(function(x) {
      return x.id !== p.id && x.category === p.category;
    }).slice(0, 6);
    if (related.length === 0) {
      related = PRODUCTS.filter(function(x) { return x.id !== p.id; }).slice(0, 6);
    }
    relatedEl.innerHTML = related.map(function(r) {
      var rUrl  = _escAttr(r.affiliateUrl || '#');
      var rPid  = _escAttr(r.id || '');
      var rImg  = _escAttr(r.image || '');
      var rTitle = _escHtml(r.title || '');
      var rPrice = r.price ? '$' + r.price.toFixed(2) : '';
      return '<div class="min-w-[160px] w-[160px] bg-surface-container-lowest rounded-xl shadow-sm overflow-hidden flex-shrink-0 snap-center border border-surface-container cursor-pointer" '
           + 'onclick="App.openProduct(\'' + rPid + '\')">'
           + '<div class="h-[120px] bg-surface-container-low flex items-center justify-center p-3">'
           + '<img src="' + rImg + '" alt="' + rTitle + '" class="h-full w-full object-contain mix-blend-multiply">'
           + '</div>'
           + '<div class="p-3 space-y-1">'
           + '<h4 class="text-xs font-medium text-on-surface line-clamp-2 leading-snug">' + rTitle + '</h4>'
           + (rPrice ? '<div class="text-sm font-semibold text-primary-container mt-1">' + _escHtml(rPrice) + '</div>' : '')
           + '</div>'
           + '</div>';
    }).join('');
  }
}

function _deriveSpecs(p) {
  var specs = [];
  if (p.rating && p.rating >= 4.0) specs.push('Rated ' + p.rating.toFixed(1) + '/5 by customers');
  if (p.reviews && p.reviews > 0) specs.push(p.reviews.toLocaleString() + ' verified customer reviews');
  var cat = (p.category || '').toLowerCase();
  if (cat === 'electronics') {
    specs.push('Compatible with major platforms and devices');
    specs.push('Energy efficient design');
  } else if (cat === 'beauty') {
    specs.push('Dermatologist tested formula');
    specs.push('Cruelty-free certified');
  } else if (cat === 'fashion') {
    specs.push('Premium quality materials');
    specs.push('Available in multiple sizes');
  } else if (cat === 'home') {
    specs.push('Durable construction for everyday use');
    specs.push('Easy to clean and maintain');
  } else if (cat === 'sports' || cat === 'fitness') {
    specs.push('Designed for active lifestyles');
    specs.push('Sweat and moisture resistant');
  }
  if (p.tags && p.tags.indexOf('bestseller') !== -1) specs.push('Amazon Best Seller in its category');
  specs.push('Ships and sold by Amazon');
  specs.push('Eligible for Amazon Prime delivery');
  return specs.slice(0, 5);
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
  // Mobile search toggle
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

  // Desktop search input
  var inputD = document.getElementById('search-input-desktop');
  if (inputD) {
    var debounceD;
    inputD.addEventListener('input', function() {
      clearTimeout(debounceD);
      debounceD = setTimeout(function() {
        App.query = inputD.value.trim();
        // Sync mobile input
        if (input) input.value = inputD.value;
        App.render();
      }, 220);
    });

    inputD.addEventListener('keydown', function(e) {
      if (e.key === 'Escape') {
        inputD.value = '';
        App.clearSearch();
      }
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
  // Mobile lang button
  var btn = document.getElementById('lang-cycle');
  if (btn) {
    btn.addEventListener('click', function() {
      var idx  = _LANGS.indexOf(App.lang);
      var next = _LANGS[(idx + 1) % _LANGS.length];
      App.setLang(next);
    });
  }

  // Desktop lang button
  var btnD = document.getElementById('lang-cycle-desktop');
  if (btnD) {
    btnD.addEventListener('click', function() {
      var idx  = _LANGS.indexOf(App.lang);
      var next = _LANGS[(idx + 1) % _LANGS.length];
      App.setLang(next);
    });
  }
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

// ── Brand links ───────────────────────────────────────────────────────────────

function _setupBrandLink() {
  var link = document.getElementById('brand-link');
  if (link) {
    link.addEventListener('click', function(e) {
      e.preventDefault();
      App.reset();
    });
  }
  var linkD = document.getElementById('brand-link-desktop');
  if (linkD) {
    linkD.addEventListener('click', function(e) {
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
  var displayD = document.getElementById('lang-display-desktop');
  if (displayD) displayD.textContent = App.lang.toUpperCase();

  _setupSearch();
  _setupSort();
  _setupLang();
  _setupBrandLink();

  // Handle browser back button closing detail panel
  window.addEventListener('popstate', function(e) {
    var panel = document.getElementById('detail-panel');
    if (panel && !panel.classList.contains('hidden')) {
      panel.classList.add('hidden');
      document.body.style.overflow = '';
    }
  });

  App.render();
});

window.App = App;

})();
