#include "cv_painter.h"
#include "src/diagnostics/logger.h"
#include <algorithm>

inline uchar get_color(bool is_erase) {
    return is_erase ? 0 : 255;
}

void cv_painter::draw_brush(cv::Mat& mask, const QPoint& p1, const QPoint& p2, int thickness, bool is_erase) {
    if (mask.empty()) return;
    try {
        cv::Scalar color(get_color(is_erase));
        cv::line(mask, cv::Point(p1.x(), p1.y()), cv::Point(p2.x(), p2.y()), color, thickness, cv::LINE_AA);
        cv::circle(mask, cv::Point(p2.x(), p2.y()), thickness / 2, color, cv::FILLED, cv::LINE_AA);
    }
    catch (const cv::Exception& e) { LOG_ERROR(QString("OpenCV Exception draw_brush: ") + e.what()); }
}

void cv_painter::draw_rect(cv::Mat& mask, const QPoint& top_left, const QPoint& bottom_right, bool is_erase) {
    if (mask.empty()) return;
    try {
        cv::Scalar color(get_color(is_erase));

        // Normalize the drag so dragging right-to-left / bottom-to-top still fills.
        const int x0 = std::min(top_left.x(), bottom_right.x());
        const int y0 = std::min(top_left.y(), bottom_right.y());
        const int x1 = std::max(top_left.x(), bottom_right.x());
        const int y1 = std::max(top_left.y(), bottom_right.y());

        cv::Rect rect(x0, y0, x1 - x0, y1 - y0);
        cv::rectangle(mask, rect, color, cv::FILLED);
    }
    catch (const cv::Exception& e) { LOG_ERROR(QString("OpenCV Exception draw_rect: ") + e.what()); }
}

void cv_painter::draw_lasso(cv::Mat& mask, const QPolygon& q_poly, bool is_erase) {
    if (mask.empty() || q_poly.isEmpty()) return;
    try {
        cv::Scalar color(get_color(is_erase));
        std::vector<cv::Point> cv_pts = qpolygon_to_cv(q_poly);
        std::vector<std::vector<cv::Point>> contours = { cv_pts };
        cv::fillPoly(mask, contours, color, cv::LINE_AA);
    }
    catch (const cv::Exception& e) { LOG_ERROR(QString("OpenCV Exception draw_lasso: ") + e.what()); }
}

void cv_painter::magic_wand(const cv::Mat& original_img, cv::Mat& mask, const QPoint& seed_point, int tolerance, bool is_erase) {
    if (original_img.empty() || mask.empty()) return;

    try {
        cv::Point seed(seed_point.x(), seed_point.y());
        if (seed.x < 0 || seed.x >= original_img.cols || seed.y < 0 || seed.y >= original_img.rows) return;

        // cv::floodFill only accepts 1- or 3-channel images. The session may
        // hold RGBA (CV_8UC4) for pages that keep their transparency, where the
        // fill used to throw an assertion and the wand silently did nothing:
        // strip the alpha channel first (region growing is channel-symmetric,
        // so the RGB result is identical in meaning).
        cv::Mat fill_img;
        if (original_img.channels() == 4) cv::cvtColor(original_img, fill_img, cv::COLOR_RGBA2RGB);
        else fill_img = original_img;

        cv::Mat flood_mask = cv::Mat::zeros(fill_img.rows + 2, fill_img.cols + 2, CV_8UC1);
        cv::Scalar diff(tolerance, tolerance, tolerance);

        // === THE FIX ===
        // cv::FLOODFILL_FIXED_RANGE stops the wand from continuously "creeping" across gradients.
        // It now compares all pixels strictly to the exact pixel you clicked on.
        cv::floodFill(fill_img, flood_mask, seed, cv::Scalar(255, 255, 255), nullptr, diff, diff,
            4 | (255 << 8) | cv::FLOODFILL_FIXED_RANGE | cv::FLOODFILL_MASK_ONLY);

        cv::Mat exact_flood_mask = flood_mask(cv::Rect(1, 1, fill_img.cols, fill_img.rows));

        if (is_erase) {
            cv::bitwise_and(mask, ~exact_flood_mask, mask);
        }
        else {
            cv::bitwise_or(mask, exact_flood_mask, mask);
        }
    }
    catch (const cv::Exception& e) { LOG_ERROR(QString("OpenCV Exception magic_wand: ") + e.what()); }
}

std::vector<cv::Point> cv_painter::qpolygon_to_cv(const QPolygon& poly) {
    std::vector<cv::Point> cv_pts;
    cv_pts.reserve(poly.size());
    for (int i = 0; i < poly.size(); ++i) {
        cv_pts.emplace_back(poly.at(i).x(), poly.at(i).y());
    }
    return cv_pts;
}