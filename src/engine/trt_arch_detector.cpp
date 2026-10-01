#include "trt_arch_detector.h"
#include "src/diagnostics/logger.h"
#include "src/storage/config_mgr.h"

#include <QCoreApplication>
#include <QDir>
#include <QFileInfo>
#include <QStringList>

trt_arch_detector& trt_arch_detector::instance() {
    static trt_arch_detector _instance;
    return _instance;
}

trt_arch_detector::trt_arch_detector() : m_detected_arch(GpuArch::Unknown), m_major(0), m_minor(0) {
    detect_hardware();
}

void trt_arch_detector::refresh() {
    detect_hardware();
}

void trt_arch_detector::detect_hardware() {
    LOG_INFO("Scanning GPU Microarchitecture via CUDA Runtime...");

    int device_count = 0;
    cudaError_t err = cudaGetDeviceCount(&device_count);

    if (err != cudaSuccess || device_count == 0) {
        LOG_ERROR("No CUDA-compatible GPU detected! Falling back to Turing profile.");
        m_detected_arch = GpuArch::Turing;
        m_major = 7;
        m_minor = 5;
        m_gpu_name = "Generic CUDA Device";
        return;
    }

    cudaDeviceProp prop;
    cudaGetDeviceProperties(&prop, 0); // Primary GPU

    m_major = prop.major;
    m_minor = prop.minor;
    m_gpu_name = prop.name;

    int sm_code = (m_major * 10) + m_minor;

    LOG_INFO(QString("GPU Detected: %1 | Compute Capability: SM %2.%3 (Code: %4)")
        .arg(m_gpu_name).arg(m_major).arg(m_minor).arg(sm_code));

    // 1. Check if user configured a manual override in Settings
    int override_mode = config_mgr::instance().get_settings().arch_dispatch_mode;
    if (override_mode == 1) {
        LOG_INFO("Manual Override Active: Forcing Ada Lovelace Profile (Batch 2 / 800px)");
        m_detected_arch = GpuArch::Lovelace;
        return;
    }
    else if (override_mode == 2) {
        LOG_INFO("Manual Override Active: Forcing Turing Profile (Batch 1 / 512px - 4GB Safe)");
        m_detected_arch = GpuArch::Turing;
        return;
    }

    // 2. Automatic Hardware Classification
    if (m_major >= 10 || (m_major == 9 && m_minor >= 0)) {
        m_detected_arch = GpuArch::Blackwell; // SM 10.x / 12.x
    }
    else if (m_major == 8 && m_minor == 9) {
        m_detected_arch = GpuArch::Lovelace;  // SM 8.9 (RTX 40xx)
    }
    else if (m_major == 8 && (m_minor == 0 || m_minor == 6)) {
        m_detected_arch = GpuArch::Ampere;    // SM 8.0 / 8.6 (RTX 30xx)
    }
    else if (m_major == 7 && m_minor == 5) {
        m_detected_arch = GpuArch::Turing;    // SM 7.5 (RTX 20xx, GTX 16xx)
    }
    else {
        LOG_WARN(QString("Unrecognized SM %1.%2. Defaulting to Turing profile for maximum safety.").arg(m_major).arg(m_minor));
        m_detected_arch = GpuArch::Turing;
    }

    LOG_INFO("Hardware Router selected architecture subfolder: " + get_arch_folder());
}

GpuArch trt_arch_detector::get_current_arch() const {
    return m_detected_arch;
}

QString trt_arch_detector::get_arch_name() const {
    switch (m_detected_arch) {
    case GpuArch::Blackwell: return "Blackwell (SM 10.x / 12.x)";
    case GpuArch::Lovelace:  return "Ada Lovelace (SM 8.9)";
    case GpuArch::Ampere:    return "Ampere (SM 8.0 / 8.6)";
    case GpuArch::Turing:    return "Turing (SM 7.5)";
    default:                 return "Turing (Fallback)";
    }
}

QString trt_arch_detector::get_arch_folder() const {
    switch (m_detected_arch) {
    case GpuArch::Blackwell: return "blackwell";
    case GpuArch::Lovelace:  return "lovelace";
    case GpuArch::Ampere:    return "ampere";
    case GpuArch::Turing:    return "turing";
    default:                 return "turing";
    }
}

int trt_arch_detector::get_compute_capability() const {
    return (m_major * 10) + m_minor;
}

bool trt_arch_detector::is_ada_or_newer() const {
    return (m_detected_arch == GpuArch::Lovelace || m_detected_arch == GpuArch::Blackwell);
}

bool trt_arch_detector::is_turing() const {
    return (m_detected_arch == GpuArch::Turing || m_detected_arch == GpuArch::Ampere);
}

QString trt_arch_detector::get_engine_path(const QString& base_name) const {
    const QString root = QCoreApplication::applicationDirPath() + "/models";

    // Accept both "lama" and "lama.engine" so callers can pass a stem.
    QString base = base_name;
    if (base.endsWith(".engine", Qt::CaseInsensitive)) base.chop(7);
    if (base.isEmpty()) return root + "/" + base_name;

    // Engine packs are named "<base>_<arch>.engine", so the arch folder and the file
    // suffix must stay in sync. Search the detected arch first, then the closest pack
    // that actually ships engines (Blackwell/Ampere folders are empty in current packs).
    QStringList folders;
    auto push_folder = [&folders](const QString& folder) {
        if (!folder.isEmpty() && !folders.contains(folder)) folders << folder;
    };

    push_folder(get_arch_folder());
    if (is_ada_or_newer()) {
        push_folder("lovelace");
        push_folder("turing");
    } else {
        push_folder("ampere");
        push_folder("turing");
        push_folder("lovelace");
    }

    for (const QString& folder : folders) {
        const QString primary = QDir(root).filePath(folder + "/" + base + "_" + folder + ".engine");
        if (QFileInfo::exists(primary)) return primary;

        const QString unsuffixed = QDir(root).filePath(folder + "/" + base + ".engine");
        if (QFileInfo::exists(unsuffixed)) return unsuffixed;
    }

    // Last resort: loose files dropped straight into models/.
    const QStringList root_names{ base + "_lovelace.engine", base + "_turing.engine", base + ".engine" };
    for (const QString& name : root_names) {
        const QString path = QDir(root).filePath(name);
        if (QFileInfo::exists(path)) return path;
    }

    LOG_ERROR(QString("Could not locate TensorRT engine '%1' in any models/ subfolder.").arg(base_name));
    return QDir(root).filePath(get_arch_folder() + "/" + base + "_" + get_arch_folder() + ".engine");
}