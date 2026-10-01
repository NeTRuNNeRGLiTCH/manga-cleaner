#ifndef RIGHT_AI_PANEL_H
#define RIGHT_AI_PANEL_H

#include <QWidget>
#include <QVBoxLayout>
#include <QHBoxLayout>
#include <QPushButton>
#include <QButtonGroup>
#include <QStackedWidget>
#include <QLabel>
#include <QMovie>
#include <QProgressBar>

// Forward declarations for the 4 actual tabs
class studio_tab;
class wizard_tab;
class gallery_tab;
class transcript_tab;

class right_ai_panel : public QWidget {
    Q_OBJECT

public:
    explicit right_ai_panel(QWidget* parent = nullptr);
    ~right_ai_panel() = default;

    // === PUBLIC AI METHODS ===
    // states: "idle", "working", "error"
    void set_ai_state(const QString& state, const QString& message = "");
    void update_progress(int percentage);

    // === TAB GETTERS (Crucial for the Grand Wiring) ===
    studio_tab* get_studio_tab() const { return m_studio_tab; }
    wizard_tab* get_wizard_tab() const { return m_wizard_tab; }
    gallery_tab* get_gallery_tab() const { return m_gallery_tab; }
    transcript_tab* get_transcript_tab() const { return m_transcript_tab; }

private slots:
    // === NAVIGATION LOGIC ===
    void on_nav_clicked(int index);

private:
    // === UI SETUP ===
    void setup_ui();
    QPushButton* create_nav_button(const QString& text, const QString& icon_path, const QString& active_color);
    QWidget* create_placeholder_page(const QString& title);
    QPixmap recolor_svg(const QString& path, const QString& hex_color);

    // === WIDGETS ===
    QButtonGroup* nav_group;
    QStackedWidget* stacked_content;

    // === AI Status Header ===
    QLabel* anim_label;
    QLabel* status_text_label;
    QProgressBar* progress_bar;
    QMovie* current_movie;

    // === Navigation Buttons ===
    QPushButton* btn_studio;
    QPushButton* btn_wizard;
    QPushButton* btn_gallery;
    QPushButton* btn_layers;
    QPushButton* btn_easter_egg;

    // === Internal Tab Pointers ===
    studio_tab* m_studio_tab;
    wizard_tab* m_wizard_tab;
    gallery_tab* m_gallery_tab;
    transcript_tab* m_transcript_tab;
};

#endif // RIGHT_AI_PANEL_H