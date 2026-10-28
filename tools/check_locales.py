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
        total = len([k for k in ref if k != "meta.language_name"])
        print(f"\n{os.path.basename(path)}: {len(errors)} error(s), {len(warnings)} warning(s)  [{total} keys in en.json]")
        for m in errors:
            print(f"  ERROR  {m}")
        for m in warnings[:20]:
            print(f"  warn   {m}")
        if len(warnings) > 20:
            print(f"  warn   ... and {len(warnings) - 20} more missing keys")
        failed = failed or bool(errors)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())