"""
mc_launcher/i18n.py — Merkezi dil yönetimi
"""

import os
import json
from mc_launcher.config import load_cfg

# Dizin yolları
LOCALES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "locales")

# Bellekteki dil sözlüğü önbelleği
_STRINGS = {}
_current_lang = "en"

def load_locale(lang_code: str) -> dict:
    """Belirtilen dil kodunun JSON dosyasını okur ve önbelleğe alır."""
    global _STRINGS
    if lang_code in _STRINGS and _STRINGS[lang_code]:
        return _STRINGS[lang_code]

    path = os.path.join(LOCALES_DIR, f"{lang_code}.json")
    try:
        if os.path.isfile(path):
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    _STRINGS[lang_code] = data
                    return data
    except Exception as e:
        print(f"[i18n] Error loading locale {lang_code}: {e}")
    
    _STRINGS[lang_code] = {}
    return {}

def init_i18n():
    """Varsayılan dili belirler ve temel dil dosyalarını yükler."""
    global _current_lang
    cfg = load_cfg()
    lang = cfg.get("language")
    if not lang:
        lang = "en"
        sys_lang = ""
        try:
            sys_lang = os.environ.get("LANG", "")
        except Exception:
            pass
        if not sys_lang:
            try:
                import locale
                sys_lang = (locale.getlocale()[0] or locale.getdefaultlocale()[0] or "")
            except Exception:
                pass
        
        if sys_lang:
            sys_lang = sys_lang.lower()
            if sys_lang.startswith("tr"):
                lang = "tr"
            elif sys_lang.startswith("de"):
                lang = "de"
            elif sys_lang.startswith("zh"):
                lang = "zh"
                
    _current_lang = lang
    # Temel dilleri önbelleğe yükle
    load_locale("en")
    load_locale("tr")
    if _current_lang not in ("en", "tr"):
        load_locale(_current_lang)

def get_current_lang():
    return _current_lang

def set_current_lang(code):
    global _current_lang
    if code in ("tr", "en", "de", "zh"):
        _current_lang = code
        load_locale(code)

def _t(key, **kwargs):
    """
    Belirtilen anahtar için çeviriyi döner.
    Gelişmiş Fallback Sistemi: Seçilen dil -> İngilizce -> Türkçe -> Anahtar
    """
    # Seçilen dilden oku
    text = _STRINGS.get(_current_lang, {}).get(key)
    # Bulamazsa İngilizceye bak
    if text is None:
        text = _STRINGS.get("en", {}).get(key)
    # Bulamazsa Türkçeye bak
    if text is None:
        text = _STRINGS.get("tr", {}).get(key)
    # Bulamazsa anahtarın kendisini kullan
    if text is None:
        text = key
    
    if kwargs:
        try:
            return text.format(**kwargs)
        except Exception:
            return text
    return text

# İlklendirmeyi yap
init_i18n()
