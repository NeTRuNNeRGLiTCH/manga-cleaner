#ifndef ENGINE_TRT_ARCH_DETECTOR_H
#define ENGINE_TRT_ARCH_DETECTOR_H

#include <QString>
#include <cuda_runtime.h>

enum class GpuArch {
    Turing,     // SM 7.5 (RTX 20xx, GTX 16xx)
    Ampere,     // SM 8.0 / 8.6 (RTX 30xx)
    Lovelace,   // SM 8.9 (RTX 40xx)
    Blackwell,  // SM 10.x / 12.x (RTX 50xx)
    Unknown
};

class trt_arch_detector {
public:
    // Singleton access
    static trt_arch_detector& instance();

    // Query active architecture info
    GpuArch get_current_arch() const;
    QString get_arch_name() const;
    QString get_arch_folder() const;
    int get_compute_capability() const; // e.g. 89 for SM 8.9

    // Fast boolean checks for model pipeline branching
    bool is_ada_or_newer() const;
    bool is_turing() const;

    // Resolves the absolute path of an engine pack entry.
    // Pass the pack stem ("lama", "segmentation", "moebius_unet", ...),
    // optionally with a trailing ".engine". Searches models/<arch>/<stem>_<arch>.engine
    // first, then the closest pack that actually ships engines, then models/ root.
    // Example: get_engine_path("lama") -> "C:/.../models/lovelace/lama_lovelace.engine"
    QString get_engine_path(const QString& base_name) const;

    // Force re-scan (e.g. after user changes override in Settings)
    void refresh();

private:
    trt_arch_detector();
    ~trt_arch_detector() = default;
    trt_arch_detector(const trt_arch_detector&) = delete;
    trt_arch_detector& operator=(const trt_arch_detector&) = delete;

    void detect_hardware();

    GpuArch m_detected_arch;
    int m_major;
    int m_minor;
    QString m_gpu_name;
};

#endif // ENGINE_TRT_ARCH_DETECTOR_H