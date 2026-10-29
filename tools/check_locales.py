"""Validate translation catalogs and approve them for a specific English source.

    python tools/check_locales.py                 # inspect all catalogs
    python tools/check_locales.py locales/es.json # inspect one catalog
    python tools/check_locales.py --approve       # interactively complete/approve catalogs
    python tools/check_locales.py --release       # fail if any catalog is stale or unapproved

Approval checks key parity and named placeholders. It does not assess translation
quality. Missing or empty entries may be filled with English source text so the
interface remains complete while those strings await translation.
"""

import argparse
import glob
import hashlib
import json
import os
import re
import sys

PLACEHOLDER = re.compile(r"(?<!\{)\{(\w+)\}(?!\})")
CATALOG_ROLE_KEY = "meta.catalog_role"
TRANSLATION_STATUS_KEY = "meta.translation_status"
TRANSLATION_SOURCE_HASH_KEY = "meta.translation_source_sha256"
VERIFIED_STATUS = "Verified and approved for use in Manga Cleaner Studio"
SOURCE_ROLE = "Original source catalog and primary language"
SPECIAL_KEYS = {
    CATALOG_ROLE_KEY,
    TRANSLATION_STATUS_KEY,
    TRANSLATION_SOURCE_HASH_KEY,
}


def canonical_hash(data):
    """Hash JSON content independent of key order and line-ending style."""
    payload = json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def source_fingerprint(path):
    """Hash the English source bytes without depending on Windows line endings."""
    with open(path, "rb") as f:
        payload = f.read()
    if payload.startswith(b"\xef\xbb\xbf"):
        payload = payload[3:]
    payload = payload.replace(b"\r\n", b"\n")
    return hashlib.sha256(payload).hexdigest()


def load(path):
    with open(path, "r", encoding="utf-8-sig") as f:
        return json.load(f)


def write_json(path, data):
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def catalog_keys(data):
    """Return translatable/source keys, excluding validation-only metadata."""
    return set(data) - SPECIAL_KEYS


def missing_or_empty_keys(data, ref):
    """Return source keys absent from or blank in a target catalog."""
    target_keys = catalog_keys(data)
    source_keys = catalog_keys(ref)
    return sorted(
        key for key in source_keys
        if key not in data or not isinstance(data.get(key), str) or not data[key].strip()
    )


def check_file(path, ref, strict=False):
    try:
        data = load(path)
    except (OSError, ValueError) as e:
        return [f"invalid JSON: {e}"], []
    if not isinstance(data, dict):
        return ["top level must be a JSON object"], []

    return check_data(data, ref, strict)


def check_data(data, ref, strict=False):
    """Validate an already parsed translation dictionary."""
    errors, warnings = [], []

    for k, v in data.items():
        if not isinstance(v, str):
            errors.append(f"{k}: value must be a string")
        elif not v.strip() and k not in SPECIAL_KEYS:
            errors.append(f"{k}: value must not be empty")
    if not str(data.get("meta.language_name", "")).strip():
        errors.append("missing 'meta.language_name' (shown in the language selector)")
    if not str(data.get("meta.language_name_english", "")).strip():
        errors.append("missing 'meta.language_name_english' (English language name for the selector)")

    ref_keys, keys = catalog_keys(ref), catalog_keys(data)
    for k in sorted(keys - ref_keys):
        errors.append(f"{k}: not in en.json (typo, or removed from the program)")
    for k in missing_or_empty_keys(data, ref):
        message = f"{k}: missing or empty (English source text can be copied into this catalog)"
        (errors if strict else warnings).append(message)

    for k in sorted(keys & ref_keys):
        if not isinstance(data.get(k), str) or not isinstance(ref.get(k), str):
            continue
        want = set(PLACEHOLDER.findall(ref[k]))
        got = set(PLACEHOLDER.findall(data[k]))
        if want != got:
            errors.append(
                f"{k}: placeholders differ - English has {sorted(want)}, "
                f"this file has {sorted(got)}"
            )
    return errors, warnings


