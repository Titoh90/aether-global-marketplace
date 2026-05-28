"""
template_renderer.py — Premium light-theme affiliate marketplace renderer.

Zero frameworks: HTML + CSS + vanilla JS (~12KB gzipped).
Mobile-first, gold-accented premium design.
Features: i18n (EN/ES/FR), search bar, category filters,
IntersectionObserver lazy loading, trust labels, star ratings.
Output: self-contained index.html with embedded products JSON.
"""
from __future__ import annotations

import html as _html
import json
from .schemas import HubSurface, SurfaceProduct


# ═══════════════════════════════════════════════════════════════════════════════
# Public API
# ═══════════════════════════════════════════════════════════════════════════════

def render_html(surface: HubSurface) -> str:
    """Render the complete SPA shell with embedded product data and i18n."""
    products_json = _build_products_json(surface)
    translations_json = json.dumps(_TRANSLATIONS, ensure_ascii=False)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Aether Global — Premium Deals</title>
  <meta name="description" content="Curated premium products with affiliate links. Quality you can trust.">
  <link rel="preconnect" href="https://m.media-amazon.com" crossorigin>
  <link rel="stylesheet" href="assets/styles.css">
</head>
<body>
  <noscript><div style="text-align:center;padding:3rem 1rem;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif"><p style="color:#9CA3AF;font-size:1rem">JavaScript is required to view our curated product deals.</p></div></noscript>
  <header class="site-header" id="site-header">
    <div class="header-inner">
      <a href="#" class="brand" aria-label="Aether Global Home" onclick="App.reset();return false">
        <span class="brand-icon">◆</span>
        <span class="brand-text">AETHER</span>
        <span class="brand-sub">GLOBAL</span>
      </a>
      <div class="header-right">
        <div class="search-box">
          <svg class="search-icon" viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/></svg>
          <input type="text" id="search-input" class="search-input" placeholder="Search products..." autocomplete="off">
          <button class="search-clear" id="search-clear" aria-label="Clear search" onclick="App.clearSearch()">&times;</button>
        </div>
        <div class="lang-selector">
          <button class="lang-btn" data-lang="en" onclick="App.setLang('en')" id="lang-en">EN</button>
          <button class="lang-btn" data-lang="es" onclick="App.setLang('es')" id="lang-es">ES</button>
          <button class="lang-btn" data-lang="fr" onclick="App.setLang('fr')" id="lang-fr">FR</button>
        </div>
      </div>
    </div>
  </header>

  <main>
    <section class="hero-section">
      <div class="hero-content">
        <h1 class="hero-title" data-i18n="heroTitle">Curated Premium Deals</h1>
        <p class="hero-subtitle" data-i18n="heroSubtitle">Hand-picked products from Amazon's best sellers. Quality you can trust.</p>
        <button class="hero-cta" onclick="document.getElementById('search-input').focus()" data-i18n="heroCTA">Explore Deals</button>
      </div>
    </section>

    <nav class="category-nav" id="category-nav">
      <div class="category-inner">
        <button class="cat-pill active" data-category="all" onclick="App.filterCategory('all')">
          <span data-i18n="allCategories">All</span>
        </button>
      </div>
    </nav>

    <section class="products-section">
      <div class="section-header">
        <div class="header-left">
          <h2 class="products-count" id="products-count"></h2>
        </div>
        <div class="header-right">
          <div class="sort-bar">
            <label class="sort-label" for="sort-select" data-i18n="sortLabel">Sort by</label>
            <select id="sort-select" class="sort-select" onchange="App.setSort(this.value)">
              <option value="default">—</option>
              <option value="trending">Trending</option>
              <option value="bestseller">Best Sellers</option>
              <option value="rating">Top Rated</option>
              <option value="price-low">Price: Low to High</option>
              <option value="price-high">Price: High to Low</option>
            </select>
          </div>
          <div class="view-toggle">
            <button class="view-btn active" data-view="grid" onclick="App.setView('grid')" title="Grid view" aria-label="Grid view">
              <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor"><rect x="1" y="1" width="6" height="6" rx="1"/><rect x="9" y="1" width="6" height="6" rx="1"/><rect x="1" y="9" width="6" height="6" rx="1"/><rect x="9" y="9" width="6" height="6" rx="1"/></svg>
            </button>
            <button class="view-btn" data-view="list" onclick="App.setView('list')" title="List view" aria-label="List view">
              <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor"><rect x="1" y="2" width="14" height="3" rx="1"/><rect x="1" y="7" width="14" height="3" rx="1"/><rect x="1" y="12" width="14" height="3" rx="1"/></svg>
            </button>
          </div>
        </div>
      </div>
      <div class="product-grid" id="product-grid"></div>
      <div class="no-results" id="no-results" style="display:none">
        <p data-i18n="noResults">No products found</p>
      </div>
    </section>
  </main>

  <footer class="site-footer">
    <div class="footer-inner">
      <p class="footer-brand">◆ AETHER GLOBAL</p>
      <p class="footer-disclaimer" data-i18n="footerDisclaimer">As an Amazon Associate we earn from qualifying purchases.</p>
      <p class="footer-updated"><span data-i18n="updated">Updated</span>: {_e(surface.generated_at[:16].replace('T', ' '))}</p>
    </div>
  </footer>

  <script id="products-data" type="application/json">{products_json}</script>
  <script id="translations-data" type="application/json">{translations_json}</script>
  <script src="assets/app.js"></script>
