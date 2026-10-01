#include "session_data.h"
#include "src/diagnostics/logger.h"
#include <QFile>
#include <QFileInfo>
#include <QSaveFile>
#include <QDir>
#include <QStandardPaths>
#include <QCryptographicHash>
#include <QDateTime>
#include <opencv2/imgcodecs.hpp>
#include <cstring>
#include <vector>

session_data::session_data() : m_image_dirty(true), m_mask_dirty(true) {
    clear_session();
}

session_data::~session_data() {
    clear_session();
}

void session_data::clear_session() {
    std::unique_lock<std::shared_mutex> lock(m_rw_mutex);
    LOG_TRACE("Clearing active image session data.");
    m_filepath.clear();
    m_original_image.release();
    m_current_image.release();
    m_current_mask.release();
    m_mask_overlay.release(); // Drop the page-sized overlay buffer, don't keep it alive
    m_cached_image = QImage();
    m_cached_mask = QImage();
    m_image_dirty = true;
    m_mask_dirty = true;
    m_page_dirty.store(false, std::memory_order_relaxed);
}

bool session_data::has_active_image() const {
    std::shared_lock<std::shared_mutex> lock(m_rw_mutex);
    return !m_current_image.empty();
}

bool session_data::load_image(const QString& filepath) {
    LOG_TRACE("Loading image into session: " + filepath);

    // Keep the current page's edits before it is replaced by the new one.
    QString previous_filepath;
    cv::Mat previous_image, previous_mask;
    {
        std::shared_lock<std::shared_mutex> lock(m_rw_mutex);
        if (!m_current_image.empty() && m_filepath != filepath) {
            previous_filepath = m_filepath;
            previous_image = m_current_image.clone();
            previous_mask = m_current_mask.clone();
        }
    }

    QFile file(filepath);
    if (!file.open(QIODevice::ReadOnly)) {
        LOG_ERROR("Failed to open image file for reading: " + filepath);
        return false;
    }

    QByteArray file_data = file.readAll();
    file.close();

    try {
        std::vector<uchar> buffer(file_data.begin(), file_data.end());
        cv::Mat decoded = cv::imdecode(buffer, cv::IMREAD_UNCHANGED);
        if (decoded.empty()) {
            LOG_ERROR("OpenCV failed to decode image buffer: " + filepath);
            return false;
        }

        std::unique_lock<std::shared_mutex> lock(m_rw_mutex);
        m_filepath = filepath;

        // Preserve 4-channel alpha transparency if present
        if (decoded.channels() == 4) {
            cv::cvtColor(decoded, m_original_image, cv::COLOR_BGRA2RGBA);
            LOG_TRACE("Preserved PNG Transparency (RGBA 4-Channels).");
        }
        else if (decoded.channels() == 3) {
            cv::cvtColor(decoded, m_original_image, cv::COLOR_BGR2RGB);
        }
        else {
            cv::cvtColor(decoded, m_original_image, cv::COLOR_GRAY2RGB);
        }

        m_current_image = m_original_image.clone();
        m_current_mask = cv::Mat::zeros(m_current_image.size(), CV_8UC1);

        if (!previous_image.empty() && m_page_dirty.load(std::memory_order_relaxed)) {
            save_working_state(previous_filepath, previous_image, previous_mask);
        }
        m_page_dirty.store(false, std::memory_order_relaxed);
        if (!load_working_state(filepath, m_current_image, m_current_mask)) {
            // Fresh page: mask starts empty, image stays the decoded original.
            m_current_mask.release();
        }
        m_current_mask = m_current_mask.empty()
            ? cv::Mat::zeros(m_current_image.size(), CV_8UC1)
            : m_current_mask;

        m_image_dirty = true;
        m_mask_dirty = true;

        LOG_INFO(QString("Successfully loaded image: %1 [%2x%3]")
            .arg(filepath)
            .arg(m_current_image.cols)
            .arg(m_current_image.rows));

        return true;
    }
    catch (const cv::Exception& e) {
        LOG_ERROR(QString("OpenCV Exception during image load: ") + e.what());
        return false;
    }
}

