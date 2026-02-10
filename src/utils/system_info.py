import torch
import psutil
from typing import Tuple

#////////////////////////#
#  TELEMETRY & MONITOR   #
#////////////////////////#

class SystemMonitor:
    @staticmethod
    def get_vram_info() -> Tuple[int, int]:
        if torch.cuda.is_available():
            total = torch.cuda.get_device_properties(0).total_memory / 1e6
            allocated = torch.cuda.memory_allocated(0) / 1e6
            reserved = torch.cuda.memory_reserved(0) / 1e6
            return int(allocated + reserved), int(total)
        return 0, 0

    @staticmethod
    def get_ram_usage() -> float:
        return psutil.virtual_memory().percent