#include "left_toolbar.h"
#include <QSpacerItem>
#include <QSizePolicy>

left_toolbar::left_toolbar(QWidget* parent) : QWidget(parent) {
    this->setAttribute(Qt::WA_StyledBackground, true);
    setup_ui();
}

void left_toolbar::setup_ui() {
    QVBoxLayout* main_layout = new QVBoxLayout(this);
    main_layout->setContentsMargins(8, 12, 8, 12);
    main_layout->setSpacing(8);
    main_layout->setAlignment(Qt::AlignTop | Qt::AlignHCenter);

    // === GROUP 1: MODES ===
    mode_group = new QButtonGroup(this);
    mode_group->setExclusive(true);

    btn_move = create_tool_button(":/axis_cleaner/assets/icons/hand.svg", "Hand (Space)", "#4a9eff");
    btn_paint = create_tool_button(":/axis_cleaner/assets/icons/paint-roller.svg", "Paint (B)", "#9b59ff");
    btn_erase = create_tool_button(":/axis_cleaner/assets/icons/eraser.svg", "Erase (E)", "#ff5959");

    btn_move->setFixedSize(48, 48);
    btn_paint->setFixedSize(48, 48);
    btn_erase->setFixedSize(48, 48);

    mode_group->addButton(btn_move, 0);
    mode_group->addButton(btn_paint, 1);
    mode_group->addButton(btn_erase, 2);

    main_layout->addWidget(btn_move);
    main_layout->addWidget(btn_paint);
    main_layout->addWidget(btn_erase);

    main_layout->addWidget(create_separator(), 0, Qt::AlignHCenter);

    // === GROUP 2: TOOLS ===
    tool_group = new QButtonGroup(this);
    tool_group->setExclusive(true);

    btn_brush = create_tool_button(":/axis_cleaner/assets/icons/brush.svg", "Brush (B)", "#9b59ff");
    btn_rect = create_tool_button(":/axis_cleaner/assets/icons/square.svg", "Rectangular Marquee (M)", "#4a9eff");
    btn_lasso = create_tool_button(":/axis_cleaner/assets/icons/lasso-select.svg", "Lasso (L)", "#4a9eff");
    btn_wand = create_tool_button(":/axis_cleaner/assets/icons/wand-sparkles.svg", "Magic Wand (W)", "#9b59ff");
    btn_color = create_tool_button(":/axis_cleaner/assets/icons/paint-roller.svg", "Color Paint (C) - paints real pixels. Right-click for the color picker.", "#fbbf24");

    tool_group->addButton(btn_brush, 0);
    tool_group->addButton(btn_rect, 1);
    tool_group->addButton(btn_lasso, 2);
    tool_group->addButton(btn_wand, 3);
    tool_group->addButton(btn_color, 4);

    main_layout->addWidget(btn_brush);
    main_layout->addWidget(btn_rect);
    main_layout->addWidget(btn_lasso);
    main_layout->addWidget(btn_wand);
    main_layout->addWidget(btn_color);

    main_layout->addWidget(create_separator(), 0, Qt::AlignHCenter);

    // === GROUP 3: DYNAMIC SLIDERS ===
    QString slider_style = "color: #8f8f8f; font-size: 9px; font-weight: bold;";

    QString fancy_purple_slider =
        "QSlider::groove:vertical { background: #3c3c3c; width: 4px; border-radius: 2px; }"
        "QSlider::handle:vertical { background: #9b59ff; height: 14px; margin: 0 -5px; border-radius: 7px; border: 2px solid #1e1e1e; }"
        "QSlider::handle:vertical:hover { background: #b57cff; }";

    QString fancy_blue_slider =
        "QSlider::groove:vertical { background: #3c3c3c; width: 4px; border-radius: 2px; }"
        "QSlider::handle:vertical { background: #4a9eff; height: 14px; margin: 0 -5px; border-radius: 7px; border: 2px solid #1e1e1e; }"
        "QSlider::handle:vertical:hover { background: #6eb3ff; }";

    brush_slider_container = new QWidget(this);
    brush_slider_container->setSizePolicy(QSizePolicy::Preferred, QSizePolicy::Fixed);

    QVBoxLayout* brush_layout = new QVBoxLayout(brush_slider_container);
    brush_layout->setContentsMargins(0, 0, 0, 0);
    brush_layout->setSpacing(6);
    brush_layout->setAlignment(Qt::AlignTop | Qt::AlignHCenter);

    brush_label = new QLabel("SIZE: 20", this);
    brush_label->setStyleSheet(slider_style);
    brush_label->setAlignment(Qt::AlignCenter);
    brush_label->setFixedWidth(46);

    brush_slider = new QSlider(Qt::Vertical, this);
    brush_slider->setRange(1, 300); // Expanded range to match Canvas logic
    brush_slider->setValue(20);
    brush_slider->setFixedHeight(120);
    brush_slider->setStyleSheet(fancy_purple_slider);
    brush_slider->setCursor(Qt::PointingHandCursor);

    brush_layout->addWidget(brush_label, 0, Qt::AlignHCenter);
    brush_layout->addWidget(brush_slider, 0, Qt::AlignHCenter);

    wand_slider_container = new QWidget(this);
    wand_slider_container->setSizePolicy(QSizePolicy::Preferred, QSizePolicy::Fixed);

    QVBoxLayout* wand_layout = new QVBoxLayout(wand_slider_container);
    wand_layout->setContentsMargins(0, 0, 0, 0);
    wand_layout->setSpacing(6);
    wand_layout->setAlignment(Qt::AlignTop | Qt::AlignHCenter);

    wand_label = new QLabel("TOL: 30", this);
    wand_label->setStyleSheet(slider_style);
    wand_label->setAlignment(Qt::AlignCenter);
    wand_label->setFixedWidth(46);

    wand_slider = new QSlider(Qt::Vertical, this);
    wand_slider->setRange(0, 255);
    wand_slider->setValue(30);
    wand_slider->setFixedHeight(120);
    wand_slider->setStyleSheet(fancy_blue_slider);
    wand_slider->setCursor(Qt::PointingHandCursor);

    wand_layout->addWidget(wand_label, 0, Qt::AlignHCenter);
    wand_layout->addWidget(wand_slider, 0, Qt::AlignHCenter);

    main_layout->addWidget(brush_slider_container);
    main_layout->addWidget(wand_slider_container);

    main_layout->addStretch();

    // === CONNECTIONS & INITIAL STATE ===
    connect(mode_group, &QButtonGroup::idClicked, this, &left_toolbar::on_mode_clicked);
    connect(tool_group, &QButtonGroup::idClicked, this, &left_toolbar::on_tool_clicked);

    connect(brush_slider, &QSlider::valueChanged, this, &left_toolbar::update_brush_label);
    connect(wand_slider, &QSlider::valueChanged, this, &left_toolbar::update_wand_label);

    btn_paint->setChecked(true);
    btn_brush->setChecked(true);
    update_slider_visibility();
}