cv::Mat session_data::get_original_image() const {
    std::shared_lock<std::shared_mutex> lock(m_rw_mutex);
    return m_original_image.clone();
}

cv::Mat session_data::get_current_image() const {
    std::shared_lock<std::shared_mutex> lock(m_rw_mutex);
    return m_current_image.clone();
}

cv::Mat session_data::get_current_mask() const {
    std::shared_lock<std::shared_mutex> lock(m_rw_mutex);
    return m_current_mask.clone();
}

cv::Size session_data::get_image_size() const {
    std::shared_lock<std::shared_mutex> lock(m_rw_mutex);
    return m_current_image.size();
}

QString session_data::get_current_filepath() const {
    std::shared_lock<std::shared_mutex> lock(m_rw_mutex);
    return m_filepath;
}

void session_data::set_mask(const cv::Mat& new_mask) {
    try {
        std::unique_lock<std::shared_mutex> lock(m_rw_mutex);
        if (m_current_image.empty()) return;

        if (new_mask.size() == m_current_image.size() && new_mask.type() == CV_8UC1) {
            m_current_mask = new_mask.clone();
            m_mask_dirty = true;
            m_page_dirty.store(true, std::memory_order_relaxed);
        }
        else {
            LOG_WARN("set_mask rejected: Mask dimensions/type do not match active image.");
        }
    }
    catch (const cv::Exception& e) {
        LOG_ERROR(QString("OpenCV Exception in set_mask: ") + e.what());
    }
}

void session_data::set_mask_patch(const cv::Rect& roi, const cv::Mat& mask_patch) {
    try {
        std::unique_lock<std::shared_mutex> lock(m_rw_mutex);
        if (m_current_mask.empty() || mask_patch.empty()) return;

        const int cols = m_current_mask.cols;
        const int rows = m_current_mask.rows;
        const cv::Rect safe = roi & cv::Rect(0, 0, cols, rows);
        if (safe.width <= 0 || safe.height <= 0) return;

        // Anything unexpected means we cannot do a region update safely; fall back to
        // a full overlay rebuild on the next paint instead of guessing.
        if (mask_patch.type() != CV_8UC1 || mask_patch.size() != safe.size()) {
            m_mask_dirty = true;
            return;
        }

        mask_patch.copyTo(m_current_mask(safe));
        m_page_dirty.store(true, std::memory_order_relaxed);

        const bool cache_is_patchable =
            !m_mask_dirty &&
            !m_cached_mask.isNull() &&
            m_cached_mask.width() == cols &&
            m_cached_mask.height() == rows &&
            m_cached_mask.format() == QImage::Format_RGBA8888 &&
            m_mask_overlay.size() == m_current_mask.size() &&
            m_mask_overlay.type() == CV_8UC4 &&
            m_mask_overlay.isContinuous();

        if (!cache_is_patchable) {
            m_mask_dirty = true;
            return;
        }

        // Refresh just the touched band of the translucent overlay...
        cv::Mat overlay_roi = m_mask_overlay(safe);
        cv::Mat outside;
        cv::bitwise_not(mask_patch, outside);
        overlay_roi.setTo(cv::Scalar(255, 0, 0, 120), mask_patch); // painted pixels
        overlay_roi.setTo(cv::Scalar(0, 0, 0, 0), outside);       // cleared pixels

        // ...and mirror it into the cached QImage's pixels, row by row.
        const int bytes_per_line = static_cast<int>(m_cached_mask.bytesPerLine());
        uchar* dst_base = m_cached_mask.bits();
        if (!dst_base || bytes_per_line < cols * 4) {
            m_mask_dirty = true;
            return;
        }

        const size_t row_bytes = static_cast<size_t>(safe.width) * 4;
        for (int y = 0; y < safe.height; ++y) {
            const uchar* src = m_mask_overlay.ptr<uchar>(safe.y + y) + static_cast<size_t>(safe.x) * 4;
            uchar* dst = dst_base + static_cast<size_t>(safe.y + y) * bytes_per_line + static_cast<size_t>(safe.x) * 4;
            std::memcpy(dst, src, row_bytes);
        }
    }
    catch (const cv::Exception& e) {
        LOG_ERROR(QString("OpenCV Exception in set_mask_patch: ") + e.what());
    }
}

