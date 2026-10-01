#include "telemetry.h"
#include "src/diagnostics/logger.h"
#include <psapi.h>

#pragma comment(lib, "psapi.lib")
#pragma comment(lib, "dxgi.lib")

using Microsoft::WRL::ComPtr;

telemetry::telemetry(int adapter_index, QObject* parent)
    : QObject(parent), current_adapter_index(adapter_index), m_dxgi_initialized(false) {

    ticker = new QTimer(this);
    connect(ticker, &QTimer::timeout, this, &telemetry::on_tick);

    if (SUCCEEDED(CreateDXGIFactory1(IID_PPV_ARGS(&dxgi_factory)))) {
        m_dxgi_initialized = true;
    }
    else {
        LOG_ERROR("Telemetry failed to initialize DXGI factory. VRAM stats will show 0.0 GB.");
    }
}

telemetry::~telemetry() {
    stop();
}

void telemetry::start(int interval_ms) {
    if (!ticker->isActive()) {
        ticker->start(interval_ms);
        LOG_INFO("Hardware telemetry heartbeat started.");
    }
}

void telemetry::stop() {
    if (ticker->isActive()) {
        ticker->stop();
        LOG_INFO("Hardware telemetry heartbeat stopped.");
    }
}

void telemetry::set_target_gpu(int adapter_index) {
    current_adapter_index = adapter_index;
    LOG_TRACE(QString("Telemetry target GPU switched to index: %1").arg(adapter_index));
}

void telemetry::on_tick() {
    double ram = get_app_ram_usage_gb();
    double vram = get_gpu_vram_usage_gb();
    emit metrics_updated(ram, vram);
}

double telemetry::get_app_ram_usage_gb() {
    PROCESS_MEMORY_COUNTERS_EX pmc;
    if (GetProcessMemoryInfo(GetCurrentProcess(), (PROCESS_MEMORY_COUNTERS*)&pmc, sizeof(pmc))) {
        return static_cast<double>(pmc.WorkingSetSize) / (1024.0 * 1024.0 * 1024.0);
    }
    return 0.0;
}

double telemetry::get_gpu_vram_usage_gb() {
    if (current_adapter_index < 0 || !m_dxgi_initialized) return 0.0;

    ComPtr<IDXGIAdapter1> adapter;
    if (SUCCEEDED(dxgi_factory->EnumAdapters1(current_adapter_index, &adapter))) {
        ComPtr<IDXGIAdapter3> adapter3;
        if (SUCCEEDED(adapter.As(&adapter3))) {
            DXGI_QUERY_VIDEO_MEMORY_INFO mem_info;
            if (SUCCEEDED(adapter3->QueryVideoMemoryInfo(0, DXGI_MEMORY_SEGMENT_GROUP_LOCAL, &mem_info))) {
                return static_cast<double>(mem_info.CurrentUsage) / (1024.0 * 1024.0 * 1024.0);
            }
        }
    }
    return 0.0;
}