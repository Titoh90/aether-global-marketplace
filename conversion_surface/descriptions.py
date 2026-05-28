"""
descriptions.py — Shared product description translations for EN/ES/FR.

Single source of truth for category-to-marketing-text mappings.
Import _DESCRIPTIONS and use _product_description() to get
{"en": ..., "es": ..., "fr": ...} for any product.
"""

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
    "outdoors": {"es": "Aventura y aire libre con el mejor equipo", "fr": "Aventure et plein air avec le meilleur équipement"},
    "pet supplies": {"es": "Todo para el cuidado de tu mascota", "fr": "Tout pour le bien-être de votre animal"},
    "pets": {"es": "Todo para el cuidado de tu mascota", "fr": "Tout pour le bien-être de votre animal"},
    "baby": {"es": "Lo mejor para tu bebé y su desarrollo", "fr": "Le meilleur pour votre bébé et son développement"},
    "tools": {"es": "Herramientas profesionales para cada proyecto", "fr": "Outils professionnels pour chaque projet"},
    "fitness": {"es": "Equipo fitness para alcanzar tus metas", "fr": "Équipement fitness pour atteindre vos objectifs"},
    "travel": {"es": "Viaja cómodo con accesorios inteligentes", "fr": "Voyagez confortablement avec des accessoires intelligents"},
    "grocery": {"es": "Alimentos y productos gourmet seleccionados", "fr": "Aliments et produits gourmet sélectionnés"},
    "music": {"es": "Instrumentos y equipos de audio profesional", "fr": "Instruments et équipements audio professionnels"},
    "musical instruments": {"es": "Instrumentos y equipos de audio profesional", "fr": "Instruments et équipements audio professionnels"},
    "general": {"es": "Producto seleccionado por su calidad", "fr": "Produit sélectionné pour sa qualité"},
}


def product_description(desc_en: str, category: str = "") -> dict[str, str]:
    """Build {"en": ..., "es": ..., "fr": ...} with real translations.

    Strategy:
    1. Match desc_en (archetype label) or category against _DESCRIPTIONS (case-insensitive).
    2. Fall back to auto-generated text: "Premium {category} products" pattern.
    """
    key = desc_en.lower().strip()
    if key in _DESCRIPTIONS:
        return {"en": desc_en, "es": _DESCRIPTIONS[key]["es"], "fr": _DESCRIPTIONS[key]["fr"]}

    cat_key = category.lower().strip()
    if cat_key in _DESCRIPTIONS:
        return {"en": desc_en, "es": _DESCRIPTIONS[cat_key]["es"], "fr": _DESCRIPTIONS[cat_key]["fr"]}

    cat_title = category.title() if category else desc_en
    return {
        "en": desc_en,
        "es": f"{cat_title} — producto premium seleccionado",
        "fr": f"{cat_title} — produit premium sélectionné",
    }
