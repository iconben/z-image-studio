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


def main() -> None:
    device = "mps" if torch.backends.mps.is_available() else "cpu"

    # 先试 bfloat16，不行再换 float16
    dtype = torch.bfloat16
    try:
        pipe = ZImagePipeline.from_pretrained(
            MODEL_ID,
            torch_dtype=dtype,
            low_cpu_mem_usage=False,
        )
        pipe.to(device)
    except Exception as e:
        print("bfloat16 可能不被 MPS 支持，改用 float16:", e)
        dtype = torch.float16
        pipe = ZImagePipeline.from_pretrained(
            MODEL_ID,
            torch_dtype=dtype,
            low_cpu_mem_usage=False,
        )
        pipe.to(device)

    image = pipe(PROMPT, num_inference_steps=9).images[0]
    image.save("z_image_macos_test.png")
    print("Wrote z_image_macos_test.png")


if __name__ == "__main__":
    main()
