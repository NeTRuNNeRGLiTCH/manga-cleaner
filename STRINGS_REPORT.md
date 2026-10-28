# UI strings report (auto-generated)

- Call sites with visible text: **255**
- Unique strings (keys in `en.json`): **238**
- Reused across modules (`common.*`): **1**
- Labels of internal IDs (`label.*`, see section 1): **14**

| Module | Keys |
| :--- | ---: |
| `main` | 101 |
| `translator` | 52 |
| `stitcher` | 48 |
| `label` | 14 |
| `help` | 14 |
| `reset` | 6 |
| `widgets` | 2 |
| `common` | 1 |

## 1. Needs code changes BEFORE translating (logic depends on the text)

### ID_AND_LABEL (14)
The same string is the visible label AND a dict key / signal value. Translating it breaks the logic. Split into (id, label).

- `label.brush` = "BRUSH"  
  src/frontend/main_window.py:270 (ToolGroup)
- `label.bucket` = "BUCKET"  
  src/frontend/main_window.py:270 (ToolGroup)
- `label.cleaner` = "CLEANER"  
  src/frontend/main_window.py:254 (CategorySelector)
- `label.clear` = "CLEAR"  
  src/frontend/main_window.py:270 (ToolGroup)
- `label.eraser` = "ERASER"  
  src/frontend/main_window.py:270 (ToolGroup)
- `label.lasso` = "LASSO"  
  src/frontend/main_window.py:270 (ToolGroup)
- `label.manual` = "MANUAL"  
  src/frontend/main_window.py:270 (ToolGroup)
- `label.move` = "MOVE"  
  src/frontend/main_window.py:270 (ToolGroup)
- `label.poly` = "POLY"  
  src/frontend/main_window.py:270 (ToolGroup)
- `label.rect` = "RECT"  
  src/frontend/main_window.py:270 (ToolGroup)
- `label.stitcher` = "STITCHER"  
  src/frontend/main_window.py:254 (CategorySelector)
- `label.text` = "TEXT"  
  src/frontend/main_window.py:353 (ToolGroup)
- `label.translator` = "TRANSLATOR"  
  src/frontend/main_window.py:254 (CategorySelector)
- `label.typesetter` = "TYPESETTER"  
  src/frontend/main_window.py:254 (CategorySelector)

### COMBO_VALUE_USED_AS_LOGIC (10)
Combo items whose `currentText()` is read by the code. Use `addItem(label, userData)` + `currentData()`.

- `main.jpg` = "jpg"  
  src/frontend/main_window.py:1672 (export_fmt.addItems)
- `main.mask` = "Mask"  
  src/frontend/main_window.py:1668 (scan_mode.addItems)
- `main.none` = "none"  
  src/frontend/main_window.py:1668 (scan_mode.addItems)
- `main.ocr_scan` = "OCR Scan"  
  src/frontend/main_window.py:1668 (scan_mode.addItems)
- `main.photopea` = "photopea"  
  src/frontend/main_window.py:1672 (export_fmt.addItems)
- `main.photoshop` = "photoshop"  
  src/frontend/main_window.py:1672 (export_fmt.addItems)
- `main.png` = "png"  
  src/frontend/main_window.py:1672 (export_fmt.addItems)
- `main.transparency_scan` = "Transparency Scan"  
  src/frontend/main_window.py:1668 (scan_mode.addItems)
- `stitcher.jpg_100_quality_4_4_4` = "JPG (100% Quality 4:4:4)"  
  src/backend/stitcher.py:302 (fmt_combo.addItems)
- `stitcher.png_100_lossless` = "PNG (100% Lossless)"  
  src/backend/stitcher.py:302 (fmt_combo.addItems)

## 2. Strings with placeholders (use named `{fields}`, never concatenation)

