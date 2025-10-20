import json
import pandas as pd
import numpy as np
import io
import re
from datetime import datetime
import time
from collections import defaultdict
import logging
from .models import *
from action_execution.policy_storage import load_alert_policies, delete_alert_policy

from sklearn.metrics import f1_score, precision_score, recall_score, accuracy_score, confusion_matrix, mean_squared_error, mean_absolute_error, r2_score
from tensorflow.keras import Sequential
from tensorflow.keras.layers import Dense, Flatten, Dropout, Conv1D, Conv2D, MaxPooling1D, AveragePooling1D, MaxPooling2D, AveragePooling2D,SimpleRNN, LSTM, GRU

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

PROCESS_PROFILE_MAP = {
    "bash": "interactive",
    "zsh": "interactive",
    "sh": "interactive",
    "python": "script",
    "python3": "script",
    "curl": "networking",
    "ssh": "remote",
    "vim": "editor",
    "Finder": "ui",
    "Safari": "ui",
    "Mail": "ui",
    # por defecto -> "generic"
}

CATEGORY_MAP = {
    # FS
    "open": "fs", "openat": "fs", "close": "fs", "read": "fs", "write": "fs",
    "stat": "fs", "lstat": "fs", "fstat": "fs", "unlink": "fs", "rename": "fs",
    "mkdir": "fs", "rmdir": "fs", "link": "fs", "symlink": "fs", "creat": "fs",
    "readlink": "fs", "chmod": "fs", "fchmod": "fs", "truncate": "fs", "ftruncate": "fs",
    # NET
    "socket": "net", "connect": "net", "accept": "net", "sendto": "net", "recvfrom": "net",
    "sendmsg": "net", "recvmsg": "net", "bind": "net", "listen": "net", "getsockname": "net",
    "getpeername": "net", "shutdown": "net", "getsockopt": "net", "setsockopt": "net",
    # PROC
    "fork": "proc", "vfork": "proc", "execve": "proc", "exit": "proc", "wait4": "proc", "kill": "proc",
    # MEM
    "mmap": "mem", "munmap": "mem", "mprotect": "mem", "brk": "mem", "mremap": "mem", "msync": "mem",
    # TIME
    "gettimeofday": "time", "nanosleep": "time", "clock_gettime": "time",
}

_KDUMP_CALL_RE = re.compile(
    r"""^\s*
        (?P<pid>\d+)\s+                      # PID
        (?P<proc>[A-Za-z0-9_\-\.]+)          # proceso (puede llevar .hilo)
        (?::)?\s*                            # ':' opcional
        (?P<ts>\d{10}(?:\.\d+)?)\s+          # timestamp epoch
        CALL\s+(?P<sys>\w+)                  # nombre de syscall
        """,
    re.VERBOSE
)

def load_config():
    """
    Loads the configuration from the frontend's config.json file.

    The config.json file is expected to be located at:
    <BASE_DIR>/frontend/src/assets/config.json

    Returns:
        dict: Parsed JSON configuration if the file is found and valid.
        None: If the file is missing or contains invalid JSON.
    """

    # Resolve the base directory two levels up from this script
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    # Construct the absolute path to the config.json file
    CONFIG_PATH = os.path.join(BASE_DIR, 'frontend', 'src', 'assets', 'config.json')

    try:
        with open(CONFIG_PATH, 'r', encoding='utf-8') as file:
            config = json.load(file)
        return config
    except FileNotFoundError:
        logger.error("[LOAD CONFIG] Error: config.json file not found at %s", CONFIG_PATH)
    except json.JSONDecodeError:
        logger.error("[LOAD CONFIG] Error: Failed to decode config.json (invalid JSON format)")

