#include "file.h"
#include <QFileDialog>
#include <QApplication>

file_actions::file_actions(QWidget* parent) : QObject(parent), parent_widget(parent) {
    file_menu = new QMenu(parent);
    setup_menu();
}

QMenu* file_actions::get_menu() const {
    return file_menu;
}

void file_actions::setup_menu() {
    // === OBSIDIAN STYLING FOR THE MENU ===
    file_menu->setStyleSheet(
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
        "   color: #9b59ff; " // Violet highlight on hover
        "}"
        "QMenu::separator { "
        "   height: 1px; "
        "   background: #3c3c3c; "
        "   margin: 4px 12px; "
        "}"
    );

    // === POPULATE MENU ACTIONS ===
    QAction* act_open_img = file_menu->addAction("Open Image...");
    QAction* act_open_chap = file_menu->addAction("Open Chapter...");
    file_menu->addSeparator();

    QAction* act_add_img = file_menu->addAction("Add Image...");
    file_menu->addSeparator();

    QAction* act_save = file_menu->addAction("Save");
    QAction* act_save_all = file_menu->addAction("Save All");
    file_menu->addSeparator();

    QAction* act_remove = file_menu->addAction("Remove Image");
    QAction* act_clear_cache = file_menu->addAction("Clear Cached Page Edits");
    file_menu->addSeparator();

    QAction* act_exit = file_menu->addAction("Exit");

    // === CONNECT ACTIONS TO SLOTS AND SIGNALS ===
    connect(act_open_img, &QAction::triggered, this, &file_actions::on_open_image_clicked);
    connect(act_open_chap, &QAction::triggered, this, &file_actions::on_open_chapter_clicked);
    connect(act_add_img, &QAction::triggered, this, &file_actions::on_add_image_clicked);

    // Direct signal emission for actions that don't need a UI dialog
    connect(act_save, &QAction::triggered, this, &file_actions::request_save);
    connect(act_save_all, &QAction::triggered, this, &file_actions::request_save_all);
    connect(act_remove, &QAction::triggered, this, &file_actions::request_remove);
    connect(act_clear_cache, &QAction::triggered, this, &file_actions::request_clear_cached_edits);
    connect(act_exit, &QAction::triggered, this, &file_actions::request_exit);
}

// === DIALOG LOGIC ===

void file_actions::on_open_image_clicked() {
    QStringList files = QFileDialog::getOpenFileNames(
        parent_widget,
        "Open Manga Image(s)",
        "",
        "Images (*.png *.jpg *.jpeg *.webp *.bmp)"
    );

    if (!files.isEmpty()) {
        emit request_open_image(files);
    }
}

void file_actions::on_open_chapter_clicked() {
    QString dir = QFileDialog::getExistingDirectory(
        parent_widget,
        "Select Chapter Folder",
        "",
        QFileDialog::ShowDirsOnly | QFileDialog::DontResolveSymlinks
    );

    if (!dir.isEmpty()) {
        emit request_open_chapter(dir);
    }
}

void file_actions::on_add_image_clicked() {
    QStringList files = QFileDialog::getOpenFileNames(
        parent_widget,
        "Add Manga Image(s)",
        "",
        "Images (*.png *.jpg *.jpeg *.webp *.bmp)"
    );

    if (!files.isEmpty()) {
        emit request_add_image(files);
    }
}