#ifndef CORE_STATE_SESSION_DATA_H
#define CORE_STATE_SESSION_DATA_H

#include <QString>
#include <QImage>
#include <opencv2/opencv.hpp>
#include <shared_mutex>
#include <mutex>
#include <atomic>

class session_data {
public:
    session_data();
    ~session_data();

    // === GLOBAL STATE MANAGEMENT ===
    bool load_image(const QString& filepath);
    void clear_session();
    bool has_active_image() const;

    // === PER-PAGE WORKING-STATE PERSISTENCE ===
    // Saves/restores inpainted pixels and the mask per source file so switching
    // pages in the gallery never loses work. Images go to
    // AppLocalData/working_state as PNG (keyed by a hash of the absolute path).
    void save_working_state(const QString& filepath, const cv::Mat& image_rgb, const cv::Mat& mask) const;
    bool load_working_state(const QString& filepath, cv::Mat& image_rgb, cv::Mat& mask);

    // Disk budget for the working-state cache: `prune_working_state` deletes
    // cached page-edit files untouched for more than `max_age_days` (runs once
    // at startup), `clear_working_state` wipes the whole cache (File menu
    // button). Both return how many files they removed.
    static int prune_working_state(int max_age_days = 30);
    static int clear_working_state();

    // Session-independent restore for EXPORT: returns the persisted edited
    // image + mask for `filepath` (as written by save_working_state) WITHOUT    // touching any session instance, so the batch worker can export cleaned    // pages from another thread. `source_size` (the freshly decoded page)    // guards against stale state after a file changed on disk. Returns false    // when the page has no persisted edits.
    static bool load_persisted_page_state(
        const QString& filepath, const cv::Size& source_size,
        cv::Mat& image_rgb, cv::Mat& mask);

    static QString working_state_dir();
    static QString working_state_prefix(const QString& filepath);

    // === THREAD-SAFE DATA GETTERS (Shared Read Locks) ===
    cv::Mat get_original_image() const;
    cv::Mat get_current_image() const;
    cv::Mat get_current_mask() const;
    QString get_current_filepath() const;

    // Cheap geometry query (no image clone) for hot UI paths such as the canvas.
    cv::Size get_image_size() const;

    // === THREAD-SAFE DATA MODIFIERS (Exclusive Write Locks) ===
    void set_mask(const cv::Mat& new_mask);

    // Cheap incremental mask write for interactive brush strokes: only `roi` is copied
    // and only that region of the translucent display overlay is refreshed, so painting
    // never reallocates the whole page mask or overlay on every mouse-move.
    // `mask_patch` must be a CV_8UC1 image of exactly `roi`'s size.
    void set_mask_patch(const cv::Rect& roi, const cv::Mat& mask_patch);
    void apply_cleaned_patch(const cv::Rect& roi, const cv::Mat& cleaned_patch_rgb);
    void replace_image(const cv::Mat& new_image_rgb);

    // Swaps the working image WITHOUT clearing the mask (used by the color paint
    // tool: a manual touch-up must not destroy the detection/inpainting mask).
    void replace_image_keep_mask(const cv::Mat& new_image_rgb);

    // === UI RENDERING (Zero-Copy Display Cache) ===
    QImage get_display_image() const;
    QImage get_display_mask() const;

private:
    // Shared decoder for the per-page PNGs behind load_working_state and
    // load_persisted_page_state. `required_size` may be empty; when set,
    // restored images must match it exactly (stale-state guard).
    static bool read_working_state(
        const QString& filepath, const cv::Size& required_size,
        bool& out_image, bool& out_mask,
        cv::Mat& image_rgb, cv::Mat& mask);

    mutable std::shared_mutex m_rw_mutex; // Reader/Writer lock for multi-threaded safety

    QString m_filepath;
    cv::Mat m_original_image;
    cv::Mat m_current_image;
    cv::Mat m_current_mask;

    // Persistent RGBA scratch buffer backing m_cached_mask; updated in place by
    // set_mask_patch() so the overlay is never rebuilt from scratch mid-stroke.
    mutable cv::Mat m_mask_overlay;

    mutable QImage m_cached_image;
    mutable QImage m_cached_mask;
    mutable bool m_image_dirty;
    mutable bool m_mask_dirty;

    // True when the ACTIVE page received at least one real edit (mask stroke,
    // detection, inpaint, color touch-up) since it was loaded/restored. Only
    // dirty pages are written to the working-state cache, so merely visiting a
    // page neither grows the cache on disk nor makes the exporter treat the
    // untouched page as "edited". Atomic: the export flush reads it on the UI
    // thread while a worker thread may be mutating the page concurrently.
    std::atomic<bool> m_page_dirty{ false };
};

#endif // CORE_STATE_SESSION_DATA_H