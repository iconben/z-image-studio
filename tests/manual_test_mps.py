import torch
from diffusers import ZImagePipeline

device = "mps" if torch.backends.mps.is_available() else "cpu"

# Prefer the lightweight 4-bit model to reduce VRAM/CPU RAM needs in manual checks
MODEL_ID = "Disty0/Z-Image-Turbo-SDNQ-uint4-svd-r32"

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

prompt = "夜晚的上海街头，霓虹灯，高对比度写实照片，中英双语招牌"
image = pipe(prompt, num_inference_steps=9).images[0]
image.save("z_image_macos_test.png")
