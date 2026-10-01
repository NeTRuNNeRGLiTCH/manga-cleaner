#ifndef TOPBAR_ACTION_EDIT_H
#define TOPBAR_ACTION_EDIT_H

#include <QObject>
#include <QMenu>
#include <QWidget>

class edit_actions : public QObject {
    Q_OBJECT

public:
    explicit edit_actions(QWidget* parent = nullptr);
    ~edit_actions() = default;

    // Returns the fully styled menu to be attached to the TopBar's "Edit" button
    QMenu* get_menu() const;

signals:
    // === HISTORY SIGNALS ===
    void request_undo_selection();
    void request_redo_selection();
    void request_undo_inpaint();
    void request_redo_inpaint();

    // === SELECTION / MASK SIGNALS ===
    void request_delete_mask();    // Clears the current mask overlay
    void request_scan_transparency();

private:
    QMenu* edit_menu;
    QWidget* parent_widget;

    void setup_menu();
};

#endif // TOPBAR_ACTION_EDIT_H