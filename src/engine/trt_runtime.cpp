#if defined(_MSC_VER)
#pragma warning(disable: 4996)
#endif

#include "trt_runtime.h"
#include "src/diagnostics/logger.h"
#include <QFile>
#include <QFileInfo>
#include <sstream>

// ==========================================================
// 1. TENSORRT LOGGER IMPLEMENTATION
// ==========================================================
void TrtLogger::log(Severity severity, const char* msg) noexcept {
    switch (severity) {
    case Severity::kINTERNAL_ERROR:
    case Severity::kERROR:
        LOG_ERROR(QString("[TensorRT Error] ") + msg);
        break;
    case Severity::kWARNING:
        LOG_WARN(QString("[TensorRT Warning] ") + msg);
        break;
    case Severity::kINFO:
    case Severity::kVERBOSE:
        break;
    }
}

// ==========================================================
// 2. GPU BUFFER (VRAM)
// ==========================================================
GpuBuffer::GpuBuffer() : m_ptr(nullptr), m_size(0) {}

GpuBuffer::GpuBuffer(size_t size_bytes) : m_ptr(nullptr), m_size(0) {
    allocate(size_bytes);
}

GpuBuffer::~GpuBuffer() {
    release();
}

GpuBuffer::GpuBuffer(GpuBuffer&& other) noexcept : m_ptr(other.m_ptr), m_size(other.m_size) {
    other.m_ptr = nullptr;
    other.m_size = 0;
}

GpuBuffer& GpuBuffer::operator=(GpuBuffer&& other) noexcept {
    if (this != &other) {
        release();
        m_ptr = other.m_ptr;
        m_size = other.m_size;
        other.m_ptr = nullptr;
        other.m_size = 0;
    }
    return *this;
}

bool GpuBuffer::allocate(size_t size_bytes) {
    if (size_bytes == 0) return false;
    if (m_ptr && m_size >= size_bytes) return true;

    release();

    cudaError_t err = cudaMalloc(&m_ptr, size_bytes);
    if (err != cudaSuccess) {
        LOG_FATAL(QString("cudaMalloc failed to allocate %1 MB: %2")
            .arg(size_bytes / (1024.0 * 1024.0), 0, 'f', 2)
            .arg(cudaGetErrorString(err)));
        m_ptr = nullptr;
        m_size = 0;
        return false;
    }

    m_size = size_bytes;
    return true;
}

void GpuBuffer::release() {
    if (m_ptr) {
        cudaFree(m_ptr);
        m_ptr = nullptr;
        m_size = 0;
    }
}

// ==========================================================
// 3. PINNED HOST BUFFER (Page-locked RAM)
// ==========================================================
PinnedBuffer::PinnedBuffer() : m_ptr(nullptr), m_size(0) {}

PinnedBuffer::PinnedBuffer(size_t size_bytes) : m_ptr(nullptr), m_size(0) {
    allocate(size_bytes);
}

PinnedBuffer::~PinnedBuffer() {
    release();
}

PinnedBuffer::PinnedBuffer(PinnedBuffer&& other) noexcept : m_ptr(other.m_ptr), m_size(other.m_size) {
    other.m_ptr = nullptr;
    other.m_size = 0;
}

PinnedBuffer& PinnedBuffer::operator=(PinnedBuffer&& other) noexcept {
    if (this != &other) {
        release();
        m_ptr = other.m_ptr;
        m_size = other.m_size;
        other.m_ptr = nullptr;
        other.m_size = 0;
    }
    return *this;
}

bool PinnedBuffer::allocate(size_t size_bytes) {
    if (size_bytes == 0) return false;
    if (m_ptr && m_size >= size_bytes) return true;

    release();

    cudaError_t err = cudaMallocHost(&m_ptr, size_bytes);
    if (err != cudaSuccess) {
        LOG_ERROR(QString("cudaMallocHost failed: ") + cudaGetErrorString(err));
        m_ptr = nullptr;
        m_size = 0;
        return false;
    }

    m_size = size_bytes;
    return true;
}

