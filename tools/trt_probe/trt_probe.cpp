// Console probe: dumps every TensorRT engine's IO tensor names, dtypes, shapes,
// and optimization profiles (MIN/OPT/MAX). Run from the models/ root, e.g.:
//   trt_probe.exe x64/Release/models/lovelace
// Output goes to stdout AND appends to trt_probe_log.txt (no codebuff logger dependency).
#include <NvInfer.h>
#include <cuda_runtime.h>
#include <cuda_fp16.h>
#include <windows.h>
#include <string>
#include <fstream>
#include <cstring>
#include <cmath>
#include <iostream>
#include <memory>
#include <vector>

static std::ofstream g_log;
static size_t g_pool_bytes = 0; // optional user-managed activation pool (--pool MB)

static void out_line(const std::string& s) {
    std::cout << s << std::endl;
    if (g_log.is_open()) g_log << s << "\n" << std::flush;
}

class ProbeLogger : public nvinfer1::ILogger {
    void log(Severity severity, const char* msg) noexcept override {
        if (severity == Severity::kERROR) out_line(std::string("[TRT ERROR] ") + msg);
        else if (severity == Severity::kWARNING) out_line(std::string("[TRT WARN ] ") + msg);
    }
};

// Minimal RAII device buffer (mirrors the app's GpuBuffer, no logger dependency)
struct GpuBufferLocal {
    void* ptr = nullptr;
    size_t size = 0;
    bool allocate(size_t bytes) {
        if (cudaMalloc(&ptr, bytes) != cudaSuccess) { ptr = nullptr; return false; }
        size = bytes;
        return true;
    }
    void* data() const { return ptr; }
    ~GpuBufferLocal() { if (ptr) cudaFree(ptr); }
};

static const char* dtype_name(nvinfer1::DataType t) {
    switch (t) {
    case nvinfer1::DataType::kFLOAT: return "fp32";
    case nvinfer1::DataType::kHALF:  return "fp16";
    case nvinfer1::DataType::kINT8:  return "int8";
    case nvinfer1::DataType::kINT32: return "int32";
    case nvinfer1::DataType::kBOOL:  return "bool";
    case nvinfer1::DataType::kUINT8: return "uint8";
    default: return "?";
    }
}

static std::string dims_to_string(const nvinfer1::Dims& d) {
    std::string s = "[";
    for (int i = 0; i < d.nbDims; ++i) {
        if (i) s += ",";
        s += std::to_string(d.d[i]);
    }
    return s + "]";
}