def validate_design(config, design):
    """
    Validates the structural integrity and logical rules of a visual scenario design.

    This function checks whether elements and their connections within a given design
    comply with required placement, allowed flow constraints, and configuration compatibility
    as defined in the config.json schema.

    Args:
        config (dict): Parsed JSON configuration defining valid element types.
        design (dict): Scenario design containing 'elements' and 'connections'.

    Raises:
        ValueError: If the design violates any structural or semantic rules.
    """

    # Map element IDs to their corresponding definitions
    elements = {e["id"]: e for e in design["elements"]}
    connections = design["connections"]

    # Extract IDs used in connections
    start_ids = [conn["startId"] for conn in connections]
    end_ids = [conn["endId"] for conn in connections]

    # Extract processing types from configuration sections
    processing_types = [el["type"] for el in config.get("sections", {}).get("dataProcessing", {}).get("elements", [])]
    logger.info("[VALIDATE DESIGN] Processing types: %s", processing_types)

    # Extract classification types from configuration sections
    classification_types = [el["type"] for el in config.get("sections", {}).get("dataModel", {}).get("classification", [])]
    logger.info("[VALIDATE DESIGN] Classification types: %s", classification_types)

    # Extract regression types from configuration sections
    regression_types = [el["type"] for el in config.get("sections", {}).get("dataModel", {}).get("regression", [])]
    logger.info("[VALIDATE DESIGN] Regression types: %s", regression_types)

    # Extract anomaly detection types from configuration sections
    anomaly_types = [el["type"] for el in config.get("sections", {}).get("dataModel", {}).get("anomalyDetection", [])]
    logger.info("[VALIDATE DESIGN] Anomaly detection types: %s", anomaly_types)

    # Extract explainability types from configuration sections
    explainability_types = [el["type"] for el in config.get("sections", {}).get("dataModel", {}).get("explainability", [])]
    logger.info("[VALIDATE DESIGN] Explainability types: %s", explainability_types)

    # Extract monitor types from configuration sections
    monitor_types = [el["type"] for el in config.get("sections", {}).get("dataModel", {}).get("monitoring", [])]
    logger.info("[VALIDATE DESIGN] Monitoring types: %s", monitor_types)

    # Elements that must act as both source and destination in a connection
    must_be_start_and_end = set(processing_types + classification_types + regression_types)
    splitter_types = {"DataSplitter", "CodeSplitter"}

    # Build connection maps
    forward_map = {}
    backward_map = {}
    for conn in connections:
        forward_map.setdefault(conn["startId"], []).append(conn["endId"])
        backward_map.setdefault(conn["endId"], []).append(conn["startId"])

    # Validate individual element rules
    for element_id, element in elements.items():
        el_type = element["type"]
        appears_in_start = element_id in start_ids
        appears_in_end = element_id in end_ids

        # Source-only elements
        if el_type in ["CSV", "Network"]:
            if not appears_in_start:
                raise ValueError(f"{el_type} '{element_id}' must appear as startId.")
            if appears_in_end:
                raise ValueError(f"{el_type} '{element_id}' cannot appear as endId.")

        # Sink-only elements
        elif el_type in ["ClassificationMonitor", "RegressionMonitor"]:
            if not appears_in_end:
                raise ValueError(f"{el_type} '{element_id}' must appear as endId.")
            if appears_in_start:
                raise ValueError(f"{el_type} '{element_id}' cannot appear as startId.")

        # Elements that must have both input and output
        elif el_type in must_be_start_and_end:
            if not appears_in_start:
                raise ValueError(f"Element '{element_id}' ({el_type}) should appear as startId but does not.")
            if not appears_in_end:
                raise ValueError(f"Element '{element_id}' ({el_type}) should appear as endId but does not.")

        # Validate next (outgoing) connections. After a CSV or Network element, there must be a processing or model node.
        # If it's a classification or regression model, it must be followed by a monitor node.
        next_ids = forward_map.get(element_id, [])
        next_types = [elements[nid]["type"] for nid in next_ids if nid in elements]

        valid_next_types = set(processing_types + classification_types + regression_types + anomaly_types)
        if el_type in ["CSV", "Network"]:
            if not any(nt in valid_next_types for nt in next_types):
                raise ValueError(
                    f"After '{element_id}' ({el_type}) there must be a processing or model node "
                    f"(classification/regression/anomaly). Found types: {next_types}"
                )

        if el_type in classification_types:
            if not any(nt == "ClassificationMonitor" for nt in next_types):
                raise ValueError(f"'{element_id}' ({el_type}) must be followed by a ClassificationMonitor.")

        if el_type in regression_types:
            if not any(nt == "RegressionMonitor" for nt in next_types):
                raise ValueError(f"'{element_id}' ({el_type}) must be followed by a RegressionMonitor.")

        # if el_type in anomaly_types:
        #     if not any(nt in explainability_types for nt in next_types):
        #         raise ValueError(f"'{element_id}' ({el_type}) must be followed by an explainability node.")

        # Validate previous (incoming) connections. Before a classification or regression node three must be a 
        # DataSplitter or CodeSplitter. If it's an explainability node, it must be preceded by a classification, 
        # regression, or anomaly model node.
        prev_ids = backward_map.get(element_id, [])
        prev_types = [elements[pid]["type"] for pid in prev_ids if pid in elements]

        if el_type in (classification_types + regression_types):
            if not any(pt in splitter_types for pt in prev_types):
                raise ValueError(f"Before '{element_id}' ({el_type}) there must be a DataSplitter or CodeSplitter.")
            
        if el_type in explainability_types:
            if not any(pt in (classification_types + regression_types + anomaly_types) for pt in prev_types):
                raise ValueError(
                    f"'{element_id}' ({el_type}) must be preceded by a classification, regression, or anomaly model node. "
                    f"Found previous types: {prev_types}"
                )

def import_class(full_class_name):
    """
    Dynamically imports and returns a class from its fully qualified name.

    This function is useful when class names are specified as strings in configuration
    files or dynamically determined at runtime.

    Args:
        full_class_name (str): Fully qualified class name (e.g., 'my_module.submodule.MyClass').

    Returns:
        type: The class object referenced by the input string.

    Raises:
        ImportError: If the module cannot be imported.
        AttributeError: If the class is not found in the module.
    """

    # Split the full path into module and class name
    module_name, class_name = full_class_name.rsplit(".", 1)
    module = importlib.import_module(module_name)

    # Retrieve and return the class from the module
    return getattr(module, class_name)

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

