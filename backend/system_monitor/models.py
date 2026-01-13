from django.db import models

class SystemConfiguration(models.Model):
    """
    Stores system-level configuration settings associated with a specific user.

    Fields:
    - user: Reference to the user who owns this configuration.
    - host_username: Username of the host system where the configuration is applied.
    - tshark_path: Path to the TShark executable used for network analysis.
    - interface: Network interface to monitor for traffic analysis.
    - bpftrace_script_path: Path to the bpftrace script used for system tracing.
    """

    # Reference to the user who owns this configuration
    user = models.ForeignKey('accounts.CustomUser', on_delete=models.CASCADE)
    host_username = models.CharField(max_length=100)
    tshark_path = models.CharField(max_length=255)
    interface = models.CharField(max_length=100)
    bpftrace_script_path = models.CharField(max_length=255, blank=True, default='')

    class Meta:
        db_table = "SystemConfiguration"