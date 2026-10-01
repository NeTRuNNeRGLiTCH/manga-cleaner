#ifndef CORE_HARDWARE_SYSTEM_SCANNER_H
#define CORE_HARDWARE_SYSTEM_SCANNER_H

#include <vector>
#include <QString>

enum class DeviceType { CPU, IntegratedGPU, DiscreteGPU };
enum class Vendor { NVIDIA, AMD, Intel, Unknown };

struct ComputeDevice {
    QString name;
    DeviceType type;
    Vendor vendor;
    
    size_t vram_bytes;       
    size_t sys_ram_bytes;    
    
    bool supports_fp16;      
    int adapter_index;       
    
    QString get_vram_string() const;
};

class system_scanner {
public:
    static std::vector<ComputeDevice> get_all_devices();
    static ComputeDevice get_best_device();

    static size_t get_total_system_ram();
    static int get_cpu_thread_count();
    static QString get_cpu_name();
};

#endif // CORE_HARDWARE_SYSTEM_SCANNER_H