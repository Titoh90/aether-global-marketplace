"""
template_renderer.py — AffilioLux premium affiliate marketplace renderer.

Design: Tailwind CDN + Material Symbols + Inter font.
Responsive: Mobile-first bottom nav + Desktop top nav with sidebar + 3-col grid.
Output: self-contained index.html with embedded products JSON.
"""
from __future__ import annotations

import html as _html
import json
from .schemas import HubSurface, SurfaceProduct
from .descriptions import product_description


# ── Tailwind color config ─────────────────────────────────────────────────────

_TW_COLORS: dict = {
    "primary":                   "#755b00",
    "primary-container":         "#c9a84c",
    "primary-fixed":             "#ffe08f",
    "primary-fixed-dim":         "#e6c364",
    "on-primary":                "#ffffff",
    "on-primary-container":      "#503d00",
    "on-primary-fixed":          "#241a00",
    "on-primary-fixed-variant":  "#584400",
    "secondary":                 "#5f5e5e",
    "secondary-container":       "#e2dfde",
    "secondary-fixed":           "#e5e2e1",
    "secondary-fixed-dim":       "#c8c6c5",
    "on-secondary":              "#ffffff",
    "on-secondary-container":    "#636262",
    "on-secondary-fixed":        "#1c1b1b",
    "on-secondary-fixed-variant":"#474746",
    "tertiary":                  "#765b00",
    "tertiary-container":        "#cda740",
    "tertiary-fixed":            "#ffdf93",
    "tertiary-fixed-dim":        "#eac258",
    "on-tertiary":               "#ffffff",
    "on-tertiary-container":     "#503d00",
    "on-tertiary-fixed":         "#241a00",
    "on-tertiary-fixed-variant": "#594400",
    "error":                     "#ba1a1a",
    "error-container":           "#ffdad6",
    "on-error":                  "#ffffff",
    "on-error-container":        "#93000a",
    "background":                "#f9f9f9",
    "on-background":             "#1a1c1c",
    "surface":                   "#f9f9f9",
    "surface-dim":               "#dadada",
    "surface-bright":            "#f9f9f9",
    "surface-container-lowest":  "#ffffff",
    "surface-container-low":     "#f3f3f3",
    "surface-container":         "#eeeeee",
    "surface-container-high":    "#e8e8e8",
    "surface-container-highest": "#e2e2e2",
    "surface-variant":           "#e2e2e2",
    "surface-tint":              "#755b00",
    "on-surface":                "#1a1c1c",
    "on-surface-variant":        "#4d4637",
    "outline":                   "#7e7665",
    "outline-variant":           "#d0c5b2",
    "inverse-surface":           "#2f3131",
    "inverse-on-surface":        "#f0f1f1",
    "inverse-primary":           "#e6c364",
}

_TW_CONFIG: str = json.dumps({
    "darkMode": "class",
    "theme": {
        "extend": {
            "colors": _TW_COLORS,
        }
    }
}, separators=(",", ":"))


# ═══════════════════════════════════════════════════════════════════════════════
# Public API
# ═══════════════════════════════════════════════════════════════════════════════

def render_html(surface: HubSurface) -> str:
    """Render the complete AffilioLux SPA with embedded product data."""
    products_json  = _build_products_json(surface)
    translations_json = json.dumps(_TRANSLATIONS, ensure_ascii=False)
    updated = _e(surface.generated_at[:16].replace("T", " "))

    return (
        _SHELL_HEAD
        + _SHELL_BODY.replace("__PRODUCTS__", products_json)
                     .replace("__TRANSLATIONS__", translations_json)
                     .replace("__UPDATED__", updated)
    )


def render_css() -> str:
    """Minimal CSS — Tailwind CDN handles layout, this adds animations/overrides."""
    return _CSS


def render_js() -> str:
    """AffilioLux client app — filtering, sorting, lazy loading."""
    return _JS


# ═══════════════════════════════════════════════════════════════════════════════
# Image helpers — Amazon CDN (no domain registration required)
# ═══════════════════════════════════════════════════════════════════════════════

