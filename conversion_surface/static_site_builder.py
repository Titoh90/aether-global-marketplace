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
from .descriptions import product_description

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


# Verified HD image IDs scraped from Amazon product pages (2026-05-28)
_HD_IMAGE_IDS: dict[str, list[str]] = {
    # Electronics (hiRes from colorImages/data-old-hires, 2026-05-29)
    "B0BDHWDR12": ["61f1YfTkTDL", "617I3mDGmTL", "51OoKCakCfL"],
    "B08KTZ8249": ["61P+vrvFZ9L", "51QCk82iGcL", "71d6+Ib9muL"],
    "B09XS7JWHH": ["61vJtKbAssL", "51QbrLdao0L", "81V1VCLb4oL"],
    "B09B8V1LZ3": ["61J2sQtBYDL", "71hNp8d9WvL", "71kDL97LTgL"],
    "B0DGJ4QQ5W": ["61QQUuYtWNL", "515oIieSmnL", "51yI62DIDmL"],
    # Beauty
    "B00TTD9BRC": ["61EidjXUBrL", "61-Ut3jOyyL", "91cwHnwUVEL"],
    # Home
    "B085DTZQNZ": ["718RbhzhVbL", "51B4ZbLNkOL", "512t1wfCMZL"],
    "B00FLYWNYQ": ["71Z401LjFFL", "91V5r8X2VgL", "81s0Ow2f6sL"],
    "B07FDJMC9Q": ["71+8uTMDRFL", "71wDCEfqZlL", "917o1KllOxL"],
    # Fashion
    "B0BXNRRN4Y": ["51+YqqbWIML", "513yiRQ4xwL", "51DXz1+d1mL"],
    "B0D9KM5SFR": ["61WTJldtvgL", "61yUyjhKsLL", "71YkzMrd6ZL"],
    "B0018OQQBE": ["41NgDv59BaL", "51WtUkd+bDL", "61ERUtlEPGL"],
    "B07PGR1XGZ": ["51wCTS-vHXL", "717P2-hKtoL", "61D4PlHJmGL"],
    "B097DD3G8G": ["71G65R-XC2L", "71dhTScRQgL", "61JRJjqnzSL"],
    "B017SN1OI8": ["818lBoWqXtL", "61V+is+XpkL", "61dh4J4f8ML"],
    "B087FD9DSV": ["61PGo56GK5S", "71a9nX2lPAS", "61IwyWsyO5S"],
    "B000VUCLII": ["61bIZNWiM8L"],
    "B06Y2ZW779": ["81j9yqr0R9L", "91+8pVW0mPL", "71Oe8HH5g2L"],
    "B06XW16QMS": ["618RD2rf+UL", "511cl6-GKkL", "51GEvpRPsUL"],
}


def _hd_image_url(image_id: str) -> str:
    return f"https://m.media-amazon.com/images/I/{image_id}._AC_SL1500_.jpg"


def _amazon_image_url(asin: str) -> str:
    if not asin:
        return ""
    ids = _HD_IMAGE_IDS.get(asin)
    if ids:
        return _hd_image_url(ids[0])
    return f"https://m.media-amazon.com/images/P/{asin}.01._SL1500_.jpg"


def _build_carousel_image_urls(asin: str, primary_url: str) -> list:
    """Up to 3 HD Amazon images. Uses verified I/ image IDs when available."""
    if not asin:
        return [primary_url] if primary_url else []
    ids = _HD_IMAGE_IDS.get(asin)
    if ids:
        return [_hd_image_url(img_id) for img_id in ids[:3]]
    return [primary_url] if primary_url else []


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

        # Build correct affiliate URL with /?tag= format
        raw_url = p.tracking_url or p.affiliate_url or ""
        # Normalize: ensure /dp/ASIN/?tag= not /dp/ASIN?tag=
        if "amazon.com/dp/" in raw_url and "?tag=" in raw_url and "/?tag=" not in raw_url:
            raw_url = raw_url.replace("?tag=", "/?tag=")

        # Extract English string for description, keep dict under descriptionI18n
        desc_result = product_description(desc_en, p.category)
        desc_str = desc_result.get("en", desc_en) if isinstance(desc_result, dict) else str(desc_result)

        products_out.append({
            "id": p.asin,
            "title": p.name,
            "price": p.price,
            "image": img_src,
            "imageUrls": image_urls,
            "rating": p.rating,
            "reviews": p.reviews,
            "category": p.category,
            "affiliateUrl": raw_url,
            "description": desc_str,
            "descriptionI18n": desc_result if isinstance(desc_result, dict) else {"en": desc_str, "es": desc_str, "fr": desc_str},
            "tags": tags,
            "section": p.section,
            "type": ptype,
        })

    return {
        "generated_at": surface.generated_at,
        "categories": sorted(categories),
        "products": products_out,
    }
