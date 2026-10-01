#ifndef TOPBAR_ACTION_HELP_H
#define TOPBAR_ACTION_HELP_H

#include <QDialog>
#include <QVBoxLayout>
#include <QScrollArea>
#include <QLabel>
#include <QPushButton>

class help_dialog : public QDialog {
    Q_OBJECT

public:
    explicit help_dialog(QWidget* parent = nullptr);
    ~help_dialog() = default;

private:
    void setup_ui();
    QLabel* create_section_header(const QString& title, const QString& hex_color);
    QWidget* create_shortcut_row(const QString& keys, const QString& description);
};

#endif // TOPBAR_ACTION_HELP_H