def _amazon_image_url(asin: str, size: str = "SL400") -> str:
    if not asin:
        return ""
    return f"https://m.media-amazon.com/images/P/{asin}.01._{size}_.jpg"


def _build_carousel_image_urls(asin: str, primary_url: str) -> list:
    """Up to 3 Amazon CDN image variants (.01 / .02 / .03)."""
    if not asin:
        return [primary_url] if primary_url else []
    return [
        f"https://m.media-amazon.com/images/P/{asin}.01._SL400_.jpg",
        f"https://m.media-amazon.com/images/P/{asin}.02._SL400_.jpg",
        f"https://m.media-amazon.com/images/P/{asin}.03._SL400_.jpg",
    ]


# ═══════════════════════════════════════════════════════════════════════════════
# Data helpers
# ═══════════════════════════════════════════════════════════════════════════════

def _e(s: str) -> str:
    return _html.escape(str(s))


def _build_products_json(surface: HubSurface) -> str:
    all_products = [surface.hero]
    all_products.extend(surface.trending)
    all_products.extend(surface.evergreen)
    for prods in surface.by_category.values():
        all_products.extend(prods)
    all_products.extend(surface.recent)

    seen:       set[str] = set()
    categories: set[str] = set()
    products_out = []

    for p in all_products:
        if p.asin in seen:
            continue
        seen.add(p.asin)
        categories.add(p.category)

        desc_en = (
            p.archetype_label
            or (p.creative_mode.replace("_", " ").title() if p.creative_mode else p.category)
        )
        tags = []
        if p.section == "hero":
            tags.append("bestseller")
        if p.section == "trending":
            tags.append("trending")
        if p.evergreen_status == "experimental":
            tags.append("limited")

        img_src = p.image_url or _amazon_image_url(p.asin)

        products_out.append({
            "id":          p.asin,
            "title":       p.name,
            "price":       p.price,
            "image":       img_src,
            "imageUrls":   _build_carousel_image_urls(p.asin, img_src),
            "rating":      p.rating,
            "reviews":     p.reviews,
            "category":    p.category,
            "affiliateUrl": p.tracking_url or p.affiliate_url,
            "description": product_description(desc_en, p.category),
            "tags":        tags,
            "section":     p.section,
        })

    return json.dumps({
        "generated_at": surface.generated_at,
        "categories":   sorted(categories),
        "products":     products_out,
    }, ensure_ascii=False)


# ═══════════════════════════════════════════════════════════════════════════════
# i18n
# ═══════════════════════════════════════════════════════════════════════════════

