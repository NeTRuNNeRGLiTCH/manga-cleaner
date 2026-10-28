"""Run from the repo root:  python -m unittest tests.test_i18n -v"""

import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.utils import i18n  # noqa: E402


def write(folder, name, data):
    os.makedirs(folder, exist_ok=True)
    with open(os.path.join(folder, name), "w", encoding="utf-8") as f:
        if isinstance(data, str):
            f.write(data)
        else:
            json.dump(data, f, ensure_ascii=False)


EN = {
    "meta.language_name": "English",
    "common.cancel": "Cancel",
    "common.ok": "OK",
    "t.lines": "Injected {n} lines into {page}",
    "t.braces": "Use {{name}} literally",
}
ES = {
    "meta.language_name": "Español",
    "common.cancel": "Cancelar",
    "t.lines": "Se inyectaron {n} líneas en {page}",
}


class I18nTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.bundled = os.path.join(self.tmp.name, "bundle", "locales")
        self.user = os.path.join(self.tmp.name, "exe", "locales")
        self.settings = os.path.join(self.tmp.name, "cache", "settings.json")
        write(self.bundled, "en.json", EN)
        write(self.bundled, "es.json", ES)
        write(self.bundled, "en.sources.json", {"x": ["a.py:1"]})

    def tearDown(self):
        self.tmp.cleanup()

    def init(self, **kw):
        return i18n.init(self.bundled, self.user, self.settings, **kw)

    def test_english_default(self):
        self.assertEqual(self.init(), "en")
        self.assertEqual(i18n.tr("common.cancel"), "Cancel")

    def test_spanish_with_fallback_to_english(self):
        self.init(language="es")
        self.assertEqual(i18n.tr("common.cancel"), "Cancelar")
        self.assertEqual(i18n.tr("common.ok"), "OK")  # missing in es -> English

    def test_missing_key_returns_key(self):
        self.init()
        self.assertEqual(i18n.tr("nope.nothing"), "nope.nothing")

    def test_placeholders(self):
        self.init(language="es")
        self.assertEqual(i18n.tr("t.lines", n=3, page="001.jpg"), "Se inyectaron 3 líneas en 001.jpg")

    def test_missing_kwarg_does_not_crash(self):
        self.init()
        self.assertEqual(i18n.tr("t.lines", n=3), "Injected 3 lines into {page}")

    def test_braces_untouched_without_kwargs(self):
        self.init()
        self.assertEqual(i18n.tr("t.braces"), "Use {{name}} literally")

    def test_bad_placeholder_in_community_file(self):
        write(self.user, "es.json", {"t.lines": "Roto {n:} {0} {"})
        self.init(language="es")
        self.assertIn("3", i18n.tr("t.lines", n=3))

    def test_user_overrides_per_key(self):
        write(self.user, "es.json", {"common.cancel": "Anular"})
        self.init(language="es")
        self.assertEqual(i18n.tr("common.cancel"), "Anular")
        self.assertEqual(i18n.tr("t.lines", n=1, page="p"), "Se inyectaron 1 líneas en p")

    def test_user_only_language(self):
        write(self.user, "pt-BR.json", {"meta.language_name": "Português (Brasil)", "common.cancel": "Cancelar!"})
        self.assertEqual(self.init(language="PT-br"), "pt-BR")
        self.assertEqual(i18n.tr("common.cancel"), "Cancelar!")

    def test_available_languages(self):
        write(self.user, "pt-BR.json", {"meta.language_name": "Português"})
        self.init()
        langs = i18n.available_languages()
        self.assertEqual(langs[0], ("en", "English"))
        self.assertEqual([c for c, _ in langs], ["en", "es", "pt-BR"])  # sources.json excluded

    def test_corrupt_json_ignored(self):
        write(self.user, "es.json", "{ not json")
        self.init(language="es")
        self.assertEqual(i18n.tr("common.cancel"), "Cancelar")  # bundled still loads

    def test_non_string_values_dropped(self):
        write(self.user, "es.json", {"common.cancel": 123, "common.ok": "Vale"})
        self.init(language="es")
        self.assertEqual(i18n.tr("common.cancel"), "Cancelar")
        self.assertEqual(i18n.tr("common.ok"), "Vale")

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
        write(self.bundled, "en.json", dict(EN, **{"label.brush": "BRUSH"}))
        write(self.bundled, "es.json", dict(ES, **{"label.brush": "PINCEL"}))
        self.init(language="es")
        self.assertEqual(i18n.tr_label("BRUSH"), "PINCEL")
        self.assertEqual(i18n.tr_label("PICKER"), "PICKER")  # no key -> the ID, silently

    def test_works_without_any_folder(self):
        i18n.init(os.path.join(self.tmp.name, "nope"), None, None)
        self.assertEqual(i18n.tr("anything"), "anything")


class CheckLocalesTests(unittest.TestCase):
    def test_validator(self):
        sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "tools")))
        import check_locales

        ref = EN
        good = dict(ES, **{"common.ok": "Vale", "t.braces": "Usa {{name}}"})
        with tempfile.TemporaryDirectory() as d:
            write(d, "en.json", EN)
            write(d, "bad.json", {"meta.language_name": "Bad", "t.lines": "Solo {n}", "ghost.key": "x"})
            write(d, "ok.json", good)
            e1, w1 = check_locales.check_file(os.path.join(d, "bad.json"), ref, False)
            e2, w2 = check_locales.check_file(os.path.join(d, "ok.json"), ref, False)
            self.assertTrue(any("placeholders differ" in m for m in e1))
            self.assertTrue(any("ghost.key" in m for m in e1))
            self.assertEqual(e2, [])
            self.assertEqual(check_locales.main(["--locales", d]), 1)
            os.remove(os.path.join(d, "bad.json"))
            self.assertEqual(check_locales.main(["--locales", d]), 0)


if __name__ == "__main__":
    unittest.main()