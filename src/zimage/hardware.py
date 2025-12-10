from __future__ import annotations

import platform
import subprocess
import warnings
from typing import Literal, TypedDict, List, Optional

import torch

try:
    from .logger import get_logger
except ImportError:
    from logger import get_logger

logger = get_logger("zimage.hardware")

# -------------------------------
# Constants & Types
# -------------------------------

PrecisionId = Literal["full", "q8", "q4"]

MODEL_ID_MAP: dict[PrecisionId, str] = {
    "full": "Tongyi-MAI/Z-Image-Turbo",
    "q8":   "Disty0/Z-Image-Turbo-SDNQ-int8",
    "q4":   "Disty0/Z-Image-Turbo-SDNQ-uint4-svd-r32",
}

class ModelInfo(TypedDict):
    id: PrecisionId
    precision: PrecisionId
    hf_model_id: str
    available: bool
    recommended: bool

class ModelsResponse(TypedDict):
    device: str
    ram_gb: float | None
    vram_gb: float | None
    default_precision: str
    models: List[ModelInfo]

# -------------------------------
# Logging Helpers (Internal)
# -------------------------------

def _log_info(message: str):
    logger.info(message)

def _log_warn(message: str):
    logger.warning(message)

# -------------------------------
# Hardware Detection
# -------------------------------

def detect_device() -> str:
    if torch.backends.mps.is_available():
        return "mps"
    if torch.cuda.is_available():
        return "cuda"
    return "cpu"


def get_ram_gb() -> float | None:
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
        # Other systems not yet supported, return None
    except Exception:
        pass
    return None


def get_vram_gb() -> float | None:
    try:
        if torch.cuda.is_available():
            props = torch.cuda.get_device_properties(0)
            return props.total_memory / (1024 ** 3)
    except Exception:
        pass
    return None


def has_sdnq() -> bool:
    try:
        from sdnq import SDNQConfig  # noqa: F401
        return True
    except Exception:
        return False

# -------------------------------
# Logic: Available Models & Recommendations
# -------------------------------

_cached_models_response: ModelsResponse | None = None