def build_neural_network(input_shape, model_type, parameters):
    """
    Builds and compiles a neural network model based on the given type and parameters.

    Supported model types:
        - "CNNClassifier": Builds a convolutional neural network (1D or 2D).
        - "RNNClassifier": Builds a recurrent neural network using SimpleRNN, LSTM, or GRU.
        - "MLPClassifier": Builds a multi-layer perceptron (dense network).

    Args:
        input_shape (tuple): Shape of the input data (excluding batch size).
        model_type (str): Type of model to build (e.g., "CNNClassifier").
        parameters (dict): Configuration dictionary with layer and model settings.

    Returns:
        keras.Model: A compiled Keras model ready for training.

    Raises:
        ValueError: If the provided model_type is not supported.
    """

    model = Sequential()
    logger.info("[BUILD NN] Building neural network model: %s", model_type)
    logger.info("[BUILD NN] Model parameters: %s", parameters)

    # Case for CNNClassifier
    if model_type == "CNNClassifier":
        for i, layer in enumerate(parameters.get("conv_layers", [])):
            # Determine the convolutional layer type based on the configuration
            conv_cls = Conv1D if parameters["conv_type"] == "Conv1D" else Conv2D
            kwargs = {
                "filters": layer["filters"],
                "kernel_size": layer["kernel_size"],
                "activation": layer["activation"]
            }
            if i == 0:
                kwargs["input_shape"] = input_shape
            model.add(conv_cls(**kwargs))

            # Add pooling layer if enabled
            if layer.get("use_pooling") == "true":
                pool_type = layer.get("pool_type", "max").lower()
                if parameters["conv_type"] == "Conv1D":
                    pool_cls = MaxPooling1D if pool_type == "max" else AveragePooling1D
                else:
                    pool_cls = MaxPooling2D if pool_type == "max" else AveragePooling2D
                model.add(pool_cls(pool_size=layer["pool_size"]))

            # Add dropout layer if specified
            if layer.get("use_dropout") == "true":
                model.add(Dropout(rate=layer["dropout_rate"]))

        # Add flattening layer if specified
        if parameters.get("use_flatten", "true") == "true":
            model.add(Flatten())
        model.add(Dense(parameters["dense_units"], activation=parameters["output_activation"]))

    # Case for RNNClassifier
    elif model_type == "RNNClassifier":
        for i, layer in enumerate(parameters.get("rnn_layers", [])):
            # Determine the RNN cell type based on the configuration
            rnn_cls = {"SimpleRNN": SimpleRNN, "LSTM": LSTM, "GRU": GRU}[parameters["rnn_cell_type"]]
            kwargs = {
                "units": layer["units"],
                "activation": layer["activation"],
                "return_sequences": layer["return_sequences"] == "true",
                "go_backwards": layer.get("go_backwards", "false") == "true"
            }

            # Add dropout and recurrent dropout if specified
            if layer.get("use_dropout") == "true":
                kwargs["dropout"] = layer["dropout_rate"]
            if layer.get("use_recurrent_dropout") == "true":
                kwargs["recurrent_dropout"] = layer["recurrent_dropout_rate"]
            if i == 0:
                kwargs["input_shape"] = input_shape
            model.add(rnn_cls(**kwargs))

        # Add flattening layer if specified
        if parameters.get("use_dense", "true") == "true":
            model.add(Dense(parameters["dense_units"], activation=parameters["output_activation"]))

    # Case for MLPClassifier
    elif model_type == "MLPClassifier":
        model.add(Flatten(input_shape=input_shape))
        for layer in parameters.get("hidden_layers", []):
            model.add(Dense(layer["units"], activation=layer["activation"]))

            # Add dropout layer if specified
            if layer.get("use_dropout") == "true":
                model.add(Dropout(rate=layer["dropout_rate"]))

        # Add output activation layer
        model.add(Dense(parameters["dense_units"], activation=parameters["output_activation"]))

    else:
        raise ValueError(f"Unsupported model type: {model_type}")

    # Compile the model with the specified optimizer and loss function
    model.compile(
        optimizer=parameters["optimizer"],
        loss=parameters["loss"],
        metrics=["accuracy"]
    )
    return model


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
    
