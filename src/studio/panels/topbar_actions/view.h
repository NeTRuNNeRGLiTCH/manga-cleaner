#ifndef TOPBAR_ACTION_VIEW_H
#define TOPBAR_ACTION_VIEW_H

#include <QObject>
#include <QMenu>
#include <QWidget>

class view_actions : public QObject {
    Q_OBJECT

public:
    explicit view_actions(QWidget* parent = nullptr);
    ~view_actions() = default;

    // Returns the fully styled menu to be attached to the TopBar's "View" button
    QMenu* get_menu() const;

signals:
    void request_zoom_in();
    void request_zoom_out();
    void request_zoom_fit();
    void request_toggle_panels();

private:
    QMenu* view_menu;
    QWidget* parent_widget;

    void setup_menu();
};

#endif // TOPBAR_ACTION_VIEW_H