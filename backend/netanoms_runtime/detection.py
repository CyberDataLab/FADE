# -*- coding: utf-8 -*-
"""
runtime.py
----------
Lanza la captura (SSH+tshark o local) desde aquí, ejecuta la detección en un hilo
y devuelve un ProductionHandle con stop()/join(). La librería **NO** guarda en BD;
en su lugar, **emite eventos** de anomalía a través del callback `on_anomaly`.

Compatibilidad con tu código existente:
- Usa tus funciones `handle_packet_prediction` y `handle_flow_prediction` tal cual si están disponibles.
- Si esas funciones no soportan callbacks, este runtime hace "monkeypatch" de
  funciones típicas de guardado (p.ej. `save_anomaly_metrics`, `save_anomaly_information`)
  para convertir esos guardados en un evento `on_anomaly`.

Cómo detectar entorno (Docker vs host):
- `run_env="docker"`: ejecuta `ssh {user}@{host} "sudo -n tshark -l -i {iface} -T ek"`
- `run_env="host"`: ejecuta localmente `/usr/bin/tshark -l -i {iface} -T ek` (opcional sudo).

Ejemplo de uso en views.py (play):
    from netanoms_runtime.runtime import run_live_production, SSHConfig, CaptureConfig

    ssh = SSHConfig(username=host_username, host="host.docker.internal",
                    tshark_path=tshark_path, interface=interface, sudo=True)
    cap = CaptureConfig(mode=analysis_mode, run_env="docker")

    def on_anomaly(evt): 
        # evt es un dict con info de la anomalía + artefactos (si hay)
        guardar_en_BD(evt)

    handle = run_live_production(
        ssh=ssh,
        capture=cap,
        pipelines=pipelines,
        scenario_model=scenario_model,
        design=design,
        config=config,
        execution=execution,
        uuid=str(uuid),
        scenario=scenario,
        on_anomaly=on_anomaly,
        on_status=lambda m: logger.info(m),
        on_error=lambda e: logger.error(str(e)),
    )
    production_handles[uuid] = handle

En views.py (stop):
    handle = production_handles.pop(uuid, None)
    if handle: handle.stop()

Requisitos:
- Tener `handle_packet_prediction` y/o `handle_flow_prediction` accesibles en el import path del proceso
  (por ejemplo, definidas en utils.py e importadas en este módulo). Si sus nombres son distintos,
  cambia _HANDLER_PACKET_NAME / _HANDLER_FLOW_NAME.
"""

from __future__ import annotations
import os
import shlex
import subprocess
import threading
import logging
from dataclasses import dataclass
from typing import Any, Callable, Optional, Dict, List
import inspect

logger = logging.getLogger(__name__)

# =============================================================================
# Configs
# =============================================================================
@dataclass
class SSHConfig:
    username: str
    host: str = "host.docker.internal"
    tshark_path: str = "/usr/bin/tshark"
    interface: str = "eth0"
    sudo: bool = True

@dataclass
class CaptureConfig:
    mode: str = "flow"           # "packet" | "flow"
    ek: bool = True              # usar -T ek
    run_env: str = "docker"      # "docker" -> via SSH | "host" -> local tshark
    extra_args: Optional[List[str]] = None  # args extra para tshark

# =============================================================================
# Production handle (stop/join)
# =============================================================================
class ProductionHandle:
    def __init__(self, proc: subprocess.Popen, thread: threading.Thread,
                 status_cb: Optional[Callable[[str], None]] = None,
                 uuid: str | None = None):
        self._uuid = uuid
        self._proc = proc
        self._thread = thread
        self._status_cb = status_cb

    
    def stop(self):
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
                    self._proc.terminate()  # SIGTERM
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
        if self._thread:
            self._thread.join(timeout=timeout)

# =============================================================================
# Handlers: nombres esperados (cámbialos si en tu proyecto son otros)
# =============================================================================
_HANDLER_PACKET_NAME = "handle_packet_prediction"   # o "handle_packet_prediction"
_HANDLER_FLOW_NAME   = "handle_flow_prediction"     # o "handle_flow_prediction"

def _get_handler(fn_name: str) -> Callable[..., Any]:
    g = globals()
    if fn_name in g and callable(g[fn_name]):
        return g[fn_name]
    # Si el handler está en otro módulo, intenta importarlo de forma perezosa:
    # Puedes personalizar aquí imports adicionales si lo necesitas.
    raise RuntimeError(f"No se encontró el handler '{fn_name}' en runtime.py. "
                       f"Importa tus funciones (utils.py) o cambia los nombres en _HANDLER_*_NAME.")

# =============================================================================
# Build tshark command (docker vs host)
# =============================================================================
def _build_tshark_cmd(ssh: SSHConfig, cap: CaptureConfig) -> List[str]:
    base = f"{ssh.tshark_path} -l -i {ssh.interface}"
    if cap.ek:
        base += " -T ek"
    if cap.extra_args:
        base += " " + " ".join(shlex.quote(x) for x in cap.extra_args)

    if cap.run_env.lower() == "docker":
        # Ejecutar por SSH en el host
        if ssh.sudo:
            base = "sudo -n " + base
        return ["ssh", f"{ssh.username}@{ssh.host}", base]
    elif cap.run_env.lower() == "host":
        # Ejecutar localmente
        if ssh.sudo:
            base = "sudo -n " + base
        # shell=False con lista para evitar /bin/sh -c
        return shlex.split(base)
    else:
        raise ValueError(f"run_env desconocido: {cap.run_env} (esperado 'docker' o 'host')")

# =============================================================================
# Callbacks & shims (no BD; emitir eventos)
# =============================================================================
_callbacks: Dict[str, Optional[Callable]] = {
    "on_anomaly": None,
    "on_status": None,
    "on_error": None,
}

def _emit_status(msg: str):
    cb = _callbacks.get("on_status")
    if cb: 
        try: cb(msg)
        except Exception: pass
    else:
        logger.info(msg)

def _emit_error(err: Exception | str):
    cb = _callbacks.get("on_error")
    if cb:
        try: cb(err)
        except Exception: pass
    else:
        logger.error(str(err))

def _emit_anomaly(evt: Dict[str, Any]):
    cb = _callbacks.get("on_anomaly")
    if cb:
        try:
            logger.info("ENTRO") 
            logger.info(evt)
            cb(evt)
        except Exception as e:
            logger.exception("Error en on_anomaly callback: %s", e)
    else:
        # si no hay callback, al menos logueamos
        logger.info(f"[ANOMALY evt] {evt}")

# --- Monkeypatch de funciones típicas de guardado ---
# Si tus funciones de utils.py guardan en BD, puedes redirigirlas a eventos.
def save_anomaly_metrics(*args, **kwargs):  # noqa: D401
    """Shim: en lugar de guardar en BD, emitimos un evento de anomalía con lo que recibimos."""
    evt = {"type": "anomaly_metrics", "args": args, "kwargs": kwargs}
    _emit_anomaly(evt)

def save_anomaly_information(*args, **kwargs):
    evt = {"type": "anomaly_info", "args": args, "kwargs": kwargs}
    _emit_anomaly(evt)

def save_explain_artifacts(*args, **kwargs):
    evt = {"type": "explain_artifacts", "args": args, "kwargs": kwargs}
    _emit_anomaly(evt)


import json
import pandas as pd
import numpy as np
import time
from collections import defaultdict
import logging
from action_execution.policy_storage import load_alert_policies, delete_alert_policy

from django.core.mail import send_mail
from django.conf import settings
import os
import socket
import struct
import importlib
import ipaddress
import shap
import matplotlib.pyplot as plt
import tempfile
import pyshark

from collections import defaultdict
import joblib

logger = logging.getLogger('backend')

# Used to track running threads for traffic capture
thread_controls = {}

# Tracks anomaly counts per IP address
ip_anomaly_counter = defaultdict(int)