// ==============================================================
// SMOKE MODE: run one real inference per engine using the exact
// tensor names / dtypes / shapes the app binds, so fixes are
// verified against the actual engine files.
// ==============================================================
static bool smoke_run(nvinfer1::ICudaEngine* engine, const std::string& path) {
    struct Binding { const char* name; nvinfer1::Dims dims; size_t elem_size; const void* host_src; };
    auto dims_of = [](std::initializer_list<int64_t> ds) {
        nvinfer1::Dims d{}; d.nbDims = static_cast<int>(ds.size());
        int i = 0; for (int64_t v : ds) d.d[i++] = v;
        return d;
    };
    std::string fname = path.substr(path.find_last_of("\\/") + 1);

    std::vector<Binding> in, out;
    std::vector<char> enc_in(3 * 512 * 512 * 2), enc_out(4 * 64 * 64 * 2);
    std::vector<char> unet_in(9 * 64 * 64 * 2), unet_t(8), unet_tok(10 * 8), unet_out(4 * 64 * 64 * 2);
    std::vector<char> dec_in(4 * 64 * 64 * 2), dec_out(3 * 512 * 512 * 2);
    std::vector<char> seg_in(3 * 2560 * 800 * 4), seg_out(4 * 2560 * 800 * 4);

    auto half_fill = [](std::vector<char>& buf, float lo, float hi) {
        __half* h = reinterpret_cast<__half*>(buf.data());
        for (size_t i = 0; i < buf.size() / 2; ++i)
            h[i] = __float2half(lo + (hi - lo) * (float)((i * 2654435761u) % 1000) / 1000.0f);
    };
    auto float_fill = [](std::vector<char>& buf, float lo, float hi) {
        float* f = reinterpret_cast<float*>(buf.data());
        for (size_t i = 0; i < buf.size() / 4; ++i)
            f[i] = lo + (hi - lo) * (float)((i * 2654435761u) % 1000) / 1000.0f;
    };

    if (fname.find("vae_encoder") == 0) {
        half_fill(enc_in, -1.0f, 1.0f);
        in = { { "sample", nvinfer1::Dims4{1,3,512,512}, 2, enc_in.data() } };
        out = { { "latents", nvinfer1::Dims4{1,4,64,64}, 2, nullptr } };
    } else if (fname.find("vae_decoder") == 0) {
        half_fill(dec_in, -1.0f, 1.0f);
        in = { { "latents", nvinfer1::Dims4{1,4,64,64}, 2, dec_in.data() } };
        out = { { "sample", nvinfer1::Dims4{1,3,512,512}, 2, nullptr } };
    } else if (fname.find("moebius_unet") == 0) {
        half_fill(unet_in, -2.0f, 2.0f);
        int64_t t = 999; std::memcpy(unet_t.data(), &t, 8);
        int64_t tok[10] = {0,1,2,3,4,5,6,7,8,9}; std::memcpy(unet_tok.data(), tok, 80);
        in = { { "sample", dims_of({1,9,64,64}), 2, unet_in.data() },
               { "timestep", dims_of({1}), 8, unet_t.data() },
               { "category_tokens", dims_of({1,10}), 8, unet_tok.data() } };
        out = { { "noise_pred", dims_of({1,4,64,64}), 2, nullptr } };
    } else if (fname.find("segmentation") == 0) {
        float_fill(seg_in, -2.5f, 2.5f);
        in = { { "input", nvinfer1::Dims4{1,3,2560,800}, 4, seg_in.data() } };
        out = { { "output", nvinfer1::Dims4{1,4,2560,800}, 4, nullptr } };
    } else if (fname.find("lama") == 0) {
        return true; // skipped: batch-2 opt needs a 2-element batch smoke; not used by fixed app paths here
    } else {
        out_line("  SMOKE SKIP (unknown engine)");
        return true;
    }

    std::unique_ptr<nvinfer1::IExecutionContext> ctx;
    std::unique_ptr<GpuBufferLocal> pool;
    if (g_pool_bytes > 0) {
        out_line("  SMOKE: using user-managed pool of " + std::to_string(g_pool_bytes / (1024 * 1024)) + " MB");
        pool = std::make_unique<GpuBufferLocal>();
        if (!pool->allocate(g_pool_bytes)) { out_line("  SMOKE FAIL: pool alloc"); return false; }
        ctx.reset(engine->createExecutionContext(nvinfer1::ExecutionContextAllocationStrategy::kUSER_MANAGED));
        if (ctx) ctx->setDeviceMemoryV2(pool->data(), static_cast<int64_t>(pool->size));
    }
    else {
        ctx.reset(engine->createExecutionContext());
    }
    if (!ctx) { out_line("  SMOKE FAIL: no context"); return false; }

    std::vector<void*> dev_in(in.size()), dev_out(out.size());
    for (size_t i = 0; i < in.size(); ++i) {
        if (!ctx->setInputShape(in[i].name, in[i].dims)) {
            out_line(std::string("  SMOKE FAIL: setInputShape rejected for ") + in[i].name);
            return false;
        }
        size_t bytes = in[i].elem_size; for (int d = 0; d < in[i].dims.nbDims; ++d) bytes *= in[i].dims.d[d];
        void* p = nullptr; if (cudaMalloc(&p, bytes) != cudaSuccess) { out_line("  SMOKE FAIL: cudaMalloc in"); return false; }
        cudaMemcpy(p, in[i].host_src, bytes, cudaMemcpyHostToDevice);
        if (!ctx->setTensorAddress(in[i].name, p)) {
            out_line(std::string("  SMOKE FAIL: setTensorAddress rejected for ") + in[i].name);
            return false;
        }
        dev_in[i] = p;
    }
    for (size_t i = 0; i < out.size(); ++i) {
        size_t bytes = out[i].elem_size; for (int d = 0; d < out[i].dims.nbDims; ++d) bytes *= out[i].dims.d[d];
        void* p = nullptr; if (cudaMalloc(&p, bytes) != cudaSuccess) { out_line("  SMOKE FAIL: cudaMalloc out"); return false; }
        if (!ctx->setTensorAddress(out[i].name, p)) {
            out_line(std::string("  SMOKE FAIL: setTensorAddress rejected for ") + out[i].name);
            return false;
        }
        dev_out[i] = p;
    }

    cudaStream_t stream; cudaStreamCreate(&stream);
    bool ok = ctx->enqueueV3(stream);
    cudaStreamSynchronize(stream);
    cudaStreamDestroy(stream);
    if (!ok) {
        out_line("  SMOKE FAIL: enqueueV3 returned false");
        for (void* p : dev_in) cudaFree(p);
        for (void* p : dev_out) cudaFree(p);
        return false;
    }

    // Sanity: outputs must not be all-zero / NaN
    for (size_t i = 0; i < out.size(); ++i) {
        size_t count = 1; for (int d = 0; d < out[i].dims.nbDims; ++d) count *= out[i].dims.d[d];
        std::vector<char> host(out[i].elem_size * std::min<size_t>(count, 4096));
        cudaMemcpy(host.data(), dev_out[i], host.size(), cudaMemcpyDeviceToHost);
        double sum = 0; bool nan = false; size_t n = host.size() / out[i].elem_size;
        if (out[i].elem_size == 2) {
            __half* h = reinterpret_cast<__half*>(host.data());
            for (size_t j = 0; j < n; ++j) { float v = __half2float(h[j]); if (std::isnan(v)) nan = true; sum += v; }
        } else {
            float* f = reinterpret_cast<float*>(host.data());
            for (size_t j = 0; j < n; ++j) { if (std::isnan(f[j])) nan = true; sum += f[j]; }
        }
        if (nan || sum == 0.0) {
            std::string msg = std::string("  SMOKE FAIL: output '") + out[i].name + (nan ? " contains NaN" : " is all zero");
            out_line(msg);
            for (void* p : dev_in) cudaFree(p);
            for (void* p : dev_out) cudaFree(p);
            return false;
        }
    }

    for (void* p : dev_in) cudaFree(p);
    for (void* p : dev_out) cudaFree(p);
    out_line("  SMOKE PASS");
    return true;
}