void session_data::apply_cleaned_patch(const cv::Rect& roi, const cv::Mat& cleaned_patch_rgb) {
    try {
        std::unique_lock<std::shared_mutex> lock(m_rw_mutex);
        if (m_current_image.empty() || cleaned_patch_rgb.empty()) return;

        cv::Rect safe_roi = roi & cv::Rect(0, 0, m_current_image.cols, m_current_image.rows);
        if (safe_roi.area() == 0) return;

        cv::Rect patch_roi(0, 0, safe_roi.width, safe_roi.height);

        // Alpha channel preservation if working on 4-channel image
        if (m_current_image.channels() == 4 && cleaned_patch_rgb.channels() == 3) {
            cv::Mat patch_rgba;
            cv::cvtColor(cleaned_patch_rgb(patch_roi), patch_rgba, cv::COLOR_RGB2RGBA);

            std::vector<cv::Mat> orig_ch, clean_ch;
            cv::split(m_current_image(safe_roi), orig_ch);
            cv::split(patch_rgba, clean_ch);
            clean_ch[3] = orig_ch[3]; // Keep original alpha channel
            cv::merge(clean_ch, patch_rgba);

            patch_rgba.copyTo(m_current_image(safe_roi));
        }
        else {
            cleaned_patch_rgb(patch_roi).copyTo(m_current_image(safe_roi));
        }

        m_image_dirty = true;
        m_page_dirty.store(true, std::memory_order_relaxed);
    }
    catch (const cv::Exception& e) {
        LOG_ERROR(QString("OpenCV Exception in apply_cleaned_patch: ") + e.what());
    }
}

// ==========================================================
// PER-PAGE WORKING-STATE PERSISTENCE (image edits + mask)
// ==========================================================
int session_data::prune_working_state(int max_age_days) {
    const QString dir_path = working_state_dir();
    QDir dir(dir_path);
    if (!dir.exists() || max_age_days <= 0) return 0;

    const QDateTime cutoff = QDateTime::currentDateTime().addDays(-max_age_days);
    int removed = 0;
    const QFileInfoList entries = dir.entryInfoList(QStringList("page_*.png"), QDir::Files);
    for (const QFileInfo& entry : entries) {
        if (entry.lastModified() < cutoff && dir.remove(entry.fileName())) ++removed;
    }

    if (removed > 0) {
        LOG_INFO(QString("Working-state cache: pruned %1 file(s) older than %2 days.")
            .arg(removed).arg(max_age_days));
    }
    return removed;
}

int session_data::clear_working_state() {
    const QString dir_path = working_state_dir();
    QDir dir(dir_path);
    if (!dir.exists()) return 0;

    int removed = 0;
    const QFileInfoList entries = dir.entryInfoList(QStringList("page_*.png"), QDir::Files);
    for (const QFileInfo& entry : entries) {
        if (dir.remove(entry.fileName())) ++removed;
    }

    LOG_INFO(QString("Working-state cache cleared: %1 file(s) removed.").arg(removed));
    return removed;
}

QString session_data::working_state_dir() {
    return QStandardPaths::writableLocation(QStandardPaths::AppLocalDataLocation) + "/working_state";
}

QString session_data::working_state_prefix(const QString& filepath) {
    const QString canonical = QFileInfo(filepath).absoluteFilePath();
    const QByteArray digest = QCryptographicHash::hash(
        canonical.toUtf8(), QCryptographicHash::Md5).toHex();
    return QString("page_") + QString::fromLatin1(digest);
}