# Tracks anomaly counts per port
port_anomaly_counter = defaultdict(int)

# Path to the alert policy configuration file
EMAIL_POLICY_FILE = os.path.join(settings.BASE_DIR, "alert_policies.json")

# Protocol mapping for common network protocols
PROTOCOL_MAP = {
    "1": "ICMP",
    "2": "IGMP",
    "6": "TCP",
    "17": "UDP",
    "41": "IPv6",
    "47": "GRE",
    "50": "ESP",
    "51": "AH",
    "58": "ICMPv6",
    "89": "OSPF",
    "132": "SCTP",
}

# Reverse mapping: from protocol name to number
PROTOCOL_REVERSE_MAP = {v: int(k) for k, v in PROTOCOL_MAP.items()}

def ip_to_int(ip_str):
    """
    Converts an IPv4 address string to its 32-bit integer representation.

    Args:
        ip_str (str): The IP address in dotted-decimal notation (e.g., '192.168.1.1').

    Returns:
        int: The integer representation of the IP address (e.g. 3232235777).
             Returns 0 if the input is invalid or conversion fails.
    """
    try:
        return int(ipaddress.IPv4Address(ip_str))
    except Exception:
        return 0

def int_to_ip(ip_int):
    """
    Converts a 32-bit integer to its IPv4 dotted-decimal string representation.

    Args:
        ip_int (int): The integer value of the IP address (e.g., 3232235777).

    Returns:
        str: The IP address in dotted-decimal notation (e.g., '192.168.1.1').
    """
    return socket.inet_ntoa(struct.pack("!I", int(ip_int)))

def find_explainer_class(module_name, explainer_name):
    """
    Dynamically searches for and returns a class reference to a SHAP or LIME explainer.

    This function attempts to import the specified class from a given module or from common
    submodules used by SHAP and LIME. If the class is not found, an ImportError is raised.

    Args:
        module_name (str): Name of the root module (e.g., 'shap' or 'lime').
        explainer_name (str): Name of the explainer class to find (e.g., 'TreeExplainer').

    Returns:
        type: The explainer class object if found.

    Raises:
        ImportError: If the explainer class cannot be found in the specified module or its known submodules.
    """

    try:
        # Try importing directly from the root module
        mod = importlib.import_module(module_name)
        if hasattr(mod, explainer_name):
            return getattr(mod, explainer_name)
    except Exception:
        pass    # Silent fail; try submodules next

    # Common SHAP submodules
    shap_submodules = [
        f"{module_name}.explainers", 
        f"{module_name}.explainers.tree",
        f"{module_name}.explainers.kernel",
        f"{module_name}.explainers.deep",
        f"{module_name}.explainers.linear"
    ]
    
    # Common SHAP submodules
    lime_submodules = [
        f"{module_name}.lime_tabular",
        "lime.lime_tabular"
    ]

    # Try importing from all known submodules
    submodules = shap_submodules + lime_submodules

    for sub in submodules:
        try:
            mod = importlib.import_module(sub)
            if hasattr(mod, explainer_name):
                return getattr(mod, explainer_name)
        except Exception:
            continue

    raise ImportError(f"Could not find explainer '{explainer_name}' in '{module_name}' or its known submodules.")

def save_lime_bar_local(exp, scenario_uuid: str, anomaly_index: int) -> str:
    """
    Generates and saves a local LIME explanation bar chart for a specific anomaly instance.

    Args:
        exp (LIME explanation): The LIME explanation object (e.g., from LimeTabularExplainer.explain_instance).
        scenario_uuid (str): Unique identifier of the scenario.
        anomaly_index (int): Index of the anomaly being explained.

    Returns:
        str: Relative path to the saved image file, or an empty string if saving fails.
    """

    output_dir = os.path.join(settings.MEDIA_ROOT, "lime_local_images")
    os.makedirs(output_dir, exist_ok=True)

    try:
        # Extract and sort feature contributions by absolute value
        contribs = sorted(exp.as_list(), key=lambda x: abs(x[1]), reverse=True)
        features, values = zip(*contribs)

        # Reverse for top-down bar chart
        features = features[::-1]
        values = values[::-1]
        feature_labels = [f"{cond}" for cond in features]

        # Set up the figure
        plt.figure(figsize=(8, 6))
        colors = ["#FF0051" if v > 0 else "#1E88E5" for v in values]
        bars = plt.barh(range(len(values)), values, color=colors)

        # Label the y-axis and add a reference line at x=0
        plt.yticks(range(len(features)), feature_labels)
        plt.axvline(0, color="black", linewidth=0.5, linestyle="--")
        plt.xlabel("LIME value")
        plt.title("Local explanation (LIME)")

        # Add value annotations to each bar
        for i, (bar, value) in enumerate(zip(bars, values)):
            offset = 0.001 * (1 if value > 0 else -1)
            plt.text(
                bar.get_width() + offset,
                bar.get_y() + bar.get_height() / 2,
                f"{value:+.2f}",
                va="center",
                ha="left" if value > 0 else "right",
                fontsize=9,
                color=colors[i]
            )

        plt.tight_layout()

        # Save the image
        output_filename = f"lime_local_{scenario_uuid}_{anomaly_index}.png"
        output_path = os.path.join(output_dir, output_filename)
        plt.savefig(output_path, bbox_inches="tight")
        plt.close()
        logger.info(f"[LIME LOCAL] Local LIME plot saved at: {output_path}")
        return f"lime_local_images/{output_filename}"

    except Exception as e:
        logger.warning(f"[LIME LOCAL] Error while saving local LIME plot: {e}")
        return ""
    
def save_shap_bar_local(shap_values, scenario_uuid, index) -> str:
    """
    Generates and saves a local SHAP bar chart for a specific sample (anomaly or instance).

    Args:
        shap_values (shap.Explanation or array-like): SHAP values for a single instance.
        scenario_uuid (str): Unique identifier of the scenario.
        index (int): Index of the instance being explained.

    Returns:
        str: Relative path to the saved SHAP image file, or an empty string if saving fails.
    """

    output_dir = os.path.join(settings.MEDIA_ROOT, "shap_local_images")
    os.makedirs(output_dir, exist_ok=True)

    try:
        # Generate the SHAP bar plot
        plt.figure()
        shap.plots.bar(shap_values, show=False)

        # Define output filename and path
        output_filename = f"local_shap_{scenario_uuid}_{index}.png"
        output_path = os.path.join(output_dir, output_filename)

        # Save the plot
        plt.tight_layout()
        plt.savefig(output_path, bbox_inches='tight')
        plt.close()
        logger.info(f"[SHAP LOCAL] Plot saved at: {output_path}")
        return f"shap_local_images/{output_filename}"
    except Exception as e:
        logger.warning(f"[SHAP LOCAL] Error while saving SHAP plot: {e}")
        return ""

def save_anomaly_information(info: dict, uuid: str, index: int, protocol: str) -> str:
    """
    Generates and saves an image representation of anomaly information.

    The image includes key-value pairs (e.g., protocol, ports, IPs) displayed as text.
    This is useful for preserving structured anomaly metadata in a visual format.

    Args:
        info (dict): Dictionary containing anomaly information (e.g., IPs, ports).
        uuid (str): Unique identifier for the scenario or execution.
        index (int): Index of the anomaly instance.
        protocol (str): Protocol name (e.g., TCP, UDP).

    Returns:
        str: Relative path to the saved image file.
    """

    # Enrich anomaly info with protocol and ensure port values are integers
    info["protocol"] = protocol
    info["src_port"] = int(info["src_port"])
    info["dst_port"] = int(info["dst_port"])

    logger.info("[ANOMALY INFO] Generating anomaly image with the following information: %s", info)

    # Create the figure
    plt.figure(figsize=(6, 4))
    plt.axis("off")

    # Format the text to display
    text = "\n".join([f"{k}: {v}" for k, v in info.items()])
    plt.text(0, 0.9, text, fontsize=10, va='top')

    # Build output path
    path = os.path.join(settings.MEDIA_ROOT, "anomaly_images", f"anomaly_{uuid}_{index}.png")
    os.makedirs(os.path.dirname(path), exist_ok=True)

    # Save the image
    plt.savefig(path, bbox_inches="tight")
    plt.close()
    return f"anomaly_images/anomaly_{uuid}_{index}.png"

