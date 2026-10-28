"""
Manga Cleaner - lightweight i18n (v3.4.0)

Pure Python (no Qt, no extra dependencies), so it can be imported anywhere
and unit-tested without a GUI.

Usage
-----
    from src.utils.i18n import tr

    QPushButton(tr("common.cancel"))
    QLabel(tr("translator.injected_lines", n=12))      # "Injected {n} lines"

Rules
-----
* Catalogs are flat JSON files: {"key": "text with {placeholders}"}.
* English (``en.json``) is the source of truth and the fallback:
  language -> English -> the key itself (never raises, never shows empty text).
* Language files are looked up in two places; the user folder wins per key:
    1. bundled : <bundle>/locales/*.json      (shipped inside the .exe)
    2. user    : <exe folder>/locales/*.json  (community / custom translations)
  A user file may be partial: missing keys fall back to the bundled file, then English.
* The language is applied at startup (restart to change it).
* The file name is the language code (``es.json``, ``pt-BR.json``); the display
  name comes from the ``meta.language_name`` key inside the file.
"""

import json
import logging
import os
import re

log = logging.getLogger("MangaCleaner")

FALLBACK_LANG = "en"
META_PREFIX = "meta."
SETTINGS_KEY = "language"
AUTO = "auto"

_NON_CATALOG_SUFFIXES = (".sources.json",)
_NON_CATALOG_NAMES = {"index.json"}

_state = {
    "bundled_dir": None,
    "user_dir": None,
    "settings_path": None,
    "lang": FALLBACK_LANG,
    "catalog": {},
    "fallback": {},
    "missing_logged": set(),
}


# ----------------------------------------------------------------------------
# File helpers
# ----------------------------------------------------------------------------
def _norm(code):
    return (code or "").strip().replace("_", "-").lower()


def _is_catalog_file(name):
    low = name.lower()
    return (
        low.endswith(".json")
        and low not in _NON_CATALOG_NAMES
        and not low.endswith(_NON_CATALOG_SUFFIXES)
    )


def _scan_dir(folder):
    """Return {normalized_code: (original_code, path)} for catalog files in folder."""
    found = {}
    if not folder or not os.path.isdir(folder):
        return found
    try:
        names = sorted(os.listdir(folder))
    except OSError as e:
        log.warning(f"i18n: cannot list {folder}: {e}")
        return found
    for name in names:
        if _is_catalog_file(name):
            code = name[:-5]
            found[_norm(code)] = (code, os.path.join(folder, name))
    return found


def _load_file(path):
    """Load one catalog. Bad file -> {} (logged). Non-string values are dropped."""
    try:
        with open(path, "r", encoding="utf-8-sig") as f:
            data = json.load(f)
    except (OSError, ValueError) as e:
        log.warning(f"i18n: ignoring {path}: {e}")
        return {}
    if not isinstance(data, dict):
        log.warning(f"i18n: ignoring {path}: top level must be an object")
        return {}
    clean = {}
    for k, v in data.items():
        if isinstance(k, str) and isinstance(v, str):
            clean[k] = v
        else:
            log.warning(f"i18n: {os.path.basename(path)}: skipped non-string entry {k!r}")
    return clean


def _load_language(code):
    """Bundled file first, then user file on top (per-key override)."""
    key = _norm(code)
    merged = {}
    for folder in (_state["bundled_dir"], _state["user_dir"]):
        entry = _scan_dir(folder).get(key)
        if entry:
            merged.update(_load_file(entry[1]))
    return merged


def _load_language_index(folder):
    """Read display names from the small index instead of parsing every catalog."""
    if not folder or not os.path.isdir(folder):
        return {}
    path = os.path.join(folder, "index.json")
    try:
        with open(path, "r", encoding="utf-8-sig") as f:
            data = json.load(f)
    except FileNotFoundError:
        return {}
    except (OSError, ValueError) as e:
        log.warning(f"i18n: ignoring language index {path}: {e}")
        return {}

    languages = data.get("languages") if isinstance(data, dict) else None
    if not isinstance(languages, dict):
        log.warning(f"i18n: ignoring language index {path}: 'languages' must be an object")
        return {}

    found = {}
    for code, names in languages.items():
        if not isinstance(code, str) or not isinstance(names, dict):
            continue
        english_name = names.get("english_name")
        native_name = names.get("native_name")
        if not isinstance(english_name, str) or not english_name.strip():
            continue
        if not isinstance(native_name, str) or not native_name.strip():
            continue
        found[_norm(code)] = (code, english_name.strip(), native_name.strip())
    return found


