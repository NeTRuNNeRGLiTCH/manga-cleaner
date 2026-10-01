#ifndef STATUS_BAR_H
#define STATUS_BAR_H

#include <QWidget>
#include <QLabel>
#include <QHBoxLayout>
#include <QString>

class status_bar : public QWidget {
    Q_OBJECT

public:
    explicit status_bar(QWidget* parent = nullptr);
    ~status_bar() = default;

    // === UPDATE METHODS ===
    void update_status(const QString& text);
    void update_mode(const QString& mode);
    void update_tool(const QString& tool);
    void update_loaded_models(const QString& models_info);

private:
    // === UI ELEMENTS ===
    QLabel* status_label;
    QLabel* mode_label;
    QLabel* tool_label;
    QLabel* models_label;

    // === SETUP METHODS ===
    void setup_ui();
};

#endif