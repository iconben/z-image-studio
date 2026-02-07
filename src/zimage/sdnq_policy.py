from __future__ import annotations

import os


def basic_has_triton() -> bool:
    """
    Perform a lightweight Triton availability check.

    This is intentionally conservative and not a final authority:
    - False means Triton is not usable in this process.
    - True means Triton appears available, but SDNQ must still run its own
      deeper runtime probe to decide if compile mode is actually safe.
    """
    try:
        import torch

        # If Dynamo is globally disabled, torch.compile-based Triton usage is unavailable.
        if torch._dynamo.config.disable:  # pylint: disable=protected-access
            return False

        from torch.utils._triton import has_triton as torch_has_triton

        return bool(torch_has_triton())
    except Exception:
        return False


def apply_sdnq_compile_policy() -> None:
    """
    Apply process-level SDNQ compile policy before importing SDNQ.

    Policy:
    - Respect user explicit setting of SDNQ_USE_TORCH_COMPILE.
    - If basic Triton check is false, force eager fallback by setting
      SDNQ_USE_TORCH_COMPILE=0 to avoid noisy probe warnings.
    - If basic Triton check is true, do not force anything and let SDNQ's
      own runtime probe make the final decision.
    """
    if os.environ.get("SDNQ_USE_TORCH_COMPILE") is not None:
        return

    if not basic_has_triton():
        os.environ["SDNQ_USE_TORCH_COMPILE"] = "0"
