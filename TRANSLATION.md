# UI Localization

## Purpose

Manga Cleaner uses a small localization layer so the application can display its interface in multiple languages. Keep localization separate from application logic: code refers to stable keys, while language catalogs provide the text shown to users.

## The English catalog is required

`locales/en.json` is the original source catalog. It contains the `meta.catalog_role` marker to identify its role; this metadata is not displayed in the interface. Every user-visible key must have a non-empty English value in this file. When adding or changing application UI text, developers edit this file only; the validator keeps other catalogs structurally complete.

Every non-English catalog must be structurally verified against the current English source before the application loads it. An approved catalog contains every source key and matching named placeholders. Missing entries can be filled with the English source text; these remain untranslated but do not leave blank UI strings. The validator records a source fingerprint and a catalog fingerprint in the locale and `locales/index.json`.

If a selected catalog is missing its verification marker, has changed since approval, or targets a different source fingerprint, the application warns the user and loads English for that session. English is loaded as a recovery catalog only in this case; a normally approved non-English startup loads the language index and the selected catalog only. The build workflow runs release validation so stale source fingerprints cannot be packaged accidentally.

## Adding or changing user-visible text

1. Add a stable, descriptive key and a non-empty English value to `locales/en.json`.
2. In code, request the text through the localization API instead of embedding user-facing text in a widget or message:

   ```python
   from src.utils.i18n import tr

   save_button = QPushButton(tr("common.save"))
   status_label.setText(tr("project.saved_to", path=output_path))
   ```

3. Use named placeholders for dynamic values. Keep the same placeholder names in every language catalog, for example `{path}`, `{count}`, or `{filename}`.
4. Keep internal identifiers separate from translated labels. Do not translate IDs, enum values, file formats, paths, keys, or values used in comparisons and program logic. For tool and category IDs, use `tr_label(id)`. For combo boxes whose selection is read by code, use translated labels with stable item data and read the selection using `currentData()`.
5. Route help and HTML content through localization keys as well. Preserve valid HTML, keyboard shortcut letters, literal tokens, and markup users need to type.
6. Run `python tools/check_locales.py --approve`. For each locale missing new keys, it lists them and asks whether to copy the English source text into that locale. This keeps the catalog complete; copied values remain English until translated.
7. Review translation wording separately. The verifier checks structure and placeholders, not meaning. Run `python tools/check_locales.py --release` to confirm every catalog is complete and approved for the current English source.

### Adding a new language

1. Create `locales/<code>.json` by translating values from `locales/en.json`. Preserve all keys and named placeholders. An LLM-generated catalog can be submitted for structural approval before a human language audit; record its audit status accurately in the table below.
2. Set `meta.language_name` to the language's native name and `meta.language_name_english` to its English name in the new catalog. These values are used to label the language selector.
3. Run `python tools/check_locales.py --approve locales/<code>.json`. Resolve missing keys and placeholder errors, then approve the structurally valid catalog. On approval, the tool copies both display names from the catalog into `locales/index.json` and generates the verification fingerprints; do not enter or invent these index values manually.
4. If the catalog is not approved, the application warns on startup and uses English for that session.

### LLM-assisted localization workflow

The usual workflow does not require a contributor to translate the catalog manually. An LLM that has reviewed the application code can use that context to understand UI terms, then translate the values in `locales/en.json` into a complete target catalog. The contributor supplies `en.json` and the target language to the LLM, saves its JSON output as `locales/<code>.json`, and runs the approval tool. The approval tool validates and records the catalog; it does not perform the translation or certify its wording.

Use a prompt like this when requesting a catalog:

```text
Using your context from reviewing the Manga Cleaner Studio code, localize the attached
locales/en.json catalog into [LANGUAGE] ([LOCALE_CODE]). Return only the complete,
valid JSON object for locales/[LOCALE_CODE].json.

Requirements:
- Preserve every existing key exactly. Do not add, remove, rename, or reorder keys
  unless JSON formatting requires it.
- Translate the values shown to users. Keep meta.language_name in the target language
  and meta.language_name_english in English.
- Do not copy meta.catalog_role into the translated catalog. Do not create approval
  markers or fingerprints; check_locales.py generates those.
- Preserve named placeholders such as {path}, {count}, and {filename}, along with
  keyboard shortcuts, HTML, literal tokens, file formats, IDs, and paths.
- Use the source-code context to choose terminology that matches the feature.
- Return no Markdown fences or commentary, only JSON.
```