# ----------------------------------------------------------------------------
# Settings (tiny JSON next to the other cache files; keeps unrelated keys)
# ----------------------------------------------------------------------------
def _read_settings():
    path = _state["settings_path"]
    if not path or not os.path.isfile(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def get_saved_language():
    """Saved choice: a language code, 'auto', or None if never chosen."""
    value = _read_settings().get(SETTINGS_KEY)
    return value if isinstance(value, str) and value.strip() else None


def save_language(code):
    """Persist the choice ('auto' or a code). Applied on next start."""
    path = _state["settings_path"]
    if not path:
        return False
    data = _read_settings()
    data[SETTINGS_KEY] = code
    try:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
        return True
    except OSError as e:
        log.warning(f"i18n: could not save language setting: {e}")
        return False


# ----------------------------------------------------------------------------
# Public API
# ----------------------------------------------------------------------------
def available_languages():
    """[(code, display_name)] - English first, then alphabetical by English display name."""
    catalog_files = {}
    for folder in (_state["bundled_dir"], _state["user_dir"]):
        for norm, (code, path) in _scan_dir(folder).items():
            catalog_files[norm] = (code, path)  # user dir overrides the entry

    metadata = {}
    for folder in (_state["bundled_dir"], _state["user_dir"]):
        for norm, (code, english_name, native_name) in _load_language_index(folder).items():
            if norm in catalog_files:
                catalog_code = catalog_files[norm][0]
                metadata[norm] = (catalog_code, english_name, native_name)

    # Backward compatibility for old/custom locale folders without an index.
    if not metadata:
        for norm, (code, _path) in catalog_files.items():
            catalog = _load_language(code)
            native_name = catalog.get(META_PREFIX + "language_name") or code
            english_name = catalog.get(META_PREFIX + "language_name_english")
            if not english_name and norm == FALLBACK_LANG:
                english_name = "English"
            metadata[norm] = (code, english_name or native_name, native_name)

    result = []
    for norm, (code, english_name, native_name) in metadata.items():
        if english_name and english_name.casefold() != native_name.casefold():
            name = f"{english_name} ({native_name})"
        else:
            name = native_name
        result.append((code, name))
    result.sort(key=lambda t: (_norm(t[0]) != FALLBACK_LANG, t[1].lower()))
    return result


def current_language():
    return _state["lang"]


def resolve_language(requested, system_locale=None):
    """Pick the best available code for a request.

    requested: explicit code, 'auto', or None.
    system_locale: e.g. 'es_AR' (only used for auto / None).
    Returns an existing code, or 'en'.
    """
    available = {_norm(c): c for c, _ in available_languages()}
    if requested and _norm(requested) != AUTO:
        return available.get(_norm(requested), FALLBACK_LANG)
    loc = _norm(system_locale)
    if loc:
        for candidate in (loc, loc.split("-")[0]):
            if candidate in available:
                return available[candidate]
    return FALLBACK_LANG


def set_language(code):
    """Load a language now (used by init and by tests). Unknown code -> English."""
    _state["fallback"] = _load_language(FALLBACK_LANG)
    if _norm(code) == FALLBACK_LANG:
        _state["lang"] = FALLBACK_LANG
        _state["catalog"] = _state["fallback"]
    else:
        catalog = _load_language(code)
        if catalog:
            _state["lang"] = code
            _state["catalog"] = catalog
        else:
            log.warning(f"i18n: language '{code}' not found, using English")
            _state["lang"] = FALLBACK_LANG
            _state["catalog"] = _state["fallback"]
    _state["missing_logged"] = set()
    return _state["lang"]


def init(bundled_dir, user_dir=None, settings_path=None, system_locale=None, language=None):
    """Call once at startup, after Paths.initialize() and before creating windows.

    language: force a code (tests / CLI). Otherwise: saved setting -> system locale -> English.
    """
    _state["bundled_dir"] = bundled_dir
    _state["user_dir"] = user_dir
    _state["settings_path"] = settings_path
    requested = language if language is not None else get_saved_language()
    chosen = resolve_language(requested, system_locale)
    set_language(chosen)
    log.info(f"i18n: language = {_state['lang']} ({len(_state['catalog'])} keys)")
    return _state["lang"]


class _SafeDict(dict):
    def __missing__(self, key):
        return "{" + key + "}"


def _format(text, kwargs):
    if not kwargs:
        return text
    try:
        return text.format_map(_SafeDict(kwargs))
    except (ValueError, IndexError, KeyError, AttributeError):
        # Broken placeholder in a community file: plain replace, never crash the UI.
        for k, v in kwargs.items():
            text = re.sub(r"\{" + re.escape(k) + r"(?:[:!][^}]*)?\}", lambda _m, v=v: str(v), text)
        return text


def tr(key, **kwargs):
    """Translate `key`. Falls back to English, then to the key itself."""
    text = _state["catalog"].get(key)
    if text is None:
        text = _state["fallback"].get(key)
        if text is None:
            if key not in _state["missing_logged"]:
                _state["missing_logged"].add(key)
                log.warning(f"i18n: missing key '{key}'")
            text = key
    return _format(text, kwargs)


def tr_label(name):
    """Visible label for an internal ID (tool/category names such as "BRUSH").

    Looks up "label.<id lowercase>"; if there is none, shows the ID unchanged
    (no warning). The ID itself must stay untouched for logic/dict keys.
    """
    key = "label." + str(name).strip().lower()
    text = _state["catalog"].get(key)
    if text is None:
        text = _state["fallback"].get(key)
    return text if text is not None else str(name)
