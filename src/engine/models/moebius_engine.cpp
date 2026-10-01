#include "moebius_engine.h"
#include "src/engine/trt_arch_detector.h"
#include "src/core/pipeline/task_queue.h"
#include "src/diagnostics/logger.h"
#include <cuda_fp16.h>
#include <random>
#include "src/core/image_ops/mask_tiling.h"
#include <algorithm>
#include <cmath>

moebius_engine::moebius_engine() : m_is_ada(false), m_unet_batch(1) {
    init_ddim_schedule();
}

moebius_engine::~moebius_engine() {
    unload();
}

void moebius_engine::init_ddim_schedule() {
    m_alphas_cumprod.resize(1000);
    const float beta_start = 0.00085f;
    const float beta_end = 0.0120f;
    float prod = 1.0f;

    for (int i = 0; i < 1000; ++i) {
        float beta = beta_start + (beta_end - beta_start) * (static_cast<float>(i) / 999.0f);
        float alpha = 1.0f - beta;
        prod *= alpha;
        m_alphas_cumprod[i] = prod;
    }
}

bool moebius_engine::init() {
    if (is_loaded()) return true;

    m_is_ada = trt_arch_detector::instance().is_ada_or_newer();

    QString enc_path = trt_arch_detector::instance().get_engine_path("vae_encoder");
    QString unet_path = trt_arch_detector::instance().get_engine_path("moebius_unet");
    QString dec_path = trt_arch_detector::instance().get_engine_path("vae_decoder");

    LOG_INFO("Initializing Moebius Latent Inpainting Suite (" + QString(m_is_ada ? "Ada-class GPU" : "Turing-class GPU") + ")...");

    if (!trt_runtime::instance().init()) {
        LOG_FATAL("Failed to initialize TensorRT Runtime for Moebius.");
        return false;
    }

    nvinfer1::IRuntime* runtime = trt_runtime::instance().get_runtime();

    if (!m_vae_encoder.load_from_file(enc_path, runtime) ||
        !m_unet.load_from_file(unet_path, runtime) ||
        !m_vae_decoder.load_from_file(dec_path, runtime)) {
        LOG_FATAL("Failed to deserialize Moebius TensorRT engines.");
        unload();
        return false;
    }

    // Allocate GPU and Pinned Memory Buffers (FP16 = 2 bytes). Every allocation
    // is checked: running inference against a null cudaMalloc result would only
    // surface as a cryptic CUDA error (or worse, a sticky one) mid-pipeline.
    // VAE Encoder: [B, 3, 512, 512] -> [B, 4, 64, 64]
    if (!m_gpu_enc_in.allocate(1 * 3 * 512 * 512 * sizeof(__half)) ||
        !m_gpu_enc_out.allocate(1 * 4 * 64 * 64 * sizeof(__half)) ||
        !m_pinned_enc_in.allocate(1 * 3 * 512 * 512 * sizeof(__half))) {
        LOG_FATAL("Moebius: failed to allocate VAE encoder buffers.");
        unload();
        return false;
    }

    // UNet batch must come from the ENGINE, not the GPU arch: the shipped pack is
    // static [1, 9, 64, 64] even on Lovelace. Binding [2, ...] against it fails.
    const nvinfer1::Dims unet_engine_shape = m_unet.get_tensor_shape("sample");
    m_unet_batch = (unet_engine_shape.nbDims > 0 && unet_engine_shape.d[0] > 0)
        ? static_cast<int>(unet_engine_shape.d[0]) : 1;
    if (m_unet_batch != 1 && m_unet_batch != 2) m_unet_batch = 1;
    const int unet_batch = m_unet_batch;
    LOG_INFO(QString("Moebius UNet working batch size: %1").arg(unet_batch));

    if (!m_gpu_unet_sample.allocate(unet_batch * 9 * 64 * 64 * sizeof(__half)) ||
        !m_gpu_unet_timestep.allocate(unet_batch * sizeof(int64_t)) || // engine tensor is INT64
        !m_gpu_unet_tokens.allocate(unet_batch * 10 * sizeof(int64_t)) ||
        !m_gpu_unet_out.allocate(unet_batch * 4 * 64 * 64 * sizeof(__half))) {
        LOG_FATAL("Moebius: failed to allocate UNet buffers.");
        unload();
        return false;
    }

    // VAE Decoder: [1, 4, 64, 64] -> [1, 3, 512, 512]
    if (!m_gpu_dec_in.allocate(1 * 4 * 64 * 64 * sizeof(__half)) ||
        !m_gpu_dec_out.allocate(1 * 3 * 512 * 512 * sizeof(__half)) ||
        !m_pinned_dec_out.allocate(1 * 3 * 512 * 512 * sizeof(__half))) {
        LOG_FATAL("Moebius: failed to allocate VAE decoder buffers.");
        unload();
        return false;
    }

    LOG_INFO("Moebius Latent Inpainting Suite successfully loaded into VRAM.");
    return true;
}