def check_and_send_email_alerts():
    """
    Checks all active email alert policies and sends notifications if thresholds are exceeded.

    This function evaluates whether the anomaly count for a given IP or port has reached
    the threshold specified in the alert policy. If so, it sends an email alert and removes
    the policy to avoid repeated alerts for the same condition.

    Alert reasons must be in the format:
        - "ip:<IP_ADDRESS>"
        - "port:<PORT_NUMBER>"

    Returns:
        None
    """

    policies = load_alert_policies()
    to_remove = []

    for reason, policy in policies.items():
        email = policy.get("target")
        threshold = policy.get("threshold")

        if not all([email, threshold]):
            continue

        count = 0
        if reason.startswith("ip:"):
            ip = reason.split("ip:")[1]
            count = ip_anomaly_counter.get(ip, 0)
        elif reason.startswith("port:"):
            try:
                port = int(reason.split("port:")[1])
                count = port_anomaly_counter.get(port, 0)
            except ValueError:
                continue

        # Check if the count exceeds the threshold
        if count >= threshold:
            logger.info(f"[EMAIL ALERT] Sending alert to {email} for reason: '{reason}' | Count: {count} ≥ {threshold}")
            try:
                send_mail(
                    subject=f"[Network Alert] {reason}",
                    message=f'Network policy alert triggered. \n\n Reason: Excessive number of packets from a specific {reason} \n\n Threshold: {threshold} \n\n Detected: {count}',
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[email],
                    fail_silently=False
                )

                # Remove the policy after sending the alert
                to_remove.append(reason)
            except Exception as e:
                logger.exception(f"[EMAIL ALERT] Failed to send email to {email}: {e}")

    # Remove policies that triggered alerts
    for reason in to_remove:
        delete_alert_policy(reason)

