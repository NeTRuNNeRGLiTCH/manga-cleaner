"""
Validate translation files against locales/en.json.

    python tools/check_locales.py                 # checks every locales/*.json
    python tools/check_locales.py locales/es.json # one file
    python tools/check_locales.py --strict        # missing keys also fail (CI)

Errors (exit code 1): invalid JSON, non-string values, extra keys that are not
in en.json, placeholder mismatch ({n} in English but not in the translation, or
vice versa), missing meta.language_name.
Warnings: missing keys (they fall back to English at runtime). --strict makes
them errors.
"""

import argparse
import glob
import json
import os
import re
import sys

PLACEHOLDER = re.compile(r"(?<!\{)\{(\w+)\}(?!\})")


def load(path):
    with open(path, "r", encoding="utf-8-sig") as f:
        return json.load(f)


def check_file(path, ref, strict):
    errors, warnings = [], []
    try:
        data = load(path)
    except (OSError, ValueError) as e:
        return [f"invalid JSON: {e}"], []
    if not isinstance(data, dict):
        return ["top level must be a JSON object"], []

    for k, v in data.items():
        if not isinstance(v, str):
            errors.append(f"{k}: value must be a string")
    if not str(data.get("meta.language_name", "")).strip():
        errors.append("missing 'meta.language_name' (shown in the language selector)")

    ref_keys, keys = set(ref), set(data)
    for k in sorted(keys - ref_keys):
        errors.append(f"{k}: not in en.json (typo, or removed from the program)")
    missing = sorted(ref_keys - keys)
    for k in missing:
        (errors if strict else warnings).append(f"{k}: missing (will show English)")

    for k in sorted(keys & ref_keys):
        if not isinstance(data[k], str):
            continue
        want, got = set(PLACEHOLDER.findall(ref[k])), set(PLACEHOLDER.findall(data[k]))
        if want != got:
            errors.append(
                f"{k}: placeholders differ - English has {sorted(want)}, this file has {sorted(got)}"
            )
    return errors, warnings


def check_language_index(locales_dir, files, ref_path, include_unselected_entries=True):
    """Check the fast-discovery index when a locale directory provides one."""
    index_path = os.path.join(locales_dir, "index.json")
    if not os.path.isfile(index_path):
        return []  # Older/custom locale folders can still use legacy discovery.
    try:
        index = load(index_path)
    except (OSError, ValueError) as e:
        return [f"index.json: invalid JSON: {e}"]
    if not isinstance(index, dict) or not isinstance(index.get("languages"), dict):
        return ["index.json: 'languages' must be an object"]

    catalog_paths = {"en": ref_path}
    catalog_paths.update({os.path.splitext(os.path.basename(path))[0]: path for path in files})
    languages = index["languages"]
    errors = []

    for code in sorted(catalog_paths):
        entry = languages.get(code)
        if not isinstance(entry, dict):
            errors.append(f"{code}.json: missing from index.json")
            continue
        english_name = entry.get("english_name")
        native_name = entry.get("native_name")
        if not isinstance(english_name, str) or not english_name.strip():
            errors.append(f"index.json: {code}.english_name must be a non-empty string")
        if not isinstance(native_name, str) or not native_name.strip():
            errors.append(f"index.json: {code}.native_name must be a non-empty string")
        try:
            catalog = load(catalog_paths[code])
        except (OSError, ValueError):
            continue
        if isinstance(english_name, str) and catalog.get("meta.language_name_english") != english_name:
            errors.append(f"{code}.json: meta.language_name_english differs from index.json")
        if isinstance(native_name, str) and catalog.get("meta.language_name") != native_name:
            errors.append(f"{code}.json: meta.language_name differs from index.json")

    if include_unselected_entries:
        for code in sorted(languages):
            if code not in catalog_paths:
                errors.append(f"index.json: {code}.json is missing")
    return errors


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("files", nargs="*", help="catalogs to check (default: locales/*.json)")
    ap.add_argument("--locales", default="locales", help="folder with en.json (default: locales)")
    ap.add_argument("--strict", action="store_true", help="treat missing keys as errors")
    a = ap.parse_args(argv)

    ref_path = os.path.join(a.locales, "en.json")
    if not os.path.isfile(ref_path):
        print(f"ERROR: {ref_path} not found. Run the extractor first.")
        return 2
    ref = load(ref_path)

    files = a.files or sorted(
        p for p in glob.glob(os.path.join(a.locales, "*.json"))
        if not p.lower().endswith(".sources.json")
        and os.path.basename(p).lower() not in ("en.json", "index.json")
    )
    if not files:
        print("No translations to check (only en.json exists).")
        return 0

    failed = False
    for path in files:
        errors, warnings = check_file(path, ref, a.strict)
        metadata = {"meta.language_name", "meta.language_name_english"}
        total = len([k for k in ref if k not in metadata])
        print(f"\n{os.path.basename(path)}: {len(errors)} error(s), {len(warnings)} warning(s)  [{total} keys in en.json]")
        for m in errors:
            print(f"  ERROR  {m}")
        for m in warnings[:20]:
            print(f"  warn   {m}")
        if len(warnings) > 20:
            print(f"  warn   ... and {len(warnings) - 20} more missing keys")
        failed = failed or bool(errors)

    index_errors = check_language_index(
        a.locales, files, ref_path, include_unselected_entries=not bool(a.files)
    )
    if index_errors:
        print(f"\nindex.json: {len(index_errors)} error(s)")
        for message in index_errors:
            print(f"  ERROR  {message}")
        failed = True
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
