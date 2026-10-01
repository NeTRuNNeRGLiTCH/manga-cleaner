#include "textbpn_engine.h"
#include "src/engine/trt_arch_detector.h"
#include "src/core/pipeline/task_queue.h"
#include "src/diagnostics/logger.h"
#include <opencv2/imgproc.hpp>
#include <vector>
#include <algorithm>

textbpn_engine::textbpn_engine() {}

textbpn_engine::~textbpn_engine() {
    unload();
}

bool textbpn_engine::init() {
    if (is_loaded()) return true;

    QString resolved_path = trt_arch_detector::instance().get_engine_path("segmentation");

    LOG_INFO("Initializing TextBPN++ TensorRT Engine: " + resolved_path);

    if (!trt_runtime::instance().init()) {
        LOG_FATAL("Failed to initialize TensorRT Runtime for TextBPN++.");
        return false;
    }

    if (!m_model.load_from_file(resolved_path, trt_runtime::instance().get_runtime())) {
        LOG_FATAL("Failed to load TextBPN++ engine file from: " + resolved_path);
        return false;
    }

    // Buffers are sized for the largest tile the detect() grid can produce
    // (2560x1024); shapes are always clamped down to the engine profile, so this
    // is guaranteed to fit. (Sizing from the profile max instead would page-lock
    // ~235 MB of pinned RAM for nothing.)
    const int max_h = 2560;
    const int max_w = 1024;

    // The shipped Lovelace pack's output has FOUR channels [-1,4,H,W]
    // (cls, dis + 2 aux) - assuming 2 made every enqueueV3 die in the reformatter
    // with cudaError invalid argument. Read the real channel count from the engine.
    int out_channels = 4;
    {
        const nvinfer1::Dims out_shape = m_model.get_tensor_shape("output");
        if (out_shape.nbDims == 4 && out_shape.d[1] > 0) out_channels = static_cast<int>(out_shape.d[1]);
    }
    m_out_channels = out_channels;

    nvinfer1::Dims prof_min{ 0 }, prof_max{ 0 };
    if (m_model.get_profile_bounds("input", prof_min, prof_max) && prof_max.nbDims == 4) {
        LOG_INFO(QString("TextBPN profile: max [%1x%2], output channels: %3")
            .arg(prof_max.d[2]).arg(prof_max.d[3]).arg(out_channels));
    }

    size_t max_input_bytes = 1 * 3 * max_h * max_w * sizeof(float);
    size_t max_output_bytes = 1 * out_channels * max_h * max_w * sizeof(float); // [1, C, H, W]

    // Checked allocations: a silent cudaMalloc failure would send the first
    // inference into a null device pointer.
    if (!m_gpu_input.allocate(max_input_bytes) ||
        !m_gpu_output.allocate(max_output_bytes) ||
        !m_pinned_input.allocate(max_input_bytes) ||
        !m_pinned_output.allocate(max_output_bytes)) {
        LOG_FATAL("TextBPN++: failed to allocate GPU/pinned buffers.");
        unload();
        return false;
    }

    LOG_INFO("TextBPN++ TensorRT Engine loaded and ready.");
    return true;
}

void textbpn_engine::unload() {
    m_model.unload();
    m_gpu_input.release();
    m_gpu_output.release();
    m_pinned_input.release();
    m_pinned_output.release();
    LOG_INFO("TextBPN++ Engine unloaded from VRAM.");
}

bool textbpn_engine::is_loaded() const {
    return m_model.is_loaded();
}

