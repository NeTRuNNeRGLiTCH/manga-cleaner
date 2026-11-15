import os
import sys
from src.utils.logger import logger

#/////////////////////////////////#
#   HARDWARE-AWARE ONNX ENGINE    #
#/////////////////////////////////#

class ONNXEngine:
    def __init__(self, model_path):
        if sys.platform == "win32":
            import site
            from pathlib import Path
            search_dirs = []
            if getattr(sys, 'frozen', False):
                base_exe = Path(sys.executable).resolve().parent
                search_dirs.append(base_exe)
                search_dirs.append(base_exe / "_internal")
                meipass = getattr(sys, '_MEIPASS', None)
                if meipass:
                    search_dirs.append(Path(meipass))
            else:
                for p in site.getsitepackages():
                    nd = Path(p) / "nvidia"
                    if nd.is_dir():
                        search_dirs.extend(nd.rglob("bin"))
            for d in search_dirs:
                if d.is_dir():
                    try:
                        os.add_dll_directory(str(d))
                    except Exception:
                        pass
                    os.environ["PATH"] = str(d) + os.pathsep + os.environ.get("PATH", "")

        elif sys.platform.startswith("linux"):
            from pathlib import Path
            import ctypes
            search_dirs = []
            if getattr(sys, 'frozen', False):
                base_exe = Path(sys.executable).resolve().parent
                search_dirs.append(base_exe)
                search_dirs.append(base_exe / "_internal")
                meipass = getattr(sys, '_MEIPASS', None)
                if meipass:
                    search_dirs.append(Path(meipass))
            else:
                import site
                for p in site.getsitepackages():
                    nd = Path(p) / "nvidia"
                    if nd.is_dir():
                        search_dirs.extend(nd.rglob("lib"))
            for d in search_dirs:
                if d.is_dir():
                    os.environ["LD_LIBRARY_PATH"] = str(d) + os.pathsep + os.environ.get("LD_LIBRARY_PATH", "")
                    for so_path in sorted(d.rglob("*.so*")):
                        so_name = so_path.name
                        if any(k in so_name for k in ["libcuda", "libnvJitLink", "libnvrtc", "libcublas", "libcufft", "libcudnn"]):
                            try:
                                ctypes.CDLL(str(so_path), mode=ctypes.RTLD_GLOBAL)
                            except Exception:
                                pass

        import onnxruntime as ort

        # Preload DLLs to avoid runtime errors on Linux when using CUDA (CuBlas and CuDNN are troublesome)
        if hasattr(ort, "preload_dlls"):
            try:
                ort.preload_dlls()
            except Exception:
                pass
        
        providers = ort.get_available_providers()
        
        sess_opt = ort.SessionOptions()
        sess_opt.enable_mem_pattern = False 
        sess_opt.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
        
        success = False
        if 'CUDAExecutionProvider' in providers:
            try:
                cuda_options = {
                    'device_id': 0,
                    'arena_extend_strategy': 'kSameAsRequested',
                    'cudnn_conv_algo_search': 'HEURISTIC', 
                    'do_copy_in_default_stream': True,
                }
                
                self.session = ort.InferenceSession(
                    model_path, 
                    sess_options=sess_opt,
                    providers=[('CUDAExecutionProvider', cuda_options), 'CPUExecutionProvider']
                )
                self.device = "GPU"
                success = True
            except Exception as e:
                logger.warning(f"CUDA initialization error: {e}")

        if not success:
            self.session = ort.InferenceSession(
                model_path, 
                sess_options=sess_opt,
                providers=['CPUExecutionProvider']
            )
            self.device = "CPU"
            
        self.input_names = [i.name for i in self.session.get_inputs()]
        logger.info(f"Engine Ready | Device: {self.device} | {model_path}")

    def run(self, input_data):
        if isinstance(input_data, dict):
            return self.session.run(None, input_data)
        return self.session.run(None, {self.input_names[0]: input_data})
