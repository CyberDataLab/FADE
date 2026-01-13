from __future__ import annotations
import os
import shlex
import logging
from typing import Any, Optional, Dict, List

import pandas as pd

import logging
from netanoms_runtime.policy_storage import load_alert_policies, delete_alert_policy

from django.core.mail import send_mail
from django.conf import settings
import io
import socket
import struct
import tempfile
import pyshark
import ipaddress
import shap
from collections import defaultdict
import matplotlib.pyplot as plt

from typing import Any, Dict, List, Optional, Tuple
from .capture_config import CaptureConfig
from .ssh_config import SSHConfig
from .pipeline_def import PipelineDef

logger = logging.getLogger('backend')

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

# =============================================================================
# Build tshark command (docker vs host)
# =============================================================================

def _build_capture_cmd(ssh: SSHConfig, capture: CaptureConfig) -> list[str]:
    """
    Builds the command used to start a capture process based on the provided configuration.

    This function constructs the appropriate command-line arguments depending on the
    selected capture mode. It delegates command construction to either `_build_tshark_cmd`
    or `_build_bpftrace_cmd`, depending on whether the mode involves network traffic
    or system call tracing.

    Args:
        ssh (SSHConfig): SSH configuration object containing remote execution parameters.
        capture (CaptureConfig): Capture configuration object defining mode, environment,
            and additional arguments.

    Returns:
        list[str]: A list of command-line arguments ready to be executed for the capture process.

    Raises:
        ValueError: If the capture mode specified in `capture.mode` is not supported.
    """

    mode = capture.mode.strip().lower()
    if mode == "packet":
        return _build_tshark_cmd(ssh, capture)
    if mode == "flow":
        return _build_argus_flow_cmd(ssh, capture)
    if mode == "syscalls":
        return _build_bpftrace_cmd(ssh, capture)
    raise ValueError(f"Capture mode not supported: {capture.mode!r}")

def _build_tshark_cmd(ssh: SSHConfig, cap: CaptureConfig) -> List[str]:
    """
    Builds the command-line instruction to launch a `tshark` capture session.

    This function dynamically constructs the appropriate `tshark` command based on
    the provided SSH and capture configurations. It supports both local and remote
    execution modes:
    - **"docker"** → executes remotely through SSH on the host machine.
    - **"host"** → executes locally on the same machine.

    The function also adds `sudo` when required and escapes additional arguments
    securely using `shlex.quote()` to prevent shell injection issues.

    Args:
        ssh (SSHConfig): SSH configuration object containing connection parameters
            (host, username, interface, binary path, etc.).
        cap (CaptureConfig): Capture configuration object defining mode, environment,
            and optional tshark parameters.

    Returns:
        List[str]: The fully constructed `tshark` command as a list of arguments
        suitable for subprocess execution.

    Raises:
        ValueError: If `cap.run_env` is not recognized (expected "docker" or "host").
    """

    base = f"{ssh.tshark_path} -l -i {ssh.interface}"
    if cap.ek:
        base += " -T ek"
    if cap.extra_args:
        base += " " + " ".join(shlex.quote(x) for x in cap.extra_args)

    if cap.run_env.lower() == "docker":
        # Executed via SSH
        if ssh.sudo:
            base = "sudo -n " + base
        return ["ssh", f"{ssh.username}@{ssh.host}", base]
    elif cap.run_env.lower() == "host":
        # Executed locally
        if ssh.sudo:
            base = "sudo -n " + base
        return shlex.split(base)
    else:
        raise ValueError(f"run_env unknown: {cap.run_env} (Expected 'docker' o 'host')")

