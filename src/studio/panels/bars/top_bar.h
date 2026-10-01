#ifndef TOP_BAR_H
#define TOP_BAR_H

#include <QWidget>
#include <QLabel>
#include <QPushButton>
#include <QHBoxLayout>
#include <QFrame>

// Forward declarations for our action controllers
class file_actions;
class edit_actions;
class view_actions;
class folder_actions;
class export_actions;

class top_bar : public QWidget {
    Q_OBJECT

public:
    explicit top_bar(QWidget* parent = nullptr);
    ~top_bar() = default;

    // === PUBLIC UPDATE METHODS ===
    void update_ram(double gb);
    void update_vram(double gb);
    void set_processor_mode(bool is_gpu);

    // === ACTION CONTROLLER GETTERS ===
    // This allows the main axis_cleaner window to connect directly to the backend
    file_actions* get_file_actions() const { return file_ctrl; }
    edit_actions* get_edit_actions() const { return edit_ctrl; }
    view_actions* get_view_actions() const { return view_ctrl; }
    folder_actions* get_folder_actions() const { return folder_ctrl; }
    export_actions* get_export_actions() const { return export_ctrl; }

signals:
    // === TAB / DIALOG REQUEST SIGNALS ===
    // These tell the main window to open the respective modal dialogs
    void settings_requested();
    void help_requested();
    void feedback_requested();
    void about_requested();

private:
    // === UI SETUP ===
    void setup_ui();
    QPushButton* create_menu_button(const QString& text);
    QWidget* create_resource_badge(const QString& icon_path, const QString& prefix_text, QLabel*& value_label);

    // === ACTION CONTROLLERS ===
    file_actions* file_ctrl;
    edit_actions* edit_ctrl;
    view_actions* view_ctrl;
    folder_actions* folder_ctrl;
    export_actions* export_ctrl;

    // === WIDGETS ===
    QLabel* ram_value_label;
    QLabel* vram_value_label;

    QLabel* processor_icon_label;
    QLabel* processor_text_label;
    QWidget* processor_badge;

    QPushButton* btn_export;
    QPushButton* btn_folder;
};

#endif // TOP_BAR_H