#ifndef TOPBAR_ACTION_EXPORT_H
#define TOPBAR_ACTION_EXPORT_H

#include <QObject>
#include <QWidget>
#include <QString>

class export_actions : public QObject {
    Q_OBJECT

public:
    explicit export_actions(QWidget* parent = nullptr);
    ~export_actions() = default;

signals:
    // === OUTGOING SIGNAL TO THE STORAGE MODULE ===
    // We send the destination folder. The backend will check the user's 
    // global settings to determine if it should use .jpg, .png, etc.
    void request_batch_export(const QString& output_dir);

public slots:
    // === TRIGGER SLOT FOR THE EXPORT BUTTON ===
    void on_export_button_clicked();

private:
    QWidget* parent_widget;
};

#endif // TOPBAR_ACTION_EXPORT_H