def _build_argus_flow_cmd(ssh: SSHConfig, cap: CaptureConfig) -> list[str]:
    """
    Build a remote Argus pipeline that outputs live flow records in (quasi) real-time.

    Key points for your setup:
      - dumpcap must use -P (PCAP/libpcap) so Argus can read stdin correctly
      - Argus emits status frequently with ARGUS_FLOW_STATUS_INTERVAL=1
      - ra prints CSV (commas) so your df_from_ra_csv_lines() + handler work as-is
      - In docker mode we execute on the HOST via ssh user@host and wrap in bash -lc + pipefail
      - No timeout here: production must be continuous
    """
    dumpcap_bin = getattr(ssh, "dumpcap_path", "/usr/bin/dumpcap")

    ra_fields = "saddr,sport,daddr,dport,proto,pkts,bytes,dur,sttl,dttl"

    dumpcap_base = f"{dumpcap_bin} -P -i {shlex.quote(ssh.interface)} -q"

    if cap.extra_args:
        dumpcap_base += " " + " ".join(shlex.quote(x) for x in cap.extra_args)

    pipeline = (
        f"{dumpcap_base} -w - "
        f"| stdbuf -oL argus -X -B ARGUS_FLOW_STATUS_INTERVAL=1 -e 127.0.0.1 -r - -w - "
        f"| stdbuf -oL ra -r - -n -c , -s {shlex.quote(ra_fields)}"
    )

    if cap.run_env.lower() == "docker":
        # Run capture on the host (from inside container) via SSH
        if ssh.sudo:
            pipeline = "sudo -n " + pipeline

        remote_cmd = f"bash -lc {shlex.quote('set -o pipefail; ' + pipeline)}"
        return ["ssh", f"{ssh.username}@{ssh.host}", remote_cmd]

    elif cap.run_env.lower() == "host":
        if ssh.sudo:
            pipeline = "sudo -n " + pipeline
        return ["bash", "-lc", f"set -o pipefail; {pipeline}"]

    else:
        raise ValueError(f"run_env unknown: {cap.run_env}")


def _build_bpftrace_cmd(ssh: SSHConfig, capture: CaptureConfig) -> list[str]:
    """
    Builds the command-line instruction to launch a `bpftrace` syscall capture session.

    This function constructs the appropriate `bpftrace` command based on the
    provided SSH and capture configurations. It supports both local and remote
    execution, using `sudo` for elevated privileges where required.  
    The command is built safely using list-based arguments suitable for
    subprocess execution without shell expansion.

    Args:
        ssh (SSHConfig): SSH configuration object containing connection parameters
            (username, host, binary path, and privilege options).
        capture (CaptureConfig): Capture configuration object defining the execution
            environment and additional bpftrace arguments.

    Returns:
        List[str]: A list of command arguments ready to be passed to `subprocess.Popen`
        for starting the `bpftrace` process.

    Notes:
        - The function assumes that root privileges are typically required for `bpftrace`.
        - If `run_env` is set to `"docker"`, the command is executed remotely via SSH.
        - The `--` separator ensures that SSH does not interpret subsequent arguments.
    """

    bpftrace_script_path = capture.bpftrace_script_path or ""

    logger.info(f"[BUILD BPFTRACE CMD] Using bpftrace script: {bpftrace_script_path}")
    bpftrace_bin = getattr(ssh, "bpftrace_path", "/usr/bin/bpftrace")

    remote_cmd = []
    if ssh.sudo:
        remote_cmd += ["sudo", "-n"]

    remote_cmd += [bpftrace_bin, "-q", bpftrace_script_path]
    if capture.extra_args:
        remote_cmd += capture.extra_args

    # Executed via SSH
    if capture.run_env == "docker":
        return [
            "ssh", f"{ssh.username}@{ssh.host}",
            "--",
            *remote_cmd
        ]
    else:
        # Executed locally
        return remote_cmd
    

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


