from __future__ import annotations

import warnings
import traceback

# Silence the noisy CUDA autocast warning on Mac
warnings.filterwarnings(
    "ignore",
    message="User provided device_type of 'cuda', but CUDA is not available",
    category=UserWarning,
)

import torch
from diffusers import ZImagePipeline
from sdnq.common import use_torch_compile as triton_is_available
from sdnq.loader import apply_sdnq_options_to_model
from safetensors.torch import load_file
from diffusers.loaders.peft import _SET_ADAPTER_SCALE_FN_MAPPING

# Import from hardware module
try:
    from .hardware import (
        PrecisionId,
        MODEL_ID_MAP,
        get_available_models, # Not used in engine directly but might be imported from engine by others (backward compat? No, I will update callers)
        should_enable_attention_slicing,
        get_ram_gb,
        detect_device,
    )
    from .paths import get_models_dir
except ImportError:
    from hardware import (
        PrecisionId,
        MODEL_ID_MAP,
        get_available_models, # Not used in engine directly but might be imported from engine by others (backward compat? No, I will update callers)
        should_enable_attention_slicing,
        get_ram_gb,
        detect_device,
    )
    from paths import get_models_dir

# ANSI escape codes for colors
GREEN = "\033[92m"
YELLOW = "\033[93m"
RESET = "\033[0m"

def log_info(message: str):
    print(f"{GREEN}INFO{RESET}: {message}")

def log_warn(message: str):
    print(f"{YELLOW}WARN{RESET}: {message}")

warnings.filterwarnings(
    "ignore",
    message="`torch_dtype` is deprecated! Use `dtype` instead!",
    category=FutureWarning,
)

_cached_pipe = None
_cached_precision = None

def load_pipeline(device: str = None, precision: PrecisionId = "q8") -> ZImagePipeline:
    global _cached_pipe, _cached_precision
    
    # Cache key uses precision directly now
    cache_key = precision

    if _cached_pipe is not None and _cached_precision == cache_key:
        return _cached_pipe
    
    # If we are switching models, unload the old one first to free memory
    if _cached_pipe is not None:
        log_info(f"Switching model. Unloading old model...")
        del _cached_pipe
        import gc
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        if torch.backends.mps.is_available():
             torch.mps.empty_cache()
        _cached_pipe = None

    if device is None:
        if torch.backends.mps.is_available():
            device = "mps"
        else:
            log_warn("MPS not available, using CPU (slow).")
            device = "cpu"
    
    log_info(f"using device: {device}")

    # Directly use MODEL_ID_MAP
    model_id = MODEL_ID_MAP[precision] # This will raise KeyError if precision is not valid, let it
    log_info(f"using model: {model_id} (precision={precision})")

    # Select optimal dtype based on device capabilities
    if device == "cpu":
        torch_dtype = torch.float32
    elif device == "mps":
        torch_dtype = torch.bfloat16
    elif device == "cuda":
        if torch.cuda.is_bf16_supported():
            log_info("CUDA device supports bfloat16 -> using bfloat16")
            torch_dtype = torch.bfloat16
        else:
            log_warn("CUDA device does NOT support bfloat16 -> falling back to float16")
            torch_dtype = torch.float16
    else:
        torch_dtype = torch.float32

    # Replaced subprocess call with get_ram_gb() from hardware module
    total_ram_gb = get_ram_gb()
    if total_ram_gb is None:
        # Fallback logic if detection fails, assume high ram? Or low?
        # Original code would crash if sysctl failed on Mac, or maybe returned 0.
        # Let's assume 0 or handle None.
        total_ram_gb = 0

    if model_id == "Tongyi-MAI/Z-Image-Turbo" and total_ram_gb >= 32:
        low_cpu_mem_usage=False
    else:
        low_cpu_mem_usage=True

    log_info(f"try to load model with torch_dtype={torch_dtype} ...")

    pipe = ZImagePipeline.from_pretrained(
        model_id,
        torch_dtype=torch_dtype,
        low_cpu_mem_usage=low_cpu_mem_usage,
        cache_dir=str(get_models_dir()),
    )
    pipe = pipe.to(device)
    
    # Compatibility shim for SD3LoraLoaderMixin which expects text_encoder_2 and 3
    if not hasattr(pipe, "text_encoder_2"):
        pipe.text_encoder_2 = None
    if not hasattr(pipe, "text_encoder_3"):
        pipe.text_encoder_3 = None

    # Monkey-patch peft scale mapping for ZImageTransformer2DModel
    if "ZImageTransformer2DModel" not in _SET_ADAPTER_SCALE_FN_MAPPING:
        log_info("Monkey-patching PEFT mapping for ZImageTransformer2DModel")
        _SET_ADAPTER_SCALE_FN_MAPPING["ZImageTransformer2DModel"] = lambda model_cls, weights: weights

    # Enable INT8 MatMul for AMD, Intel ARC and Nvidia GPUs:
    if triton_is_available and (torch.cuda.is_available() or torch.xpu.is_available()):
        pipe.transformer = apply_sdnq_options_to_model(pipe.transformer, use_quantized_matmul=True)
        pipe.text_encoder = apply_sdnq_options_to_model(pipe.text_encoder, use_quantized_matmul=True)
        pipe.transformer = torch.compile(pipe.transformer) 

    if device == "cuda":
        pipe.enable_model_cpu_offload()

    if should_enable_attention_slicing(device):
        pipe.enable_attention_slicing()
    else:
        pipe.disable_attention_slicing()

    if hasattr(pipe, "safety_checker") and pipe.safety_checker is not None:
        log_info("disable safety_checker")
        pipe.safety_checker = None

    _cached_pipe = pipe
    _cached_precision = cache_key
    return pipe

