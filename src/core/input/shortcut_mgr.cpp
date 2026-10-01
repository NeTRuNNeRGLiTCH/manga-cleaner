#include "shortcut_mgr.h"
#include "src/diagnostics/logger.h"
#include <QKeySequence>
#include <QApplication>
#include <QKeyEvent>

shortcut_mgr::shortcut_mgr(QWidget* main_window) : QObject(main_window), m_main_window(main_window) {
    LOG_TRACE("Initializing Global Shortcut Manager...");
    if (m_main_window) {
        m_main_window->installEventFilter(this);
    }
    register_shortcuts(main_window);
    LOG_INFO("Global keyboard shortcuts registered successfully.");
}

shortcut_mgr::~shortcut_mgr() {
    end_space_pan();
}

bool shortcut_mgr::is_editable_control(QWidget* widget) const {
    if (!widget) return false;
    return widget->inherits("QLineEdit") || 
           widget->inherits("QTextEdit") || 
           widget->inherits("QPlainTextEdit") || 
           widget->inherits("QSpinBox") || 
           widget->inherits("QDoubleSpinBox");
}

bool shortcut_mgr::is_in_main_window(QWidget* widget) const {
    if (!widget || !m_main_window) return false;
    return widget == m_main_window || m_main_window->isAncestorOf(widget);
}

void shortcut_mgr::end_space_pan() {
    if (m_space_pressed) {
        m_space_pressed = false;
        emit sig_pan_ended();
    }
}

bool shortcut_mgr::eventFilter(QObject* watched, QEvent* event) {
    if (event->type() == QEvent::KeyPress) {
        QKeyEvent* keyEvent = static_cast<QKeyEvent*>(event);
        if (keyEvent->key() == Qt::Key_Space && !keyEvent->isAutoRepeat()) {
            QWidget* focused = QApplication::focusWidget();
            if (!is_editable_control(focused)) {
                m_space_pressed = true;
                emit sig_pan_started();
            }
        }
    }
    else if (event->type() == QEvent::KeyRelease) {
        QKeyEvent* keyEvent = static_cast<QKeyEvent*>(event);
        if (keyEvent->key() == Qt::Key_Space && !keyEvent->isAutoRepeat()) {
            end_space_pan();
        }
    }
    return QObject::eventFilter(watched, event);
}

void shortcut_mgr::register_shortcuts(QWidget* parent) {
    // === HISTORY ===
    // Photoshop & Axis: Selection Undo/Redo is Ctrl+Z / Ctrl+Q, Inpaint Undo/Redo is Shift+Z / Shift+Q
    connect(create_shortcut("Ctrl+Z", parent), &QShortcut::activated, this, &shortcut_mgr::sig_undo_mask);
    connect(create_shortcut("Ctrl+Q", parent), &QShortcut::activated, this, &shortcut_mgr::sig_redo_mask);
    connect(create_shortcut("Shift+Z", parent), &QShortcut::activated, this, &shortcut_mgr::sig_undo_image);
    connect(create_shortcut("Shift+Q", parent), &QShortcut::activated, this, &shortcut_mgr::sig_redo_image);

    // === AI EXECUTION ===
    connect(create_shortcut("1", parent), &QShortcut::activated, this, [this]() {
        if (!is_editable_control(QApplication::focusWidget())) emit sig_run_ocr();
    });
    connect(create_shortcut("2", parent), &QShortcut::activated, this, [this]() {
        if (!is_editable_control(QApplication::focusWidget())) emit sig_run_inpaint();
    });

    // === TOOLS & MODES (Photoshop Parity) ===
    connect(create_shortcut("B", parent), &QShortcut::activated, this, [this]() {
        if (!is_editable_control(QApplication::focusWidget())) {
            emit sig_mode_paint();
            emit sig_tool_brush();
        }
    });
    connect(create_shortcut("E", parent), &QShortcut::activated, this, [this]() {
        if (!is_editable_control(QApplication::focusWidget())) emit sig_mode_erase();
    });
    connect(create_shortcut("M", parent), &QShortcut::activated, this, [this]() {
        if (!is_editable_control(QApplication::focusWidget())) emit sig_tool_rect();
    });
    connect(create_shortcut("L", parent), &QShortcut::activated, this, [this]() {
        if (!is_editable_control(QApplication::focusWidget())) emit sig_tool_lasso();
    });
    connect(create_shortcut("W", parent), &QShortcut::activated, this, [this]() {
        if (!is_editable_control(QApplication::focusWidget())) emit sig_tool_wand();
    });
    connect(create_shortcut("H", parent), &QShortcut::activated, this, [this]() {
        if (!is_editable_control(QApplication::focusWidget())) emit sig_tool_move();
    });

    // === MODIFIERS ===
    connect(create_shortcut("[", parent), &QShortcut::activated, this, [this]() {
        if (!is_editable_control(QApplication::focusWidget())) emit sig_decrease_value();
    });
    connect(create_shortcut("]", parent), &QShortcut::activated, this, [this]() {
        if (!is_editable_control(QApplication::focusWidget())) emit sig_increase_value();
    });

    // === FILE & SYSTEM ===
    connect(create_shortcut("Ctrl+S", parent), &QShortcut::activated, this, &shortcut_mgr::sig_export);
    connect(create_shortcut("Ctrl+O", parent), &QShortcut::activated, this, &shortcut_mgr::sig_open);
    connect(create_shortcut("Ctrl+Shift+O", parent), &QShortcut::activated, this, &shortcut_mgr::sig_open_folder);
    
    // === VIEW / CANVAS ===
    connect(create_shortcut("Ctrl+=", parent), &QShortcut::activated, this, &shortcut_mgr::sig_zoom_in);
    connect(create_shortcut("Ctrl+-", parent), &QShortcut::activated, this, &shortcut_mgr::sig_zoom_out);
    connect(create_shortcut("Ctrl+0", parent), &QShortcut::activated, this, &shortcut_mgr::sig_zoom_fit);
    connect(create_shortcut("Tab", parent), &QShortcut::activated, this, &shortcut_mgr::sig_toggle_ui);

    // === GALLERY PAGE NAVIGATION ===
    connect(create_shortcut("PgDown", parent), &QShortcut::activated, this, &shortcut_mgr::sig_page_next);
    connect(create_shortcut("PgUp", parent), &QShortcut::activated, this, &shortcut_mgr::sig_page_prev);
}

QShortcut* shortcut_mgr::create_shortcut(const QString& sequence, QWidget* parent,
    Qt::ShortcutContext context) {
    QShortcut* shortcut = new QShortcut(QKeySequence(sequence), parent);
    shortcut->setContext(context);
    return shortcut;
}