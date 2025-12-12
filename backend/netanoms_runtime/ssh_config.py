class SSHConfig:

    """
    Configuration class for defining capture settings for network traffic
    or system calls.

    This class specifies how data should be captured—either as network
    flows, individual packets, or system call traces. It also defines
    whether the capture runs locally or over SSH within a Docker
    environment, and supports additional arguments for advanced capture
    customization.
    """

    def __init__(
        self,
        username: str,
        host: str = "host.docker.internal",
        tshark_path: str = "/usr/bin/tshark",
        bpftrace_path: str = "/usr/bin/bpftrace",
        interface: str = "eth0",
        sudo: bool = True
    ):
    
        """
        Initializes a new SSHConfig instance.

        Args:
            username (str): Username used to authenticate via SSH.
            host (str, optional): Hostname or IP address of the target system.
                Defaults to "host.docker.internal".
            tshark_path (str, optional): Absolute path to the `tshark` binary.
                Defaults to "/usr/bin/tshark".
            bpftrace_path (str, optional): Absolute path to the `bpftrace` binary.
                Defaults to "/usr/bin/bpftrace".
            interface (str, optional): Name of the network interface used for capture.
                Defaults to "eth0".
            sudo (bool, optional): Whether to prepend remote commands with `sudo`.
                Defaults to True.
        """

        self.username = username
        self.host = host
        self.tshark_path = tshark_path
        self.bpftrace_path = bpftrace_path
        self.interface = interface
        self.sudo = sudo