_TRANSLATIONS = {
    "en": {
        "siteTagline":    "Premium Deals",
        "pageTitle":      "Curated Premium Deals",
        "pageSubtitle":   "Hand-picked products. Updated daily.",
        "allCategories":  "All",
        "buyOnAmazon":    "View Deal",
        "bestseller":     "Top Pick",
        "limitedOffer":   "Limited",
        "trendingLabel":  "Trending",
        "footerDisclaimer": "As an Amazon Associate we earn from qualifying purchases.",
        "updated":        "Updated",
        "noResults":      "No products found",
        "productsFound":  "products",
        "sortLabel":      "Sort",
        "sortDefault":    "Featured",
        "sortTrending":   "Trending",
        "sortBestseller": "Best Sellers",
        "sortPriceLow":   "Price \u2191",
        "sortPriceHigh":  "Price \u2193",
        "sortRating":     "Top Rated",
        "navShop":        "Shop",
        "navTrends":      "Trends",
        "navSaved":       "Saved",
        "navAccount":     "Account",
        "navShopAll":     "Shop All",
        "navTrending":    "Trending",
        "navDailyDeals":  "Daily Deals",
        "herobadge":      "CURATED EXCELLENCE",
        "category":       "Category",
        "sortBy":         "Sort By",
    },
    "es": {
        "siteTagline":    "Ofertas Premium",
        "pageTitle":      "Ofertas Premium Seleccionadas",
        "pageSubtitle":   "Productos seleccionados. Actualizados diariamente.",
        "allCategories":  "Todos",
        "buyOnAmazon":    "Ver Oferta",
        "bestseller":     "Top Pick",
        "limitedOffer":   "Limitado",
        "trendingLabel":  "Tendencia",
        "footerDisclaimer": "Como Asociado de Amazon, ganamos comisiones por compras que califican.",
        "updated":        "Actualizado",
        "noResults":      "No se encontraron productos",
        "productsFound":  "productos",
        "sortLabel":      "Ordenar",
        "sortDefault":    "Destacados",
        "sortTrending":   "Tendencias",
        "sortBestseller": "M\u00e1s Vendidos",
        "sortPriceLow":   "Precio \u2191",
        "sortPriceHigh":  "Precio \u2193",
        "sortRating":     "Mejor Valorados",
        "navShop":        "Tienda",
        "navTrends":      "Tendencias",
        "navSaved":       "Guardados",
        "navAccount":     "Cuenta",
        "navShopAll":     "Ver Todo",
        "navTrending":    "Tendencias",
        "navDailyDeals":  "Ofertas del D\u00eda",
        "herobage":       "EXCELENCIA CURADA",
        "herobage":       "EXCELENCIA CURADA",
        "herobage":       "EXCELENCIA CURADA",
        "herobage":       "EXCELENCIA CURADA",
        "herobage":       "EXCELENCIA CURADA",
        "herobage":       "EXCELENCIA CURADA",
        "herobage":       "EXCELENCIA CURADA",
        "herobage":       "EXCELENCIA CURADA",
        "herobage":       "EXCELENCIA CURADA",
        "herobage":       "EXCELENCIA CURADA",
        "herobage":       "EXCELENCIA CURADA",
        "herobage":       "EXCELENCIA CURADA",
        "herobadge":      "EXCELENCIA CURADA",
        "category":       "Categor\u00eda",
        "sortBy":         "Ordenar Por",
    },
    "fr": {
        "siteTagline":    "Offres Premium",
        "pageTitle":      "S\u00e9lections Premium",
        "pageSubtitle":   "Produits s\u00e9lectionn\u00e9s. Mis \u00e0 jour quotidiennement.",
        "allCategories":  "Tout",
        "buyOnAmazon":    "Voir l'offre",
        "bestseller":     "Top Pick",
        "limitedOffer":   "Limit\u00e9",
        "trendingLabel":  "Tendance",
        "footerDisclaimer": "En tant qu'Associ\u00e9 Amazon, nous gagnons des commissions sur les achats \u00e9ligibles.",
        "updated":        "Mis \u00e0 jour",
        "noResults":      "Aucun produit trouv\u00e9",
        "productsFound":  "produits",
        "sortLabel":      "Trier",
        "sortDefault":    "Vedette",
        "sortTrending":   "Tendance",
        "sortBestseller": "Meilleures ventes",
        "sortPriceLow":   "Prix \u2191",
        "sortPriceHigh":  "Prix \u2193",
        "sortRating":     "Mieux not\u00e9s",
        "navShop":        "Boutique",
        "navTrends":      "Tendances",
        "navSaved":       "Sauvegard\u00e9s",
        "navAccount":     "Compte",
        "navShopAll":     "Tout voir",
        "navTrending":    "Tendances",
        "navDailyDeals":  "Offres du jour",
        "herobage":       "EXCELLENCE CURATED",
        "herobage":       "EXCELLENCE CURATED",
        "herobage":       "EXCELLENCE CURATED",
        "herobage":       "EXCELLENCE CURATED",
        "herobage":       "EXCELLENCE CURATED",
        "herobage":       "EXCELLENCE CURATED",
        "herobage":       "EXCELLENCE CURATED",
        "herobage":       "EXCELLENCE CURATED",
        "herobage":       "EXCELLENCE CURATED",
        "herobage":       "EXCELLENCE CURATED",
        "herobage":       "EXCELLENCE CURATED",
        "herobage":       "EXCELLENCE CURATED",
        "herobage":       "EXCELLENCE CURATED",
        "herobage":       "EXCELLENCE CURATED",
        "herobage":       "EXCELLENCE CURATED",
        "herobage":       "EXCELLENCE CURATED",
        "herobadge":      "EXCELLENCE CURATED",
        "category":       "Cat\u00e9gorie",
        "sortBy":         "Trier Par",
    },
}


