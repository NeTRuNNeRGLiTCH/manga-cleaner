#!/usr/bin/env python3
"""
Extracts every user-visible UI string from the Manga Cleaner source tree and writes
a draft translation catalog.

Run from the repository root:
    python tools/extract_strings.py            # writes locales/en.json, locales/en.sources.json, STRINGS_REPORT.md
    python tools/extract_strings.py --root . --out locales

How it works (static analysis, nothing is imported or executed):
  * Parses each .py file with `ast`.
  * Collects string arguments of Qt calls that put text on screen (QLabel, QPushButton,
    setText, setToolTip, QMessageBox.*, addItem, setHtml, ...).
  * Converts f-strings / "a" + b concatenations to {placeholder} templates.
  * Flags entries that need a human decision (see the report).

The output is a STARTING POINT: keys are auto-generated and the code still has to be
migrated to tr("key"). en.sources.json maps each key to the file:line sites to replace.
"""
import argparse
import ast
import json
import os
import re
import sys
import unicodedata
from collections import OrderedDict, defaultdict

# call name -> positional argument indexes that hold visible text
SINKS = {
    "QLabel": [0], "QPushButton": [0], "QCheckBox": [0], "QRadioButton": [0],
    "QGroupBox": [0], "QAction": [0], "QListWidgetItem": [0], "QToolButton": [0],
    "setText": [0], "setToolTip": [0], "setStatusTip": [0], "setPlaceholderText": [0],
    "setWindowTitle": [0], "setTitle": [0], "setHtml": [0], "setWhatsThis": [0],
    "addItem": [0], "addItems": [0], "addTab": [1], "addAction": [0], "addMenu": [0],
    "addRow": [0], "setLabelText": [0], "LabeledSlider": [0], "ToolGroup": [0, 1], "CategorySelector": [0],
}
# (receiver, method) -> indexes
QUALIFIED = {
    ("QMessageBox", "information"): [1, 2], ("QMessageBox", "warning"): [1, 2],
    ("QMessageBox", "critical"): [1, 2], ("QMessageBox", "question"): [1, 2],
    ("QMessageBox", "about"): [1, 2],
    ("QInputDialog", "getText"): [1, 2], ("QInputDialog", "getInt"): [1, 2],
    ("QFileDialog", "getOpenFileName"): [1, 3], ("QFileDialog", "getSaveFileName"): [1, 3],
    ("QFileDialog", "getExistingDirectory"): [1],
    ("QColorDialog", "getColor"): [2],
}
TEXT_KWARGS = {"tooltip", "text", "title", "label", "placeholder", "description"}
ID_LABEL_CALLS = {"ToolGroup": [1], "CategorySelector": [0]}   # list args that are ALSO dict keys / signal ids
SKIP_DIRS = {"__pycache__", "venv", ".venv", "build", "dist", ".git"}
LETTER = re.compile(r"[^\W\d_]", re.UNICODE)


# --------------------------------------------------------------------------- helpers
def call_info(node):
    f = node.func
    if isinstance(f, ast.Attribute):
        recv = f.value.attr if isinstance(f.value, ast.Attribute) else getattr(f.value, "id", "")
        return f.attr, recv
    return getattr(f, "id", ""), ""


def placeholder_name(expr, used):
    if isinstance(expr, ast.Name):
        base = expr.id
    elif isinstance(expr, ast.Attribute):
        base = expr.attr
    elif isinstance(expr, ast.Subscript) and isinstance(expr.slice, ast.Constant) and isinstance(expr.slice.value, str):
        base = expr.slice.value
    elif isinstance(expr, ast.IfExp):
        base = "choice"
    elif isinstance(expr, ast.Call):
        fn = call_info(expr)[0]
        base = {"len": "count"}.get(fn, fn or "value")
    else:
        base = "value"
    base = re.sub(r"\W", "_", base).strip("_").lower() or "value"
    if base == "key":            # would collide with tr(key, **kwargs)
        base = "key_"
    name, i = base, 2
    while name in used:
        name, i = f"{base}{i}", i + 1
    used.add(name)
    return name