void PinnedBuffer::release() {
    if (m_ptr) {
        cudaFreeHost(m_ptr);
        m_ptr = nullptr;
        m_size = 0;
    }
}

// ==========================================================
// 4. TRT MODEL IMPLEMENTATION
// ==========================================================
TrtModel::TrtModel() {}

TrtModel::~TrtModel() {
    unload();
}

void TrtModel::unload() {
    // Flag down first: a concurrent is_loaded() must never report residency for
    // buffers that are about to be freed.
    m_resident.store(false, std::memory_order_release);
    m_context.reset();
    m_engine.reset();
    m_engine_name.clear();
}

bool TrtModel::load_from_file(const QString& engine_filepath, nvinfer1::IRuntime* runtime) {
    if (!runtime) {
        LOG_ERROR("Cannot deserialize engine: TensorRT IRuntime is null.");
        return false;
    }

    unload();

    QFileInfo fi(engine_filepath);
    m_engine_name = fi.fileName();

    LOG_INFO("Loading TensorRT engine: " + engine_filepath);

    QFile file(engine_filepath);
    if (!file.open(QIODevice::ReadOnly)) {
        LOG_ERROR("Failed to open TensorRT engine file: " + engine_filepath);
        return false;
    }

    QByteArray engine_data = file.readAll();
    file.close();

    if (engine_data.isEmpty()) {
        LOG_ERROR("Engine file is empty: " + engine_filepath);
        return false;
    }

    m_engine.reset(runtime->deserializeCudaEngine(engine_data.constData(), engine_data.size()));
    if (!m_engine) {
        LOG_FATAL("Failed to deserialize CUDA engine for: " + m_engine_name);
        return false;
    }

    // Pre-flight: the execution context allocates its full activation memory
    // (profile-max bound, baked into the engine at build time) at creation, and
    // TensorRT 11 hard-validates that bound even for user-managed pools. There
    // is no runtime way to shrink it, so when it cannot fit we fail here with
    // an actionable message instead of a raw cudaError 2 OOM + poisoned allocator.
    const size_t required = get_device_memory_size();
    size_t free_bytes = 0, total_bytes = 0;
    if (required > 0 && cudaMemGetInfo(&free_bytes, &total_bytes) == cudaSuccess) {
        constexpr size_t kMargin = 384ull * 1024ull * 1024ull; // io buffers + CUDA scratch headroom
        if (required + kMargin > free_bytes) {
            LOG_FATAL(QString("Cannot create execution context for '%1': it needs %2 MB of VRAM but only %3 MB is free. "
                "This bound was baked into the engine at build time - rebuild the engine with a smaller "
                "max profile (e.g. trtexec --maxShapes=input:1x3x512x512) or use a GPU with more VRAM.")
                .arg(m_engine_name)
                .arg(required / (1024.0 * 1024.0), 0, 'f', 0)
                .arg(free_bytes / (1024.0 * 1024.0), 0, 'f', 0));
            m_engine.reset();
            return false;
        }
    }

    m_context.reset(m_engine->createExecutionContext());
    if (!m_context) {
        LOG_FATAL("Failed to create execution context for: " + m_engine_name);
        m_engine.reset();
        return false;
    }

    m_resident.store(true, std::memory_order_release);

    LOG_INFO(QString("Successfully loaded '%1' [Activation Memory: %2 MB]")
        .arg(m_engine_name)
        .arg(get_device_memory_size() / (1024.0 * 1024.0), 0, 'f', 1));

    // Log the engine's real IO contract. These names/shapes/dtypes were hard-coded
    // per engine before and drifted from the actual packs (e.g. a VAE encoder that
    // takes "sample", not "image"), producing failures that were painful to trace.
    for (const TrtIoTensor& t : describe_io_tensors()) {
        std::ostringstream oss;
        oss << "  " << (t.is_input ? "IN " : "OUT") << " \"" << t.name << "\" dtype="
            << static_cast<int>(t.dtype) << " shape=[";
        for (int i = 0; i < t.shape.nbDims; ++i) oss << (i ? "," : "") << t.shape.d[i];
        oss << "]";
        if (t.profile_max.nbDims > 0) {
            oss << " profile[min=[";
            for (int i = 0; i < t.profile_min.nbDims; ++i) oss << (i ? "," : "") << t.profile_min.d[i];
            oss << "] max=[";
            for (int i = 0; i < t.profile_max.nbDims; ++i) oss << (i ? "," : "") << t.profile_max.d[i];
            oss << "]]";
        }
        LOG_INFO(QString("TensorIO %1:%2").arg(m_engine_name, QString::fromStdString(oss.str())));
    }

    return true;
}

