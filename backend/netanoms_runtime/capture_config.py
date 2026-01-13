from typing import List, Optional

class CaptureConfig:
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
        mode: str,
        ek: bool = True,
        run_env: str = "docker",
        extra_args: Optional[List[str]] = None,
        bpftrace_script_path: Optional[str] = None
    ):
        
        """
        Initializes a new CaptureConfig instance.

        Args:
            mode (str): Capture mode to use ("flow", "packet", or "syscalls").
            ek (bool, optional): Whether to enable JSON (`-T ek`) output in tshark.
                Defaults to True.
            run_env (str, optional): Execution environment for the capture.
                Use "docker" for SSH-based remote capture or "host" for local execution.
                Defaults to "docker".
            extra_args (List[str], optional): Additional command-line arguments for
                tshark or bpftrace. Defaults to an empty list.
            bpftrace_script_path (str, optional): Absolute path to the bpftrace script
                when running in syscall capture mode. Defaults to None.
        """

        self.mode = mode
        self.ek = ek
        self.run_env = run_env
        self.extra_args = extra_args or []
        self.bpftrace_script_path = bpftrace_script_path