Save the output under its locale code, then run:

```bash
python tools/check_locales.py --approve locales/<code>.json
```

Approval checks catalog structure, key coverage, placeholders, and source fingerprints. It may offer to copy missing English values into the catalog; accept only if you want those strings left untranslated for now. Approval is not a language-quality audit. Record the LLM and any human contributors in the language table below, and keep `Audited` as `No` until a fluent human reviewer checks the translation in context. A code review by an LLM, successful validation, or a successful application startup does not by itself count as that audit.

Do not display application messages with `print()`. Use translated UI messages for users and the project logger for diagnostics.

## Catalog format

Catalogs are flat JSON objects. The file name identifies the language (`en.json`, `es.json`, `pt-BR.json`). The small `locales/index.json` manifest provides language display names and the current English source fingerprint, so language discovery does not parse every translation catalog. Keep each catalog's `meta.language_name` and `meta.language_name_english` entries in sync with the index; if both names are the same, the menu shows the name only once.

```json
{
  "meta.language_name": "English",
  "meta.language_name_english": "English",
  "meta.catalog_role": "Original source catalog and primary language",
  "common.save": "Save",
  "project.saved_to": "Saved to: {path}"
}
```

The approval tool adds each available language to `locales/index.json`, copying its display names from `meta.language_name_english` and `meta.language_name`. It also adds `verified_source_sha256` and `catalog_sha256` to approved secondary entries, and `source_catalog_sha256` at the manifest root. These index values and fingerprints are generated; do not edit them manually.

```json
{
  "schema_version": 1,
  "source_catalog_sha256": "<generated by check_locales.py>",
  "languages": {
    "fr": {
      "english_name": "French",
      "native_name": "Français",
      "verified_source_sha256": "<generated by check_locales.py>",
      "catalog_sha256": "<generated by check_locales.py>"
    }
  }
}
```

Keep the key stable when improving a translation. Do not reuse one key for unrelated messages, because a translation may need different wording in each context.

## Runtime behavior

- The application initializes localization before creating its main window. Language discovery reads `locales/index.json` and does not parse language catalogs to populate the selector.
- English is loaded alone when English is selected. For an approved non-English language, the application loads the small index and that one language catalog. The English catalog is loaded on a non-English startup only if verification fails and the app needs to recover in English.
- To detect a changed English source even when a developer forgot to refresh the manifest, the app reads its bytes to calculate a fingerprint. It does not parse the English JSON or keep its catalog in memory during a valid non-English startup.
- The saved language choice is applied at startup. Automatic selection can use the operating system locale when a matching catalog is available.
- Approved catalogs must have complete key coverage and matching placeholders. If a non-English catalog is not approved for the current source version, the app displays an English warning, switches to English for the current session, and tells the user how to run the validator from the source project.
- The selected user catalog replaces its bundled counterpart; catalogs are not merged per key. User-provided catalogs must therefore be complete and independently verified before use.
- Arabic language codes use a right-to-left application layout. Keep filenames, code tokens, and keyboard shortcut letters intact inside translated strings.
- Include the `locales/` directory in every PyInstaller spec so the bundled catalogs are available in packaged builds.
- Keep every bundled language in `locales/index.json`. If an index is missing, legacy catalog files may be discovered by filename, but non-English catalogs without verification metadata are not eligible for loading.
- A language change is applied on the next application start unless the UI explicitly reloads localized content.

## Validation and maintenance tools

Run commands from the repository root.

Inspect every locale catalog and its approval fingerprints:

```bash
python tools/check_locales.py
```

Validate one catalog:

```bash
python tools/check_locales.py locales/es.json
```

Interactively copy English source text into missing/empty entries and approve catalogs whose keys and placeholders validate:

```bash
python tools/check_locales.py --approve
```

Approve one catalog:

```bash
python tools/check_locales.py --approve locales/fr.json
```

Require every catalog to be complete, approved for the current source fingerprint, and unchanged since approval:

```bash
python tools/check_locales.py --release
```

The validator checks JSON structure, source-key coverage, unexpected keys, empty values, named placeholder consistency, language metadata, verification markers, and source/catalog fingerprints. It can copy missing English source values into a target catalog, but it does not machine-translate those values or judge translation quality. Treat approval as a structural check, then review translated wording separately. Editing `en.json` changes its source fingerprint and makes all secondary approvals stale until they are rechecked. Running `--approve` with no file arguments processes all locale catalogs; this is the recommended workflow after changing English strings.