def extract_features_by_flow_from_pcap(file_obj):
    """
    Extracts flow-based features from a PCAP file using PyShark.

    This function processes the PCAP packet by packet, grouping them by flow (identified by
    source/destination IPs and ports, and protocol), and computes flow-level statistics such as:
    - packet count
    - total bytes
    - average packet size
    - flow duration
    - average TTL

    Args:
        file_obj (file-like object): The uploaded PCAP file.

    Returns:
        pandas.DataFrame: A DataFrame containing the aggregated flow features.
    """

    logger.info("[EXTRACT FLOW] Extracting features from PCAP file...")

    # Save uploaded file to a temporary .pcap file
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pcap") as tmp:
        tmp.write(file_obj.read())
        tmp_path = tmp.name

    logger.info("[EXTRACT FLOW] Temporary file created at: %s", tmp_path)

    cap = None
    flow_dict = defaultdict(list)

    try:
        # Initialize PyShark capture
        cap = pyshark.FileCapture(tmp_path, keep_packets=False)

        for i, pkt in enumerate(cap):
            try:
                # Basic packet metadata
                time = float(pkt.sniff_time.timestamp()) if hasattr(pkt, 'sniff_time') else None
                length = int(pkt.length) if hasattr(pkt, 'length') else None

                # Extract source and destination IPs
                src = pkt.ip.src if hasattr(pkt, 'ip') else None
                dst = pkt.ip.dst if hasattr(pkt, 'ip') else None

                # Extract protocol information
                proto = pkt.transport_layer or getattr(pkt, 'highest_layer', None)
                proto_name = PROTOCOL_MAP.get(str(proto), str(proto)) if proto else 'UNKNOWN'

                # Extract source and destination ports, defaulting to -1 if not available
                src_port = dst_port = -1

                if pkt.transport_layer:
                    try:
                        layer = pkt[pkt.transport_layer]
                        
                        # Use getattr to safely access srcport and dstport attributes
                        src_port = int(getattr(layer, 'srcport', -1)) if hasattr(layer, 'srcport') else -1
                        dst_port = int(getattr(layer, 'dstport', -1)) if hasattr(layer, 'dstport') else -1
                    except Exception as e:
                        logger.warning("[EXTRACT FLOW] Error retrieving ports from packet %d: %s", i + 1, str(e))

                # Extract TCP flags and TTL if available
                flags = pkt.tcp.flags if hasattr(pkt, 'tcp') and hasattr(pkt.tcp, 'flags') else None
                ttl = int(pkt.ip.ttl) if hasattr(pkt, 'ip') and hasattr(pkt.ip, 'ttl') else None

                # Create a unique key for the flow based on src, src_port, dst, dst_port, and protocol
                flow_key = (src, src_port, dst, dst_port, proto_name)
                flow_dict[flow_key].append({
                    'time': time,
                    'length': length,
                    'ttl': ttl,
                    'flags': flags
                })

            except Exception as e:
                logger.warning("[EXTRACT FLOW] Error processing packet %d: %s", i + 1, str(e))
                continue

    except Exception as e:
        logger.error("[EXTRACT FLOW] Error reading PCAP file: %s", str(e))
    finally:
        if cap:
            cap.close()
            del cap
        logger.info("[EXTRACT FLOW] Capture closed successfully")

    # Aggregate flow-level statistics
    aggregated = []
    for flow, packets in flow_dict.items():
        times = [p['time'] for p in packets if p['time'] is not None]
        lengths = [p['length'] for p in packets if p['length'] is not None]
        ttls = [p['ttl'] for p in packets if p['ttl'] is not None]

        aggregated.append({
            'src': flow[0],
            'src_port': flow[1],
            'dst': flow[2],
            'dst_port': flow[3],
            'protocol': flow[4],
            'packet_count': len(packets),
            'total_bytes': sum(lengths),
            'avg_packet_size': sum(lengths) / len(lengths) if lengths else 0,
            'flow_duration': max(times) - min(times) if times else 0,
            'avg_ttl': sum(ttls) / len(ttls) if ttls else None,
        })

    # Convert to DataFrame
    df = pd.DataFrame(aggregated)

    # Fill NaN values and replace empty strings
    df['src_port'] = df['src_port'].fillna(-1)
    df['dst_port'] = df['dst_port'].fillna(-1)
    df['protocol'] = df['protocol'].fillna('UNKNOWN').replace('', 'UNKNOWN')

    logger.info("[EXTRACT FLOW] DataFrame aggregated: %s", df)
    return df