bool TrtModel::clamp_to_profile(const char* tensor_name, nvinfer1::Dims& dims) const {
    if (!m_engine) return false;

    // The shipped packs define a single optimization profile per engine.
    // (Dims64 has no isValid(); an undefined shape comes back with nbDims <= 0.)
    const nvinfer1::Dims min_d = m_engine->getProfileShape(tensor_name, 0, nvinfer1::OptProfileSelector::kMIN);
    const nvinfer1::Dims max_d = m_engine->getProfileShape(tensor_name, 0, nvinfer1::OptProfileSelector::kMAX);
    if (min_d.nbDims <= 0 || max_d.nbDims <= 0) return true; // Unknown bounds: leave untouched.
    if (min_d.nbDims != dims.nbDims || max_d.nbDims != dims.nbDims) return false;

    bool clamped = false;
    for (int i = 0; i < dims.nbDims; ++i) {
        const int64_t lo = std::max<int64_t>(1, min_d.d[i]);
        int64_t v = dims.d[i];

        if (v < lo) { v = lo; clamped = true; }
        if (max_d.d[i] > 0 && v > max_d.d[i]) { v = max_d.d[i]; clamped = true; }
        dims.d[i] = v;
    }

    if (clamped) {
        LOG_WARN(QString("Input '%1' shape clamped to the engine's optimization profile bounds.")
            .arg(tensor_name));
    }
    return true;
}

bool TrtModel::set_input_shape(const char* tensor_name, const nvinfer1::Dims& dims) {
    if (!m_context) return false;

    // setInputShape silently returns false for out-of-profile shapes and the
    // failure only surfaces later as an enqueueV3 reformat error. Surface it now.
    if (!m_context->setInputShape(tensor_name, dims)) {
        LOG_ERROR(QString("setInputShape rejected for '%1' (outside optimization profile?).").arg(tensor_name));
        return false;
    }
    return true;
}

bool TrtModel::set_tensor_address(const char* tensor_name, void* data_ptr) {
    if (!m_context) return false;
    return m_context->setTensorAddress(tensor_name, data_ptr);
}

nvinfer1::Dims TrtModel::get_tensor_shape(const char* tensor_name) const {
    if (!m_context) return nvinfer1::Dims{ 0 };
    return m_context->getTensorShape(tensor_name);
}

bool TrtModel::forward(cudaStream_t stream) {
    if (!m_context) {
        LOG_ERROR("Execution context is null during forward pass.");
        return false;
    }

    bool status = m_context->enqueueV3(stream);
    if (!status) {
        LOG_ERROR(QString("enqueueV3 failed for engine: ") + m_engine_name);

        // CUDA errors are sticky for the whole process. Clear them, otherwise every
        // later operation - including unrelated engines and future cudaMallocs -
        // inherits this failure and the app never recovers.
        const cudaError_t last = cudaGetLastError();
        if (last != cudaSuccess) {
            LOG_WARN(QString("Cleared sticky CUDA error after failed forward: %1")
                .arg(cudaGetErrorString(last)));
        }
        return false;
    }

    return true;
}