def extract_parameters(properties, params):
    """
    Extracts and converts parameter values from a dynamic configuration form.

    This function:
        - Converts string values like "true", "false", "none", and numeric strings to appropriate Python types.
        - Handles "conditional-select" types where a custom value can be supplied.
        - Removes parameters that are not active based on conditional dependencies.

    Args:
        properties (list): A list of property definitions from the node configuration.
        params (dict): A dictionary of parameter values submitted by the user.

    Returns:
        dict: A dictionary of cleaned and type-correct parameter values.
    """

    extracted = {}

    # Stores user-defined custom values for conditional-selects
    custom_params = {} 

    for prop in properties:
        prop_name = prop["name"]
        if prop_name in params:
            value = params[prop_name]
            
            # Convert string values to appropriate types
            if isinstance(value, str):
                if value.lower() == "none":
                    extracted[prop_name] = None
                elif value.lower() == "true":
                    extracted[prop_name] = True
                elif value.lower() == "false":
                    extracted[prop_name] = False
                else:
                    try:
                        extracted[prop_name] = int(value)
                    except ValueError:
                        try:
                            extracted[prop_name] = float(value)
                        except ValueError:
                            extracted[prop_name] = value
            else:
                extracted[prop_name] = value

            # Handle custom value in conditional-selects
            if prop.get("type") == "conditional-select" and value == "custom":
                dependent_prop = next(
                    (p for p in properties if p.get("conditional", {}).get("dependsOn") == prop_name),
                    None
                )
                if dependent_prop and params.get(dependent_prop["name"]):
                    custom_params[prop_name] = params[dependent_prop["name"]]

    # Overwrite main param with the custom value, and clean up any dependent duplicates
    for main_param, custom_value in custom_params.items():
        extracted[main_param] = int(custom_value)
        dependent_prop_name = f"custom_{main_param}"
        if dependent_prop_name in extracted:
            del extracted[dependent_prop_name]

    # Remove conditionally inactive parameters
    for prop in properties:
        if "conditional" in prop:
            depends_on = prop["conditional"].get("dependsOn")
            
            condition_values = prop["conditional"].get("values", [])
            condition_value = prop["conditional"].get("value", None)

            if depends_on and depends_on in extracted:
                parent_value = extracted[depends_on]
                
                # Remove the param if the condition does not match
                if condition_value:
                    if parent_value != condition_value:
                        extracted.pop(prop["name"], None)
                elif condition_values:
                    if parent_value not in condition_values:
                        extracted.pop(prop["name"], None)

    return extracted

def calculate_classification_metrics(y_true, y_pred, metrics_config):
    """
    Calculates selected classification metrics based on user configuration.

    Supported metrics (enabled via metrics_config):
        - Accuracy
        - Precision (weighted)
        - Recall (weighted)
        - F1 Score (weighted)
        - Confusion Matrix

    Args:
        y_true (list or array-like): Ground truth class labels.
        y_pred (list or array-like): Predicted class labels.
        metrics_config (dict): Dictionary indicating which metrics to compute (bool flags).

    Returns:
        dict: Dictionary containing the selected metrics and their values.
    """

    logger.info("[CLF METRICS] Metrics: %s", metrics_config)
    logger.info("[CLF METRICS]y_true: %s", y_true)
    logger.info("[CLF METRICS]y_pred: %s", y_pred)

    metrics = {}

    # Accuracy if requested
    if metrics_config.get("accuracy"):
         metrics["accuracy"] = round(accuracy_score(y_true, y_pred), 2)
    
    # Precision if requested
    if metrics_config.get("precision"):
        metrics["precision"] = round(precision_score(y_true, y_pred, average="weighted", zero_division=0), 2)

    # Recall if requested
    if metrics_config.get("recall"):
        metrics["recall"] = round(recall_score(y_true, y_pred, average="weighted", zero_division=0), 2)

    # F1 Score if requested
    if metrics_config.get("f1Score"):
        metrics["f1_score"] = round(f1_score(y_true, y_pred, average="weighted", zero_division=0), 2)

    # Confusion Matrix if requested
    if metrics_config.get("confusionMatrix"):
        metrics["confusion_matrix"] = confusion_matrix(y_true, y_pred).tolist()

    return metrics

def calculate_regression_metrics(y_true, y_pred, metrics_config):
    """
    Calculates selected regression metrics based on user configuration.

    Supported metrics (enabled via metrics_config):
        - MSE (Mean Squared Error)
        - RMSE (Root Mean Squared Error)
        - MAE (Mean Absolute Error)
        - R² Score (Coefficient of Determination)
        - MSLE (Mean Squared Logarithmic Error)

    Args:
        y_true (list or array-like): Ground truth target values.
        y_pred (list or array-like): Predicted target values.
        metrics_config (dict): Dictionary indicating which metrics to compute (bool flags).

    Returns:
        dict: Dictionary containing the selected metrics and their values.
    """

    logger.info("[REGRESSION METRICS]Metrics: %s", metrics_config)
    logger.info("[REGRESSION METRICS]y_true: %s", y_true)
    logger.info("[REGRESSION METRICS]y_pred: %s", y_pred)

    metrics = {}
    
    # MSE if requested
    if metrics_config.get("mse"):
        metrics["mse"] = round(mean_squared_error(y_true, y_pred), 2)
    
    # RMSE if requested
    if metrics_config.get("rmse"):
        metrics["rmse"] = round(np.sqrt(metrics["mse"]), 2)
    
    # MAE if requested
    if metrics_config.get("mae"):
        metrics["mae"] = round(mean_absolute_error(y_true, y_pred), 2)
    
    # R² Score if requested
    if metrics_config.get("r2"):
        metrics["r2"] = round(r2_score(y_true, y_pred), 2)
    
    # MSLE if requested
    if metrics_config.get("msle"):
        metrics["msle"] = round(mean_squared_error(np.log1p(y_true), np.log1p(y_pred)), 2)
    
    return metrics

