#include "lama_engine.h"
#include "src/engine/trt_arch_detector.h"
#include "src/core/pipeline/task_queue.h"
#include "src/diagnostics/logger.h"
#include "src/core/image_ops/mask_tiling.h"
#include <algorithm>
#include <cmath>

lama_engine::lama_engine() : m_is_ada(false), m_max_pixels(1024 * 1024) {}

lama_engine::~lama_engine() {
    unload();
}

bool lama_engine::init() {
    if (is_loaded()) return true;

    m_is_ada = trt_arch_detector::instance().is_ada_or_newer();
    QString resolved_path = trt_arch_detector::instance().get_engine_path("lama");

    LOG_INFO(QString("Initializing LaMa Fast Inpainter (%1)...: %2")
        .arg(m_is_ada ? "Ada Lovelace" : "Turing")
        .arg(resolved_path));

    if (!trt_runtime::instance().init()) {
        LOG_FATAL("Failed to initialize TensorRT Runtime for LaMa.");
        return false;
    }

    if (!m_model.load_from_file(resolved_path, trt_runtime::instance().get_runtime())) {
        LOG_FATAL("Failed to load LaMa engine file from: " + resolved_path);
        return false;
    }

    // Pre-allocate maximum GPU buffers up to 1024x1024 (Float32 = 4 bytes)
    // Image:  [1, 3, 1024, 1024] Float32 (~12 MB)
    // Mask:   [1, 1, 1024, 1024] Float32 (~4 MB)
    // Output: [1, 3, 1024, 1024] Float32 (~12 MB)
    size_t img_bytes = 1 * 3 * m_max_pixels * sizeof(float);
    size_t mask_bytes = 1 * 1 * m_max_pixels * sizeof(float);

    // Checked allocations: a silent cudaMalloc failure would send the first
    // inference into a null device pointer.
    if (!m_gpu_image.allocate(img_bytes) ||
        !m_gpu_mask.allocate(mask_bytes) ||
        !m_gpu_output.allocate(img_bytes) ||
        !m_pinned_image.allocate(img_bytes) ||
        !m_pinned_mask.allocate(mask_bytes) ||
        !m_pinned_output.allocate(img_bytes)) {
        LOG_FATAL("LaMa: failed to allocate GPU/pinned buffers.");
        unload();
        return false;
    }

    LOG_INFO("LaMa Fast Inpainter successfully initialized in VRAM.");
    return true;
}

void lama_engine::unload() {
    m_model.unload();
    m_gpu_image.release();
    m_gpu_mask.release();
    m_gpu_output.release();

    m_pinned_image.release();
    m_pinned_mask.release();
    m_pinned_output.release();

    LOG_INFO("LaMa Inpainter unloaded from VRAM.");
}

bool lama_engine::is_loaded() const {
    return m_model.is_loaded();
}

