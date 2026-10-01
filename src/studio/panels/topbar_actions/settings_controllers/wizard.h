#ifndef SETTINGS_CONTROLLERS_WIZARD_H
#define SETTINGS_CONTROLLERS_WIZARD_H

#include <QWidget>
#include <QVBoxLayout>
#include <QHBoxLayout>
#include <QLabel>
#include <QComboBox>
#include <QLineEdit>
#include <QPushButton>
#include <QScrollArea>
#include <QPainter>
#include <QMouseEvent>

// ==========================================================
// Isolated Switch for the Wizard Settings Tab
// ==========================================================
class WizSetToggle : public QWidget {
    Q_OBJECT
public:
    explicit WizSetToggle(bool default_state = false, QWidget* parent = nullptr);
    bool isChecked() const;

signals:
    void toggled(bool checked);

protected:
    void mouseReleaseEvent(QMouseEvent* event) override;
    void paintEvent(QPaintEvent* event) override;

private:
    bool m_checked;
};

// ==========================================================
// Wizard Settings Controller
// ==========================================================
class settings_wizard : public QWidget {
    Q_OBJECT

public:
    explicit settings_wizard(QWidget* parent = nullptr);
    ~settings_wizard() = default;

private:
    void setup_ui();

    // UI Helpers
    QLabel* create_section_header(const QString& title, const QString& hex_color);
    QFrame* create_separator();
    QWidget* create_toggle_row(const QString& label_text, const QString& desc_text, bool is_checked, WizSetToggle*& toggle_ptr);
    QWidget* create_combo_row(const QString& label_text, const QString& desc_text, const QStringList& options, int default_index, QComboBox*& combo_ptr);
    QWidget* create_path_row(const QString& label_text, const QString& desc_text, const QString& default_path, QLineEdit*& line_ptr, QPushButton*& btn_ptr);

    // WIDGET POINTERS
    WizSetToggle* toggle_run_bpn;
    WizSetToggle* toggle_run_moebius;

    QLineEdit* line_batch_export;
    QPushButton* btn_batch_browse;
    QComboBox* combo_batch_format;
    QComboBox* combo_error_handling;

    WizSetToggle* toggle_zip_archive;
};

#endif // SETTINGS_CONTROLLERS_WIZARD_H