</body>
</html>"""


# ═══════════════════════════════════════════════════════════════════════════════
# Public renderers for multi-file output
# ═══════════════════════════════════════════════════════════════════════════════

def render_css() -> str:
    """Return standalone CSS for assets/styles.css."""
    return _css()


def render_js() -> str:
    """Return standalone JS for assets/app.js."""
    return _js()


# ═══════════════════════════════════════════════════════════════════════════════
# Data Helpers
# ═══════════════════════════════════════════════════════════════════════════════

def _amazon_image_url(asin: str, size: str = "SL400") -> str:
    """Return direct Amazon CDN image URL. Works without domain registration."""
    if not asin:
        return ""
    return f"https://m.media-amazon.com/images/P/{asin}.01._{size}_.jpg"


def _build_carousel_image_urls(asin: str, primary_url: str) -> list:
    """Generate up to 3 image URLs for carousel slides using Amazon CDN image variants.
    Uses .01. .02. .03. suffixes which are standard Amazon product image indices.
    Falls back to primary_url if no asin."""
    if not asin:
        return [primary_url] if primary_url else []
    return [
        f"https://m.media-amazon.com/images/P/{asin}.01._SL400_.jpg",
        f"https://m.media-amazon.com/images/P/{asin}.02._SL400_.jpg",
        f"https://m.media-amazon.com/images/P/{asin}.03._SL400_.jpg",
    ]

# ── Product Description i18n ────────────────────────────────────────────────────

# Mapping: English archetype/category name → {es, fr} marketing descriptions.
# Keys are matched case-insensitively. Falls back to auto-generated text.
_DESCRIPTIONS: dict[str, dict[str, str]] = {
    # Categories
    "electronics": {
        "es": "Electrónica y tecnología premium",
        "fr": "Électronique et high-tech premium",
    },
    "beauty": {
        "es": "Belleza y cuidado personal de lujo",
        "fr": "Beauté et soins personnels de luxe",
    },
    "home": {
        "es": "Esenciales para el hogar y la cocina",
        "fr": "Indispensables pour la maison et la cuisine",
    },
    "fashion": {
        "es": "Moda y accesorios con estilo",
        "fr": "Mode et accessoires élégants",
    },
    "kitchen": {
        "es": "Innovación para tu cocina",
        "fr": "Innovation pour votre cuisine",
    },
    "sports": {
        "es": "Equipamiento deportivo de alto rendimiento",
        "fr": "Équipement sportif haute performance",
    },
    "office": {
        "es": "Productividad y ergonomía para tu oficina",
        "fr": "Productivité et ergonomie pour votre bureau",
    },
    "toys": {
        "es": "Juguetes y entretenimiento para todas las edades",
        "fr": "Jouets et divertissement pour tous les âges",
    },
    "garden": {
        "es": "Herramientas y decoración para exteriores",
        "fr": "Outils et décoration d'extérieur",
    },
    "automotive": {
        "es": "Accesorios y cuidado automotriz",
        "fr": "Accessoires et entretien automobile",
    },
    "health": {
        "es": "Salud y bienestar personal",
        "fr": "Santé et bien-être personnel",
    },
    "books": {
        "es": "Libros y conocimiento al mejor precio",
        "fr": "Livres et savoir au meilleur prix",
    },
    "general": {
        "es": "Producto seleccionado por su calidad",
        "fr": "Produit sélectionné pour sa qualité",
    },
}


def _build_product_description(desc_en: str, category: str = "") -> dict[str, str]:
    """Build {"en": ..., "es": ..., "fr": ...} with real translations.

    Strategy:
    1. Match desc_en (archetype label) or category against _DESCRIPTIONS (case-insensitive).
    2. Fall back to auto-generated text: "Premium {category} products" pattern.
    """
    key = desc_en.lower().strip()
    if key in _DESCRIPTIONS:
        return {"en": desc_en, "es": _DESCRIPTIONS[key]["es"], "fr": _DESCRIPTIONS[key]["fr"]}

    # Try matching category
    cat_key = category.lower().strip()
    if cat_key in _DESCRIPTIONS:
        return {"en": desc_en, "es": _DESCRIPTIONS[cat_key]["es"], "fr": _DESCRIPTIONS[cat_key]["fr"]}

    # Fallback: auto-generate from category name
    cat_title = category.title() if category else desc_en
    fallback_es = f"{cat_title} — producto premium seleccionado"
    fallback_fr = f"{cat_title} — produit premium sélectionné"
    return {"en": desc_en, "es": fallback_es, "fr": fallback_fr}


def _build_products_json(surface: HubSurface) -> str:
    """Build enriched products JSON matching the JS frontend schema."""
    all_products = [surface.hero]
    all_products.extend(surface.trending)
    all_products.extend(surface.evergreen)
    for prods in surface.by_category.values():
        all_products.extend(prods)
    all_products.extend(surface.recent)

    seen: set[str] = set()
    categories: set[str] = set()
    products_out = []
    for p in all_products:
        if p.asin in seen:
            continue
        seen.add(p.asin)
        categories.add(p.category)
        desc_en = p.archetype_label or (p.creative_mode.replace("_", " ").title() if p.creative_mode else p.category)
        tags = []
        if p.section == "hero":
            tags.append("bestseller")
        if p.section == "trending":
            tags.append("trending")
        if p.evergreen_status == "experimental":
            tags.append("limited")
        # Type assignment: video for high-conversion bestsellers, carousel for trending, product for rest
        has_bestseller = "bestseller" in tags
        has_trending = "trending" in tags
        rating = p.rating or 0
        if has_bestseller and rating >= 4.0:
            ptype = "video"
        elif has_trending:
            ptype = "carousel"
        else:
            ptype = "product"
        img_src = p.image_url or _amazon_image_url(p.asin)
        if ptype in ("carousel", "video"):
            image_urls = _build_carousel_image_urls(p.asin, img_src)
        else:
            image_urls = [img_src] if img_src else []
        products_out.append({
            "id": p.asin,
            "title": p.name,
            "price": p.price,
            "image": img_src,
            "imageUrls": image_urls,
            "rating": p.rating,
            "reviews": p.reviews,
            "category": p.category,
            "affiliateUrl": p.tracking_url or p.affiliate_url,
            "description": _build_product_description(desc_en, p.category),
            "tags": tags,
            "section": p.section,
            "type": ptype,
        })

    return json.dumps({
        "generated_at": surface.generated_at,
        "categories": sorted(categories),
        "products": products_out,
    }, ensure_ascii=False)


# ═══════════════════════════════════════════════════════════════════════════════
# i18n
# ═══════════════════════════════════════════════════════════════════════════════

_TRANSLATIONS = {
    "en": {
        "siteTagline": "Premium Deals",
        "searchPlaceholder": "Search products...",
        "allCategories": "All",
        "buyOnAmazon": "Buy on Amazon",
        "heroTitle": "Curated Premium Deals",
        "heroSubtitle": "Hand-picked products from Amazon's best sellers. Quality you can trust.",
        "heroCTA": "Explore Deals",
        "bestseller": "Best Seller",
        "limitedOffer": "Limited Offer",
        "trendingLabel": "Trending",
        "footerDisclaimer": "As an Amazon Associate we earn from qualifying purchases.",
        "updated": "Updated",
        "noResults": "No products found",
        "productsFound": "products",
        "sortLabel": "Sort by",
        "sortDefault": "Featured",
        "sortTrending": "Trending",
        "sortBestseller": "Best Sellers",
        "sortPriceLow": "Price: Low to High",
        "sortPriceHigh": "Price: High to Low",
        "sortRating": "Top Rated",
        "viewGrid": "Grid",
        "viewList": "List",
        "watchVideo": "Watch Video",
        "closePreview": "Close",
        "watchOnAmazon": "Watch on Amazon",
    },
    "es": {
        "siteTagline": "Ofertas Premium",
        "searchPlaceholder": "Buscar productos...",
        "allCategories": "Todos",
        "buyOnAmazon": "Comprar en Amazon",
        "heroTitle": "Ofertas Premium Seleccionadas",
        "heroSubtitle": "Productos seleccionados de los más vendidos de Amazon. Calidad en la que puedes confiar.",
        "heroCTA": "Explorar Ofertas",
        "bestseller": "Más Vendido",
        "limitedOffer": "Oferta Limitada",
        "trendingLabel": "Tendencia",
        "footerDisclaimer": "Como Asociado de Amazon, ganamos comisiones por compras que califican.",
        "updated": "Actualizado",
        "noResults": "No se encontraron productos",
        "productsFound": "productos",
        "sortLabel": "Ordenar por",
        "sortDefault": "Destacados",
        "sortTrending": "Tendencias",
        "sortBestseller": "Más Vendidos",
        "sortPriceLow": "Precio: Menor a Mayor",
        "sortPriceHigh": "Precio: Mayor a Menor",
        "sortRating": "Mejor Valorados",
        "viewGrid": "Cuadrícula",
        "viewList": "Lista",
        "watchVideo": "Ver Video",
        "closePreview": "Cerrar",
        "watchOnAmazon": "Ver en Amazon",
    },
    "fr": {
        "siteTagline": "Offres Premium",
        "searchPlaceholder": "Rechercher des produits...",
        "allCategories": "Tous",
        "buyOnAmazon": "Acheter sur Amazon",
        "heroTitle": "Offres Premium Sélectionnées",
        "heroSubtitle": "Produits triés sur le volet parmi les meilleures ventes d'Amazon. Une qualité de confiance.",
        "heroCTA": "Explorer les Offres",
        "bestseller": "Meilleure Vente",
        "limitedOffer": "Offre Limitée",
        "trendingLabel": "Tendance",
        "footerDisclaimer": "En tant que Partenaire Amazon, nous gagnons des commissions sur les achats éligibles.",
        "updated": "Mis à jour",
        "noResults": "Aucun produit trouvé",
        "productsFound": "produits",
        "sortLabel": "Trier par",
        "sortDefault": "En vedette",
        "sortTrending": "Tendances",
        "sortBestseller": "Meilleures Ventes",
        "sortPriceLow": "Prix: Croissant",
        "sortPriceHigh": "Prix: Décroissant",
        "sortRating": "Mieux Notés",
        "viewGrid": "Grille",
        "viewList": "Liste",
        "watchVideo": "Voir Vidéo",
        "closePreview": "Fermer",
        "watchOnAmazon": "Voir sur Amazon",
    },
}


# ═══════════════════════════════════════════════════════════════════════════════
# CSS — Light Premium Theme
# ═══════════════════════════════════════════════════════════════════════════════

def _css() -> str:
    return """/* ═══════════════════════════════════════════════════════════
   AETHER GLOBAL — Premium Affiliate Marketplace
   Design System: Light + Gold (#C9A84C)
   ═══════════════════════════════════════════════════════════ */

