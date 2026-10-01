#ifndef ENGINE_MODELS_TEXTBPN_ENGINE_H
#define ENGINE_MODELS_TEXTBPN_ENGINE_H

#include <opencv2/opencv.hpp>
#include <vector>
#include <memory>
#include "src/engine/trt_runtime.h"

// Output package returned by TextBPN++
struct TextBpnResult {
    cv::Mat full_mask;                       // Dilated binary mask (CV_8UC1)
    std::vector<cv::Point> bubble_centers;   // (cx, cy) coordinates for Moebius inpainting
    int num_bubbles = 0;
};

class textbpn_engine {
public:
    textbpn_engine();
    ~textbpn_engine();

    bool init();
    void unload();
    bool is_loaded() const;

    // Stage 1: Full-Image Detection with Vertical Slicing & Dual-Threshold Filtering
    // min_bubble_area: post-filter that discards connected masks below this area (px).
    // dilation_radius: EXTRA padding on top of the guaranteed 8px text coverage.
    TextBpnResult detect(
        const cv::Mat& src_rgb,
        float cls_threshold = 0.65f,
        float dis_threshold = 0.35f,
        int min_bubble_area = 100,
        int dilation_radius = 0
    );

private:
    TrtModel m_model;

    // Output channel count from the loaded engine ([1, C, H, W]; shipped packs: C = 4).
    int m_out_channels = 4;

    // Reusable GPU & Host staging buffers
    GpuBuffer m_gpu_input;
    GpuBuffer m_gpu_output;
    PinnedBuffer m_pinned_input;
    PinnedBuffer m_pinned_output;

    // Slicing & Preprocessing helpers
    cv::Mat run_single_tile(const cv::Mat& tile_rgb, cv::Mat& out_dis_tile);
    void pack_imagenet_nchw(const cv::Mat& rgb_padded, float* dst_ptr);

    // Magic-wand-style text completion. The dis core only fires on the most
    // confident stroke pixels, so glyph edges, antialiased pixels, small
    // glyphs ("I") and gaps between letters can end up OUTSIDE the raw mask.
    // From the seed cores, a frontier sweep hops up to `reach_px` in each
    // direction per round and claims pixels the network still rates as text
    // (weak dis response above `dis_floor` AND at least `cls_floor`
    // confidence - so background/screentone speckles are never claimed).
    // The walk follows the network's own text probabilities - not any color -
    // so it works for any text color and stops where text ends (it never
    // floods the bubble interior). Then: close, dilate by `dilate_px`, and
    // fill enclosed holes (glyph counters like the inside of O/A/D).
    cv::Mat complete_text_mask(
        const cv::Mat& dis_map,        // CV_32FC1 text-core probability (full page)
        const cv::Mat& cls_map,        // CV_32FC1 text confidence (full page)
        const cv::Mat& seeds_binary,   // {0,255} accepted text cores
        float dis_floor,
        float cls_floor,
        int reach_px,
        int dilate_px) const;
};

#endif // ENGINE_MODELS_TEXTBPN_ENGINE_H