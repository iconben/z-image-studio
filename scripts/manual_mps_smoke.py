"""Manual end-to-end smoke check on Apple Silicon (MPS) or CPU.

This is **not** a pytest test. It downloads real model weights (a few GB) and runs
a real generation, so it must never be part of the automated suite or of CI --
which is why it lives in ``scripts/`` rather than ``tests/`` and does all of its
work inside ``main()``.

Usage::

    python scripts/manual_mps_smoke.py

The resulting image is written to ``z_image_macos_test.png`` in the current
working directory.
"""

import torch
from diffusers import ZImagePipeline

# Prefer the lightweight 4-bit model to reduce VRAM/CPU RAM needs in manual checks
MODEL_ID = "Disty0/Z-Image-Turbo-SDNQ-uint4-svd-r32"

PROMPT = "夜晚的上海街头，霓虹灯，高对比度写实照片，中英双语招牌"

OUTPUT_NAME = "z_image_macos_test.png"


def _generate(device: str, dtype: torch.dtype) -> None:
    """Load the pipeline in ``dtype`` on ``device``, generate one image and save it.

    The pipeline is a local, so a failed attempt releases it -- and the memory it
    holds -- before :func:`main` retries in the other precision.
    """
    pipe = ZImagePipeline.from_pretrained(
        MODEL_ID,
        torch_dtype=dtype,
        low_cpu_mem_usage=False,
    )
    pipe.to(device)
    # An unsupported dtype shows up when an op runs, not when the pipeline is
    # loaded, so the caller has to guard this call as well.
    image = pipe(PROMPT, num_inference_steps=9).images[0]
    image.save(OUTPUT_NAME)


def main() -> None:
    """Run the smoke check, falling back from bfloat16 to float16 on failure."""
    device = "mps" if torch.backends.mps.is_available() else "cpu"

    # 先试 bfloat16，不行再换 float16
    failure: Exception | None = None
    for dtype in (torch.bfloat16, torch.float16):
        try:
            _generate(device, dtype)
        except Exception as exc:  # Report the failure instead of a bare traceback
            failure = exc
            print(f"WARNING: generation with {dtype} on {device} failed: {exc}")
            continue
        print(f"Wrote {OUTPUT_NAME} ({dtype} on {device})")
        return

    raise SystemExit(f"Smoke check failed on {device}: {failure}")


if __name__ == "__main__":
    main()