:root {
  --gold: #C9A84C;
  --gold-hover: #D4B55E;
  --gold-soft: rgba(201,168,76,.08);
  --gold-glow: rgba(201,168,76,.18);
  --bg: #FAFBFC;
  --surface: #FFFFFF;
  --surface-hover: #F7F8FA;
  --border: #E5E7EB;
  --border-hover: #D1D5DB;
  --text: #1A1A2E;
  --text-secondary: #6B7280;
  --text-muted: #9CA3AF;
  --shadow-sm: 0 1px 2px rgba(0,0,0,.04);
  --shadow-md: 0 4px 12px rgba(0,0,0,.06);
  --shadow-lg: 0 8px 30px rgba(0,0,0,.08);
  --radius-sm: 8px;
  --radius: 12px;
  --radius-lg: 16px;
  --font: -apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,'Helvetica Neue',Arial,sans-serif;
}

*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}

html{scroll-behavior:smooth}
body{
  background:var(--bg);
  color:var(--text);
  font-family:var(--font);
  line-height:1.5;
  -webkit-font-smoothing:antialiased;
  min-height:100vh;
}

/* ── Header ─────────────────────────────── */
.site-header{
  position:sticky;top:0;z-index:100;
  background:rgba(255,255,255,.88);
  backdrop-filter:blur(12px);
  -webkit-backdrop-filter:blur(12px);
  border-bottom:1px solid var(--border);
}
.header-inner{
  max-width:1200px;margin:0 auto;
  display:flex;align-items:center;justify-content:space-between;
  padding:.65rem 1rem;gap:1rem;
  flex-wrap:wrap;
}
.brand{
  display:flex;align-items:center;gap:.4rem;
  text-decoration:none;color:inherit;
  flex-shrink:0;
}
.brand-icon{color:var(--gold);font-size:1.3rem}
.brand-text{font-weight:700;font-size:1.05rem;letter-spacing:.08em}
.brand-sub{
  color:var(--text-muted);font-size:.65rem;
  font-weight:500;letter-spacing:.15em;
}
.header-right{
  display:flex;align-items:center;gap:.75rem;flex:1;justify-content:flex-end;
}