// ==========================================================
// Magic-wand-style text completion (see header for rationale).
// ==========================================================
cv::Mat textbpn_engine::complete_text_mask(
    const cv::Mat& dis_map,
    const cv::Mat& cls_map,
    const cv::Mat& seeds_binary,
    float dis_floor,
    float cls_floor,
    int reach_px,
    int dilate_px) const
{
    CV_Assert(dis_map.type() == CV_32FC1 && cls_map.type() == CV_32FC1 && seeds_binary.type() == CV_8UC1);
    CV_Assert(dis_map.size() == cls_map.size() && dis_map.size() == seeds_binary.size());

    const int rows = dis_map.rows;
    const int cols = dis_map.cols;

    // 1. Candidate pixels: the network still rates them as text, just below
    // the core threshold - glyph edges, antialiasing, faint strokes. Requiring
    // BOTH a weak dis response and a modest cls confidence keeps background
    // and screentone speckles out of the sweep.
    cv::Mat weak_f, cls_f;
    cv::threshold(dis_map, weak_f, dis_floor, 255.0, cv::THRESH_BINARY);
    cv::threshold(cls_map, cls_f, cls_floor, 255.0, cv::THRESH_BINARY);
    cv::Mat weak_mask, cls_mask;
    weak_f.convertTo(weak_mask, CV_8UC1);
    cls_f.convertTo(cls_mask, CV_8UC1);
    cv::Mat candidates;
    cv::bitwise_and(weak_mask, cls_mask, candidates);

    cv::Mat accepted = seeds_binary.clone();

    // 2. Magic-wand growth. Each round sweeps the frontier up to reach_px in
    // EVERY direction (a box-dilation - the same shape as a per-pixel ±reach
    // scan); any candidate pixel inside the swept range is claimed and becomes
    // the next frontier, so the walk chains across inter-letter gaps a few
    // pixels at a time until nothing new is reachable. The walk follows the
    // network's own text probabilities - not any pixel color - so it works
    // for any text color and stops where text ends (it never floods the
    // bubble interior).
    cv::Mat frontier = accepted.clone();

    for (int round = 0; round < reach_px && cv::countNonZero(frontier) > 0; ++round) {
        const int k = reach_px * 2 + 1;
        cv::Mat box_kernel = cv::getStructuringElement(cv::MORPH_RECT, cv::Size(k, k));
        cv::Mat swept;
        cv::dilate(frontier, swept, box_kernel);

        cv::Mat newly;
        cv::bitwise_and(swept, candidates, newly);
        cv::Mat not_accepted;
        cv::bitwise_not(accepted, not_accepted);
        cv::bitwise_and(newly, not_accepted, newly);

        cv::bitwise_or(accepted, newly, accepted);        frontier = newly;
    }


    // 3. Post-processing.
    // a) Close: seals sub-pixel cracks along the stroke boundary.
    cv::Mat close_kernel = cv::getStructuringElement(cv::MORPH_ELLIPSE, cv::Size(3, 3));
    cv::morphologyEx(accepted, accepted, cv::MORPH_CLOSE, close_kernel);

    // b) Dilate: the guaranteed text padding around every glyph.
    if (dilate_px > 0) {
        const int k = dilate_px * 2 + 1;
        cv::Mat dil_kernel = cv::getStructuringElement(cv::MORPH_ELLIPSE, cv::Size(k, k));
        cv::dilate(accepted, accepted, dil_kernel);
    }

    // c) Hole fill: enclosed glyph counters (the inside of O, A, D, !) are text
    // surroundings and must be masked too. Flood the inverted mask from a
    // synthetic 1px border; whatever the flood cannot reach is a hole.
    cv::Mat inv;
    cv::bitwise_not(accepted, inv);
    cv::Mat outside;
    cv::copyMakeBorder(inv, outside, 1, 1, 1, 1, cv::BORDER_CONSTANT, cv::Scalar(255));
    cv::floodFill(outside, cv::Point(0, 0), cv::Scalar(0)); // border-connected background -> 0

    cv::Mat holes;
    cv::threshold(outside(cv::Rect(1, 1, cols, rows)), holes, 127, 255, cv::THRESH_BINARY);
    cv::bitwise_or(accepted, holes, accepted);

    return accepted;
}

