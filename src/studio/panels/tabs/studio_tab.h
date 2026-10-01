#ifndef STUDIO_TAB_H
#define STUDIO_TAB_H

#include <QWidget>
#include <QVBoxLayout>
#include <QLabel>
#include <QPushButton>
#include <QScrollArea>
#include <QEvent>
#include <QPixmap>
#include <QRadioButton>
#include <QButtonGroup>
#include "src/core/pipeline/ai_types.h"

// ==========================================================
// Studio Tab Controller
// ==========================================================
class studio_tab : public QWidget {
    Q_OBJECT

public:
    explicit studio_tab(QWidget* parent = nullptr);
    ~studio_tab() = default;

    // Inpainting backend selected by the radio row under the Clean button.
    // Mirrors InpaintEngine: 0 = Auto, 1 = LaMa, 2 = Moebius.
    int selected_inpaint_engine() const;
    void set_inpaint_engine(int engine);

signals:
    // === OUTGOING ACTION SIGNALS ===
    // These tell the Pipeline Manager exactly which AI model to run on the active canvas
    void run_detect_requested();
    void scan_transparency_requested();
    void run_clean_requested();
    void inpaint_engine_changed(int engine);
    void stop_requested();

protected:
    bool eventFilter(QObject* obj, QEvent* event) override;

private slots:
    void on_inpaint_engine_clicked(int id);

private:
    void setup_ui();
    QLabel* create_section_header(const QString& title);
    QLabel* create_description_text(const QString& text);
    QFrame* create_separator();
    QPixmap recolor_svg(const QString& path, const QString& hex_color);

    QScrollArea* scroll_area;
    QWidget* scroll_content;

    QPushButton* btn_detect;
    QPushButton* btn_scan_transparency;
    QPushButton* btn_clean;
    QPushButton* btn_stop;

    QButtonGroup* inpaint_group;
    QRadioButton* radio_auto;
    QRadioButton* radio_lama;
    QRadioButton* radio_moebius;
};

#endif // STUDIO_TAB_H