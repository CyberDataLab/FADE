import socket
import psutil
import subprocess
import os
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from django.http import JsonResponse
from rest_framework import status

def get_cpu_model():
    try:
        with open('/proc/cpuinfo') as f:
            for line in f:
                if "model name" in line:
                    model = line.split(":")[1].strip()
                    if model and model != "-":
                        return model
    except:
        pass

    try:
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
        pass

    return "Unknown"

def get_gpu_model():
    try:
        output = subprocess.check_output(['lspci'], stderr=subprocess.DEVNULL).decode()
        for line in output.split('\n'):
            if 'VGA' in line or '3D controller' in line:
                return line.split(':')[-1].strip()
    except:
        pass

    try:
        output = subprocess.check_output(['nvidia-smi', '--query-gpu=name', '--format=csv,noheader'], stderr=subprocess.DEVNULL).decode()
        gpu = output.strip()
        if gpu:
            return f"NVIDIA {gpu}"
    except:
        pass

    import os
    gpu_env = os.environ.get("GPU_MODEL")
    if gpu_env:
        return gpu_env

    return "Unknown"

def get_gpu_info():
    try:
        output = subprocess.check_output([
            'nvidia-smi', '--query-gpu=name', '--format=csv,noheader'
        ], stderr=subprocess.DEVNULL).decode().strip().split('\n')

        gpus = [f'NVIDIA {gpu.strip()}' for gpu in output if gpu.strip()]
        return {
            'gpu_count': len(gpus),
            'gpu_models': gpus
        }
    except:
        pass

    try:
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
        pass

    gpu_model = os.environ.get("GPU_MODEL")
    if gpu_model:
        return {
            'gpu_count': 1,
            'gpu_models': [gpu_model]
        }

    return {
        'gpu_count': 0,
        'gpu_models': []
    }

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def system_info(request):
    try:
        with open('/mnt/host_hostname') as f:
            hostname = f.read().strip()
    except:
        hostname = socket.gethostname()

    cpu_freq = psutil.cpu_freq()
    gpu_info = get_gpu_info()

    info = {
        'hostname': hostname,
        'cpu_model': get_cpu_model(),
        'cpu_count_logical': psutil.cpu_count(logical=True),
        'cpu_count_physical': psutil.cpu_count(logical=False),
        'cpu_freq': {
        'current': round(cpu_freq.current, 2) if cpu_freq and cpu_freq.current else None,
        'min': round(cpu_freq.min, 2) if cpu_freq and cpu_freq.min else None,
        'max': round(cpu_freq.max, 2) if cpu_freq and cpu_freq.max else None,
    },
        'gpu_count': gpu_info['gpu_count'],
        'gpu_models': gpu_info['gpu_models'],
        'memory': psutil.virtual_memory()._asdict()
    }

    return JsonResponse(info, status=status.HTTP_200_OK)
