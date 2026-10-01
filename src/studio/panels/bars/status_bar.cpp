#include "status_bar.h"

status_bar::status_bar(QWidget* parent) : QWidget(parent) {
    this->setAttribute(Qt::WA_StyledBackground, true);

    setup_ui();
}

// === MAIN UI INITIALIZATION ===

void status_bar::setup_ui() {
    QHBoxLayout* main_layout = new QHBoxLayout(this);
    main_layout->setContentsMargins(12, 0, 12, 0);
    main_layout->setSpacing(16);

    QString text_style = "color: #8f8f8f; font-size: 11px;";
    QString separator_style = "color: #3c3c3c; font-size: 11px;";

    status_label = new QLabel("No image loaded", this);
    status_label->setStyleSheet(text_style);

    mode_label = new QLabel("Mode: Paint", this);
    mode_label->setStyleSheet(text_style);

    tool_label = new QLabel("Tool: brush", this);
    tool_label->setStyleSheet(text_style);

    QLabel* sep1 = new QLabel("|", this);
    sep1->setStyleSheet(separator_style);

    QLabel* sep2 = new QLabel("|", this);
    sep2->setStyleSheet(separator_style);

    QLabel* sep5 = new QLabel("|", this);
    sep5->setStyleSheet(separator_style);

    models_label = new QLabel("Models: scanning...", this);
    models_label->setStyleSheet("color: #a78bfa; font-size: 11px; font-weight: 500;");
    models_label->setToolTip("Resident AI models. [VRAM] = loaded on the GPU, [RAM] = present but not resident.");

    main_layout->addWidget(status_label);
    main_layout->addWidget(sep1);
    main_layout->addWidget(mode_label);
    main_layout->addWidget(sep2);
    main_layout->addWidget(tool_label);
    main_layout->addWidget(sep5);
    main_layout->addWidget(models_label);

    main_layout->addStretch();
}

void status_bar::update_loaded_models(const QString& models_info) {
    if (models_label) {
        models_label->setText(models_info);
    }
}

// === PUBLIC UPDATE METHODS ===

void status_bar::update_status(const QString& text) {
    status_label->setText(text);
}

void status_bar::update_mode(const QString& mode) {
    mode_label->setText("Mode: " + mode);
}

void status_bar::update_tool(const QString& tool) {
    tool_label->setText("Tool: " + tool);
}

