#ifndef CORE_HARDWARE_TELEMETRY_H
#define CORE_HARDWARE_TELEMETRY_H

#include <QObject>
#include <QTimer>
#include <windows.h>
#include <dxgi1_4.h>
#include <wrl/client.h>

class telemetry : public QObject {
    Q_OBJECT

public:
    explicit telemetry(int adapter_index = 0, QObject* parent = nullptr);
    ~telemetry();

    void start(int interval_ms = 1000);
    void stop();
    void set_target_gpu(int adapter_index);

signals:
    void metrics_updated(double ram_gb, double vram_gb);

private slots:
    void on_tick();

private:
    QTimer* ticker;
    int current_adapter_index;
    Microsoft::WRL::ComPtr<IDXGIFactory4> dxgi_factory;
    bool m_dxgi_initialized; // Tracks if DXGI is healthy

    double get_app_ram_usage_gb();
    double get_gpu_vram_usage_gb();
};

#endif // CORE_HARDWARE_TELEMETRY_H