/* ── Search ──────────────────────────────── */
.search-box{
  position:relative;flex:1;max-width:340px;min-width:180px;
}
.search-icon{
  position:absolute;left:.65rem;top:50%;transform:translateY(-50%);
  color:var(--text-muted);pointer-events:none;
}
.search-input{
  width:100%;padding:.45rem .7rem .45rem 2rem;
  border:1px solid var(--border);border-radius:20px;
  font-size:.8rem;font-family:inherit;
  background:var(--bg);color:var(--text);
  transition:border-color .2s,box-shadow .2s;
  outline:none;
}
.search-input:focus{
  border-color:var(--gold);box-shadow:0 0 0 3px var(--gold-soft);
}
.search-input::placeholder{color:var(--text-muted)}
.search-clear{
  position:absolute;right:.5rem;top:50%;transform:translateY(-50%);
  background:none;border:none;color:var(--text-muted);
  font-size:1rem;cursor:pointer;padding:0 .2rem;line-height:1;
  display:none;
}
.search-clear.visible{display:block}

/* ── Language Selector ───────────────────── */
.lang-selector{display:flex;gap:2px;flex-shrink:0}
.lang-btn{
  background:none;border:1px solid var(--border);border-radius:6px;
  padding:.3rem .5rem;font-size:.68rem;font-weight:600;font-family:inherit;
  color:var(--text-muted);cursor:pointer;
  transition:all .15s;
}
.lang-btn:hover{color:var(--text);border-color:var(--border-hover)}
.lang-btn.active{
  background:var(--gold);color:#fff;border-color:var(--gold);
}