`tools/extract_strings.py` scans known UI text call sites and updates the English catalog and reports. Its output is a review aid: inspect the generated diff and report because static extraction can miss strings or misclassify text used by application logic.

`tools/migrate_to_tr.py` helps convert existing hard-coded UI text to localization calls. Run it first without `--apply` and inspect `MIGRATION_REPORT.md`; use `--apply` only after reviewing the proposed changes. It is primarily a migration tool, not the normal way to write new features.

`tools/fix_leftovers.py` contains exact, one-time replacements for cases that need manual treatment. Run it without `--apply` first. Its replacements depend on the source matching the expected text, so inspect every result and the resulting diff before applying or keeping it for future use.

## Contributor checklist

- [ ] New or changed user-visible strings are requested with `tr()` or `tr_label()`; no user-facing UI strings are hard-coded.
- [ ] Every referenced key exists in `locales/en.json` and has a non-empty English value.
- [ ] The catalog has correct `meta.language_name` and `meta.language_name_english` values; `--approve` copies them into `locales/index.json`.
- [ ] Dynamic placeholders match across catalogs.
- [ ] Internal IDs and logic values remain stable and separate from translated labels.
- [ ] Secondary catalogs contain every source key and are approved against the current English source.
- [ ] LLM and human localization contributors are credited in the language table; mark `Audited` as `No` until a fluent human reviewer checks the translation in context.
- [ ] `python tools/check_locales.py --release` passes before packaging or release.
- [ ] The relevant UI has been checked in the selected language and English; stale catalogs should recover to English with a clear warning.

## Roadmap

1. Continue auditing visible text in the frontend, backend messages, dialogs, and help content.
2. Keep catalogs and the language index synchronized, and verify inclusion in supported packages.
3. Document how community translators can propose, review, and maintain language catalogs.
4. Review translation quality and exercise the app in supported languages.

The goal is community-maintained language catalogs that remain structurally complete and traceable to the current English source. Keep `locales/en.json` in the project; do not remove or rename it.

## Available languages and localization credits

The table below records the localization contributors and review status for the catalogs currently included in the project. “Not audited” means the translation has not received a human language-quality review; LLM code review, structural verification, and successful application startup do not count as an audit. The content of the text, as well as the quality of the writing and/or translation, can only be audited by humans.

| Language | Localization credits | Audited | Manga Cleaner version |
|---|---|---|---|
| English (English) | Original source catalog | N/A — source language | 3.4.2 |
| Spanish (Español) | LLM ChatGPT | SI —  Santiagodvergara05-debug | 3.4.2 |
| Portuguese (Brasil) | LLM ChatGPT | No — review pending | 3.4.2 |
| French (Français) | LLM ChatGPT | No — review pending | 3.4.2 |
| Arabic (Egypt) (العربية (مصر)) | LLM ChatGPT | No — review pending | 3.4.2 |
| Korean (한국어) | LLM Gemini | No — review pending | 3.4.2 |
| Japanese (日本語) | LLM Gemini | No — review pending | 3.4.2 |
| Simplified Chinese (简体中文) | LLM Gemini | No — review pending | 3.4.2 |
| Traditional Chinese (繁體中文) | LLM Gemini | No — review pending | 3.4.2 |

## Localization integrity and review policy

Every localization must faithfully convey the meaning, intent, and tone of its English source. Contributors must not add unrelated text, alter a message's meaning, or introduce profanity, slurs, hateful or harassing language, or other prohibited material that is absent from the source. This applies to catalog values, metadata shown to users, and any other localized content.

If a pull request or issue reports a potentially abusive, misleading, or unrelated translation, maintainers will review the reported key in context against the English source. They may consult multiple independent large language models (LLMs), such as Claude, ChatGPT, Gemini, DeepSeek, or Grok, as supporting reviewers. A finding is counted as positive when a model identifies a material mismatch or prohibited content. If more than 80% of the participating models flag the reported content, the report qualifies for an expedited maintainer review. Model votes are advisory and do not, by themselves, establish misconduct.

If maintainers confirm that a submitted localization deliberately or materially violates this policy, they may suspend or remove the affected catalog, remove the associated localization credit, and permanently restrict the responsible contributor from submitting further localization contributions. Maintainers should document the decision and its evidence in the relevant pull request or issue. Accidental errors should be corrected and do not automatically warrant these sanctions.
