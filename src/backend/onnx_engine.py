from src.utils.logger import logger

#/////////////////////////////////#
#   HARDWARE-AWARE ONNX ENGINE    #
#/////////////////////////////////#

class ONNXEngine:
    def __init__(self, model_path):
        import onnxruntime as ort

        # Preload DLLs to avoid runtime errors on Linux when using CUDA (CuBlas and CuDNN are troublesome)
        ort.preload_dlls()
        
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
