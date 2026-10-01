#ifndef GALLERY_TAB_H
#define GALLERY_TAB_H

#include <QWidget>
#include <QVBoxLayout>
#include <QHBoxLayout>
#include <QLabel>
#include <QPushButton>
#include <QScrollArea>
#include <QEvent>
#include <QStringList>

class gallery_tab : public QWidget {
    Q_OBJECT

public:
    explicit gallery_tab(QWidget* parent = nullptr);
    ~gallery_tab() = default;

    // === NEW UI LINKING METHODS ===
    // Populates the side panel with actual files from the user's hard drive
    void populate_gallery(const QStringList& file_paths);

    // Wipes the panel clean (used when opening a new folder)
    void clear_gallery();

    void update_image_count(int count);

    // Highlights the item matching `filepath` without loading anything - used
    // by the main window to keep the selection in sync after programmatic
    // loads (File > Remove, Add Image, page navigation).
    void set_active_file(const QString& filepath);

signals:
    // Tells the main window to load the clicked file into OpenCV and the Canvas
    void request_open_image(const QString& filepath);

    // Trash button: the main window must also drop its own m_active_files
    // list and the open session, otherwise Save All / Run Wizard would still
    // process files the user believes are gone.
    void clear_requested();

protected:
    bool eventFilter(QObject* obj, QEvent* event) override;

private slots:
    void on_image_clicked(int index);

private:
    void setup_ui();
    QPixmap recolor_svg(const QString& path, const QString& hex_color);
    QFrame* create_separator();
    void highlight_item(int index);

    QWidget* create_empty_state();
    QPushButton* create_gallery_item(int index, const QString& name, const QString& info, const QString& thumb_icon, bool is_active);

    // === WIDGETS ===
    QScrollArea* scroll_area;
    QWidget* scroll_content;
    QVBoxLayout* list_layout;

    QLabel* header_count_label;
    QWidget* empty_state_widget;

    // === TRACKERS ===
    QStringList m_file_paths; // Holds the real absolute paths to the images
    QList<QPushButton*> image_buttons;
    QList<QWidget*> indicator_dots;
};

#endif // GALLERY_TAB_H