from PySide6.QtWidgets import QDialog, QVBoxLayout, QTabWidget, QTextEdit, QPushButton
from src.utils.system_info import SystemMonitor

#/////////////////////////////////#
#    STUDIO KNOWLEDGE BASE        #
#/////////////////////////////////#

class HelpSystem(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Manga-Cleaner Studio Manual")
        self.resize(740, 560)
        self.setStyleSheet("background-color: #121217; color: #e0e0e0; font-family: 'Segoe UI';")
        
        layout = QVBoxLayout(self)
        tabs = QTabWidget()
        
        # ==========================================
        # TAB 1: KEYBOARD SHORTCUTS
        # ==========================================
        tab_shortcuts = QTextEdit()
        tab_shortcuts.setReadOnly(True)
        tab_shortcuts.setHtml(
            "<h3 style='color: #00d4ff;'>⌨️ Keyboard & Mouse Shortcuts</h3>"
            "<p><i>Note: Single-key shortcuts are automatically paused while typing inside a text box.</i></p>"
            "<table border='0' cellpadding='5' width='100%'>"
            "<tr><td colspan='2'><b style='color: #00d4ff;'>— AI & Scanning —</b></td></tr>"
            "<tr><td width='38%'><b>[O]</b></td><td>Auto-Detect Text Bubbles (OCR Scan)</td></tr>"
            "<tr><td><b>[T]</b></td><td>Auto-Detect Transparent Areas</td></tr>"
            "<tr><td><b>[C]</b></td><td>Execute AI Clean (LaMa Inpainting)</td></tr>"
            "<tr><td colspan='2'><hr></td></tr>"
            "<tr><td colspan='2'><b style='color: #00d4ff;'>— Workspace Tools —</b></td></tr>"
            "<tr><td><b>[M]</b></td><td>Move / Pan Canvas Tool</td></tr>"
            "<tr><td><b>[B] / [E]</b></td><td>Mask Brush / Mask Eraser</td></tr>"
            "<tr><td><b>[R] / [L] / [P]</b></td><td>Rectangle / Lasso / Polygon Mask Tools</td></tr>"
            "<tr><td><b>[G]</b></td><td>Bucket Fill Tool (Fills or erases contiguous mask areas)</td></tr>"
            "<tr><td><b>[D]</b></td><td><b>Manual Cleaner Brush</b> (Paints directly onto page image)</td></tr>"
            "<tr><td><b>[I]</b></td><td><b>Eyedropper Color Picker</b> (Samples pixel color from page)</td></tr>"
            "<tr><td><b>[X]</b></td><td><b>Typesetter Tool</b> (Switches to TYPESETTER & activates Text mode)</td></tr>"
            "<tr><td colspan='2'><hr></td></tr>"
            "<tr><td colspan='2'><b style='color: #00d4ff;'>— Canvas & Gizmo Modifiers —</b></td></tr>"
            "<tr><td><b>[Shift] + Click</b></td><td>Draw straight line between brush points (Mask & Manual Brush)</td></tr>"
            "<tr><td><b>Double-Click</b></td><td>Commit Polygonal Selection / Edit existing Text Box</td></tr>"
            "<tr><td><b>Alt + Right-Click Drag</b></td><td><b>Dynamically Resize Brush</b> (Left: Smaller, Right: Bigger)</td></tr>"
            "<tr><td><b>Hold [Alt]</b></td><td><b>Quick Toggle:</b> Erase Mode (Mask tools) or Eyedropper (Manual Brush)</td></tr>"
            "<tr><td><b>Hold [Space]</b></td><td><b>Quick Pan:</b> Temporarily switch to Hand Move tool</td></tr>"
            "<tr><td><b>Alt + Mouse Wheel</b></td><td>Zoom In / Zoom Out at cursor position</td></tr>"
            "<tr><td><b>Ctrl + Mouse Wheel</b></td><td>Scale selected Text Box font size dynamically</td></tr>"
            "<tr><td><b>Ctrl + Shift + Wheel</b></td><td>Rotate selected Text Box in 5° steps</td></tr>"
            "<tr><td><b>[Delete] / Right-Click</b></td><td>Delete selected Text Box (returns script lines to <code>[ + ]</code> queue)</td></tr>"
            "<tr><td colspan='2'><hr></td></tr>"
            "<tr><td colspan='2'><b style='color: #00d4ff;'>— History (Undo / Redo) —</b></td></tr>"
            "<tr><td><b>[Ctrl + Z]</b></td><td><b>Smart Undo:</b> Undoes Image stroke in <b>MANUAL</b> mode, or Mask stroke otherwise</td></tr>"
            "<tr><td><b>[Ctrl + Shift + Z]</b></td><td><b>Smart Redo:</b> Redoes Image stroke in <b>MANUAL</b> mode, or Mask stroke otherwise</td></tr>"
            "<tr><td><b>[Alt + Z] / [Alt + Shift + Z]</b></td><td>Explicit Undo / Redo for AI Clean & Image patches</td></tr>"
            "</table>"
        )

        # ==========================================
        # TAB 2: CLEANER & MANUAL BRUSH
        # ==========================================
        tab_cleaner = QTextEdit()
        tab_cleaner.setReadOnly(True)
        tab_cleaner.setHtml(
            "<h3 style='color: #00d4ff;'>🧹 Cleaner Workspace & Manual Brush</h3>"
            "<p>The <b>CLEANER</b> category provides two complementary ways to clean pages:</p>"
            "<h4>1. AI Inpainting Mask (Red / Cyan Overlay)</h4>"
            "<ul>"
            "<li>Use <b>OCR SCAN [O]</b> or <b>TRANSPARENCY SCAN [T]</b> to automatically highlight text or transparent regions, "
            "or paint masks manually with <b>BRUSH</b>, <b>RECT</b>, <b>LASSO</b>, <b>POLY</b>, and <b>BUCKET</b>.</li>"
            "<li>Hold <b>[Alt]</b> with any mask tool to erase mask areas (shown in Cyan).</li>"
            "<li>Press <b>EXECUTE CLEAN [C]</b> to run LaMa AI inpainting on the masked regions.</li>"
            "</ul>"
            "<h4>2. Manual Cleaner Brush (<code>MANUAL [D]</code> & <code>PICKER [I]</code>)</h4>"
            "<ul>"
            "<li>Designed for quick touch-ups inside flat speech bubbles or backgrounds where AI is unnecessary.</li>"
            "<li>Click <b>MANUAL</b> to reveal the contextual color bar containing <b>PICKER [I]</b>, the <b>Color Swatch</b>, and the quick <b>White</b> reset button.</li>"
            "<li>While in <b>MANUAL</b> mode, hold <b>[Alt] + Left-Click</b> anywhere on the canvas to sample a color on the fly.</li>"
            "<li>Pressing <b>Ctrl + Z</b> while in Manual mode safely undoes your painted image strokes without losing your work.</li>"
            "</ul>"
        )

        # ==========================================
        # TAB 3: TYPESETTER & FONT MANAGER
        # ==========================================
        tab_typesetter = QTextEdit()
        tab_typesetter.setReadOnly(True)
        tab_typesetter.setHtml(
            "<h3 style='color: #00d4ff;'>🔤 Typesetter & Font Manager</h3>"
            "<p>Switch to the <b>TYPESETTER</b> category (or press <b>[X]</b>) to access a dedicated, clutter-free typesetting studio.</p>"
            "<h4>1. Font Manager, Favorites & Aliases</h4>"
            "<ul>"
            "<li><b>Search & Filter:</b> Filter system fonts by name or custom alias in real time.</li>"
            "<li><b>★ Only:</b> Toggle to display only your favorite scanlation fonts. This state and your last used font are automatically saved in <code>font_presets.json</code>.</li>"
            "<li><b>Favorite (★) & Rename Alias (✎):</b> Assign custom use-case names (e.g., <i>★ Shout [Wild Words]</i>) while keeping the real font family visible in brackets.</li>"
            "</ul>"
            "<h4>2. Interactive Transform Gizmo</h4>"
            "<ul>"
            "<li><b>White Corner Handles:</b> Drag to scale font size proportionally.</li>"
            "<li><b>Cyan Side Handles (L / R):</b> Drag horizontally to set a fixed word-wrap width. Click <b>Fit Box</b> to reset to auto-width.</li>"
            "<li><b>Top Cyan Circle:</b> Drag to rotate text freely around its center (hold <b>Shift</b> to snap to 15° angles, or click <b>0°</b> to reset).</li>"
            "</ul>"
            "<h4>3. Outer Stroke & Page Text Layers</h4>"
            "<ul>"
            "<li>Click the <b>Fill</b> or <b>Stroke</b> color swatches to pick colors, or click <b>⇄</b> to swap them in one click.</li>"
            "<li>Toggle <b>Mode: Stroke (Outside)</b> to enable a clean vector outer outline with adjustable pixel <b>Size</b> and <b>Opacity</b>.</li>"
            "<li><b>PAGE TEXT LAYERS:</b> Lists all placed boxes (<code>[ ✓ ]</code>) and queued script lines (<code>[ + ]</code>). Subtle dashed guides remain visible on unselected text boxes while the Text tool is active so dark text on dark backgrounds is never lost.</li>"
            "</ul>"
        )

        # ==========================================
        # TAB 4: TRANSLATOR (.TXT SCRIPT)
        # ==========================================
        tab_translator = QTextEdit()
        tab_translator.setReadOnly(True)
        tab_translator.setHtml(
            "<h3 style='color: #00d4ff;'>📄 Translator Script Generator & Lazy-Queue Importer</h3>"
            "<p>The <b>TRANSLATOR</b> category streamlines teamwork between translators and typesetters using lightweight <code>.txt</code> files.</p>"
            "<h4>1. Generating a Template</h4>"
            "<ul>"
            "<li>Load a chapter folder first, then click <b>Generate .TXT Template</b>.</li>"
            "<li>Creates a structured file with <code>Image 1 [image name.jpg] o [image name.png]</code> blocks and empty <code>-</code> bullets enclosed inside <code>&lt;translation&gt; ... &lt;/translation&gt;</code> tags.</li>"
            "</ul>"
            "<h4>2. Script Formatting Rules</h4>"
            "<ul>"
            "<li><b>Strict Tag Isolation:</b> Only text inside <code>&lt;translation&gt; ... &lt;/translation&gt;</code> is parsed. Any notes, metadata, or <code>#</code> comments outside the tags are 100% ignored.</li>"
            "<li><b>Dialogue Bullets:</b> Each <code>-</code> line represents one text box. Empty <code>-</code> lines are automatically skipped.</li>"
            "<li><b>Manual Line Breaks:</b> Use <code>//</code> inside a line to force a line break within the same text box.</li>"
            "<li><b>Unicode Ready:</b> Full NFC normalization ensures filenames and dialogues in Japanese, Korean, Chinese, Russian, Arabic, and Spanish match reliably across Windows, Linux, and macOS.</li>"
            "</ul>"
            "<h4>3. Zero-RAM Lazy Queue Workflow (<code>[ + ]</code> ➔ <code>[ ✓ ]</code>)</h4>"
            "<ul>"
            "<li>Importing a script queues dialogues into <b>PAGE TEXT LAYERS</b> as <code>[ + ]</code> items with <b>0 MB extra RAM usage</b> (images are not pre-decoded and no default font is forced).</li>"
            "<li>In <b>TYPESETTER</b>, select your desired font/stroke first, then click any <code>[ + ]</code> line (or click directly on the canvas) to spawn it immediately with your active typography settings!</li>"
            "<li>Deleting a script-spawned text box or clicking <b>CLEAR ALL</b> safely returns those lines back to the <code>[ + ]</code> queue.</li>"
            "</ul>"
        )

        # ==========================================
        # TAB 5: STITCHER & BATCHING
        # ==========================================
        tab_stitch_batch = QTextEdit()
        tab_stitch_batch.setReadOnly(True)
        tab_stitch_batch.setHtml(
            "<h3 style='color: #00d4ff;'>🧩 Lossless Image Stitcher & Batch Processing</h3>"
            "<h4>1. Lossless Vertical Stitcher (<code>STITCHER</code> Workspace)</h4>"
            "<p>Combines multiple manga/webtoon pages vertically without visible seams or compression artifacts—ideal when platforms enforce strict file count limits (e.g., reducing 150 pages into 100 files).</p>"
            "<ul>"
            "<li><b>Manual Blocks:</b> Check specific files in Project Assets or pick a page range (<i>From # ➔ To #</i>) to build custom multi-page strips.</li>"
            "<li><b>Auto: Pages per Output File:</b> Automatically groups every <i>N</i> consecutive pages into one output file.</li>"
            "<li><b>Auto: Fit to Max File Count:</b> Automatically distributes all project pages to fit within your target file limit.</li>"
            "<li><b>Height Guard & Lossless Export:</b> Optional maximum pixel height splitter (can sync to 4x Max Tile Size) and lossless export in <b>PNG</b> or <b>100% Quality 4:4:4 JPG</b> (including all active cleanings and typeset layers).</li>"
            "</ul>"
            "<hr>"
            "<h4>2. Automated Batch Processing (<code>RUN BATCH PROCESS</code>)</h4>"
            "<ol>"
            "<li>Import a folder of pages (check specific files, or leave unchecked to process all).</li>"
            "<li>Click <b>RUN BATCH PROCESS</b> and select your <b>Scan Mode</b> (<i>none, Mask, OCR Scan, Transparency Scan</i>) and <b>Export Format</b> (<i>none, png, jpg, photoshop, photopea</i>).</li>"
            "<li>Cleaned and typesetted pages are saved to the <b>/processed/</b> directory.</li>"
            "<li><i>Safety Check:</i> Before exporting, batching, or stitching, the studio warns you if any page still has unplaced <code>[ + ]</code> script dialogues in the queue.</li>"
            "</ol>"
        )

        # ==========================================
        # TAB 6: HARDWARE DIAGNOSTICS
        # ==========================================
        specs = SystemMonitor.get_detailed_specs()
        tab_hardware = QTextEdit()
        tab_hardware.setReadOnly(True)
        tab_hardware.setHtml(
            "<h3 style='color: #00d4ff;'>💻 System Diagnostics & Performance</h3>"
            f"<p><b>Compute Engine Found:</b> {specs['engine']}</p>"
            f"<p><b>System RAM Detected:</b> {specs['ram']} GB</p>"
            "<hr>"
            "<h4>Memory & GPU Optimizations</h4>"
            "<ul>"
            "<li><b>VRAM Tiling:</b> AI Inpainting processes patches in configurable chunks (<i>Max Tile Size</i> slider) to prevent GPU out-of-memory crashes on high-resolution webtoons.</li>"
            "<li><b>Model Persistence:</b> During batch operations, ONNX/CUDA models remain warm in memory to maximize throughput.</li>"
            "<li><b>Lazy Script Queue:</b> Importing <code>.txt</code> translation scripts across 100+ pages stores only lightweight UTF-8 strings in memory until each page is actively opened.</li>"
            "</ul>"
        )
        
        tabs.addTab(tab_shortcuts, "Shortcuts")
        tabs.addTab(tab_cleaner, "Cleaner && Manual")
        tabs.addTab(tab_typesetter, "Typesetter")
        tabs.addTab(tab_translator, "Translator (.txt)")
        tabs.addTab(tab_stitch_batch, "Stitcher && Batch")
        tabs.addTab(tab_hardware, "Hardware")
        layout.addWidget(tabs)
        
        close_btn = QPushButton("CLOSE")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)

    @staticmethod
    def show_guide(parent):
        dialog = HelpSystem(parent)
        dialog.exec()