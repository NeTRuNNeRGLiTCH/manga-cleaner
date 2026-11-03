# Developer Review Notes

This document records maintainability and performance observations found during a static review of the current 3.4.x codebase. It is intended as a follow-up checklist for developers, not as a claim that every item is a confirmed defect. Profile and reproduce performance concerns before changing behavior.

## Performance and UI follow-ups

### 1. Stitcher memory use with large chapters

**Location:** `src/backend/stitcher.py`, batch export loop (around `raw_imgs`, `align_widths_and_channels`, `split_by_max_height`, and `np.vstack`).

The export path loads every available image for a stitch block into `raw_imgs`, aligns the full list, and only then splits the aligned images according to the configured maximum output height. It subsequently creates each output part with `np.vstack`. This means the height limit controls the dimensions of exported parts, but it does not cap the memory needed to load and align a large block first. During processing, source images, aligned images, and the current concatenated output may coexist in memory.

**Why to keep this in mind:** Large chapters or high-resolution scans can use substantially more RAM and may cause pauses or allocation failures, especially on older machines. The current behavior may be acceptable for ordinary projects; the concern should be measured with representative large inputs before attempting a redesign.

**Possible follow-up:** Profile peak resident memory and elapsed time for small, typical, and large chapters. If memory use is excessive, consider an incremental alignment/stitching pipeline that writes bounded-height parts as it goes. Preserve current width/channel normalization, ordering, lossless output behavior, cancellation, and progress reporting. Compare output dimensions and pixels against the current implementation before replacing it.

### 2. Typesetter panel is constructed during startup

**Location:** `src/frontend/main_window.py`, where `TypesetterPanel(self)` is instantiated during main-window setup; panel construction is implemented in `src/frontend/typesetter_panel.py`.

The typesetting controls are separated from `main_window.py`, which improves code organization, but the complete `TypesetterPanel` widget tree is still created when the main window is initialized. This keeps the main window module smaller; it does not defer the panel's widget-construction cost. The system font inventory is loaded lazily by `populate_font_combo`, so font enumeration is not necessarily part of initial construction.

**Why to keep this in mind:** If startup remains noticeably slow after other startup work is optimized, eager construction of this secondary workspace is a measurable candidate. Moving code to another module alone does not reduce startup work.

**Possible follow-up:** Measure startup time before changing lifecycle behavior. If panel construction is a meaningful part of the delay, create the typesetter panel the first time the Typesetter category is opened, then retain and reuse it. Check category switching, canvas signals, pending text state, localization, and font preferences after lazy construction. Avoid rebuilding the panel on every visit.

### 3. Font search sorts the full font list on every refresh

**Location:** `src/frontend/typesetter_panel.py`, `populate_font_combo()`.

The font inventory is cached after the first query, but every call to `populate_font_combo()` sorts the complete cached list before filtering it. The method is called when the search text changes, as well as when favorites or aliases change. Typing a query can therefore repeat the same sort for each keystroke.

**Why to keep this in mind:** On systems with many installed fonts, repeated sorting may make the font selector feel less responsive. This is a potential inefficiency; its impact depends on the machine and font count.

**Possible follow-up:** Profile the selector with a large font inventory. If the sort is significant, cache the ordered font list and rebuild it only when favorite status or aliases change; apply the search and favorites filters to that ordered list. Preserve current favorite-first ordering and alias behavior.

### 4. Unlocalized empty text-layer placeholder

**Location:** `src/frontend/typesetter_panel.py`, `refresh_page_text_list()`.

When a placed text layer has no non-whitespace content, the layer list displays the hard-coded English placeholder `<Empty>`. This string bypasses the localization catalog, so it remains English in every other language.

**Suggested follow-up:** Add a stable key to `locales/en.json`, use `tr()` at the display call site, then follow the catalog approval workflow in `TRANSLATION.md`. Keep the placeholder presentation behavior unchanged.

## Localization and release maintenance

### Model delivery in the GitHub Actions workflow

**Location:** `.github/workflows/build.yml`, the Windows and Linux model-download steps.

**Status: updated.** The current workflow no longer downloads `models.zip` or bundles model weights. The packaged application includes `src/`, which contains `ModelManager`; `Paths.MODELS` resolves to a writable `models/` directory beside the executable in frozen builds. Users can download models from the configured Hugging Face repository through the application. Older published releases remain unchanged and may still depend on their bundled or archived model files.

**Remaining release check:** Exercise packaged Windows and Linux CPU/GPU builds before publishing: confirm first-run setup downloads into the writable model directory, installed models are discovered after restart, and inference works. Windows GPU builds still need their CUDA runtime DLLs; those are collected separately and are not model weights. Linux GPU dependencies continue to be collected by its PyInstaller spec.

## Dead-code review outcome

A repository-wide reference scan did not identify additional application functions or classes that can confidently be removed. Several names that appeared to have no direct call sites are framework hooks and must remain:

- `MangaCanvas.drawBackground()` overrides a Qt graphics-scene drawing hook.
- `CORSImageHandler.log_message()` overrides the HTTP server logger to suppress request logs.
- `_SafeDict.__missing__()` supplies fallback formatting for unresolved named placeholders.

The localization migration utilities in `tools/` are not runtime application code, but they remain documented developer tools. `check_locales.py` is also used by the release workflow, so it is actively part of release validation. One-time migration scripts can remain useful for future audits and should only be removed if maintainers decide to retire that workflow and update its documentation.

Previously confirmed unused members/imports were removed during the preceding cleanup. Keep `AIManager.set_persistence()` because a worker calls it and its non-persistent path flushes the model cache.

## Review limits

These notes come from source inspection and reference searches. The application was not benchmarked with large chapters, a large font inventory, or a packaged build as part of this review. Reproduce and measure the relevant behavior before prioritizing performance changes, and validate functional behavior after implementation.
