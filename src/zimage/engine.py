from __future__ import annotations

import warnings

# Silence the noisy CUDA autocast warning on Mac
warnings.filterwarnings(
    "ignore",
    message="User provided device_type of 'cuda', but CUDA is not available",
    category=UserWarning,
)

import platform
import subprocess
from typing import Literal, TypedDict, List, Optional

import torch
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

# -------------------------------
# 模型精度枚举 & HF 模型映射
# -------------------------------

PrecisionId = Literal["full", "q8", "q4"]

MODEL_ID_MAP: dict[PrecisionId, str] = {
    "full": "Tongyi-MAI/Z-Image-Turbo",
    "q8":   "Disty0/Z-Image-Turbo-SDNQ-int8",
    "q4":   "Disty0/Z-Image-Turbo-SDNQ-uint4-svd-r32",
}

# -------------------------------
# 类型声明
# -------------------------------

class ModelInfo(TypedDict):
    id: PrecisionId
    hf_model_id: str
    available: bool
    recommended: bool

class ModelsResponse(TypedDict):
    device: str
    ram_gb: float | None
    vram_gb: float | None
    models: List[ModelInfo]

# -------------------------------
# 硬件检测工具
# -------------------------------

def _detect_device() -> str:
    if torch.backends.mps.is_available():
        return "mps"
    if torch.cuda.is_available():
        return "cuda"
    return "cpu"


def _get_ram_gb() -> float | None:
    try:
        system = platform.system()
        if system == "Darwin":
            # macOS: sysctl hw.memsize
            out = subprocess.check_output(["sysctl", "-n", "hw.memsize"]).strip()
            return int(out) / (1024 ** 3)
        elif system == "Linux":
            with open("/proc/meminfo") as f:
                for line in f:
                    if line.startswith("MemTotal:"):
                        kb = int(line.split()[1])
                        return kb / 1024 / 1024
        # 其它系统暂时不支持，返回 None
    except Exception:
        pass
    return None


def _get_vram_gb() -> float | None:
    try:
        if torch.cuda.is_available():
            props = torch.cuda.get_device_properties(0)
            return props.total_memory / (1024 ** 3)
    except Exception:
        pass
    return None


def _has_sdnq() -> bool:
    try:
        from sdnq import SDNQConfig  # noqa: F401
        return True
    except Exception:
        return False



# -------------------------------
# 主逻辑：返回可用模型 + 推荐
# -------------------------------

_cached_models_response: ModelsResponse | None = None


def get_available_models() -> ModelsResponse:
    """
    返回当前机器“可以用哪些精度”的信息。
    结构：
    {
      "device": "mps" | "cuda" | "cpu",
      "ram_gb": float | None,
      "vram_gb": float | None,
      "models": [
        { "id": "full", "hf_model_id": "...", "available": True, "recommended": True },
        ...
      ]
    }
    """
    global _cached_models_response
    if _cached_models_response is not None:
        return _cached_models_response

    device = _detect_device()
    ram_gb = _get_ram_gb()
    vram_gb = _get_vram_gb()
    sdnq_ok = _has_sdnq()

    # 初始：full 总是“逻辑上”可用，推荐先设 True，后面再按设备修正。
    models: dict[PrecisionId, ModelInfo] = {
        "full": {
            "id": "full",
            "hf_model_id": MODEL_ID_MAP["full"],
            "available": True,
            "recommended": True,
        },
        "q8": {
            "id": "q8",
            "hf_model_id": MODEL_ID_MAP["q8"],
            "available": False,
            "recommended": False,
        },
        "q4": {
            "id": "q4",
            "hf_model_id": MODEL_ID_MAP["q4"],
            "available": False,
            "recommended": False,
        },
    }

    # 量化模型前提：必须安装 SDNQ
    if sdnq_ok:
        models["q8"]["available"] = True
        models["q4"]["available"] = True

    # ------- 按设备 & 内存调整逻辑 -------

    if device == "mps":
        # Mac / Apple Silicon：按系统 RAM 做比较，保守一点
        if ram_gb is None:
            # 不知道内存大小：保守策略，推荐 q8（如果有），full 不推荐
            models["full"]["recommended"] = False
            if sdnq_ok:
                models["q8"]["recommended"] = True
        else:
            if ram_gb < 16:
                # 8～16G Mac：full 很容易爆，直接隐藏，强制量化
                models["full"]["available"] = False
                models["full"]["recommended"] = False
                if sdnq_ok:
                    models["q8"]["recommended"] = True
            elif ram_gb < 32:
                # 16～32G Mac：full 勉强可用但不推荐；q8 默认
                models["full"]["recommended"] = False
                if sdnq_ok:
                    models["q8"]["recommended"] = True
            else:
                # >=32G：full & q8 都算合理选择
                models["full"]["recommended"] = True
                if sdnq_ok:
                    models["q8"]["recommended"] = True
                # q4 永远留给“高级/极限压缩用户”，不主动推荐

    elif device == "cuda":
        # CUDA：按 VRAM 判断
        if vram_gb is None:
            # 不知道 VRAM：保守策略，不把 full 当默认
            models["full"]["recommended"] = False
            if sdnq_ok:
                models["q8"]["recommended"] = True
        else:
            if vram_gb < 8:
                # <8GB 显存：full 几乎可以视为不可用，只给量化
                models["full"]["available"] = False
                models["full"]["recommended"] = False
                if sdnq_ok:
                    models["q8"]["available"] = True
                    models["q8"]["recommended"] = True
                    models["q4"]["available"] = True
            elif vram_gb < 16:
                # 8～16GB：full 可用但不推荐；q8 当主力
                models["full"]["recommended"] = False
                if sdnq_ok:
                    models["q8"]["available"] = True
                    models["q8"]["recommended"] = True
                    models["q4"]["available"] = True
            else:
                # >=16GB：full & q8 都推荐
                models["full"]["recommended"] = True
                if sdnq_ok:
                    models["q8"]["available"] = True
                    models["q8"]["recommended"] = True
                # q4 依然不默认推荐

    else:  # CPU-only
        # 理论上 full 可以跑，但会非常慢，所以不推荐
        models["full"]["recommended"] = False
        if sdnq_ok:
            models["q8"]["available"] = True
            models["q8"]["recommended"] = True
            models["q4"]["available"] = True
            # 看你心情，可以把 q4 也标成 recommended

    # 构造响应：过滤掉 available=False 的
    result: ModelsResponse = {
        "device": device,
        "ram_gb": ram_gb,
        "vram_gb": vram_gb,
        "models": [
            m for m in models.values() if m["available"]
        ],
    }

    _cached_models_response = result
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
