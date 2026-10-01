#ifndef CORE_PIPELINE_AI_TYPES_H
#define CORE_PIPELINE_AI_TYPES_H

// ==========================================================
// Shared AI task types (kept dependency-free so both the UI
// and the worker threads can include this header cheaply).
// ==========================================================

// Which inpainting backend the Studio tab should use.
enum class InpaintEngine {
    Auto,    // Heuristic: LaMa for clean bubble-shaped masks, Moebius for hard/complex ones
    LaMa,    // Fast single-pass FFC inpainting
    Moebius  // High-quality 30-step latent diffusion
};

#endif // CORE_PIPELINE_AI_TYPES_H
