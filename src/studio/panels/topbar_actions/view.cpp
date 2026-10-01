#include "view.h"

view_actions::view_actions(QWidget* parent) : QObject(parent), parent_widget(parent) {
    view_menu = new QMenu(parent);
    setup_menu();
}

QMenu* view_actions::get_menu() const {
    return view_menu;
}

void view_actions::setup_menu() {
    // === OBSIDIAN STYLING FOR THE MENU ===
    view_menu->setStyleSheet(
        "QMenu { "
        "   background-color: #1e1e1e; "
        "   color: #e0e0e0; "
        "   border: 1px solid #3c3c3c; "
        "   border-radius: 4px; "
        "   padding: 4px 0px; "
        "}"
        "QMenu::item { "
        "   padding: 6px 32px 6px 24px; "
        "   background-color: transparent; "
        "}"
        "QMenu::item:selected { "
        "   background-color: #3c3c3c; "
        "   color: #10b981; " 
        "}"
        "QMenu::item:disabled { "
        "   color: #6f6f6f; " 
        "}"
        "QMenu::separator { "
        "   height: 1px; "
        "   background: #3c3c3c; "
        "   margin: 4px 12px; "
        "}"
    );

    // === POPULATE MENU ACTIONS ===

    QAction* act_zoom_in = view_menu->addAction("Zoom In\tCtrl++");
    QAction* act_zoom_out = view_menu->addAction("Zoom Out\tCtrl+-");
    QAction* act_zoom_fit = view_menu->addAction("Fit to Window\tCtrl+0");
    view_menu->addSeparator();
    QAction* act_toggle_panels = view_menu->addAction("Toggle Panels\tTab");

    connect(act_zoom_in, &QAction::triggered, this, &view_actions::request_zoom_in);
    connect(act_zoom_out, &QAction::triggered, this, &view_actions::request_zoom_out);
    connect(act_zoom_fit, &QAction::triggered, this, &view_actions::request_zoom_fit);
    connect(act_toggle_panels, &QAction::triggered, this, &view_actions::request_toggle_panels);
}