- `help.tab_hardware_html`: "<h3 style='color: #00d4ff;'>💻 System Diagnostics & Performance</h3><p><b>Compute Engine Found:</b> {engine}</p><p><b>System RAM Detected:</b> {ram} GB</p><hr><h4>Memory & GPU Optimizations</h4><ul><li><b>VRAM Tiling:</b> AI Inpainting processes patches in configurable chunks (<i>Max Tile Size</i> slider) to prevent GPU out-of-memory crashes on high-resolution webtoons.</li><li><b>Model Persistence:</b> During batch operations, ONNX/CUDA models remain warm in memory to maximize throughput.</li><li><b>Lazy Script Queue:</b> Importing <code>.txt</code> translation scripts across 100+ pages stores only lightweight UTF-8 strings in memory until each page is actively opened.</li></ul>"  
  `engine` = `specs['engine']`, `ram` = `specs['ram']`  — src/frontend/help_system.py:174 (tab_hardware.setHtml)
- `main.app_name_v_version`: "{app_name} v{version}"  
  `app_name` = `Config.APP_NAME`, `version` = `Config.VERSION`  — src/frontend/main_window.py:52 (self.setWindowTitle)
- `main.category_category`: "CATEGORY: {category}"  
  `category` = `category`  — src/frontend/main_window.py:697 (cat_lbl.setText)
- `main.choice_ram_ram_mb`: "{choice} | RAM: {ram}MB"  
  `choice` = `'GPU' if gpu else 'CPU'   <-- PLACEHOLDER_IS_TEXT: translate these branches as their own keys`, `ram` = `ram`  — src/frontend/main_window.py:1654 (lbl.setText)
- `main.click_to_place_on_canvas_with`: "Click to place on canvas with current font:\n{text_str}"  
  `text_str` = `text_str`  — src/frontend/main_window.py:879 (list_item.setToolTip)
- `main.could_not_send_to_capitalize_res`: "Could not send to {capitalize}:\n{res}\n\nCheck your logs folder for details."  
  `capitalize` = `target.capitalize()`, `res` = `res`  — src/frontend/main_window.py:1650 (QMessageBox.warning)
- `main.enter_custom_alias_for_fam_leave`: "Enter custom alias for '{fam}'\n(Leave empty to restore default name):"  
  `fam` = `fam`  — src/frontend/main_window.py:678 (QInputDialog.getText)
- `main.page_text_layers_placed_count_placed`: "PAGE TEXT LAYERS ({placed_count} Placed | {pending_count} Queued)"  
  `placed_count` = `placed_count`, `pending_count` = `pending_count`  — src/frontend/main_window.py:855 (lbl_text_layers.setText)
- `main.processing_queued_pending`: "Processing / Queued: {pending}"  
  `pending` = `pending`  — src/frontend/main_window.py:1202 (queue_lbl.setText)
- `main.saved_to_output_dir`: "Saved to: {output_dir}"  
  `output_dir` = `self.batch_engine.output_dir`  — src/frontend/main_window.py:1514 (QMessageBox.information)
- `main.the_file_is_corrupted_or_cannot`: "The file is corrupted or cannot be processed:\n{basename}"  
  `basename` = `os.path.basename(path_real)`  — src/frontend/main_window.py:1597 (QMessageBox.warning)
- `main.there_are_total_pending_lines_unplaced`: "There are {total_pending_lines} unplaced '[ + ]' dialogue line(s) across {count} page(s):\n{preview}\n\nUnplaced lines in the queue will NOT be rendered onto the exported image.\nDo you want to continue anyway?"  
  `total_pending_lines` = `total_pending_lines`, `count` = `len(pages_with_pending)`, `preview` = `preview`  — src/frontend/main_window.py:1400 (QMessageBox.warning)
- `stitcher.2_stitch_queue_total_outputs_files`: "2. STITCH QUEUE ({total_outputs} FILES) — Double-click to rename"  
  `total_outputs` = `total_outputs`  — src/backend/stitcher.py:383 (lbl_queue.setText)
- `stitcher.an_error_occurred_while_stitching_e`: "An error occurred while stitching:\n{e}"  
  `e` = `e`  — src/backend/stitcher.py:628 (QMessageBox.critical)
- `stitcher.successfully_exported_saved_count_lossle`: "Successfully exported {saved_count} lossless stitched files to:\n{out_dir}"  
  `saved_count` = `saved_count`, `out_dir` = `out_dir`  — src/backend/stitcher.py:624 (QMessageBox.information)