# ═══════════════════════════════════════════════════════════════════════════════
# HTML Shell
# ═══════════════════════════════════════════════════════════════════════════════

_SHELL_HEAD = f"""<!DOCTYPE html>
<html class="light" lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Aether Global — Premium Deals</title>
  <meta name="description" content="Curated premium Amazon products with affiliate deals. Updated daily.">
  <link rel="preconnect" href="https://m.media-amazon.com" crossorigin>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
  <link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:wght,FILL@100..700,0..1&display=swap" rel="stylesheet">
  <script src="https://cdn.tailwindcss.com"></script>
  <script>tailwind.config = {_TW_CONFIG}</script>
  <link rel="stylesheet" href="assets/styles.css">
</head>"""

_SHELL_BODY = """
<body class="bg-background text-on-surface min-h-screen" style="font-family:'Inter',sans-serif">

  <!-- ══ DESKTOP TOP NAV (hidden on mobile) ══════════════════════════════ -->
  <header class="hidden md:flex sticky top-0 z-50 bg-surface-container-lowest shadow-sm">
    <div class="flex justify-between items-center w-full max-w-[1440px] mx-auto px-16 py-3 gap-6">

      <!-- Brand -->
      <a href="#" id="brand-link-desktop"
         class="text-xl font-bold text-primary select-none whitespace-nowrap shrink-0">
        Aether Global
      </a>

      <!-- Search -->
      <div class="flex-1 max-w-xl relative">
        <span class="material-symbols-outlined absolute left-3 top-1/2 -translate-y-1/2 text-on-surface-variant pointer-events-none" style="font-size:18px">search</span>
        <input id="search-input-desktop" type="search" autocomplete="off"
               class="w-full bg-surface-container rounded-full border border-outline-variant pl-10 pr-4 py-2 text-sm text-on-surface placeholder:text-on-surface-variant outline-none focus:border-primary transition-colors"
               placeholder="Search products...">
      </div>

      <!-- Desktop nav links (lg+) -->
      <nav class="hidden lg:flex items-center gap-1 shrink-0">
        <button onclick="App.navShop()"
                class="px-3 py-1.5 text-sm text-on-surface hover:text-primary hover:bg-surface-container-low rounded-lg transition-colors">
          <span id="desktop-nav-shop-label">Shop All</span>
        </button>
        <button onclick="App.navTrends()"
                class="px-3 py-1.5 text-sm text-on-surface hover:text-primary hover:bg-surface-container-low rounded-lg transition-colors">
          <span id="desktop-nav-trends-label">Trending</span>
        </button>
        <button onclick="App.navShop()"
                class="px-3 py-1.5 text-sm text-on-surface hover:text-primary hover:bg-surface-container-low rounded-lg transition-colors">
          <span id="desktop-nav-deals-label">Daily Deals</span>
        </button>
      </nav>

      <!-- Right icons -->
      <div class="flex items-center gap-2 shrink-0">
        <button id="lang-cycle-desktop" aria-label="Language"
                class="flex items-center gap-1 px-2 py-1.5 rounded-lg text-on-surface-variant hover:bg-surface-container-low transition-colors">
          <span class="material-symbols-outlined" style="font-size:18px">language</span>
          <span id="lang-display-desktop" class="text-xs font-semibold">EN</span>
        </button>
      </div>

    </div>
  </header>

  <!-- ══ MOBILE TOP APP BAR (hidden on desktop) ══════════════════════════ -->
  <header id="top-bar" class="md:hidden fixed top-0 w-full z-50 bg-surface shadow-sm">
    <div class="flex justify-between items-center px-5 h-16">
      <button id="search-toggle" aria-label="Search"
              class="p-2 rounded-full text-on-surface-variant hover:bg-surface-container-low transition-colors active:scale-95">
        <span class="material-symbols-outlined">search</span>
      </button>
      <a href="#" id="brand-link" class="text-xl font-bold text-primary select-none">
        Aether Global
      </a>
      <button id="lang-cycle" aria-label="Language"
              class="p-2 rounded-full text-on-surface-variant hover:bg-surface-container-low transition-colors active:scale-95 flex items-center gap-0.5">
        <span class="material-symbols-outlined">language</span>
        <span id="lang-display" class="text-xs font-semibold">EN</span>
      </button>
    </div>
    <!-- Mobile search bar (collapsible) -->
    <div id="search-bar" class="hidden px-5 pb-3">
      <div class="flex items-center bg-surface-container rounded-full px-4 py-2 gap-2">
        <span class="material-symbols-outlined text-on-surface-variant" style="font-size:18px">search</span>
        <input id="search-input" type="search" autocomplete="off"
               class="flex-1 bg-transparent outline-none text-sm text-on-surface placeholder:text-on-surface-variant"
               placeholder="Search products...">
        <button id="search-clear" aria-label="Clear search"
                class="hidden text-on-surface-variant hover:text-on-surface transition-colors">
          <span class="material-symbols-outlined" style="font-size:18px">close</span>
        </button>
      </div>
    </div>
  </header>

  <!-- ══ MAIN ════════════════════════════════════════════════════════════ -->
  <main class="md:max-w-[1440px] md:mx-auto md:px-16 px-5 pb-24 md:pb-10">

    <!-- DESKTOP HERO (md+) -->
    <section class="hidden md:block my-8">
      <div class="bg-gradient-to-r from-surface-container via-surface to-surface-container rounded-xl p-10 relative overflow-hidden">
        <!-- Decorative circles -->
        <div class="absolute -top-12 right-8 w-48 h-48 bg-primary-container opacity-20 blur-3xl rounded-full pointer-events-none"></div>
        <div class="absolute top-4 right-32 w-32 h-32 bg-primary-container opacity-15 blur-2xl rounded-full pointer-events-none"></div>
        <!-- Content -->
        <div class="relative z-10 max-w-xl">
          <div class="inline-flex items-center gap-2 bg-primary-container bg-opacity-20 border border-primary-container text-primary rounded-full px-3 py-1 text-xs font-semibold uppercase tracking-widest mb-4">
            <span class="material-symbols-outlined" style="font-size:14px;font-variation-settings:'FILL' 1">auto_awesome</span>
            <span id="hero-badge">CURATED EXCELLENCE</span>
          </div>
          <h1 id="page-title-desktop" class="text-3xl font-bold text-on-surface mb-2 leading-tight">Curated Premium Deals</h1>
          <p id="page-subtitle-desktop" class="text-base text-on-surface-variant leading-relaxed">Hand-picked products. Updated daily.</p>
        </div>
      </div>
    </section>

    <!-- MOBILE PAGE HEADER -->
    <div class="md:hidden py-6 pt-20 animate-in">
      <h2 id="page-title" class="text-xl font-semibold text-on-surface">Curated Premium Deals</h2>
      <p id="page-subtitle" class="text-sm text-on-surface-variant mt-1">Hand-picked products. Updated daily.</p>
    </div>

    <!-- CONTENT FLEX ROW: sidebar + product area -->
    <div class="flex gap-8 md:mt-2">

      <!-- SIDEBAR (lg+) -->
      <aside class="hidden lg:block w-64 flex-shrink-0 pt-2">
        <div class="sticky top-20 space-y-8">

          <!-- Category filter -->
          <div>
            <h3 id="sidebar-category-heading" class="text-xs font-semibold text-secondary uppercase tracking-widest mb-4">Category</h3>
            <div id="sidebar-categories" class="space-y-1"></div>
          </div>

          <!-- Sort -->
          <div class="border-t border-outline-variant pt-6">
            <h3 id="sidebar-sort-heading" class="text-xs font-semibold text-secondary uppercase tracking-widest mb-4">Sort By</h3>
            <div id="sidebar-sort" class="space-y-1"></div>
          </div>

        </div>
      </aside>

      <!-- PRODUCT AREA -->
      <div class="flex-grow min-w-0">

        <!-- Mobile filter chips (hidden on lg sidebar) -->
        <div id="filter-bar" class="lg:hidden flex items-center gap-2 mb-4 overflow-x-auto no-scrollbar pb-2"></div>

        <!-- Count + sort row -->
        <div class="flex justify-between items-center mb-5">
          <span id="products-count" class="text-xs text-on-surface-variant"></span>
          <select id="sort-select"
                  class="text-xs text-on-surface bg-surface-container-lowest border border-outline-variant rounded-full px-3 py-1.5 outline-none cursor-pointer">
            <option value="default">Featured</option>
            <option value="trending">Trending</option>
            <option value="bestseller">Best Sellers</option>
            <option value="rating">Top Rated</option>
            <option value="price-low">Price &#8593;</option>
            <option value="price-high">Price &#8595;</option>
          </select>
        </div>

        <!-- Product grid: 1-col mobile, 2-col sm, 3-col lg -->
        <div id="product-grid" class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 md:gap-6"></div>

        <!-- No results -->
        <div id="no-results" class="hidden py-16 text-center">
          <span class="material-symbols-outlined text-4xl text-on-surface-variant block mb-3">search_off</span>
          <p id="no-results-text" class="text-on-surface-variant text-sm">No products found</p>
        </div>

      </div>
    </div>

  </main>

  <!-- ══ FOOTER ══════════════════════════════════════════════════════════ -->
  <footer class="mt-10 border-t border-surface-container">
    <div class="grid grid-cols-1 md:grid-cols-4 gap-6 max-w-[1440px] mx-auto px-5 md:px-16 py-10">

      <!-- Brand + disclaimer -->
      <div class="md:col-span-2">
        <p class="text-xl font-bold text-primary mb-2">Aether Global</p>
        <p id="footer-disclaimer" class="text-xs text-secondary leading-relaxed max-w-sm">
          As an Amazon Associate we earn from qualifying purchases.
        </p>
        <p class="text-xs text-secondary mt-2">Updated: __UPDATED__</p>
      </div>

      <!-- Links col 1 -->
      <div>
        <p class="text-xs font-semibold text-on-surface uppercase tracking-widest mb-3">Shop</p>
        <ul class="space-y-2">
          <li><button onclick="App.navShop()" class="text-xs text-secondary hover:text-primary transition-colors">All Products</button></li>
          <li><button onclick="App.navTrends()" class="text-xs text-secondary hover:text-primary transition-colors">Trending Now</button></li>
        </ul>
      </div>

      <!-- Links col 2 -->
      <div>
        <p class="text-xs font-semibold text-on-surface uppercase tracking-widest mb-3">About</p>
        <ul class="space-y-2">
          <li><span class="text-xs text-secondary">affiliate disclosure</span></li>
          <li><span class="text-xs text-secondary">privacy policy</span></li>
        </ul>
      </div>

    </div>
  </footer>

  <!-- ══ MOBILE BOTTOM NAV (hidden on desktop) ═══════════════════════════ -->
  <nav class="md:hidden fixed bottom-0 w-full z-50 flex justify-around items-center h-20 px-4 pb-2 bg-surface-container-lowest shadow-md border-t border-surface-container">
    <button id="nav-shop" onclick="App.navShop()"
            class="flex flex-col items-center justify-center px-4 py-1 rounded-xl text-xs bg-primary-container text-on-primary-container transition-all active:scale-90">
      <span class="material-symbols-outlined" style="font-variation-settings:'FILL' 1">shopping_bag</span>
      <span id="nav-shop-label">Shop</span>
    </button>
    <button id="nav-trends" onclick="App.navTrends()"
            class="flex flex-col items-center justify-center px-4 py-1 rounded-xl text-xs text-secondary transition-all active:scale-90">
      <span class="material-symbols-outlined">auto_awesome</span>
      <span id="nav-trends-label">Trends</span>
    </button>
    <button id="nav-saved" onclick="App.navSaved()"
            class="flex flex-col items-center justify-center px-4 py-1 rounded-xl text-xs text-secondary transition-all active:scale-90">
      <span class="material-symbols-outlined">favorite</span>
      <span id="nav-saved-label">Saved</span>
    </button>
    <button id="nav-account"
            class="flex flex-col items-center justify-center px-4 py-1 rounded-xl text-xs text-secondary transition-all active:scale-90">
      <span class="material-symbols-outlined">person</span>
      <span id="nav-account-label">Account</span>
    </button>
  </nav>

  <!-- ══ DATA ══════════════════════════════════════════════════════════════ -->
  <script id="products-data" type="application/json">__PRODUCTS__</script>
  <script id="translations-data" type="application/json">__TRANSLATIONS__</script>
  <script src="assets/app.js"></script>
</body>
</html>"""