std::vector<TrtIoTensor> TrtModel::describe_io_tensors() const {
    std::vector<TrtIoTensor> out;
    if (!m_engine) return out;

    const int32_t count = m_engine->getNbIOTensors();
    out.reserve(count);
    for (int32_t i = 0; i < count; ++i) {
        const char* name = m_engine->getIOTensorName(i);
        if (!name) continue;

        TrtIoTensor t;
        t.name = name;
        t.is_input = (m_engine->getTensorIOMode(name) == nvinfer1::TensorIOMode::kINPUT);
        t.dtype = m_engine->getTensorDataType(name);
        t.shape = m_engine->getTensorShape(name);

        if (t.is_input) {
            t.profile_min = m_engine->getProfileShape(name, 0, nvinfer1::OptProfileSelector::kMIN);
            t.profile_opt = m_engine->getProfileShape(name, 0, nvinfer1::OptProfileSelector::kOPT);
            t.profile_max = m_engine->getProfileShape(name, 0, nvinfer1::OptProfileSelector::kMAX);
        }
        out.push_back(std::move(t));
    }
    return out;
}

bool TrtModel::get_profile_bounds(const char* tensor_name, nvinfer1::Dims& min_dims, nvinfer1::Dims& max_dims) const {
    if (!m_engine) return false;

    min_dims = m_engine->getProfileShape(tensor_name, 0, nvinfer1::OptProfileSelector::kMIN);
    max_dims = m_engine->getProfileShape(tensor_name, 0, nvinfer1::OptProfileSelector::kMAX);
    if (min_dims.nbDims <= 0 || max_dims.nbDims <= 0) return false;
    return true;
}

size_t TrtModel::get_device_memory_size() const {
    if (!m_engine) return 0;
    // TensorRT 11 V2 API
    return static_cast<size_t>(m_engine->getDeviceMemorySizeV2());
}

// ==========================================================
// 5. TRT RUNTIME SINGLETON IMPLEMENTATION
// ==========================================================
trt_runtime& trt_runtime::instance() {
    static trt_runtime _instance;
    return _instance;
}

trt_runtime::trt_runtime() : m_initialized(false) {}

trt_runtime::~trt_runtime() {
    shutdown();
}

bool trt_runtime::init() {
    if (m_initialized) return true;

    LOG_INFO("Initializing Bare-Metal TensorRT Core Runtime...");

    m_runtime.reset(nvinfer1::createInferRuntime(m_logger));
    if (!m_runtime) {
        LOG_FATAL("Failed to create TensorRT IRuntime instance.");
        return false;
    }

    cudaError_t err = cudaStreamCreateWithFlags(&m_worker_stream, cudaStreamNonBlocking);
    if (err != cudaSuccess) {
        LOG_ERROR(QString("Failed to create worker CUDA stream: ") + cudaGetErrorString(err));
        return false;
    }

    m_initialized = true;
    LOG_INFO("TensorRT Core Runtime and CUDA Worker Stream initialized.");
    return true;
}

void trt_runtime::shutdown() {
    if (!m_initialized) return;

    LOG_INFO("Shutting down TensorRT Core Runtime...");

    if (m_worker_stream) {
        cudaStreamSynchronize(m_worker_stream);
        cudaStreamDestroy(m_worker_stream);
        m_worker_stream = nullptr;
    }

    m_runtime.reset();
    m_initialized = false;
}

size_t trt_runtime::volume(const nvinfer1::Dims& dims) {
    if (dims.nbDims <= 0) return 0;
    size_t vol = 1;
    for (int i = 0; i < dims.nbDims; ++i) {
        vol *= dims.d[i];
    }
    return vol;
}

size_t trt_runtime::element_size(nvinfer1::DataType type) {
    switch (type) {
    case nvinfer1::DataType::kFLOAT: return 4;
    case nvinfer1::DataType::kHALF:  return 2;
    case nvinfer1::DataType::kINT8:  return 1;
    case nvinfer1::DataType::kINT32: return 4;
    case nvinfer1::DataType::kBOOL:  return 1;
    case nvinfer1::DataType::kUINT8: return 1;
    default: return 4;
    }
}