def check_language_index(locales_dir, files, ref_path, include_unselected_entries=True):
    """Check language names and the source/catalog verification fingerprints."""
    index_path = os.path.join(locales_dir, "index.json")
    if not os.path.isfile(index_path):
        return ["index.json is required for verified language catalogs"]
    try:
        index = load(index_path)
    except (OSError, ValueError) as e:
        return [f"index.json: invalid JSON: {e}"]
    if not isinstance(index, dict) or not isinstance(index.get("languages"), dict):
        return ["index.json: 'languages' must be an object"]

    try:
        ref = load(ref_path)
    except (OSError, ValueError) as e:
        return [f"en.json: invalid JSON: {e}"]
    expected_source_hash = source_fingerprint(ref_path)
    errors = []
    if ref.get(CATALOG_ROLE_KEY) != SOURCE_ROLE:
        errors.append("en.json: missing original source-catalog marker")
    if index.get("source_catalog_sha256") != expected_source_hash:
        errors.append("index.json: source catalog fingerprint is stale; run check_locales.py --approve")

    catalog_paths = {"en": ref_path}
    catalog_paths.update({os.path.splitext(os.path.basename(path))[0]: path for path in files})
    languages = index["languages"]
    for code in sorted(catalog_paths):
        entry = languages.get(code)
        if not isinstance(entry, dict):
            errors.append(f"{code}.json: missing from index.json")
            continue
        if code == "en":
            continue
        path = catalog_paths[code]
        try:
            catalog = load(path)
        except (OSError, ValueError):
            continue
        if not isinstance(catalog, dict):
            errors.append(f"{code}.json: top level must be a JSON object")
            continue
        if entry.get("verified_source_sha256") != expected_source_hash:
            errors.append(f"{code}.json: approval is stale; run check_locales.py --approve")
        if entry.get("catalog_sha256") != canonical_hash(catalog):
            errors.append(f"{code}.json: catalog changed after approval; run check_locales.py --approve")

        for field in ("english_name", "native_name"):
            value = entry.get(field)
            if not isinstance(value, str) or not value.strip():
                errors.append(f"index.json: {code}.{field} must be a non-empty string")
        if catalog.get("meta.translation_status") != VERIFIED_STATUS:
            errors.append(f"{code}.json: missing verified translation status")
        if catalog.get(TRANSLATION_SOURCE_HASH_KEY) != expected_source_hash:
            errors.append(f"{code}.json: source fingerprint is missing or stale")
        if catalog.get("meta.language_name_english") != entry.get("english_name"):
            errors.append(f"{code}.json: meta.language_name_english differs from index.json")
        if catalog.get("meta.language_name") != entry.get("native_name"):
            errors.append(f"{code}.json: meta.language_name differs from index.json")

    if include_unselected_entries:
        for code in sorted(languages):
            if code not in catalog_paths:
                errors.append(f"index.json: {code}.json is missing")
    return errors


def prompt_yes_no(message):
    try:
        return input(f"{message} [y/N] ").strip().lower() in ("y", "yes")
    except (EOFError, KeyboardInterrupt):
        print("\nNo changes approved.")
        return False