void moebius_engine::unload() {
    m_vae_encoder.unload();
    m_unet.unload();
    m_vae_decoder.unload();

    m_gpu_enc_in.release();
    m_gpu_enc_out.release();
    m_gpu_unet_sample.release();
    m_gpu_unet_timestep.release();
    m_gpu_unet_tokens.release();
    m_gpu_unet_out.release();
    m_gpu_dec_in.release();
    m_gpu_dec_out.release();

    m_pinned_enc_in.release();
    m_pinned_dec_out.release();

    LOG_INFO("Moebius Latent Inpainting Suite unloaded from VRAM.");
}

bool moebius_engine::is_loaded() const {
    return m_vae_encoder.is_loaded() && m_unet.is_loaded() && m_vae_decoder.is_loaded();
}

void moebius_engine::generate_random_latents(float* dst_ptr, size_t count) {
    static std::mt19937 rng(std::random_device{}());
    std::normal_distribution<float> dist(0.0f, 1.0f);
    for (size_t i = 0; i < count; ++i) {
        dst_ptr[i] = dist(rng);
    }
}

cv::Mat moebius_engine::inpaint_patch(const cv::Mat& rgb_512, const cv::Mat& mask_512, int ddim_steps) {
    if (rgb_512.empty() || mask_512.empty() || !is_loaded()) return cv::Mat();

    cudaStream_t stream = trt_runtime::instance().get_worker_stream();

    // ==========================================================
    // 1. PREPROCESSING (Cheatsheet)
    // ==========================================================
    // I_norm = (RGB / 127.5) - 1.0 in [-1.0, 1.0] (FLOAT16)
    // M_norm = (Mask > 127) ? 1.0 : 0.0
    // I_masked = I_norm * (1.0 - M_norm)
    __half* host_enc_in = static_cast<__half*>(m_pinned_enc_in.data());

    std::vector<float> mask_latent(64 * 64, 0.0f);

    // Downsample 512x512 mask to 64x64 mask_latent via Nearest Neighbor
    for (int y = 0; y < 64; ++y) {
        for (int x = 0; x < 64; ++x) {
            uchar m_val = mask_512.at<uchar>(y * 8, x * 8);
            mask_latent[y * 64 + x] = (m_val > 127) ? 1.0f : 0.0f;
        }
    }

    const size_t plane_stride = 512 * 512;
    for (int y = 0; y < 512; ++y) {
        const cv::Vec3b* row_ptr = rgb_512.ptr<cv::Vec3b>(y);
        const uchar* mask_row = mask_512.ptr<uchar>(y);
        size_t row_offset = static_cast<size_t>(y) * 512;

        for (int x = 0; x < 512; ++x) {
            const cv::Vec3b& pixel = row_ptr[x];
            float is_hole = (mask_row[x] > 127) ? 1.0f : 0.0f;
            float keep = 1.0f - is_hole;

            float r = ((pixel[0] / 127.5f) - 1.0f) * keep;
            float g = ((pixel[1] / 127.5f) - 1.0f) * keep;
            float b = ((pixel[2] / 127.5f) - 1.0f) * keep;

            host_enc_in[row_offset + x] = __float2half(r);
            host_enc_in[plane_stride + row_offset + x] = __float2half(g);
            host_enc_in[(2 * plane_stride) + row_offset + x] = __float2half(b);
        }
    }

    // ==========================================================
    // 2. VAE ENCODE (Cheatsheet: NO external scaling)
    // ==========================================================
    cudaMemcpyAsync(m_gpu_enc_in.data(), host_enc_in, 3 * 512 * 512 * sizeof(__half), cudaMemcpyHostToDevice, stream);

    // The encoder input "sample" is DYNAMIC [-1,3,512,512]: without an explicit
    // setInputShape, enqueueV3 fails with "Not all shapes are specified: sample".
    if (!m_vae_encoder.set_input_shape("sample", nvinfer1::Dims4{ 1, 3, 512, 512 })) {
        LOG_ERROR("Moebius VAE encoder rejected its input shape.");
        return cv::Mat();
    }

    // Tensor names verified against the shipped engines (trt_probe --smoke):
    //   vae_encoder: in "sample" -> out "latents"
    //   vae_decoder: in "latents" -> out "sample"
    m_vae_encoder.set_tensor_address("sample", m_gpu_enc_in.data());
    m_vae_encoder.set_tensor_address("latents", m_gpu_enc_out.data());
    if (!m_vae_encoder.forward(stream)) {
        LOG_ERROR("Moebius VAE encoder forward pass failed. Skipping this patch.");
        return cv::Mat();
    }

    std::vector<float> masked_latents(4 * 64 * 64);
    std::vector<__half> masked_latents_half(4 * 64 * 64);
    cudaMemcpyAsync(masked_latents_half.data(), m_gpu_enc_out.data(), 4 * 64 * 64 * sizeof(__half), cudaMemcpyDeviceToHost, stream);
    cudaStreamSynchronize(stream);

    for (size_t i = 0; i < 4 * 64 * 64; ++i) {
        masked_latents[i] = __half2float(masked_latents_half[i]);
    }

    // ==========================================================
    // 3. NOISE INIT: randn([1, 4, 64, 64]) (FLOAT16)
    // ==========================================================
    std::vector<float> latents(4 * 64 * 64);
    generate_random_latents(latents.data(), latents.size());

    // ==========================================================
    // 4. 30 DDIM INPAINTING STEPS (Linspace 999 down to 0)
    // ==========================================================
    int num_steps = std::clamp(ddim_steps, 10, 50);
    std::vector<int> timesteps(num_steps);
    for (int i = 0; i < num_steps; ++i) {
        float ratio = static_cast<float>(i) / static_cast<float>(num_steps - 1);
        timesteps[i] = static_cast<int>(std::round(999.0f * (1.0f - ratio)));
    }

    const int32_t cond_tokens[10] = { 0, 1, 2, 3, 4, 5, 6, 7, 8, 9 };
    const int32_t uncond_tokens[10] = { 10, 11, 12, 13, 14, 15, 16, 17, 18, 19 };

    std::vector<float> noise_cond(4 * 64 * 64);
    std::vector<float> noise_uncond(4 * 64 * 64);

    // Scratch buffers hoisted out of the DDIM loop: allocating these 30x per
    // inference was pure allocator churn on the critical path.
    std::vector<__half> unet_in_9ch(9 * 64 * 64);
    std::vector<__half> batch2_in(m_unet_batch == 2 ? 2 * 9 * 64 * 64 : 0);
    std::vector<__half> batch2_out(m_unet_batch == 2 ? 2 * 4 * 64 * 64 : 0);
    std::vector<__half> out_half(4 * 64 * 64);

    for (int step = 0; step < num_steps; ++step) {
        // Cooperative cancellation: 30 UNet passes take many seconds; without
        // this checkpoint the Stop button could not interrupt a patch mid-run.
        if (task_cancel_requested()) {
            LOG_INFO("Moebius inpainting cancelled by user at DDIM step " + QString::number(step + 1));
            return cv::Mat();
        }

        int t = timesteps[step];
        int t_prev = (step < num_steps - 1) ? timesteps[step + 1] : 0;

        float alpha_bar_t = m_alphas_cumprod[t];
        float alpha_bar_prev = (step < num_steps - 1) ? m_alphas_cumprod[t_prev] : 1.0f;

        // Build 9-Channel UNet Input: [latents(4), mask_latent(1), masked_latents(4)]
        for (int c = 0; c < 4; ++c) {
            for (int i = 0; i < 64 * 64; ++i) {
                unet_in_9ch[c * 64 * 64 + i] = __float2half(latents[c * 64 * 64 + i]);
            }
        }
        for (int i = 0; i < 64 * 64; ++i) {
            unet_in_9ch[4 * 64 * 64 + i] = __float2half(mask_latent[i]);
        }
        for (int c = 0; c < 4; ++c) {
            for (int i = 0; i < 64 * 64; ++i) {
                unet_in_9ch[(5 + c) * 64 * 64 + i] = __float2half(masked_latents[c * 64 * 64 + i]);
            }
        }

        if (m_unet_batch == 2) {
            // === BATCH 2 PARALLEL (only if the engine itself is [2, 9, 64, 64]) ===
            std::copy(unet_in_9ch.begin(), unet_in_9ch.end(), batch2_in.begin());
            std::copy(unet_in_9ch.begin(), unet_in_9ch.end(), batch2_in.begin() + 9 * 64 * 64);

            int64_t batch2_t[2] = { t, t };
            int64_t batch2_tokens[20];
            for (int i = 0; i < 10; ++i) { batch2_tokens[i] = cond_tokens[i]; batch2_tokens[10 + i] = uncond_tokens[i]; }

            cudaMemcpyAsync(m_gpu_unet_sample.data(), batch2_in.data(), 2 * 9 * 64 * 64 * sizeof(__half), cudaMemcpyHostToDevice, stream);
            cudaMemcpyAsync(m_gpu_unet_timestep.data(), batch2_t, 2 * sizeof(int64_t), cudaMemcpyHostToDevice, stream);
            cudaMemcpyAsync(m_gpu_unet_tokens.data(), batch2_tokens, 20 * sizeof(int64_t), cudaMemcpyHostToDevice, stream);

            m_unet.set_tensor_address("sample", m_gpu_unet_sample.data());
            m_unet.set_tensor_address("timestep", m_gpu_unet_timestep.data());
            m_unet.set_tensor_address("category_tokens", m_gpu_unet_tokens.data());
            m_unet.set_tensor_address("noise_pred", m_gpu_unet_out.data());
            if (!m_unet.forward(stream)) {
                LOG_ERROR("Moebius UNet forward pass failed. Skipping this patch.");
                return cv::Mat();
            }

            cudaMemcpyAsync(batch2_out.data(), m_gpu_unet_out.data(), 2 * 4 * 64 * 64 * sizeof(__half), cudaMemcpyDeviceToHost, stream);
            cudaStreamSynchronize(stream);

            for (size_t i = 0; i < 4 * 64 * 64; ++i) {
                noise_cond[i] = __half2float(batch2_out[i]);
                noise_uncond[i] = __half2float(batch2_out[4 * 64 * 64 + i]);
            }
        }
        else {
            // === BATCH 1 SEQUENTIAL (shipped pack) ===
            cudaMemcpyAsync(m_gpu_unet_sample.data(), unet_in_9ch.data(), 9 * 64 * 64 * sizeof(__half), cudaMemcpyHostToDevice, stream);
            int64_t t_single[1] = { t };
            cudaMemcpyAsync(m_gpu_unet_timestep.data(), t_single, sizeof(int64_t), cudaMemcpyHostToDevice, stream);

            // Pass 1: Cond
            int64_t cond_i64[10];
            int64_t uncond_i64[10];
            for (int i = 0; i < 10; ++i) { cond_i64[i] = cond_tokens[i]; uncond_i64[i] = uncond_tokens[i]; }
            cudaMemcpyAsync(m_gpu_unet_tokens.data(), cond_i64, 10 * sizeof(int64_t), cudaMemcpyHostToDevice, stream);
            m_unet.set_tensor_address("sample", m_gpu_unet_sample.data());
            m_unet.set_tensor_address("timestep", m_gpu_unet_timestep.data());
            m_unet.set_tensor_address("category_tokens", m_gpu_unet_tokens.data());
            m_unet.set_tensor_address("noise_pred", m_gpu_unet_out.data());
            if (!m_unet.forward(stream)) {
                LOG_ERROR("Moebius UNet forward pass failed. Skipping this patch.");
                return cv::Mat();
            }

            cudaMemcpyAsync(out_half.data(), m_gpu_unet_out.data(), 4 * 64 * 64 * sizeof(__half), cudaMemcpyDeviceToHost, stream);
            cudaStreamSynchronize(stream);
            for (size_t i = 0; i < 4 * 64 * 64; ++i) noise_cond[i] = __half2float(out_half[i]);

            // Pass 2: Uncond
            cudaMemcpyAsync(m_gpu_unet_tokens.data(), uncond_i64, 10 * sizeof(int64_t), cudaMemcpyHostToDevice, stream);
            if (!m_unet.forward(stream)) {
                LOG_ERROR("Moebius UNet forward pass failed. Skipping this patch.");
                return cv::Mat();
            }
            cudaMemcpyAsync(out_half.data(), m_gpu_unet_out.data(), 4 * 64 * 64 * sizeof(__half), cudaMemcpyDeviceToHost, stream);
            cudaStreamSynchronize(stream);
            for (size_t i = 0; i < 4 * 64 * 64; ++i) noise_uncond[i] = __half2float(out_half[i]);
        }

        // === DDIM LATENT UPDATE MATH (Cheatsheet: CFG = 2.0) ===
        float sqrt_alpha_t = std::sqrt(alpha_bar_t);
        float sqrt_one_minus_alpha_t = std::sqrt(1.0f - alpha_bar_t);
        float sqrt_alpha_prev = std::sqrt(alpha_bar_prev);
        float sqrt_one_minus_alpha_prev = std::sqrt(std::max(0.0f, 1.0f - alpha_bar_prev));

#pragma omp parallel for
        for (int i = 0; i < 4 * 64 * 64; ++i) {
            float final_noise = noise_uncond[i] + 2.0f * (noise_cond[i] - noise_uncond[i]);
            float pred_x0 = (latents[i] - sqrt_one_minus_alpha_t * final_noise) / sqrt_alpha_t;
            latents[i] = sqrt_alpha_prev * pred_x0 + sqrt_one_minus_alpha_prev * final_noise;
        }
    }

    // ==========================================================
    // 5. VAE DECODE
    // ==========================================================
    std::vector<__half> final_latents_half(4 * 64 * 64);
    for (size_t i = 0; i < 4 * 64 * 64; ++i) {
        final_latents_half[i] = __float2half(latents[i]);
    }

    cudaMemcpyAsync(m_gpu_dec_in.data(), final_latents_half.data(), 4 * 64 * 64 * sizeof(__half), cudaMemcpyHostToDevice, stream);

    // Decoder input "latents" is likewise dynamic [-1,4,64,64].
    if (!m_vae_decoder.set_input_shape("latents", nvinfer1::Dims4{ 1, 4, 64, 64 })) {
        LOG_ERROR("Moebius VAE decoder rejected its input shape.");
        return cv::Mat();
    }
    m_vae_decoder.set_tensor_address("latents", m_gpu_dec_in.data());
    m_vae_decoder.set_tensor_address("sample", m_gpu_dec_out.data());
    if (!m_vae_decoder.forward(stream)) {
        LOG_ERROR("Moebius VAE decoder forward pass failed. Skipping this patch.");
        return cv::Mat();
    }

    __half* host_dec_out = static_cast<__half*>(m_pinned_dec_out.data());
    cudaMemcpyAsync(host_dec_out, m_gpu_dec_out.data(), 3 * 512 * 512 * sizeof(__half), cudaMemcpyDeviceToHost, stream);
    cudaStreamSynchronize(stream);

    // Pixel_clean = clamp((Output + 1.0) * 127.5, 0, 255) (RGB)
    cv::Mat clean_rgb(512, 512, CV_8UC3);

#pragma omp parallel for
    for (int y = 0; y < 512; ++y) {
        cv::Vec3b* row = clean_rgb.ptr<cv::Vec3b>(y);
        size_t offset = static_cast<size_t>(y) * 512;

        for (int x = 0; x < 512; ++x) {
            float r = __half2float(host_dec_out[offset + x]);
            float g = __half2float(host_dec_out[plane_stride + offset + x]);
            float b = __half2float(host_dec_out[(2 * plane_stride) + offset + x]);

            row[x][0] = static_cast<uchar>(std::clamp((r + 1.0f) * 127.5f, 0.0f, 255.0f));
            row[x][1] = static_cast<uchar>(std::clamp((g + 1.0f) * 127.5f, 0.0f, 255.0f));
            row[x][2] = static_cast<uchar>(std::clamp((b + 1.0f) * 127.5f, 0.0f, 255.0f));
        }
    }

    return clean_rgb;
}

