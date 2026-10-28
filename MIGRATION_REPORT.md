# tr() migration report - DRY RUN (nothing was written)

- Strings rewritten: **217**
- Strings left untouched (need a human): **29**
- New keys added to en.json: **0**

## Per file

| File | Rewritten | Left |
| :--- | ---: | ---: |
| `src/backend/stitcher.py` | 48 | 3 |
| `src/backend/translator.py` | 57 | 1 |
| `src/frontend/help_system.py` | 14 | 0 |
| `src/frontend/main_window.py` | 96 | 25 |
| `src/frontend/widgets.py` | 2 | 0 |

## ID_AND_LABEL (15)
Visible label AND internal id. Use tr_label(id) for the button; keep the id.

- `src/frontend/main_window.py:255`  "CLEANER"
- `src/frontend/main_window.py:255`  "STITCHER"
- `src/frontend/main_window.py:255`  "TRANSLATOR"
- `src/frontend/main_window.py:255`  "TYPESETTER"
- `src/frontend/main_window.py:271`  "BRUSH"
- `src/frontend/main_window.py:271`  "BUCKET"
- `src/frontend/main_window.py:271`  "CLEAR"
- `src/frontend/main_window.py:271`  "ERASER"
- `src/frontend/main_window.py:271`  "LASSO"
- `src/frontend/main_window.py:271`  "MANUAL"
- `src/frontend/main_window.py:271`  "MOVE"
- `src/frontend/main_window.py:271`  "POLY"
- `src/frontend/main_window.py:271`  "RECT"
- `src/frontend/main_window.py:354`  "MOVE"
- `src/frontend/main_window.py:354`  "TEXT"

## COMBO_VALUE_USED_AS_LOGIC (11)
Combo item whose currentText() drives logic. Switch to addItem(label, id) + currentData().

- `src/backend/stitcher.py:302`  "JPG (100% Quality 4:4:4)"
- `src/backend/stitcher.py:302`  "PNG (100% Lossless)"
- `src/frontend/main_window.py:1669`  "Mask"
- `src/frontend/main_window.py:1669`  "OCR Scan"
- `src/frontend/main_window.py:1669`  "Transparency Scan"
- `src/frontend/main_window.py:1669`  "none"
- `src/frontend/main_window.py:1673`  "jpg"
- `src/frontend/main_window.py:1673`  "none"
- `src/frontend/main_window.py:1673`  "photopea"
- `src/frontend/main_window.py:1673`  "photoshop"
- `src/frontend/main_window.py:1673`  "png"

## PLACEHOLDER_IS_TEXT (2)
An f-string embeds translatable words. Give each branch its own key.

- `src/backend/translator.py:506`  "Matched by: {choice}\nQueued {total_lines} dialogue lines across {queued_pages} pages.\n{unm"
- `src/frontend/main_window.py:1655`  "{choice} | RAM: {ram}MB"

## TEXT_USED_IN_LOGIC (1)
The same text is compared / used as a dict key somewhere. Check before translating.

- `src/backend/stitcher.py:264`  "CLEAR"

