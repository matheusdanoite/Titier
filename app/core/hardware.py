"""
Titier - Hardware Detection & Optimization Module
Detects system hardware and configures llama.cpp parameters dynamically.
"""
import os
import platform
import subprocess
import multiprocessing
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Tuple
from pathlib import Path

# Lazy import psutil
_psutil = None

def _get_psutil():
    global _psutil
    if _psutil is None:
        try:
            import psutil
            _psutil = psutil
        except ImportError:
            print("[Hardware] Warning: psutil not installed, using fallback detection")
            _psutil = False
    return _psutil


# Platform detection
PLATFORM = platform.system()
IS_MACOS = PLATFORM == "Darwin"
IS_WINDOWS = PLATFORM == "Windows"
IS_LINUX = PLATFORM == "Linux"


class HardwareTier(Enum):
    """Hardware capability tiers."""
    LOW = "low"        # <8GB RAM, no dedicated GPU
    MEDIUM = "medium"  # 8-16GB RAM or 4-8GB VRAM
    HIGH = "high"      # 16-32GB RAM or 8-16GB VRAM
    ULTRA = "ultra"    # 32GB+ RAM or 16GB+ VRAM


@dataclass
class HardwareProfile:
    """Complete hardware profile with optimized llama.cpp parameters."""
    tier: HardwareTier
    
    # Detected Hardware
    ram_total_gb: float
    ram_available_gb: float
    vram_total_gb: float
    vram_available_gb: float
    cpu_cores_physical: int
    cpu_cores_logical: int
    
    # Context & Batching
    n_ctx: int
    n_batch: int
    max_tokens_default: int
    
    # Threading
    n_threads: int
    n_threads_batch: int
    
    # Memory Management
    use_mmap: bool
    use_mlock: bool
    
    # GPU Offloading
    n_gpu_layers: int  # -1=all, 0=none, N=partial
    offload_kqv: bool
    
    # KV Cache Optimization (Q8_0, Q4_0, or None for F16)
    type_k: Optional[str]
    type_v: Optional[str]
    
    # Advanced Features
    flash_attn: bool
    mul_mat_q: bool
    
    # Extended Context (optional)
    rope_freq_base: Optional[float] = None
    rope_freq_scale: Optional[float] = None
    
    # RAG & Indexing (Words per chunk)
    recommended_chunk_size: int = 150
    recommended_chunk_overlap: int = 30
    
    # Metadata
    backend: str = "cpu"
    gpu_name: Optional[str] = None


# ============================================================================
# Hardware Detection Functions
# ============================================================================

def get_system_memory() -> Tuple[float, float]:
    """Returns (total_gb, available_gb) of system RAM."""
    psutil = _get_psutil()
    if psutil:
        mem = psutil.virtual_memory()
        return (mem.total / (1024**3), mem.available / (1024**3))
    
    # Fallback for systems without psutil
    if IS_MACOS:
        try:
            result = subprocess.run(
                ['sysctl', '-n', 'hw.memsize'],
                capture_output=True, text=True, timeout=5
            )
            total_bytes = int(result.stdout.strip())
            return (total_bytes / (1024**3), total_bytes * 0.5 / (1024**3))
        except:
            pass
    
    return (8.0, 4.0)  # Conservative fallback


def get_gpu_vram() -> Tuple[float, float, str, Optional[str]]:
    """
    Returns (total_vram_gb, available_vram_gb, backend, gpu_name).
    Backend is 'metal', 'cuda', or 'cpu'.
    """
    if IS_MACOS:
        return _get_metal_vram()
    elif IS_WINDOWS or IS_LINUX:
        return _get_cuda_vram()
    return (0.0, 0.0, "cpu", None)