TextBpnResult textbpn_engine::detect(
    const cv::Mat& src_rgb,
    float cls_threshold,
    float dis_threshold,
    int min_bubble_area,
    int dilation_radius)
{
    TextBpnResult result;
    if (src_rgb.empty()) {
        LOG_ERROR("TextBPN received empty image.");
        return result;
    }

    if (!is_loaded() && !init()) {
        LOG_ERROR("TextBPN Engine is not initialized.");
        return result;
    }

    int full_w = src_rgb.cols;
    int full_h = src_rgb.rows;

    LOG_INFO(QString("TextBPN++ scanning image [%1x%2] (cls_th: %3, dis_th: %4)...")
        .arg(full_w).arg(full_h).arg(cls_threshold).arg(dis_threshold));

    // Master stitch canvas (FLOAT32)
    cv::Mat global_cls = cv::Mat::zeros(full_h, full_w, CV_32FC1);
    cv::Mat global_dis = cv::Mat::zeros(full_h, full_w, CV_32FC1);

    // Cheatsheet: Strip slicing parameters. Always step by (tile - overlap) so
    // the whole page is covered; the engine clamps/pads each tile to its own
    // profile bounds inside run_single_tile().
    const int tile_h_max = 2560;
    const int overlap_y = 256;
    const int step_y = tile_h_max - overlap_y; // 2304

    const int tile_w_max = 1024;
    const int overlap_x = 128;
    const int step_x = tile_w_max - overlap_x; // 896

    int tile_count = 0;
    int failed_tiles = 0;

    // 1. GRID & STRIP SLICING LOOP
    for (int y = 0; y < full_h; y += step_y) {
        if (task_cancel_requested()) {
            LOG_WARN("TextBPN++ detection cancelled by user.");
            return result;
        }
        const int cur_h = std::min(tile_h_max, full_h - y);

        for (int x = 0; x < full_w; x += step_x) {
            if (task_cancel_requested()) {
                LOG_WARN("TextBPN++ detection cancelled by user.");
                return result;
            }
            const int cur_w = std::min(tile_w_max, full_w - x);

            ++tile_count;
            cv::Rect tile_roi(x, y, cur_w, cur_h);
            cv::Mat tile_rgb = src_rgb(tile_roi);

            cv::Mat out_dis_tile;
            cv::Mat out_cls_tile = run_single_tile(tile_rgb, out_dis_tile);

            if (out_cls_tile.empty() || out_dis_tile.empty()) {
                ++failed_tiles;
                LOG_ERROR(QString("TextBPN tile [%1,%2] (%3x%4) failed; region skipped.")
                    .arg(x).arg(y).arg(cur_w).arg(cur_h));
                continue;
            }

            // The tile may be clamped smaller than tile_roi (engine profile
            // bounds); intersect so the stitch never reads out of range.
            const cv::Rect valid_roi = tile_roi & cv::Rect(x, y, out_cls_tile.cols, out_cls_tile.rows);
            if (valid_roi.width > 0 && valid_roi.height > 0) {
                const cv::Rect src_roi(0, 0, valid_roi.width, valid_roi.height);

                // Cheatsheet: Stitch tiles onto full canvas using cv::max
                cv::Mat roi_cls = global_cls(valid_roi);
                cv::Mat roi_dis = global_dis(valid_roi);

                cv::max(roi_cls, out_cls_tile(src_roi), roi_cls);
                cv::max(roi_dis, out_dis_tile(src_roi), roi_dis);
            }
        }
    }

    if (failed_tiles > 0) {
        LOG_ERROR(QString("TextBPN++ finished with %1/%2 failed tiles; affected page regions were NOT scanned.")
            .arg(failed_tiles).arg(tile_count));
    }

    // 2. CONNECTED COMPONENTS ON THE TEXT-CORE MASK
    // Reference pipeline (TextBPN++ get_boundary_proposal_eval): candidates are
    // grown from the dis (text core / kernel) mask; each component is scored by
    // the MEAN cls probability over its pixels and rejected below cls_threshold,
    // plus a minimum-area guard.
    cv::Mat core_candidates = (global_dis >= dis_threshold); // CV_8UC1 {0,255}

    cv::Mat labels, stats, centroids;
    int num_labels = cv::connectedComponentsWithStats(core_candidates, labels, stats, centroids, 8, CV_32S);

    // 3. FILTERING + MASK ASSEMBLY
    // The detection seed IS the text-core component (reference:
    // get_sample_point over the dis component); cls only gates its confidence.
    // The seeds are grown into complete text masks by the magic-wand completion
    // in step 4.
    cv::Mat clean_mask = cv::Mat::zeros(full_h, full_w, CV_8UC1);

    for (int i = 1; i < num_labels; ++i) {
        const int area = stats.at<int>(i, cv::CC_STAT_AREA);

        // Post-filter: discard masks below the minimum area (default 100 px).
        if (area < min_bubble_area) continue;

        const cv::Rect box(stats.at<int>(i, cv::CC_STAT_LEFT), stats.at<int>(i, cv::CC_STAT_TOP),
            stats.at<int>(i, cv::CC_STAT_WIDTH), stats.at<int>(i, cv::CC_STAT_HEIGHT));

        // Confidence = mean cls probability over the component (reference semantics).
        cv::Mat comp_roi = (labels(box) == i);
        const double confidence = cv::mean(global_cls(box), comp_roi)[0];
        if (confidence < cls_threshold) continue;

        clean_mask(box).setTo(255, comp_roi);

        result.bubble_centers.push_back(cv::Point(
            static_cast<int>(centroids.at<double>(i, 0)),
            static_cast<int>(centroids.at<double>(i, 1))));
    }

    // Nothing survived the filters: return an EMPTY mask so callers take the
    // "nothing detected" path instead of committing a blank mask as success.
    if (result.bubble_centers.empty()) {
        LOG_WARN("TextBPN++ found no text regions passing the confidence/area filters.");
        return result;
    }

    // 4. TEXT MASK COMPLETION (magic-wand style)
    // The dis core marks the most confident stroke pixels only, so glyph
    // edges, antialiased pixels and letter gaps can end up unmasked (visible
    // as clipped glyphs - an "I" or the tail of "ELDEST" left unmasked).
    // Grow the mask from the accepted seeds: scan up to 8px in each direction,
    // claim any pixel the network still rates as text (color-agnostic - the
    // text color is irrelevant), then solidify: a close pass, hard 8px
    // dilation and enclosed-hole filling. The bubble interior is never touched:
    // growth follows text probability and stops where text ends.
    if (cv::countNonZero(clean_mask) > 0) {
        // The acceptance floor must sit well BELOW the core threshold: the
        // pixels that get clipped (glyph edges, antialiasing) are exactly the
        // sub-core responses. A floor at dis_threshold itself would make the
        // completion pass a no-op. The cls floor mirrors the detection gate
        // (bpn_prob): a pixel with no confidence is background, not faint text.
        constexpr float kDisFloor = 0.05f;
        clean_mask = complete_text_mask(
            global_dis, global_cls, clean_mask,
            kDisFloor, cls_threshold, 8, 8);
    }

    // 5. USER PADDING (bpn_expand): extra elliptical dilation on top of the
    // guaranteed 8px text coverage, for inpainters that need a wider brush.
    if (dilation_radius > 0) {
        int ksize = (dilation_radius * 2) + 1;
        cv::Mat kernel = cv::getStructuringElement(cv::MORPH_ELLIPSE, cv::Size(ksize, ksize));
        cv::dilate(clean_mask, clean_mask, kernel);
    }

    result.full_mask = clean_mask;
    result.num_bubbles = static_cast<int>(result.bubble_centers.size());

    LOG_INFO(QString("TextBPN++ detected %1 text/SFX bubble regions.").arg(result.num_bubbles));
    return result;
}