namespace {

// Re-applies the page's original alpha on top of an RGB result. Pages with an
// alpha channel arrive here as CV_8UC4; without this the composite would be
// returned as CV_8UC3 and crash the session paste with "Can't reallocate Mat
// with locked type".
cv::Mat restore_alpha(const cv::Mat& rgb3, const cv::Mat& alpha_from)
{
    cv::Mat out(rgb3.size(), CV_8UC4);
    for (int y = 0; y < rgb3.rows; ++y) {
        const cv::Vec3b* src = rgb3.ptr<cv::Vec3b>(y);
        const cv::Vec4b* src4 = alpha_from.ptr<cv::Vec4b>(y);
        cv::Vec4b* dst = out.ptr<cv::Vec4b>(y);
        for (int x = 0; x < rgb3.cols; ++x) {
            dst[x] = cv::Vec4b(src[x][0], src[x][1], src[x][2], src4[x][3]);
        }
    }
    return out;
}

// Blends the inpainted result into the page with a 2px feather inside the
// paste region. Tiled boundaries land on mask-quiet bands, but this removes
// any residual 1px step where two tiles reconstructed the same glyph.
void paste_blended(cv::Mat& page_rgb, const cv::Mat& tile_result,
    const cv::Mat& tile_mask, const cv::Rect& roi)
{
    cv::Mat feather;
    cv::dilate(tile_mask, feather,
        cv::getStructuringElement(cv::MORPH_RECT, cv::Size(5, 5)));
    cv::blur(feather, feather, cv::Size(5, 5));

    cv::Mat dst = page_rgb(roi);
    for (int y = 0; y < tile_result.rows; ++y) {
        const cv::Vec3b* s = tile_result.ptr<cv::Vec3b>(y);
        const cv::Vec3b* orig = dst.ptr<cv::Vec3b>(y);
        cv::Vec3b* d = dst.ptr<cv::Vec3b>(y);
        const uchar* m = feather.ptr<uchar>(y);
        for (int x = 0; x < tile_result.cols; ++x) {
            // Hard paste inside the mask, feathered only at its rim.
            const float w = (tile_mask.at<uchar>(y, x) > 127)
                ? 1.0f : (m[x] / 255.0f) * 0.9f;
            if (w <= 0.0f) continue;
            const cv::Vec3f blend =
                (1.0f - w) * cv::Vec3f(orig[x]) + w * cv::Vec3f(s[x]);
            d[x] = cv::Vec3b(
                static_cast<uchar>(std::clamp(blend[0] + 0.5f, 0.0f, 255.0f)),
                static_cast<uchar>(std::clamp(blend[1] + 0.5f, 0.0f, 255.0f)),
                static_cast<uchar>(std::clamp(blend[2] + 0.5f, 0.0f, 255.0f)));
        }
    }
}

} // namespace

