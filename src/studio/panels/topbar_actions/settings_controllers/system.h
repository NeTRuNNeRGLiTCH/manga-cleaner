#ifndef SETTINGS_CONTROLLERS_SYSTEM_H
#define SETTINGS_CONTROLLERS_SYSTEM_H

#include <QWidget>
#include <QVBoxLayout>
#include <QHBoxLayout>
#include <QLabel>
#include <QComboBox>
#include <QScrollArea>

class settings_system : public QWidget {
    Q_OBJECT

public:
    explicit settings_system(QWidget* parent = nullptr);
    ~settings_system() = default;

private:
    void setup_ui();

    // UI Generators
    QLabel* create_section_header(const QString& title, const QString& hex_color);
    QFrame* create_separator();
    QWidget* create_combo_row(const QString& label_text, const QString& desc_text, const QStringList& options, int default_index, QComboBox*& combo_ptr);
    QWidget* create_spec_row(const QString& label, const QString& value, const QString& val_color = "#e0e0e0");

    // WIDGET POINTERS: Model Persistence
    QComboBox* combo_persist_bpn;
    QComboBox* combo_persist_moebius;
    QComboBox* combo_persist_lama;

    // Architecture Dispatch Override
    QComboBox* combo_arch_dispatch;
};

#endif // SETTINGS_CONTROLLERS_SYSTEM_H