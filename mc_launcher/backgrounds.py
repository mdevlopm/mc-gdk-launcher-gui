"""
mc_launcher/backgrounds.py — Oyna sayfası arka plan görselleri
"""

import os

from mc_launcher.config import SCRIPT_DIR

def get_backgrounds_dir() -> str:
    # Try dev directory
    dev_path = os.path.join(SCRIPT_DIR, "assets", "backgrounds")
    if os.path.isdir(dev_path):
        return dev_path
        
    # Fallback to standard packaged asset paths (Flatpak / system)
    system_paths = [
        "/app/share/mc-gdk-linux-launcher/assets/backgrounds",
        "/usr/share/mc-gdk-linux-launcher/assets/backgrounds",
        os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", "backgrounds")
    ]
    for sp in system_paths:
        if os.path.isdir(sp):
            return sp
    return dev_path

BACKGROUNDS_DIR = get_backgrounds_dir()

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
    if os.path.isfile(path):
        return path
    if bg_id == "default":
        # Generate a fallback default SVG in DATA_DIR to ensure a background always exists
        from mc_launcher.config import DATA_DIR
        fallback_path = os.path.join(DATA_DIR, "bg_fallback.svg")
        if not os.path.isfile(fallback_path):
            try:
                os.makedirs(DATA_DIR, exist_ok=True)
                with open(fallback_path, "w", encoding="utf-8") as f:
                    f.write(
                        '<svg xmlns="http://www.w3.org/2000/svg" width="800" height="600">'
                        '<rect width="100%" height="100%" fill="#1a1a1a"/>'
                        '<text x="50%" y="50%" dominant-baseline="middle" text-anchor="middle" '
                        'fill="#888888" font-family="sans-serif" font-size="20">Minecraft GDK Launcher</text>'
                        '</svg>'
                    )
            except Exception:
                pass
        if os.path.isfile(fallback_path):
            return fallback_path
    return None


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