def generate_image(
    prompt: str,
    steps: int,
    width: int,
    height: int,
    seed: int = None,
    precision: str = "q4",
    loras: list[tuple[str, float]] = None,
):
    pipe = load_pipeline(precision=precision)
    
    log_info(f"generating image for prompt: {prompt!r}")
    
    if loras:
        log_info(f"using LoRAs: {loras}")

    # Removed: DEBUG print statement
    # print(
    #     f"DEBUG: steps={steps}, width={width}, "
    #     f"height={height}, guidance_scale=0.0, seed={seed}, precision={precision}, "
    #     f"loras={loras}"
    # )

    active_adapters = []
    adapter_weights = []

    if loras:
        try:
            for i, (path, strength) in enumerate(loras):
                adapter_name = f"lora_{i}"
                
                # Load raw state dict
                state_dict = load_file(path)
                
                # Remap keys: diffusion_model -> transformer
                new_state_dict = {}
                for key, value in state_dict.items():
                    if key.startswith("diffusion_model."):
                        new_key = key.replace("diffusion_model.", "transformer.")
                    else:
                        new_key = key
                    new_state_dict[new_key] = value
                
                pipe.load_lora_weights(new_state_dict, adapter_name=adapter_name)
                active_adapters.append(adapter_name)
                adapter_weights.append(strength)
            
            if active_adapters:
                pipe.set_adapters(active_adapters, adapter_weights=adapter_weights)

        except Exception as e:
            log_warn(f"Failed to load LoRA weights: {e}")
            traceback.print_exc()
            # Clean up any loaded adapters if possible, though finally block should handle it
            raise e

    generator = None
    if seed is not None:
        generator = torch.Generator(device=pipe.device).manual_seed(seed)

    # Prepare kwargs for generation
    gen_kwargs = {
        "prompt": prompt,
        "num_inference_steps": steps,
        "height": height,
        "width": width,
        "guidance_scale": 0.0, 
        "generator": generator,
    }

    try:
        with torch.inference_mode():
            image = pipe(**gen_kwargs).images[0]
        
        return image
    finally:
        if loras:
            try:
                log_info("unloading LoRA weights")
                pipe.unload_lora_weights()
            except Exception as e:
                log_warn(f"Failed to unload LoRA weights: {e}")

        import gc
        gc.collect()
        if torch.backends.mps.is_available():
            torch.mps.empty_cache()