def save_classification_metrics(scenario_model, model_name, metrics, execution):
    """
    Persists classification metrics to the database for a given model and execution.

    Args:
        scenario_model (ScenarioModel): The scenario model instance associated with the metrics.
        model_name (str): Name of the model used for prediction.
        metrics (dict): Dictionary containing calculated classification metrics.
        execution (integer): The execution record tied to this metric entry.

    Returns:
        None
    """

    ClassificationMetric.objects.create(
        scenario_model=scenario_model,
        execution=execution,
        model_name=model_name,
        accuracy=metrics.get("accuracy"),
        precision=metrics.get("precision"),
        recall=metrics.get("recall"),
        f1_score=metrics.get("f1_score"),
        confusion_matrix=json.dumps(metrics.get("confusion_matrix")),
    )

def save_regression_metrics(scenario_model, model_name, metrics, execution):
    """
    Persists regression metrics to the database for a given model and execution.

    Args:
        scenario_model (ScenarioModel): The scenario model instance associated with the metrics.
        model_name (str): Name of the model used for prediction.
        metrics (dict): Dictionary containing calculated regression metrics.
        execution (integer): The execution record tied to this metric entry.

    Returns:
        None
    """
    RegressionMetric.objects.create(
        scenario_model=scenario_model,
        execution=execution,
        model_name=model_name,
        mse=metrics.get("mse"),
        rmse=metrics.get("rmse"),
        mae=metrics.get("mae"),
        r2=metrics.get("r2"),
        msle=metrics.get("msle"),
    )

def save_anomaly_metrics(scenario_model, model_name, feature_name, feature_values, anomalies, execution, production, anomaly_details=None, global_shap_images=None, local_shap_images=None, global_lime_images=None, local_lime_images=None
):
    """
    Persists anomaly detection metrics and metadata to the database.

    This includes anomaly positions, associated feature values, optional SHAP/LIME
    explainability images, and whether the execution occurred in production mode.

    Args:
        scenario_model (ScenarioModel): The scenario model instance associated with the anomalies.
        model_name (str): Name of the anomaly detection model used.
        feature_name (str): The name of the feature being monitored.
        feature_values (list or array): Values of the feature during detection.
        anomalies (list): Indices or positions of detected anomalies.
        execution (integer): The execution record tied to this detection.
        production (bool): Indicates if this was a production execution.
        anomaly_details (Any, optional): Additional anomaly info (e.g., packet data or text).
        global_shap_images (list, optional): List of SHAP global explanation image paths or URLs.
        local_shap_images (list, optional): List of SHAP local explanation image paths or URLs.
        global_lime_images (list, optional): List of LIME global explanation image paths or URLs.
        local_lime_images (list, optional): List of LIME local explanation image paths or URLs.

    Returns:
        None
    """

    # Use empty lists as defaults if not provided
    global_shap_images = global_shap_images or []
    local_shap_images = local_shap_images or []
    global_lime_images = global_lime_images or []
    local_lime_images = local_lime_images or []

    # Prepare the payload for anomalies
    anomaly_payload = {
        'values': feature_values.tolist() if not production else feature_values,
        'anomaly_indices': anomalies
    }

    AnomalyMetric.objects.create(
        scenario_model=scenario_model,
        model_name=model_name,
        feature_name=feature_name,
        anomalies=anomaly_payload,
        execution=execution,
        production=production,
        anomaly_details=anomaly_details,
        global_shap_images=global_shap_images,
        local_shap_images=local_shap_images,
        global_lime_images=global_lime_images,
        local_lime_images=local_lime_images
    )


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

def save_shap_bar_global(
    shap_values, scenario_uuid, model_name, class_names=None, label=None, selected_classes=None
) -> str:
    """
    Generates and saves global SHAP bar plots from SHAP values.

    If `shap_values` contains 3 dimensions (e.g., [samples, features, classes]),
    it generates one plot per class (unless filtered via `selected_classes`).
    Otherwise, it generates a single global plot.

    Args:
        shap_values (shap.Explanation or ndarray): SHAP values array.
        scenario_uuid (str): Unique identifier for the scenario.
        model_name (str): Name of the model associated with the plot.
        class_names (list, optional): List of class names (for multiclass SHAP).
        label (str, optional): Label to include in the filename for non-multiclass.
        selected_classes (list, optional): If provided, only these classes are plotted.

    Returns:
        str or list: Relative path(s) to the saved SHAP image(s), or empty string on failure.
    """

    output_dir = os.path.join(settings.MEDIA_ROOT, "shap_global_images")
    os.makedirs(output_dir, exist_ok=True)

    try:
        # Normalize class names
        if class_names is not None:
            if isinstance(class_names, np.ndarray):
                class_names = class_names.tolist()
            class_names = [str(c).replace(" ", "_").replace("/", "_") for c in class_names]

        # Multiclass SHAP values: shape [samples, features, classes]
        if len(shap_values.shape) == 3:
            n_classes = shap_values.shape[2]
            paths = []

            for class_idx in range(n_classes):
                class_label = (
                    class_names[class_idx] if class_names and class_idx < len(class_names)
                    else f"class_{class_idx}"
                )

                if selected_classes and class_label not in selected_classes:
                    continue

                try:
                    plt.figure()
                    shap.plots.bar(shap_values[:, :, class_idx], show=False)

                    output_filename = f"global_shap_{scenario_uuid}_{model_name}_{class_label}.png"
                    output_path = os.path.join(output_dir, output_filename)

                    plt.tight_layout()
                    plt.savefig(output_path, bbox_inches='tight')
                    plt.close()

                    logger.info(f"[SHAP GLOBAL] Plot saved: {output_path}")
                    paths.append(f"shap_global_images/{output_filename}")
                except Exception as e:
                    logger.warning(f"[SHAP GLOBAL] Failed to save plot for class {class_label}: {e}")

            return paths if paths else ""

        # Single class SHAP values: shape [samples, features]
        else:
            plt.figure()
            shap.plots.bar(shap_values, show=False)

            suffix = f"_{label}" if label else ""
            output_filename = f"global_shap_{scenario_uuid}{suffix}.png"
            output_path = os.path.join(output_dir, output_filename)

            plt.tight_layout()
            plt.savefig(output_path, bbox_inches='tight')
            plt.close()

            logger.info(f"[SHAP GLOBAL] Plot saved: {output_path}")
            return f"shap_global_images/{output_filename}"

    except Exception as e:
        logger.warning(f"[SHAP GLOBAL] Error while saving SHAP plot: {e}")
        return ""