def extract_features_by_packet_from_pcap(file_obj):
    """
    Extracts packet-level features from a PCAP file using PyShark.

    This function processes each packet in the capture individually and extracts features
    such as timestamp, length, IP addresses, ports, protocol name, TTL, etc.

    Args:
        file_obj (file-like object): The uploaded PCAP file.

    Returns:
        pandas.DataFrame: A DataFrame containing one row per packet with basic features.
    """

    logger.info("[EXTRACT PACKET] Extracting packet-level features...")

    # Save uploaded PCAP file to a temporary file
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pcap") as tmp:
        tmp.write(file_obj.read())
        tmp_path = tmp.name

    # Initialize PyShark capture
    cap = pyshark.FileCapture(tmp_path, keep_packets=False)
    packets = []

    try:
        for i, pkt in enumerate(cap):
            try:
                # Timestamp and packet length
                time = float(pkt.sniff_time.timestamp())
                length = int(pkt.length)

                # Extract source and destination IPs
                src = pkt.ip.src if hasattr(pkt, 'ip') else None
                dst = pkt.ip.dst if hasattr(pkt, 'ip') else None

                # Extract TTL
                ttl = int(pkt.ip.ttl) if hasattr(pkt, 'ip') and hasattr(pkt.ip, 'ttl') else None

                # Extract protocol information
                proto = pkt.transport_layer or getattr(pkt, 'highest_layer', None)
                proto_name = PROTOCOL_MAP.get(str(proto), str(proto)) if proto else 'UNKNOWN'

                # Extract source and destination ports, defaulting to -1 if not available
                src_port = dst_port = -1

                # Use getattr to safely access srcport and dstport attributes
                if pkt.transport_layer:
                    layer = pkt[pkt.transport_layer]
                    src_port = int(getattr(layer, 'srcport', -1))
                    dst_port = int(getattr(layer, 'dstport', -1))

                # Append packet features to the list
                packets.append({
                    'time': time,
                    'length': length,
                    'src': src,
                    'dst': dst,
                    'src_port': src_port,
                    'dst_port': dst_port,
                    'protocol': proto_name,
                    'ttl': ttl,
                })
            except Exception as e:
                logger.warning("[EXTRACT PACKET] Error in packet %d: %s", i + 1, str(e))
    finally:
        cap.close()
        del cap

    # Convert the list of packets to a DataFrame
    df = pd.DataFrame(packets)
    logger.info("[EXTRACT PACKET] DataFrame aggregated: %s", df)

    return df

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

def check_and_send_email_alerts(ip_anomaly_counter: Dict[str, int], port_anomaly_counter: Dict[int, int]) -> None:
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

def build_anomaly_description(row: pd.Series) -> str:
    """
    Builds a human-readable description of an anomaly event.

    This function generates a descriptive summary for a detected anomaly
    based on the content of a given `pandas.Series` row.  
    It supports two main contexts:
    
    1. **Network traffic anomalies** — when fields like `src`, `dst`, and `protocol`
       are present. The description includes source/destination IPs, ports,
       and protocol name.
    2. **System call anomalies** — when syscall-related counters and time window
       fields are available. The description includes the nanosecond window
       and syscall counters.

    Args:
        row (pd.Series): A pandas Series representing a single anomaly record.
            Must include either network traffic fields (`src`, `dst`, `protocol`)
            or syscall frequency columns.

    Returns:
        str: A formatted human-readable description of the anomaly.
    """
        
    # Network traffic case
    if {'src', 'dst', 'protocol'}.issubset(row.index):
        try:
            src = int_to_ip(int(row.get('src', 0)))
        except Exception:
            src = "UNDEFINED"
        try:
            dst = int_to_ip(int(row.get('dst', 0)))
        except Exception:
            dst = "UNDEFINED"

        src_port = int(row.get('src_port', -1)) if pd.notna(row.get('src_port')) else -1
        dst_port = int(row.get('dst_port', -1)) if pd.notna(row.get('dst_port')) else -1

        protocol_val = row.get('protocol')
        try:
            protocol_val = int(protocol_val)
        except Exception:
            protocol_val = str(protocol_val).strip()

        protocol_name = PROTOCOL_MAP.get(str(protocol_val), "UNKNOWN")

        return (
            f"src: {src}, "
            f"dst: {dst}, "
            f"ports: {src_port}->{dst_port}, "
            f"protocol: {protocol_name}"
        )

    # Syscalls case
    win_start = row.get('window_start_ns', None)
    win_end = row.get('window_end_ns', None)
    try:
        win_start = int(win_start) if win_start is not None and not pd.isna(win_start) else -1
    except Exception:
        win_start = -1
    try:
        win_end = int(win_end) if win_end is not None and not pd.isna(win_end) else -1
    except Exception:
        win_end = -1

    # Syscall columns = all except window markers and anomaly flag
    exclude = {'window_start_ns', 'window_end_ns', 'anomaly'}
    syscall_cols = [c for c in row.index if c not in exclude]

    parts = []
    for c in syscall_cols:
        val = row.get(c, 0)
        try:
            val = int(val) if not pd.isna(val) else 0
        except Exception:
            val = 0
        parts.append(f"{c}={val}")

    return f"window: {win_start}->{win_end}, " + ", ".join(parts)

