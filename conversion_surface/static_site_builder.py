"""
static_site_builder.py — Writes rendered HTML + assets + data + i18n to disk.

Compatible with GitHub Pages (no server-side code).
Default output: IMPERIO_ROOT/public/conversion_surface/

Multi-file output:
  index.html            — SPA shell
  assets/styles.css      — CSS stylesheet
  assets/app.js          — Client-side JS
  data/products.json     — Product data + categories
  i18n/en.json           — English translations
  i18n/es.json           — Spanish translations
  i18n/fr.json           — French translations
"""
from __future__ import annotations

import json
from pathlib import Path

from .schemas import HubSurface

_IMPERIO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT   = _IMPERIO_ROOT / "public" / "conversion_surface"

# ── i18n Translations (for i18n/*.json files) ─────────────────────────────────

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


# ── Product Description i18n ────────────────────────────────────────────────────

# Mapping: English archetype/category name → {es, fr} marketing descriptions.
# Keys are matched case-insensitively. Falls back to auto-generated text.
_DESCRIPTIONS: dict[str, dict[str, str]] = {
    "electronics": {"es": "Electrónica y tecnología premium", "fr": "Électronique et high-tech premium"},
    "beauty": {"es": "Belleza y cuidado personal de lujo", "fr": "Beauté et soins personnels de luxe"},
    "home": {"es": "Esenciales para el hogar y la cocina", "fr": "Indispensables pour la maison et la cuisine"},
    "fashion": {"es": "Moda y accesorios con estilo", "fr": "Mode et accessoires élégants"},
    "kitchen": {"es": "Innovación para tu cocina", "fr": "Innovation pour votre cuisine"},
    "sports": {"es": "Equipamiento deportivo de alto rendimiento", "fr": "Équipement sportif haute performance"},
    "office": {"es": "Productividad y ergonomía para tu oficina", "fr": "Productivité et ergonomie pour votre bureau"},
    "toys": {"es": "Juguetes y entretenimiento para todas las edades", "fr": "Jouets et divertissement pour tous les âges"},
    "garden": {"es": "Herramientas y decoración para exteriores", "fr": "Outils et décoration d'extérieur"},
    "automotive": {"es": "Accesorios y cuidado automotriz", "fr": "Accessoires et entretien automobile"},
    "health": {"es": "Salud y bienestar personal", "fr": "Santé et bien-être personnel"},
    "books": {"es": "Libros y conocimiento al mejor precio", "fr": "Livres et savoir au meilleur prix"},
    "general": {"es": "Producto seleccionado por su calidad", "fr": "Produit sélectionné pour sa qualité"},
}


def _product_description(desc_en: str, category: str = "") -> dict:
    """Build {"en": ..., "es": ..., "fr": ...} with real ES/FR translations."""
    key = desc_en.lower().strip()
    if key in _DESCRIPTIONS:
        return {"en": desc_en, "es": _DESCRIPTIONS[key]["es"], "fr": _DESCRIPTIONS[key]["fr"]}

    cat_key = category.lower().strip()
    if cat_key in _DESCRIPTIONS:
        return {"en": desc_en, "es": _DESCRIPTIONS[cat_key]["es"], "fr": _DESCRIPTIONS[cat_key]["fr"]}

    cat_title = category.title() if category else desc_en
    return {"en": desc_en, "es": f"{cat_title} — producto premium seleccionado", "fr": f"{cat_title} — produit premium sélectionné"}


def _product_tags(p) -> list:
    """Derive display tags from section and status."""
    tags = []
    if p.section == "hero":
        tags.append("bestseller")
    if p.section == "trending":
        tags.append("trending")
    if p.evergreen_status == "experimental":
        tags.append("limited")
    return tags


def _amazon_image_url(asin: str, size: str = "SL400", img_id: str = "AsinImage") -> str:
    if not asin:
        return ""
    return f"https://ws-na.amazon-adsystem.com/widgets/q?_encoding=UTF8&ASIN={asin}&Format=_{size}_&ID={img_id}&MarketPlace=US&ServiceVersion=20070822&WS=1"


def _build_carousel_image_urls(asin: str, primary_url: str) -> list:
    """Generate up to 3 image URLs for carousel slides using Amazon alternate image IDs."""
    urls = [primary_url] if primary_url else []
    if asin:
        for suffix in (".01", ".02"):
            alt = _amazon_image_url(asin, img_id=f"AsinImage{suffix}")
            if alt and alt not in urls:
                urls.append(alt)
    return urls


def build_static_site(
    surface: HubSurface,
    html: str,
    output_dir: Path | None = None,
) -> None:
    """
    Write index.html, assets/, data/, and i18n/ to output_dir.
    Creates output_dir and subdirectories if needed.
    """
    from .template_renderer import render_css, render_js

    out = Path(output_dir) if output_dir else DEFAULT_OUT

    # Subdirectories
    assets_dir = out / "assets"
    data_dir   = out / "data"
    i18n_dir   = out / "i18n"
    for d in (assets_dir, data_dir, i18n_dir):
        d.mkdir(parents=True, exist_ok=True)

    # ── index.html ───────────────────────────────────────────────────────
    (out / "index.html").write_text(html, encoding="utf-8")

    # ── assets/styles.css ────────────────────────────────────────────────
    (assets_dir / "styles.css").write_text(render_css(), encoding="utf-8")

    # ── assets/app.js ────────────────────────────────────────────────────
    (assets_dir / "app.js").write_text(render_js(), encoding="utf-8")

    # ── data/products.json ───────────────────────────────────────────────
    products_json = _build_enriched_products(surface)
    (data_dir / "products.json").write_text(
        json.dumps(products_json, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    # ── i18n/*.json ──────────────────────────────────────────────────────
    for lang in ("en", "es", "fr"):
        (i18n_dir / f"{lang}.json").write_text(
            json.dumps(_TRANSLATIONS.get(lang, {}), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )


def _build_enriched_products(surface: HubSurface) -> dict:
    """Build enriched product data matching the JS frontend schema."""
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
            "description": _product_description(desc_en, p.category),
            "tags": tags,
            "section": p.section,
            "type": ptype,
        })

    return {
        "generated_at": surface.generated_at,
        "categories": sorted(categories),
        "products": products_out,
    }
