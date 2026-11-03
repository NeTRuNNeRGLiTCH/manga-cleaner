"""Run from the repo root: python -m unittest tests.test_i18n -v"""

import json
import os
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.utils import i18n  # noqa: E402


SOURCE_ROLE = "Original source catalog and primary language"
VERIFIED_STATUS = "Verified and approved for use in Manga Cleaner Studio"
SOURCE = {
    "meta.language_name": "English",
    "meta.language_name_english": "English",
    "meta.catalog_role": SOURCE_ROLE,
    "common.cancel": "Cancel",
    "common.ok": "OK",
    "t.lines": "Injected {n} lines into {page}",
    "t.braces": "Use {{name}} literally",
    "label.brush": "BRUSH",
}
SPANISH = {
    "meta.language_name": "Español",
    "meta.language_name_english": "Spanish",
    "common.cancel": "Cancelar",
    "common.ok": "Vale",
    "t.lines": "Se inyectaron {n} líneas en {page}",
    "t.braces": "Usa {{name}} literalmente",
    "label.brush": "PINCEL",
}


def canonical_hash(data):
    import hashlib
    payload = json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def source_fingerprint(path):
    import hashlib
    with open(path, "rb") as f:
        payload = f.read()
    if payload.startswith(b"\xef\xbb\xbf"):
        payload = payload[3:]
    return hashlib.sha256(payload.replace(b"\r\n", b"\n")).hexdigest()


def write(folder, name, data):
    os.makedirs(folder, exist_ok=True)
    with open(os.path.join(folder, name), "w", encoding="utf-8") as f:
        if isinstance(data, str):
            f.write(data)
        else:
            json.dump(data, f, ensure_ascii=False, indent=2)


def approved_catalog(data, source_hash):
    result = dict(data)
    result["meta.translation_status"] = VERIFIED_STATUS
    result["meta.translation_source_sha256"] = source_hash
    return result


