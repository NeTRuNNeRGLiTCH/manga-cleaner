#ifndef TOPBAR_ACTION_FILE_H
#define TOPBAR_ACTION_FILE_H

#include <QObject>
#include <QMenu>
#include <QWidget>
#include <QStringList>

class file_actions : public QObject {
    Q_OBJECT

public:
    explicit file_actions(QWidget* parent = nullptr);
    ~file_actions() = default;

    // Returns the fully styled menu to be attached to the TopBar's "File" button
    QMenu* get_menu() const;

signals:
    // === OUTGOING SIGNALS TO THE BACKEND / WORKSPACE ===
    void request_open_image(const QStringList& file_paths);
    void request_open_chapter(const QString& folder_path);
    void request_add_image(const QStringList& file_paths);

    void request_save();       // Saves current active image (default JPG)
    void request_save_all();   // Saves everything in the gallery tab
    void request_remove();     // Removes current active image and frees RAM/VRAM
    void request_clear_cached_edits(); // Deletes the per-page working-state cache from disk
    void request_exit();       // Clean application shutdown

private slots:
    // === INTERNAL DIALOG HANDLERS ===
    void on_open_image_clicked();
    void on_open_chapter_clicked();
    void on_add_image_clicked();

private:
    QMenu* file_menu;
    QWidget* parent_widget;

    void setup_menu();
};

#endif