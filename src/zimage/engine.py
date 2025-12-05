import warnings

# Silence the noisy CUDA autocast warning on Mac
warnings.filterwarnings(
    "ignore",
    message="User provided device_type of 'cuda', but CUDA is not available",
    category=UserWarning,
)

import torch
import subprocess
import platform
from diffusers import ZImagePipeline
from sdnq import SDNQConfig
from sdnq.common import use_torch_compile as triton_is_available
from sdnq.loader import apply_sdnq_options_to_model

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

# Model Definitions
MODEL_DEFINITIONS = [
    {
        "id": "turbo-full",
        "precision": "full",
        "tasks": ["generate"],
        "hf_id": "Tongyi-MAI/Z-Image-Turbo",
    },
    {
        "id": "turbo-q8",
        "precision": "q8",
        "tasks": ["generate"],
        "hf_id": "Disty0/Z-Image-Turbo-SDNQ-int8",
    },
    {
        "id": "turbo-q4",
        "precision": "q4",
        "tasks": ["generate"],
        "hf_id": "Disty0/Z-Image-Turbo-SDNQ-uint4-svd-r32",
    },
]

_cached_available_models = None
try:
    from sdnq import SDNQConfig # Import to check for availability
    _sdnq_available = True
except ImportError:
    _sdnq_available = False

def get_available_models() -> dict:
    """
    Returns a categorized dictionary of available models with hardware-based recommendations.
    Format: {"generate": [...], "edit": [...]}
    """
    global _cached_available_models
    if _cached_available_models:
        log_info("Using cached available models.")
        return _cached_available_models

    # 1. Detect available RAM/VRAM
    total_ram_gb = 0
    try:
        if platform.system() == "Darwin":
            cmd_out = subprocess.check_output(["sysctl", "-n", "hw.memsize"]).strip()
            total_ram_gb = int(cmd_out) / (1024**3)
        elif platform.system() == "Linux":
             with open('/proc/meminfo', 'r') as f:
                 for line in f:
                     if 'MemTotal' in line:
                         kb = int(line.split()[1])
                         total_ram_gb = kb / (1024**2)
                         break
    except Exception:
        pass
    
    if torch.cuda.is_available():
         try:
            props = torch.cuda.get_device_properties(0)
            total_ram_gb = props.total_memory / (1024**3)
         except:
             pass

    # 2. Determine recommended precision
    recommended_precision = "q8" 
    if total_ram_gb > 0:
        if total_ram_gb < 8:
            recommended_precision = "q4"
        elif total_ram_gb < 16:
            recommended_precision = "q8"
        else:
            recommended_precision = "full"

    # 3. Build and categorize list
    result = {"generate": [], "edit": []}
    
    for m in MODEL_DEFINITIONS:
        # Filter by SDNQ availability
        if m["precision"] != "full" and not _sdnq_available:
            continue
            
        model_info = m.copy()
        model_info["recommended"] = (m["precision"] == recommended_precision)
        
        # Add to task-specific lists
        for task in m["tasks"]:
            if task not in result:
                result[task] = []
            result[task].append(model_info)
            
    _cached_available_models = result
    return result

def should_enable_attention_slicing(device: str) -> bool:
    """
    Determine if attention slicing should be enabled based on hardware specs.
    - MPS (Mac): Enable if RAM < 32 GB.
    - CUDA: Enable if VRAM < 12 GB.
    - CPU: Always enable.
    """
    try:
        if device == "cpu":
            log_info("Device is CPU -> Enabling attention slicing.")
            return True
            
        if device == "mps" and platform.system() == "Darwin":
            log_info("Device is MPS -> Enabling attention slicing for stability.")
            return True

        if device == "cuda" and torch.cuda.is_available():
            # Get CUDA VRAM in bytes
            props = torch.cuda.get_device_properties(0)
            total_vram_gb = props.total_memory / (1024**3)
            
            log_info(f"Detected GPU VRAM: {total_vram_gb:.1f} GB")
            
            if total_vram_gb < 12:
                log_info("VRAM < 12GB -> Enabling attention slicing.")
                return True
            else:
                log_info("VRAM >= 12GB -> Disabling attention slicing for performance.")
                return False

    except Exception as e:
        log_warn(f"Failed to detect hardware specs ({e}), defaulting to attention slicing enabled.")
        return True

    # Default safe fallback
    return True

def load_pipeline(device: str = None, precision: str = "q8") -> ZImagePipeline:
    global _cached_pipe, _cached_precision
    
    # Look up model definition for "generate" task
    model_def = next((m for m in MODEL_DEFINITIONS if m["precision"] == precision and "generate" in m["tasks"]), None)
    
    if not model_def:
        log_warn(f"Unknown precision '{precision}' for generation, falling back to 'q8'")
        precision = "q8"
        model_def = next((m for m in MODEL_DEFINITIONS if m["precision"] == "q8" and "generate" in m["tasks"]), None)
    
    model_id = model_def["hf_id"]
    # Cache key uses model_id to be specific
    cache_key = model_id

    if _cached_pipe is not None and _cached_precision == cache_key:
        return _cached_pipe
    
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

    cmd_out = subprocess.check_output(["sysctl", "-n", "hw.memsize"]).strip()
    total_ram_bytes = int(cmd_out)
    total_ram_gb = total_ram_bytes / (1024**3)

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
    pipe = pipe.to(device)

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
    precision: str = "int8",
):
    pipe = load_pipeline(precision=precision)
    
    log_info(f"generating image for prompt: {prompt!r}")
    print(
        f"DEBUG: steps={steps}, width={width}, "
        f"height={height}, guidance_scale=0.0, seed={seed}, precision={precision}"
    )

    generator = None
    if seed is not None:
        generator = torch.Generator(device=pipe.device).manual_seed(seed)

    try:
        with torch.inference_mode():
            image = pipe(
                prompt,
                num_inference_steps=steps,
                height=height,
                width=width,
                guidance_scale=0.0, 
                generator=generator,
            ).images[0]
        
        return image
    finally:
        import gc
        gc.collect()
        if torch.backends.mps.is_available():
            torch.mps.empty_cache()