cv::Mat textbpn_engine::run_single_tile(const cv::Mat& tile_rgb, cv::Mat& out_dis_tile) {
    int cur_w = tile_rgb.cols;
    int cur_h = tile_rgb.rows;

    // Cheatsheet: Dimensions MUST be multiples of 32
    int aligned_w = ((cur_w + 31) / 32) * 32;
    int aligned_h = ((cur_h + 31) / 32) * 32;

    // The engine was built with a fixed [H, W] optimization profile (e.g. max
    // 2560x1024). Shapes outside it make enqueueV3 fail with "invalid argument"
    // in the reformatter, so clamp BEFORE padding. The tile is then padded to
    // the clamped size and simply covers a smaller page region when stitched.
    nvinfer1::Dims4 input_dims{ 1, 3, aligned_h, aligned_w };
    if (!m_model.clamp_to_profile("input", input_dims)) {
        LOG_ERROR("TextBPN input rank does not match the engine profile.");
        return cv::Mat();
    }
    aligned_h = static_cast<int>(input_dims.d[2]);
    aligned_w = static_cast<int>(input_dims.d[3]);

    cv::Mat padded_rgb;

    if (aligned_w == cur_w && aligned_h == cur_h) {
        padded_rgb = tile_rgb;
    }
    else {
        cv::copyMakeBorder(tile_rgb, padded_rgb, 0, aligned_h - cur_h, 0, aligned_w - cur_w, cv::BORDER_CONSTANT, cv::Scalar(0, 0, 0));
    }

    // The session stores RGB (session_data converts BGR->RGB on load and the
    // batch worker mirrors that), so NO extra conversion here: applying one
    // swapped the network's channels and silently degraded detection accuracy.
    // Pack into Pinned Host Memory with ImageNet Normalization
    float* input_host = static_cast<float*>(m_pinned_input.data());
    pack_imagenet_nchw(padded_rgb, input_host);

    cudaStream_t stream = trt_runtime::instance().get_worker_stream();

    // 1. Asynchronous Copy H2D
    size_t input_bytes = 1 * 3 * aligned_h * aligned_w * sizeof(float);
    cudaMemcpyAsync(m_gpu_input.data(), input_host, input_bytes, cudaMemcpyHostToDevice, stream);

    // 2. Set TensorRT Dynamic Input Dimensions
    if (!m_model.set_input_shape("input", input_dims)) {
        return cv::Mat();
    }

    // 3. Bind Pointers
    m_model.set_tensor_address("input", m_gpu_input.data());
    m_model.set_tensor_address("output", m_gpu_output.data());

    // 4. Execute Asynchronously
    if (!m_model.forward(stream)) {
        LOG_ERROR("TextBPN forward pass failed.");
        return cv::Mat();
    }

    // 5. Asynchronous Copy D2H
    size_t output_bytes = 1 * m_out_channels * aligned_h * aligned_w * sizeof(float);
    float* output_host = static_cast<float*>(m_pinned_output.data());
    cudaMemcpyAsync(output_host, m_gpu_output.data(), output_bytes, cudaMemcpyDeviceToHost, stream);

    // 6. Synchronize Worker Stream
    cudaStreamSynchronize(stream);

    // Extract cls and dis planes. Layout [1, C, H, W]: channel 0 = cls,
    // channel 1 = dis. The model itself applies sigmoid to channels 0/1
    // (textnet.py: fy_preds = cat([sigmoid(preds[:, 0:2]), preds[:, 2:4]])),
    // so these are ALREADY probabilities in [0,1] - applying sigmoid again
    // compressed every value into ~[0.5, 0.7] and made low thresholds mark
    // the whole image while high thresholds marked nothing.
    size_t plane_elements = static_cast<size_t>(aligned_h) * aligned_w;
    float* cls_raw = output_host;
    float* dis_raw = output_host + plane_elements;

    cv::Mat tile_cls(aligned_h, aligned_w, CV_32FC1);
    cv::Mat tile_dis(aligned_h, aligned_w, CV_32FC1);

#pragma omp parallel for
    for (int i = 0; i < aligned_h * aligned_w; ++i) {
        tile_cls.ptr<float>()[i] = cls_raw[i];
        tile_dis.ptr<float>()[i] = dis_raw[i];
    }

    // Crop away padding. The tile may have been clamped to the engine's profile,
    // so the output can be smaller than the requested tile: crop to whatever
    // actually fits and let the stitcher intersect.
    const int out_w = std::min(cur_w, tile_cls.cols);
    const int out_h = std::min(cur_h, tile_cls.rows);
    if (out_w <= 0 || out_h <= 0) {
        out_dis_tile.release();
        return cv::Mat();
    }

    cv::Rect original_rect(0, 0, out_w, out_h);
    out_dis_tile = tile_dis(original_rect).clone();
    return tile_cls(original_rect).clone();
}