def handle_packet_prediction(proc, pipelines, scenario_model, design, config, execution, uuid, scenario):
    """
    Processes packets in real time from a subprocess and detects anomalies.
    If anomalies are found, they are explained using SHAP or LIME (if configured)
    and then saved along with metadata and visualizations.

    Args:
        proc (subprocess.Popen): Running packet capture process.
        pipelines (list): List of (element_id, model, preprocessing steps, X_train).
        scenario_model: Scenario model instance to associate with anomaly metrics.
        design (dict): Visual scenario design with elements and connections.
        config (dict): System configuration (e.g., config.json).
        execution: Execution context for the current detection run.
        uuid (str): Unique scenario ID.
        scenario: Scenario object for reference (used in filenames).
    """

    # Initialize counters and mappings
    image_counter = get_next_anomaly_index(scenario_model, getattr(scenario, 'uuid', None))
    elements_map = {e["id"]: e for e in design["elements"]}
    connections = design["connections"]

    # Keep processing while the thread control flag is True
    while thread_controls.get(uuid, True):
        # Read a line from the subprocess output
        line = proc.stdout.readline()

        if not line:
            continue

        try:
            # Parse the JSON packet
            pkt = json.loads(line.strip())

            # Skip packets without layers
            if "layers" not in pkt:
                continue

            # Extract relevant fields from the packet
            layers = pkt.get("layers", {})
            frame = layers.get("frame", {})
            frame_time = frame.get("frame_frame_time_epoch")
            length = int(frame.get("frame_frame_len", 0))
            time_ = float(pd.to_datetime(frame_time).timestamp())

            src = dst = proto = ttl = None
            ip_layer = layers.get("ip", {})
            ipv6_layer = layers.get("ipv6", {})

            # Extract IP and protocol information from IPv4 or IPv6 layers
            if ipv6_layer:
                proto = ipv6_layer.get("ipv6_ipv6_nxt")
                src = ipv6_layer.get("ipv6_ipv6_src")
                dst = ipv6_layer.get("ipv6_ipv6_dst")
                ttl = ipv6_layer.get("ipv6_ipv6_hlim")
            elif ip_layer:
                proto = ip_layer.get("ip_ip_proto")
                src = ip_layer.get("ip_ip_src")
                dst = ip_layer.get("ip_ip_dst")
                ttl = ip_layer.get("ip_ip_ttl")

            # Extract protocol name
            proto_name = PROTOCOL_MAP.get(str(proto), str(proto)) if proto else "UNKNOWN"

            # Extract TCP/UDP ports
            tcp_layer = layers.get("tcp", {})
            udp_layer = layers.get("udp", {})

            # Default ports to -1 if not found
            src_port = tcp_layer.get("tcp_tcp_srcport") or udp_layer.get("udp_udp_srcport") or -1
            dst_port = tcp_layer.get("tcp_tcp_dstport") or udp_layer.get("udp_udp_dstport") or -1

            # Convert ports to integers, defaulting to -1 if conversion fails
            try:
                src_port = int(src_port)
            except:
                src_port = -1
                
            try:
                dst_port = int(dst_port)
            except:
                dst_port = -1

            # Create a DataFrame row for the packet
            row = {
                'time': time_,
                'length': length,
                'src': src,
                'dst': dst,
                'src_port': src_port,
                'dst_port': dst_port,
                'protocol': proto_name,
                'ttl': int(ttl) if ttl else None
            }
            df = pd.DataFrame([row])

            if df.empty:
                continue

            # Process each pipeline: preprocessing + model inference
            for element_id, model_instance, steps, X_train in pipelines:
                df_proc = df.copy()
                
                # Apply preprocessing steps
                for step_type, transformer in steps:
                    if step_type in ["StandardScaler", "MinMaxScaler", "Normalizer", "KNNImputer", "PCA"]:
                        expected_cols = transformer.feature_names_in_
                        logger.info(f"[HANDLE PACKET] Transformer {step_type} expects columns: {expected_cols}")
                        
                        df_proc_transformable = df_proc.reindex(columns=expected_cols, fill_value=0)

                        df_proc_transformed = transformer.transform(df_proc_transformable)

                        df_proc_transformed = pd.DataFrame(df_proc_transformed, columns=expected_cols, index=df_proc.index)

                        df_proc[expected_cols] = df_proc_transformed

                    elif step_type == "OneHotEncoding":
                        df_proc = pd.get_dummies(df_proc)

                # Convert IP addresses to integers and protocols to codes
                for ip_col in ['src', 'dst']:
                    if ip_col in df_proc.columns:
                        df_proc[ip_col] = df_proc[ip_col].apply(ip_to_int)

                if 'protocol' in df_proc.columns:
                    def protocol_to_code(p):
                        if isinstance(p, str):
                            p_clean = p.strip().upper()
                            code = PROTOCOL_REVERSE_MAP.get(p_clean, -1)
                            if code == -1:
                                logger.warning(f"[HANDLE PACKET] Unknown protocol: {p}")
                            return code
                        return p

                    df_proc['protocol'] = df_proc['protocol'].apply(protocol_to_code)

                logger.info("[HANDLE PACKET] Processed DataFrame before prediction:")
                logger.info("[HANDLE PACKET] Columns: %s", df_proc.columns.tolist())

                # Predict anomalies (-1 → anomaly → 1, 1 → normal → 0)
                preds = model_instance.predict(df_proc)
                preds = [1 if x == -1 else 0 for x in preds]

                df_proc["anomaly"] = preds
                df["anomaly"] = preds

                logger.info(f"[HANDLE PACKET] {model_instance.__class__.__name__} → Anomalies detected: {sum(preds)}")

                # Continue only if anomalies were detected
                df_anomalous = df_proc[df_proc["anomaly"] == 1]
                if not df_anomalous.empty:
                    logger.info("[HANDLE PACKET] Explaining detected anomalies...")

                    try:
                        elements_map = {e["id"]: e for e in design["elements"]}
                        connections = design["connections"]

                        explainer_id = next((conn["endId"] for conn in connections if conn["startId"] == element_id and elements_map[conn["endId"]]["type"] in ["SHAP", "LIME"]), None)

                        # If no explainability node (SHAP or LIME) is connected
                        if not explainer_id:
                            logger.info("[HANDLE PACKET] No explainability node connected.")

                            # Remove the 'anomaly' column from the anomalous DataFrame
                            anomalous_data = df_anomalous.drop(columns=["anomaly"])

                            for i, row in anomalous_data.iterrows():

                                # Construct a simple textual description of the anomaly
                                anomaly_description = (
                                    f"src: {df.loc[i, 'src']}, "
                                    f"dst: {df.loc[i, 'dst']}, "
                                    f"ports: {df.loc[i, 'src_port']}->{df.loc[i, 'dst_port']} "
                                )

                                # Track source IP and port for alerting policies
                                ip_src = df.loc[i, 'src']
                                port_src = df.loc[i, 'src_port']

                                if ip_src:
                                    ip_anomaly_counter[ip_src] += 1
                                    check_and_send_email_alerts()

                                if port_src != -1:
                                    port_anomaly_counter[port_src] += 1
                                    check_and_send_email_alerts()

                            logger.info("[HANDLE PACKET] Saving anomaly without explanation.")
                            logger.info("[HANDLE PACKET] Description: %s", anomaly_description)

                            save_anomaly_metrics(
                                scenario_model=scenario_model,
                                model_name=model_instance.__class__.__name__,
                                feature_name="",
                                feature_values="",
                                anomalies=anomaly_description,
                                execution=execution,
                                production=True,
                                anomaly_details=None,
                                global_shap_images=[],
                                local_shap_images=[],
                                global_lime_images=[],
                                local_lime_images=[] 
                            )
                        
                        # An explainability node (SHAP or LIME) is connected
                        else:
                            logger.info(f"[HANDLE PACKET] Explainability node found: {explainer_id}")

                            # Extract the explainability node and its parameters
                            explainer_element = elements_map[explainer_id]
                            el_type = explainer_element["type"]
                            params = explainer_element.get("parameters", {})
                            explainer_type = params.get("explainer_type", "").strip()

                            # Determine the module path from config for SHAP, fallback to 'lime' for LIME
                            explainer_module_path = config["sections"]["dataModel"]["explainability"][0]["class"] if el_type == "SHAP" else "lime"

                             # Validate configuration before attempting explanation
                            if not explainer_module_path or not explainer_type:
                                logger.warning(f"[HANDLE PACKET] Missing configuration for explainability node of type {el_type}")
                            else:
                                # Dynamically locate and load the explainer class
                                explainer_class = find_explainer_class(explainer_module_path, explainer_type)

                                # Prepare input data and isolate anomalous rows
                                input_data = df_proc.drop(columns=["anomaly"])
                                anomalous_data = df_anomalous.drop(columns=["anomaly"])

                                def clean_for_json(obj):
                                    """
                                    Recursively clean an object to ensure it's safe for JSON serialization.
                                    
                                    - Replaces NaN and infinite floats with 0.0
                                    - Replaces None with 0.0
                                    - Handles nested dictionaries recursively

                                    Parameters:
                                        obj (Any): The input object to clean (can be dict, float, None, or any other type)

                                    Returns:
                                        Any: The cleaned object, safe for JSON serialization.
                                    """

                                    # If the object is a dictionary, clean each key-value pair recursively
                                    if isinstance(obj, dict):
                                        return {k: clean_for_json(v) for k, v in obj.items()}
                                    elif isinstance(obj, float):
                                        if np.isnan(obj) or np.isinf(obj):
                                            return 0.0
                                    elif obj is None:
                                        return 0.0 
                                    return obj

                                for i, row in anomalous_data.iterrows():
                                    row_df = row.to_frame().T 

                                    # === SHAP Explanation ===
                                    if el_type == "SHAP":
                                        if explainer_type == "KernelExplainer":
                                            def anomaly_score(X):
                                                """
                                                Computes the anomaly score using the model's decision function.

                                                This function is designed to be compatible with explainability tools like LIME.
                                                It converts the input to a pandas DataFrame if it is a NumPy array, ensuring that
                                                column names align with those used during training.

                                                Args:
                                                    X (np.ndarray or pd.DataFrame): The input data for which to compute the anomaly scores.

                                                Returns:
                                                    np.ndarray: The reshaped anomaly scores as a column vector.
                                                """
                                                if isinstance(X, np.ndarray):
                                                    X = pd.DataFrame(X, columns=X_train.columns)
                                                scores = model_instance.decision_function(X)
                                                return scores

                                            explainer = explainer_class(anomaly_score, X_train)

                                        elif explainer_type in ["LinearExplainer", "TreeExplainer", "DeepExplainer"]:
                                            explainer = explainer_class(model_instance, X_train)

                                        else:
                                            explainer = explainer_class(model_instance)

                                        shap_values = explainer(row_df)

                                        logger.info(f"[HANDLE PACKET] SHAP input: {row_df.columns}")
                                        logger.info(f"[HANDLE PACKET] SHAP training columns: {X_train.columns}")

                                        # Extract top contributing feature
                                        contribs = shap_values[0].values 
                                        shap_contribs = sorted(
                                            zip(contribs, row.values, row.index),
                                            key=lambda x: abs(x[0]),
                                            reverse=True
                                        )

                                        top_feature = shap_contribs[0]
                                        feature_name = top_feature[2]

                                        # Format source and destination ports for anomaly description
                                        src_port_str = str(df.loc[i, 'src_port']) if pd.notna(df.loc[i, 'src_port']) else "N/A"
                                        dst_port_str = str(df.loc[i, 'dst_port']) if pd.notna(df.loc[i, 'dst_port']) else "N/A"

                                        # Construct a detailed anomaly description
                                        anomaly_description = (
                                            f"src: {df.loc[i, 'src']}, "
                                            f"dst: {df.loc[i, 'dst']}, "
                                            f"ports: {src_port_str}->{dst_port_str}, "
                                            f"protocol: {df.loc[i, 'protocol']}"
                                        )

                                        # Track source IP and port for alerting policies
                                        ip_src = df.loc[i, 'src']
                                        port_src = df.loc[i, 'src_port']

                                        if ip_src:
                                            ip_anomaly_counter[ip_src] += 1
                                            check_and_send_email_alerts()

                                        if port_src != -1:
                                            port_anomaly_counter[port_src] += 1
                                            check_and_send_email_alerts()

                                        for col in ['src_port', 'dst_port']:
                                            if col in row and not pd.isnull(row[col]):
                                                try:
                                                    row[col] = int(row[col])
                                                except:
                                                    row[col] = -1

                                        feature_values = row.apply(lambda x: x.item() if hasattr(x, "item") else x).to_dict()

                                        # Ensure IPs are strings and ports are integers
                                        for ip_key in ['src', 'dst']:
                                            val = df.loc[i, ip_key]
                                            feature_values[ip_key] = val if isinstance(val, str) else "UNDEFINED"

                                        for port_key in ['src_port', 'dst_port']:
                                            if port_key in feature_values:
                                                try:
                                                    feature_values[port_key] = int(float(feature_values[port_key]))
                                                except:
                                                    feature_values[port_key] = "N/A"

                                        # Add protocol information
                                        proto_code = df.loc[i, 'protocol']
                                        feature_values['protocol'] = PROTOCOL_MAP.get(str(proto_code), proto_code)

                                        '''
                                        safe_payload = {
                                            "values": clean_for_json(feature_values),
                                            "anomaly_indices": anomaly_description
                                        }
                                        '''
                                        safe_payload = {
                                            "anomaly_indices": anomaly_description
                                        }

                                        logger.info(f"[HANDLE PACKET] SHAP anomaly #{i}, top feature: {feature_name}")
                                        logger.info(f"[HANDLE PACKET] Generating anomaly record with index: {image_counter}")

                                        anomaly_details = "\n".join([
                                            f"{k}: {v}" for k, v in feature_values.items()
                                        ])

                                        logger.info("[HANDLE PACKET] Anomaly details: %s", anomaly_details)

                                        shap_paths = [save_shap_bar_local(shap_values[0], scenario.uuid, image_counter)]

                                        logger.info(f"[HANDLE PACKET] Anomaly with index: {image_counter} generated")

                                        # Save the anomaly metrics with SHAP explanations
                                        save_anomaly_metrics(
                                            scenario_model=scenario_model,
                                            model_name=model_instance.__class__.__name__,
                                            feature_name=feature_name,
                                            feature_values=clean_for_json(feature_values),
                                            anomalies=anomaly_description,
                                            execution=execution,
                                            production=True,
                                            anomaly_details=json.dumps(pkt, indent=2),
                                            global_shap_images=[],
                                            local_shap_images=shap_paths,
                                            global_lime_images=[],
                                            local_lime_images=[]
                                        )

                                        # Increase index for next anomaly
                                        image_counter += 1

                                    # === LIME Explanation ===
                                    elif el_type == "LIME":
                                        logger.info(f"[HANDLE PACKET] Explaining row {i} with LIME...")

                                        explainer = explainer_class(
                                            training_data=X_train.values,
                                            feature_names=X_train.columns.tolist(),
                                            mode="regression"
                                        )

                                        def anomaly_score(X):
                                            """
                                            Computes the anomaly score using the model's decision function.

                                            This function is designed to be compatible with explainability tools like LIME.
                                            It converts the input to a pandas DataFrame if it is a NumPy array, ensuring that
                                            column names align with those used during training.

                                            Args:
                                                X (np.ndarray or pd.DataFrame): The input data for which to compute the anomaly scores.

                                            Returns:
                                                np.ndarray: The reshaped anomaly scores as a column vector.
                                            """
                                            if isinstance(X, np.ndarray):
                                                X = pd.DataFrame(X, columns=X_train.columns)
                                            return model_instance.decision_function(X).reshape(-1, 1)

                                        # Generate local explanation for the current row
                                        exp = explainer.explain_instance(
                                            row.values,
                                            anomaly_score,
                                            num_features=10
                                        )

                                        # Sort contributions by absolute value and get most relevant feature
                                        sorted_contribs = sorted(exp.as_list(), key=lambda x: abs(x[1]), reverse=True)
                                        feature_name = sorted_contribs[0][0] 

                                        # Ensure src_port and dst_port are integers
                                        for col in ['src_port', 'dst_port']:
                                            if col in row and not pd.isnull(row[col]):
                                                try:
                                                    row[col] = int(row[col])
                                                except:
                                                    row[col] = -1

                                        # Convert row to dictionary, applying .item() when needed
                                        feature_values = row.apply(lambda x: x.item() if hasattr(x, "item") else x).to_dict()
                                        
                                        # Clean IPs: convert int to string if needed, or fallback to "UNDEFINED"
                                        for ip_key in ['src', 'dst']:
                                            if ip_key in feature_values:
                                                val = feature_values[ip_key]
                                                if isinstance(val, str):
                                                    feature_values[ip_key] = val  
                                                elif isinstance(val, (int, float)):
                                                    try:
                                                        feature_values[ip_key] = int_to_ip(int(val))
                                                    except:
                                                        feature_values[ip_key] = "UNDEFINED"
                                                else:
                                                    feature_values[ip_key] = "UNDEFINED"

                                        # Normalize protocol name
                                        feature_values['protocol'] = PROTOCOL_MAP.get(str(feature_values.get('protocol', '')), feature_values.get('protocol', 'UNKNOWN'))

                                        # Format source and destination ports for anomaly description
                                        src_port_str = str(df.loc[i, 'src_port']) if pd.notna(df.loc[i, 'src_port']) else "N/A"
                                        dst_port_str = str(df.loc[i, 'dst_port']) if pd.notna(df.loc[i, 'dst_port']) else "N/A"

                                        # Construct a detailed anomaly description
                                        anomaly_description = (
                                            f"src: {df.loc[i, 'src']}, "
                                            f"dst: {df.loc[i, 'dst']}, "
                                            f"ports: {src_port_str}->{dst_port_str}, "
                                            f"protocol: {df.loc[i, 'protocol']}"
                                        )

                                        # Format full anomaly details for display or database
                                        anomaly_details = "\n".join([
                                            f"{k}: {v}" for k, v in feature_values.items()
                                        ])

                                        # Save local explanation as LIME bar chart
                                        lime_path = [save_lime_bar_local(exp, scenario.uuid, image_counter)]

                                        logger.info("[HANDLE PACKET] Anomaly details: %s", anomaly_details)

                                        # Save the anomaly metrics with LIME explanations
                                        save_anomaly_metrics(
                                            scenario_model=scenario_model,
                                            model_name=model_instance.__class__.__name__,
                                            feature_name=feature_name,
                                            feature_values=clean_for_json(feature_values),
                                            anomalies=anomaly_description,
                                            execution=execution,
                                            production=True,
                                            anomaly_details=json.dumps(pkt, indent=2),
                                            global_shap_images=[],
                                            local_shap_images=[],
                                            global_lime_images=[],
                                            local_lime_images=lime_path
                                        )

                                        # Increase index for next anomaly
                                        image_counter += 1

                                    else:
                                        logger.warning(f"[HANDLE PACKET ]Explainability node not supported yet: {el_type}")
                    except Exception as e:
                        logger.warning(f"[HANDLE PACKET] Could not interpret with dynamic explainer: {e}")

        except Exception as e:
            logger.error(f"[HANDLE PACKET] Error processing line: {line.strip()} - {e}")
            continue