def approve_catalog(path, ref, source_hash, index):
    """Interactively repair missing keys and stamp a structurally valid catalog."""
    code = os.path.splitext(os.path.basename(path))[0]
    if code == "en":
        print("en.json is the source catalog and does not receive a translation approval marker.")
        return False
    try:
        data = load(path)
    except (OSError, ValueError) as e:
        print(f"  ERROR  invalid JSON: {e}")
        return False
    if not isinstance(data, dict):
        print("  ERROR  top level must be a JSON object")
        return False

    missing = missing_or_empty_keys(data, ref)
    if missing:
        print(f"  Missing/empty keys ({len(missing)}):")
        for key in missing:
            print(f"    - {key}")
        if not prompt_yes_no("Copy the English source text for these keys into this catalog? (They can be translated later)"):
            print("  Not approved. Add and translate the missing keys, then run this command again.")
            return False
        for key in missing:
            data[key] = ref[key]

    errors, warnings = check_data(data, ref, strict=True)
    if errors or warnings:
        for message in errors + warnings:
            print(f"  ERROR  {message}")
        print("  Not approved. Fix the catalog errors and run this command again.")
        return False

    english_name = data["meta.language_name_english"].strip()
    native_name = data["meta.language_name"].strip()

    if not prompt_yes_no("Approve this catalog as structurally verified for the current English source?"):
        print("  Catalog was not approved.")
        return False

    data.pop("meta.catalog_role", None)
    data["meta.translation_status"] = VERIFIED_STATUS
    data[TRANSLATION_SOURCE_HASH_KEY] = source_hash
    write_json(path, data)

    entry = index["languages"].setdefault(code, {})
    # Keep display names in the lightweight index sourced from the catalog metadata.
    entry["english_name"] = english_name
    entry["native_name"] = native_name
    entry["verified_source_sha256"] = source_hash
    entry["catalog_sha256"] = canonical_hash(data)
    return True


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("files", nargs="*", help="catalogs to check (default: locales/*.json)")
    ap.add_argument("--locales", default="locales", help="folder with en.json (default: locales)")
    ap.add_argument("--strict", action="store_true", help="treat missing keys as errors")
    ap.add_argument("--approve", action="store_true", help="interactively complete and approve catalogs")
    ap.add_argument("--release", action="store_true", help="require complete, current approvals for release")
    args = ap.parse_args(argv)
    if args.approve and args.release:
        ap.error("--approve and --release cannot be used together")

    ref_path = os.path.join(args.locales, "en.json")
    if not os.path.isfile(ref_path):
        print(f"ERROR: {ref_path} not found. The English source catalog is required.")
        return 2
    try:
        ref = load(ref_path)
    except (OSError, ValueError) as e:
        print(f"ERROR: invalid English source catalog: {e}")
        return 2
    if not isinstance(ref, dict):
        print("ERROR: en.json must contain a JSON object.")
        return 2

    source_hash = source_fingerprint(ref_path)
    files = args.files or sorted(
        p for p in glob.glob(os.path.join(args.locales, "*.json"))
        if not p.lower().endswith(".sources.json")
        and os.path.basename(p).lower() not in ("en.json", "index.json")
    )
    if not files:
        print("No translations to check (only en.json exists).")
        return 0

    if args.approve:
        if ref.get(CATALOG_ROLE_KEY) != SOURCE_ROLE:
            ref[CATALOG_ROLE_KEY] = SOURCE_ROLE
            write_json(ref_path, ref)
            source_hash = source_fingerprint(ref_path)
            print("Added the source-catalog marker to en.json.")
        index_path = os.path.join(args.locales, "index.json")
        try:
            index = load(index_path)
        except (OSError, ValueError) as e:
            print(f"ERROR: cannot approve catalogs without a valid index.json: {e}")
            return 2
        if not isinstance(index, dict) or not isinstance(index.get("languages"), dict):
            print("ERROR: index.json must contain a 'languages' object.")
            return 2
        index["source_catalog_sha256"] = source_hash
        approved_any = False
        all_approved = True
        for path in files:
            print(f"\n{os.path.basename(path)}")
            approved = approve_catalog(path, ref, source_hash, index)
            approved_any = approved or approved_any
            all_approved = approved and all_approved
        if approved_any:
            write_json(index_path, index)
            print("\nUpdated locales/index.json with the current source and catalog fingerprints.")
        else:
            print("\nNo catalogs were approved; locales/index.json was not changed.")
        return 0 if approved_any and all_approved else 1

    failed = False
    for path in files:
        errors, warnings = check_file(path, ref, strict=args.strict or args.release)
        try:
            data = load(path)
        except (OSError, ValueError):
            data = {}
        missing = missing_or_empty_keys(data, ref) if isinstance(data, dict) else []
        total = len(catalog_keys(ref))
        print(f"\n{os.path.basename(path)}: {len(errors)} error(s), {len(warnings)} warning(s)  [{total} source keys]")
        for message in errors:
            print(f"  ERROR  {message}")
        for message in warnings[:20]:
            print(f"  WARN   {message}")
        if len(warnings) > 20:
            print(f"  WARN   ... and {len(warnings) - 20} more missing keys")
        if args.release and missing:
            failed = True
        failed = failed or bool(errors)

    index_errors = check_language_index(
        args.locales, files, ref_path, include_unselected_entries=not bool(args.files)
    )
    if index_errors:
        print(f"\nindex.json: {len(index_errors)} error(s)")
        for message in index_errors:
            print(f"  ERROR  {message}")
        failed = True
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