void textbpn_engine::pack_imagenet_nchw(const cv::Mat& rgb_padded, float* dst_ptr) {
    int h = rgb_padded.rows;
    int w = rgb_padded.cols;
    size_t plane_stride = static_cast<size_t>(h) * w;

    float* r_plane = dst_ptr;
    float* g_plane = dst_ptr + plane_stride;
    float* b_plane = dst_ptr + (2 * plane_stride);

    // Cheatsheet: ImageNet normalization
    // Mean = [0.485, 0.456, 0.406], Std = [0.229, 0.224, 0.225]
    const float inv_255 = 1.0f / 255.0f;
    const float mean_r = 0.485f, mean_g = 0.456f, mean_b = 0.406f;
    const float std_r = 0.229f, std_g = 0.224f, std_b = 0.225f;

#pragma omp parallel for
    for (int y = 0; y < h; ++y) {
        const cv::Vec3b* row_ptr = rgb_padded.ptr<cv::Vec3b>(y);
        size_t row_offset = static_cast<size_t>(y) * w;

        for (int x = 0; x < w; ++x) {
            const cv::Vec3b& pixel = row_ptr[x]; // RGB

            r_plane[row_offset + x] = ((pixel[0] * inv_255) - mean_r) / std_r;
            g_plane[row_offset + x] = ((pixel[1] * inv_255) - mean_g) / std_g;
            b_plane[row_offset + x] = ((pixel[2] * inv_255) - mean_b) / std_b;
        }
    }
}