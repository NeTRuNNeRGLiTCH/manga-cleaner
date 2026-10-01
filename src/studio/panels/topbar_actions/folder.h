#ifndef TOPBAR_ACTION_FOLDER_H
#define TOPBAR_ACTION_FOLDER_H

#include <QObject>
#include <QWidget>
#include <QString>

class folder_actions : public QObject {
    Q_OBJECT

public:
    explicit folder_actions(QWidget* parent = nullptr);
    ~folder_actions() = default;

signals:
    // === OUTGOING SIGNAL TO THE WORKSPACE ===
    void request_open_folder(const QString& folder_path);

public slots:
    // === TRIGGER SLOT FOR THE BUTTON ===
    void on_folder_button_clicked();

private:
    QWidget* parent_widget;
};

#endif // TOPBAR_ACTION_FOLDER_H