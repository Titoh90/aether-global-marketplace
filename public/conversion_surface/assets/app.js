
(function(){
'use strict';

/* ═══════════════════════════════════════════════════════════════════════
   Aether Global Marketplace — Client App
   Features: i18n, search, category filters,
   IntersectionObserver lazy loading, trust labels
   ═══════════════════════════════════════════════════════════════════════ */

// ── Data ────────────────────────────────────────────────────────────────

var DATA = JSON.parse(document.getElementById('products-data').textContent);
var I18N = JSON.parse(document.getElementById('translations-data').textContent);
var PRODUCTS = DATA.products || [];
var CATEGORIES = DATA.categories || [];

// ── State ───────────────────────────────────────────────────────────────

var App = {
  lang: _detectLang(),
  category: 'all',
  query: '',
  sort: 'default',
  view: 'grid',

  t: function(key) {
    return (I18N[this.lang] && I18N[this.lang][key]) || (I18N['en'] && I18N['en'][key]) || key;
  },

  reset: function() {
    this.category = 'all';
    this.query = '';
    this.sort = 'default';
    var sortSel = document.getElementById('sort-select');
    if (sortSel) sortSel.value = 'default';
    document.getElementById('search-input').value = '';
    document.getElementById('search-clear').classList.remove('visible');
    this.render();
    window.scrollTo({top:0,behavior:'smooth'});
  },

  setLang: function(lang) {
    this.lang = lang;
    _saveLang(lang);
    _updateLangUI();
    this.render();
  },

  clearSearch: function() {
    this.query = '';
    document.getElementById('search-input').value = '';
    document.getElementById('search-clear').classList.remove('visible');
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

  setView: function(val) {
    this.view = val;
    // Toggle grid class and update view buttons
    var grid = document.getElementById('product-grid');
    if (grid) {
      grid.classList.toggle('list', val === 'list');
      grid.classList.toggle('grid', val === 'grid');
    }
    var btns = document.querySelectorAll('.view-btn');
    btns.forEach(function(b) {
      b.classList.toggle('active', b.getAttribute('data-view') === val);
    });
  },

  getFilteredProducts: function() {
    var self = this;
    return PRODUCTS.filter(function(p) {
      if (self.category !== 'all' && p.category !== self.category) return false;
      if (self.query) {
        var q = self.query.toLowerCase();
        var title = (p.title || '').toLowerCase();
        var desc = (p.description && p.description[self.lang]) || (p.description && p.description['en']) || '';
        desc = desc.toLowerCase();
        if (title.indexOf(q) === -1 && desc.indexOf(q) === -1 && p.category.toLowerCase().indexOf(q) === -1) return false;
      }
      return true;
    }).sort(function(a, b) {
      switch (self.sort) {
        case 'trending':
          var aTrend = (a.tags || []).indexOf('trending') !== -1 ? 1 : 0;
          var bTrend = (b.tags || []).indexOf('trending') !== -1 ? 1 : 0;
          if (aTrend !== bTrend) return bTrend - aTrend;
          return (b.rating || 0) - (a.rating || 0);
        case 'bestseller':
          var aBest = (a.tags || []).indexOf('bestseller') !== -1 ? 1 : 0;
          var bBest = (b.tags || []).indexOf('bestseller') !== -1 ? 1 : 0;
          if (aBest !== bBest) return bBest - aBest;
          return (b.rating || 0) - (a.rating || 0);
        case 'rating':
          return (b.rating || 0) - (a.rating || 0);
        case 'price-low':
          return (a.price || 0) - (b.price || 0);
        case 'price-high':
          return (b.price || 0) - (a.price || 0);
        default:
          return 0;
      }
    });
  },

  goToProduct: function(url) {
    if (url) window.open(url, '_blank', 'noopener,noreferrer');
  },

  render: function() {
    _renderCategories();
    _renderProducts();
    _updateSortUI();
  }
};

window.App = App;

// ── Language Detection ──────────────────────────────────────────────────

function _detectLang() {
  try {
    var stored = localStorage.getItem('aether_lang');
    if (stored && I18N[stored]) return stored;
    var nav = (navigator.language || 'en').split('-')[0];
    if (I18N[nav]) return nav;
  } catch(e) {}
  return 'en';
}

function _saveLang(lang) {
  try { localStorage.setItem('aether_lang', lang); } catch(e) {}
}

// ── UI Updates ──────────────────────────────────────────────────────────

function _updateLangUI() {
  var btns = document.querySelectorAll('.lang-btn');
  btns.forEach(function(b) {
    b.classList.toggle('active', b.getAttribute('data-lang') === App.lang);
  });
  // Update i18n text nodes
  var els = document.querySelectorAll('[data-i18n]');
  els.forEach(function(el) {
    var key = el.getAttribute('data-i18n');
    var translated = App.t(key);
    if (translated) el.textContent = translated;
  });
  // Update search placeholder
  var searchInput = document.getElementById('search-input');
  if (searchInput) searchInput.placeholder = App.t('searchPlaceholder');
  // Update sort dropdown option text
  _updateSortUI();
}

// ── Sort UI Update ─────────────────────────────────────────────────────

function _updateSortUI() {
  var sel = document.getElementById('sort-select');
  if (!sel) return;
  var label = document.querySelector('.sort-label');
  if (label) label.textContent = App.t('sortLabel');
  var keys = ['sortDefault','sortTrending','sortBestseller','sortRating','sortPriceLow','sortPriceHigh'];
  var vals = ['default','trending','bestseller','rating','price-low','price-high'];
  keys.forEach(function(k, i) {
    var opt = sel.querySelector('option[value="' + vals[i] + '"]');
    if (opt) opt.textContent = App.t(k);
  });
  sel.value = App.sort;
}

// ── Category Pills ──────────────────────────────────────────────────────

function _renderCategories() {
  var nav = document.getElementById('category-nav');
  if (!nav) return;
  var inner = nav.querySelector('.category-inner');
  var html = '<button class="cat-pill' + (App.category === 'all' ? ' active' : '') + '" data-category="all" onclick="App.filterCategory(\'all\')">' + App.t('allCategories') + '</button>';
  CATEGORIES.forEach(function(cat) {
    html += '<button class="cat-pill' + (App.category === cat ? ' active' : '') + '" data-category="' + _escAttr(cat) + '" onclick="App.filterCategory(\'' + _escAttr(cat) + '\')">' + _escHtml(cat) + '</button>';
  });
  inner.innerHTML = html;
}

// ── Product Rendering ───────────────────────────────────────────────────

function _renderProducts() {
  var grid = document.getElementById('product-grid');
  var countEl = document.getElementById('products-count');
  var noResults = document.getElementById('no-results');
  if (!grid) return;

  var filtered = App.getFilteredProducts();

  if (countEl) {
    countEl.textContent = filtered.length + ' ' + App.t('productsFound');
  }

  if (filtered.length === 0) {
    grid.innerHTML = '';
    if (noResults) noResults.style.display = 'block';
    return;
  }

  if (noResults) noResults.style.display = 'none';

  // Apply view class
  grid.className = 'product-grid' + (App.view === 'list' ? ' list' : '');

  var html = '';
  filtered.forEach(function(p) {
    html += _renderCard(p);
  });
  grid.innerHTML = html;

  // Setup carousels first (clones tracks), then lazy-load new images
  _setupCarousels();
  _setupLazyImages();

}

function _renderCard(p) {
  var ptype = p.type || 'product';
  if (ptype === 'video') return _renderVideoCard(p);
  if (ptype === 'carousel') return _renderCarouselCard(p);
  return _renderProductCard(p);
}

function _renderProductCard(p) {
  var url = _escAttr(p.affiliateUrl || '');
  var title = _escHtml(p.title || '');
  var price = p.price ? '$' + p.price.toFixed(2) : '';
  var desc = _escHtml((p.description && p.description[App.lang]) || (p.description && p.description['en']) || p.category);
  var imgSrc = _escAttr(p.image || '');
  var rating = p.rating || 0;
  var reviews = p.reviews || 0;

  var labels = _buildLabels(p);
  var ratingHtml = _buildRating(rating, reviews);

  return '<div class="product-card" data-url="' + url + '">' +
    '<div class="card-img-wrap">' +
      '<img data-src="' + imgSrc + '" alt="' + title + '" class="card-img" loading="lazy" onerror="this.hidden=true">' +
      '<span class="card-img-placeholder">◆</span>' +
      (price ? '<span class="price-badge">' + _escHtml(price) + '</span>' : '') +
      labels +
    '</div>' +
    '<div class="card-body">' +
      '<h3 class="product-name">' + title + '</h3>' +
      '<p class="product-desc">' + _escHtml(desc) + '</p>' +
      ratingHtml +
      '<button class="cta-btn" data-url="' + url + '">' + App.t('buyOnAmazon') + '</button>' +
    '</div>' +
  '</div>';
}

function _renderVideoCard(p) {
  var url = _escAttr(p.affiliateUrl || '');
  var title = _escHtml(p.title || '');
  var price = p.price ? '$' + p.price.toFixed(2) : '';
  var desc = _escHtml((p.description && p.description[App.lang]) || (p.description && p.description['en']) || p.category);
  var imgSrc = _escAttr(p.image || '');
  var rating = p.rating || 0;
  var reviews = p.reviews || 0;

  var labels = _buildLabels(p);
  var ratingHtml = _buildRating(rating, reviews);

  return '<div class="product-card video-card" data-url="' + url + '">' +
    '<div class="card-img-wrap">' +
      '<img data-src="' + imgSrc + '" alt="' + title + '" class="card-img" loading="lazy" onerror="this.hidden=true">' +
      '<span class="card-img-placeholder">◆</span>' +
      '<div class="video-overlay" data-images="' + _escAttr(JSON.stringify(p.imageUrls || [p.image])) + '">' +
        '<span class="play-icon">▶</span>' +
        '<span class="video-label">' + App.t('watchVideo') + '</span>' +
      '</div>' +
      (price ? '<span class="price-badge">' + _escHtml(price) + '</span>' : '') +
      labels +
    '</div>' +
    '<div class="card-body">' +
      '<h3 class="product-name">' + title + '</h3>' +
      '<p class="product-desc">' + _escHtml(desc) + '</p>' +
      ratingHtml +
      '<button class="cta-btn" data-url="' + url + '">' + App.t('buyOnAmazon') + '</button>' +
    '</div>' +
  '</div>';
}

function _renderCarouselCard(p) {
  var url = _escAttr(p.affiliateUrl || '');
  var title = _escHtml(p.title || '');
  var price = p.price ? '$' + p.price.toFixed(2) : '';
  var desc = _escHtml((p.description && p.description[App.lang]) || (p.description && p.description['en']) || p.category);
  var imgSrc = _escAttr(p.image || '');
  var rating = p.rating || 0;
  var reviews = p.reviews || 0;

  var labels = _buildLabels(p);
  var ratingHtml = _buildRating(rating, reviews);

  // Build carousel slides from product images (imageUrls is an optional array)
  var slides = p.imageUrls && p.imageUrls.length ? p.imageUrls : [p.image];
  var dotsHtml = '';
  var slidesHtml = '';
  slides.forEach(function(src, i) {
    var s = _escAttr(src || '');
    var activeClass = i === 0 ? ' active' : '';
    dotsHtml += '<span class="carousel-dot' + activeClass + '" data-index="' + i + '"></span>';
    slidesHtml += '<div class="carousel-slide"><img data-src="' + s + '" alt="' + title + '" class="card-img" loading="lazy" onerror="this.hidden=true"><span class="card-img-placeholder">◆</span></div>';
  });

  return '<div class="product-card" data-url="' + url + '">' +
    '<div class="card-img-wrap">' +
      '<div class="carousel-track" data-carousel>' +
        slidesHtml +
      '</div>' +
      (slides.length > 1 ? '<div class="carousel-dots">' + dotsHtml + '</div>' : '') +
      (price ? '<span class="price-badge">' + _escHtml(price) + '</span>' : '') +
      labels +
    '</div>' +
    '<div class="card-body">' +
      '<h3 class="product-name">' + title + '</h3>' +
      '<p class="product-desc">' + _escHtml(desc) + '</p>' +
      ratingHtml +
      '<button class="cta-btn" data-url="' + url + '">' + App.t('buyOnAmazon') + '</button>' +
    '</div>' +
  '</div>';
}

function _buildLabels(p) {
  var labels = '';
  var tags = p.tags || [];
  tags.forEach(function(tag) {
    var labelKey = tag === 'bestseller' ? 'bestseller' : tag === 'trending' ? 'trendingLabel' : tag === 'limited' ? 'limitedOffer' : '';
    var labelText = labelKey ? App.t(labelKey) : tag;
    labels += '<span class="trust-label ' + tag + '">' + labelText + '</span>';
  });
  return labels;
}

function _buildRating(rating, reviews) {
  if (!rating || rating <= 0) return '';
  var pct = (rating / 5.0) * 100;
  var rv = rating.toFixed(1);
  var rc = reviews > 0 ? '<span class="review-count">(' + reviews.toLocaleString() + ')</span>' : '';
  return '<div class="rating-row"><span class="stars" style="--pct:' + pct.toFixed(0) + '%"></span><span class="rating-value">' + rv + '</span>' + rc + '</div>';
}

// ── Lazy Loading ────────────────────────────────────────────────────────

var _observer = null;

function _setupLazyImages() {
  if (_observer) _observer.disconnect();

  if ('IntersectionObserver' in window) {
    _observer = new IntersectionObserver(function(entries) {
      entries.forEach(function(entry) {
        if (entry.isIntersecting) {
          var img = entry.target;
          var src = img.getAttribute('data-src');
          if (src && !img.src) {
            img.src = src;
          }
          img.classList.add('loaded');
          _observer.unobserve(img);
        }
      });
    }, { rootMargin: '200px' });

    document.querySelectorAll('.card-img').forEach(function(img) {
      _observer.observe(img);
    });
  } else {
    // Fallback: load all immediately
    document.querySelectorAll('.card-img').forEach(function(img) {
      var src = img.getAttribute('data-src');
      if (src && !img.src) img.src = src;
      img.classList.add('loaded');
    });
  }
}

// ── Card Click Delegation ───────────────────────────────────────────────

function _setupCardClickDelegation() {
  var grid = document.getElementById('product-grid');
  if (!grid) return;
  grid.addEventListener('click', function(e) {
    // Intercept clicks on video overlay — open preview modal
    var overlay = e.target.closest('.video-overlay');
    if (overlay) {
      e.preventDefault();
      e.stopPropagation();
      var imagesJson = overlay.getAttribute('data-images');
      if (imagesJson) {
        try {
          var images = JSON.parse(imagesJson);
          var card = overlay.closest('.product-card');
          var url = card ? card.getAttribute('data-url') : '';
          _showVideoPreview(images, url);
        } catch(err) {}
      }
      return;
    }
    // Don't intercept carousel CTA buttons — they have their own data-url
    var cta = e.target.closest('.cta-btn');
    if (cta) {
      var ctaUrl = cta.getAttribute('data-url');
      if (ctaUrl) window.open(ctaUrl, '_blank', 'noopener,noreferrer');
      return;
    }
    // Normal card click
    var card = e.target.closest('.product-card');
    if (!card) return;
    var url = card.getAttribute('data-url');
    if (url) window.open(url, '_blank', 'noopener,noreferrer');
  });
}

// ── Carousel Scroll Tracking ────────────────────────────────────────────

function _setupCarousels() {
  var tracks = document.querySelectorAll('[data-carousel]');
  tracks.forEach(function(track) {
    // Remove old listener by cloning
    var clone = track.cloneNode(true);
    track.parentNode.replaceChild(clone, track);

    clone.addEventListener('scroll', function() {
      var dots = clone.parentNode.querySelectorAll('.carousel-dot');
      if (!dots.length) return;
      var index = Math.round(clone.scrollLeft / clone.clientWidth);
      dots.forEach(function(d, i) {
        d.classList.toggle('active', i === index);
      });
    }, {passive: true});
  });
}

// ── Video Preview Modal ────────────────────────────────────────────────

var _videoTimer = null;
var _videoSlideIndex = 0;
var _videoImages = [];
var _videoUrl = '';

function _showVideoPreview(images, url) {
  _videoImages = images || [];
  _videoUrl = url || '';
  _videoSlideIndex = 0;
  _buildVideoModal();
  _startVideoTimer();
  document.body.classList.add('modal-open');
  // Focus trap
  setTimeout(function() {
    var closeBtn = document.querySelector('.video-modal-close');
    if (closeBtn) closeBtn.focus();
  }, 100);
}

function _closeVideoPreview() {
  _stopVideoTimer();
  document.body.classList.remove('modal-open');
  var modal = document.getElementById('video-modal');
  if (modal) modal.remove();
  _videoImages = [];
  _videoUrl = '';
}

function _buildVideoModal() {
  // Remove any existing modal DOM (don't reset globals)
  var existing = document.getElementById('video-modal');
  if (existing) existing.remove();

  var slidesHtml = '';
  var dotsHtml = '';
  _videoImages.forEach(function(src, i) {
    var s = _escAttr(src || '');
    var activeClass = i === 0 ? ' active' : '';
    slidesHtml += '<div class="video-slide' + activeClass + '"><img data-src="' + s + '" alt="Product preview ' + (i + 1) + '" class="video-modal-img" loading="eager"></div>';
    dotsHtml += '<span class="video-dot' + activeClass + '" data-index="' + i + '"></span>';
  });

  var closeLabel = _escHtml(App.t('closePreview'));
  var ctaLabel = _escHtml(App.t('watchOnAmazon'));
  var hasMultiple = _videoImages.length > 1;

  var modal = document.createElement('div');
  modal.id = 'video-modal';
  modal.className = 'video-modal';
  modal.innerHTML =
    '<div class="video-modal-backdrop"></div>' +
    '<div class="video-modal-content">' +
      '<button class="video-modal-close" aria-label="' + closeLabel + '">&times;</button>' +
      '<div class="video-slides">' + slidesHtml + '</div>' +
      (hasMultiple ? '<div class="video-dots">' + dotsHtml + '</div>' : '') +
      '<div class="video-info-bar">' +
        '<div class="video-nav-arrows">' +
          (hasMultiple ? '<button class="video-arrow video-arrow-prev">‹</button>' : '') +
          (hasMultiple ? '<button class="video-arrow video-arrow-next">›</button>' : '') +
        '</div>' +
        (_videoUrl ? '<a href="' + _escAttr(_videoUrl) + '" target="_blank" rel="noopener noreferrer" class="video-cta-btn">' + ctaLabel + ' →</a>' : '') +
      '</div>' +
    '</div>';
  document.body.appendChild(modal);

  // Attach event listeners (not inline onclick — these are IIFE-scoped)
  var backdrop = modal.querySelector('.video-modal-backdrop');
  if (backdrop) backdrop.addEventListener('click', _closeVideoPreview);

  var closeBtn = modal.querySelector('.video-modal-close');
  if (closeBtn) closeBtn.addEventListener('click', _closeVideoPreview);

  var content = modal.querySelector('.video-modal-content');
  if (content) {
    content.addEventListener('mouseenter', _pauseVideoTimer);
    content.addEventListener('mouseleave', _startVideoTimer);
  }

  var prevBtn = modal.querySelector('.video-arrow-prev');
  if (prevBtn) prevBtn.addEventListener('click', function(e) {
    e.stopPropagation();
    _videoPrevSlide();
  });

  var nextBtn = modal.querySelector('.video-arrow-next');
  if (nextBtn) nextBtn.addEventListener('click', function(e) {
    e.stopPropagation();
    _videoNextSlide();
  });

  // Load visible image immediately
  var activeSlide = modal.querySelector('.video-slide.active');
  if (activeSlide) {
    var img = activeSlide.querySelector('.video-modal-img');
    if (img) {
      var src = img.getAttribute('data-src');
      if (src) img.src = src;
    }
  }
}

function _startVideoTimer() {
  _stopVideoTimer();
  if (_videoImages.length <= 1) return;
  _videoTimer = setInterval(_videoNextSlide, 3500);
}

function _pauseVideoTimer() {
  _stopVideoTimer();
}

function _stopVideoTimer() {
  if (_videoTimer) { clearInterval(_videoTimer); _videoTimer = null; }
}

function _videoPrevSlide() {
  _videoSlideIndex = (_videoSlideIndex - 1 + _videoImages.length) % _videoImages.length;
  _updateVideoSlide();
  _startVideoTimer(); // restart timer on manual nav
}

function _videoNextSlide() {
  _videoSlideIndex = (_videoSlideIndex + 1) % _videoImages.length;
  _updateVideoSlide();
}

function _updateVideoSlide() {
  var slides = document.querySelectorAll('.video-slide');
  var dots = document.querySelectorAll('.video-dot');
  slides.forEach(function(s, i) {
    s.classList.toggle('active', i === _videoSlideIndex);
  });
  dots.forEach(function(d, i) {
    d.classList.toggle('active', i === _videoSlideIndex);
  });
  // Load the active image if not yet loaded
  var activeSlide = document.querySelector('.video-slide.active');
  if (activeSlide) {
    var img = activeSlide.querySelector('.video-modal-img');
    if (img) {
      var src = img.getAttribute('data-src');
      if (src && !img.src) img.src = src;
    }
  }
}

function _setupVideoKeyboard() {
  document.addEventListener('keydown', function(e) {
    var modal = document.getElementById('video-modal');
    if (!modal) return;
    if (e.key === 'Escape') {
      _closeVideoPreview();
    } else if (e.key === 'ArrowLeft') {
      _videoPrevSlide();
    } else if (e.key === 'ArrowRight') {
      _videoNextSlide();
    }
  });
  // Touch swipe support
  var touchStartX = 0;
  document.addEventListener('touchstart', function(e) {
    var modal = document.getElementById('video-modal');
    if (!modal) return;
    touchStartX = e.touches[0].clientX;
  }, {passive: true});
  document.addEventListener('touchend', function(e) {
    var modal = document.getElementById('video-modal');
    if (!modal) return;
    var diff = e.changedTouches[0].clientX - touchStartX;
    if (Math.abs(diff) > 60) {
      if (diff < 0) _videoNextSlide();
      else _videoPrevSlide();
    }
  });
}

function _setupSearch() {
  var input = document.getElementById('search-input');
  var clear = document.getElementById('search-clear');
  if (!input) return;

  var debounceTimer;
  input.addEventListener('input', function() {
    clear.classList.toggle('visible', input.value.length > 0);
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(function() {
      App.query = input.value.trim();
      App.render();
    }, 200);
  });

  input.addEventListener('keydown', function(e) {
    if (e.key === 'Escape') {
      input.value = '';
      App.clearSearch();
    }
  });
}

// ── Utilities ───────────────────────────────────────────────────────────

function _escHtml(s) {
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

function _escAttr(s) {
  return String(s).replace(/&/g,'&amp;').replace(/"/g,'&quot;').replace(/'/g,'&#39;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

// ── Init ────────────────────────────────────────────────────────────────

_updateLangUI();
_setupSearch();
_setupCardClickDelegation();
_setupVideoKeyboard();
App.render();
_setupCarousels();

})();
