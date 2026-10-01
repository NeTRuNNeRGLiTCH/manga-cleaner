#ifndef CORE_IMAGE_OPS_CV_PAINTER_H
#define CORE_IMAGE_OPS_CV_PAINTER_H

#include <opencv2/opencv.hpp>
#include <QPoint>
#include <QPolygon>
#include <vector>

class cv_painter {
public:
    // === DRAWING TOOLS ===
    // These modify the passed mask reference directly. 
    // is_erase = true writes 0 (Black). is_erase = false writes 255 (White).

    static void draw_brush(cv::Mat& mask, const QPoint& p1, const QPoint& p2, int thickness, bool is_erase);

    static void draw_rect(cv::Mat& mask, const QPoint& top_left, const QPoint& bottom_right, bool is_erase);

    static void draw_lasso(cv::Mat& mask, const QPolygon& q_poly, bool is_erase);

    // Magic wand uses the ORIGINAL image to find similar colors, but writes the result to the MASK
    static void magic_wand(const cv::Mat& original_img, cv::Mat& mask, const QPoint& seed_point, int tolerance, bool is_erase);

private:
    // Helper to convert Qt UI Points to OpenCV math Points
    static std::vector<cv::Point> qpolygon_to_cv(const QPolygon& poly);
};

#endif // CORE_IMAGE_OPS_CV_PAINTER_H