#include "edit.h"

edit_actions::edit_actions(QWidget* parent) : QObject(parent), parent_widget(parent) {
    edit_menu = new QMenu(parent);
    setup_menu();
}

QMenu* edit_actions::get_menu() const {
    return edit_menu;
}

void edit_actions::setup_menu() {
    // === OBSIDIAN STYLING FOR THE MENU ===
    edit_menu->setStyleSheet(
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
        "   color: #4a9eff; "
        "}"
        "QMenu::separator { "
        "   height: 1px; "
        "   background: #3c3c3c; "
        "   margin: 4px 12px; "
        "}"
    );

    // === POPULATE MENU ACTIONS ===

    // Selection Undo / Redo Block
    QAction* act_undo_sel = edit_menu->addAction("Undo Selection\tCtrl+Z");
    QAction* act_redo_sel = edit_menu->addAction("Redo Selection\tCtrl+Q");
    edit_menu->addSeparator();

    // Inpaint Undo / Redo Block
    QAction* act_undo_inp = edit_menu->addAction("Undo Inpaint\tShift+Z");
    QAction* act_redo_inp = edit_menu->addAction("Redo Inpaint\tShift+Q");
    edit_menu->addSeparator();

    // Mask / Selection Block
    QAction* act_del_mask = edit_menu->addAction("Delete Mask");
    QAction* act_scan_trans = edit_menu->addAction("Scan Transparency");

    // === CONNECT ACTIONS DIRECTLY TO SIGNALS ===
    connect(act_undo_sel, &QAction::triggered, this, &edit_actions::request_undo_selection);
    connect(act_redo_sel, &QAction::triggered, this, &edit_actions::request_redo_selection);

    connect(act_undo_inp, &QAction::triggered, this, &edit_actions::request_undo_inpaint);
    connect(act_redo_inp, &QAction::triggered, this, &edit_actions::request_redo_inpaint);

    connect(act_del_mask, &QAction::triggered, this, &edit_actions::request_delete_mask);
    connect(act_scan_trans, &QAction::triggered, this, &edit_actions::request_scan_transparency);
}