// === THE INFINITE LOOP FIX ===
void left_toolbar::set_brush_size(int size) {
    // 1. Block the slider from emitting "valueChanged" so it doesn't bounce back to the canvas
    brush_slider->blockSignals(true);

    // 2. Safely update the UI
    brush_slider->setValue(size);
    brush_label->setText(QString("SIZE: %1").arg(size));

    // 3. Unblock it so the user can drag it normally again
    brush_slider->blockSignals(false);
}

void left_toolbar::adjust_brush_size(int delta) {
    if (!brush_slider) return;
    int new_val = qBound(brush_slider->minimum(), brush_slider->value() + delta, brush_slider->maximum());
    brush_slider->setValue(new_val);
}

void left_toolbar::set_mode(const QString& mode) {
    if (mode == "Move") {
        remember_active_tool();
        btn_move->setChecked(true);
        clear_tool_selection();
        emit mode_changed("Move");
    }
    else if (mode == "Paint") {
        btn_paint->setChecked(true);
        if (!tool_group->checkedButton()) restore_last_tool();
        emit mode_changed("Paint");
    }
    else if (mode == "Erase") {
        btn_erase->setChecked(true);
        if (!tool_group->checkedButton()) restore_last_tool();
        emit mode_changed("Erase");
    }
    update_slider_visibility();
}