def build_pipelines_from_components(
    model: Any,
    preprocessors: Optional[List[Any]] = None,
    *,
    model_id: str = "model_1",
    X_train: Optional[Any] = None,
) -> List[PipelineDef]:
    preprocessors = preprocessors or []
    steps: List[Tuple[str, Any]] = []

    for p in preprocessors:
        step_name = p.__class__.__name__
        steps.append((step_name, p))

    return [
        PipelineDef(
            id=model_id,
            model=model,
            steps=steps,
            X_train=X_train,
        )
    ]

def get_next_anomaly_index(scenario_uuid: str = None) -> int:
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
    if not scenario_uuid:
        return 1

    try:
        # 1) Determinar MEDIA_ROOT
        if base_dir is None:
            try:
                base_dir = getattr(settings, "MEDIA_ROOT", "./media")
            except Exception:
                base_dir = "./media"

        shap_dir = os.path.join(base_dir, "shap_local_images")
        lime_dir = os.path.join(base_dir, "lime_local_images")
        os.makedirs(shap_dir, exist_ok=True)
        os.makedirs(lime_dir, exist_ok=True)

        def _count(dir_path: str, prefix: str) -> int:
            try:
                return sum(
                    1
                    for name in os.listdir(dir_path)
                    if name.startswith(f"{prefix}_{scenario_uuid}_")
                    and name.endswith(".png")
                )
            except Exception:
                return 0

        shap_count = _count(shap_dir, "local_shap")
        lime_count = _count(lime_dir, "local_lime")

        return max(shap_count, lime_count) + 1

    except Exception:
        return 1
    
def df_from_ra_csv_lines(lines: list[str]) -> pd.DataFrame:
    out_cols = [
        "src","src_port","dst","dst_port","protocol",
        "packet_count","total_bytes","avg_packet_size",
        "flow_duration","avg_ttl"
    ]
    if not lines:
        return pd.DataFrame(columns=out_cols)

    csv_text = "\n".join(lines)

    names = ["saddr","sport","daddr","dport","proto","pkts","bytes","dur","sttl","dttl"]
    df_raw = pd.read_csv(io.StringIO(csv_text), header=None, names=names)

    # Convert numerics
    for c in ["sport","dport","pkts","bytes","dur","sttl","dttl"]:
        df_raw[c] = pd.to_numeric(df_raw[c], errors="coerce")

    out_df = pd.DataFrame({
        "src": df_raw["saddr"].astype("string"),
        "src_port": df_raw["sport"].fillna(-1).astype("int64", errors="ignore"),
        "dst": df_raw["daddr"].astype("string"),
        "dst_port": df_raw["dport"].fillna(-1).astype("int64", errors="ignore"),
        "protocol": df_raw["proto"].astype("string").fillna("UNKNOWN").replace("", "UNKNOWN"),
        "packet_count": df_raw["pkts"].fillna(0).astype("int64", errors="ignore"),
        "total_bytes": df_raw["bytes"].fillna(0).astype("int64", errors="ignore"),
        "flow_duration": df_raw["dur"].fillna(0).astype(float),
    })

    pkts = pd.to_numeric(out_df["packet_count"], errors="coerce").fillna(0)
    bytes_ = pd.to_numeric(out_df["total_bytes"], errors="coerce").fillna(0)
    out_df["avg_packet_size"] = (bytes_ / pkts.replace(0, pd.NA)).fillna(0).astype(float)

    out_df["avg_ttl"] = pd.concat([df_raw["sttl"], df_raw["dttl"]], axis=1).mean(axis=1, skipna=True)

    out_df = out_df.dropna(subset=["src","dst","protocol"], how="all")
    return out_df