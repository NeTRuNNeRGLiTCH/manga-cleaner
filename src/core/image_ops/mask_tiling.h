#ifndef CORE_IMAGE_OPS_MASK_TILING_H
#define CORE_IMAGE_OPS_MASK_TILING_H

#include <opencv2/opencv.hpp>
#include <vector>
#include <limits>

// ==========================================================
// Mask-region tiling for inpainting engines with a fixed
// maximum input size (LaMa <= 1024px, Moebius = 512px).
//
// The masked areas (connected mask components) are the units
// of work: each component's bounding box is padded with
// context and, when it still exceeds the engine's bound, cut
// into non-overlapping tiles. Cuts always fall on the
// quietest band of mask pixels (letter/word gaps), so a tile
// boundary cannot slice a glyph and no pasted outputs ever
// overlap (hard project rule).
// ==========================================================
namespace mask_tiling {

// Splits `region` (page coordinates) into tiles of at most
// `max_side` x `max_side` pixels. Returns the tile rects.
inline std::vector<cv::Rect> split_region(
    const cv::Mat& page_mask,   // CV_8UC1 {0,255}, full page
    const cv::Rect& region,
    int max_side)
{
    std::vector<cv::Rect> out;
    if (page_mask.empty() || region.width <= 0 || region.height <= 0) return out;
    const cv::Rect page(0, 0, page_mask.cols, page_mask.rows);
    const cv::Rect seed = region & page;
    if (seed.area() <= 0) return out;

    if (seed.width <= max_side && seed.height <= max_side) {
        out.push_back(seed);
        return out;
    }

    // Breadth-first split: every tile that is still too large is cut on its
    // longer axis through the mask-quietest column/row (search band keeps a
    // 20% margin on each side so tiles never degenerate to slivers).
    std::vector<cv::Rect> work{ seed };
    while (!work.empty()) {
        const cv::Rect r = work.back();
        work.pop_back();

        if (r.width <= max_side && r.height <= max_side) {
            out.push_back(r);
            continue;
        }

        if (r.width >= r.height) {
            const int lo = r.x + std::max(1, r.width / 5);
            const int hi = r.x + r.width - std::max(1, r.width / 5);
            int best = lo, best_count = std::numeric_limits<int>::max();
            for (int x = lo; x <= hi; ++x) {
                const int cnt = cv::countNonZero(page_mask(cv::Rect(x, r.y, 1, r.height)));
                if (cnt < best_count) { best_count = cnt; best = x; }
            }
            work.push_back(cv::Rect(r.x, r.y, best - r.x, r.height));
            work.push_back(cv::Rect(best, r.y, r.x + r.width - best, r.height));
        }
        else {
            const int lo = r.y + std::max(1, r.height / 5);
            const int hi = r.y + r.height - std::max(1, r.height / 5);
            int best = lo, best_count = std::numeric_limits<int>::max();
            for (int y = lo; y <= hi; ++y) {
                const int cnt = cv::countNonZero(page_mask(cv::Rect(r.x, y, r.width, 1)));
                if (cnt < best_count) { best_count = cnt; best = y; }
            }
            work.push_back(cv::Rect(r.x, r.y, r.width, best - r.y));
            work.push_back(cv::Rect(r.x, best, r.width, r.y + r.height - best));
        }
    }
    return out;
}

// Padded bounding box of a mask component, clamped to the page.
inline cv::Rect component_crop(const cv::Rect& box, const cv::Size& page_size, int pad_px)
{
    const int x0 = std::max(0, box.x - pad_px);
    const int y0 = std::max(0, box.y - pad_px);
    const int x1 = std::min(page_size.width, box.x + box.width + pad_px);
    const int y1 = std::min(page_size.height, box.y + box.height + pad_px);
    return cv::Rect(x0, y0, x1 - x0, y1 - y0);
}

} // namespace mask_tiling

#endif // CORE_IMAGE_OPS_MASK_TILING_H
