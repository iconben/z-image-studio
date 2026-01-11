# ROCm (AMD GPU) Support Plan

## Goals
- Make AMD/ROCm support explicit and robust on Linux.
- Avoid CUDA-only optimizations that may break on ROCm.
- Provide version-agnostic installation/verification guidance and compatibility notes.

## Scope
- Device detection and reporting in backend.
- Safe defaults for dtype, attention slicing, and memory/offload behavior.
- Optional UI labels for ROCm.
- Documentation updates (README + troubleshooting).

## Plan
1) Research and confirm ROCm detection strategy
   - Use torch.version.hip to detect ROCm.
   - Validate that torch.cuda.is_available() is true on ROCm builds.

2) Add explicit ROCm device detection
   - Update detect_device() to return "rocm" when torch.version.hip is set.
   - Keep CUDA/MPS/CPU order but make ROCm distinct from CUDA.

3) Update hardware heuristics for ROCm
   - Treat "rocm" like "cuda" for VRAM checks in get_vram_gb().
   - Extend attention slicing logic to include ROCm VRAM thresholds.

4) Guard CUDA-only optimizations
   - Gate torch.compile + SDNQ quantized matmul to NVIDIA-only unless ROCm is known good.
   - Gate enable_model_cpu_offload() to NVIDIA-only unless ROCm is confirmed.
   - Add log warnings when skipping these paths on ROCm.

5) Update UI device labels (optional)
   - Add model_desc_*_rocm strings in static i18n JSON files.
   - Ensure fallback labels remain correct if not present.

6) Documentation
   - Expand README with version-agnostic ROCm install/verify guidance and links.
   - Add a short compatibility matrix by ROCm major/minor (best-effort, user-reported).
   - Add a troubleshooting section (common ROCm pitfalls + diagnostics).

7) Validation
   - Smoke test on ROCm environment (or ask a user to confirm).
   - Confirm device reporting and model selection behavior.

## Risks / Open Questions
- ROCm support varies by GPU architecture, kernel version, and ROCm version.
- torch.compile stability on ROCm depends on Triton/Inductor versions.
- Some diffusers kernels may not be ROCm-friendly yet.
- Driver/runtime/PyTorch version skew is the most common source of issues.

## Deliverables
- Code changes in hardware and engine modules.
- Updated README and any ROCm troubleshooting notes.
- Optional i18n label updates for ROCm device display.
