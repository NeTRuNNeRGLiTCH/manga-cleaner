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
* English (``en.json``) is the source of truth and the recovery language. Verified
  secondary catalogs are complete, so normal startup loads only the selected one.
* Language files are looked up in two places; the user folder replaces the bundle:
    1. bundled : <bundle>/locales/*.json      (shipped inside the .exe)
    2. user    : <exe folder>/locales/*.json  (community / custom translations)
* Non-English catalogs must match the verification hashes in ``index.json``. If
  validation fails, English is loaded for recovery and a startup warning is shown.
* The language is applied at startup (restart to change it).
* The file name is the language code (``es.json``, ``pt-BR.json``); the display
  name comes from the ``meta.language_name`` key inside the file.
"""

import hashlib
import json
import logging
import os
import re

log = logging.getLogger("MangaCleaner")

FALLBACK_LANG = "en"
SETTINGS_KEY = "language"
AUTO = "auto"
CATALOG_ROLE_KEY = "meta.catalog_role"
TRANSLATION_STATUS_KEY = "meta.translation_status"
TRANSLATION_SOURCE_HASH_KEY = "meta.translation_source_sha256"
VERIFIED_STATUS = "Verified and approved for use in Manga Cleaner Studio"

_NON_CATALOG_SUFFIXES = (".sources.json",)
_NON_CATALOG_NAMES = {"index.json"}

_state = {
    "bundled_dir": None,
    "user_dir": None,
    "settings_path": None,
    "lang": FALLBACK_LANG,
    "catalog": {},
    "fallback": {},
    "catalog_warning": None,
    "index_cache": {},
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


def _unique_folders(*folders):
    """Return non-empty locale folders once, preserving the requested precedence."""
    result, seen = [], set()
    for folder in folders:
        if not folder:
            continue
        key = os.path.normcase(os.path.abspath(folder))
        if key not in seen:
            seen.add(key)
            result.append(folder)
    return result


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
    """Load one locale catalog, preferring the user catalog over the bundled copy."""
    path = _find_language_path(code)
    return _load_file(path) if path else {}


def _find_language_path(code):
    """Find a locale file using user-over-bundled precedence."""
    key = _norm(code)
    for folder in _unique_folders(_state["user_dir"], _state["bundled_dir"]):
        entry = _scan_dir(folder).get(key)
        if entry:
            return entry[1]
    return None


def _canonical_hash(data):
    """Hash parsed JSON independently of formatting and line endings."""
    payload = json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _source_fingerprint(path):
    """Hash English catalog bytes without parsing them or retaining their contents."""
    try:
        with open(path, "rb") as f:
            payload = f.read()
    except OSError:
        return None
    if payload.startswith(b"\xef\xbb\xbf"):
        payload = payload[3:]
    payload = payload.replace(b"\r\n", b"\n")
    return hashlib.sha256(payload).hexdigest()


def _read_index_manifest(folder):
    """Read the small locale manifest without loading any translation catalogs."""
    if not folder or not os.path.isdir(folder):
        return {}
    cache_key = os.path.normcase(os.path.abspath(folder))
    if cache_key in _state["index_cache"]:
        return _state["index_cache"][cache_key]
    try:
        with open(os.path.join(folder, "index.json"), "r", encoding="utf-8-sig") as f:
            data = json.load(f)
    except (OSError, ValueError):
        data = {}
    if not isinstance(data, dict):
        data = {}
    _state["index_cache"][cache_key] = data
    return data


def _verification_entry(code, catalog_path):
    """Return whether a locale file matches its approved source and catalog hashes."""
    manifest = _read_index_manifest(os.path.dirname(catalog_path))
    languages = manifest.get("languages")
    if not isinstance(languages, dict):
        return False, "the locale index is missing or invalid", {}
    entry = next(
        (value for name, value in languages.items()
         if _norm(name) == _norm(code) and isinstance(value, dict)),
        None,
    )
    if entry is None:
        return False, "the language is not listed in locales/index.json", {}

    catalog = _load_file(catalog_path)
    source_hash = manifest.get("source_catalog_sha256")
    english_path = _find_language_path(FALLBACK_LANG)
    if not english_path or _source_fingerprint(english_path) != source_hash:
        return False, "the English source catalog changed or is unavailable", catalog
    if not source_hash or entry.get("verified_source_sha256") != source_hash:
        return False, "the catalog was not verified against the current source version", catalog
    if catalog.get(TRANSLATION_STATUS_KEY) != VERIFIED_STATUS:
        return False, "the catalog is missing its verification marker", catalog
    if catalog.get(TRANSLATION_SOURCE_HASH_KEY) != source_hash:
        return False, "the catalog source fingerprint is missing or outdated", catalog
    if entry.get("catalog_sha256") != _canonical_hash(catalog):
        return False, "the catalog changed after it was verified", catalog
    return True, "", catalog


def _load_language_index(folder):
    """Read display names from the small index instead of parsing every catalog."""
    if not folder or not os.path.isdir(folder):
        return {}
    path = os.path.join(folder, "index.json")
    data = _read_index_manifest(folder)
    if not data:
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
    """Return indexed languages without opening their translation catalogs."""
    catalog_files = {}
    for folder in _unique_folders(_state["bundled_dir"], _state["user_dir"]):
        for norm, (code, path) in _scan_dir(folder).items():
            catalog_files[norm] = (code, path)  # user dir overrides the entry

    metadata = {}
    for folder in _unique_folders(_state["bundled_dir"], _state["user_dir"]):
        for norm, (code, english_name, native_name) in _load_language_index(folder).items():
            if norm in catalog_files:
                catalog_code = catalog_files[norm][0]
                metadata[norm] = (catalog_code, english_name, native_name)

    # Legacy folders without an index remain discoverable by filename only.
    # Never parse every catalog just to populate the language selector.
    for norm, (code, _path) in catalog_files.items():
        metadata.setdefault(norm, (code, code, code))

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


def has_english_source_catalog():
    """Check whether an English source catalog file exists without loading it."""
    for folder in _unique_folders(_state["bundled_dir"], _state["user_dir"]):
        if _scan_dir(folder).get(FALLBACK_LANG):
            return True
    return False


def catalog_warning():
    """Return startup details when the requested locale failed verification."""
    return _state["catalog_warning"]


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
    """Load English or one approved locale; unverified catalogs recover to English."""
    _state["fallback"] = {}
    _state["catalog_warning"] = None
    if _norm(code) == FALLBACK_LANG:
        _state["lang"] = FALLBACK_LANG
        _state["catalog"] = _load_language(FALLBACK_LANG)
    else:
        path = _find_language_path(code)
        if path:
            approved, reason, catalog = _verification_entry(code, path)
        else:
            approved, reason, catalog = False, "the translation catalog file is missing", {}
        if approved and catalog:
            _state["lang"] = code
            _state["catalog"] = catalog
        else:
            log.warning(f"i18n: language '{code}' is not verified ({reason}); using English")
            _state["catalog_warning"] = {"language": code, "reason": reason}
            _state["lang"] = FALLBACK_LANG
            _state["catalog"] = _load_language(FALLBACK_LANG)
            _state["fallback"] = _state["catalog"]
    _state["missing_logged"] = set()
    return _state["lang"]


def init(bundled_dir, user_dir=None, settings_path=None, system_locale=None, language=None):
    """Call once at startup, after Paths.initialize() and before creating windows.

    language: force a code (tests / CLI). Otherwise: saved setting -> system locale -> English.
    """
    _state["bundled_dir"] = bundled_dir
    _state["user_dir"] = user_dir
    _state["settings_path"] = settings_path
    _state["index_cache"] = {}
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
    """Translate `key`; use English only during recovery, then the key itself."""
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
