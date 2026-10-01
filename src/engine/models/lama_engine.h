#ifndef ENGINE_MODELS_LAMA_ENGINE_H
#define ENGINE_MODELS_LAMA_ENGINE_H

#include <opencv2/opencv.hpp>
#include <vector>
#include <memory>
#include <functional>
#include "src/engine/trt_runtime.h"

class lama_engine {
public:
    lama_engine();
    ~lama_engine();

    bool init();
    void unload();
    bool is_loaded() const;

    // Inpaint a single speech bubble crop (>= 512x512, multiple of 32)
    cv::Mat inpaint_patch(
        const cv::Mat& rgb_crop,
        const cv::Mat& mask_crop
    );

    // Batch Inpaint all detected text bubbles on the full manga page
    bool inpaint_image(
        cv::Mat& full_image_rgb,
        const cv::Mat& full_mask,
        const std::vector<cv::Point>& bubble_centers,
        std::function<void(int current, int total)> progress_cb = nullptr
    );

private:
    TrtModel m_model;
    bool m_is_ada;
    size_t m_max_pixels; // Pre-allocated buffer capacity (1024x1024)

    // GPU VRAM Buffers
    GpuBuffer m_gpu_image;
    GpuBuffer m_gpu_mask;
    GpuBuffer m_gpu_output;

    // Pinned Host Buffers (Page-locked for instant transfers)
    PinnedBuffer m_pinned_image;
    PinnedBuffer m_pinned_mask;
    PinnedBuffer m_pinned_output;

    void pack_fp32_nchw(const cv::Mat& rgb_padded, const cv::Mat& mask_padded, float* dst_img, float* dst_mask);
    void unpack_fp32_nchw(const float* src_output, int h, int w, cv::Mat& dst_rgb);
};

#endif // ENGINE_MODELS_LAMA_ENGINE_H