- `translator.3_fname_queued_count`: "3. [{fname}] QUEUED ({count})"  
  `fname` = `fname`, `count` = `len(lines)`  — src/backend/translator.py:588 (lbl_page_lines.setText)
- `translator.could_not_save_template_e`: "Could not save template:\n{e}"  
  `e` = `e`  — src/backend/translator.py:437 (QMessageBox.critical)
- `translator.created_translation_template_for_count_i`: "Created translation template for {count} images:\n{save_path}"  
  `count` = `len(paths)`, `save_path` = `save_path`  — src/backend/translator.py:433 (QMessageBox.information)
- `translator.loaded_mode_str_basename_total_lines`: "Loaded ({mode_str}): {basename} ({total_lines} lines / {pages_with_text} pages)"  
  `mode_str` = `mode_str`, `basename` = `os.path.basename(open_path)`, `total_lines` = `total_lines`, `pages_with_text` = `pages_with_text`  — src/backend/translator.py:488 (lbl_script_status.setText)
- `translator.matched_by_choice_queued_total_lines`: "Matched by: {choice}\nQueued {total_lines} dialogue lines across {queued_pages} pages.\n{unmatched_msg}\nIn TYPESETTER -> PAGE TEXT LAYERS, simply click any '[ + ]' line to spawn it on the canvas!"  
  `choice` = `'[filename] brackets' if use_brackets else 'Image Order'   <-- PLACEHOLDER_IS_TEXT: translate these branches as their own keys`, `total_lines` = `total_lines`, `queued_pages` = `queued_pages`, `unmatched_msg` = `unmatched_msg`  — src/backend/translator.py:506 (QMessageBox.information)
- `widgets.base_label_value_px`: "{base_label}: {value}px"  
  `base_label` = `self.base_label`, `value` = `val * 512`  — src/frontend/widgets.py:216 (display.setText)

### Placeholders that are themselves translatable text

- `main.choice_ram_ram_mb` — src/frontend/main_window.py:1654 (lbl.setText)
- `translator.matched_by_choice_queued_total_lines` — src/backend/translator.py:506 (QMessageBox.information)

## 3. HTML / long blocks (consider one file per language, not JSON values)

- `help.tab_cleaner_html` (1199 chars, long) — src/frontend/help_system.py:65 (tab_cleaner.setHtml)
- `help.tab_hardware_html` (687 chars, long) — src/frontend/help_system.py:174 (tab_hardware.setHtml)
- `help.tab_shortcuts_html` (2807 chars, long) — src/frontend/help_system.py:24 (tab_shortcuts.setHtml)
- `help.tab_stitch_batch_html` (1613 chars, long) — src/frontend/help_system.py:148 (tab_stitch_batch.setHtml)
- `help.tab_translator_html` (2364 chars, long) — src/frontend/help_system.py:118 (tab_translator.setHtml)
- `help.tab_typesetter_html` (1890 chars, long) — src/frontend/help_system.py:89 (tab_typesetter.setHtml)

## 4. Shortcut hints inside labels (translators must keep the key letter)

