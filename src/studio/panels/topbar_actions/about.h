#ifndef TOPBAR_ACTION_ABOUT_H
#define TOPBAR_ACTION_ABOUT_H

#include <QDialog>
#include <QVBoxLayout>
#include <QScrollArea>
#include <QLabel>
#include <QPushButton>

class about_dialog : public QDialog {
    Q_OBJECT

public:
    explicit about_dialog(QWidget* parent = nullptr);
    ~about_dialog() = default;

private slots:
    void show_binance_qr_dialog();

private:
    void setup_ui();
    QPushButton* create_offering_button(const QString& text, const QString& icon_path, const QString& glow_color, const QString& url);
    QPushButton* create_action_button(const QString& text, const QString& icon_path, const QString& glow_color);
    QPixmap recolor_svg(const QString& path, const QString& hex_color);
};

#endif // TOPBAR_ACTION_ABOUT_H