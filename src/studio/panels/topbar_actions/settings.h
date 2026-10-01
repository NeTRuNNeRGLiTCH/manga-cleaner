#ifndef TOPBAR_ACTION_SETTINGS_H
#define TOPBAR_ACTION_SETTINGS_H

#include <QDialog>
#include <QVBoxLayout>
#include <QHBoxLayout>
#include <QStackedWidget>
#include <QPushButton>
#include <QButtonGroup>

// Forward declarations for the 4 sub-controllers
class settings_models;
class settings_system;
class settings_image;  // Fixed to singular
class settings_wizard;

class settings_dialog : public QDialog {
    Q_OBJECT

public:
    explicit settings_dialog(QWidget* parent = nullptr);
    ~settings_dialog() = default;

private slots:
    void on_nav_clicked(int index);

private:
    void setup_ui();
    QPushButton* create_nav_button(const QString& text, const QString& icon_path);
    QPixmap recolor_svg(const QString& path, const QString& hex_color);

    // === WIDGETS ===
    QStackedWidget* stacked_content;
    QButtonGroup* nav_group;

    // === SUB-CONTROLLERS (The 4 Real Tabs) ===
    settings_models* ctrl_models;
    settings_system* ctrl_system;
    settings_image* ctrl_image;   // Fixed to singular
    settings_wizard* ctrl_wizard;
};

#endif // TOPBAR_ACTION_SETTINGS_H