def flatten(node, parts):
    """Append str or ('expr', node) parts; return False if node isn't string-like."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        parts.append(node.value)
        return True
    if isinstance(node, ast.JoinedStr):
        for v in node.values:
            if isinstance(v, ast.Constant):
                parts.append(v.value)
            elif isinstance(v, ast.FormattedValue):
                parts.append(("expr", v.value, v))
        return True
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left, right = [], []
        if flatten(node.left, left) and (flatten(node.right, right) or True):
            parts.extend(left)
            if not right:
                parts.append(("expr", node.right, None))
            else:
                parts.extend(right)
            return any(isinstance(p, str) for p in left + right)
    return False


def _kwarg_source(expr, fv):
    """Python source for the value passed to tr(..., name=<this>), keeping f-string :spec / !r."""
    src = ast.unparse(expr)
    unsafe = False
    if fv is not None:
        conv = {115: "str", 114: "repr", 97: "ascii"}.get(fv.conversion)
        if conv:
            src = f"{conv}({src})"
        if fv.format_spec is not None:
            if all(isinstance(x, ast.Constant) for x in fv.format_spec.values):
                spec = "".join(x.value for x in fv.format_spec.values)
                src = f"format({src}, {spec!r})"
            else:
                unsafe = True
    return src, unsafe


def to_template(node):
    parts = []
    if not flatten(node, parts):
        return None
    if all(isinstance(p, str) for p in parts):          # no placeholders: keep braces untouched
        return "".join(parts), []
    used, out, exprs = set(), [], []
    for p in parts:
        if isinstance(p, str):
            out.append(p.replace("{", "{{").replace("}", "}}"))
        else:
            n = placeholder_name(p[1], used)
            out.append("{" + n + "}")
            src = ast.unparse(p[1])
            kwsrc, unsafe = _kwarg_source(p[1], p[2] if len(p) > 2 else None)
            if isinstance(p[1], ast.IfExp) and any(isinstance(x, ast.Constant) and isinstance(x.value, str)
                                                  for x in (p[1].body, p[1].orelse)):
                src += "   <-- PLACEHOLDER_IS_TEXT: translate these branches as their own keys"
            exprs.append((n, src, kwsrc, unsafe))
    return "".join(out), exprs


def strings_in(arg):
    """Yield AST nodes that are text candidates from an argument (handles lists)."""
    if isinstance(arg, (ast.List, ast.Tuple)):
        for el in arg.elts:
            yield from strings_in(el)
    elif isinstance(arg, ast.IfExp):
        yield from strings_in(arg.body)
        yield from strings_in(arg.orelse)
    else:
        yield arg


def slug(text, n=6):
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    t = re.sub(r"<[^>]+>", " ", text)
    t = re.sub(r"\{(\w+)\}", r" \1 ", t)
    words = re.findall(r"[A-Za-z0-9]+", t.lower())[:n]
    s = "_".join(words)[:40].strip("_")
    return s or "text"


MODULE_PREFIX = {"main_window": "main", "help_system": "help", "project_reset": "reset"}


def module_prefix(path):
    base = os.path.splitext(os.path.basename(path))[0]
    return "app" if base == "main" else MODULE_PREFIX.get(base, base)


# --------------------------------------------------------------------------- extraction
def scan_file(path, rel):
    src = open(path, encoding="utf-8").read()
    tree = ast.parse(src)
    # names used with .currentText() -> combo items double as logic values
    combo_logic = {call_info(n)[1] for n in ast.walk(tree)
                   if isinstance(n, ast.Call) and call_info(n)[0] == "currentText"}
    found, captured = [], set()
    in_func = set()                      # nodes that run at call time (not import/class-definition time)
    for fn in ast.walk(tree):
        if isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for stmt in fn.body:
                in_func.update(id(x) for x in ast.walk(stmt))
        elif isinstance(fn, ast.Lambda):
            in_func.update(id(x) for x in ast.walk(fn.body))
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name, recv = call_info(node)
        idxs = QUALIFIED.get((recv, name)) or SINKS.get(name)
        targets = []
        if idxs:
            for i in idxs:
                if i < len(node.args):
                    targets += [(i, t) for t in strings_in(node.args[i])]
        for kw in node.keywords:
            if kw.arg in TEXT_KWARGS:
                targets.append((-1, kw.value))
        for i, t in targets:
            res = to_template(t)
            if not res:
                continue
            text, exprs = res
            if not LETTER.search(re.sub(r"\{[^}]*\}", "", text)):
                continue
            flags = []
            if exprs:
                flags.append("placeholders")
                if any("PLACEHOLDER_IS_TEXT" in e[1] for e in exprs):
                    flags.append("PLACEHOLDER_IS_TEXT")
            if re.search(r"</?\w+[^>]*>", text):
                flags.append("html")
            if len(text) > 400:
                flags.append("long")
            if "&&" in text:
                flags.append("mnemonic_&&")
            if re.search(r"\[[A-Z]\]", text):
                flags.append("shortcut_in_text")
            if name in ID_LABEL_CALLS and i in ID_LABEL_CALLS[name]:
                flags.append("ID_AND_LABEL")
            if name in ("addItem", "addItems") and recv in combo_logic:
                flags.append("COMBO_VALUE_USED_AS_LOGIC")
            found.append({"text": text, "line": t.lineno, "file": rel, "call": f"{recv + '.' if recv else ''}{name}",
                          "flags": flags, "exprs": exprs, "recv": recv,
                          "pos": (t.lineno, t.col_offset, t.end_lineno, t.end_col_offset),
                          "in_func": id(t) in in_func})
            for sub in ast.walk(t):
                captured.add((getattr(sub, "lineno", 0), getattr(sub, "col_offset", 0)))
    return tree, src, found, captured


NOT_UI_CALLS = {"info", "warning", "error", "debug", "critical", "setStyleSheet", "join", "open", "getattr", "hasattr",
                "setObjectName", "setProperty", "compile", "match", "search", "sub", "findall", "startswith",
                "endswith", "exists", "isfile", "isdir", "makedirs", "listdir", "get", "setdefault", "print"}


def candidates(tree, captured, rel):
    """Strings that look like prose but were not captured by a known sink (manual review)."""
    doc_ids = set()
    for n in ast.walk(tree):
        if isinstance(n, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) and n.body \
                and isinstance(n.body[0], ast.Expr) and isinstance(n.body[0].value, ast.Constant):
            doc_ids.add(id(n.body[0].value))
    skip_ids = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Call) and call_info(n)[0] in NOT_UI_CALLS:
            for s in ast.walk(n):
                skip_ids.add(id(s))
        if isinstance(n, ast.Compare) or isinstance(n, ast.Subscript):
            for s in ast.walk(n):
                skip_ids.add(id(s))
        if isinstance(n, ast.Dict):
            for k in n.keys:
                if k is not None:
                    skip_ids.add(id(k))
    out = []
    for n in ast.walk(tree):
        if isinstance(n, ast.Constant) and isinstance(n.value, str) and id(n) not in doc_ids and id(n) not in skip_ids:
            if (n.lineno, n.col_offset) in captured:
                continue
            v = n.value.strip()
            if len(v) < 6 or not LETTER.search(v) or ":" in v and ";" in v or v.startswith(("#", "/", "\\", "<")):
                continue
            if " " not in v and not v.endswith((".", "!", "?", "...")):
                continue
            out.append((rel, n.lineno, v[:110].replace("\n", "\\n")))
    return sorted(set(out))


def logic_constants(tree):
    """String constants the code COMPARES or uses as dict keys / subscripts. A UI text equal to one
    of these may be logic (e.g. `if btn.text() == "Mask"`), so it must not be translated blindly."""
    out = set()
    def add(n):
        for sub in ast.walk(n):
            if isinstance(sub, ast.Constant) and isinstance(sub.value, str):
                out.add(sub.value)
    for n in ast.walk(tree):
        if isinstance(n, ast.Compare):
            add(n)
        elif isinstance(n, ast.Dict):
            for k in n.keys:
                if k is not None:
                    add(k)
        elif isinstance(n, ast.Subscript):
            add(n.slice)
    return out


def source_files(root):
    files = []
    for dp, dn, fn in os.walk(root):
        dn[:] = sorted(d for d in dn if d not in SKIP_DIRS)
        for f in sorted(fn):
            if f.endswith(".py") and (dp == root and f == "main.py" or os.sep + "src" in dp):
                files.append(os.path.join(dp, f))
    return sorted(files)


def collect(root, existing=None):
    """Scan the tree. `existing` (an en.json dict) keeps already-chosen keys stable.
    Returns entries (each with its "key"), candidates, catalog, sources, meta, logic-constants."""
    existing = existing or {}
    entries, cands, logic = [], [], set()
    for p in source_files(root):
        rel = os.path.relpath(p, root).replace("\\", "/")
        tree, _, found, captured = scan_file(p, rel)
        entries += found
        cands += candidates(tree, captured, rel)
        logic |= logic_constants(tree)

    by_text = OrderedDict()
    for e in entries:
        kind = "label" if "ID_AND_LABEL" in e["flags"] else ("html" if e["call"].endswith("setHtml") else "text")
        by_text.setdefault((kind, e["text"]), []).append(e)
    taken, catalog, sources, meta = {}, OrderedDict(), defaultdict(list), {}
    for (kind, text), es in by_text.items():
        mods = {module_prefix(e["file"]) for e in es}
        prefix = "common" if len(mods) > 1 else next(iter(mods))
        if kind == "label":
            base = f"label.{slug(text)}"
        elif kind == "html":
            base = f"{prefix}.{es[0]['recv'] or slug(text)}_html"
        else:
            base = f"{prefix}.{slug(text)}"
        key, i = base, 2
        while key in taken and taken[key] != text:
            key, i = f"{base}_{i}", i + 1
        if existing.get(key) != text:          # honor a key someone already chose/renamed in en.json
            for k, v in existing.items():
                if v == text and k.startswith("label.") == (kind == "label") and k not in taken:
                    key = k
                    break
        taken[key] = text
        flags = sorted({f for e in es for f in e["flags"]})
        catalog[key] = text
        meta[key] = {"flags": flags, "exprs": es[0]["exprs"]}
        for e in es:
            e["key"] = key
            sources[key].append(f"{e['file']}:{e['line']} ({e['call']})")
    return entries, cands, catalog, sources, meta, logic


def sort_catalog(cat):
    order = {"meta": -1, "common": 0, "label": 1}
    return OrderedDict(sorted(cat.items(), key=lambda kv: (order.get(kv[0].split(".")[0], 2), kv[0])))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".")
    ap.add_argument("--out", default="locales")
    ap.add_argument("--report", default="STRINGS_REPORT.md")
    ap.add_argument("--fresh", action="store_true",
                    help="rebuild en.json from scratch (default: MERGE - keep existing keys/values, add new ones)")
    a = ap.parse_args()
    root = os.path.abspath(a.root)

    en_path = os.path.join(a.out, "en.json")
    existing = {}
    if os.path.isfile(en_path) and not a.fresh:
        existing = json.load(open(en_path, encoding="utf-8-sig"))
    entries, cands, found_cat, sources, meta, _ = collect(root, existing)

    # merge mode: en.json is the source of truth once strings are migrated to tr()
    catalog = OrderedDict((k, v) for k, v in existing.items() if k != "meta.language_name")
    added = [k for k in found_cat if k not in catalog]
    for k in added:
        catalog[k] = found_cat[k]
    catalog = sort_catalog(catalog)

    os.makedirs(a.out, exist_ok=True)
    with open(en_path, "w", encoding="utf-8", newline="\n") as f:
        json.dump({"meta.language_name": "English", **catalog}, f, ensure_ascii=False, indent=2)
        f.write("\n")
    with open(os.path.join(a.out, "en.sources.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump({k: sources[k] for k in found_cat}, f, ensure_ascii=False, indent=2)
        f.write("\n")

    # -------- report (only about strings still present in the code as literals)
    per_mod = defaultdict(int)
    for k in catalog:
        per_mod[k.split(".")[0]] += 1
    flagged = lambda fl: [(k, meta[k]) for k in found_cat if fl in meta[k]["flags"]]
    L = ["# UI strings report (auto-generated)", "",
         f"- Call sites with visible text still hard-coded: **{len(entries)}**",
         f"- Keys in `en.json`: **{len(catalog)}** (new this run: {len(added)})",
         f"- Reused across modules (`common.*`): **{per_mod.get('common', 0)}**",
         f"- Labels of internal IDs (`label.*`, see section 1): **{per_mod.get('label', 0)}**", "",
         "| Module | Keys |", "| :--- | ---: |"]
    L += [f"| `{m}` | {c} |" for m, c in sorted(per_mod.items(), key=lambda x: -x[1])]

    L += ["", "## 1. Needs code changes BEFORE translating (logic depends on the text)", ""]
    for title, fl, why in (
        ("ID_AND_LABEL", "ID_AND_LABEL", "The same string is the visible label AND a dict key / signal value. Translating it breaks the logic. Split into (id, label)."),
        ("COMBO_VALUE_USED_AS_LOGIC", "COMBO_VALUE_USED_AS_LOGIC", "Combo items whose `currentText()` is read by the code. Use `addItem(label, userData)` + `currentData()`."),
    ):
        items = flagged(fl)
        L.append(f"### {title} ({len(items)})\n{why}\n")
        for k, _ in items:
            L.append(f"- `{k}` = {json.dumps(catalog[k], ensure_ascii=False)}  \n  {sources[k][0]}")
        L.append("")

    L += ["## 2. Strings with placeholders (use named `{fields}`, never concatenation)", ""]
    for k, m in flagged("placeholders"):
        ex = ", ".join(f"`{e[0]}` = `{e[1]}`" for e in m["exprs"])
        L.append(f"- `{k}`: {json.dumps(catalog[k], ensure_ascii=False)}  \n  {ex}  — {sources[k][0]}")
    L += ["", "### Placeholders that are themselves translatable text", ""]
    for k, m in flagged("PLACEHOLDER_IS_TEXT"):
        L.append(f"- `{k}` — {sources[k][0]}")
    L += ["", "## 3. HTML / long blocks (consider one file per language, not JSON values)", ""]
    for k, m in flagged("html"):
        L.append(f"- `{k}` ({len(catalog[k])} chars{', long' if 'long' in m['flags'] else ''}) — {sources[k][0]}")
    L += ["", "## 4. Shortcut hints inside labels (translators must keep the key letter)", ""]
    for k, _ in flagged("shortcut_in_text"):
        L.append(f"- `{k}` = {json.dumps(catalog[k], ensure_ascii=False)}")
    L += ["", "## 5. Possible UI text NOT captured (review by hand)", "",
          "Prose-like string constants outside the known Qt sinks (assigned to variables, returned from helpers, etc.).", ""]
    for rel, ln, v in cands:
        L.append(f"- {rel}:{ln}  `{v}`")
    open(a.report, "w", encoding="utf-8", newline="\n").write("\n".join(L) + "\n")
    print(f"strings still hard-coded: {len(entries)} sites | keys in en.json: {len(catalog)} (+{len(added)} new) | candidates to review: {len(cands)} | wrote {en_path}, {a.report}")


if __name__ == "__main__":
    sys.exit(main())