/* ── Hero ────────────────────────────────── */
.hero-section{
  background:linear-gradient(135deg,#F7F8FA 0%,#F0F1F5 50%,#F7F8FA 100%);
  border-bottom:1px solid var(--border);
}
.hero-content{
  max-width:800px;margin:0 auto;text-align:center;
  padding:2.5rem 1rem 2rem;
}
.hero-title{
  font-size:1.6rem;font-weight:800;letter-spacing:-.02em;
  color:var(--text);margin-bottom:.5rem;
  line-height:1.2;
}
.hero-subtitle{
  font-size:.9rem;color:var(--text-secondary);
  max-width:500px;margin:0 auto 1.25rem;line-height:1.5;
}
.hero-cta{
  display:inline-block;padding:.65rem 1.75rem;
  background:var(--gold);color:#fff;
  border:none;border-radius:20px;
  font-size:.85rem;font-weight:600;font-family:inherit;
  cursor:pointer;letter-spacing:.02em;
  transition:background .2s,transform .15s,box-shadow .2s;
}
.hero-cta:hover{
  background:var(--gold-hover);
  transform:translateY(-1px);
  box-shadow:0 4px 16px var(--gold-glow);
}

/* ── Category Nav ────────────────────────── */
.category-nav{
  border-bottom:1px solid var(--border);
  background:var(--surface);
  position:sticky;top:56px;z-index:99;
}
.category-inner{
  max-width:1200px;margin:0 auto;
  display:flex;gap:.4rem;padding:.55rem 1rem;
  overflow-x:auto;-webkit-overflow-scrolling:touch;
  scrollbar-width:none;
}
.category-inner::-webkit-scrollbar{display:none}
.cat-pill{
  flex-shrink:0;padding:.35rem .85rem;
  border:1px solid var(--border);border-radius:20px;
  font-size:.73rem;font-weight:500;font-family:inherit;
  background:var(--surface);color:var(--text-secondary);
  cursor:pointer;white-space:nowrap;
  transition:all .18s;
}
.cat-pill:hover{border-color:var(--gold);color:var(--text)}
.cat-pill.active{
  background:var(--gold);color:#fff;border-color:var(--gold);
  font-weight:600;
}

/* ── Products Section ────────────────────── */
.products-section{max-width:1200px;margin:0 auto;padding:1.25rem 1rem 3rem}
.section-header{
  display:flex;align-items:center;justify-content:space-between;
  flex-wrap:wrap;gap:.5rem;margin-bottom:.75rem;
}
.header-left{flex-shrink:0}
.header-right{display:flex;align-items:center;gap:.75rem}
.products-count{font-size:.75rem;color:var(--text-muted);font-weight:500}

/* ── Sort Bar ────────────────────────────── */
.sort-bar{display:flex;align-items:center;gap:.4rem}
.sort-label{font-size:.68rem;color:var(--text-muted);white-space:nowrap}
.sort-select{
  padding:.3rem .6rem;font-size:.7rem;font-family:inherit;
  border:1px solid var(--border);border-radius:8px;
  background:var(--surface);color:var(--text);
  cursor:pointer;outline:none;
  transition:border-color .15s;
  -webkit-appearance:none;appearance:none;
  background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='8' height='5'%3E%3Cpath d='M0 0l4 5 4-5z' fill='%239CA3AF'/%3E%3C/svg%3E");
  background-repeat:no-repeat;background-position:right .4rem center;
  padding-right:1.3rem;
}
.sort-select:focus{border-color:var(--gold)}

/* ── View Toggle ─────────────────────────── */
.view-toggle{display:flex;gap:2px;flex-shrink:0}
.view-btn{
  display:flex;align-items:center;justify-content:center;
  width:32px;height:30px;padding:0;
  background:var(--surface);border:1px solid var(--border);
  border-radius:6px;color:var(--text-muted);cursor:pointer;
  transition:all .15s;
}
.view-btn:first-child{border-radius:6px 0 0 6px}
.view-btn:last-child{border-radius:0 6px 6px 0}
.view-btn:hover{color:var(--text);border-color:var(--border-hover)}
.view-btn.active{background:var(--gold);color:#fff;border-color:var(--gold)}

/* ── Product Grid ────────────────────────── */
.product-grid{
  display:grid;
  grid-template-columns:repeat(2,1fr);
  gap:.75rem;
}

/* ── Product Card ────────────────────────── */
.product-card{
  background:var(--surface);
  border:1px solid var(--border);
  border-radius:var(--radius);
  overflow:hidden;
  transition:border-color .25s,box-shadow .25s,transform .2s;
  display:flex;flex-direction:column;
  cursor:pointer;
  position:relative;
}
.product-card:hover{
  border-color:var(--gold);
  box-shadow:var(--shadow-lg);
  transform:translateY(-2px);
}
.card-img-wrap{position:relative;overflow:hidden;aspect-ratio:1/1;background:var(--bg)}
.card-img{
  width:100%;height:100%;object-fit:cover;
  display:block;transition:transform .4s;
  opacity:0;
}
.card-img.loaded{opacity:1}
.product-card:hover .card-img{transform:scale(1.05)}
.card-img-placeholder{
  position:absolute;inset:0;
  display:flex;align-items:center;justify-content:center;
  color:var(--text-muted);font-size:.7rem;
  background:var(--bg);
}

/* ── Price Badge ─────────────────────────── */
.price-badge{
  position:absolute;bottom:.5rem;left:.5rem;
  background:rgba(0,0,0,.78);color:var(--gold);
  font-weight:700;font-size:.78rem;
  padding:.25rem .5rem;border-radius:5px;
  letter-spacing:.02em;
}

/* ── Trust Labels ────────────────────────── */
.trust-label{
  position:absolute;top:.5rem;right:.5rem;
  font-size:.58rem;font-weight:700;text-transform:uppercase;
  padding:.18rem .45rem;border-radius:4px;
  letter-spacing:.05em;
  z-index:2;
}
.trust-label.bestseller{background:#C9A84C;color:#fff}
.trust-label.trending{background:#B8942E;color:#fff}
.trust-label.limited{background:#E5D5A0;color:#5C4A1E}

/* ── Card Body ───────────────────────────── */
.card-body{padding:.65rem;display:flex;flex-direction:column;flex:1}
.product-name{
  font-size:.8rem;font-weight:600;line-height:1.3;
  display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;
  overflow:hidden;color:var(--text);margin-bottom:.2rem;
}
.product-desc{
  font-size:.68rem;color:var(--text-secondary);
  line-height:1.35;margin-bottom:.3rem;
  display:-webkit-box;-webkit-line-clamp:1;-webkit-box-orient:vertical;
  overflow:hidden;
}

/* ── Star Rating ─────────────────────────── */
.rating-row{display:flex;align-items:center;gap:.3rem;margin-bottom:.45rem}
.stars{
  display:inline-block;font-size:.8rem;
  font-family:Times,serif;line-height:1;
  letter-spacing:1px;white-space:nowrap;
}
.stars::before{
  content:'★★★★★';
  background:linear-gradient(90deg,var(--gold) var(--pct,0%),#D1D5DB var(--pct,0%));
  -webkit-background-clip:text;-webkit-text-fill-color:transparent;
  background-clip:text;
}
.rating-value{font-size:.68rem;font-weight:700;color:var(--gold)}
.review-count{font-size:.62rem;color:var(--text-muted)}

/* ── CTA Button ──────────────────────────── */
.cta-btn{
  display:block;width:100%;padding:.5rem .5rem;
  background:var(--gold);color:#fff;
  font-weight:700;font-size:.72rem;font-family:inherit;
  letter-spacing:.05em;text-transform:uppercase;
  border:none;border-radius:6px;cursor:pointer;
  transition:background .2s,transform .15s;
  margin-top:auto;
}
.cta-btn:hover{background:var(--gold-hover);transform:scale(1.02)}
.cta-btn:active{transform:scale(.98)}

/* ── List View ───────────────────────────── */
.product-grid.list{
  display:flex;flex-direction:column;
  gap:.625rem;
}
.product-grid.list .product-card{
  flex-direction:row;
  align-items:stretch;
}
.product-grid.list .product-card:hover{
  transform:translateX(4px);
}
.product-grid.list .card-img-wrap{
  width:140px;min-width:140px;flex-shrink:0;
  aspect-ratio:auto;height:auto;
}
.product-grid.list .card-img-wrap .card-img{
  position:relative;inset:auto;
}
.product-grid.list .card-body{
  flex:1;padding:.75rem;
  justify-content:center;
}
.product-grid.list .product-name{
  font-size:.82rem;-webkit-line-clamp:3;
}
.product-grid.list .product-desc{
  -webkit-line-clamp:2;
}
.product-grid.list .cta-btn{
  width:auto;align-self:flex-start;
  padding:.45rem 1rem;
}
.product-grid.list .price-badge{
  position:absolute;bottom:.4rem;left:.4rem;
  font-size:.7rem;
}
.product-grid.list .trust-label{
  top:.4rem;right:.4rem;
}

/* ── Video Card ──────────────────────────── */
.video-card .card-img-wrap{position:relative}
.video-overlay{
  position:absolute;inset:0;
  display:flex;flex-direction:column;
  align-items:center;justify-content:center;
  background:rgba(0,0,0,.35);
  transition:background .3s;
  z-index:2;
}
.video-card:hover .video-overlay{background:rgba(0,0,0,.5)}
.play-icon{
  width:40px;height:40px;
  background:var(--gold);color:#fff;
  border-radius:50%;
  display:flex;align-items:center;justify-content:center;
  font-size:.9rem;margin-bottom:.35rem;
  box-shadow:0 4px 16px rgba(0,0,0,.3);
  transition:transform .2s,box-shadow .2s;
}
.video-card:hover .play-icon{
  transform:scale(1.1);
  box-shadow:0 6px 24px rgba(0,0,0,.4);
}
.video-label{
  color:#fff;font-size:.65rem;font-weight:600;
  letter-spacing:.05em;text-transform:uppercase;
}

/* ── Carousel Card ───────────────────────── */
.carousel-track{
  display:flex;overflow-x:auto;scroll-snap-type:x mandatory;
  -webkit-overflow-scrolling:touch;
  scrollbar-width:none;
  aspect-ratio:1/1;
}
.carousel-track::-webkit-scrollbar{display:none}
.carousel-slide{
  flex:0 0 100%;scroll-snap-align:start;
  position:relative;background:var(--bg);
}
.carousel-slide img{
  width:100%;height:100%;object-fit:cover;
  display:block;
}
.carousel-dots{
  position:absolute;bottom:.5rem;left:50%;transform:translateX(-50%);
  display:flex;gap:.3rem;z-index:3;
}
.carousel-dot{
  width:6px;height:6px;border-radius:50%;
  background:rgba(255,255,255,.5);
  transition:background .2s,transform .2s;
}
.carousel-dot.active{
  background:var(--gold);transform:scale(1.3);
}

/* ── Video Preview Modal ─────────────────── */
body.modal-open{overflow:hidden}
.video-modal{
  position:fixed;inset:0;z-index:1000;
  display:flex;align-items:center;justify-content:center;
  animation:modalFadeIn .25s ease;
}
@keyframes modalFadeIn{from{opacity:0}to{opacity:1}}
.video-modal-backdrop{
  position:absolute;inset:0;
  background:rgba(0,0,0,.92);
  cursor:pointer;
}
.video-modal-content{
  position:relative;z-index:1;
  width:92vw;max-width:900px;max-height:90vh;
  background:#000;border-radius:var(--radius-lg);
  overflow:hidden;
  box-shadow:0 20px 60px rgba(0,0,0,.5);
  animation:modalSlideUp .3s ease;
}
@keyframes modalSlideUp{from{opacity:0;transform:translateY(30px)}to{opacity:1;transform:translateY(0)}}

.video-modal-close{
  position:absolute;top:.75rem;right:.75rem;z-index:10;
  width:36px;height:36px;
  background:rgba(0,0,0,.65);color:#fff;
  border:2px solid rgba(255,255,255,.25);
  border-radius:50%;
  font-size:1.2rem;line-height:1;
  cursor:pointer;display:flex;align-items:center;justify-content:center;
  transition:background .2s,border-color .2s;
}
.video-modal-close:hover{
  background:rgba(255,255,255,.15);border-color:rgba(255,255,255,.5);
}

.video-slides{position:relative;aspect-ratio:16/10;background:#000}
.video-slide{
  position:absolute;inset:0;opacity:0;
  transition:opacity .5s ease;
}
.video-slide.active{opacity:1}
.video-modal-img{
  width:100%;height:100%;object-fit:contain;
  display:block;
  animation:kenBurns 4s ease-in-out infinite alternate;
}
.video-slide.active .video-modal-img{
  animation-play-state:running;
}
@keyframes kenBurns{
  from{transform:scale(1) translateY(0)}
  to{transform:scale(1.08) translateY(-1%)}
}

/* ── Video Dots ──────────────────────────── */
.video-dots{
  position:absolute;bottom:.75rem;left:50%;transform:translateX(-50%);
  display:flex;gap:.35rem;z-index:5;
}
.video-dot{
  width:8px;height:8px;border-radius:50%;
  background:rgba(255,255,255,.4);
  transition:background .2s,transform .2s;
  cursor:pointer;
}
.video-dot.active{
  background:var(--gold);transform:scale(1.4);
}

/* ── Video Info Bar ──────────────────────── */
.video-info-bar{
  display:flex;align-items:center;justify-content:space-between;
  padding:.75rem 1rem;
  background:rgba(0,0,0,.85);
  border-top:1px solid rgba(255,255,255,.08);
  gap:.75rem;
}
.video-nav-arrows{display:flex;gap:.5rem}
.video-arrow{
  width:34px;height:34px;
  background:rgba(255,255,255,.08);color:#fff;
  border:1px solid rgba(255,255,255,.15);
  border-radius:8px;
  font-size:1.2rem;line-height:1;
  cursor:pointer;display:flex;align-items:center;justify-content:center;
  transition:background .2s,border-color .2s;
}
.video-arrow:hover{
  background:rgba(255,255,255,.18);border-color:rgba(255,255,255,.3);
}
.video-cta-btn{
  display:inline-flex;align-items:center;gap:.35rem;
  padding:.55rem 1.25rem;
  background:var(--gold);color:#fff;
  font-weight:700;font-size:.78rem;font-family:inherit;
  letter-spacing:.03em;text-transform:uppercase;
  border-radius:8px;text-decoration:none;
  transition:background .2s,transform .15s;
  white-space:nowrap;
}
.video-cta-btn:hover{
  background:var(--gold-hover);transform:scale(1.03);
}

/* ── No Results ──────────────────────────── */
.no-results{text-align:center;padding:3rem 1rem}
.no-results p{color:var(--text-muted);font-size:.9rem}

/* ── Footer ──────────────────────────────── */
.site-footer{
  border-top:1px solid var(--border);
  background:var(--surface);
}
.footer-inner{
  max-width:1200px;margin:0 auto;
  padding:2rem 1rem;text-align:center;
}
.footer-brand{
  color:var(--gold);font-weight:700;font-size:.75rem;
  letter-spacing:.1em;margin-bottom:.5rem;
}
.footer-disclaimer{font-size:.65rem;color:var(--text-muted);margin-bottom:.3rem}
.footer-updated{font-size:.6rem;color:#c0c4cc}

/* ── Responsive ──────────────────────────── */
@media(min-width:480px){
  .product-grid{grid-template-columns:repeat(2,1fr);gap:.875rem}
  .product-name{font-size:.82rem}.cta-btn{font-size:.75rem}
}
@media(min-width:640px){
  .hero-content{padding:3.5rem 1.5rem 2.5rem}
  .hero-title{font-size:2rem}
  .hero-subtitle{font-size:.95rem}
  .product-grid{grid-template-columns:repeat(3,1fr)}
}
@media(min-width:900px){
  .product-grid{grid-template-columns:repeat(4,1fr);gap:1rem}
  .hero-title{font-size:2.2rem}
}
@media(min-width:1200px){
  .product-grid{grid-template-columns:repeat(4,1fr);gap:1.25rem}
}
@media(max-width:540px){
  .header-inner{flex-direction:column;align-items:stretch;gap:.5rem}
  .header-right{justify-content:stretch}
  .search-box{max-width:none}
}
"""


# ═══════════════════════════════════════════════════════════════════════════════
# JavaScript — Marketplace SPA
# ═══════════════════════════════════════════════════════════════════════════════

def _js() -> str:
    return """
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
  var html = '<button class="cat-pill' + (App.category === 'all' ? ' active' : '') + '" data-category="all" onclick="App.filterCategory(\\'all\\')">' + App.t('allCategories') + '</button>';
  CATEGORIES.forEach(function(cat) {
    html += '<button class="cat-pill' + (App.category === cat ? ' active' : '') + '" data-category="' + _escAttr(cat) + '" onclick="App.filterCategory(\\'' + _escAttr(cat) + '\\')">' + _escHtml(cat) + '</button>';
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
          if (src && !img.getAttribute('src')) {
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
      if (src && !img.getAttribute('src')) img.src = src;
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
          (hasMultiple ? '<button class="video-arrow video-arrow-prev">&#8249;</button>' : '') +
          (hasMultiple ? '<button class="video-arrow video-arrow-next">&#8250;</button>' : '') +
        '</div>' +
        (_videoUrl ? '<a href="' + _escAttr(_videoUrl) + '" target="_blank" rel="noopener noreferrer" class="video-cta-btn">' + ctaLabel + ' &rarr;</a>' : '') +
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
      if (src && !img.getAttribute('src')) img.src = src;
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
"""


# ═══════════════════════════════════════════════════════════════════════════════
# Legacy helpers (kept for import compatibility)
# ═══════════════════════════════════════════════════════════════════════════════

def _e(s: str) -> str:
    return _html.escape(str(s), quote=True)

def _render_product_card(p: SurfaceProduct) -> str:
    """Legacy stub — JS now handles rendering."""
    return ""

def _render_hero(p: SurfaceProduct) -> str:
    """Legacy stub — JS now handles rendering."""
    return ""