def _get_metal_vram() -> Tuple[float, float, str, Optional[str]]:
    """Get VRAM for Apple Silicon (unified memory)."""
    try:
        # Check if Metal is available via llama-cpp
        try:
            from llama_cpp import llama_supports_gpu_offload
            if not llama_supports_gpu_offload():
                return (0.0, 0.0, "cpu", None)
        except ImportError:
            pass
        
        # Get total memory (unified memory on Apple Silicon)
        result = subprocess.run(
            ['sysctl', '-n', 'hw.memsize'],
            capture_output=True, text=True, timeout=5
        )
        total_bytes = int(result.stdout.strip())
        total_gb = total_bytes / (1024**3)
        
        # Apple Silicon can use ~75% of RAM for GPU, assume 50% available
        vram_total = total_gb * 0.75
        vram_available = total_gb * 0.5
        
        # Try to get chip name
        chip_name = None
        try:
            result = subprocess.run(
                ['sysctl', '-n', 'machdep.cpu.brand_string'],
                capture_output=True, text=True, timeout=5
            )
            chip_name = result.stdout.strip()
        except:
            chip_name = "Apple Silicon"
        
        return (vram_total, vram_available, "metal", chip_name)
    except Exception as e:
        print(f"[Hardware] Metal detection failed: {e}")
        return (0.0, 0.0, "cpu", None)


def _get_cuda_vram() -> Tuple[float, float, str, Optional[str]]:
    """Get VRAM for NVIDIA GPUs via nvidia-smi."""
    try:
        result = subprocess.run(
            ['nvidia-smi', '--query-gpu=memory.total,memory.free,name', 
             '--format=csv,nounits,noheader'],
            capture_output=True, text=True, timeout=10
        )
        
        if result.returncode != 0:
            return (0.0, 0.0, "cpu", None)
        
        lines = result.stdout.strip().split('\n')
        if not lines:
            return (0.0, 0.0, "cpu", None)
        
        # Use first GPU
        parts = lines[0].split(',')
        total_mb = int(parts[0].strip())
        free_mb = int(parts[1].strip())
        gpu_name = parts[2].strip() if len(parts) > 2 else "NVIDIA GPU"
        
        return (total_mb / 1024, free_mb / 1024, "cuda", gpu_name)
    except FileNotFoundError:
        # nvidia-smi not found
        return (0.0, 0.0, "cpu", None)
    except Exception as e:
        print(f"[Hardware] CUDA detection failed: {e}")
        return (0.0, 0.0, "cpu", None)


