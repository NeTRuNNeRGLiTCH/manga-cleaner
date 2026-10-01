#ifndef CORE_IMAGE_OPS_INPAINT_ROUTER_H
#define CORE_IMAGE_OPS_INPAINT_ROUTER_H

#include <opencv2/opencv.hpp>
#include <algorithm>
#include "src/core/pipeline/ai_types.h"

// ==========================================================
// Inpaint engine router (header-only, shared by the Studio
// worker and the Wizard batch worker).
// ==========================================================
namespace inpaint_router {

// A mask region counts as "simple" when the strip of pixels around it is a flat
// fill: at most `max_colors` distinct quantized colors, or a smooth single-hue
// gradient (screentones, flat shading, plain paper). Anything else - detailed
// line art, patterns, characters behind the text - needs Moebius.
inline bool region_surrounding_is_simple(
    const cv::Mat& image_rgb,
    const cv::Mat& binary_region,   // CV_8UC1 {0,255}, same size as image
    int max_colors = 3)
{
    if (image_rgb.empty() || binary_region.empty()) return false;
    if (image_rgb.size() != binary_region.size()) return false;

    // Dilate the region to build a ring around it, then the ring = dilated - region.
    cv::Mat dilated;
    cv::dilate(binary_region, dilated,
        cv::getStructuringElement(cv::MORPH_ELLIPSE, cv::Size(31, 31)));
    cv::Mat ring = dilated & ~binary_region;

    cv::Mat mask_u8;
    cv::threshold(ring, mask_u8, 127, 255, cv::THRESH_BINARY);
    if (cv::countNonZero(mask_u8) < 32) return false; // too tight to judge

    // Sample ring pixels and quantize each channel to 32 levels (8:1 compression):
    // gradients of a single hue collapse to a few neighboring bins.
    // The session page may be RGBA (PNG scans keep their alpha) - calcHist wants
    // a dense CV_8UC3 mat, so normalize every channel layout to BGR first.
    cv::Mat bgr;
    if (image_rgb.channels() == 4)      cv::cvtColor(image_rgb, bgr, cv::COLOR_RGBA2BGR);
    else if (image_rgb.channels() == 3) cv::cvtColor(image_rgb, bgr, cv::COLOR_RGB2BGR);
    else                                cv::cvtColor(image_rgb, bgr, cv::COLOR_GRAY2BGR);
    const int hist_size[] = { 32, 32, 32 };

    cv::Mat hist;
    int channels[] = { 0, 1, 2 };
    // calcHist needs ONE [lo,hi] pair PER DIMENSION - two pairs for three dims
    // reads out of bounds and trips the ranges[i] assertion.
    const float ch_range[2] = { 0.0f, 256.0f };
    const float* ranges[3] = { ch_range, ch_range, ch_range };
    cv::calcHist(&bgr, 1, channels, mask_u8, hist, 3, hist_size, ranges, true);

    const int total = cv::countNonZero(mask_u8);
    const int significant = std::max(1, total / 100); // >= 1% of the ring

    int used_bins = 0;
    int peaks = 0;
    for (int r = 0; r < 32; ++r) {
        for (int g = 0; g < 32; ++g) {
            for (int b = 0; b < 32; ++b) {
                const float v = hist.at<float>(r, g, b);
                if (v >= static_cast<float>(significant)) {
                    ++used_bins;
                    // Gradient smoothness: every occupied bin must touch the
                    // dominant bin in at least two channels (a diagonal jump in
                    // all three channels means a genuinely different color).
                    int touches = 0;
                    for (int dr = -1; dr <= 1; ++dr) {
                        for (int dg = -1; dg <= 1; ++dg) {
                            for (int db = -1; db <= 1; ++db) {
                                const int nr = r + dr, ng = g + dg, nb = b + db;
                                if (nr < 0 || nr >= 32 || ng < 0 || ng >= 32 || nb < 0 || nb >= 32) continue;
                                if (hist.at<float>(nr, ng, nb) > v) { ++touches; break; }
                            }
                        }
                    }
                    if (touches >= 2) ++peaks;
                }
            }
        }
    }

    return used_bins <= max_colors && peaks <= 3;
}

inline bool mask_is_simple_bubble(const cv::Mat& image_rgb, const cv::Mat& mask) {
    if (mask.empty() || mask.type() != CV_8UC1) return false;
    if (image_rgb.empty() || image_rgb.size() != mask.size()) return false;

    cv::Mat labels, stats, centroids;
    const int num_labels = cv::connectedComponentsWithStats(mask, labels, stats, centroids, 8, CV_32S);

    int components = 0;
    int simple = 0;
    long long largest = 0;

    for (int i = 1; i < num_labels; ++i) {
        const int area = stats.at<int>(i, cv::CC_STAT_AREA);
        if (area < 10) continue; // stray noise pixel

        ++components;
        largest = std::max<long long>(largest, area);

        // Judge only the component's bounding ROI - extracting (labels == i)
        // over the full page allocates a full-size Mat per component. Pad the
        // box by the ring radius so the ring still sees the same pixels the
        // full-page version did.
        constexpr int kRingPad = 16; // 31x31 ring reaches ~15px past the bbox
        const cv::Rect box(stats.at<int>(i, cv::CC_STAT_LEFT), stats.at<int>(i, cv::CC_STAT_TOP),
            stats.at<int>(i, cv::CC_STAT_WIDTH), stats.at<int>(i, cv::CC_STAT_HEIGHT));
        const cv::Rect padded(
            std::max(0, box.x - kRingPad),
            std::max(0, box.y - kRingPad),
            std::min(image_rgb.cols, box.x + box.width + kRingPad) - std::max(0, box.x - kRingPad),
            std::min(image_rgb.rows, box.y + box.height + kRingPad) - std::max(0, box.y - kRingPad));
        cv::Mat region = (labels(padded) == i);
        if (region_surrounding_is_simple(image_rgb(padded), region)) ++simple;
    }

    if (components == 0) return false;

    // Too fragmented, or one region swallowing a third of the page => hard mask.
    if (components > 24) return false;
    if (largest > static_cast<long long>(mask.rows) * mask.cols / 3) return false;

    // The majority of detected regions must sit on simple backgrounds.
    return simple * 2 >= components;
}

// Turns a user/AI request into a concrete engine choice.
// Auto: flat/gradient surroundings (few quantized colors) -> LaMa; anything
// structurally rich -> Moebius.
inline InpaintEngine resolve(InpaintEngine requested, const cv::Mat& image_rgb, const cv::Mat& mask) {
    if (requested != InpaintEngine::Auto) return requested;
    return mask_is_simple_bubble(image_rgb, mask) ? InpaintEngine::LaMa : InpaintEngine::Moebius;
}

} // namespace inpaint_router

#endif // CORE_IMAGE_OPS_INPAINT_ROUTER_H