- `help.tab_cleaner_html` = "<h3 style='color: #00d4ff;'>🧹 Cleaner Workspace & Manual Brush</h3><p>The <b>CLEANER</b> category provides two complementary ways to clean pages:</p><h4>1. AI Inpainting Mask (Red / Cyan Overlay)</h4><ul><li>Use <b>OCR SCAN [O]</b> or <b>TRANSPARENCY SCAN [T]</b> to automatically highlight text or transparent regions, or paint masks manually with <b>BRUSH</b>, <b>RECT</b>, <b>LASSO</b>, <b>POLY</b>, and <b>BUCKET</b>.</li><li>Hold <b>[Alt]</b> with any mask tool to erase mask areas (shown in Cyan).</li><li>Press <b>EXECUTE CLEAN [C]</b> to run LaMa AI inpainting on the masked regions.</li></ul><h4>2. Manual Cleaner Brush (<code>MANUAL [D]</code> & <code>PICKER [I]</code>)</h4><ul><li>Designed for quick touch-ups inside flat speech bubbles or backgrounds where AI is unnecessary.</li><li>Click <b>MANUAL</b> to reveal the contextual color bar containing <b>PICKER [I]</b>, the <b>Color Swatch</b>, and the quick <b>White</b> reset button.</li><li>While in <b>MANUAL</b> mode, hold <b>[Alt] + Left-Click</b> anywhere on the canvas to sample a color on the fly.</li><li>Pressing <b>Ctrl + Z</b> while in Manual mode safely undoes your painted image strokes without losing your work.</li></ul>"
- `help.tab_shortcuts_html` = "<h3 style='color: #00d4ff;'>⌨️ Keyboard & Mouse Shortcuts</h3><p><i>Note: Single-key shortcuts are automatically paused while typing inside a text box.</i></p><table border='0' cellpadding='5' width='100%'><tr><td colspan='2'><b style='color: #00d4ff;'>— AI & Scanning —</b></td></tr><tr><td width='38%'><b>[O]</b></td><td>Auto-Detect Text Bubbles (OCR Scan)</td></tr><tr><td><b>[T]</b></td><td>Auto-Detect Transparent Areas</td></tr><tr><td><b>[C]</b></td><td>Execute AI Clean (LaMa Inpainting)</td></tr><tr><td colspan='2'><hr></td></tr><tr><td colspan='2'><b style='color: #00d4ff;'>— Workspace Tools —</b></td></tr><tr><td><b>[M]</b></td><td>Move / Pan Canvas Tool</td></tr><tr><td><b>[B] / [E]</b></td><td>Mask Brush / Mask Eraser</td></tr><tr><td><b>[R] / [L] / [P]</b></td><td>Rectangle / Lasso / Polygon Mask Tools</td></tr><tr><td><b>[G]</b></td><td>Bucket Fill Tool (Fills or erases contiguous mask areas)</td></tr><tr><td><b>[D]</b></td><td><b>Manual Cleaner Brush</b> (Paints directly onto page image)</td></tr><tr><td><b>[I]</b></td><td><b>Eyedropper Color Picker</b> (Samples pixel color from page)</td></tr><tr><td><b>[X]</b></td><td><b>Typesetter Tool</b> (Switches to TYPESETTER & activates Text mode)</td></tr><tr><td colspan='2'><hr></td></tr><tr><td colspan='2'><b style='color: #00d4ff;'>— Canvas & Gizmo Modifiers —</b></td></tr><tr><td><b>[Shift] + Click</b></td><td>Draw straight line between brush points (Mask & Manual Brush)</td></tr><tr><td><b>Double-Click</b></td><td>Commit Polygonal Selection / Edit existing Text Box</td></tr><tr><td><b>Alt + Right-Click Drag</b></td><td><b>Dynamically Resize Brush</b> (Left: Smaller, Right: Bigger)</td></tr><tr><td><b>Hold [Alt]</b></td><td><b>Quick Toggle:</b> Erase Mode (Mask tools) or Eyedropper (Manual Brush)</td></tr><tr><td><b>Hold [Space]</b></td><td><b>Quick Pan:</b> Temporarily switch to Hand Move tool</td></tr><tr><td><b>Alt + Mouse Wheel</b></td><td>Zoom In / Zoom Out at cursor position</td></tr><tr><td><b>Ctrl + Mouse Wheel</b></td><td>Scale selected Text Box font size dynamically</td></tr><tr><td><b>Ctrl + Shift + Wheel</b></td><td>Rotate selected Text Box in 5° steps</td></tr><tr><td><b>[Delete] / Right-Click</b></td><td>Delete selected Text Box (returns script lines to <code>[ + ]</code> queue)</td></tr><tr><td colspan='2'><hr></td></tr><tr><td colspan='2'><b style='color: #00d4ff;'>— History (Undo / Redo) —</b></td></tr><tr><td><b>[Ctrl + Z]</b></td><td><b>Smart Undo:</b> Undoes Image stroke in <b>MANUAL</b> mode, or Mask stroke otherwise</td></tr><tr><td><b>[Ctrl + Shift + Z]</b></td><td><b>Smart Redo:</b> Redoes Image stroke in <b>MANUAL</b> mode, or Mask stroke otherwise</td></tr><tr><td><b>[Alt + Z] / [Alt + Shift + Z]</b></td><td>Explicit Undo / Redo for AI Clean & Image patches</td></tr></table>"
- `help.tab_typesetter_html` = "<h3 style='color: #00d4ff;'>🔤 Typesetter & Font Manager</h3><p>Switch to the <b>TYPESETTER</b> category (or press <b>[X]</b>) to access a dedicated, clutter-free typesetting studio.</p><h4>1. Font Manager, Favorites & Aliases</h4><ul><li><b>Search & Filter:</b> Filter system fonts by name or custom alias in real time.</li><li><b>★ Only:</b> Toggle to display only your favorite scanlation fonts. This state and your last used font are automatically saved in <code>font_presets.json</code>.</li><li><b>Favorite (★) & Rename Alias (✎):</b> Assign custom use-case names (e.g., <i>★ Shout [Wild Words]</i>) while keeping the real font family visible in brackets.</li></ul><h4>2. Interactive Transform Gizmo</h4><ul><li><b>Smooth Center-Locked Scaling:</b> Corner handles scale font size proportionally with stabilized sensitivity without drifting away from the dialogue bubble.</li><li><b>Cyan Side Handles (L / R):</b> Drag horizontally to set a fixed word-wrap width aligned with the text's active rotation. Click <b>Fit Box</b> to reset to auto-width.</li><li><b>Top Cyan Circle:</b> Drag to rotate text freely around its fixed center (hold <b>Shift</b> to snap to 15° angles, or click <b>0°</b> to reset).</li></ul><h4>3. Outer Stroke & Page Text Layers</h4><ul><li>Click the <b>Fill</b> or <b>Stroke</b> color swatches to pick colors, or click <b>⇄</b> to swap them in one click.</li><li>Toggle <b>Mode: Stroke (Outside)</b> to enable a clean vector outer outline with adjustable pixel <b>Size</b> and <b>Opacity</b>.</li><li><b>PAGE TEXT LAYERS & Show Outlines:</b> Lists all placed boxes (<code>[ ✓ ]</code>) and queued script lines (<code>[ + ]</code>).</li><li><b>Show Outlines Checkbox:</b> Enable to display subtle cyan dashed borders around unselected text boxes to easily spot misplaced text on dark backgrounds; uncheck for an instant, clean preview of the final page.</li></ul>"
- `main.execute_clean_c` = "EXECUTE CLEAN [C]"
- `main.eyedropper_color_picker_i_click_on` = "Eyedropper Color Picker [I] - Click on page to sample color"
- `main.manual_cleaner_brush_d_paint_directly` = "Manual Cleaner Brush [D] - Paint directly on page (Ctrl+Z to Undo)"
- `main.ocr_scan_o` = "OCR SCAN [O]"
- `main.picker_i` = "PICKER [I]"
- `main.transparency_scan_t` = "TRANSPARENCY SCAN [T]"

## 5. Possible UI text NOT captured (review by hand)

Prose-like string constants outside the known Qt sinks (assigned to variables, returned from helpers, etc.).

- main.py:18  `Point size <= 0`
- main.py:50  `Segoe UI`
- src/backend/batch_engine.py:50  `_cleaned.`
- src/backend/photoshop.py:15  `Photoshop Bridge is only available on Windows.`
- src/backend/photoshop.py:50  `Could not establish a COM connection to Adobe Photoshop. Ensure Photoshop is installed.`
- src/backend/stitcher.py:390  `(1 page)`
- src/backend/stitcher.py:578  `Stitching blocks losslessly...`
- src/backend/translator.py:79  `Could not find <translation> ... </translation> tags in the selected file.\nPlease ensure the tags were not mod`
- src/backend/translator.py:387  `[missing brackets]`
- src/backend/translator.py:501  `⚠️ Unmatched pages (`
- src/utils/config.py:10  `MANGA-CLEANER STUDIO`
- src/utils/logger.py:29  `%(asctime)s | %(levelname)-8s | %(message)s`
- src/utils/system_info.py:31  `CPU ONLY (Slow Mode)`
- src/utils/system_info.py:34  `NVIDIA CUDA (High Speed)`
