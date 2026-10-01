#ifndef CORE_PIPELINE_BATCH_WORKER_H
#define CORE_PIPELINE_BATCH_WORKER_H

#include <QThread>
#include <QStringList>
#include <QString>
#include <atomic>
#include <memory>
#include <mutex>
#include <opencv2/opencv.hpp>
#include "studio_worker.h"

class session_data;

struct BatchConfig {
    QStringList input_files;
    QString output_dir;
    QString export_format;

    bool run_bpn = false;
    bool run_moebius = false;   // AI inpainting stage (Moebius or LaMa, auto-routed)
    bool scan_transparency = false;

    bool halt_on_error = false;
    bool create_zip = false;

    // Export-only mode: skip the AI stages and write each page's CLEANED pixels
    // from the Studio's per-page working state instead of the untouched file on
    // disk. Pages without persisted edits fall back to the original decode.
    bool use_session_state = false;
};

class pipeline_manager;

class batch_worker : public QThread {
    Q_OBJECT

public:
    // inference_mutex is shared with the studio worker so the two threads can never
    // drive the same TensorRT contexts / CUDA stream at the same time.
    // m_pipeline (not owned) lazy-loads engines into VRAM right before each stage.
    batch_worker(AI_Engine_Pack models, std::shared_ptr<std::mutex> inference_mutex,
        pipeline_manager* pipeline = nullptr, session_data* session = nullptr, QObject* parent = nullptr);
    ~batch_worker() override;

    void start_batch(const BatchConfig& config);
    void cancel();

signals:
    void batch_progress(int processed, int total);
    void batch_progress_failed(int failed);
    void current_task_changed(const QString& task_name);
    void batch_finished(bool completed_successfully);
    void error_occurred(const QString& message);

protected:
    void run() override;

private:
    BatchConfig m_config;
    std::atomic<bool> m_cancel_requested;
    AI_Engine_Pack m_models;
    std::shared_ptr<std::mutex> m_inference_mutex;
    pipeline_manager* m_pipeline;
    session_data* m_session; // not owned; needed for export-from-session state

    bool process_single_image(const QString& filepath, const cv::Mat& raw_img);
    // `out_skipped` distinguishes "page untouched in the Studio (no output
    // written, not an error)" from a real processing failure.
    bool process_session_state_image(const QString& filepath, const cv::Mat& raw_img, bool* out_skipped = nullptr);
    static cv::Mat decode_image_file(const QString& filepath);
    bool save_image_unicode(const QString& save_path, const cv::Mat& img);
    void create_zip_archive(const QString& folder_path, const QString& batch_name);
};

#endif // CORE_PIPELINE_BATCH_WORKER_H