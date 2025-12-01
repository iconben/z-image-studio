import warnings
import torch
from diffusers import ZImagePipeline

# Silence the noisy CUDA autocast warning on Mac
warnings.filterwarnings(
    "ignore",
    message="User provided device_type of 'cuda', but CUDA is not available. Disabling warnings.warn",
    category=UserWarning,
)

warnings.filterwarnings(
    "ignore",
    message="`torch_dtype` is deprecated! Use `dtype` instead!",
    category=UserWarning,
)

_cached_pipe = None

def load_pipeline(device: str = None) -> ZImagePipeline:
    global _cached_pipe
    if _cached_pipe is not None:
        return _cached_pipe

    if device is None:
        if torch.backends.mps.is_available():
            device = "mps"
        else:
            print("[warn] MPS not available, using CPU (slow).")
            device = "cpu"
    
    print(f"[info] using device: {device}")

    model_id = "Tongyi-MAI/Z-Image-Turbo"

    # Select optimal dtype based on device capabilities
    if device == "cpu":
        torch_dtype = torch.float32
    else:
        # CUDA and MPS (for this model) prefer bfloat16.
        # Note: float16 on MPS causes black images due to numerical instability with Z-Image-Turbo.
        torch_dtype = torch.bfloat16

    print(f"[info] try to load model with torch_dtype={torch_dtype} ...")

    pipe = ZImagePipeline.from_pretrained(
        model_id,
        torch_dtype=torch_dtype,   # ZImagePipeline still expects torch_dtype
        low_cpu_mem_usage=False,
    )
    pipe = pipe.to(device)

    # Memory Optimization: Enable attention slicing to prevent OOM/Swapping
    # This slices the attention computation into chunks, trading a tiny bit of 
    # speed for massive memory savings (which prevents disk swapping).
    print("[info] enabling attention slicing for lower memory usage")
    pipe.enable_attention_slicing()

    # Disable safety checker while debugging (it can output black images)
    if hasattr(pipe, "safety_checker") and pipe.safety_checker is not None:
        print("[info] disable safety_checker")
        pipe.safety_checker = None

    # Debug actual dtypes
    if hasattr(pipe, "unet"):
        print("[info] UNet dtype:", pipe.unet.dtype)
    if hasattr(pipe, "vae"):
        print("[info] VAE  dtype:", pipe.vae.dtype)
    if hasattr(pipe, "text_encoder"):
        print("[info] Text encoder dtype:", pipe.text_encoder.dtype)

    _cached_pipe = pipe
    return pipe

def generate_image(prompt: str, steps: int, width: int, height: int):
    pipe = load_pipeline()
    
    print(f"[info] generating image for prompt: {prompt!r}")
    print(
        f"[debug] steps={steps}, width={width}, "
        f"height={height}, guidance_scale=0.0"
    )

    image = pipe(
        prompt,
        num_inference_steps=steps,
        height=height,
        width=width,
        guidance_scale=0.0,  # Turbo model: CFG must be 0
    ).images[0]
    
    return image
