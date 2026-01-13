from rest_framework import serializers
from .models import SystemConfiguration

class SystemSerializer(serializers.ModelSerializer):
    """
    Serializer for the SystemConfiguration model.

    Serializes configuration settings tied to a user, such as:
    - SSH username for remote execution
    - TShark binary path
    - Network interface to monitor

    The user field is read-only.
    """

    class Meta:
        model = SystemConfiguration
        fields = ['id', "host_username", "tshark_path", "interface", "bpftrace_script_path"]
        extra_kwargs = {'user': {'read_only': True}}