bool session_data::read_working_state(
    const QString& filepath, const cv::Size& required_size,
    bool& out_image, bool& out_mask,
    cv::Mat& image_rgb, cv::Mat& mask)
{
    out_image = false;
    out_mask = false;
    if (filepath.isEmpty()) return false;

    const QString prefix = working_state_prefix(filepath);
    const QString image_path = working_state_dir() + "/" + prefix + "_image.png";
    const QString mask_path = working_state_dir() + "/" + prefix + "_mask.png";

    if (QFileInfo::exists(image_path)) {
        QFile f(image_path);
        if (f.open(QIODevice::ReadOnly)) {
            const QByteArray raw = f.readAll();
            f.close();
            const std::vector<uchar> buf(raw.cbegin(), raw.cend());
            cv::Mat saved = cv::imdecode(buf, cv::IMREAD_UNCHANGED);
            // Only restore if dimensions still match (the file may have changed on disk).
            if (!saved.empty() && (required_size == cv::Size() || saved.size() == required_size)) {
                // PNG is BGR/RGBA on disk; the session works in RGB/RGBA.
                if (saved.channels() == 3) cv::cvtColor(saved, image_rgb, cv::COLOR_BGR2RGB);
                else if (saved.channels() == 4) cv::cvtColor(saved, image_rgb, cv::COLOR_BGRA2RGBA);
                else if (saved.channels() == 1) cv::cvtColor(saved, image_rgb, cv::COLOR_GRAY2RGB);
                out_image = true;
            }
        }
    }
    if (QFileInfo::exists(mask_path)) {
        QFile f(mask_path);
        if (f.open(QIODevice::ReadOnly)) {
            const QByteArray raw = f.readAll();
            f.close();
            const std::vector<uchar> buf(raw.cbegin(), raw.cend());
            cv::Mat saved = cv::imdecode(buf, cv::IMREAD_UNCHANGED);
            if (!saved.empty() && (required_size == cv::Size() || saved.size() == required_size)) {
                if (saved.channels() != 1) cv::cvtColor(saved, saved, cv::COLOR_BGR2GRAY);
                mask = saved;
                out_mask = true;
            }
        }
    }
    return out_image || out_mask;
}

bool session_data::load_persisted_page_state(
    const QString& filepath, const cv::Size& source_size,
    cv::Mat& image_rgb, cv::Mat& mask)
{
    bool got_image = false, got_mask = false;
    read_working_state(filepath, source_size, got_image, got_mask, image_rgb, mask);
    return got_image || got_mask;
}

void session_data::save_working_state(const QString& filepath, const cv::Mat& image_rgb, const cv::Mat& mask) const {
    // The dirty flag describes the page being saved here: in load_image() it
    // still refers to the PREVIOUS page (reset happens right after this call),
    // in the export flush it refers to the active page. Unedited pages skip the
    // write so the cache only ever holds real work.
    if (!m_page_dirty.load(std::memory_order_relaxed)) return;
    if (filepath.isEmpty() || image_rgb.empty() || mask.empty()) return;
    if (image_rgb.size() != mask.size()) return;

    QDir().mkpath(working_state_dir());
    const QString prefix = working_state_prefix(filepath);

    // PNG keeps the mask 1:1 and image edits pixel-perfect. The session mats are
    // RGB/RGBA; convert to BGR/BGRA because that is what image codecs expect on
    // disk (load_working_state swaps them back).
    cv::Mat image_bgr;
    if (image_rgb.channels() == 4) cv::cvtColor(image_rgb, image_bgr, cv::COLOR_RGBA2BGRA);
    else cv::cvtColor(image_rgb, image_bgr, cv::COLOR_RGB2BGR);

    std::vector<uchar> buf;
    cv::imencode(".png", mask, buf);
    QSaveFile mask_file(working_state_dir() + "/" + prefix + "_mask.png");
    if (mask_file.open(QIODevice::WriteOnly)) {
        mask_file.write(reinterpret_cast<const char*>(buf.data()), static_cast<qint64>(buf.size()));
        mask_file.commit();
    }

    buf.clear();
    cv::imencode(".png", image_bgr, buf);
    QSaveFile image_file(working_state_dir() + "/" + prefix + "_image.png");
    if (image_file.open(QIODevice::WriteOnly)) {
        image_file.write(reinterpret_cast<const char*>(buf.data()), static_cast<qint64>(buf.size()));
        image_file.commit();
    }
}

bool session_data::load_working_state(const QString& filepath, cv::Mat& image_rgb, cv::Mat& mask) {
    // Precondition: the caller (load_image) already holds m_rw_mutex exclusively,
    // so m_original_image is read directly here - locking again would deadlock.
    bool got_image = false, got_mask = false;
    const bool found = read_working_state(filepath, m_original_image.size(), got_image, got_mask, image_rgb, mask);

    // A partially-saved page (mask without image or vice versa) restores what exists.
    return found;
}