int main(int argc, char** argv) {
    bool smoke = false;
    const char* dir = ".";
    for (int i = 1; i < argc; ++i) {
        const std::string a = argv[i];
        if (a == "--smoke") smoke = true;
        else if (a.rfind("--pool=", 0) == 0) g_pool_bytes = static_cast<size_t>(std::stoull(a.substr(7))) * 1024ull * 1024ull;
        else dir = argv[i];
    }
    g_log.open("trt_probe_log.txt", std::ios::app);

    ProbeLogger logger;
    std::unique_ptr<nvinfer1::IRuntime> runtime(nvinfer1::createInferRuntime(logger));
    if (!runtime) { out_line("FATAL: createInferRuntime failed"); return 1; }

    WIN32_FIND_DATAA fd;
    std::string pattern = std::string(dir) + "\\*.engine";
    HANDLE h = FindFirstFileA(pattern.c_str(), &fd);
    if (h == INVALID_HANDLE_VALUE) { out_line(std::string("No .engine files under: ") + dir); return 1; }

    do {
        const std::string path = std::string(dir) + "\\" + fd.cFileName;
        out_line("================================================");
        out_line("ENGINE: " + path);

        std::ifstream f(path, std::ios::binary);
        if (!f) { out_line("  open failed"); continue; }
        std::vector<char> blob((std::istreambuf_iterator<char>(f)), std::istreambuf_iterator<char>());
        f.close();

        std::unique_ptr<nvinfer1::ICudaEngine> engine(runtime->deserializeCudaEngine(blob.data(), blob.size()));
        if (!engine) { out_line("  deserialize FAILED"); continue; }

        const int32_t n = engine->getNbIOTensors();
        out_line("  nbIOTensors: " + std::to_string(n));

        for (int32_t i = 0; i < n; ++i) {
            const char* name = engine->getIOTensorName(i);
            const nvinfer1::TensorIOMode mode = engine->getTensorIOMode(name);
            const nvinfer1::Dims shape = engine->getTensorShape(name);
            const nvinfer1::DataType dt = engine->getTensorDataType(name);
            out_line("  IO[" + std::to_string(i) + "] \"" + name + "\" "
                + ((mode == nvinfer1::TensorIOMode::kINPUT) ? "IN " : "OUT")
                + " " + dtype_name(dt) + " " + dims_to_string(shape));
        }

        const int32_t np = engine->getNbOptimizationProfiles();
        out_line("  nbOptimizationProfiles: " + std::to_string(np));
        for (int32_t p = 0; p < np; ++p) {
            for (int32_t i = 0; i < n; ++i) {
                const char* name = engine->getIOTensorName(i);
                if (engine->getTensorIOMode(name) != nvinfer1::TensorIOMode::kINPUT) continue;
                const nvinfer1::Dims mn = engine->getProfileShape(name, p, nvinfer1::OptProfileSelector::kMIN);
                const nvinfer1::Dims op = engine->getProfileShape(name, p, nvinfer1::OptProfileSelector::kOPT);
                const nvinfer1::Dims mx = engine->getProfileShape(name, p, nvinfer1::OptProfileSelector::kMAX);
                out_line("  profile[" + std::to_string(p) + "] \"" + name + "\" min " + dims_to_string(mn)
                    + " | opt " + dims_to_string(op) + " | max " + dims_to_string(mx));
            }
        }

        if (smoke) smoke_run(engine.get(), path);
    } while (FindNextFileA(h, &fd));
    FindClose(h);
    (void)fd;

    out_line("PROBE DONE");
    return 0;
}