def handle_flow_prediction(proc, pipelines, scenario_model, design, config, execution, uuid, scenario):
    """
    Handle real-time prediction on network flows extracted from packet captures.
    This function processes packets grouped into flows, applies preprocessing steps,
    runs anomaly detection models, and triggers explainability modules (SHAP/LIME)
    when anomalies are found.

    Args:
        proc: The subprocess capturing the traffic.
        pipelines: List of tuples (element_id, model, steps, X_train).
        scenario_model: The Django model instance for storing metrics.
        design: The visual scenario configuration (nodes and connections).
        config: The backend config.json loaded object.
        execution: The Execution object linked to this run.
        uuid: The unique identifier for this scenario instance.
        scenario: The Scenario object with scenario metadata.
    """

    image_counter = get_next_anomaly_index(scenario_model, getattr(scenario, 'uuid', None))
    elements_map = {e["id"]: e for e in design["elements"]}
    connections = design["connections"]

    flow_dict = defaultdict(list)
    last_flush = time.time()

    # Time interval in seconds to flush the flow data
    interval = 1

    # Keep processing while the thread control flag is True
    while thread_controls.get(uuid, True):
        # Read a line from the subprocess output
        line = proc.stdout.readline()

        # If no line is read, continue to the next iteration
        if not line:
            continue

        try:
            # Parse the JSON packet
            pkt = json.loads(line.strip())

            # Skip packets without layers
            if "layers" not in pkt:
                continue

            # Extract relevant fields from the packet
            layers = pkt.get("layers", {})
            frame = layers.get("frame", {})
            frame_time = frame.get("frame_frame_time_epoch")
            time_ = float(pd.to_datetime(frame_time).timestamp())
            length = int(frame.get("frame_frame_len", 0))

            src = dst = proto = ttl = None
            ip_layer = layers.get("ip", {})
            ipv6_layer = layers.get("ipv6", {})

            # Extract IP and protocol information from IPv4 or IPv6 layers
            if ipv6_layer:
                proto = ipv6_layer.get("ipv6_ipv6_nxt")
                src = ipv6_layer.get("ipv6_ipv6_src")
                dst = ipv6_layer.get("ipv6_ipv6_dst")
                ttl = ipv6_layer.get("ipv6_ipv6_hlim")
            elif ip_layer:
                proto = ip_layer.get("ip_ip_proto")
                src = ip_layer.get("ip_ip_src")
                dst = ip_layer.get("ip_ip_dst")
                ttl = ip_layer.get("ip_ip_ttl")

            # Extract protocol name
            proto_name = PROTOCOL_MAP.get(str(proto), str(proto)) if proto else "UNKNOWN"

            # Extract TCP/UDP ports
            tcp_layer = layers.get("tcp", {})
            udp_layer = layers.get("udp", {})
            src_port = tcp_layer.get("tcp_tcp_srcport") or udp_layer.get("udp_udp_srcport") or -1
            dst_port = tcp_layer.get("tcp_tcp_dstport") or udp_layer.get("udp_udp_dstport") or -1

            # Convert ports to integers, defaulting to -1 if conversion fails
            try:
                src_port = int(src_port)
            except:
                src_port = -1
            try:
                dst_port = int(dst_port)
            except:
                dst_port = -1

            # Create a flow key based on source, destination, ports, and protocol
            if proto_name in ['TCP', 'UDP']:
                flow_key = tuple(sorted([(src, src_port), (dst, dst_port)])) + (proto_name,)
            else:
                flow_key = (src, dst, proto_name)

            flow_dict[flow_key].append({
                'time': time_,
                'length': length,
                'ttl': int(ttl) if ttl else None
            })

        except Exception:
            continue

        # Check if it's time to flush the flow data
        if time.time() - last_flush >= interval:
            rows = []

            # Process the collected flows
            for flow, packets in flow_dict.items():
                times = [p['time'] for p in packets if p['time'] is not None]
                lengths = [p['length'] for p in packets if p['length'] is not None]
                ttls = [p['ttl'] for p in packets if p['ttl'] is not None]

                try:
                    if isinstance(flow[0], tuple):
                        src, src_port = flow[0]
                        dst, dst_port = flow[1]
                        proto = flow[2]
                    else:
                        src, dst, proto = flow
                        src_port = dst_port = -1

                    rows.append({
                        'src': src,
                        'src_port': src_port,
                        'dst': dst,
                        'dst_port': dst_port,
                        'protocol': proto,
                        'packet_count': len(packets),
                        'total_bytes': sum(lengths),
                        'avg_packet_size': sum(lengths) / len(lengths) if lengths else 0,
                        'flow_duration': max(times) - min(times) if times else 0,
                        'avg_ttl': sum(ttls) / len(ttls) if ttls else None,
                    })
                except Exception:
                    continue

            flow_dict.clear()
            last_flush = time.time()

            # Create a DataFrame from the collected flow data
            df = pd.DataFrame(rows)

            if df.empty:
                continue

            # Process each pipeline: preprocessing + model inference
            for element_id, model_instance, steps, X_train in pipelines:
                df_proc = df.copy()
                
                # Apply preprocessing steps
                for step_type, transformer in steps:
                    if step_type in ["StandardScaler", "MinMaxScaler", "Normalizer", "KNNImputer", "PCA"]:
                        expected_cols = transformer.feature_names_in_
                        logger.info(f"[HANDLE FLOW] Transformer {step_type} expects columns: {expected_cols}")
                        
                        df_proc_transformable = df_proc.reindex(columns=expected_cols, fill_value=0)

                        df_proc_transformed = transformer.transform(df_proc_transformable)

                        df_proc_transformed = pd.DataFrame(df_proc_transformed, columns=expected_cols, index=df_proc.index)

                        df_proc[expected_cols] = df_proc_transformed

                    elif step_type == "OneHotEncoding":
                        df_proc = pd.get_dummies(df_proc)

                # Convert IP addresses to integers and protocols to codes
                for ip_col in ['src', 'dst']:
                    if ip_col in df_proc.columns:
                        df_proc[ip_col] = df_proc[ip_col].apply(ip_to_int)

                # Convert protocols to codes
                if 'protocol' in df_proc.columns:
                    def protocol_to_code(p):
                        if isinstance(p, str):
                            p_clean = p.strip().upper()
                            code = PROTOCOL_REVERSE_MAP.get(p_clean, -1)
                            if code == -1:
                                logger.warning(f"[HANDLE FLOW] Unknown protocol: {p}")
                            return code
                        return p

                    df_proc['protocol'] = df_proc['protocol'].apply(protocol_to_code)

                logger.info("[HANDLE FLOW] Processed DataFrame before prediction:")
                logger.info("[HANDLE FLOW] Columns: %s", df_proc.columns.tolist())

                # Predict anomalies (-1 → anomaly → 1, 1 → normal → 0)
                preds = model_instance.predict(df_proc)
                preds = [1 if x == -1 else 0 for x in preds]

                df_proc["anomaly"] = preds
                df["anomaly"] = preds

                logger.info(f"[HANDLE FLOW] {model_instance.__class__.__name__} → Anomalies detected: {sum(preds)}")

                # Continue only if anomalies were detected
                df_anomalous = df_proc[df_proc["anomaly"] == 1]

                if not df_anomalous.empty:
                    logger.info("[HANDLE FLOW] Explaining detected anomalies...")

                    try:
                        elements_map = {e["id"]: e for e in design["elements"]}
                        connections = design["connections"]

                        explainer_id = next((conn["endId"] for conn in connections if conn["startId"] == element_id and elements_map[conn["endId"]]["type"] in ["SHAP", "LIME"]), None)

                        # If no explainability node (SHAP or LIME) is connected
                        if not explainer_id:
                            logger.info("[HANDLE FLOW] No explainability node connected — saving anomaly without explanation.")

                            # Remove the 'anomaly' column from the anomalous DataFrame
                            anomalous_data = df_anomalous.drop(columns=["anomaly"])

                            for i, row in anomalous_data.iterrows():
                                # Construct a simple textual description of the anomaly
                                anomaly_description = (
                                    f"src: {df.loc[i, 'src']}, "
                                    f"dst: {df.loc[i, 'dst']}, "
                                    f"ports: {df.loc[i, 'src_port']}->{df.loc[i, 'dst_port']} "
                                )

                                # Track source IP and port for alerting policies
                                ip_src = df.loc[i, 'src']
                                port_src = df.loc[i, 'src_port']

                                if ip_src:
                                    ip_anomaly_counter[ip_src] += 1
                                    check_and_send_email_alerts()

                                if port_src != -1:
                                    port_anomaly_counter[port_src] += 1
                                    check_and_send_email_alerts()

                            logger.info("[HANDLE FLOW] Saving anomaly without explanation.")
                            logger.info("[HANDLE FLOW] Description: %s", anomaly_description)

                            save_anomaly_metrics(
                                scenario_model=scenario_model,
                                model_name=model_instance.__class__.__name__,
                                feature_name="",
                                feature_values="",
                                anomalies=anomaly_description,
                                execution=execution,
                                production=True,
                                anomaly_details=None,
                                global_shap_images=[],
                                local_shap_images=[],
                                global_lime_images=[],
                                local_lime_images=[] 
                            )

                        # An explainability node (SHAP or LIME) is connected
                        else:
                            logger.info(f"[HANDLE FLOW] Explainability node found: {explainer_id}")

                            # Extract the explainability node and its parameters
                            explainer_element = elements_map[explainer_id]
                            el_type = explainer_element["type"]
                            params = explainer_element.get("parameters", {})
                            explainer_type = params.get("explainer_type", "").strip()

                            # Determine the module path from config for SHAP, fallback to 'lime' for LIME
                            explainer_module_path = config["sections"]["dataModel"]["explainability"][0]["class"] if el_type == "SHAP" else "lime"

                            # Validate configuration before attempting explanation
                            if not explainer_module_path or not explainer_type:
                                logger.warning(f"[HANDLE FLOW] Missing configuration for explainability node of type {el_type}")
                            else:
                                # Dynamically locate and load the explainer class
                                explainer_class = find_explainer_class(explainer_module_path, explainer_type)

                                # Prepare input data and isolate anomalous rows
                                input_data = df_proc.drop(columns=["anomaly"])
                                anomalous_data = df_anomalous.drop(columns=["anomaly"])

                                """
                                Recursively clean an object to ensure it's safe for JSON serialization.
                                
                                - Replaces NaN and infinite floats with 0.0
                                - Replaces None with 0.0
                                - Handles nested dictionaries recursively

                                Parameters:
                                    obj (Any): The input object to clean (can be dict, float, None, or any other type)

                                Returns:
                                    Any: The cleaned object, safe for JSON serialization.
                                """

                                # If the object is a dictionary, clean each key-value pair recursively
                                def clean_for_json(obj):
                                    if isinstance(obj, dict):
                                        return {k: clean_for_json(v) for k, v in obj.items()}
                                    elif isinstance(obj, float):
                                        if np.isnan(obj) or np.isinf(obj):
                                            return 0.0
                                    elif obj is None:
                                        return 0.0 
                                    return obj

                                for i, row in anomalous_data.iterrows():
                                    row_df = row.to_frame().T 

                                    # === SHAP Explanation ===
                                    if el_type == "SHAP":
                                        if explainer_type == "KernelExplainer":
                                            def anomaly_score(X):
                                                """
                                                Computes the anomaly score using the model's decision function.

                                                This function is designed to be compatible with explainability tools like LIME.
                                                It converts the input to a pandas DataFrame if it is a NumPy array, ensuring that
                                                column names align with those used during training.

                                                Args:
                                                    X (np.ndarray or pd.DataFrame): The input data for which to compute the anomaly scores.

                                                Returns:
                                                    np.ndarray: The reshaped anomaly scores as a column vector.
                                                """
                                                if isinstance(X, np.ndarray):
                                                    X = pd.DataFrame(X, columns=X_train.columns)
                                                scores = model_instance.decision_function(X)
                                                return scores

                                            explainer = explainer_class(anomaly_score, X_train)

                                        elif explainer_type in ["LinearExplainer", "TreeExplainer", "DeepExplainer"]:
                                            explainer = explainer_class(model_instance, X_train)

                                        else:
                                            explainer = explainer_class(model_instance)

                                        shap_values = explainer(row_df)

                                        logger.info(f"[HANDLE FLOW] SHAP input: {row_df.columns}")
                                        logger.info(f"[HANDLE FLOW] SHAP training columns: {X_train.columns}")

                                        # Extract top contributing feature
                                        contribs = shap_values[0].values 
                                        shap_contribs = sorted(
                                            zip(contribs, row.values, row.index),
                                            key=lambda x: abs(x[0]),
                                            reverse=True
                                        )
                                        top_feature = shap_contribs[0]
                                        feature_name = top_feature[2]

                                        # Build human-readable anomaly description
                                        src_port_str = str(df.loc[i, 'src_port']) if pd.notna(df.loc[i, 'src_port']) else "N/A"
                                        dst_port_str = str(df.loc[i, 'dst_port']) if pd.notna(df.loc[i, 'dst_port']) else "N/A"

                                        anomaly_description = (
                                            f"src: {df.loc[i, 'src']}, "
                                            f"dst: {df.loc[i, 'dst']}, "
                                            f"ports: {src_port_str}->{dst_port_str}, "
                                            f"protocol: {df.loc[i, 'protocol']}"
                                        )

                                        # Track source IP and port for alerting policies
                                        ip_src = df.loc[i, 'src']
                                        port_src = df.loc[i, 'src_port']

                                        if ip_src:
                                            ip_anomaly_counter[ip_src] += 1
                                            check_and_send_email_alerts()

                                        if port_src != -1:
                                            port_anomaly_counter[port_src] += 1
                                            check_and_send_email_alerts()

                                        # Ensure src_port and dst_port are integers
                                        for col in ['src_port', 'dst_port']:
                                            if col in row and not pd.isnull(row[col]):
                                                try:
                                                    row[col] = int(row[col])
                                                except:
                                                    row[col] = -1

                                        # Convert row to dictionary, applying .item() when needed
                                        feature_values = row.apply(lambda x: x.item() if hasattr(x, "item") else x).to_dict()

                                        # Ensure IPs are strings and ports are integers
                                        for ip_key in ['src', 'dst']:
                                            val = df.loc[i, ip_key]
                                            feature_values[ip_key] = val if isinstance(val, str) else "UNDEFINED"

                                        for port_key in ['src_port', 'dst_port']:
                                            if port_key in feature_values:
                                                try:
                                                    feature_values[port_key] = int(float(feature_values[port_key]))
                                                except:
                                                    feature_values[port_key] = "N/A"

                                        # Add protocol information
                                        proto_code = df.loc[i, 'protocol']
                                        feature_values['protocol'] = PROTOCOL_MAP.get(str(proto_code), proto_code)

                                        '''
                                        safe_payload = {
                                            "values": clean_for_json(feature_values),
                                            "anomaly_indices": anomaly_description
                                        }
                                        '''
                                        safe_payload = {
                                            "anomaly_indices": anomaly_description
                                        }

                                        anomalies_json = json.dumps(safe_payload)

                                        logger.info(f"[HANDLE FLOW] SHAP anomaly #{i}, top feature: {feature_name}")
                                        logger.info(f"[HANDLE FLOW] Generating anomaly record with index: {image_counter}")

                                        anomaly_details = "\n".join([
                                            f"{k}: {v}" for k, v in feature_values.items()
                                        ])

                                        logger.info("Anomaly details: %s", anomaly_details)

                                        # Save local SHAP explanation as a bar chart
                                        shap_paths = [save_shap_bar_local(shap_values[0], scenario.uuid, image_counter)]

                                        logger.info(f"[HANDLE FLOW] Anomaly record with index: {image_counter} generated")

                                        # Save the anomaly metrics with SHAP explanations
                                        save_anomaly_metrics(
                                            scenario_model=scenario_model,
                                            model_name=model_instance.__class__.__name__,
                                            feature_name=feature_name,
                                            feature_values=clean_for_json(feature_values),
                                            anomalies=anomaly_description,
                                            execution=execution,
                                            production=True,
                                            anomaly_details=anomaly_details,
                                            global_shap_images=[],
                                            local_shap_images=shap_paths,
                                            global_lime_images=[],
                                            local_lime_images=[]
                                        )

                                        # Increase index for next anomaly
                                        image_counter += 1

                                    # === LIME Explanation ===
                                    elif el_type == "LIME":
                                        logger.info(f"[HANDLE FLOW] Explaining row {i} with LIME...")

                                        explainer = explainer_class(
                                            training_data=X_train.values,
                                            feature_names=X_train.columns.tolist(),
                                            mode="regression"
                                        )

                                        def anomaly_score(X):
                                            """
                                            Computes the anomaly score using the model's decision function.

                                            This function is designed to be compatible with explainability tools like LIME.
                                            It converts the input to a pandas DataFrame if it is a NumPy array, ensuring that
                                            column names align with those used during training.

                                            Args:
                                                X (np.ndarray or pd.DataFrame): The input data for which to compute the anomaly scores.

                                            Returns:
                                                np.ndarray: The reshaped anomaly scores as a column vector.
                                            """
                                            if isinstance(X, np.ndarray):
                                                X = pd.DataFrame(X, columns=X_train.columns)
                                            return model_instance.decision_function(X).reshape(-1, 1)

                                        # Generate local explanation for the current row
                                        exp = explainer.explain_instance(
                                            row.values,
                                            anomaly_score,
                                            num_features=10
                                        )

                                        # Sort contributions by absolute value and get most relevant feature
                                        sorted_contribs = sorted(exp.as_list(), key=lambda x: abs(x[1]), reverse=True)
                                        feature_name = sorted_contribs[0][0] 

                                        # Ensure src_port and dst_port are integers
                                        for col in ['src_port', 'dst_port']:
                                            if col in row and not pd.isnull(row[col]):
                                                try:
                                                    row[col] = int(row[col])
                                                except:
                                                    row[col] = -1

                                        # Convert row to dictionary, applying .item() when needed
                                        feature_values = row.apply(lambda x: x.item() if hasattr(x, "item") else x).to_dict()
                                        for ip_key in ['src', 'dst']:
                                            if ip_key in feature_values:
                                                val = feature_values[ip_key]
                                                if isinstance(val, str):
                                                    feature_values[ip_key] = val  
                                                elif isinstance(val, (int, float)):
                                                    try:
                                                        feature_values[ip_key] = int_to_ip(int(val))
                                                    except:
                                                        feature_values[ip_key] = "UNDEFINED"
                                                else:
                                                    feature_values[ip_key] = "UNDEFINED"

                                        # Normalize protocol name
                                        feature_values['protocol'] = PROTOCOL_MAP.get(str(feature_values.get('protocol', '')), feature_values.get('protocol', 'UNKNOWN'))

                                        # Build textual anomaly description
                                        src_port_str = str(df.loc[i, 'src_port']) if pd.notna(df.loc[i, 'src_port']) else "N/A"
                                        dst_port_str = str(df.loc[i, 'dst_port']) if pd.notna(df.loc[i, 'dst_port']) else "N/A"

                                        anomaly_description = (
                                            f"src: {df.loc[i, 'src']}, "
                                            f"dst: {df.loc[i, 'dst']}, "
                                            f"ports: {src_port_str}->{dst_port_str}, "
                                            f"protocol: {df.loc[i, 'protocol']}"
                                        )

                                        # Format full anomaly details for display or database
                                        anomaly_details = "\n".join([
                                            f"{k}: {v}" for k, v in feature_values.items()
                                        ])

                                        # Save local explanation as LIME bar chart
                                        lime_path = [save_lime_bar_local(exp, scenario.uuid, image_counter)]

                                        logger.info("[HANDLE FLOW] Anomaly details: %s", anomaly_details)

                                        # Save the anomaly metrics with LIME explanations
                                        save_anomaly_metrics(
                                            scenario_model=scenario_model,
                                            model_name=model_instance.__class__.__name__,
                                            feature_name=feature_name,
                                            feature_values=clean_for_json(feature_values),
                                            anomalies=anomaly_description,
                                            execution=execution,
                                            production=True,
                                            anomaly_details=anomaly_details,
                                            global_shap_images=[],
                                            local_shap_images=[],
                                            global_lime_images=[],
                                            local_lime_images=lime_path
                                        )

                                        # Increase index for next anomaly
                                        image_counter += 1

                                    else:
                                        logger.warning(f"[HANDLE FLOW]Explainability node not supported yet: {el_type}")
                    except Exception as e:
                        logger.warning(f"[HANDLE FLOW] Could not interpret with dynamic explainer: {e}")



