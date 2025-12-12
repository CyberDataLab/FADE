import subprocess
import threading
from typing import Callable, Optional

class ProductionHandle:

    """
    Manages the lifecycle of a running capture or production subprocess and its monitoring thread.

    This class encapsulates a subprocess (e.g., a tshark or bpftrace command)
    and a background thread responsible for reading or monitoring its output.
    It provides safe shutdown methods to terminate the process gracefully,
    close all associated resources, and synchronize thread completion.
    """

    def __init__(self, proc: subprocess.Popen, thread: threading.Thread,
                 status_cb: Optional[Callable[[str], None]] = None,
                 uuid: Optional[str] = None):
        
        """
        Initializes a new ProductionHandle instance.

        Args:
            proc (subprocess.Popen): The subprocess running the capture or monitoring process.
            thread (threading.Thread): The thread handling the process output or background monitoring.
            status_cb (Callable[[str], None], optional): Optional callback function to send status messages.
                Defaults to None.
            uuid (str, optional): Unique identifier for this capture session, used for thread coordination.
                Defaults to None.
        """

        self._uuid = uuid
        self._proc = proc
        self._thread = thread
        self._status_cb = status_cb

    
    def stop(self):
        """
        Gracefully stops the running capture process and its associated thread.

        This method performs a safe, multi-step shutdown sequence:
        - Sends a status message using the callback (if defined).
        - Signals the reader loop to stop through the global `thread_controls` dictionary.
        - Attempts graceful process termination (`SIGTERM`).
        - Closes stdout and stderr pipes to unblock threads.
        - Waits for the process to exit; if it does not, it is forcefully killed (`SIGKILL`).
        - Joins the background thread if still alive.

        All operations are wrapped in exception handlers to ensure fault-tolerant
        shutdown in case of unexpected process states.

        Returns:
            None
        """

        try:
            if self._status_cb:
                self._status_cb("Stopping capture...")
        except Exception:
            pass

        # Signal the reader loop to stop
        try:
            if getattr(self, "_uuid", None):
                try:
                    globals().get("thread_controls", {})[self._uuid] = False
                except Exception:
                    pass
        except Exception:
            pass

        # Try graceful process termination
        try:
            if self._proc:
                self._proc.terminate()
        except Exception:
            pass

        # Close pipes to unblock reader
        try:
            if self._proc and self._proc.stdout:
                self._proc.stdout.close()
        except Exception:
            pass
        try:
            if self._proc and self._proc.stderr:
                self._proc.stderr.close()
        except Exception:
            pass

        # Wait a bit and then force kill process group if needed
        try:
            if self._proc:
                self._proc.wait(timeout=2.0)
        except Exception:
            try:
                import os, signal
                os.killpg(self._proc.pid, signal.SIGKILL)
            except Exception:
                try:
                    self._proc.kill()
                except Exception:
                    pass

        try:
            if self._thread and self._thread.is_alive():
                self._thread.join(timeout=2.0)
        except Exception:
            pass
        finally:
            self._proc = None


    def join(self, timeout: Optional[float] = None):
        """
        Waits for the background monitoring thread to finish execution.

        Args:
            timeout (float, optional): Maximum time (in seconds) to wait for the thread.
                If None, the method blocks until the thread terminates. Defaults to None.

        Returns:
            None
        """

        if self._thread: 
           self._thread.join(timeout=timeout)