#include "psd_exporter.h"
#include "src/diagnostics/logger.h"
#include <QFileInfo>
#include <vector>

// ImageMagick C++ API
#include <Magick++.h>

namespace {

// Wraps a contiguous CV_8UC4 image into a labelled Magick++ image.
// The channel map is forced to RGBA for EVERY image in the stack: ImageMagick's
// PSD writer takes the document mode from the FIRST image (a grayscale one
// would collapse the whole document to grayscale mode) and refuses mixed
// channel counts between the composite and the layers.
Magick::Image to_magick(const cv::Mat& rgba, const QString& label) {
    Magick::Image out(
        rgba.cols,
        rgba.rows,
        "RGBA",
        Magick::CharPixel,
        rgba.data
    );

    out.label(label.toStdString());

    // The shipped Q16-HDRI build defaults newly-constituted images to 16-bit
    // depth; layers must stay 8-bit, Run-Length-Encoded PSD for the smallest
    // and most widely compatible Photoshop files.
    out.depth(8);
    out.compressType(Magick::RLECompression);
    out.magick("PSD");
    return out;
}

} // namespace

bool psd_exporter::save_layered_psd(
    const QString& save_path,
    const cv::Mat& original_img_rgb,
    const cv::Mat& cleaned_img_rgb)
{
    if (original_img_rgb.empty() || cleaned_img_rgb.empty()) {
        LOG_ERROR("Cannot export PSD: One or both input images are empty.");
        return false;
    }

    if (original_img_rgb.size() != cleaned_img_rgb.size()) {
        LOG_ERROR("Cannot export PSD: Original and Cleaned images have different dimensions!");
        return false;
    }

    try {
        // One-time thread-safe ImageMagick initialization
        static bool magick_initialized = false;
        if (!magick_initialized) {
            Magick::InitializeMagick(nullptr);
            magick_initialized = true;
        }

        LOG_INFO("Exporting layered PSD via ImageMagick: " + QFileInfo(save_path).fileName());

        // 1. Contiguous, alpha-uniform buffers: any 3-channel input is lifted to
        //    4 channels (opaque alpha) so the whole stack shares one channel map.
        //    RGBA pages keep their original alpha channel untouched.
        cv::Mat orig_rgba, clean_rgba;
        if (original_img_rgb.channels() == 4) {
            orig_rgba = original_img_rgb.isContinuous() ? original_img_rgb : original_img_rgb.clone();
        }
        else {
            cv::cvtColor(original_img_rgb, orig_rgba, cv::COLOR_RGB2RGBA);
        }
        if (cleaned_img_rgb.channels() == 4) {
            clean_rgba = cleaned_img_rgb.isContinuous() ? cleaned_img_rgb : cleaned_img_rgb.clone();
        }
        else {
            cv::cvtColor(cleaned_img_rgb, clean_rgba, cv::COLOR_RGB2RGBA);
        }

        // 2. Layer name = the original file's base name, minus a "_cleaned"
        //    suffix (the exporter may be re-run over its own output).
        QString base_name = QFileInfo(save_path).baseName();
        if (base_name.endsWith("_cleaned", Qt::CaseInsensitive)) {
            base_name.chop(8);
        }
        const std::string name = base_name.toStdString();

        // 3. Layer stack. ImageMagick's PSD writer treats the FIRST image as the
        //    flattened composite preview and writes the REMAINING images as
        //    layers, so the original is passed twice: once as the composite
        //    donor (with a 1-LSB tint so a grayscale page can never collapse
        //    the document into grayscale mode) and once as the bottom layer.
        //    The cleaned scan becomes the TOP layer.
        cv::Mat donor_rgba = orig_rgba.clone();
        donor_rgba.forEach<cv::Vec4b>([](cv::Vec4b& px, const int*) { px[2] ^= 0x01; });

        std::vector<Magick::Image> layer_stack;
        layer_stack.push_back(to_magick(donor_rgba, QString()));
        layer_stack.push_back(to_magick(orig_rgba, QString::fromStdString(name)));
        layer_stack.push_back(to_magick(clean_rgba, QString::fromStdString("C_" + name)));

        // 4. Unicode-safe path write
        std::string utf8_path = save_path.toUtf8().toStdString();
        Magick::writeImages(layer_stack.begin(), layer_stack.end(), utf8_path);

        LOG_INFO(QString("Successfully wrote 2-layer PSD (\"%1\" below, \"C_%1\" above) to disk: %2")
            .arg(QString::fromStdString(name)).arg(save_path));
        return true;

    }
    catch (Magick::Exception& error) {
        LOG_ERROR(QString("ImageMagick Exception during PSD export: ") + error.what());
        return false;
    }
    catch (const std::exception& e) {
        LOG_ERROR(QString("Standard Exception during PSD export: ") + e.what());
        return false;
    }
}