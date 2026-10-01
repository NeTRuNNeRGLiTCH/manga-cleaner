#ifndef ENGINE_MODELS_MOEBIUS_ENGINE_H
#define ENGINE_MODELS_MOEBIUS_ENGINE_H

#include <opencv2/opencv.hpp>
#include <vector>
#include <memory>
#include <functional>
#include "src/engine/trt_runtime.h"

class moebius_engine {
public:
    moebius_engine();
    ~moebius_engine();

    bool init();
    void unload();
    bool is_loaded() const;

    // Stage 2: Inpaint a single 512x512 tile
    cv::Mat inpaint_patch(
        const cv::Mat& rgb_512,
        const cv::Mat& mask_512,
        int ddim_steps = 30
    );

    // Stage 2: Batch Inpaint all detected bubble centers on full manga image
    bool inpaint_image(
        cv::Mat& full_image_rgb,
        const cv::Mat& full_mask,
        const std::vector<cv::Point>& bubble_centers,
        int ddim_steps = 30,
        std::function<void(int current, int total)> progress_cb = nullptr
    );

private:
    TrtModel m_vae_encoder;
    TrtModel m_unet;
    TrtModel m_vae_decoder;

    bool m_is_ada;

    // Working UNet batch size, resolved from the engine itself at init
    // (the shipped pack is static [1, 9, 64, 64] regardless of GPU arch).
    int m_unet_batch = 1;

    // GPU Memory Buffers
    GpuBuffer m_gpu_enc_in;
    GpuBuffer m_gpu_enc_out;

    GpuBuffer m_gpu_unet_sample;
    GpuBuffer m_gpu_unet_timestep;
    GpuBuffer m_gpu_unet_tokens;
    GpuBuffer m_gpu_unet_out;

    GpuBuffer m_gpu_dec_in;
    GpuBuffer m_gpu_dec_out;

    // Pinned Host Buffers for ultra-fast transfers
    PinnedBuffer m_pinned_enc_in;
    PinnedBuffer m_pinned_dec_out;

    // Precomputed DDIM Alpha Cumulative Product Schedule (1000 steps)
    std::vector<float> m_alphas_cumprod;
    void init_ddim_schedule();

    // Latent Generation Helper
    void generate_random_latents(float* dst_ptr, size_t count);
};

#endif // ENGINE_MODELS_MOEBIUS_ENGINE_H