class I18nTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.bundled = os.path.join(self.tmp.name, "bundle", "locales")
        self.user = os.path.join(self.tmp.name, "exe", "locales")
        self.settings = os.path.join(self.tmp.name, "cache", "settings.json")
        self.source = dict(SOURCE)
        write(self.bundled, "en.json", self.source)
        self.source_hash = source_fingerprint(os.path.join(self.bundled, "en.json"))
        self.spanish = approved_catalog(SPANISH, self.source_hash)
        write(self.bundled, "es.json", self.spanish)
        write(self.bundled, "en.sources.json", {"x": ["a.py:1"]})
        write(self.bundled, "index.json", {
            "schema_version": 1,
            "source_catalog_sha256": self.source_hash,
            "languages": {
                "en": {"english_name": "English", "native_name": "English"},
                "es": {
                    "english_name": "Spanish",
                    "native_name": "Español",
                    "verified_source_sha256": self.source_hash,
                    "catalog_sha256": canonical_hash(self.spanish),
                },
            },
        })

    def tearDown(self):
        self.tmp.cleanup()

    def init(self, **kw):
        return i18n.init(self.bundled, self.user, self.settings, **kw)

    def write_user_catalog(self, code, data, include_index=True):
        catalog = approved_catalog(data, self.source_hash)
        write(self.user, f"{code}.json", catalog)
        if include_index:
            write(self.user, "index.json", {
                "schema_version": 1,
                "source_catalog_sha256": self.source_hash,
                "languages": {
                    code: {
                        "english_name": data.get("meta.language_name_english", code),
                        "native_name": data.get("meta.language_name", code),
                        "verified_source_sha256": self.source_hash,
                        "catalog_sha256": canonical_hash(catalog),
                    },
                },
            })
        return catalog

    def test_english_default(self):
        self.assertEqual(self.init(), "en")
        self.assertEqual(i18n.tr("common.cancel"), "Cancel")

    def test_approved_spanish_uses_its_complete_catalog(self):
        self.assertEqual(self.init(language="es"), "es")
        self.assertEqual(i18n.tr("common.cancel"), "Cancelar")
        self.assertEqual(i18n.tr("common.ok"), "Vale")

    def test_unverified_catalog_recovers_to_english_with_warning(self):
        write(self.user, "es.json", SPANISH)  # no marker or current fingerprint
        self.assertEqual(self.init(language="es"), "en")
        self.assertEqual(i18n.tr("common.cancel"), "Cancel")
        self.assertIn("locale index", i18n.catalog_warning()["reason"])

    def test_catalog_changed_after_approval_recovers_to_english(self):
        changed = dict(self.spanish)
        changed["common.cancel"] = "Anular"
        write(self.bundled, "es.json", changed)
        self.assertEqual(self.init(language="es"), "en")
        self.assertIn("changed after it was verified", i18n.catalog_warning()["reason"])

    def test_stale_manifest_source_fingerprint_recovers_to_english(self):
        with open(os.path.join(self.bundled, "index.json"), encoding="utf-8") as f:
            manifest = json.load(f)
        manifest["source_catalog_sha256"] = "new-source-version"
        write(self.bundled, "index.json", manifest)
        self.assertEqual(self.init(language="es"), "en")
        self.assertIn("English source catalog changed", i18n.catalog_warning()["reason"])

    def test_selected_language_parses_only_its_translation_catalog(self):
        original = i18n._load_file
        loaded = []

        def track(path):
            loaded.append(os.path.basename(path))
            return original(path)

        with patch.object(i18n, "_load_file", side_effect=track):
            self.init(language="es")
        self.assertEqual(loaded, ["es.json"])

    def test_editing_english_source_invalidates_existing_approval(self):
        changed_source = dict(self.source)
        changed_source["common.ok"] = "Continue"
        write(self.bundled, "en.json", changed_source)
        self.assertEqual(self.init(language="es"), "en")
        self.assertIn("source catalog changed", i18n.catalog_warning()["reason"])

    def test_missing_key_returns_key_instead_of_loading_english_fallback(self):
        self.init(language="es")
        self.assertEqual(i18n.tr("missing.key"), "missing.key")

    def test_placeholders(self):
        self.init(language="es")
        self.assertEqual(
            i18n.tr("t.lines", n=3, page="001.jpg"),
            "Se inyectaron 3 líneas en 001.jpg",
        )

    def test_braces_untouched_without_kwargs(self):
        self.init(language="es")
        self.assertEqual(i18n.tr("t.braces"), "Usa {{name}} literalmente")

    def test_available_languages_uses_index_without_loading_catalogs(self):
        i18n.init(self.bundled, self.user, self.settings, language="en")
        with patch.object(i18n, "_load_file", side_effect=AssertionError("catalog read")):
            self.assertEqual(i18n.available_languages(), [("en", "English"), ("es", "Spanish (Español)")])

    def test_user_catalog_replaces_bundled_and_must_be_approved(self):
        write(self.user, "es.json", {"meta.language_name": "Español", "common.cancel": "Anular"})
        self.assertEqual(self.init(language="es"), "en")
        self.assertIn("locale index", i18n.catalog_warning()["reason"])

    def test_approved_user_only_language(self):
        portuguese = dict(SPANISH)
        portuguese.update({
            "meta.language_name": "Português (Brasil)",
            "meta.language_name_english": "Portuguese (Brazil)",
            "common.cancel": "Cancelar!",
        })
        self.write_user_catalog("pt-BR", portuguese)
        self.assertEqual(self.init(language="PT-br"), "pt-BR")
        self.assertEqual(i18n.tr("common.cancel"), "Cancelar!")

    def test_available_languages(self):
        write(self.user, "pt-BR.json", {"meta.language_name": "Português"})
        self.init()
        langs = i18n.available_languages()
        self.assertEqual(langs[0], ("en", "English"))
        self.assertEqual(set(c for c, _ in langs), {"en", "es", "pt-BR"})

    def test_unknown_language_falls_back(self):
        self.assertEqual(self.init(language="xx"), "en")

    def test_system_locale_auto(self):
        self.assertEqual(self.init(system_locale="es_AR"), "es")
        self.assertEqual(self.init(system_locale="fr_FR"), "en")

    def test_saved_setting_beats_system_locale(self):
        i18n.init(self.bundled, self.user, self.settings)
        self.assertTrue(i18n.save_language("en"))
        self.assertEqual(self.init(system_locale="es_AR"), "en")
        i18n.save_language("auto")
        self.assertEqual(self.init(system_locale="es_AR"), "es")

    def test_save_keeps_other_settings(self):
        write(os.path.dirname(self.settings), "settings.json", {"other": 1})
        i18n.init(self.bundled, self.user, self.settings)
        i18n.save_language("es")
        with open(self.settings, encoding="utf-8") as f:
            self.assertEqual(json.load(f), {"other": 1, "language": "es"})

    def test_tr_label_keeps_id_and_translates_label(self):
        self.init(language="es")
        self.assertEqual(i18n.tr_label("BRUSH"), "PINCEL")
        self.assertEqual(i18n.tr_label("PICKER"), "PICKER")

    def test_english_catalog_presence_check(self):
        self.init()
        self.assertTrue(i18n.has_english_source_catalog())
        os.remove(os.path.join(self.bundled, "en.json"))
        self.assertFalse(i18n.has_english_source_catalog())

    def test_works_without_any_folder(self):
        i18n.init(os.path.join(self.tmp.name, "nope"), None, None)
        self.assertEqual(i18n.tr("anything"), "anything")


class CheckLocalesTests(unittest.TestCase):
    def test_key_placeholders_and_verification_metadata_are_excluded(self):
        sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "tools")))
        import check_locales

        ref = dict(SOURCE)
        good = dict(SPANISH)
        good["meta.translation_status"] = VERIFIED_STATUS
        good["meta.translation_source_sha256"] = "fingerprint"
        bad = dict(good, **{"t.lines": "Solo {n}", "ghost.key": "x"})
        errors, warnings = check_locales.check_data(good, ref)
        self.assertEqual(errors, [])
        self.assertEqual(warnings, [])
        errors, _warnings = check_locales.check_data(bad, ref)
        self.assertTrue(any("placeholders differ" in message for message in errors))
        self.assertTrue(any("ghost.key" in message for message in errors))


if __name__ == "__main__":
    unittest.main()