cv::Mat lama_engine::inpaint_patch(const cv::Mat& rgb_crop, const cv::Mat& mask_crop) {
    if (rgb_crop.empty() || mask_crop.empty() || !is_loaded()) return cv::Mat();

    int orig_h = rgb_crop.rows;
    int orig_w = rgb_crop.cols;

    // Buffers and the 1024px profile cap cannot hold anything larger; a bigger
    // crop would also make the padding below negative (cv::copyMakeBorder
    // throws on that). inpaint_image() only produces <= 1024px tiles.
    if (orig_h > 1024 || orig_w > 1024) {
        LOG_ERROR(QString("LaMa patch %1x%2 exceeds the 1024px engine bound.").arg(orig_w).arg(orig_h));
        return cv::Mat();
    }

    // 1. Ensure dimensions >= 512px, <= 1024px, and divisible by 32
    int target_h = std::max(512, ((orig_h + 31) / 32) * 32);
    int target_w = std::max(512, ((orig_w + 31) / 32) * 32);
    target_h = std::min(target_h, 1024);
    target_w = std::min(target_w, 1024);

    // Respect the engine's optimization profile; shapes outside it make enqueueV3
    // fail with "invalid argument". Buffers are sized for at most 1024x1024.
    nvinfer1::Dims4 req_dims{ 1, 3, target_h, target_w };
    if (!m_model.clamp_to_profile("image", req_dims)) {
        LOG_ERROR("LaMa input rank does not match the engine profile.");
        return cv::Mat();
    }
    target_h = std::min(static_cast<int>(req_dims.d[2]), 1024);
    target_w = std::min(static_cast<int>(req_dims.d[3]), 1024);

    int pad_bottom = target_h - orig_h;
    int pad_right = target_w - orig_w;

    cv::Mat padded_rgb, padded_mask;
    if (pad_bottom > 0 || pad_right > 0) {
        cv::copyMakeBorder(rgb_crop, padded_rgb, 0, pad_bottom, 0, pad_right, cv::BORDER_REPLICATE);
        cv::copyMakeBorder(mask_crop, padded_mask, 0, pad_bottom, 0, pad_right, cv::BORDER_CONSTANT, cv::Scalar(0));
    }
    else {
        padded_rgb = rgb_crop;
        padded_mask = mask_crop;
    }

    // 2. Preprocess: RGB -> [0.0, 1.0] Float32 NCHW & Mask -> {0.0, 1.0} Float32
    float* host_image = static_cast<float*>(m_pinned_image.data());
    float* host_mask = static_cast<float*>(m_pinned_mask.data());
    pack_fp32_nchw(padded_rgb, padded_mask, host_image, host_mask);

    cudaStream_t stream = trt_runtime::instance().get_worker_stream();

    // 3. Asynchronous Copy H2D
    size_t in_img_bytes = 1 * 3 * target_h * target_w * sizeof(float);
    size_t in_mask_bytes = 1 * 1 * target_h * target_w * sizeof(float);

    cudaMemcpyAsync(m_gpu_image.data(), host_image, in_img_bytes, cudaMemcpyHostToDevice, stream);
    cudaMemcpyAsync(m_gpu_mask.data(), host_mask, in_mask_bytes, cudaMemcpyHostToDevice, stream);

    // 4. Set Dynamic Input Shapes & Pointers
    if (!m_model.set_input_shape("image", nvinfer1::Dims4{ 1, 3, target_h, target_w }) ||
        !m_model.set_input_shape("mask", nvinfer1::Dims4{ 1, 1, target_h, target_w })) {
        LOG_ERROR("LaMa input shapes rejected by the engine profile.");
        return cv::Mat();
    }

    m_model.set_tensor_address("image", m_gpu_image.data());
    m_model.set_tensor_address("mask", m_gpu_mask.data());
    m_model.set_tensor_address("inpainted", m_gpu_output.data());

    // 5. Execute Single Forward Pass (Zero Loops, Fast Fourier Convolutions)
    if (!m_model.forward(stream)) {
        LOG_ERROR("LaMa forward pass failed.");
        return cv::Mat();
    }

    // 6. Asynchronous Copy D2H
    float* host_output = static_cast<float*>(m_pinned_output.data());
    cudaMemcpyAsync(host_output, m_gpu_output.data(), in_img_bytes, cudaMemcpyDeviceToHost, stream);
    cudaStreamSynchronize(stream);

    // 7. Postprocess: Float32 NCHW -> RGB uint8
    cv::Mat out_rgb(target_h, target_w, CV_8UC3);
    unpack_fp32_nchw(host_output, target_h, target_w, out_rgb);

    // 8. Crop back to original unpadded dimensions
    cv::Mat clean_crop = out_rgb(cv::Rect(0, 0, orig_w, orig_h));

    // 9. Direct Binary Stencil Composite (Zero Seam Math)
    cv::Mat final_patch = rgb_crop.clone();
    clean_crop.copyTo(final_patch, mask_crop);

    return final_patch;
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

bool lama_engine::inpaint_image(
    cv::Mat& full_image_rgb,
    const cv::Mat& full_mask,
    const std::vector<cv::Point>& bubble_centers,
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
        unit.tiles = mask_tiling::split_region(full_mask, unit.crop, 1024);
        if (!unit.tiles.empty()) units.push_back(std::move(unit));
    }

    int total_tiles = 0;
    for (const WorkUnit& u : units) total_tiles += static_cast<int>(u.tiles.size());

    LOG_INFO(QString("LaMa fast inpainting %1 mask regions (%2 tiles <= 1024px)...")
        .arg(units.size()).arg(total_tiles));

    int done = 0;
    int failed_tiles = 0;

    for (const WorkUnit& unit : units) {
        cv::Mat unit_mask = (labels(unit.crop) == unit.label);

        for (const cv::Rect& tile_roi : unit.tiles) {
            if (task_cancel_requested()) {
                LOG_WARN("LaMa inpainting cancelled by user.");
                return false;
            }

            // tile_roi is in PAGE coordinates, but unit_mask is crop-local:
            // index it with the converted rect or the ROI goes out of bounds.
            const cv::Rect local_roi(tile_roi.x - unit.crop.x, tile_roi.y - unit.crop.y,
                tile_roi.width, tile_roi.height);

            cv::Mat tile = page(tile_roi);
            cv::Mat tile_mask = unit_mask(local_roi);

            // inpaint_patch pads undersized tiles to >= 512px itself; only
            // guard against requests that exceed the buffer bound.
            cv::Mat clean_tile = inpaint_patch(tile, tile_mask);
            ++done;

            if (clean_tile.empty()) {
                ++failed_tiles; // Never paste anything from a failed inference.
            }
            else {
                paste_blended(page, clean_tile, tile_mask, tile_roi);
            }

            if (progress_cb) progress_cb(done, total_tiles);
        }
    }

    if (failed_tiles > 0) {
        LOG_ERROR(QString("LaMa inpainting: %1/%2 tiles failed (GPU error - nothing was pasted for them).")
            .arg(failed_tiles).arg(total_tiles));
        return false;
    }

    full_image_rgb = alpha_from.empty() ? page : restore_alpha(page, alpha_from);

    LOG_INFO("LaMa fast inpainting sequence completed.");
    return true;
}

