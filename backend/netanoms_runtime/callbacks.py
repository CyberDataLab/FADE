
from typing import Any, Callable, Dict, Optional, Union
import logging

logger = logging.getLogger('backend')

_callbacks: Dict[str, Optional[Callable]] = {
    "on_anomaly": None,
    "on_status": None,
    "on_error": None,
}

def _emit_status(msg: str):
    """
    Emits a status update message through the registered callback, if available.

    This function attempts to call the `on_status` callback with the provided message.
    If no callback is registered, the message is logged using the default logger.

    Args:
        msg (str): Human-readable status message describing the current event or state.

    Returns:
        None
    """

    cb = _callbacks.get("on_status")
    if cb: 
        try: cb(msg)
        except Exception: pass
    else:
        logger.info(msg)

def _emit_error(err: Union[Exception, str]):
    """
    Emits an error event through the registered callback, if available.

    This function invokes the `on_error` callback with the given error object or message.
    If the callback is not set, the error is logged locally using the system logger.

    Args:
        err (Exception | str): The error object or string describing the failure.

    Returns:
        None
    """

    cb = _callbacks.get("on_error")
    if cb:
        try: cb(err)
        except Exception: pass
    else:
        logger.error(str(err))

def _emit_anomaly(evt: Dict[str, Any]):
    """
    Emits an anomaly event through the registered callback, if available.

    This function sends an anomaly event dictionary to the `on_anomaly` callback,
    allowing external systems or UI components to handle anomaly detections in
    real time. If no callback is registered, the anomaly event is logged instead.

    Args:
        evt (Dict[str, Any]): A dictionary containing details of the detected anomaly.

    Returns:
        None
    """

    cb = _callbacks.get("on_anomaly")
    if cb:
        try:
            logger.info("ENTRO") 
            logger.info(evt)
            cb(evt)
        except Exception as e:
            logger.exception("Error en on_anomaly callback: %s", e)
    else:
        logger.info(f"[ANOMALY evt] {evt}")

def save_anomaly_metrics(*args, **kwargs):
    """
    Emits an event containing anomaly detection metrics.

    This function packages positional and keyword arguments into an event
    dictionary and dispatches it through the `_emit_anomaly` mechanism.
    The event type is `"anomaly_metrics"`, typically used to record
    evaluation results such as accuracy, precision, recall, or anomaly ratios.

    Args:
        *args: Positional arguments containing metric data or context.
        **kwargs: Keyword arguments containing named metric details.

    Returns:
        None
    """

    evt = {"type": "anomaly_metrics", "args": args, "kwargs": kwargs}
    _emit_anomaly(evt)

def save_anomaly_information(*args, **kwargs):
    """
    Emits an event containing detailed anomaly information.

    This function sends anomaly-related contextual information such as
    timestamps, source identifiers, or feature-level details to the
    registered anomaly callback. The event type is `"anomaly_info"`.

    Args:
        *args: Positional arguments representing anomaly context or payload.
        **kwargs: Keyword arguments providing structured anomaly metadata.

    Returns:
        None
    """

    evt = {"type": "anomaly_info", "args": args, "kwargs": kwargs}
    _emit_anomaly(evt)

def save_explain_artifacts(*args, **kwargs):
    """
    Emits an event containing explainability artifacts.

    This function is typically used to forward explainability outputs
    (e.g., SHAP or LIME images, importance plots, or feature attributions)
    to the anomaly event callback for persistence or visualization.
    The event type is `"explain_artifacts"`.

    Args:
        *args: Positional arguments containing the explainability artifacts.
        **kwargs: Keyword arguments with additional metadata or identifiers.

    Returns:
        None
    """

    evt = {"type": "explain_artifacts", "args": args, "kwargs": kwargs}
    _emit_anomaly(evt)

