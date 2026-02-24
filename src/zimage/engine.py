from __future__ import annotations

import os
import sys
import warnings
import traceback

# Import from paths module for config access
try:
    from .paths import load_config
except ImportError:
    from paths import load_config

# Silence the noisy CUDA autocast warning on Mac
warnings.filterwarnings(
    "ignore",
    message="User provided device_type of 'cuda', but CUDA is not available",
    category=UserWarning,
)

import torch
from diffusers import ZImagePipeline

try:
    from .sdnq_policy import apply_sdnq_compile_policy
except ImportError:
    from sdnq_policy import apply_sdnq_compile_policy

# Basic Triton detection is a fast precheck only; SDNQ runtime probe remains
# the final authority when Triton appears available.
apply_sdnq_compile_policy()

from sdnq.common import use_torch_compile as triton_is_available
from sdnq.loader import apply_sdnq_options_to_model
from safetensors.torch import load_file
from diffusers.loaders.peft import _SET_ADAPTER_SCALE_FN_MAPPING

# Import from hardware module
try:
    from .hardware import (
        PrecisionId,
        MODEL_ID_MAP,
        get_available_models,
        should_enable_attention_slicing,
        get_ram_gb,
        detect_device,
        is_xpu_available,
    )
    from .logger import get_logger
except ImportError:
    from hardware import (
        PrecisionId,
        MODEL_ID_MAP,
        get_available_models,
        should_enable_attention_slicing,
        get_ram_gb,
        detect_device,
        is_xpu_available,
    )
    from logger import get_logger

logger = get_logger("zimage.engine")

def log_info(message: str):
    logger.info(message)

def log_warn(message: str):
    logger.warning(message)


def _empty_xpu_cache() -> None:
    xpu = getattr(torch, "xpu", None)
    if xpu is not None and hasattr(xpu, "empty_cache"):
        xpu.empty_cache()


def _is_xpu_bf16_supported() -> bool:
    xpu = getattr(torch, "xpu", None)
    if xpu is None or not hasattr(xpu, "is_bf16_supported"):
        return False
    try:
        return bool(xpu.is_bf16_supported())
    except Exception as e:
        log_warn(f"Failed to probe XPU bfloat16 support: {e}")
        return False

# Environment variable to force-enable torch.compile (use at your own risk)
_TORCH_COMPILE_ENV_VAR = "ZIMAGE_ENABLE_TORCH_COMPILE"

def is_torch_compile_safe() -> bool:
    """
    Determine if torch.compile is safe to use for the current environment.

    Returns True if torch.compile is known to be stable, False otherwise.
    This can be overridden by setting ZIMAGE_ENABLE_TORCH_COMPILE=1 via
    environment variable or config file (~/.z-image-studio/config.json).

    The safety check considers:
    - Python version (3.12+ has known torch.compile issues with Z-Image models)
    - ROCm/AMD GPUs (experimentally supported, disabled by default)
    - Future: PyTorch version (when 2.6+ potentially stabilizes 3.12 support)

    Returns:
        bool: True if torch.compile is considered safe, False otherwise
    """
    # User override - opt-in to experimental/unsafe behavior
    # Priority: environment variable > config file
    if os.getenv(_TORCH_COMPILE_ENV_VAR, "") == "1":
        log_warn(f"{_TORCH_COMPILE_ENV_VAR}=1: User has forced torch.compile enabled (via env)")
        return True

    # Check config file
    cfg = load_config()
    cfg_value = cfg.get(_TORCH_COMPILE_ENV_VAR) if isinstance(cfg, dict) else None
    if cfg_value:
        if str(cfg_value) == "1" or cfg_value is True:
            log_warn(f"{_TORCH_COMPILE_ENV_VAR}=1: User has forced torch.compile enabled (via config)")
            return True

    # Python 3.12+ has known compatibility issues with torch.compile on Z-Image models
    # See: https://github.com/anthropics/z-image-studio/issues/49
    if sys.version_info >= (3, 12):
        return False
        
    # ROCm: Disable torch.compile by default as it is experimental on AMD
    if detect_device() == "rocm":
        return False

    # TODO: Add PyTorch version check when 2.6+ is released
    # Future: if torch.__version__ >= (2, 6) and sys.version_info >= (3, 12):
    #             return True

    # Default: safe for Python < 3.12
    return True

warnings.filterwarnings(
    "ignore",
    message="`torch_dtype` is deprecated! Use `dtype` instead!",
    category=FutureWarning,
)

_cached_pipe = None
_cached_precision = None
_cached_original_transformer = None  # Store uncompiled transformer for fallback
_is_using_compiled_transformer = False  # Track if transformer is compiled

