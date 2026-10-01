#ifndef STORAGE_PSD_EXPORTER_H
#define STORAGE_PSD_EXPORTER_H

#include <QString>
#include <opencv2/opencv.hpp>

class psd_exporter {
public:
    // Writes a 2-layer Photoshop Document:
    //   bottom layer = original scan (label = the source file's base name),
    //   top layer    = cleaned scan  (label = "C_" + that base name).
    // RGBA pages keep their alpha channel on every layer; the document is
    // always RGB-mode even for grayscale sources.
    static bool save_layered_psd(
        const QString& save_path,
        const cv::Mat& original_img_rgb,
        const cv::Mat& cleaned_img_rgb
    );
};

#endif // STORAGE_PSD_EXPORTER_H