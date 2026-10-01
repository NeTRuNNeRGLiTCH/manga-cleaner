#include "export.h"
#include <QFileDialog>

export_actions::export_actions(QWidget* parent) : QObject(parent), parent_widget(parent) {
}

void export_actions::on_export_button_clicked() {
    // Open a directory dialog to ask the user WHERE to export the gallery
    QString output_dir = QFileDialog::getExistingDirectory(
        parent_widget,
        "Select Export Destination Folder",
        "",
        QFileDialog::ShowDirsOnly | QFileDialog::DontResolveSymlinks
    );

    if (!output_dir.isEmpty()) {
        emit request_batch_export(output_dir);
    }
}