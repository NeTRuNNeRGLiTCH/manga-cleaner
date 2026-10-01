#ifndef SETTINGS_CONTROLLERS_MODELS_H
#define SETTINGS_CONTROLLERS_MODELS_H

#include <QWidget>
#include <QVBoxLayout>
#include <QHBoxLayout>
#include <QLabel>
#include <QSlider>
#include <QSpinBox>
#include <QScrollArea>
#include <QPushButton>

class settings_models : public QWidget {
    Q_OBJECT

public:
    explicit settings_models(QWidget* parent = nullptr);
    ~settings_models() = default;

private slots:
    void scan_model_availability();

private:
    void setup_ui();

    // UI Helpers
    QLabel* create_section_header(const QString& title, const QString& hex_color);
    QFrame* create_separator();
    QWidget* create_slider_row(const QString& label_text, const QString& desc_text, int min, int max, int default_val, const QString& suffix, QLabel*& val_label_ptr, QSlider*& slider_ptr);
    QWidget* create_spinbox_row(const QString& label_text, const QString& desc_text, int min, int max, int default_val, const QString& suffix, QSpinBox*& spin_ptr);
    QWidget* create_model_card(const QString& title, const QString& desc, QLabel*& status_label);

    // WIDGET POINTERS: Model Availability
    QLabel* lbl_availability_arch;
    QLabel* lbl_availability_summary;
    QLabel* lbl_segmentation_status;
    QLabel* lbl_moebius_status;
    QLabel* lbl_lama_status;
    QPushButton* btn_scan_models;

    // WIDGET POINTERS: TextBPN++
    QSlider* sldr_bpn_prob;        QLabel* lbl_bpn_prob;
    QSlider* sldr_bpn_core;        QLabel* lbl_bpn_core;
    QSpinBox* spin_bpn_expand;

    // WIDGET POINTERS: Moebius Latent Suite
    QSpinBox* spin_moebius_steps;
};

#endif // SETTINGS_CONTROLLERS_MODELS_H