#include "folder.h"
#include <QFileDialog>

folder_actions::folder_actions(QWidget* parent) : QObject(parent), parent_widget(parent) {
}

void folder_actions::on_folder_button_clicked() {
    // Open a directory dialog. We enforce ShowDirsOnly and DontResolveSymlinks 
    // to prevent Windows/Linux shortcut weirdness when loading massive manga chapters.
    QString dir = QFileDialog::getExistingDirectory(
        parent_widget,
        "Import Manga Folder",
        "",
        QFileDialog::ShowDirsOnly | QFileDialog::DontResolveSymlinks
    );

    if (!dir.isEmpty()) {
        emit request_open_folder(dir);
    }
}