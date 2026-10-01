#ifndef ENGINE_TRT_RUNTIME_H
#define ENGINE_TRT_RUNTIME_H

// Silence TensorRT 11 internal header deprecation warnings
#if defined(_MSC_VER)
#pragma warning(push)
#pragma warning(disable: 4996)
#endif

#include <NvInfer.h>
#include <cuda_runtime.h>

#if defined(_MSC_VER)
#pragma warning(pop)
#endif

#include <QString>
#include <string>
#include <vector>
#include <memory>
#include <atomic>

// Name + shape of one engine IO tensor (from ICudaEngine introspection).
struct TrtIoTensor {
    std::string name;
    bool is_input = false;
    nvinfer1::DataType dtype = nvinfer1::DataType::kFLOAT;
    nvinfer1::Dims shape{};                 // engine-level shape (-1 = dynamic)
    nvinfer1::Dims profile_min{};           // profile 0 bounds (0 dims = unknown)
    nvinfer1::Dims profile_opt{};
    nvinfer1::Dims profile_max{};
};

// ==========================================================
// 1. TENSORRT INTERNAL LOGGER BRIDGE
// ==========================================================
class TrtLogger : public nvinfer1::ILogger {
public:
    void log(Severity severity, const char* msg) noexcept override;
};

// ==========================================================
// 2. RAII DEVICE MEMORY WRAPPER (cudaMalloc / cudaFree)
// ==========================================================
class GpuBuffer {
public:
    GpuBuffer();
    explicit GpuBuffer(size_t size_bytes);
    ~GpuBuffer();

    GpuBuffer(const GpuBuffer&) = delete;
    GpuBuffer& operator=(const GpuBuffer&) = delete;

    GpuBuffer(GpuBuffer&& other) noexcept;
    GpuBuffer& operator=(GpuBuffer&& other) noexcept;

    bool allocate(size_t size_bytes);
    void release();

    void* data() const { return m_ptr; }
    size_t size() const { return m_size; }
    bool empty() const { return m_ptr == nullptr; }

private:
    void* m_ptr = nullptr;
    size_t m_size = 0;
};

// ==========================================================
// 3. RAII PINNED HOST MEMORY (cudaMallocHost / cudaFreeHost)
// ==========================================================
class PinnedBuffer {
public:
    PinnedBuffer();
    explicit PinnedBuffer(size_t size_bytes);
    ~PinnedBuffer();

    PinnedBuffer(const PinnedBuffer&) = delete;
    PinnedBuffer& operator=(const PinnedBuffer&) = delete;

    PinnedBuffer(PinnedBuffer&& other) noexcept;
    PinnedBuffer& operator=(PinnedBuffer&& other) noexcept;

    bool allocate(size_t size_bytes);
    void release();

    void* data() const { return m_ptr; }
    size_t size() const { return m_size; }
    bool empty() const { return m_ptr == nullptr; }

private:
    void* m_ptr = nullptr;
    size_t m_size = 0;
};

// ==========================================================
// 4. UNIFIED TENSORRT MODEL ENGINE CONTEXT
// ==========================================================
class TrtModel {
public:
    TrtModel();
    ~TrtModel();

    bool load_from_file(const QString& engine_filepath, nvinfer1::IRuntime* runtime);
    void unload();

    // Atomic so the UI thread can query residency while a worker unloads the engine.
    bool is_loaded() const { return m_resident.load(std::memory_order_acquire); }

    // Dynamic Shape & Tensor Binding APIs (V3)
    bool set_input_shape(const char* tensor_name, const nvinfer1::Dims& dims);
    bool set_tensor_address(const char* tensor_name, void* data_ptr);
    nvinfer1::Dims get_tensor_shape(const char* tensor_name) const;

    // Clamps `dims` (in place) to the engine's optimization-profile bounds.
    // enqueueV3 fails with "invalid argument" in the reformatter when an input
    // shape falls outside the [min, max] the engine was built for, so callers
    // must clamp before set_input_shape. Returns false if the shape cannot be
    // satisfied at all (e.g. rank mismatch).
    bool clamp_to_profile(const char* tensor_name, nvinfer1::Dims& dims) const;

    // Asynchronous Execution on dedicated worker CUDA stream
    bool forward(cudaStream_t stream);

    // Introspection: dump every IO tensor (name, mode, dtype, shape, profile
    // bounds) into the log at load time. Guard against silent tensor-name drift.
    std::vector<TrtIoTensor> describe_io_tensors() const;

    // Profile bounds of `tensor_name` in profile 0. Returns false if unknown.
    bool get_profile_bounds(const char* tensor_name, nvinfer1::Dims& min_dims,
        nvinfer1::Dims& max_dims) const;

    size_t get_device_memory_size() const;
    QString get_model_name() const { return m_engine_name; }

private:
    QString m_engine_name;
    std::atomic<bool> m_resident{ false };
    std::unique_ptr<nvinfer1::ICudaEngine> m_engine;
    std::unique_ptr<nvinfer1::IExecutionContext> m_context;
};

// ==========================================================
// 5. MASTER TENSORRT RUNTIME SINGLETON
// ==========================================================
class trt_runtime {
public:
    static trt_runtime& instance();

    bool init();
    void shutdown();

    nvinfer1::IRuntime* get_runtime() { return m_runtime.get(); }
    cudaStream_t get_worker_stream() { return m_worker_stream; }

    static size_t volume(const nvinfer1::Dims& dims);
    static size_t element_size(nvinfer1::DataType type);

private:
    trt_runtime();
    ~trt_runtime();
    trt_runtime(const trt_runtime&) = delete;
    trt_runtime& operator=(const trt_runtime&) = delete;

    TrtLogger m_logger;
    std::unique_ptr<nvinfer1::IRuntime> m_runtime;
    cudaStream_t m_worker_stream = nullptr;
    bool m_initialized = false;
};

#endif // ENGINE_TRT_RUNTIME_H