def get_next_anomaly_index(scenario_model, scenario_uuid: str = None) -> int:
    """
    Get the next available anomaly index **without DB** by counting existing
    local explanation images on disk for this scenario (SHAP or LIME).

    Priority:
      - If `scenario_uuid` is provided, use it.
      - Else, if `scenario_model` has `scenario` with `.uuid`, use that.
      - Otherwise, return 1.

    We count files matching:
      - MEDIA_ROOT/shap_local_images/local_shap_{uuid}_*.png
      - MEDIA_ROOT/lime_local_images/lime_local_{uuid}_*.png
    and return max(counts)+1.
    """
    try:
        if scenario_uuid is None:
            # Try best-effort extraction from detector object
            scenario_uuid = getattr(getattr(scenario_model, "scenario", None), "uuid", None)

        if not scenario_uuid:
            return 1

        base = getattr(settings, "MEDIA_ROOT", "./media")
        shap_dir = os.path.join(base, "shap_local_images")
        lime_dir = os.path.join(base, "lime_local_images")
        os.makedirs(shap_dir, exist_ok=True)
        os.makedirs(lime_dir, exist_ok=True)

        def _count_matching(dir_path, prefix):
            try:
                return sum(
                    1 for name in os.listdir(dir_path)
                    if name.startswith(f"{prefix}_{scenario_uuid}_") and name.endswith(".png")
                )
            except Exception:
                return 0

        shap_count = _count_matching(shap_dir, "local_shap")
        lime_count = _count_matching(lime_dir, "lime_local")
        current = max(shap_count, lime_count)
        return current + 1
    except Exception:
        return 1

