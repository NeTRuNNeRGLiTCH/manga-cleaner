#include "axis_cleaner.h"
#include <QtWidgets/QApplication>
#include <QDir>
#include <QFileInfo>
#include <QStandardPaths>
#include "src/core/state/session_data.h"

int main(int argc, char* argv[])
{
    /*
    The per - page edit cache lives under QStandardPaths::AppLocalDataLocation,
    which is derived from the ORGANIZATION/APPLICATION names. Before they
    were set explicitly it fell back to the executable's base name, so
    capture that legacy location BEFORE the names are set and move any
    existing cache over - otherwise an upgrade would look like data loss.
    */
    const QString legacy_state_dir =
        QStandardPaths::writableLocation(QStandardPaths::AppLocalDataLocation) + "/working_state";

    QCoreApplication::setOrganizationName("AxisStudio");
    QCoreApplication::setApplicationName("AxisStudio");

    QApplication app(argc, argv);

    const QString state_dir = session_data::working_state_dir();
    if (state_dir != legacy_state_dir
        && QDir(legacy_state_dir).exists()
        && !QFileInfo::exists(state_dir)) {
        QDir().mkpath(QFileInfo(state_dir).absolutePath());
        if (QDir().rename(legacy_state_dir, state_dir)) {
            // Best effort: drop the now-empty legacy folder next to it.
            QDir(QFileInfo(legacy_state_dir).absolutePath())
                .rmdir(QFileInfo(legacy_state_dir).fileName());
        }
    }

    axis_cleaner window;
    window.show();
    return app.exec();
}