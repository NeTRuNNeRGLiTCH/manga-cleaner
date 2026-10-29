#!/usr/bin/env python3
"""
Replace hard-coded UI strings with tr("key") calls, using the same analysis as extract_strings.py.

Run from the repository root (commit or stash your work first, so `git diff` shows exactly what changed):

    python tools/migrate_to_tr.py              # DRY RUN: only writes MIGRATION_REPORT.md
    python tools/migrate_to_tr.py --apply      # rewrites the .py files (and adds missing keys to locales/en.json)
    python tools/migrate_to_tr.py --apply --only src/frontend/main_window.py

It is deliberately conservative. A string is NOT touched (and is listed in the report) when:
  * ID_AND_LABEL / COMBO_VALUE_USED_AS_LOGIC : the text is also used as an id or read back by the code.
  * TEXT_USED_IN_LOGIC : the same text appears in a comparison / dict key / subscript somewhere.
  * IMPORT_TIME : it is evaluated at import/class-definition time (tr() would run before i18n.init()).
  * PLACEHOLDER_IS_TEXT / UNSAFE_FORMAT_SPEC : the f-string embeds translatable text or a nested spec.
Everything else becomes tr("key") or tr("key", name=expr, ...). f-string specs/conversions are kept
(f"{x:.1f}" -> tr("k", x=format(x, '.1f'))). Each rewritten file is re-parsed before it is written.
"""
import argparse
import ast
import importlib.util
import json
import os
import re
import sys
from collections import OrderedDict, defaultdict

IMPORT_LINE = "from src.utils.i18n import tr"


def load_extractor(tools_dir):
    for name in ("extract_strings.py", "Extract_strings_translation.py"):
        path = os.path.join(tools_dir, name)
        if os.path.isfile(path):
            spec = importlib.util.spec_from_file_location("extract_strings_mod", path)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            if hasattr(mod, "collect"):
                return mod
    sys.exit("Could not find an up-to-date extract_strings.py next to this script (needs collect()).")


# --------------------------------------------------------------------------- text surgery
_EOL = re.compile(r"\r\n|\n|\r")


def split_lines(src):
    """Split keeping line endings, using the same line model as `ast` (\\n, \\r\\n, \\r)."""
    out, pos = [], 0
    for m in _EOL.finditer(src):
        out.append(src[pos:m.end()])
        pos = m.end()
    if pos < len(src):
        out.append(src[pos:])
    return out


def char_index(lines, lineno, byte_col):
    """ast columns are UTF-8 byte offsets -> absolute character index in the file."""
    base = sum(len(l) for l in lines[:lineno - 1])
    line = lines[lineno - 1]
    return base + len(line.encode("utf-8")[:byte_col].decode("utf-8"))


def build_call(key, exprs):
    if not exprs:
        return f'tr("{key}")'
    args = ", ".join(f"{e[0]}={e[2]}" for e in exprs)
    return f'tr("{key}", {args})'


def add_import(src):
    tree = ast.parse(src)
    last = None
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            last = node
    if last is None:
        return None
    lines = split_lines(src)
    eol = "\r\n" if "\r\n" in src else "\n"
    idx = last.end_lineno                      # insert after the last top-level import
    if not lines[idx - 1].endswith(("\n", "\r")):
        lines[idx - 1] += eol
    lines.insert(idx, IMPORT_LINE + eol)
    return "".join(lines)


def has_tr_import(tree):
    """True if the module already does `from src.utils.i18n import ... tr ...` (tr_label does not count)."""
    for n in tree.body:
        if isinstance(n, ast.ImportFrom) and n.module == "src.utils.i18n":
            if any(al.name == "tr" and al.asname in (None, "tr") for al in n.names):
                return True
    return False


def uses_name_tr(tree):
    for n in ast.walk(tree):
        if isinstance(n, ast.Name) and n.id == "tr" and isinstance(n.ctx, (ast.Store, ast.Del)):
            return True
        if isinstance(n, ast.arg) and n.arg == "tr":
            return True
        if isinstance(n, (ast.FunctionDef, ast.ClassDef)) and n.name == "tr":
            return True
    return False