def save_lime_bar_global(mean_weights: dict, scenario_uuid: str) -> str:
    """
    Generates and saves a horizontal bar chart of global LIME feature importances.

    Args:
        mean_weights (dict): A dictionary of features and their mean absolute weights.
        scenario_uuid (str): Unique identifier of the scenario, used in the output filename.

    Returns:
        str: Relative path to the saved image file, or an empty string if saving fails.
    """
    output_dir = os.path.join(settings.MEDIA_ROOT, "lime_global_images")
    os.makedirs(output_dir, exist_ok=True)

    try:
        # Sort features by importance (descending)
        features, values = zip(*sorted(mean_weights.items(), key=lambda x: x[1], reverse=True))

        # Plot the LIME bar chart
        plt.figure(figsize=(10, 6))
        plt.barh(features[::-1], values[::-1])
        plt.xlabel("Mean absolute weight (LIME)")
        plt.title("Global LIME Feature Importance")
        plt.tight_layout()

        # Save the plot
        output_filename = f"global_lime_{scenario_uuid}.png"
        output_path = os.path.join(output_dir, output_filename)
        plt.savefig(output_path, bbox_inches="tight")
        plt.close()

        logger.info(f"[LIME GLOBAL] Plot saved at: {output_path}")
        return f"lime_global_images/{output_filename}"

    except Exception as e:
        logger.warning(f"[LIME GLOBAL] Error while saving plot: {e}")
        return ""
    
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

def topological_sort(elements, connections):
    """
    Performs a topological sort on a set of elements based on directed connections.

    This function is used to determine a valid execution order of nodes in a scenario
    where the order is defined by their dependencies (i.e., connections). It implements
    Kahn's algorithm for topological sorting.

    Args:
        elements (list): List of all element IDs in the scenario.
        connections (list): List of connection dictionaries, each with 'startId' and 'endId'.

    Returns:
        list: A list of element IDs sorted in topological order.
    """

    # Build adjacency list and in-degree count for each node
    adj = defaultdict(list)
    in_degree = defaultdict(int)

    # Populate the adjacency list and in-degree map based on connections
    for conn in connections:
        adj[conn["startId"]].append(conn["endId"])
        in_degree[conn["endId"]] += 1
        in_degree.setdefault(conn["startId"], 0)

    # Start with all nodes that have no incoming edges (i.e., in-degree == 0)
    queue = [node for node, deg in in_degree.items() if deg == 0]
    sorted_order = []

    # Process nodes in topological order
    while queue:
        node = queue.pop(0)
        sorted_order.append(node)

        # Reduce in-degree for children and add them to the queue if they have no remaining dependencies
        for neighbor in adj[node]:
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)

    return sorted_order