void session_data::replace_image(const cv::Mat& new_image_rgb) {
    try {
        std::unique_lock<std::shared_mutex> lock(m_rw_mutex);
        m_current_image = new_image_rgb.clone();
        m_original_image = m_current_image.clone();
        m_current_mask = cv::Mat::zeros(m_current_image.size(), CV_8UC1);

        m_image_dirty = true;
        m_mask_dirty = true;
        m_page_dirty.store(true, std::memory_order_relaxed);

        LOG_INFO(QString("Canvas replaced at new resolution: %1x%2")
            .arg(m_current_image.cols).arg(m_current_image.rows));
    }
    catch (const cv::Exception& e) {
        LOG_ERROR(QString("OpenCV Exception in replace_image: ") + e.what());
    }
}

void session_data::replace_image_keep_mask(const cv::Mat& new_image_rgb) {
    try {
        std::unique_lock<std::shared_mutex> lock(m_rw_mutex);
        m_current_image = new_image_rgb.clone();
        if (m_current_mask.empty() || m_current_mask.size() != m_current_image.size()) {
            m_current_mask = cv::Mat::zeros(m_current_image.size(), CV_8UC1);
        }
        m_image_dirty = true;
        m_page_dirty.store(true, std::memory_order_relaxed);
    }
    catch (const cv::Exception& e) {
        LOG_ERROR(QString("OpenCV Exception in replace_image_keep_mask: ") + e.what());
    }
}

QImage session_data::get_display_image() const {
    // Exclusive lock: this const method mutates the display cache, so concurrent
    // readers must not race on m_cached_image.
    std::unique_lock<std::shared_mutex> lock(m_rw_mutex);
    if (m_current_image.empty()) return QImage();

    try {
        if (m_image_dirty) {
            if (m_current_image.channels() == 4) {
                m_cached_image = QImage(
                    m_current_image.data,
                    m_current_image.cols,
                    m_current_image.rows,
                    static_cast<int>(m_current_image.step),
                    QImage::Format_RGBA8888
                ).copy();
            }
            else {
                m_cached_image = QImage(
                    m_current_image.data,
                    m_current_image.cols,
                    m_current_image.rows,
                    static_cast<int>(m_current_image.step),
                    QImage::Format_RGB888
                ).copy();
            }
            m_image_dirty = false;
        }
    }
    catch (const std::exception& e) {
        LOG_ERROR(QString("Exception generating display image: ") + e.what());
    }

    return m_cached_image;
}

QImage session_data::get_display_mask() const {
    // Exclusive lock: this const method mutates the display cache.
    std::unique_lock<std::shared_mutex> lock(m_rw_mutex);
    if (m_current_mask.empty()) return QImage();

    try {
        if (m_mask_dirty) {
            // Reuse the persistent overlay buffer when the page size is unchanged so
            // repeated full rebuilds don't keep re-allocating page-sized memory.
            if (m_mask_overlay.size() != m_current_mask.size() ||
                m_mask_overlay.type() != CV_8UC4 ||
                !m_mask_overlay.isContinuous()) {
                m_mask_overlay = cv::Mat(m_current_mask.size(), CV_8UC4, cv::Scalar(0, 0, 0, 0));
            }
            else {
                m_mask_overlay.setTo(cv::Scalar(0, 0, 0, 0));
            }

            m_mask_overlay.setTo(cv::Scalar(255, 0, 0, 120), m_current_mask); // Red translucent overlay

            m_cached_mask = QImage(
                m_mask_overlay.data,
                m_mask_overlay.cols,
                m_mask_overlay.rows,
                static_cast<int>(m_mask_overlay.step),
                QImage::Format_RGBA8888
            ).copy();

            m_mask_dirty = false;
        }
    }
    catch (const cv::Exception& e) {
        LOG_ERROR(QString("OpenCV Exception generating display mask: ") + e.what());
    }

    return m_cached_mask;
}