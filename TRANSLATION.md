# UI Localization

## Purpose

Manga Cleaner uses a small localization layer so the application can display its interface in multiple languages. Keep localization separate from application logic: code refers to stable keys, while language catalogs provide the text shown to users.

## The English catalog is required

`locales/en.json` is the source catalog and the runtime fallback. Every key used by the application must have a non-empty English value in this file.

When a selected language does not contain a key, the localization layer falls back to the English value. This keeps the interface readable while a translation is incomplete. Leave untranslated entries out of a secondary catalog; an explicitly empty value is still a value and can produce a blank UI element. If the key is missing from both the selected catalog and `en.json`, the application falls back to displaying the key itself. Avoid empty English values too.

The fallback is designed to keep missing translations from leaving the UI blank; it does not replace testing the feature or guarantee that unrelated application errors cannot occur.

## Adding or changing user-visible text

1. Add the locale file as `locales/<code>.json` and add its `english_name` and `native_name` to the `languages` object in `locales/index.json`. If an index is present, a catalog not listed there will not appear in the language selector.
2. Add a stable, descriptive key and a non-empty English value to `locales/en.json`.
3. In code, request the text through the localization API instead of embedding user-facing text in a widget or message:

   ```python
   from src.utils.i18n import tr

   save_button = QPushButton(tr("common.save"))
   status_label.setText(tr("project.saved_to", path=output_path))
   ```

4. Use named placeholders for dynamic values. Keep the same placeholder names in every language catalog, for example `{path}`, `{count}`, or `{filename}`.
5. Add or update the corresponding value in `locales/es.json` when maintaining the Spanish catalog. Partial community catalogs are allowed; untranslated entries use English fallback.
6. Keep internal identifiers separate from translated labels. Do not translate IDs, enum values, file formats, paths, keys, or values used in comparisons and program logic. For tool and category IDs, use `tr_label(id)`. For combo boxes whose selection is read by code, use translated labels with stable item data and read the selection using `currentData()`.
7. Route help and HTML content through localization keys as well. Preserve valid HTML, keyboard shortcut letters, literal tokens, and markup users need to type.
8. Check the catalog and review the interface after the change.

Do not display application messages with `print()`. Use translated UI messages for users and the project logger for diagnostics.

## Catalog format

Catalogs are flat JSON objects. The file name identifies the language (`en.json`, `es.json`, `pt-BR.json`). The small `locales/index.json` manifest provides each language's English and native display names, so language discovery does not parse every translation catalog. Keep the catalog's `meta.language_name` and `meta.language_name_english` entries in sync with the index; if both names are the same, the menu shows the name only once.

```json
{
  "meta.language_name": "English",
  "meta.language_name_english": "English",
  "common.save": "Save",
  "project.saved_to": "Saved to: {path}"
}
```

Add each available catalog to `locales/index.json` as well:

```json
{
  "languages": {
    "fr": {
      "english_name": "French",
      "native_name": "Français"
    }
  }
}
```

Keep the key stable when improving a translation. Do not reuse one key for unrelated messages, because a translation may need different wording in each context.

## Runtime behavior

- The application initializes localization before creating its main window. Language discovery reads `locales/index.json`; it loads only English and the selected language catalogs for their translations.
- The saved language choice is applied at startup. Automatic selection can use the operating system locale when a matching catalog is available.
- The selected catalog is checked first, followed by English. If neither contains the key, the key is returned as the final fallback.
- Bundled catalogs are combined with user-provided catalogs. User entries can override bundled entries, and partial catalogs inherit missing entries from the bundled language and then English.
- Arabic language codes use a right-to-left application layout. Keep filenames, code tokens, and keyboard shortcut letters intact inside translated strings.
- Include the `locales/` directory in every PyInstaller spec so the bundled catalogs are available in packaged builds.
- Keep every bundled language in `locales/index.json`. If the index is missing entirely, older/custom locale folders use a slower legacy scan of catalog files.
- A language change is applied on the next application start unless the UI explicitly reloads localized content.

## Validation and maintenance tools

Run commands from the repository root.

Validate every locale catalog:

```bash
python tools/check_locales.py
```

Validate one catalog:

```bash
python tools/check_locales.py locales/es.json
```

Require a complete catalog for release review:

```bash
python tools/check_locales.py --strict
```

The validator checks JSON structure, unexpected keys, missing language metadata, named placeholder consistency, and consistency between each catalog and `locales/index.json`. In normal mode, missing translation keys are warnings because runtime fallback to English is supported. Use strict mode only when the locale is intended to be complete. The current validator does not reject empty string values, so review catalogs for them manually; omit untranslated keys to activate fallback.

`tools/extract_strings.py` scans known UI text call sites and updates the English catalog and reports. Its output is a review aid: inspect the generated diff and report because static extraction can miss strings or misclassify text used by application logic.

`tools/migrate_to_tr.py` helps convert existing hard-coded UI text to localization calls. Run it first without `--apply` and inspect `MIGRATION_REPORT.md`; use `--apply` only after reviewing the proposed changes. It is primarily a migration tool, not the normal way to write new features.

`tools/fix_leftovers.py` contains exact, one-time replacements for cases that need manual treatment. Run it without `--apply` first. Its replacements depend on the source matching the expected text, so inspect every result and the resulting diff before applying or keeping it for future use.

## Contributor checklist

- [ ] New or changed user-visible strings are requested with `tr()` or `tr_label()`; no user-facing UI strings are hard-coded.
- [ ] Every referenced key exists in `locales/en.json` and has a non-empty English value.
- [ ] The language code and matching English/native display names are present in `locales/index.json`.
- [ ] Dynamic placeholders match across catalogs.
- [ ] Internal IDs and logic values remain stable and separate from translated labels.
- [ ] Relevant secondary catalogs are updated, or intentionally rely on English fallback.
- [ ] `python tools/check_locales.py` passes, and the relevant UI has been checked in the selected language and English fallback where practical.

## Roadmap

1. Continue auditing visible text in the frontend, backend messages, dialogs, and help content.
2. Keep catalogs and the language index synchronized, and verify inclusion in supported packages.
3. Document how community translators can propose, review, and maintain language catalogs.
4. Review catalog completeness and exercise the app in supported languages and English fallback.

The goal is community-maintained language catalogs that keep the application usable while translations are in progress. The English catalog must remain complete so missing translations have readable fallback text.