def build_pipelines_from_design(design, scenario_uuid, config, base_path):
    """
    Constructs execution pipelines for machine learning models based on a visual design.

    This function parses the scenario design (nodes and connections), performs a topological sort,
    and reconstructs preprocessing pipelines by tracing upstream nodes connected to each model.
    Only elements matching known model types are processed.

    Args:
        design (dict): Dictionary containing elements and their connections in the scenario.
        scenario_uuid (str): Unique identifier for the current scenario.
        config (dict): Configuration containing the list of valid model types per section.
        base_path (str): Filesystem path where serialized (.pkl) components are stored.

    Returns:
        list: A list of tuples, each containing:
              - element_id (str): The ID of the model node.
              - model_instance: The loaded model object.
              - pipeline_steps (list): List of (type, instance) tuples for preprocessing.
              - X_train (optional): Training data used (if available) for explainability.
    """

    # Map element IDs to their definitions for quick lookup
    elements = {e["id"]: e for e in design["elements"]}
    connections = design["connections"]

    # Build a map of all nodes that point to a given node (for reverse traversal)
    prev_map = defaultdict(list)
    for conn in connections:
        prev_map[conn["endId"]].append(conn["startId"])

    # Get a valid processing order using topological sort
    sorted_order = topological_sort(elements, connections)

    # Collect all known model types from the config
    model_types = set()
    for section in config["sections"].values():
        for key in ["classification", "regression", "anomalyDetection"]:
            for model in section.get(key, []):
                model_types.add(model["type"])

    pipelines = []

    # Traverse the sorted nodes and build pipelines for each model node
    for element_id in sorted_order:
        element = elements[element_id]
        el_type = element["type"]

        # Only build pipeline for recognized model types
        if el_type in model_types:
            pipeline_steps = []
            visited = set()
            stack = [element_id]

            # Traverse upstream to collect all connected preprocessing steps
            while stack:
                node = stack.pop()
                if node in visited:
                    continue
                visited.add(node)

                for prev_id in prev_map.get(node, []):
                    stack.append(prev_id)
                    prev_type = elements[prev_id]["type"]

                    # Load the component from disk if it exists
                    pkl_path = os.path.join(base_path, f'{prev_id}_{scenario_uuid}.pkl')
                    if os.path.exists(pkl_path):
                        instance = joblib.load(pkl_path)
                        pipeline_steps.insert(0, (prev_type, instance))

            # Load the actual model instance
            model_path = os.path.join(base_path, f'{element_id}_{scenario_uuid}.pkl')
            if os.path.exists(model_path):
                model_bundle = joblib.load(model_path)

                # Extract model and optional training data
                if isinstance(model_bundle, dict):
                    model_instance = model_bundle.get("model")
                    X_train = model_bundle.get("X_train")
                else:
                    model_instance = model_bundle
                    X_train = None

                # Append the complete pipeline
                pipelines.append((element_id, model_instance, pipeline_steps, X_train))

    return pipelines

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
    image_counter = get_next_anomaly_index(scenario_model)
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

    image_counter = get_next_anomaly_index(scenario_model)
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


def get_next_anomaly_index(scenario_model):
    """
    Get the next available index for anomaly identification based on how many
    anomaly records have already been stored in production for the given scenario model.

    Args:
        scenario_model: The scenario model instance associated with the execution.

    Returns:
        int: The next sequential anomaly index.
    """
    # Count all existing anomalies for the current scenario model and execution in production mode
    current = AnomalyMetric.objects.filter(
        scenario_model=scenario_model,
        execution=scenario_model.execution,
        production=True
    ).count()

    # Return the next available index
    return current + 1

def _clean_json_values(values):
    """
    Convierte un array/lista a una lista JSON-segura:
    - ±inf -> NaN -> None
    - NaN -> None
    - numpy.* -> tipos nativos (float/int/bool/str)
    """
    # Acepta list/ndarray/Series
    s = pd.Series(values, copy=False)

    # Sustituir ±inf por NaN
    s = s.replace([np.inf, -np.inf], np.nan)

    cleaned = []
    for x in s.tolist():
        if pd.isna(x):
            cleaned.append(None)
        elif isinstance(x, (np.floating, float)):
            cleaned.append(float(x))
        elif isinstance(x, (np.integer, int)):
            cleaned.append(int(x))
        elif isinstance(x, (np.bool_, bool)):
            cleaned.append(bool(x))
        elif isinstance(x, (str,)):
            cleaned.append(x)
        else:
            # Último recurso: convertir a string para no romper JSON
            cleaned.append(str(x))
    return cleaned


def _process_profile_from_name(proc_name: str) -> str:
    return PROCESS_PROFILE_MAP.get(proc_name, "generic")

def _category_from_syscall(sc: str) -> str:
    return CATEGORY_MAP.get(sc, "other")