void lama_engine::pack_fp32_nchw(
    const cv::Mat& rgb_padded,
    const cv::Mat& mask_padded,
    float* dst_img,
    float* dst_mask)
{
    int h = rgb_padded.rows;
    int w = rgb_padded.cols;
    size_t plane_stride = static_cast<size_t>(h) * w;

    float* r_plane = dst_img;
    float* g_plane = dst_img + plane_stride;
    float* b_plane = dst_img + (2 * plane_stride);

    const float inv_255 = 1.0f / 255.0f;

#pragma omp parallel for
    for (int y = 0; y < h; ++y) {
        const cv::Vec3b* row_rgb = rgb_padded.ptr<cv::Vec3b>(y);
        const uchar* row_mask = mask_padded.ptr<uchar>(y);
        size_t offset = static_cast<size_t>(y) * w;

        for (int x = 0; x < w; ++x) {
            const cv::Vec3b& px = row_rgb[x];
            r_plane[offset + x] = px[0] * inv_255;
            g_plane[offset + x] = px[1] * inv_255;
            b_plane[offset + x] = px[2] * inv_255;

            dst_mask[offset + x] = (row_mask[x] > 127) ? 1.0f : 0.0f;
        }
    }
}

void lama_engine::unpack_fp32_nchw(const float* src_output, int h, int w, cv::Mat& dst_rgb) {
    size_t plane_stride = static_cast<size_t>(h) * w;

    const float* r_plane = src_output;
    const float* g_plane = src_output + plane_stride;
    const float* b_plane = src_output + (2 * plane_stride);

#pragma omp parallel for
    for (int y = 0; y < h; ++y) {
        cv::Vec3b* row_ptr = dst_rgb.ptr<cv::Vec3b>(y);
        size_t offset = static_cast<size_t>(y) * w;

        for (int x = 0; x < w; ++x) {
            float r = r_plane[offset + x];
            float g = g_plane[offset + x];
            float b = b_plane[offset + x];

            // Rescale if model outputs [0.0, 1.0]
            if (r <= 1.5f && g <= 1.5f && b <= 1.5f) {
                r *= 255.0f;
                g *= 255.0f;
                b *= 255.0f;
            }

            row_ptr[x][0] = static_cast<uchar>(std::clamp(std::round(r), 0.0f, 255.0f));
            row_ptr[x][1] = static_cast<uchar>(std::clamp(std::round(g), 0.0f, 255.0f));
            row_ptr[x][2] = static_cast<uchar>(std::clamp(std::round(b), 0.0f, 255.0f));
        }
    }
}