# --------------------------------------------------------------------------- main
def decide(e, logic):
    """Return None if the entry can be migrated, else a reason string."""
    for fl in ("ID_AND_LABEL", "COMBO_VALUE_USED_AS_LOGIC", "PLACEHOLDER_IS_TEXT"):
        if fl in e["flags"]:
            return fl
    if not e["in_func"]:
        return "IMPORT_TIME"
    if any(x[3] for x in e["exprs"]):
        return "UNSAFE_FORMAT_SPEC"
    if not e["exprs"] and e["text"] in logic:
        return "TEXT_USED_IN_LOGIC"
    return None


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--root", default=".")
    ap.add_argument("--locales", default="locales")
    ap.add_argument("--apply", action="store_true", help="write the changes (default is a dry run)")
    ap.add_argument("--only", action="append", default=[], help="limit to these files (relative paths)")
    ap.add_argument("--report", default="MIGRATION_REPORT.md")
    a = ap.parse_args()

    root = os.path.abspath(a.root)
    ex = load_extractor(os.path.dirname(os.path.abspath(__file__)))
    en_path = os.path.join(a.locales, "en.json")
    existing = json.load(open(en_path, encoding="utf-8-sig")) if os.path.isfile(en_path) else {}
    entries, _, catalog, _, _, logic = ex.collect(root, existing)

    only = {o.replace("\\", "/") for o in a.only}
    by_file = defaultdict(list)
    for e in entries:
        if not only or e["file"] in only:
            by_file[e["file"]].append(e)

    applied_total, skipped, file_stats, failures = 0, [], [], []
    new_keys = OrderedDict()

    for rel in sorted(by_file):
        path = os.path.join(root, rel)
        with open(path, "r", encoding="utf-8", newline="") as f:
            src = f.read()
        tree = ast.parse(src)
        todo = []
        for e in by_file[rel]:
            reason = decide(e, logic)
            if reason:
                skipped.append((rel, e["line"], reason, e["text"]))
            else:
                todo.append(e)
        if todo and uses_name_tr(tree):
            for e in todo:
                skipped.append((rel, e["line"], "NAME_tr_ALREADY_USED", e["text"]))
            continue
        if not todo:
            continue

        lines = split_lines(src)
        spans = []
        for e in todo:
            l1, c1, l2, c2 = e["pos"]
            spans.append((char_index(lines, l1, c1), char_index(lines, l2, c2), e))
        spans.sort(key=lambda t: t[0], reverse=True)

        new, last_start, done = src, None, 0
        for s, t, e in spans:
            if last_start is not None and t > last_start:        # overlaps a region already replaced
                skipped.append((rel, e["line"], "OVERLAP", e["text"]))
                continue
            new = new[:s] + build_call(e["key"], e["exprs"]) + new[t:]
            last_start = s
            done += 1
            if e["key"] not in existing:
                new_keys[e["key"]] = catalog[e["key"]]
        try:
            ast.parse(new)
            with_import = new if has_tr_import(ast.parse(new)) else add_import(new)
            if with_import is None:
                raise ValueError("no top-level import to anchor the tr import")
            ast.parse(with_import)
        except (SyntaxError, ValueError) as err:
            failures.append((rel, str(err)))
            continue
        if a.apply:
            with open(path, "w", encoding="utf-8", newline="") as f:
                f.write(with_import)
        file_stats.append((rel, done, len([x for x in by_file[rel]]) - done))
        applied_total += done

    if a.apply and new_keys:
        merged = OrderedDict((k, v) for k, v in existing.items() if k != "meta.language_name")
        merged.update(new_keys)
        merged = ex.sort_catalog(merged)
        with open(en_path, "w", encoding="utf-8", newline="\n") as f:
            json.dump({"meta.language_name": "English", **merged}, f, ensure_ascii=False, indent=2)
            f.write("\n")

    # ------------------------------------------------------------------ report
    mode = "APPLIED" if a.apply else "DRY RUN (nothing was written)"
    L = [f"# tr() migration report - {mode}", "",
         f"- Strings rewritten: **{applied_total}**",
         f"- Strings left untouched (need a human): **{len(skipped)}**",
         f"- New keys added to en.json: **{len(new_keys)}**", ""]
    if failures:
        L += ["## Files NOT written (the rewrite failed validation)", ""]
        L += [f"- `{r}`: {m}" for r, m in failures] + [""]
    L += ["## Per file", "", "| File | Rewritten | Left |", "| :--- | ---: | ---: |"]
    L += [f"| `{r}` | {d} | {l} |" for r, d, l in file_stats] + [""]
    reasons = defaultdict(list)
    for rel, ln, why, text in skipped:
        reasons[why].append((rel, ln, text))
    explain = {
        "ID_AND_LABEL": "Visible label AND internal id. Use tr_label(id) for the button; keep the id.",
        "COMBO_VALUE_USED_AS_LOGIC": "Combo item whose currentText() drives logic. Switch to addItem(label, id) + currentData().",
        "TEXT_USED_IN_LOGIC": "The same text is compared / used as a dict key somewhere. Check before translating.",
        "IMPORT_TIME": "Evaluated at import/class level; tr() would run before i18n.init(). Move it into __init__/a method.",
        "PLACEHOLDER_IS_TEXT": "An f-string embeds translatable words. Give each branch its own key.",
        "UNSAFE_FORMAT_SPEC": "Nested format spec in an f-string. Rewrite by hand.",
        "NAME_tr_ALREADY_USED": "The file already uses `tr` as a variable/function name. Rename it, then rerun.",
        "OVERLAP": "Nested inside another replaced string.",
    }
    for why, items in sorted(reasons.items(), key=lambda kv: -len(kv[1])):
        L += [f"## {why} ({len(items)})", explain.get(why, ""), ""]
        for rel, ln, text in sorted(items):
            L.append(f"- `{rel}:{ln}`  {json.dumps(text[:90], ensure_ascii=False)}")
        L.append("")
    with open(a.report, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(L) + "\n")
    print(f"{mode}: rewritten {applied_total}, left {len(skipped)}, failed files {len(failures)}, new keys {len(new_keys)} -> {a.report}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())