def extract_features_syscalls_macOS(file_obj) -> pd.DataFrame:
    """
    Lee un log de syscalls (salida de `kdump -T`) desde un file-like object (binario o texto)
    y devuelve un DataFrame con las 9 features requeridas.

    Espera líneas 'CALL ...' con timestamp epoch. Si no hay timestamp, genera uno relativo.
    """
    # Asegurar lectura en texto aunque venga 'rb'
    if isinstance(file_obj, io.BufferedReader) or "b" in getattr(file_obj, "mode", ""):
        stream = io.TextIOWrapper(file_obj, encoding="utf-8", errors="ignore")
        need_detach = True
    else:
        stream = file_obj
        need_detach = False

    rows = []
    first_seen_time = None
    fallback_start = time.time()

    try:
        for raw in stream:
            line = raw.rstrip("\n")
            m = _KDUMP_CALL_RE.match(line)
            if not m:
                # ignorar líneas RET u otros eventos
                continue

            pid = int(m.group("pid"))
            proc = m.group("proc")
            sysc = m.group("sys").lower()
            ts_raw = m.group("ts")

            if ts_raw:
                ts_epoch = float(ts_raw)
            else:
                # muy raro en -T; fallback relativo si faltara
                now = time.time()
                if first_seen_time is None:
                    first_seen_time = now
                ts_epoch = fallback_start + (now - first_seen_time)

            rows.append({
                "timestamp_epoch": ts_epoch,
                "pid": pid,
                "process_name": proc,
                "syscall_name": sysc,
            })
    finally:
        # Evitar cerrar el file_obj original si nos lo pasan abierto por Django
        if need_detach:
            try:
                stream.detach()
            except Exception:
                pass

    if not rows:
        # DataFrame vacío con columnas esperadas
        return pd.DataFrame(columns=[
            "timestamp_epoch","pid","process_profile","syscall_name","category",
            "seq_no_pid","inter_arrival_ms","hour_of_day","weekday"
        ])

    df = pd.DataFrame(rows)

    # Enriquecimientos
    df["process_profile"] = df["process_name"].apply(_process_profile_from_name)
    df["category"] = df["syscall_name"].apply(_category_from_syscall)

    # Orden estable por pid y tiempo
    df = df.sort_values(["pid", "timestamp_epoch"], kind="stable").reset_index(drop=True)

    # Secuencia por PID
    df["seq_no_pid"] = df.groupby("pid").cumcount()

    # Inter-arrival por PID (ms)
    df["inter_arrival_ms"] = (
        df.groupby("pid")["timestamp_epoch"].diff().fillna(0.0) * 1000.0
    )

    # Hora del día y día de la semana
    df["hour_of_day"] = df["timestamp_epoch"].apply(lambda t: datetime.fromtimestamp(t).hour)
    df["weekday"] = df["timestamp_epoch"].apply(lambda t: datetime.fromtimestamp(t).weekday())  # 0=Lunes

    # Selección y orden final de columnas
    df_final = df[[
        "timestamp_epoch",
        "pid",
        "process_profile",
        "syscall_name",
        "category",
        "seq_no_pid",
        "inter_arrival_ms",
        "hour_of_day",
        "weekday",
    ]].copy()

    return df_final

def extract_features_syscalls_linux(file_obj) -> pd.DataFrame:
    """
    Lee un log de syscalls (salida de `kdump -T`) desde un file-like object (binario o texto)
    y devuelve un DataFrame con las 9 features requeridas.

    Espera líneas 'CALL ...' con timestamp epoch. Si no hay timestamp, genera uno relativo.
    """
    # Asegurar lectura en texto aunque venga 'rb'
    if isinstance(file_obj, io.BufferedReader) or "b" in getattr(file_obj, "mode", ""):
        stream = io.TextIOWrapper(file_obj, encoding="utf-8", errors="ignore")
        need_detach = True
    else:
        stream = file_obj
        need_detach = False

    rows = []
    first_seen_time = None
    fallback_start = time.time()

    try:
        for raw in stream:
            line = raw.rstrip("\n")
            m = _KDUMP_CALL_RE.match(line)
            if not m:
                # ignorar líneas RET u otros eventos
                continue

            pid = int(m.group("pid"))
            proc = m.group("proc")
            sysc = m.group("sys").lower()
            ts_raw = m.group("ts")

            if ts_raw:
                ts_epoch = float(ts_raw)
            else:
                # muy raro en -T; fallback relativo si faltara
                now = time.time()
                if first_seen_time is None:
                    first_seen_time = now
                ts_epoch = fallback_start + (now - first_seen_time)

            rows.append({
                "timestamp_epoch": ts_epoch,
                "pid": pid,
                "process_name": proc,
                "syscall_name": sysc,
            })
    finally:
        # Evitar cerrar el file_obj original si nos lo pasan abierto por Django
        if need_detach:
            try:
                stream.detach()
            except Exception:
                pass

    if not rows:
        # DataFrame vacío con columnas esperadas
        return pd.DataFrame(columns=[
            "timestamp_epoch","pid","process_profile","syscall_name","category",
            "seq_no_pid","inter_arrival_ms","hour_of_day","weekday"
        ])

    df = pd.DataFrame(rows)

    # Enriquecimientos
    df["process_profile"] = df["process_name"].apply(_process_profile_from_name)
    df["category"] = df["syscall_name"].apply(_category_from_syscall)

    # Orden estable por pid y tiempo
    df = df.sort_values(["pid", "timestamp_epoch"], kind="stable").reset_index(drop=True)

    # Secuencia por PID
    df["seq_no_pid"] = df.groupby("pid").cumcount()

    # Inter-arrival por PID (ms)
    df["inter_arrival_ms"] = (
        df.groupby("pid")["timestamp_epoch"].diff().fillna(0.0) * 1000.0
    )

    # Hora del día y día de la semana
    df["hour_of_day"] = df["timestamp_epoch"].apply(lambda t: datetime.fromtimestamp(t).hour)
    df["weekday"] = df["timestamp_epoch"].apply(lambda t: datetime.fromtimestamp(t).weekday())  # 0=Lunes

    # Selección y orden final de columnas
    df_final = df[[
        "timestamp_epoch",
        "pid",
        "process_profile",
        "syscall_name",
        "category",
        "seq_no_pid",
        "inter_arrival_ms",
        "hour_of_day",
        "weekday",
    ]].copy()

    return df_final