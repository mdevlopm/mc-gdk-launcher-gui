"""
mc_launcher/backgrounds.py — Oyna sayfası arka plan görselleri
"""

import os

from mc_launcher.config import SCRIPT_DIR

BACKGROUNDS_DIR = os.path.join(SCRIPT_DIR, "assets", "backgrounds")

# id → dosya adı (assets/backgrounds/ içinde)
BUILTIN_BACKGROUNDS = {
    "default": "bg_default.svg",
    "forest": "bg_forest.svg",
    "nether": "bg_nether.svg",
    "ocean": "bg_ocean.svg",
    "end": "bg_end.svg",
    "mountains": "bg_mountains.svg",
}

BACKGROUND_ORDER = ["default", "forest", "ocean", "mountains", "nether", "end", "custom"]

_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".svg", ".bmp"}


def list_background_ids():
    return list(BACKGROUND_ORDER)


def builtin_path(bg_id: str) -> str | None:
    filename = BUILTIN_BACKGROUNDS.get(bg_id)
    if not filename:
        return None
    path = os.path.join(BACKGROUNDS_DIR, filename)
    return path if os.path.isfile(path) else None


def resolve_background(bg_id: str, custom_path: str = "") -> str | None:
    """Seçilen arka plan için dosya yolunu döner."""
    if bg_id == "custom":
        custom_path = (custom_path or "").strip()
        if custom_path and os.path.isfile(custom_path):
            ext = os.path.splitext(custom_path)[1].lower()
            if ext in _IMAGE_EXTS:
                return custom_path
        return builtin_path("default")

    path = builtin_path(bg_id)
    if path:
        return path
    return builtin_path("default")
