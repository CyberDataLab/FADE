import subprocess
import os

def get_cpu_model():
    """
    Retrieves the CPU model name of the current system.

    Tries multiple methods:
        1. Extract the model from /proc/cpuinfo (common on Linux).
        2. Extract the model from lscpu command.

    Returns:
        str: CPU model name, vendor fallback, or "Unknown" if detection fails.
    """
    try:
        # Try to read from /proc/cpuinfo (available on most Linux systems)
        with open('/proc/cpuinfo') as f:
            for line in f:
                if "model name" in line:
                    model = line.split(":")[1].strip()
                    if model and model != "-":
                        return model
    except:
        pass    # Ignore and try fallback method

    try:
        # Fallback: use lscpu command
        output = subprocess.check_output(['lscpu']).decode()
        model = None
        vendor = None
        for line in output.split('\n'):
            if 'Model name' in line:
                model = line.split(':')[1].strip()
            if 'Vendor ID' in line:
                vendor = line.split(':')[1].strip()

        if model and model != "-":
            return model
        elif vendor:
            return f"{vendor} (model unknown)"
    except:
        pass    # Both methods failed

    # If all methods fail, return "Unknown"
    return "Unknown"

def get_gpu_model():
    """
    Detects and returns the GPU model of the current system.

    Tries multiple methods:
        1. Parses output of `lspci` for VGA or 3D controllers (common on Linux).
        2. Uses `nvidia-smi` for NVIDIA-specific detection.
        3. Reads from the GPU_MODEL environment variable as a fallback.

    Returns:
        str: The GPU model name, or "Unknown" if not detectable.
    """
    try:
        # Check connected devices via lspci (Linux)
        output = subprocess.check_output(['lspci'], stderr=subprocess.DEVNULL).decode()
        for line in output.split('\n'):
            if 'VGA' in line or '3D controller' in line:
                return line.split(':')[-1].strip()
    except:
        pass    # Ignore and try NVIDIA-specific detection

    try:
        # Use nvidia-smi to get GPU model (NVIDIA-specific)
        output = subprocess.check_output(['nvidia-smi', '--query-gpu=name', '--format=csv,noheader'], stderr=subprocess.DEVNULL).decode()
        gpu = output.strip()
        if gpu:
            return f"NVIDIA {gpu}"
    except:
        pass    # Ignore and try environment variable fallback

    # Check for manually set environment variable
    gpu_env = os.environ.get("GPU_MODEL")
    if gpu_env:
        return gpu_env

    # If all methods fail, return "Unknown"
    return "Unknown"

def get_gpu_info():
    """
    Retrieves detailed GPU information from the system.

    Attempts detection in the following order:
        1. NVIDIA GPUs using `nvidia-smi`.
        2. General GPU info via `lspci` (for other vendors).
        3. Falls back to the GPU_MODEL environment variable.

    Returns:
        dict: {
            'gpu_count': int - number of GPUs detected,
            'gpu_models': list[str] - names of detected GPUs
        }
    """
    try:
        # Try NVIDIA-specific detection
        output = subprocess.check_output([
            'nvidia-smi', '--query-gpu=name', '--format=csv,noheader'
        ], stderr=subprocess.DEVNULL).decode().strip().split('\n')

        gpus = [f'NVIDIA {gpu.strip()}' for gpu in output if gpu.strip()]
        return {
            'gpu_count': len(gpus),
            'gpu_models': gpus
        }
    except:
        pass    # Try next method if NVIDIA tools aren't available

    try:
        # Use lspci as a fallback for general detection
        output = subprocess.check_output(['lspci'], stderr=subprocess.DEVNULL).decode()
        gpus = []
        for line in output.split('\n'):
            if 'VGA compatible controller' in line or '3D controller' in line:
                gpus.append(line.split(':')[-1].strip())
        return {
            'gpu_count': len(gpus),
            'gpu_models': gpus
        }
    except:
        pass    # Try environment variable as last resort

    # Fallback to environment variable
    gpu_model = os.environ.get("GPU_MODEL")
    if gpu_model:
        return {
            'gpu_count': 1,
            'gpu_models': [gpu_model]
        }

    # If all methods fail, return empty info
    return {
        'gpu_count': 0,
        'gpu_models': []
    }