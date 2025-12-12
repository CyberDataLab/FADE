from __future__ import annotations
import subprocess
import threading
import logging
from typing import Any, Callable, Optional, Dict, List

import logging

from typing import Any, Dict, List, Optional, Callable

from .capture_config import CaptureConfig
from .ssh_config import SSHConfig
from .pipeline_def import PipelineDef
from .explainability_config import ExplainabilityConfig
from .production_handle import ProductionHandle
from .utils import _build_capture_cmd

from . import (
        handler_packet_traffic_anomalies,
        handler_flow_traffic_anomalies,
        handler_syscalls_anomalies
    )

from .callbacks import _callbacks, _emit_status, _emit_error

from .state import thread_controls

logger = logging.getLogger('backend')


# =============================================================================
# Handlers: expected names (change them if they are different in your project)
# =============================================================================
_HANDLER_PACKET_NAME = "handle_packet_traffic_anomalies"
_HANDLER_FLOW_NAME   = "handle_flow_traffic_anomalies"
_HANDLER_SYSCALLS_NAME = "handle_syscalls_anomalies"

def _get_handler(fn_name: str) -> Callable[..., Any]:
    """
    Retrieves a callable handler function by its name from the global namespace.

    This function looks up the specified handler name within the current module's
    global scope and returns the corresponding callable object if it exists.
    It is typically used to dynamically resolve and execute handler functions
    (e.g., `ProductionHandle`, `CaptureHandle`, etc.) by name.

    Args:
        fn_name (str): The name of the handler function to retrieve.

    Returns:
        Callable[..., Any]: The handler function associated with the provided name.

    Raises:
        RuntimeError: If the handler name does not exist in the global namespace
            or the retrieved object is not callable.
    """

    mapping = {
        _HANDLER_PACKET_NAME: handler_packet_traffic_anomalies.handle_packet_traffic_anomalies,
        _HANDLER_FLOW_NAME: handler_flow_traffic_anomalies.handle_flow_traffic_anomalies,
        _HANDLER_SYSCALLS_NAME: handler_syscalls_anomalies.handle_syscalls_anomalies
    }

    if fn_name not in mapping:
        raise RuntimeError(f"Handler '{fn_name}' not found.")
    
    return mapping[fn_name]

# =============================================================================
# Runner
# =============================================================================
def run_live_production(
    *,
    ssh: SSHConfig,
    capture: CaptureConfig,
    pipelines: List[PipelineDef],
    explainability: Optional[ExplainabilityConfig] = None,
    scenario_uuid: Optional[str] = None,
    execution: int = 1, 
    on_anomaly: Optional[Callable[[Dict[str, Any]], None]] = None,
    on_status: Optional[Callable[[str], None]] = None,
    on_error: Optional[Callable[[Exception | str], None]] = None,
) -> ProductionHandle:
    """
    Starts a live production capture and anomaly detection loop in a background thread.

    This function spawns a capture subprocess (tshark or bpftrace depending on
    the capture mode), selects the appropriate handler for the given mode
    ("packet", "flow", or "syscalls"), and runs the prediction+explainability
    loop asynchronously in a dedicated thread.

    The function also wires optional callbacks for:
    - `on_status`: human-readable status updates.
    - `on_error`: error reporting.
    - `on_anomaly`: real-time anomaly events and artifacts.

    Args:
        ssh (SSHConfig): SSH configuration used to build the capture command
            (remote host, interface, tool paths, sudo usage).
        capture (CaptureConfig): Capture configuration defining mode, execution
            environment, and extra arguments for tshark/bpftrace.
        pipelines (Any): Collection of pipelines, typically an iterable of
            `(element_id, model_instance, steps, X_train)` tuples.
        scenario_model (Any): Scenario model instance in the database associated
            with this production run.
        design (Dict[str, Any]): Design dictionary containing `elements` and
            `connections` for the visual pipeline.
        config (Dict[str, Any]): Global configuration dictionary, including
            explainability modules and other settings.
        execution (Any): Execution object or identifier associated with this run.
        uuid (str): Unique identifier for this live production session, used
            in `thread_controls` to manage lifecycle.
        scenario (Any): Scenario object containing metadata such as `uuid`
            for image storage and logging.
        on_anomaly (Callable[[Dict[str, Any]], None], optional): Callback invoked
            whenever an anomaly event is produced. Defaults to None.
        on_status (Callable[[str], None], optional): Callback for human-readable
            status updates. Defaults to None.
        on_error (Callable[[Exception | str], None], optional): Callback invoked
            on fatal or non-recoverable errors. Defaults to None.

    Returns:
        ProductionHandle: A handle that can be used to stop and join the
        live production process and its background thread.

    Raises:
        ValueError: If `capture.mode` is not one of the supported modes
            ("packet", "flow", "syscalls").
    """

    session_id = scenario_uuid or "default"

    # Registrar callbacks globales para que los handlers puedan emitir eventos
    _callbacks["on_anomaly"] = on_anomaly
    _callbacks["on_status"] = on_status
    _callbacks["on_error"] = on_error

    # Construir comando de captura (tshark/bpftrace, etc.)
    cmd = _build_capture_cmd(ssh, capture)
    _emit_status(f"Launching capture: {' '.join(cmd)}")

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
        start_new_session=True,
    )

    # Seleccionar handler según el modo de captura
    mode = (capture.mode or "").strip().lower()
    if mode == "packet":
        handler = _get_handler(_HANDLER_PACKET_NAME)
    elif mode == "flow":
        handler = _get_handler(_HANDLER_FLOW_NAME)
    elif mode == "syscalls":
        handler = _get_handler(_HANDLER_SYSCALLS_NAME)
    else:
        proc.terminate()
        raise ValueError(f"Unsupported mode: {capture.mode!r}")

    def _runner():
        try:
            _emit_status(f"Starting live mode = '{capture.mode}' (execution={execution})")
            # Handler genérico: sólo recibe lo que es común a cualquier app
            handler(
                proc,
                pipelines,
                execution=execution,
                explainability=explainability,
                scenario_uuid=session_id,
            )
        except Exception as e:
            logger.exception("[run_live_production] Fatal error")
            _emit_error(e)
        finally:
            try:
                if proc and proc.poll() is None:
                    proc.terminate()
            except Exception:
                pass
            _emit_status("Live capture finished")
            thread_controls[session_id] = False

    t = threading.Thread(target=_runner, daemon=True)

    # Marcar control del hilo por uuid/session_id
    thread_controls[session_id] = True

    t.start()
    return ProductionHandle(proc, t, status_cb=on_status, uuid=session_id)

