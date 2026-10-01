#ifndef SETTINGS_CONTROLLERS_IMAGE_H
#define SETTINGS_CONTROLLERS_IMAGE_H

#include <QWidget>
#include <QVBoxLayout>
#include <QHBoxLayout>
#include <QLabel>
#include <QSlider>
#include <QComboBox>
#include <QLineEdit>
#include <QPushButton>
#include <QScrollArea>
#include <QPainter>
#include <QMouseEvent>

// ==========================================================
// Isolated Switch for the Image Tab
// ==========================================================
class ImageToggle : public QWidget {
    Q_OBJECT
public:
    explicit ImageToggle(bool default_state = false, QWidget* parent = nullptr);
    bool isChecked() const;

signals:
    void toggled(bool checked);

protected:
    void mouseReleaseEvent(QMouseEvent* event) override;
    void paintEvent(QPaintEvent* event) override;

private:
    bool m_checked;
};

// ==========================================================
// Image Settings Controller
// ==========================================================
class settings_image : public QWidget {
    Q_OBJECT

public:
    explicit settings_image(QWidget* parent = nullptr);
    ~settings_image() = default;

private:
    void setup_ui();

    // UI Helpers
    QLabel* create_section_header(const QString& title, const QString& hex_color);
    QFrame* create_separator();
    QWidget* create_toggle_row(const QString& label_text, const QString& desc_text, bool is_checked, ImageToggle*& toggle_ptr);
    QWidget* create_combo_row(const QString& label_text, const QString& desc_text, const QStringList& options, int default_index, QComboBox*& combo_ptr);
    QWidget* create_slider_row(const QString& label_text, const QString& desc_text, int min, int max, int default_val, const QString& suffix, QLabel*& val_label_ptr, QSlider*& slider_ptr);
    QWidget* create_path_row(const QString& label_text, const QString& desc_text, const QString& default_path, QLineEdit*& line_ptr, QPushButton*& btn_ptr);

    // WIDGET POINTERS
    QComboBox* combo_export_format;
    QSlider* sldr_jpg_quality;   QLabel* lbl_jpg_quality;
    QLineEdit* line_import_path;   QPushButton* btn_import_browse;
    QLineEdit* line_export_path;   QPushButton* btn_export_browse;
    ImageToggle* toggle_save_in_src;
};

#endif // SETTINGS_CONTROLLERS_IMAGE_H