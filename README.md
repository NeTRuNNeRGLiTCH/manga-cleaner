🌌 Titan Manga Studio v1
    Titan Manga Studio is a high-performance, AI-powered desktop application designed for manga scanlation and restoration. It automates the tedious process of text removal and background inpainting using state-of-the-art Computer Vision and Deep Learning models.

🚀 Key Technical Features
    🧠 Advanced AI Inpainting
        Integrated the SimpleLama (LaMa) model to handle complex background restoration. Unlike standard blur-based fills, LaMa uses large-mask inpainting to reconstruct textures and patterns behind deleted text.
    🧩 Dynamic Proportional Tiling
        To handle high-resolution manga pages (4K+) without crashing GPUs (VRAM limitations), I developed a Dynamic Tiling Engine.
        Divides images into overlapping segments.
        Processes in-memory chunks.
        Seamlessly blends results using a Gaussian-weighted mask to prevent visible seams.
    🤖 Multi-Stage Auto-Detection
        Uses a hybrid detection logic to create perfect cleaning masks:
        OCR Detection: Identifies text coordinates using EasyOCR.
        Saturation Analysis: Captures "Purple/Red Energy" glows and SFX often missed by standard OCR.
        Contour Logic: Automatically fills hollow/outlined text centers to ensure a solid clean.
    ⚡ Professional GUI Architecture
        Multi-threaded Execution: Heavy AI processing is offloaded to QThreads to keep the UI responsive (60 FPS).
        Singleton Model Caching: OCR and AI models are cached in memory, reducing latency between operations.
        State History Stack: Implemented a bounded Undo system for non-destructive editing.
        Photoshop Bridge: Uses win32com to automate professional export workflows directly into Adobe Photoshop.
    🛠️ Tech Stack
        Core: Python 3.10
        GUI: PySide6 (Qt for Python)
        Deep Learning: PyTorch
        Computer Vision: OpenCV, NumPy
        OCR: EasyOCR
        Inpainting: SimpleLama
        Automation: PyWin32 (Photoshop COM API)

##NOTE: it only works with python 3.12 or lower!!!