# ═══════════════════════════════════════════════════════════════════════════════
# CSS — minimal, Tailwind CDN handles layout
# ═══════════════════════════════════════════════════════════════════════════════

_CSS = """
/* Material Symbols base */
.material-symbols-outlined {
  font-variation-settings: 'FILL' 0, 'wght' 400, 'GRAD' 0, 'opsz' 24;
}

/* Hide scrollbar for filter bar */
.no-scrollbar::-webkit-scrollbar { display: none; }
.no-scrollbar { -ms-overflow-style: none; scrollbar-width: none; }

/* Entry animation */
@keyframes fadeSlideUp {
  from { opacity: 0; transform: translateY(16px); }
  to   { opacity: 1; transform: translateY(0);    }
}
.animate-in {
  animation: fadeSlideUp 0.45s cubic-bezier(0.16, 1, 0.3, 1) forwards;
  opacity: 0;
}

/* Lazy-loaded images fade in */
.card-img {
  opacity: 0;
  transition: opacity 0.3s ease;
}
.card-img.loaded {
  opacity: 1;
}

/* Line clamp (cross-browser) */
.line-clamp-2 {
  overflow: hidden;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}

/* Shimmer loading skeleton */
.shimmer-bg {
  background: #f6f7f8;
  background-image: linear-gradient(to right, #f6f7f8 0%, #edeef1 20%, #f6f7f8 40%, #f6f7f8 100%);
  background-repeat: no-repeat;
  background-size: 1000px 100%;
  animation: shimmer 1.5s infinite linear;
}
@keyframes shimmer {
  0% { background-position: -1000px 0; }
  100% { background-position: 1000px 0; }
}

/* Card hover lift */
.product-card {
  transition: transform 0.25s ease, box-shadow 0.25s ease;
}
.product-card:hover {
  transform: translateY(-3px);
  box-shadow: 0 10px 28px rgba(117, 91, 0, 0.12);
}
"""


# ═══════════════════════════════════════════════════════════════════════════════
# JavaScript — AffilioLux client app
# ═══════════════════════════════════════════════════════════════════════════════

_JS = r"""
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

  return '<article class="product-card bg-surface-container-lowest rounded-xl shadow-sm overflow-hidden flex flex-col animate-in" '
       + 'style="animation-delay:' + delay + 's">'

       // Image area with shimmer
       + '<div class="relative w-full aspect-square bg-surface-container-low cursor-pointer shimmer-bg" '
       + 'onclick="window.open(\'' + url + '\',\'_blank\')">'
       + '<img data-src="' + imgSrc + '" alt="' + title + '" '
       + 'class="card-img w-full h-full object-contain mix-blend-multiply p-4" '
       + 'onload="this.parentElement.classList.remove(\'shimmer-bg\')" '
       + 'onerror="this.hidden=true;this.parentElement.classList.remove(\'shimmer-bg\')">'
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
  App.render();
});

window.App = App;

})();
"""