void left_toolbar::set_tool(const QString& tool) {
    if (tool == "Brush") {
        btn_brush->setChecked(true);
        emit tool_changed("Brush");
    }
    else if (tool == "Rectangle" || tool == "Rect") {
        btn_rect->setChecked(true);
        emit tool_changed("Rectangle");
    }
    else if (tool == "Lasso") {
        btn_lasso->setChecked(true);
        emit tool_changed("Lasso");
    }
    else if (tool == "Wand") {
        btn_wand->setChecked(true);
        emit tool_changed("Wand");
    }
    else if (tool == "Color") {
        btn_color->setChecked(true);
        emit tool_changed("Color");
    }
    update_slider_visibility();
}

// === PHOTOSHOP-STYLE TOOL MEMORY ===
// Hand mode (Space / H) is temporary: remember the active tool so leaving it returns
// the user to what they were doing instead of silently snapping back to the Brush.
void left_toolbar::remember_active_tool() {
    if (btn_brush->isChecked()) m_last_tool = "Brush";
    else if (btn_rect->isChecked()) m_last_tool = "Rectangle";
    else if (btn_lasso->isChecked()) m_last_tool = "Lasso";
    else if (btn_wand->isChecked()) m_last_tool = "Wand";
    else if (btn_color->isChecked()) m_last_tool = "Color";
}

void left_toolbar::clear_tool_selection() {
    tool_group->setExclusive(false);
    foreach(QAbstractButton * btn, tool_group->buttons()) {
        btn->setChecked(false);
    }
    tool_group->setExclusive(true);
}

void left_toolbar::restore_last_tool() {
    set_tool(m_last_tool.isEmpty() ? QString("Brush") : m_last_tool);
}

// === HELPER METHODS ===
QPushButton* left_toolbar::create_tool_button(const QString& icon_path, const QString& tooltip, const QString& active_color) {
    QPushButton* btn = new QPushButton(this);
    btn->setFixedSize(40, 40);
    btn->setCheckable(true);
    btn->setToolTip(tooltip);
    btn->setCursor(Qt::PointingHandCursor);

    btn->setIcon(QIcon(icon_path));
    btn->setIconSize(QSize(24, 24));

    btn->setStyleSheet(QString(
        "QPushButton { background-color: transparent; border-radius: 6px; border: 1px solid transparent; }"
        "QPushButton:hover { background-color: #2b2b2b; }"
        "QPushButton:checked { background-color: #3c3c3c; border: 1px solid %1; }"
    ).arg(active_color));

    return btn;
}

QFrame* left_toolbar::create_separator() {
    QFrame* line = new QFrame(this);
    line->setFrameShape(QFrame::HLine);
    line->setFrameShadow(QFrame::Plain);
    line->setFixedWidth(32);
    line->setStyleSheet("color: #3c3c3c;");
    return line;
}

// === SLOTS & LOGIC ===
void left_toolbar::on_mode_clicked(int id) {
    QString mode_name;
    if (id == 0) mode_name = "Move";
    else if (id == 1) mode_name = "Paint";
    else if (id == 2) mode_name = "Erase";

    if (id == 0) {
        remember_active_tool();
        clear_tool_selection();
    }
    else if (!tool_group->checkedButton()) {
        restore_last_tool();
    }

    update_slider_visibility();
    emit mode_changed(mode_name);
}

void left_toolbar::on_tool_clicked(int id) {
    QString tool_name;
    if (id == 0) tool_name = "Brush";
    else if (id == 1) tool_name = "Rectangle";
    else if (id == 2) tool_name = "Lasso";
    else if (id == 3) tool_name = "Wand";
    else if (id == 4) tool_name = "Color";

    if (btn_move->isChecked()) {
        btn_paint->setChecked(true);
        emit mode_changed("Paint");
    }

    update_slider_visibility();
    emit tool_changed(tool_name);
}

void left_toolbar::update_slider_visibility() {
    bool show_brush = false;
    bool show_wand = false;

    if (!btn_move->isChecked()) {
        if (btn_wand->isChecked()) {
            show_wand = true;
        }
        else if (btn_brush->isChecked()) {
            show_brush = true;
        }
    }

    brush_slider_container->setVisible(show_brush);
    wand_slider_container->setVisible(show_wand);
}

void left_toolbar::update_brush_label(int value) {
    brush_label->setText(QString("SIZE: %1").arg(value));
    emit brush_size_changed(value);
}

void left_toolbar::update_wand_label(int value) {
    wand_label->setText(QString("TOL: %1").arg(value));
    emit wand_tolerance_changed(value);
}