def get_available_models() -> ModelsResponse:
    """
    Returns information about which model precisions are available and recommended
    for the current hardware.
    Structure:
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

    device = detect_device()
    ram_gb = get_ram_gb()
    vram_gb = get_vram_gb()
    sdnq_ok = has_sdnq()
    default_precision = "full" # Very likely to be overridden below

    # Initial: full is logically available.
    models: dict[PrecisionId, ModelInfo] = {
        "full": {
            "id": "full",
            "precision": "full",
            "hf_model_id": MODEL_ID_MAP["full"],
            "available": True,
            "recommended": True,
        },
        "q8": {
            "id": "q8",
            "precision": "q8",
            "hf_model_id": MODEL_ID_MAP["q8"],
            "available": False,
            "recommended": False,
        },
        "q4": {
            "id": "q4",
            "precision": "q4",
            "hf_model_id": MODEL_ID_MAP["q4"],
            "available": False,
            "recommended": False,
        },
    }

    # Quantization prerequisite: SDNQ must be installed
    if sdnq_ok:
        models["q8"]["available"] = True
        models["q4"]["available"] = True
        default_precision = "q4"  # If SDNQ is available, default to q4

    # ------- Adjust Logic by Device & Memory -------

    if device == "mps":
        # Mac / Apple Silicon: Check System RAM
        if ram_gb is None:
            # Unknown memory: conservative strategy, recommend q4 (if available), full not recommended
            models["full"]["recommended"] = False
            if sdnq_ok:
                models["q4"]["recommended"] = True
                default_precision = "q4"
        else:
            if ram_gb <= 24:
                # 8-24G Mac: full basically leads to OOM; q4 default
                models["full"]["available"] = False
                models["full"]["recommended"] = False
                if sdnq_ok:
                    models["q4"]["recommended"] = True
            elif ram_gb <= 32:
                # 24-32G Mac: full barely works but not recommended; q8 default
                models["full"]["recommended"] = False
                if sdnq_ok:
                    models["q8"]["recommended"] = True
                    default_precision = "q8"
            elif ram_gb <= 48:
                # >=32G to 48G: full & q8 both reasonable
                models["full"]["recommended"] = True
                if sdnq_ok:
                    models["q8"]["recommended"] = True
                    default_precision = "q8"
                # q4 left for "advanced/extreme compression" users, not actively recommended
            else:
                # >48G: full & q8 both reasonable
                models["full"]["recommended"] = True
                if sdnq_ok:
                    models["q8"]["recommended"] = True
                # q4 left for "advanced/extreme compression" users, not actively recommended

    elif device == "cuda":
        # CUDA: Check VRAM
        if vram_gb is None:
            # Unknown VRAM: conservative strategy, don't make full default
            models["full"]["recommended"] = False
            if sdnq_ok:
                models["q8"]["recommended"] = True
        else:
            if vram_gb < 8:
                # <8GB VRAM: full almost unusable, only quantized
                models["full"]["available"] = False
                models["full"]["recommended"] = False
                if sdnq_ok:
                    models["q8"]["available"] = True
                    models["q8"]["recommended"] = True
                    models["q4"]["available"] = True
                    default_precision = "q4"
            elif vram_gb < 16:
                # 8-16GB: full available but not recommended; q8 as main
                models["full"]["recommended"] = False
                if sdnq_ok:
                    models["q8"]["available"] = True
                    models["q8"]["recommended"] = True
                    models["q4"]["available"] = True
                    default_precision = "q8"
            else:
                # >=16GB: full & q8 both recommended
                models["full"]["recommended"] = True
                if sdnq_ok:
                    models["q8"]["available"] = True
                    models["q8"]["recommended"] = True
                default_precision = "full"
                # q4 still not default recommended

    else:  # CPU-only
        # CPU Scenario: Compute is bottleneck, memory also matters
        models["full"]["recommended"] = False  # full never recommended on CPU

        if ram_gb is None:
            # Unknown memory: conservative choice q8 as default (if available)
            if sdnq_ok:
                models["q8"]["recommended"] = True
                models["q4"]["available"] = True
                default_precision = "q4"
        else:
            if ram_gb < 8:
                # <8GB RAM: full unusable; memory too small, q4 is lifesaver
                models["full"]["available"] = False
                if sdnq_ok:
                    models["q4"]["recommended"] = True
                    default_precision = "q4"
            elif ram_gb < 16:
                # 8-16GB: forbid full; q8 as main
                models["full"]["available"] = False
                if sdnq_ok:
                    models["q8"]["recommended"] = True
                    default_precision = "q8"
            else:
                # >=16GB: q8 as main, q4 as alternative
                if sdnq_ok:
                    models["q8"]["recommended"] = True
                    default_precision = "q8"

    # Construct response: filter out available=False
    # Safety check: If no SDNQ, we MUST enable full precision regardless of RAM/VRAM,
    # otherwise the user has no models to run.
    if not sdnq_ok:
        models["full"]["available"] = True
        models["full"]["recommended"] = True
        default_precision = "full"

    result: ModelsResponse = {
        "device": device,
        "ram_gb": ram_gb,
        "vram_gb": vram_gb,
        "default_precision": default_precision,
        "models": []
    }

    for precision, hf_id in MODEL_ID_MAP.items():
        status = models.get(precision)
        if not status or not status["available"]:
            continue

        # Construct ModelInfo
        model_info: ModelInfo = {
            "id": precision,
            "precision": precision,
            "hf_model_id": hf_id,
            "available": status["available"],
            "recommended": status["recommended"]
        }

        result["models"].append(model_info)

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
            _log_info("Device is CPU -> Enabling attention slicing.")
            return True

        if device == "mps" and platform.system() == "Darwin":
            _log_info("Device is MPS -> Enabling attention slicing for stability.")
            return True

        if device == "cuda" and torch.cuda.is_available():
            # Get CUDA VRAM in bytes
            props = torch.cuda.get_device_properties(0)
            total_vram_gb = props.total_memory / (1024**3)

            _log_info(f"Detected GPU VRAM: {total_vram_gb:.1f} GB")

            if total_vram_gb < 12:
                _log_info("VRAM < 12GB -> Enabling attention slicing.")
                return True
            else:
                _log_info("VRAM >= 12GB -> Disabling attention slicing for performance.")
                return False

    except Exception as e:
        _log_warn(f"Failed to detect hardware specs ({e}), defaulting to attention slicing enabled.")
        return True

    # Default safe fallback
    return True