def get_cpu_info() -> Tuple[int, int]:
    """Returns (physical_cores, logical_cores)."""
    psutil = _get_psutil()
    if psutil:
        physical = psutil.cpu_count(logical=False) or 4
        logical = psutil.cpu_count(logical=True) or 4
        return (physical, logical)
    
    logical = multiprocessing.cpu_count()
    # Estimate physical cores (assume hyperthreading divides by 2)
    physical = max(1, logical // 2)
    return (physical, logical)


def check_flash_attention_support() -> bool:
    """Check if Flash Attention is available in llama-cpp-python."""
    try:
        from llama_cpp import Llama
        # Flash attention is available if compiled with GGML_USE_FLASH_ATTN
        # We can't easily check this, so we assume it's available on modern builds
        # and let llama.cpp handle the fallback
        return True
    except ImportError:
        return False


# ============================================================================
# Model Size Estimation
# ============================================================================

def estimate_model_size_gb(model_path: str) -> float:
    """
    Estimate model size from filename or file size.
    Returns size in GB.
    """
    path = Path(model_path)
    
    # Try to get actual file size
    if path.exists():
        return path.stat().st_size / (1024**3)
    
    # Estimate from filename pattern
    name = path.name.lower()
    
    # Common patterns: "7b", "13b", "70b" etc.
    size_patterns = [
        ("70b", 40.0), ("65b", 37.0), ("34b", 20.0),
        ("33b", 19.0), ("30b", 18.0), ("13b", 7.5),
        ("7b", 4.0), ("3b", 2.0), ("1b", 1.0),
    ]
    
    for pattern, size in size_patterns:
        if pattern in name:
            # Adjust for quantization
            if "q4" in name or "q4_k" in name:
                return size * 0.5
            elif "q5" in name or "q5_k" in name:
                return size * 0.6
            elif "q8" in name:
                return size * 0.8
            return size
    
    return 4.0  # Default assumption: 7B Q4


def estimate_model_layers(model_path: str) -> int:
    """Estimate number of layers from model name."""
    name = Path(model_path).name.lower()
    
    layer_estimates = {
        "70b": 80, "65b": 80, "34b": 60, "33b": 60,
        "30b": 60, "13b": 40, "7b": 32, "3b": 28, "1b": 22,
    }
    
    for pattern, layers in layer_estimates.items():
        if pattern in name:
            return layers
    
    return 32  # Default


# ============================================================================
# Optimal Parameter Calculation
# ============================================================================

def calculate_optimal_gpu_layers(
    model_size_gb: float,
    vram_available_gb: float,
    total_layers: int = 32
) -> int:
    """
    Calculate how many layers can fit in VRAM.
    Returns -1 for all layers, 0 for CPU-only, or N for partial offload.
    """
    # Reserve memory for KV cache and overhead
    reserved_gb = 0.5 + (total_layers * 0.01)  # ~10MB per layer overhead
    usable_vram = vram_available_gb - reserved_gb
    
    if usable_vram >= model_size_gb:
        return -1  # All layers fit in GPU
    
    if usable_vram <= 0.5:
        return 0  # Not enough VRAM, use CPU
    
    # Calculate partial offload
    ratio = usable_vram / model_size_gb
    gpu_layers = int(total_layers * ratio)
    
    return max(1, gpu_layers)  # At least 1 layer on GPU if possible


def calculate_optimal_n_ctx(
    vram_available_gb: float,
    ram_available_gb: float,
    model_size_gb: float,
    n_gpu_layers: int
) -> int:
    """
    Calculate optimal context window based on available memory.
    """
    # Memory available for KV cache
    # Reserved memory for system and overhead:
    # 0.5 GB for base KV overhead + dynamic reservation per model size
    reserved_gb = 0.5 + (model_size_gb * 0.1) # Reserver 10% of model size for KV overhead
    
    if n_gpu_layers == -1:
        # Full GPU - use VRAM for KV cache
        available_for_ctx = max(0, vram_available_gb - model_size_gb - reserved_gb)
    elif n_gpu_layers == 0:
        # Full CPU - use RAM for KV cache
        available_for_ctx = max(0, ram_available_gb - model_size_gb - 1.5) # Reduced from 2.0 to 1.5
    else:
        # Partial offload - be conservative but reasonable
        available_for_ctx = max(0, min(vram_available_gb, ram_available_gb) - model_size_gb - reserved_gb)
    
    # Approximate: 1GB ≈ 8K context for 7B/8B model (F16/Q8 KV Cache)
    # If using quantized KV cache (Q8/Q4), this would be even higher, 
    # but we stick to a safe 8K per GB estimate.
    estimated_ctx = int(available_for_ctx * 8192)
    
    # Clamp to reasonable values - Recommend 4096 as modern minimum
    ctx_options = [4096, 8192, 16384, 32768, 65536, 131072]
    
    for ctx in reversed(ctx_options):
        if estimated_ctx >= ctx:
            return ctx
    
    return 4096  # Increased from 2048 to 4096 as practical minimum for RAG


# ============================================================================
# Profile Detection
# ============================================================================

def detect_hardware_profile(model_path: Optional[str] = None) -> HardwareProfile:
    """
    Detect hardware and create optimized profile.
    If model_path is provided, optimizes parameters for that specific model.
    """
    # Gather hardware info
    ram_total, ram_available = get_system_memory()
    vram_total, vram_available, backend, gpu_name = get_gpu_vram()
    cpu_physical, cpu_logical = get_cpu_info()
    
    # Model-specific calculations
    model_size_gb = estimate_model_size_gb(model_path) if model_path else 4.0
    model_layers = estimate_model_layers(model_path) if model_path else 32
    
    # Calculate GPU layers
    if backend == "cpu":
        n_gpu_layers = 0
    else:
        n_gpu_layers = calculate_optimal_gpu_layers(
            model_size_gb, vram_available, model_layers
        )
    
    # Determine tier
    tier = _determine_tier(ram_total, vram_total)
    
    # Calculate optimal n_ctx
    n_ctx = calculate_optimal_n_ctx(
        vram_available, ram_available, model_size_gb, n_gpu_layers
    )
    
    # Build profile based on tier
    profile = _build_profile_for_tier(
        tier=tier,
        ram_total=ram_total,
        ram_available=ram_available,
        vram_total=vram_total,
        vram_available=vram_available,
        cpu_physical=cpu_physical,
        cpu_logical=cpu_logical,
        n_gpu_layers=n_gpu_layers,
        n_ctx=n_ctx,
        backend=backend,
        gpu_name=gpu_name
    )
    
    return profile


def _determine_tier(ram_gb: float, vram_gb: float) -> HardwareTier:
    """Determine hardware tier from RAM and VRAM."""
    if vram_gb >= 16 or ram_gb >= 32:
        return HardwareTier.ULTRA
    elif vram_gb >= 8 or ram_gb >= 16:
        return HardwareTier.HIGH
    elif vram_gb >= 4 or ram_gb >= 8:
        return HardwareTier.MEDIUM
    else:
        return HardwareTier.LOW


def _build_profile_for_tier(
    tier: HardwareTier,
    ram_total: float,
    ram_available: float,
    vram_total: float,
    vram_available: float,
    cpu_physical: int,
    cpu_logical: int,
    n_gpu_layers: int,
    n_ctx: int,
    backend: str,
    gpu_name: Optional[str]
) -> HardwareProfile:
    """Build a complete profile for the given tier."""
    
    # Tier-specific settings
    tier_configs = {
        HardwareTier.LOW: {
            "n_batch": 128,
            "max_tokens_default": 256,
            "n_threads": max(1, cpu_physical // 2),
            "n_threads_batch": max(1, cpu_physical // 2),
            "use_mmap": True,
            "use_mlock": False,
            "offload_kqv": False,
            "type_k": None,  # F16
            "type_v": None,  # F16
            "flash_attn": False,
            "mul_mat_q": True,
            "recommended_chunk_size": 100,
            "recommended_chunk_overlap": 20,
        },
        HardwareTier.MEDIUM: {
            "n_batch": 256,
            "max_tokens_default": 512,
            "n_threads": max(2, cpu_physical - 1),
            "n_threads_batch": max(2, cpu_physical),
            "use_mmap": True,
            "use_mlock": False,
            "offload_kqv": n_gpu_layers != 0,
            "type_k": "q8_0",  # Quantized for stability
            "type_v": "q8_0",  # Quantized for stability
            "flash_attn": True, 
            "mul_mat_q": True,
            "recommended_chunk_size": 150,
            "recommended_chunk_overlap": 30,
        },
        HardwareTier.HIGH: {
            "n_batch": 512,
            "max_tokens_default": 1024,
            "n_threads": cpu_physical,
            "n_threads_batch": cpu_logical,
            "use_mmap": True,
            "use_mlock": True,
            "offload_kqv": True,
            "type_k": "q8_0",  # Quantized KV cache
            "type_v": "q8_0",
            "flash_attn": True,
            "mul_mat_q": True,
            "recommended_chunk_size": 200,
            "recommended_chunk_overlap": 40,
        },
        HardwareTier.ULTRA: {
            "n_batch": 1024,
            "max_tokens_default": 2048,
            "n_threads": cpu_physical,
            "n_threads_batch": cpu_logical,
            "use_mmap": True,
            "use_mlock": True,
            "offload_kqv": True,
            "type_k": "q8_0",
            "type_v": "q8_0",
            "flash_attn": True,
            "mul_mat_q": True,
            "recommended_chunk_size": 300,
            "recommended_chunk_overlap": 60,
        },
    }
    
    cfg = tier_configs[tier]
    
    return HardwareProfile(
        tier=tier,
        ram_total_gb=round(ram_total, 2),
        ram_available_gb=round(ram_available, 2),
        vram_total_gb=round(vram_total, 2),
        vram_available_gb=round(vram_available, 2),
        cpu_cores_physical=cpu_physical,
        cpu_cores_logical=cpu_logical,
        n_ctx=n_ctx,
        n_gpu_layers=n_gpu_layers,
        backend=backend,
        gpu_name=gpu_name,
        **cfg
    )


# ============================================================================
# Utility Functions
# ============================================================================

def get_ggml_type(type_str: Optional[str]):
    """Convert string type to GGML type enum."""
    if type_str is None:
        return None
    
    try:
        from llama_cpp import GGMLType
        type_map = {
            "f16": GGMLType.F16,
            "f32": GGMLType.F32,
            "q4_0": GGMLType.Q4_0,
            "q4_1": GGMLType.Q4_1,
            "q5_0": GGMLType.Q5_0,
            "q5_1": GGMLType.Q5_1,
            "q8_0": GGMLType.Q8_0,
        }
        return type_map.get(type_str.lower())
    except ImportError:
        return None


def get_recommended_models(tier: HardwareTier) -> list[dict]:
    """Get recommended models for the hardware tier."""
    recommendations = {
        HardwareTier.LOW: [
            {"name": "Phi-3-mini-4k", "size": "2.2GB", "params": "3.8B"},
            {"name": "TinyLlama-1.1B", "size": "0.6GB", "params": "1.1B"},
        ],
        HardwareTier.MEDIUM: [
            {"name": "Llama-3.2-3B-Q4_K_M", "size": "2.0GB", "params": "3B"},
            {"name": "Mistral-7B-Q4_K_M", "size": "4.1GB", "params": "7B"},
        ],
        HardwareTier.HIGH: [
            {"name": "Llama-3.1-8B-Q4_K_M", "size": "4.7GB", "params": "8B"},
            {"name": "Mistral-7B-Q8_0", "size": "7.7GB", "params": "7B"},
            {"name": "Qwen2.5-7B-Q4_K_M", "size": "4.7GB", "params": "7B"},
        ],
        HardwareTier.ULTRA: [
            {"name": "Llama-3.1-8B-Q8_0", "size": "8.5GB", "params": "8B"},
            {"name": "Mixtral-8x7B-Q4_K_M", "size": "26GB", "params": "47B"},
            {"name": "Qwen2.5-14B-Q4_K_M", "size": "8.9GB", "params": "14B"},
        ],
    }
    return recommendations.get(tier, [])


def print_hardware_summary(profile: HardwareProfile) -> None:
    """Print a formatted hardware summary."""
    print("=" * 60)
    print("Titier - Hardware Profile Detected")
    print("=" * 60)
    print(f"Tier: {profile.tier.value.upper()}")
    print(f"Backend: {profile.backend.upper()}")
    if profile.gpu_name:
        print(f"GPU: {profile.gpu_name}")
    print("-" * 60)
    print(f"RAM: {profile.ram_available_gb:.1f}GB / {profile.ram_total_gb:.1f}GB")
    print(f"VRAM: {profile.vram_available_gb:.1f}GB / {profile.vram_total_gb:.1f}GB")
    print(f"CPU Cores: {profile.cpu_cores_physical} physical, {profile.cpu_cores_logical} logical")
    print("-" * 60)
    print(f"n_ctx: {profile.n_ctx}")
    print(f"n_batch: {profile.n_batch}")
    print(f"n_gpu_layers: {profile.n_gpu_layers}")
    print(f"n_threads: {profile.n_threads}")
    print(f"Flash Attention: {'✅' if profile.flash_attn else '❌'}")
    print(f"KV Cache Type: {profile.type_k or 'F16'}")
    print("=" * 60)


# ============================================================================
# Main (for testing)
# ============================================================================

if __name__ == "__main__":
    profile = detect_hardware_profile()
    print_hardware_summary(profile)
    
    print("\nRecommended Models:")
    for model in get_recommended_models(profile.tier):
        print(f"  - {model['name']} ({model['size']}, {model['params']})")