bool moebius_engine::inpaint_image(
    cv::Mat& full_image_rgb,
    const cv::Mat& full_mask,
    const std::vector<cv::Point>& bubble_centers,
    int ddim_steps,
    std::function<void(int, int)> progress_cb)
{
    (void)bubble_centers; // API symmetry: work units are the mask components
                          // themselves, which cover every detected AND
                          // hand-drawn region.

    if (full_image_rgb.empty() || full_mask.empty()) return false;
    if (!is_loaded() && !init()) return false;

    // The engines are RGB-only: normalize RGBA pages (they crash the session
    // paste with a type-locked Mat) and grayscale pages to CV_8UC3. The page's
    // original alpha is re-applied after the last tile.
    cv::Mat page;
    int code = -1;
    if (full_image_rgb.channels() == 4) code = cv::COLOR_RGBA2RGB;
    else if (full_image_rgb.channels() == 3) code = -1;
    else if (full_image_rgb.channels() == 1) code = cv::COLOR_GRAY2RGB;
    if (code >= 0) cv::cvtColor(full_image_rgb, page, code);
    else page = full_image_rgb.clone();

    const cv::Mat alpha_from = (full_image_rgb.channels() == 4)
        ? full_image_rgb.clone() : cv::Mat();

    // Units of work: every mask component (detected text + manual strokes).
    // bubble_centers from detection are only seed hints and can miss hand-drawn
    // regions entirely - covering components directly can never skip a mask.
    cv::Mat labels, stats, centroids;
    const int num_labels = cv::connectedComponentsWithStats(full_mask, labels, stats, centroids, 8, CV_32S);

    struct WorkUnit { cv::Rect crop; std::vector<cv::Rect> tiles; int label; };
    std::vector<WorkUnit> units;

    for (int i = 1; i < num_labels; ++i) {
        if (stats.at<int>(i, cv::CC_STAT_AREA) < 10) continue;

        WorkUnit unit;
        unit.label = i;
        unit.crop = mask_tiling::component_crop(
            cv::Rect(stats.at<int>(i, cv::CC_STAT_LEFT), stats.at<int>(i, cv::CC_STAT_TOP),
                stats.at<int>(i, cv::CC_STAT_WIDTH), stats.at<int>(i, cv::CC_STAT_HEIGHT)),
            full_mask.size(), 48); // context margin so the model sees around the text
        unit.tiles = mask_tiling::split_region(full_mask, unit.crop, 512);
        if (!unit.tiles.empty()) units.push_back(std::move(unit));
    }

    int total_tiles = 0;
    for (const WorkUnit& u : units) total_tiles += static_cast<int>(u.tiles.size());

    LOG_INFO(QString("Moebius inpainting %1 mask regions (%2 tiles <= 512px)...")
        .arg(units.size()).arg(total_tiles));

    int done = 0;
    int failed_tiles = 0;

    for (const WorkUnit& unit : units) {
        cv::Mat unit_mask = (labels(unit.crop) == unit.label);

        for (const cv::Rect& tile_roi : unit.tiles) {
            if (task_cancel_requested()) {
                LOG_WARN("Moebius inpainting cancelled by user.");
                return false;
            }

            // tile_roi is in PAGE coordinates, but unit_mask is crop-local:
            // index it with the converted rect or the ROI goes out of bounds.
            const cv::Rect local_roi(tile_roi.x - unit.crop.x, tile_roi.y - unit.crop.y,
                tile_roi.width, tile_roi.height);

            cv::Mat tile = page(tile_roi);
            cv::Mat tile_mask = unit_mask(local_roi);

            // Pad undersized edge tiles to the fixed 512x512 input.
            cv::Mat tile512, mask512;
            if (tile.cols != 512 || tile.rows != 512) {
                cv::copyMakeBorder(tile, tile512, 0, 512 - tile.rows, 0, 512 - tile.cols,
                    cv::BORDER_REFLECT_101);
                cv::copyMakeBorder(tile_mask, mask512, 0, 512 - tile_mask.rows, 0, 512 - tile_mask.cols,
                    cv::BORDER_CONSTANT, cv::Scalar(0));
            }
            else {
                tile512 = tile;
                mask512 = tile_mask;
            }

            cv::Mat clean512 = inpaint_patch(tile512, mask512, ddim_steps);
            ++done;

            if (clean512.empty()) {
                ++failed_tiles; // Never paste anything from a failed inference.
            }
            else {
                cv::Mat clean_crop = clean512(cv::Rect(0, 0, tile.cols, tile.rows));
                paste_blended(page, clean_crop, tile_mask, tile_roi);
            }

            if (progress_cb) progress_cb(done, total_tiles);
        }
    }

    if (failed_tiles > 0) {
        LOG_ERROR(QString("Moebius inpainting: %1/%2 tiles failed (GPU error - nothing was pasted for them).")
            .arg(failed_tiles).arg(total_tiles));
        return false;
    }

    full_image_rgb = alpha_from.empty() ? page : restore_alpha(page, alpha_from);

    LOG_INFO("Moebius inpainting completed successfully.");
    return true;
}