def load_pipeline(device: str = None, precision: PrecisionId = "q8") -> ZImagePipeline:
    global _cached_pipe, _cached_precision, _cached_original_transformer, _is_using_compiled_transformer
    
    # Cache key uses precision directly now
    cache_key = precision

    if _cached_pipe is not None and _cached_precision == cache_key:
        return _cached_pipe

    if device is None:
        device = detect_device()
    log_info(f"using device: {device}")
    
    # If we are switching models, unload the old one first to free memory
    if _cached_pipe is not None:
        log_info(f"Switching model. Unloading old model...")
        del _cached_pipe
        import gc
        gc.collect()
        if (device == "cuda" or device == "rocm") and torch.cuda.is_available():
            torch.cuda.empty_cache()
        if device == "mps" and torch.backends.mps.is_available():
             torch.mps.empty_cache()
        if device == "xpu" and is_xpu_available():
            _empty_xpu_cache()
        _cached_pipe = None

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
    elif device == "rocm":
        # ROCm often supports float16. bfloat16 depends on newer cards (MI200+).
        if torch.cuda.is_available() and torch.cuda.is_bf16_supported():
             log_info("ROCm device supports bfloat16 -> using bfloat16")
             torch_dtype = torch.bfloat16
        else:
             log_info("ROCm device -> using float16")
             torch_dtype = torch.float16
    elif device == "xpu":
        if _is_xpu_bf16_supported():
            log_info("XPU device supports bfloat16 -> using bfloat16")
            torch_dtype = torch.bfloat16
        else:
            log_info("XPU device -> using float16")
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
    )
    
    # PyTorch ROCm builds use "cuda" as the device type
    torch_device = "cuda" if device == "rocm" else device
    pipe = pipe.to(torch_device)
    
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
    # Note: torch.compile is only applied when deemed safe for the current environment
    _is_using_compiled_transformer = False
    # Explicitly exclude ROCm for now as it may be unstable with SDNQ/Triton kernels
    if triton_is_available and (device == "cuda" or device == "xpu"):
        pipe.transformer = apply_sdnq_options_to_model(pipe.transformer, use_quantized_matmul=True)
        pipe.text_encoder = apply_sdnq_options_to_model(pipe.text_encoder, use_quantized_matmul=True)

        # Store original uncompiled transformer for potential fallback
        _cached_original_transformer = pipe.transformer

        # Apply torch.compile only if safe for the current environment
        if is_torch_compile_safe():
            try:
                pipe.transformer = torch.compile(pipe.transformer)
                _is_using_compiled_transformer = True
                log_info("torch.compile enabled for transformer")
            except Exception as e:
                log_warn(f"torch.compile failed during setup: {e}")
                _is_using_compiled_transformer = False
        else:
            log_info(
                f"torch.compile disabled for this environment. "
                f"Set {_TORCH_COMPILE_ENV_VAR}=1 to force enable (experimental)."
            ) 

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
    global _is_using_compiled_transformer
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
    # Store LoRA data for potential torch.compile fallback
    lora_data = []  # List of (adapter_name, remapped_state_dict, strength) tuples

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

                # Store for potential fallback
                lora_data.append((adapter_name, new_state_dict, strength))

                pipe.transformer.load_lora_adapter(
                    new_state_dict,
                    adapter_name=adapter_name,
                    prefix="transformer",
                )
                active_adapters.append(adapter_name)
                adapter_weights.append(strength)

            if active_adapters:
                pipe.transformer.set_adapters(active_adapters, weights=adapter_weights)

        except Exception as e:
            log_warn(f"Failed to load LoRA weights: {e}")
            traceback.print_exc()
            # Clean up any loaded adapters if possible, though finally block should handle it
            raise e
    log_info(
        f"DEBUG: steps={steps}, width={width}, "
        f"height={height}, guidance_scale=0.0, seed={seed}, precision={precision}"
    )

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

    had_error = False
    try:
        with torch.inference_mode():
            image = pipe(**gen_kwargs).images[0]
    except RuntimeError as e:
        had_error = True
        # Check if this is a torch.compile-related error that we can recover from
        error_msg = str(e)
        is_compile_error = (
            "shape of the mask" in error_msg.lower() or
            "pow_by_natural" in error_msg.lower() or
            "sympy" in error_msg.lower() or
            any(x in error_msg for x in ["indexed tensor", "does not match"])
        )

        if is_compile_error and _is_using_compiled_transformer and _cached_original_transformer is not None:
            # Fall back to uncompiled transformer
            log_warn("torch.compile failed during inference, falling back to uncompiled transformer")
            log_warn(f"Error: {error_msg}")
            pipe.transformer = _cached_original_transformer
            _is_using_compiled_transformer = False

            # Reapply LoRAs to the fallback transformer if they were loaded
            if lora_data:
                log_warn("Reapplying LoRA adapters to fallback transformer")
                fallback_adapters = []
                fallback_weights = []
                for adapter_name, state_dict, strength in lora_data:
                    pipe.transformer.load_lora_adapter(
                        state_dict,
                        adapter_name=adapter_name,
                        prefix="transformer",
                    )
                    fallback_adapters.append(adapter_name)
                    fallback_weights.append(strength)

                if fallback_adapters:
                    pipe.transformer.set_adapters(fallback_adapters, weights=fallback_weights)

            # Retry generation with uncompiled model
            with torch.inference_mode():
                image = pipe(**gen_kwargs).images[0]
        else:
            # Re-raise if not a recoverable compile error
            raise
    finally:
        if loras:
            try:
                log_info("unloading LoRA weights")
                pipe.transformer.unload_lora()
            except Exception as e:
                log_warn(f"Failed to unload LoRA weights: {e}")

        import gc
        gc.collect()
        if torch.backends.mps.is_available():
            torch.mps.empty_cache()
        if is_xpu_available():
            _empty_xpu_cache()
        # Clear CUDA cache on error to free GPU memory for next request
        if had_error and torch.cuda.is_available():
            log_warn("Clearing CUDA cache after error")
            torch.cuda.empty_cache()

    return image

def cleanup_memory():
    import gc
    gc.collect()
    if torch.backends.mps.is_available():
        torch.mps.empty_cache()
    if is_xpu_available():
        _empty_xpu_cache()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