# =============================================================================
# Runner
# =============================================================================
def run_live_production(
    *,
    ssh: SSHConfig,
    capture: CaptureConfig,
    pipelines: Any,
    scenario_model: Any,
    design: Dict[str, Any],
    config: Dict[str, Any],
    execution: Any,
    uuid: str,
    scenario: Any,
    on_anomaly: Optional[Callable[[Dict[str, Any]], None]] = None,
    on_status: Optional[Callable[[str], None]] = None,
    on_error: Optional[Callable[[Exception | str], None]] = None,
) -> ProductionHandle:
    """
    - Construye y lanza tshark (SSH o local) según capture.run_env.
    - Ejecuta tu handler (packet o flow) en un hilo.
    - Redirige guardados a callbacks (no BD).
    """
    # Registrar callbacks globales
    _callbacks["on_anomaly"] = on_anomaly
    _callbacks["on_status"] = on_status
    _callbacks["on_error"]  = on_error

    cmd = _build_tshark_cmd(ssh, capture)
    _emit_status(f"Launching capture: {cmd}")

    proc = subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, bufsize=1, start_new_session=True
    )

    handler_name = _HANDLER_PACKET_NAME if capture.mode.strip().lower() == "packet" else _HANDLER_FLOW_NAME
    handler = _get_handler(handler_name)

    # Intentamos pasar callbacks al handler si los acepta
    def _runner():
        try:
            _emit_status(f"Starting live production mode='{capture.mode}'")
            sig = inspect.signature(handler)
            accepts_kwargs = any(p.kind in (p.VAR_KEYWORD,) for p in sig.parameters.values()) or \
                             "on_anomaly" in sig.parameters or "on_status" in sig.parameters or "on_error" in sig.parameters
            if accepts_kwargs:
                handler(proc, pipelines, scenario_model, design, config, execution, uuid, scenario,
                        on_anomaly=on_anomaly, on_status=on_status, on_error=on_error)
            else:
                # Handler no acepta callbacks → lo llamamos tal cual; los shims harán el trabajo
                handler(proc, pipelines, scenario_model, design, config, execution, uuid, scenario)
        except Exception as e:
            logger.exception("[run_live_production] Fatal error")
            _emit_error(e)
        finally:
            try:
                if proc:
                    proc.terminate()
            except Exception:
                pass
            _emit_status("Live production finished")

    t = threading.Thread(target=_runner, daemon=True)
    try:
        thread_controls[uuid] = True
    except Exception:
        pass
    t.start()
    return ProductionHandle(proc, t, status_cb=on_status, uuid=uuid)

