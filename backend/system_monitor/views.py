import socket
import psutil
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from django.http import JsonResponse
from rest_framework import status
import logging
from .models import SystemConfiguration
from .utils import *

logger = logging.getLogger('backend')

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def system_info(request):
    """
    Returns detailed system information for the host.

    Returns:
        JSON response with system details.
    """
    # Attempt to read hostname from a mounted file (e.g., Docker host), fallback to socket
    try:
        with open('/mnt/host_hostname') as f:
            hostname = f.read().strip()
    except:
        hostname = socket.gethostname()

    # Get CPU information
    cpu_freq = psutil.cpu_freq()

    # Get GPU information
    gpu_info = get_gpu_info()

    # Create a dictionary with system information
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

    # Return the system information as a JSON response
    return JsonResponse(info, status=status.HTTP_200_OK)

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def system_config(request):
    """
    Retrieves or updates the system configuration for the authenticated user.

    Permissions:
        - Requires authentication via JWT.

    Methods:
        - GET: Returns the user's current system configuration.
        - POST: Creates or updates the user's system configuration.

    POST Body:
        - host_username: str (username for remote SSH access)
        - tshark_path: str (absolute path to the tshark binary)
        - interface: str (name of the network interface to monitor)

    Returns:
        - 200 OK with system configuration on GET.
        - 200 OK with success message on POST.
        - 400 Bad Request if required fields are missing on POST.
    """
    if request.method == 'GET':
        try:
            # Try to retrieve the existing system configuration for the user
            config = SystemConfiguration.objects.get(user=request.user)
            data = {
                'host_username': config.host_username,
                'tshark_path': config.tshark_path,
                'interface': config.interface
            }

        # Return empty/default values if no configuration is found
        except SystemConfiguration.DoesNotExist:
            data = {
                'host_username': '',
                'tshark_path': '',
                'interface': ''
            }
        return JsonResponse(data, status=200)

    elif request.method == 'POST':
        # Required fields for POST request
        required_fields = ['host_username', 'tshark_path', 'interface']
        data = request.data

        # Validate that all required fields are present and non-empty
        if not all(field in data and data[field] for field in required_fields):
            return JsonResponse({'error': 'Missing required fields'}, status=status.HTTP_400_BAD_REQUEST)

        # Create or update the system configuration for the authenticated user
        config, created = SystemConfiguration.objects.update_or_create(
            user=request.user,
            defaults={
                'host_username': data['host_username'],
                'tshark_path': data['tshark_path'],
                'interface': data['interface']
            }
        )

        # Return success message
        return JsonResponse({'message': 'Configuration saved successfully'}, status=status.HTTP_200_OK)