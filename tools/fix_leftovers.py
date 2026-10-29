#!/usr/bin/env python3
"""
One-shot helper: finishes the strings that migrate_to_tr.py deliberately did not touch
(f-strings that embed translatable words, a few helper messages) and adds their keys to
locales/en.json and locales/es.json.

    python tools/fix_leftovers.py            # dry run: says what it would change
    python tools/fix_leftovers.py --apply    # writes the files

Safe to run twice: replacements already applied are reported as "already done".
A replacement whose old text is not found is reported as "NOT FOUND" (the file differs from what
this script expects) and nothing is changed for that item.
"""
import argparse
import json
import os
import sys

MW = "src/frontend/main_window.py"
ST = "src/backend/stitcher.py"
TR = "src/backend/translator.py"

# (file, old, new)
REPLACEMENTS = [
    # --- main_window: category label shows the translated name; RAM label via the existing key
    (MW, 'from src.utils.i18n import tr\n', 'from src.utils.i18n import tr, tr_label\n'),
    (MW, 'tr("main.category_category", category=category)',
         'tr("main.category_category", category=tr_label(category))'),
    (MW, '''self.hw_mon.lbl.setText(f"{'GPU' if gpu else 'CPU'} | RAM: {ram}MB")''',
         '''self.hw_mon.lbl.setText(tr("main.choice_ram_ram_mb", choice='GPU' if gpu else 'CPU', ram=ram))'''),
    # --- stitcher
    (ST, 'QPushButton("CLEAR")', 'QPushButton(tr("stitcher.clear"))'),
    (ST, 'desc = f"{names[0]} (1 page)"', 'desc = tr("stitcher.one_page_desc", name=names[0])'),
    (ST, 'desc = f"{names[0]} .. {names[-1]} ({len(names)} pages)"',
         'desc = tr("stitcher.page_range_desc", first=names[0], last=names[-1], count=len(names))'),
    (ST, 'QProgressDialog("Stitching blocks losslessly...", "Cancel",',
         'QProgressDialog(tr("stitcher.stitching_blocks_losslessly"), tr("common.cancel"),'),
    # --- translator
    (TR, '''                "Could not find <translation> ... </translation> tags in the selected file.\\n"
                "Please ensure the tags were not modified or deleted."
''', '''                tr("translator.tags_not_found")
'''),
    (TR, '''unmatched.append(f"Image {entry.get('index')} [{raw_fname}]")''',
         '''unmatched.append(tr("translator.unmatched_image_named", index=entry.get('index'), fname=raw_fname))'''),
    (TR, '''unmatched.append(f"Image {entry.get('index')} [missing brackets]")''',
         '''unmatched.append(tr("translator.unmatched_missing_brackets", index=entry.get('index')))'''),
    (TR, 'mode_str = "[filename]" if use_brackets else "Order"',
         'mode_str = tr("translator.mode_filename") if use_brackets else tr("translator.mode_order")'),
    (TR, '''preview_unmatched += f" (+{len(unmatched) - 5} more)"''',
         '''preview_unmatched += tr("translator.n_more", n=len(unmatched) - 5)'''),
    (TR, '''unmatched_msg = f"\\n⚠️ Unmatched pages ({len(unmatched)}): {preview_unmatched}\\n"''',
         '''unmatched_msg = tr("translator.unmatched_pages", count=len(unmatched), preview=preview_unmatched)'''),
    (TR, '''                f"Matched by: {'[filename] brackets' if use_brackets else 'Image Order'}\\n"
                f"Queued {total_lines} dialogue lines across {queued_pages} pages.\\n"
                f"{unmatched_msg}\\n"
                f"In TYPESETTER -> PAGE TEXT LAYERS, simply click any '[ + ]' line to spawn it on the canvas!"
''', '''                tr("translator.matched_by_choice_queued_total_lines",
                   choice=tr("translator.match_by_brackets") if use_brackets else tr("translator.match_by_order"),
                   total_lines=total_lines, queued_pages=queued_pages, unmatched_msg=unmatched_msg)
'''),
]

EN = {
    "common.cancel": "Cancel",
    "stitcher.one_page_desc": "{name} (1 page)",
    "stitcher.page_range_desc": "{first} .. {last} ({count} pages)",
    "stitcher.stitching_blocks_losslessly": "Stitching blocks losslessly...",
    "translator.tags_not_found": "Could not find <translation> ... </translation> tags in the selected file.\nPlease ensure the tags were not modified or deleted.",
    "translator.unmatched_image_named": "Image {index} [{fname}]",
    "translator.unmatched_missing_brackets": "Image {index} [missing brackets]",
    "translator.mode_filename": "[filename]",
    "translator.mode_order": "Order",
    "translator.n_more": " (+{n} more)",
    "translator.unmatched_pages": "\n⚠️ Unmatched pages ({count}): {preview}\n",
    "translator.match_by_brackets": "[filename] brackets",
    "translator.match_by_order": "Image Order",
}
ES = {
    "common.cancel": "Cancelar",
    "stitcher.one_page_desc": "{name} (1 página)",
    "stitcher.page_range_desc": "{first} .. {last} ({count} páginas)",
    "stitcher.stitching_blocks_losslessly": "Uniendo bloques sin pérdida...",
    "translator.tags_not_found": "No se encontraron las etiquetas <translation> ... </translation> en el archivo seleccionado.\nAsegúrate de que las etiquetas no se hayan modificado ni eliminado.",
    "translator.unmatched_image_named": "Imagen {index} [{fname}]",
    "translator.unmatched_missing_brackets": "Imagen {index} [sin corchetes]",
    "translator.mode_filename": "[nombre de archivo]",
    "translator.mode_order": "Orden",
    "translator.n_more": " (+{n} más)",
    "translator.unmatched_pages": "\n⚠️ Páginas sin asociar ({count}): {preview}\n",
    "translator.match_by_brackets": "corchetes [nombre de archivo]",
    "translator.match_by_order": "orden de imágenes",
}


def read(path):
    with open(path, "r", encoding="utf-8", newline="") as f:
        return f.read()


def write(path, text):
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(text)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".")
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()
    root = a.root
    problems = 0

    by_file = {}
    for rel, old, new in REPLACEMENTS:
        by_file.setdefault(rel, []).append((old, new))
    for rel, items in by_file.items():
        path = os.path.join(root, rel)
        src = read(path)
        crlf = "\r\n" in src
        work = src.replace("\r\n", "\n") if crlf else src
        for old, new in items:
            label = old.strip().splitlines()[0][:70]
            if old in work:
                if work.count(old) != 1:
                    print(f"  AMBIGUOUS ({work.count(old)}x) {rel}: {label}")
                    problems += 1
                    continue
                work = work.replace(old, new)
                print(f"  ok        {rel}: {label}")
            elif new in work:
                print(f"  already   {rel}: {label}")
            else:
                print(f"  NOT FOUND {rel}: {label}")
                problems += 1
        if crlf:
            work = work.replace("\n", "\r\n")
        if a.apply and work != src:
            write(path, work)

    for name, extra in (("en.json", EN), ("es.json", ES)):
        path = os.path.join(root, "locales", name)
        data = json.loads(read(path).lstrip("﻿"))
        added = [k for k in extra if k not in data]
        data.update({k: v for k, v in extra.items() if k not in data})
        print(f"  {name}: +{len(added)} key(s)")
        if a.apply and added:
            write(path, json.dumps(data, ensure_ascii=False, indent=2) + "\n")

    print("\nAPPLIED" if a.apply else "\nDRY RUN (use --apply to write)", "| problems:", problems)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())