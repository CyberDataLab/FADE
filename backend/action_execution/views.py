from django.shortcuts import render
import os
from django.http import JsonResponse
import subprocess
from django.http import JsonResponse
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
import logging
from system_monitor.models import SystemConfiguration
from .utils import *
from action_execution.policy_storage import add_alert_policy

logger = logging.getLogger('backend')

# Create your views here.

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def apply_policy(request):
    """
    Applies a system policy (e.g., block IP, limit bandwidth, send email alert) on a remote host.

    Expects:
        - type (str): Type of policy to apply (e.g., 'block_ip', 'send_email', 'limit_bandwidth').
        - value (str): The value associated with the policy (e.g., IP address, port, or target email).
        - reason (str): The reason identifier for the policy (used in monitoring).
        - monitorTarget (str, optional): IP or port to monitor (required for send_email).
        - monitorThreshold (int, optional): Threshold for triggering alert (required for send_email).

    Behavior:
        - For 'send_email', registers an alert policy internally.
        - For other policies, builds a remote OS-specific command and executes it over SSH.

    Returns:
        - 200 OK with a success message if applied successfully.
        - 400 Bad Request if required fields are missing or invalid.
        - 404 Not Found if user system configuration does not exist.
        - 500 Internal Server Error for unexpected exceptions or command execution failures.
    """

    # Get the policy information from the request
    policy_type = request.data.get('type')
    value = request.data.get('value')
    reason = request.data.get('reason')
    monitor_target = request.data.get("monitorTarget")
    monitor_threshold = request.data.get("monitorThreshold")
    logger.info(f"Applying policy: {policy_type}, reason: {reason}")

    # Get the host OS from environment variable or default to empty string
    host_os = os.environ.get("HOST_OS", "").lower()
    logger.info(f"Host OS: {host_os}")

    # Default Docker host bridge for inter-container SSH
    ssh_host = "host.docker.internal"

    # Retrieve system configuration for authenticated user
    user = request.user
    try:
        user_config = SystemConfiguration.objects.get(user=user)
        host_username = user_config.host_username or 'default_user'

    # Return error if user system configuration does not exist
    except SystemConfiguration.DoesNotExist:
        return JsonResponse({'error': 'User system config not found'}, status=404)

    try:
        # Handle custom policy: send_email (used for alerting)
        if policy_type == 'send_email':
            # Return error if required fields are missing
            if not all([reason, monitor_target, monitor_threshold, value]):
                return JsonResponse({'message': 'Missing fields for send_email'}, status=400)
            try:
                monitor_threshold = int(monitor_threshold)
            # Return error if monitor_threshold is not a valid integer
            except ValueError:
                return JsonResponse({'message': 'Invalid threshold'}, status=400)

            # Generate internal key for policy
            if "IP" in reason:
                policy_key = f"ip:{monitor_target}"
            elif "port" in reason or "Port" in reason:
                policy_key = f"port:{monitor_target}"
            else:
                policy_key = reason

            # Store policy using helper function
            add_alert_policy(policy_key, monitor_threshold, target_email=value)

            logger.info(f"[EMAIL POLICY] {policy_key} → {value} ≥ {monitor_threshold}")

            # Return success message for email policy registration
            return JsonResponse({'message': 'Send-email policy registered'})

        # For macOS or Linux, build the appropriate command
        if host_os.startswith("darwin"):
            remote_cmd = build_mac_command(policy_type, value)
        elif host_os.startswith("linux"):
            remote_cmd = build_linux_command(policy_type, value)
        else:
            # Return error for unsupported host OS
            return JsonResponse({'message': f'Unsupported host OS: {host_os}'}, status=400)

        # Build SSH command to execute the rule remotely
        full_command = f"ssh {host_username}@{ssh_host} '{remote_cmd}'"
        logger.info(f"Executing command: {full_command}")

        # Run the command and capture output
        result = subprocess.run(full_command, shell=True, capture_output=True, text=True)

        # Handle command execution failure
        if result.returncode != 0:
            logger.error(f"Command failed: {result.stderr}")
            # Return error message if command execution fails
            return JsonResponse({'message': f'Command failed: {result.stderr}'}, status=500)

        # Return success message with applied policy details
        return JsonResponse({'message': f'Policy applied: {policy_type} with value {value}'})

    except Exception as e:
        logger.exception("Unexpected error applying policy")
        # Return error message for unexpected exceptions
        return JsonResponse({'message': str(e)}, status=500)
