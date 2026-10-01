#include "system_scanner.h"
#include "src/diagnostics/logger.h"

#include <windows.h>
#include <dxgi1_4.h>
#include <d3d12.h>
#include <wrl/client.h>
#include <intrin.h>

#pragma comment(lib, "dxgi.lib")
#pragma comment(lib, "d3d12.lib")

using Microsoft::WRL::ComPtr;

QString ComputeDevice::get_vram_string() const {
    if (type == DeviceType::CPU) return "System RAM";
    double gb = static_cast<double>(vram_bytes) / (1024.0 * 1024.0 * 1024.0);
    return QString::number(gb, 'f', 1) + " GB";
}

std::vector<ComputeDevice> system_scanner::get_all_devices() {
    std::vector<ComputeDevice> devices;
    LOG_TRACE("Initiating DXGI Hardware Scan...");

    ComputeDevice cpu_device;
    cpu_device.name = get_cpu_name();
    cpu_device.type = DeviceType::CPU;
    cpu_device.vendor = Vendor::Unknown;
    cpu_device.vram_bytes = 0;
    cpu_device.sys_ram_bytes = get_total_system_ram();
    cpu_device.supports_fp16 = false;
    cpu_device.adapter_index = -1;
    devices.push_back(cpu_device);

    LOG_INFO("Registered Host CPU: " + cpu_device.name);

    ComPtr<IDXGIFactory4> factory;
    if (FAILED(CreateDXGIFactory1(IID_PPV_ARGS(&factory)))) {
        LOG_ERROR("CreateDXGIFactory1 failed. GPU acceleration will be disabled.");
        return devices;
    }

    ComPtr<IDXGIAdapter1> adapter;
    int index = 0;

    while (factory->EnumAdapters1(index, &adapter) != DXGI_ERROR_NOT_FOUND) {
        DXGI_ADAPTER_DESC1 desc;
        adapter->GetDesc1(&desc);

        if (desc.Flags & DXGI_ADAPTER_FLAG_SOFTWARE) {
            LOG_TRACE(QString("Skipping Software Adapter[%1]").arg(index));
            index++;
            continue;
        }

        ComputeDevice gpu;
        gpu.adapter_index = index;
        gpu.name = QString::fromWCharArray(desc.Description);
        gpu.vram_bytes = desc.DedicatedVideoMemory;
        gpu.sys_ram_bytes = desc.SharedSystemMemory;

        if (desc.VendorId == 0x10DE) gpu.vendor = Vendor::NVIDIA;
        else if (desc.VendorId == 0x1002) gpu.vendor = Vendor::AMD;
        else if (desc.VendorId == 0x8086) gpu.vendor = Vendor::Intel;
        else gpu.vendor = Vendor::Unknown;

        if (gpu.vram_bytes < (512ULL * 1024 * 1024)) {
            gpu.type = DeviceType::IntegratedGPU;
        }
        else {
            gpu.type = DeviceType::DiscreteGPU;
        }

        gpu.supports_fp16 = false;
        ComPtr<ID3D12Device> d3d_device;
        if (SUCCEEDED(D3D12CreateDevice(adapter.Get(), D3D_FEATURE_LEVEL_11_0, IID_PPV_ARGS(&d3d_device)))) {
            D3D12_FEATURE_DATA_D3D12_OPTIONS options = {};
            if (SUCCEEDED(d3d_device->CheckFeatureSupport(D3D12_FEATURE_D3D12_OPTIONS, &options, sizeof(options)))) {
                if (options.MinPrecisionSupport & D3D12_SHADER_MIN_PRECISION_SUPPORT_16_BIT) {
                    gpu.supports_fp16 = true;
                }
            }
        }
        else {
            LOG_WARN(QString("Failed to create D3D12 device for GPU: %1. FP16 support unknown.").arg(gpu.name));
        }

        LOG_INFO(QString("Detected GPU [%1]: %2 | VRAM: %3 | FP16 Ready: %4")
            .arg(index).arg(gpu.name).arg(gpu.get_vram_string()).arg(gpu.supports_fp16 ? "YES" : "NO"));

        devices.push_back(gpu);
        index++;
    }

    return devices;
}

ComputeDevice system_scanner::get_best_device() {
    std::vector<ComputeDevice> all_devices = get_all_devices();
    ComputeDevice best = all_devices[0];

    for (const auto& dev : all_devices) {
        if (dev.type == DeviceType::DiscreteGPU) {
            if (best.type != DeviceType::DiscreteGPU || dev.vram_bytes > best.vram_bytes) {
                best = dev;
            }
        }
        else if (dev.type == DeviceType::IntegratedGPU && best.type == DeviceType::CPU) {
            best = dev;
        }
    }
    return best;
}

size_t system_scanner::get_total_system_ram() {
    MEMORYSTATUSEX statex;
    statex.dwLength = sizeof(statex);
    if (GlobalMemoryStatusEx(&statex)) {
        return statex.ullTotalPhys;
    }
    return 0;
}

int system_scanner::get_cpu_thread_count() {
    SYSTEM_INFO sysinfo;
    GetSystemInfo(&sysinfo);
    return static_cast<int>(sysinfo.dwNumberOfProcessors);
}

QString system_scanner::get_cpu_name() {
    int CPUInfo[4] = { -1 };
    unsigned nExIds, i = 0;
    char CPUBrandString[0x40] = { 0 };

    __cpuid(CPUInfo, 0x80000000);
    nExIds = CPUInfo[0];

    for (i = 0x80000000; i <= nExIds; ++i) {
        __cpuid(CPUInfo, i);
        if (i == 0x80000002) memcpy(CPUBrandString, CPUInfo, sizeof(CPUInfo));
        else if (i == 0x80000003) memcpy(CPUBrandString + 16, CPUInfo, sizeof(CPUInfo));
        else if (i == 0x80000004) memcpy(CPUBrandString + 32, CPUInfo, sizeof(CPUInfo));
    }

    QString name = QString::fromUtf8(CPUBrandString).trimmed();
    return name.isEmpty() ? "Unknown System CPU" : name;
}