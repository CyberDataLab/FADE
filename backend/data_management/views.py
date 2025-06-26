# Create your views here.
from django.shortcuts import render
import csv
import pyshark
from django.core.files.base import ContentFile
from io import StringIO
import os
import joblib
import subprocess
from django.conf import settings
from rest_framework.parsers import MultiPartParser, JSONParser
from rest_framework.decorators import api_view, permission_classes, parser_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from .models import Scenario, File, AnomalyDetector, ClassificationMetric, RegressionMetric, AnomalyMetric
from accounts.models import CustomUser
from .serializers import ScenarioSerializer
from django.http import JsonResponse
from .models import DataController, DataReceiver, DataFilter, DataStorage, DataMixer, DataSync
import logging
import json
import pandas as pd
import numpy as np
import copy
import socket
import struct
import importlib
import shap
import matplotlib.pyplot as plt
from celery import shared_task
from collections import defaultdict
from sklearn.model_selection import train_test_split
from sklearn.metrics import f1_score, precision_score, recall_score, accuracy_score, confusion_matrix, mean_squared_error, mean_absolute_error, r2_score
from tensorflow.keras import Sequential
from tensorflow.keras.layers import Dense, Flatten, Dropout, Conv1D, Conv2D, MaxPooling1D, MaxPooling2D, SimpleRNN, LSTM, GRU
from tensorflow.keras.utils import to_categorical

logger = logging.getLogger('backend')

thread_controls = {}

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

def load_config():
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    CONFIG_PATH = os.path.join(BASE_DIR, 'frontend', 'src', 'assets', 'config.json')

    try:
        with open(CONFIG_PATH, 'r', encoding='utf-8') as file:
            config = json.load(file)
        return config
    except FileNotFoundError:
        logger.error(" Error: Archivo config.json no encontrado en %s", CONFIG_PATH)
    except json.JSONDecodeError:
        logger.error("Error: No se pudo decodificar el archivo config.json")

def validate_design(config, design):
    elements = {e["id"]: e for e in design["elements"]}
    connections = design["connections"]

    start_ids = [conn["startId"] for conn in connections]
    end_ids = [conn["endId"] for conn in connections]

    processing_types = [el["type"] for el in config.get("sections", {}).get("dataProcessing", {}).get("elements", [])]
    logger.info("Tipos de procesamiento: %s", processing_types)
    classification_types = [el["type"] for el in config.get("sections", {}).get("dataModel", {}).get("classification", [])]
    logger.info("Tipos de clasificación: %s", classification_types)
    regression_types = [el["type"] for el in config.get("sections", {}).get("dataModel", {}).get("regression", [])]
    logger.info("Tipos de regresión: %s", regression_types)
    anomaly_types = [el["type"] for el in config.get("sections", {}).get("dataModel", {}).get("anomalyDetection", [])]
    logger.info("Tipos de anomalía: %s", anomaly_types)
    explainability_types = [el["type"] for el in config.get("sections", {}).get("dataModel", {}).get("explainability", [])]
    logger.info("Tipos de explicabilidad: %s", explainability_types)
    monitor_types = [el["type"] for el in config.get("sections", {}).get("dataModel", {}).get("monitoring", [])]
    logger.info("Tipos de monitorización: %s", monitor_types)

    must_be_start_and_end = set(processing_types + classification_types + regression_types)
    splitter_types = {"DataSplitter", "CodeSplitter"}

    forward_map = {}
    backward_map = {}
    for conn in connections:
        forward_map.setdefault(conn["startId"], []).append(conn["endId"])
        backward_map.setdefault(conn["endId"], []).append(conn["startId"])

    for element_id, element in elements.items():
        el_type = element["type"]
        appears_in_start = element_id in start_ids
        appears_in_end = element_id in end_ids

        if el_type in ["CSV", "Network"]:
            if not appears_in_start:
                raise ValueError(f"El {el_type} '{element_id}' no aparece como startId.")
            if appears_in_end:
                raise ValueError(f"El {el_type} '{element_id}' no puede aparecer como endId.")

        elif el_type in ["ClassificationMonitor", "RegressionMonitor"]:
            if not appears_in_end:
                raise ValueError(f"El {el_type} '{element_id}' debe ser endId.")
            if appears_in_start:
                raise ValueError(f"El {el_type} '{element_id}' no puede ser startId.")

        elif el_type in must_be_start_and_end:
            if not appears_in_start:
                raise ValueError(f"El elemento '{element_id}' ({el_type}) debería aparecer como startId y no lo hace.")
            if not appears_in_end:
                raise ValueError(f"El elemento '{element_id}' ({el_type}) debería aparecer como endId y no lo hace.")

        next_ids = forward_map.get(element_id, [])
        next_types = [elements[nid]["type"] for nid in next_ids if nid in elements]

        valid_next_types = set(processing_types + classification_types + regression_types + anomaly_types)
        if el_type in ["CSV", "Network"]:
            if not any(nt in valid_next_types for nt in next_types):
                raise ValueError(
                    f"Después de '{element_id}' ({el_type}) debe seguir un nodo de procesamiento o modelo "
                    f"(clasificación/regresión/anomalía). Tipos siguientes encontrados: {next_types}"
                )

        if el_type in classification_types:
            if not any(nt == "ClassificationMonitor" for nt in next_types):
                raise ValueError(f"Después de '{element_id}' ({el_type}) debe seguir un ClassificationMonitor.")

        if el_type in regression_types:
            if not any(nt == "RegressionMonitor" for nt in next_types):
                raise ValueError(f"Después de '{element_id}' ({el_type}) debe seguir un RegressionMonitor.")
        '''
        if el_type in anomaly_types:
            if not any(nt in explainability_types for nt in next_types):
                raise ValueError(f"Después de '{element_id}' ({el_type}) debe seguir un nodo de explainability.")
        '''
        prev_ids = backward_map.get(element_id, [])
        prev_types = [elements[pid]["type"] for pid in prev_ids if pid in elements]

        if el_type in (classification_types + regression_types):
            if not any(pt in splitter_types for pt in prev_types):
                raise ValueError(f"Antes de '{element_id}' ({el_type}) debe haber un DataSplitter o CodeSplitter.")

def import_class(full_class_name):
    module_name, class_name = full_class_name.rsplit(".", 1)
    module = importlib.import_module(module_name)
    return getattr(module, class_name)

import tempfile

def build_neural_network(input_shape, model_type, parameters):
    model = Sequential()
    logger.info("Construyendo modelo de red neuronal: %s", model_type)
    logger.info("Parámetros del modelo: %s", parameters)

    if model_type == "CNNClassifier":
        for i, layer in enumerate(parameters.get("conv_layers", [])):
            conv_cls = Conv1D if parameters["conv_type"] == "Conv1D" else Conv2D
            kwargs = {
                "filters": layer["filters"],
                "kernel_size": layer["kernel_size"],
                "activation": layer["activation"]
            }
            if i == 0:
                kwargs["input_shape"] = input_shape
            model.add(conv_cls(**kwargs))
            if layer.get("use_pooling") == "true":
                pool_cls = MaxPooling1D if parameters["conv_type"] == "Conv1D" else MaxPooling2D
                model.add(pool_cls(pool_size=layer["pool_size"]))
            if layer.get("use_dropout") == "true":
                model.add(Dropout(rate=layer["dropout_rate"]))

        if parameters.get("use_flatten", "true") == "true":
            model.add(Flatten())
        model.add(Dense(parameters["dense_units"], activation=parameters["output_activation"]))

    elif model_type == "RNNClassifier":
        for i, layer in enumerate(parameters.get("rnn_layers", [])):
            rnn_cls = {"SimpleRNN": SimpleRNN, "LSTM": LSTM, "GRU": GRU}[parameters["rnn_cell_type"]]
            kwargs = {
                "units": layer["units"],
                "activation": layer["activation"],
                "return_sequences": layer["return_sequences"] == "true",
                "go_backwards": layer.get("go_backwards", "false") == "true"
            }
            if layer.get("use_dropout") == "true":
                kwargs["dropout"] = layer["dropout_rate"]
            if layer.get("use_recurrent_dropout") == "true":
                kwargs["recurrent_dropout"] = layer["recurrent_dropout_rate"]
            if i == 0:
                kwargs["input_shape"] = input_shape
            model.add(rnn_cls(**kwargs))

        if parameters.get("use_dense", "true") == "true":
            model.add(Dense(parameters["dense_units"], activation=parameters["output_activation"]))

    elif model_type == "MLPClassifier":
        model.add(Flatten(input_shape=input_shape))
        for layer in parameters.get("hidden_layers", []):
            model.add(Dense(layer["units"], activation=layer["activation"]))
            if layer.get("use_dropout") == "true":
                model.add(Dropout(rate=layer["dropout_rate"]))
        model.add(Dense(parameters["dense_units"], activation=parameters["output_activation"]))

    else:
        raise ValueError(f"Unsupported model type: {model_type}")

    model.compile(
        optimizer=parameters["optimizer"],
        loss=parameters["loss"],
        metrics=["accuracy"]
    )
    return model

def extract_features_from_pcap(file_obj):
    logger.info("Extrayendo características del archivo PCAP")

    with tempfile.NamedTemporaryFile(delete=False, suffix=".pcap") as tmp:
        tmp.write(file_obj.read())
        tmp_path = tmp.name

    logger.info("Archivo temporal creado en: %s", tmp_path)

    cap = None
    data = []
    flow_dict = defaultdict(list)

    try:
        cap = pyshark.FileCapture(tmp_path, keep_packets=False)

        for i, pkt in enumerate(cap):
            try:
                time = float(pkt.sniff_time.timestamp()) if hasattr(pkt, 'sniff_time') else None
                length = int(pkt.length) if hasattr(pkt, 'length') else None

                src = pkt.ip.src if hasattr(pkt, 'ip') else None
                dst = pkt.ip.dst if hasattr(pkt, 'ip') else None

                proto = pkt.transport_layer or getattr(pkt, 'highest_layer', None)
                proto_name = PROTOCOL_MAP.get(str(proto), str(proto)) if proto else 'UNKNOWN'

                src_port = dst_port = -1

                if pkt.transport_layer:
                    try:
                        layer = pkt[pkt.transport_layer]
                        src_port = int(getattr(layer, 'srcport', -1)) if hasattr(layer, 'srcport') else -1
                        dst_port = int(getattr(layer, 'dstport', -1)) if hasattr(layer, 'dstport') else -1
                    except Exception as e:
                        logger.warning("Error obteniendo puertos del paquete %d: %s", i + 1, str(e))

                flags = pkt.tcp.flags if hasattr(pkt, 'tcp') and hasattr(pkt.tcp, 'flags') else None
                ttl = int(pkt.ip.ttl) if hasattr(pkt, 'ip') and hasattr(pkt.ip, 'ttl') else None

                flow_key = (src, src_port, dst, dst_port, proto_name)
                flow_dict[flow_key].append({
                    'time': time,
                    'length': length,
                    'ttl': ttl,
                    'flags': flags
                })

            except Exception as e:
                logger.warning("Error procesando paquete %d: %s", i + 1, str(e))
                continue

    except Exception as e:
        logger.error("Error leyendo el archivo PCAP: %s", str(e))
    finally:
        if cap:
            cap.close()
            del cap
        logger.info("Captura cerrada correctamente")

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

    df = pd.DataFrame(aggregated)
    df['src_port'] = df['src_port'].fillna(-1)
    df['dst_port'] = df['dst_port'].fillna(-1)
    df['protocol'] = df['protocol'].fillna('UNKNOWN').replace('', 'UNKNOWN')

    df.to_csv("features_por_flujo.csv", index=False)
    logger.info("DataFrame agregado: %s", df)
    return df


import ipaddress

def ip_to_int(ip_str):
    try:
        return int(ipaddress.IPv4Address(ip_str))
    except:
        return 0
    
def int_to_ip(ip_int):
    return socket.inet_ntoa(struct.pack("!I", int(ip_int)))
    
def extract_parameters(properties, params):
    extracted = {}
    custom_params = {} 

    for prop in properties:
        prop_name = prop["name"]
        if prop_name in params:
            value = params[prop_name]
            
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

            if prop.get("type") == "conditional-select" and value == "custom":
                dependent_prop = next(
                    (p for p in properties if p.get("conditional", {}).get("dependsOn") == prop_name),
                    None
                )
                if dependent_prop and params.get(dependent_prop["name"]):
                    custom_params[prop_name] = params[dependent_prop["name"]]

    for main_param, custom_value in custom_params.items():
        extracted[main_param] = int(custom_value)
        dependent_prop_name = f"custom_{main_param}"
        if dependent_prop_name in extracted:
            del extracted[dependent_prop_name]

    for prop in properties:
        if "conditional" in prop:
            depends_on = prop["conditional"].get("dependsOn")
            
            condition_values = prop["conditional"].get("values", [])
            condition_value = prop["conditional"].get("value", None)

            if depends_on and depends_on in extracted:
                parent_value = extracted[depends_on]
                
                if condition_value:
                    if parent_value != condition_value:
                        extracted.pop(prop["name"], None)
                elif condition_values:
                    if parent_value not in condition_values:
                        extracted.pop(prop["name"], None)

    return extracted

def calculate_classification_metrics(y_true, y_pred, metrics_config):
    logger.info("Métricas: %s", metrics_config)
    logger.info("y_true: %s", y_true)
    logger.info("y_pred: %s", y_pred)
    metrics = {}
    if metrics_config.get("accuracy"):
         metrics["accuracy"] = round(accuracy_score(y_true, y_pred), 2)
    if metrics_config.get("precision"):
        metrics["precision"] = round(precision_score(y_true, y_pred, average="weighted", zero_division=0), 2)
    if metrics_config.get("recall"):
        metrics["recall"] = round(recall_score(y_true, y_pred, average="weighted", zero_division=0), 2)
    if metrics_config.get("f1Score"):
        metrics["f1_score"] = round(f1_score(y_true, y_pred, average="weighted", zero_division=0), 2)
    if metrics_config.get("confusionMatrix"):
        metrics["confusion_matrix"] = confusion_matrix(y_true, y_pred).tolist()
    return metrics

def calculate_regression_metrics(y_true, y_pred):
    metrics = {}
    
    metrics["mse"] = round(mean_squared_error(y_true, y_pred), 2)
    
    metrics["rmse"] = round(np.sqrt(metrics["mse"]), 2)
    
    metrics["mae"] = round(mean_absolute_error(y_true, y_pred), 2)
    
    metrics["r2"] = round(r2_score(y_true, y_pred), 2)
    
    metrics["msle"] = round(mean_squared_error(np.log1p(y_true), np.log1p(y_pred)), 2)

    logger.info("metrics: %s", metrics)
    
    return metrics

def save_classification_metrics(detector, model_name, metrics, execution):
    ClassificationMetric.objects.create(
        detector=detector,
        execution=execution,
        model_name=model_name,
        accuracy=metrics.get("accuracy"),
        precision=metrics.get("precision"),
        recall=metrics.get("recall"),
        f1_score=metrics.get("f1_score"),
        confusion_matrix=json.dumps(metrics.get("confusion_matrix")),
    )

def save_regression_metrics(detector, model_name, metrics, execution):
    logger.info("Guardando métricas de regresión")
    RegressionMetric.objects.create(
        detector=detector,
        execution=execution,
        model_name=model_name,
        mse=metrics.get("mse"),
        rmse=metrics.get("rmse"),
        mae=metrics.get("mae"),
        r2=metrics.get("r2"),
        msle=metrics.get("msle"),
    )

def save_anomaly_metrics(detector, model_name, feature_name, feature_values, anomalies, execution, production, anomaly_image=None, global_shap_image=None, local_shap_image=None, global_lime_image=None, local_lime_image=None):
    anomaly_payload = {
        'values': feature_values.tolist() if not production else feature_values,
        'anomaly_indices': anomalies
    }

    AnomalyMetric.objects.create(
        detector=detector,
        model_name=model_name,
        feature_name=feature_name,
        anomalies=anomaly_payload,
        execution=execution,
        production=production,
        anomaly_image=anomaly_image,
        global_shap_image=global_shap_image,
        local_shap_image=local_shap_image,
        global_lime_image=global_lime_image,
        local_lime_image=local_lime_image
    )

def find_explainer_class(module_name, explainer_name):
    try:
        mod = importlib.import_module(module_name)
        if hasattr(mod, explainer_name):
            return getattr(mod, explainer_name)
    except Exception:
        pass

    shap_submodules = [
        f"{module_name}.explainers", 
        f"{module_name}.explainers.tree",
        f"{module_name}.explainers.kernel",
        f"{module_name}.explainers.deep",
        f"{module_name}.explainers.linear"
    ]
    
    lime_submodules = [
        f"{module_name}.lime_tabular",
        "lime.lime_tabular"
    ]

    submodules = shap_submodules + lime_submodules

    for sub in submodules:
        try:
            mod = importlib.import_module(sub)
            if hasattr(mod, explainer_name):
                return getattr(mod, explainer_name)
        except Exception:
            continue

    raise ImportError(f"No se pudo encontrar {explainer_name} dentro de {module_name} ni en submódulos comunes")


def save_shap_bar_global(shap_values, scenario_uuid) -> str:
    output_dir = os.path.join(settings.MEDIA_ROOT, "shap_global_images")
    os.makedirs(output_dir, exist_ok=True)

    try:
        plt.figure()
        shap.plots.bar(shap_values, show=False)
        output_filename = f"global_shap_{scenario_uuid}.png"
        output_path = os.path.join(output_dir, output_filename)
        plt.tight_layout()
        plt.savefig(output_path, bbox_inches='tight')
        plt.close()
        logger.info(f"[SHAP GLOBAL] Gráfica guardada en: {output_path}")
        return f"shap_global_images/{output_filename}"
    except Exception as e:
        logger.warning(f"[SHAP GLOBAL] Error al guardar gráfica: {e}")
        return ""
    
def save_lime_bar_global(mean_weights: dict, scenario_uuid: str) -> str:
    output_dir = os.path.join(settings.MEDIA_ROOT, "lime_global_images")
    os.makedirs(output_dir, exist_ok=True)

    try:
        features, values = zip(*sorted(mean_weights.items(), key=lambda x: x[1], reverse=True))

        plt.figure(figsize=(10, 6))
        plt.barh(features[::-1], values[::-1])
        plt.xlabel("Mean absolute weight (LIME)")
        plt.title("Global LIME Feature Importance")
        plt.tight_layout()

        output_filename = f"global_lime_{scenario_uuid}.png"
        output_path = os.path.join(output_dir, output_filename)
        plt.savefig(output_path, bbox_inches="tight")
        plt.close()

        logger.info(f"[LIME GLOBAL] Gráfica guardada en: {output_path}")
        return f"lime_global_images/{output_filename}"

    except Exception as e:
        logger.warning(f"[LIME GLOBAL] Error al guardar gráfica: {e}")
        return ""
    
def save_lime_bar_local(exp, scenario_uuid: str, anomaly_index: int) -> str:
    output_dir = os.path.join(settings.MEDIA_ROOT, "lime_local_images")
    os.makedirs(output_dir, exist_ok=True)

    try:
        contribs = sorted(exp.as_list(), key=lambda x: abs(x[1]), reverse=True)
        features, values = zip(*contribs)

        features = features[::-1]
        values = values[::-1]

        feature_labels = [f"{cond}" for cond in features]

        plt.figure(figsize=(8, 6))
        colors = ["#FF0051" if v > 0 else "#1E88E5" for v in values]
        bars = plt.barh(range(len(values)), values, color=colors)
        plt.yticks(range(len(features)), feature_labels)
        plt.axvline(0, color="black", linewidth=0.5, linestyle="--")
        plt.xlabel("LIME value")
        plt.title("Local explanation (LIME)")

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

        output_filename = f"lime_local_{scenario_uuid}_{anomaly_index}.png"
        output_path = os.path.join(output_dir, output_filename)
        plt.savefig(output_path, bbox_inches="tight")
        plt.close()
        logger.info(f"[LIME LOCAL] Gráfica tipo SHAP guardada en: {output_path}")
        return f"lime_local_images/{output_filename}"

    except Exception as e:
        logger.warning(f"[LIME LOCAL] Error al guardar gráfica estilo SHAP: {e}")
        return ""


    
def save_shap_bar_local(shap_values, scenario_uuid, index) -> str:
    output_dir = os.path.join(settings.MEDIA_ROOT, "shap_local_images")
    os.makedirs(output_dir, exist_ok=True)

    try:
        plt.figure()
        shap.plots.bar(shap_values, show=False)
        output_filename = f"local_shap_{scenario_uuid}_{index}.png"
        output_path = os.path.join(output_dir, output_filename)
        plt.tight_layout()
        plt.savefig(output_path, bbox_inches='tight')
        plt.close()
        logger.info(f"[SHAP GLOBAL] Gráfica guardada en: {output_path}")
        return f"shap_local_images/{output_filename}"
    except Exception as e:
        logger.warning(f"[SHAP GLOBAL] Error al guardar gráfica: {e}")
        return ""

def save_anomaly_information(info: dict, uuid: str, index: int, protocol: str) -> str:
    info["protocol"] = protocol
    info["src_port"] = int(info["src_port"])
    info["dst_port"] = int(info["dst_port"])

    logger.info("[IMAGEN] Generando imagen de anomalía con la información: %s", info)

    plt.figure(figsize=(6, 4))
    plt.axis("off")
    texto = "\n".join([f"{k}: {v}" for k, v in info.items()])
    plt.text(0, 0.9, texto, fontsize=10, va='top')
    path = os.path.join(settings.MEDIA_ROOT, "anomaly_images", f"anomaly_{uuid}_{index}.png")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    plt.savefig(path, bbox_inches="tight")
    plt.close()
    return f"anomaly_images/anomaly_{uuid}_{index}.png"


def get_next_anomaly_index(detector):
    return AnomalyMetric.objects.filter(detector=detector, production=True).count()

def put_data_controller(request):
    controller = DataController(name='Example Controller')
    controller.put_data() 
    return JsonResponse({'message': 'Data has been put successfully'})

def sync_data_controller(request):
    controller = DataController(name='Example Controller')
    controller.sync_data()
    return JsonResponse({'message': 'Data has been synchronized'})

def set_aggregation_technique(request, technique):
    controller = DataController(name='Example Controller')
    controller.set_aggregation_technique(technique)
    return JsonResponse({'message': f'Aggregation technique {technique} has been set'})

def set_filtering_strategy_controller(request, strategy):
    controller = DataController(name='Example Controller')
    controller.set_filtering_strategy(strategy)
    return JsonResponse({'message': f'Filtering strategy {strategy} has been set'})


# View for DataReceiver
def put_data_receiver(request):
    receiver = DataReceiver(name='Example Receiver')
    data = request.POST.get('data', '')
    receiver.put_data(data)
    return JsonResponse({'message': 'Data received by DataReceiver'})

def validate_data_receiver(request):
    receiver = DataReceiver(name='Example Receiver')
    data = request.POST.get('data', '')
    receiver.validate_data(data)
    return JsonResponse({'message': 'Data validated by DataReceiver'})


# View for DataFilter
def set_filtering_strategy_filter(request, strategy):
    data_filter = DataFilter(name='Example Filter')
    data_filter.set_filtering_strategy(strategy)
    return JsonResponse({'message': f'Filtering strategy {strategy} has been set by DataFilter'})

def filter_data(request):
    data_filter = DataFilter(name='Example Filter')
    data = request.POST.get('data', '')
    data_filter.filter_data(data)
    return JsonResponse({'message': 'Data has been filtered'})


# View for DataStorage
def serialize_data(request):
    storage = DataStorage(name='Example Storage')
    data = request.POST.get('data', '')
    storage.serialize_data(data)
    return JsonResponse({'message': 'Data has been serialized'})

def store_data(request):
    storage = DataStorage(name='Example Storage')
    data = request.POST.get('data', '')
    storage.store_data(data)
    return JsonResponse({'message': 'Data has been stored'})

def get_available_space(request):
    storage = DataStorage(name='Example Storage')
    storage.get_available_space()
    return JsonResponse({'message': 'Available space retrieved'})


# View for para DataMixer
def set_aggregation_technique_mixer(request, technique):
    mixer = DataMixer(name='Example Mixer')
    mixer.set_aggregation_technique(technique)
    return JsonResponse({'message': f'Aggregation technique {technique} has been set by DataMixer'})

def check_for_data_to_aggregate(request):
    mixer = DataMixer(name='Example Mixer')
    mixer.check_for_data_to_aggregate()
    return JsonResponse({'message': 'Checked for data to aggregate'})

def aggregate_data(request):
    mixer = DataMixer(name='Example Mixer')
    data_list = request.POST.getlist('data')
    mixer.aggregate_data(data_list)
    return JsonResponse({'message': 'Data has been aggregated'})


# View for para DataSync
def check_sync_status(request):
    sync = DataSync(name='Example Sync')
    sync.check_sync_status()
    return JsonResponse({'message': 'Sync status checked'})

def sync_data_sync(request):
    sync = DataSync(name='Example Sync')
    sync.sync()
    return JsonResponse({'message': 'Data has been synchronized'})

def verify_sync_data(request):
    sync = DataSync(name='Example Sync')
    sync.verify_sync_data()
    return JsonResponse({'message': 'Sync data verified'})

@api_view(['POST'])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser])
def create_scenario(request):
    user = request.user  
    data = request.data.dict()
    data['user'] = user.id  

    logger.info(request.data)

    csv_files = request.FILES.getlist('csv_files')
    logger.info("CSV files received: %s", [f.name for f in csv_files])
    network_files = request.FILES.getlist('network_files')

    if not csv_files and not network_files:
        return JsonResponse({"error": "At least one CSV or PCAP file is required."}, status=status.HTTP_400_BAD_REQUEST)

    saved_files = []

    try:
        for csv_file in csv_files:
            existing_file = File.objects.filter(name=csv_file.name).first()
            if existing_file:
                existing_file.references += 1
                existing_file.save()
                saved_files.append(existing_file)
            else:
                csv_content = csv_file.read().decode('utf-8')
                csv_reader = csv.reader(StringIO(csv_content))
                entry_count = sum(1 for _ in csv_reader) - 1

                new_file = File.objects.create(
                    name=csv_file.name,
                    file_type='csv',
                    entry_count=entry_count,
                    content=ContentFile(csv_content.encode('utf-8'), name=csv_file.name),
                    references=1
                )
                saved_files.append(new_file)

        for network_file in network_files:
            existing_file = File.objects.filter(name=network_file.name).first()
            if existing_file:
                existing_file.references += 1
                existing_file.save()
                saved_files.append(existing_file)
            else:
                network_content = network_file.read()
                new_file = File.objects.create(
                    name=network_file.name,
                    file_type='pcap',
                    entry_count=0,
                    content=ContentFile(network_content, name=network_file.name),
                    references=1
                )
                saved_files.append(new_file)

    except Exception as e:
        return JsonResponse({"error": f"Error while processing the files: {str(e)}"}, status=status.HTTP_400_BAD_REQUEST)

    serializer = ScenarioSerializer(data=data)
    if serializer.is_valid():
        user.number_designs_created += 1
        user.save()
        scenario_instance = serializer.save(user=user)
        scenario_instance.files.set(saved_files)
        return JsonResponse(ScenarioSerializer(scenario_instance).data, status=status.HTTP_201_CREATED)

    return JsonResponse(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_scenarios_by_user(request):
    user = request.user  

    scenarios = Scenario.objects.filter(user=user.id)

    serializer = ScenarioSerializer(scenarios, many=True)
    
    return JsonResponse(serializer.data, safe=False, status=status.HTTP_200_OK)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_scenario_by_uuid(request, uuid):
    user = request.user 

    try:
        scenario = Scenario.objects.get(uuid=uuid, user=user.id)
        serializer = ScenarioSerializer(scenario)  
        return JsonResponse(serializer.data, safe=False, status=status.HTTP_200_OK) 
    except Scenario.DoesNotExist:
        return JsonResponse({'error': 'Scenario not found or you do not have permission to access it'}, status=status.HTTP_404_NOT_FOUND)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_scenario_classification_metrics_by_uuid(request, uuid):
    try:
        scenario = Scenario.objects.get(uuid=uuid)
        detector = AnomalyDetector.objects.get(scenario=scenario)
        metrics = ClassificationMetric.objects.filter(detector=detector).order_by('-date')

        metrics_data = [
            {
                "model_name": metric.model_name,
                "accuracy": metric.accuracy,
                "precision": metric.precision,
                "recall": metric.recall,
                "f1_score": metric.f1_score,
                "confusion_matrix": metric.confusion_matrix,
                "date": metric.date,
                "execution": metric.execution
            }
            for metric in metrics
        ]

        return JsonResponse({"metrics": metrics_data}, safe=False)
    except Scenario.DoesNotExist:
        return JsonResponse({"error": "Scenario not found"}, status=404)
    except AnomalyDetector.DoesNotExist:
        return JsonResponse({"error": "Anomaly detector not found"}, status=404)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)
    
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_scenario_regression_metrics_by_uuid(request, uuid):
    try:
        scenario = Scenario.objects.get(uuid=uuid)
        detector = AnomalyDetector.objects.get(scenario=scenario)
        metrics = RegressionMetric.objects.filter(detector=detector).order_by('-date')

        metrics_data = [
            {
                "model_name": metric.model_name,
                "mse": metric.mse,
                "rmse": metric.rmse,
                "mae": metric.mae,
                "r2": metric.r2,
                "msle": metric.msle,
                "date": metric.date,
                "execution": metric.execution
            }
            for metric in metrics
        ]

        return JsonResponse({"metrics": metrics_data}, safe=False)
    except Scenario.DoesNotExist:
        return JsonResponse({"error": "Scenario not found"}, status=404)
    except AnomalyDetector.DoesNotExist:
        return JsonResponse({"error": "Anomaly detector not found"}, status=404)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)
    
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_scenario_anomaly_metrics_by_uuid(request, uuid):
    try:
        scenario = Scenario.objects.get(uuid=uuid)
        detector = AnomalyDetector.objects.get(scenario=scenario)
        metrics = AnomalyMetric.objects.filter(detector=detector).order_by('-date')

        metrics_data = []
        for metric in metrics:
            try:
                anomalies = json.loads(metric.anomalies)
            except:
                anomalies = metric.anomalies

            metrics_data.append({
                "model_name": metric.model_name,
                "feature_name": metric.feature_name,
                "anomalies": anomalies,
                "date": metric.date,
                "execution": metric.execution,
                "production": metric.production,
                "global_shap_image": metric.global_shap_image.url if metric.global_shap_image else None,
                "global_lime_image": metric.global_lime_image.url if metric.global_lime_image else None
            })

        return JsonResponse({"metrics": metrics_data}, safe=False)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)
    
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_scenario_production_anomaly_metrics_by_uuid(request, uuid):
    try:
        scenario = Scenario.objects.get(uuid=uuid)
        detector = AnomalyDetector.objects.get(scenario=scenario)
        metrics = AnomalyMetric.objects.filter(detector=detector).order_by('-date')

        metrics_data = []
        for metric in metrics:
            try:
                anomalies = json.loads(metric.anomalies)
            except:
                anomalies = metric.anomalies

            if metric.production == True:
                metrics_data.append({
                    "model_name": metric.model_name,
                    "feature_name": metric.feature_name,
                    "anomalies": anomalies,
                    "date": metric.date,
                    "execution": metric.execution,
                    "production": metric.production,
                    "anomaly_image": metric.anomaly_image.url if metric.anomaly_image else None,
                    "local_shap_image": metric.local_shap_image.url if metric.local_shap_image else None,
                    "local_lime_image": metric.local_lime_image.url if metric.local_lime_image else None
                })

        return JsonResponse({"metrics": metrics_data}, safe=False)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)

@api_view(['PUT'])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser])
def put_scenario_by_uuid(request, uuid):
    user = request.user

    try:
        scenario = Scenario.objects.get(uuid=uuid, user=user)

        design_json = request.POST.get('design')
        csv_files = request.FILES.getlist('csv_files')
        network_files = request.FILES.getlist('network_files')

        if not design_json:
            return JsonResponse({'error': 'Design field is required'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            design = json.loads(design_json)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid design JSON'}, status=status.HTTP_400_BAD_REQUEST)

        scenario.design = design

        referenced_file_names = set()
        for element in design.get("elements", []):
            if element.get("type") == "CSV":
                csv_name = element.get("parameters", {}).get("csvFileName")
                if csv_name:
                    referenced_file_names.add(csv_name)
            elif element.get("type") == "Network":
                net_name = element.get("parameters", {}).get("networkFileName")
                if net_name:
                    referenced_file_names.add(net_name)

        referenced_files = list(File.objects.filter(name__in=referenced_file_names))

        updated_files = []

        for csv_file in csv_files:
            existing = File.objects.filter(name=csv_file.name).first()
            if existing:
                existing.references += 1
                existing.save()
                updated_files.append(existing)
            else:
                csv_content = csv_file.read().decode('utf-8')
                csv_reader = csv.reader(StringIO(csv_content))
                entry_count = sum(1 for _ in csv_reader) - 1

                new_file = File.objects.create(
                    name=csv_file.name,
                    file_type='csv',
                    entry_count=entry_count,
                    content=ContentFile(csv_content.encode('utf-8'), name=csv_file.name),
                    references=1
                )
                updated_files.append(new_file)

        for network_file in network_files:
            existing = File.objects.filter(name=network_file.name).first()
            if existing:
                existing.references += 1
                existing.save()
                updated_files.append(existing)
            else:
                network_content = network_file.read()
                new_file = File.objects.create(
                    name=network_file.name,
                    file_type='pcap',
                    entry_count=0,
                    content=ContentFile(network_content, name=network_file.name),
                    references=1
                )
                updated_files.append(new_file)

        all_files_to_keep = {f.name: f for f in referenced_files + updated_files}

        current_files = list(scenario.files.all())
        for old_file in current_files:
            if old_file.name not in all_files_to_keep:
                old_file.references -= 1
                if old_file.references <= 0:
                    file_path = os.path.join(settings.MEDIA_ROOT, old_file.content.name)
                    if os.path.exists(file_path):
                        os.remove(file_path)
                    old_file.delete()
                else:
                    old_file.save()

        scenario.files.set(all_files_to_keep.values())

        serializer = ScenarioSerializer(instance=scenario, data={'design': design}, partial=True)
        if serializer.is_valid():
            serializer.save(user=user)
            return JsonResponse({'message': 'Scenario updated correctly'}, status=status.HTTP_200_OK)
        else:
            logger.error("Serializer errors: %s", serializer.errors)
            return JsonResponse(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    except Scenario.DoesNotExist:
        return JsonResponse({'error': 'Scenario not found'}, status=status.HTTP_404_NOT_FOUND)




import fnmatch

@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_scenario_by_uuid(request, uuid):
    user = request.user

    try:
        scenario = Scenario.objects.get(uuid=uuid, user=user.id)

        for file_instance in scenario.files.all():
            file_instance.references -= 1
            if file_instance.references <= 0:
                file_path = os.path.join(settings.MEDIA_ROOT, file_instance.content.name)
                if os.path.exists(file_path):
                    os.remove(file_path)
                file_instance.delete()
            else:
                file_instance.save()

        anomaly_detector = AnomalyDetector.objects.filter(scenario=scenario).first()
        if anomaly_detector:
            ClassificationMetric.objects.filter(detector=anomaly_detector).delete()
            anomaly_detector.delete()

        folders_to_clean = [
            'models_storage',
            'anomaly_images',
            'shap_global_images',
            'shap_local_images',
            'lime_global_images',
            'lime_local_images'
        ]

        scenario_uuid = str(scenario.uuid)

        for folder in folders_to_clean:
            folder_path = os.path.join(settings.MEDIA_ROOT, folder)
            if not os.path.exists(folder_path):
                continue
            for filename in os.listdir(folder_path):
                if scenario_uuid in filename:
                    file_to_delete = os.path.join(folder_path, filename)
                    logger.info(f"Eliminando archivo: {file_to_delete}")
                    try:
                        os.remove(file_to_delete)
                    except Exception as e:
                        logger.warning(f"No se pudo eliminar {file_to_delete}: {str(e)}")

        scenario.delete()

        return JsonResponse({'message': 'Scenario and related data deleted successfully'}, status=status.HTTP_200_OK)

    except Scenario.DoesNotExist:
        return JsonResponse({'error': 'Scenario not found or you do not have permission to delete it'}, status=status.HTTP_404_NOT_FOUND)

@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def run_scenario_by_uuid(request, uuid):
    user = request.user  

    try:
        scenario = Scenario.objects.get(uuid=uuid, user=user)

        scenario.status = "Running"
        scenario.save()

        anomaly_detector, created = AnomalyDetector.objects.get_or_create(scenario=scenario)

        design = scenario.design
        if isinstance(design, str):  
            design = json.loads(design)

        result = execute_scenario(anomaly_detector, scenario, design)

        if result.get('error'):
            scenario.status = "Error"
            scenario.save()
            return JsonResponse(result, status=status.HTTP_400_BAD_REQUEST)

        scenario.status = 'Finished'
        scenario.save()
        user.number_executed_scenarios += 1
        user.save()

        return JsonResponse({
            'message': 'Scenario run successfully'
        }, status=status.HTTP_200_OK)

    except Scenario.DoesNotExist:
        return JsonResponse({'error': 'Scenario not found or without permits to run it'}, status=status.HTTP_404_NOT_FOUND)

@shared_task
def execute_scenario(anomaly_detector, scenario, design):
    try:
        anomaly_detector.execution += 1
        anomaly_detector.save()
        config = load_config()
        element_types = {}
        splitter = False
        code_processing = False
        code_splitter = False
        execution_mode_env = os.getenv("EXECUTION_MODE", "").strip().lower()

        validate_design(config, design)
        
        for section_name, section in config["sections"].items():
            if section_name == "dataModel":
                for model in section.get("classification", []):
                    model["model_type"] = "classification"  
                    element_types[model["type"]] = model
                for model in section.get("regression", []):
                    model["model_type"] = "regression"
                    element_types[model["type"]] = model
                for model in section.get("anomalyDetection", []):
                    model["model_type"] = "anomalyDetection"
                    element_types[model["type"]] = model
                for model in section.get("explainability", []):
                    model["model_type"] = "explainability"
                    element_types[model["type"]] = model
                for model in section.get("monitoring", []):
                    element_types[model["type"]] = model
            elif "elements" in section:
                for element in section["elements"]:
                    element_types[element["type"]] = element


        elements = {e["id"]: e for e in design["elements"]}
        connections = design["connections"]
        
        adj = defaultdict(list)
        in_degree = defaultdict(int)
        for conn in connections:
            adj[conn["startId"]].append(conn["endId"])
            in_degree[conn["endId"]] += 1
            if conn["startId"] not in in_degree:
                in_degree[conn["startId"]] = 0

        queue = [node for node, count in in_degree.items() if count == 0]
        sorted_order = []
        while queue:
            node = queue.pop(0)
            sorted_order.append(node)
            for neighbor in adj[node]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        logger.info("Orden topológico de los elementos: %s", sorted_order)
        
        data_storage = {} 
        models = {}

        for element_id in sorted_order:
            element = elements[element_id]
            el_type = element["type"]
            logger.info("Procesando elemento %s", el_type)
            params = copy.deepcopy(element.get("parameters", {}))
            
            input_data = None
            for conn in connections:
                if conn["endId"] == element_id:
                    predecessor_id = conn["startId"]
                    input_data = data_storage.get(predecessor_id)
                    break 

            if el_type == "CSV":
                logger.info("Cargando CSV")
                csv_file_name = params.get("csvFileName")
                try:
                    file = File.objects.get(name=csv_file_name)
                    df = pd.read_csv(file.content)
                except Exception as e:
                    return {"error": f"Error loading CSV: {str(e)}"}
                
                columns = params.get("columns", [])
                selected_columns = []
                
                if isinstance(columns, list):
                    selected_columns = [col["name"] for col in columns if col.get("selected", True)]
                elif isinstance(columns, dict):
                    selected_columns = [col for col, keep in columns.items() if keep]
                
                logger.info("Columnas seleccionadas en orden original: %s", selected_columns)
                
                try:
                    df = df[selected_columns]
                except KeyError as e:
                    return {"error": f"Columna no encontrada en CSV: {str(e)}"}
                except Exception as e:
                    return {"error": f"Error procesando columnas: {str(e)}"}
                
                data_storage[element_id] = df

            elif el_type == "Network":
                logger.info("Cargando PCAP")

                network_file_name = params.get("networkFileName")
                logger.info("Nombre del archivo de red: %s", network_file_name)
                try:
                    file = File.objects.get(name=network_file_name)
                    with open(file.content.path, 'rb') as f:
                        df = extract_features_from_pcap(f)
                    logger.info("DataFrame extraído: %s", df.head())
                except Exception as e:
                    return {"error": f"Error loading PCAP: {str(e)}"}

                if df.empty:
                    return {"error": "El archivo PCAP no contiene datos utilizables"}

                data_storage[element_id] = df

            elif el_type in ["ClassificationMonitor", "RegressionMonitor"]:
                logger.info("Procesando monitor")
                for conn in connections:
                    if conn["endId"] == element_id:
                        model_id = conn["startId"]
                        model_element = elements.get(model_id)
                        if not model_element:
                            raise ValueError(f"Modelo {model_id} no encontrado para el monitor")

                        model_type = element_types.get(model_element["type"], {}).get("model_type")
                        monitor_type = "classification" if el_type == "ClassificationMonitor" else "regression"
                        logger.info("Modelo: %s, Monitor: %s", model_type, monitor_type)

                        if model_type != monitor_type:
                            raise ValueError(f"Error de tipo: {el_type} conectado a modelo {model_type}")

                        model_data = models.get(model_id)
                        logger.info("Datos del modelo: %s", model_data)
                        if model_data:
                            if el_type == "ClassificationMonitor":
                                logger.info("Calculando métricas de clasificación")
                                metrics_config = params.get("metrics", {})
                                metrics = calculate_classification_metrics(model_data["y_test"], model_data["y_pred"], metrics_config)
                                save_classification_metrics(anomaly_detector, model_element["type"], metrics, anomaly_detector.execution)
                            else:
                                logger.info("Calculando métricas de regresión")
                                metrics = calculate_regression_metrics(model_data["y_test"], model_data["y_pred"])
                                save_regression_metrics(anomaly_detector, model_element["type"], metrics, anomaly_detector.execution)

            elif el_type == "DataSplitter":
                logger.info("Ejecutando DataSplitter")
                splitter = True

                if input_data is None:
                    return {"error": "DataSplitter requiere datos de entrada"}

                try:
                    splitter_params = extract_parameters(element_types[el_type]["properties"], params)
                    logger.info("Parámetros del DataSplitter: %s", splitter_params)

                    train_size = splitter_params.get("train_size", 80) / 100
                    test_size = splitter_params.get("test_size", 20) / 100
                    logger.info("Tamaños de train y test: %s, %s", train_size, test_size)

                    if round(train_size + test_size, 2) > 1.0:
                        return {"error": "La suma de train_size y test_size no puede ser mayor que 100%"}

                    X = input_data.iloc[:, :-1]
                    y = input_data.iloc[:, -1]

                    X_train, X_test, y_train, y_test = train_test_split(
                        X, y,
                        train_size=train_size,
                        test_size=test_size
                    )

                    data_storage[element_id] = {
                        "train": (X_train, y_train),
                        "test": (X_test, y_test)
                    }

                    logger.info(data_storage)

                except Exception as e:
                    return {"error": f"Error en DataSplitter: {str(e)}"}
                
            elif el_type in ["CodeProcessing", "CodeSplitter"]:
                logger.info("Ejecutando función personalizada")

                user_code = params.get("code", "")
                if input_data is None:
                    return {"error": "CustomCode requiere datos de entrada"}
                if not user_code.strip():
                    return {"error": "No se ha proporcionado código en el elemento CustomCode"}

                exec_context = {
                    "__builtins__": __builtins__,
                    "pd": pd,
                    "np": __import__('numpy'),
                }

                try:
                    exec(user_code, exec_context)
                    user_functions = {k: v for k, v in exec_context.items() if callable(v)}
                    if len(user_functions) != 1:
                        return {"error": "Debes definir una única función en el código"}

                    user_function = list(user_functions.values())[0]
                    output_data = user_function(input_data)

                    if isinstance(output_data, pd.DataFrame):
                        logger.info("CustomCode detectado como preprocesador")
                        data_storage[element_id] = output_data
                        code_processing = True
                        logger.info(data_storage)

                    elif isinstance(output_data, dict) and "train" in output_data and "test" in output_data:
                        logger.info("CustomCode detectado como splitter")
                        data_storage[element_id] = output_data
                        code_splitter = True
                        logger.info(data_storage)

                    else:
                        return {"error": "La función debe retornar un DataFrame o un dict con claves 'train' y 'test'"}

                except Exception as e:
                    return {"error": f"Error ejecutando función personalizada: {str(e)}"}

                
            else:
                element_def = element_types.get(el_type)
                logger.info("Definición del elemento: %s", element_def)
                if not element_def:
                    return {"error": f"Tipo de elemento desconocido: {el_type}"}
                
                category = element_def.get("category", "")

                logger.info("Categoría del elemento: %s", category)

                if category not in ["model", "explainability"]:
                    logger.info("Importando clase: %s", element_def["class"])
                    cls = import_class(element_def["class"])
                
                if category == "preprocessing":
                    applies_to = element_def.get("appliesTo", "all")
                    transformer = cls(**extract_parameters(element_def["properties"], params))
                    
                    if input_data is not None:
                        '''
                        for col in input_data.columns:
                            if input_data[col].dtype == 'object':
                                try:
                                    input_data[col] = input_data[col].astype(float)
                                except ValueError:
                                    pass
                        '''

                        if 'target' in input_data.columns or 'label' in input_data.columns:
                            target_column = input_data.pop('target') if 'target' in input_data.columns else None
                            label_column = input_data.pop('label') if 'label' in input_data.columns else None

                            original_targets = {}
                            if target_column is not None:
                                original_targets['target'] = target_column
                            if label_column is not None:
                                original_targets['label'] = label_column

                            if applies_to == "numeric":
                                excluded_numeric = ['src_port', 'dst_port']
                                numeric_cols = [col for col in input_data.select_dtypes(include=['number']).columns if col not in excluded_numeric]
                                logger.info(f"[TRAINING] Columnas usadas para fit en {el_type}: {numeric_cols}")
                                
                                transformed = transformer.fit_transform(input_data[numeric_cols])
                                output_data = input_data.copy()
                                output_data[numeric_cols] = transformed


                            elif applies_to == "categorical":
                                categorical_cols = input_data.select_dtypes(exclude=['number']).columns
                                output_data = pd.get_dummies(input_data, columns=categorical_cols)

                            else:  
                                output_data = input_data.copy()
                                output_data[input_data.columns] = transformer.fit_transform(input_data)

                            for col_name, col_data in original_targets.items():
                                output_data[col_name] = col_data
                            
                        else:
                            if applies_to == "numeric":
                                excluded_numeric = ['src_port', 'dst_port']
                                numeric_cols = [col for col in input_data.select_dtypes(include=['number']).columns if col not in excluded_numeric]
                                logger.info(f"[TRAINING] Columnas usadas para fit en {el_type}: {numeric_cols}")
                                
                                transformed = transformer.fit_transform(input_data[numeric_cols])
                                output_data = input_data.copy()
                                output_data[numeric_cols] = transformed


                            elif applies_to == "categorical":
                                categorical_cols = input_data.select_dtypes(exclude=['number']).columns
                                output_data = pd.get_dummies(input_data, columns=categorical_cols)

                            else:
                                output_data = pd.DataFrame(
                                    transformer.fit_transform(input_data),
                                    columns=input_data.columns
                                )
                        
                        step_id = f"{element_id}_{scenario.uuid}"
                        model_dir = os.path.join(settings.MEDIA_ROOT, 'models_storage')
                        os.makedirs(model_dir, exist_ok=True)
                        step_path = os.path.join(model_dir, f"{step_id}.pkl")
                        joblib.dump(model, step_path)

                        joblib.dump(transformer, step_path)
                        logger.info(f"Guardado: {step_path}")

                        data_storage[element_id] = output_data
                        logger.info("Datos inicial: %s", input_data.head())
                        logger.info("Datos transformados: %s", output_data.head())
                        logger.info(data_storage)

                elif category == "model" and input_data is not None:
                    logger.info("Entrenando modelo")
                    execution_mode_model = params.pop("execution_mode", None)

                    logger.info("Execución del modelo: %s", execution_mode_model)
                    logger.info("Execución del entorno: %s", execution_mode_env)    

                    if execution_mode_model and execution_mode_env and execution_mode_model.strip().lower() != execution_mode_env:
                        error_msg = f"Incompatible execution mode: model='{execution_mode_model}', env='{execution_mode_env}'"
                        logger.error(error_msg)
                        return {"error": error_msg}
                    
                    if execution_mode_model.strip().lower() == "cpu":
                        cls = import_class(element_def["class_cpu"])
                    else:
                        cls = import_class(element_def["class_gpu"])
                    
                    if el_type not in ["CNNClassifier", "RNNClassifier", "MLPClassifier"]:
                        model = cls(**extract_parameters(element_def["properties"], params))
                        logger.info(model.get_params())

                    if element_def.get("model_type") in ["classification", "regression"]:
                        logger.info(f"Entrenamiento modelo {element_def.get('model_type')}")

                        
                        X_train_all, y_train_all = [], []
                        X_test_all, y_test_all = [], []
                        has_train = has_test = False

                        for conn in connections:
                            if conn["endId"] == element_id:
                                source_id = conn["startId"]
                                output_type = conn.get("startOutput")

                                split_data = data_storage.get(source_id)
                                if not isinstance(split_data, dict) or "train" not in split_data or "test" not in split_data:
                                    return {"error": f"El nodo conectado ({source_id}) no tiene datos de train/test"}

                                if output_type == "train":
                                    has_train = True
                                    X_train, y_train = split_data["train"]
                                    X_train_all.append(X_train)
                                    y_train_all.append(y_train)
                                elif output_type == "test":
                                    has_test = True
                                    X_test, y_test = split_data["test"]
                                    X_test_all.append(X_test)
                                    y_test_all.append(y_test)

                        if not has_train or not has_test:
                            return {"error": f"El modelo {element_id} requiere al menos una conexión con salidas 'train' y 'test'"}
                        

                        X_train_concat = pd.concat(X_train_all)
                        y_train_concat = pd.concat(y_train_all)
                        X_test_concat = pd.concat(X_test_all)
                        y_test_concat = pd.concat(y_test_all)

                        if el_type in ["CNNClassifier", "RNNClassifier", "MLPClassifier"]:
                            logger.info(f"Entrenando red neuronal: {el_type}")

                            X_train_raw = X_train_concat.values
                            X_test_raw = X_test_concat.values

                            if el_type in ["CNNClassifier", "RNNClassifier"]:
                                X_train_reshaped = X_train_raw.reshape((X_train_raw.shape[0], X_train_raw.shape[1], 1))
                                X_test_reshaped = X_test_raw.reshape((X_test_raw.shape[0], X_test_raw.shape[1], 1))
                                input_shape = (X_train_raw.shape[1], 1)
                            elif el_type == "MLPClassifier":
                                X_train_reshaped = X_train_raw
                                X_test_reshaped = X_test_raw
                                input_shape = (X_train_raw.shape[1],)

                            y_train_encoded = to_categorical(y_train_concat)
                            y_test_encoded = to_categorical(y_test_concat)

                            model = build_neural_network(input_shape, el_type, params)
                            model.fit(
                                X_train_reshaped, y_train_encoded,
                                epochs=params.get("epochs", 50),
                                batch_size=params.get("batch_size", 32),
                                verbose=0
                            )

                            y_pred_proba = model.predict(X_test_reshaped)
                            y_pred = np.argmax(y_pred_proba, axis=1)
                            y_test_labels = np.argmax(y_test_encoded, axis=1)

                            models[element_id] = {
                                "type": el_type,
                                "y_test": y_test_labels,
                                "y_pred": y_pred
                            }
                        else:
                            logger.info(f"Entrenando modelo clásico: {el_type}")

                            logger.info("Datos de entrenamiento concatenados: %s", X_train_concat)
                            logger.info("Datos de prueba concatenados: %s", X_test_concat)

                            model.fit(X_train_concat, y_train_concat)
                            y_pred = model.predict(X_test_concat)

                            models[element_id] = {
                                "type": el_type,
                                "y_test": y_test_concat,
                                "y_pred": y_pred
                            }

                    elif element_def.get("model_type") == "anomalyDetection":
                        logger.info("Modelo Detección de anomalías")

                        if not isinstance(input_data, pd.DataFrame):
                            return {"error": "Los datos de entrada para detección de anomalías deben ser un DataFrame"}

                        input_copy = input_data.copy()

                        for ip_col in ['src', 'dst']:
                            if ip_col in input_copy.columns:
                                input_copy[ip_col] = input_copy[ip_col].apply(ip_to_int)
                        
                        if 'protocol' in input_copy.columns:
                            input_copy['protocol'] = input_copy['protocol'].astype('category').cat.codes

                        #input_copy = input_copy.drop(columns=[col for col in input_copy.columns if input_copy[col].dtype == 'object'])

                        if input_copy.empty:
                            return {"error": "No hay columnas numéricas después del preprocesamiento"}
                        
                        logger.info("Datos preprocesados para detección de anomalías: %s", input_copy)

                        input_copy.to_csv("input_copy.csv", index=False)

                        model.fit(input_copy)
                        logger.info(model.feature_names_in_)
                        step_id = f"{element_id}_{scenario.uuid}"
                        model_dir = os.path.join(settings.MEDIA_ROOT, 'models_storage')
                        os.makedirs(model_dir, exist_ok=True)
                        step_path = os.path.join(model_dir, f"{step_id}.pkl")
                        joblib.dump(model, step_path)

                        joblib.dump(model, step_path)
                        logger.info(f"Guardado: {step_path}")

                        predictions = model.predict(input_copy)
                        y_pred = [1 if x == -1 else 0 for x in predictions]
                        logger.info("Predicciones: %s", y_pred)

                        for column in input_copy.columns:
                            feature_values = input_copy[column].values
                            anomalies = [i for i, (val, pred) in enumerate(zip(feature_values, y_pred)) if pred == 1]

                            save_anomaly_metrics(anomaly_detector, el_type, column, feature_values, anomalies, 
                                                 anomaly_detector.execution, production=False, anomaly_image=None, 
                                                 global_shap_image=None, local_shap_image=None, global_lime_image=None, 
                                                 local_lime_image=None)

                        models[element_id] = {
                            "type": el_type,
                            "y_pred": y_pred,
                            "model_object": model
                        }
                        data_storage[element_id] = input_copy

                        logger.info("Modelo de detección de anomalías entrenado y guardado")

                elif category == "explainability":
                    logger.info(f"Procesando nodo de explicabilidad dinámico: {el_type}")

                    if input_data is None:
                        return {"error": f"No se encontraron datos de entrada para el nodo {el_type}"}
                    
                    logger.info("Datos de entrada para explicabilidad: %s", input_data)

                    explainer_type = params.get("explainer_type", "").strip()
                    explainer_module_path = element_def.get("class")

                    if not explainer_module_path or not explainer_type:
                        return {"error": f"Faltan datos de configuración en {el_type}"}

                    model_id = next((c["startId"] for c in connections if c["endId"] == element_id), None)
                    if not model_id or model_id not in models:
                        return {"error": f"No se encontró un modelo conectado válido para {el_type}"}

                    model_info = models[model_id]
                    model_object = model_info.get("model_object")
                    if not model_object:
                        return {"error": f"No se encontró el objeto modelo en {model_id}"}

                    try:
                        explainer_class = find_explainer_class(explainer_module_path, explainer_type)

                        if el_type == "SHAP":
                            if explainer_type == "KernelExplainer":
                                def anomaly_score(X):
                                    if isinstance(X, np.ndarray):
                                        X = pd.DataFrame(X, columns=input_data.columns)
                                    return model_object.decision_function(X)

                                background = shap.kmeans(input_data, 20)  # O usa shap.sample(input_data, 50)
                                explainer = explainer_class(anomaly_score, background)

                                explainer = explainer_class(anomaly_score, background)

                            elif explainer_type in ["LinearExplainer", "TreeExplainer", "DeepExplainer"]:
                                explainer = explainer_class(model_object, input_data)
                            else:
                                explainer = explainer_class(model_object)

                            try:
                                shap_values = explainer(input_data)

                                shap_image_path = save_shap_bar_global(shap_values, scenario.uuid)

                                if shap_image_path:
                                    metrics = AnomalyMetric.objects.filter(
                                        detector=anomaly_detector,
                                        execution=anomaly_detector.execution,
                                    )

                                    for metric in metrics:
                                        metric.global_shap_image = shap_image_path
                                        metric.save()

                                logger.info(f"SHAP values generados: tipo={type(shap_values)}, shape={getattr(shap_values, 'shape', 'N/A')}")

                            except Exception as e:
                                return {"error": f"Error generando SHAP values: {str(e)}"}

                        elif el_type == "LIME":
                            explainer = explainer_class(
                                training_data=input_data.values,
                                feature_names=input_data.columns.tolist(),
                                mode="regression"
                            )

                            def anomaly_score(X):
                                if isinstance(X, np.ndarray):
                                    X = pd.DataFrame(X, columns=input_data.columns)
                                return model_object.decision_function(X).reshape(-1, 1)

                            scores = model_object.decision_function(input_data)
                            top_k = 20
                            top_indices = np.argsort(scores)[-top_k:]

                            feature_weights = defaultdict(list)

                            for i in top_indices:
                                row = input_data.iloc[i]
                                exp = explainer.explain_instance(
                                    row.values,
                                    anomaly_score,
                                    num_features=len(input_data.columns)
                                )

                                for feature, weight in exp.as_list():
                                    feature_weights[feature].append(abs(weight))

                            mean_weights = {feature: np.mean(w) for feature, w in feature_weights.items()}

                            sorted_items = sorted(mean_weights.items(), key=lambda x: x[1], reverse=True)
                            features, values = zip(*sorted_items)

                            lime_image_path = save_lime_bar_global(mean_weights, scenario.uuid)

                            metrics = AnomalyMetric.objects.filter(
                                detector=anomaly_detector,
                                execution=anomaly_detector.execution,
                            )

                            for metric in metrics:
                                metric.global_lime_image = lime_image_path
                                metric.save()

                        else:
                            return {"error": f"Nodo explainability no soportado aún: {el_type}"}

                    except Exception as e:
                        return {"error": f"Fallo al aplicar explainer '{explainer_type}' en '{el_type}': {str(e)}"}



        return {"message": "Ejecución exitosa"}

    except Exception as e:
        logger.error(f"Error en execute_scenario: {str(e)}")
        return {"error": str(e)}
    

import threading
import time

def topological_sort(elements, connections):
    adj = defaultdict(list)
    in_degree = defaultdict(int)

    for conn in connections:
        adj[conn["startId"]].append(conn["endId"])
        in_degree[conn["endId"]] += 1
        in_degree.setdefault(conn["startId"], 0)

    queue = [node for node, deg in in_degree.items() if deg == 0]
    sorted_order = []

    while queue:
        node = queue.pop(0)
        sorted_order.append(node)
        for neighbor in adj[node]:
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)

    return sorted_order


def build_pipelines_from_design(design, scenario_uuid, config, base_path):
    elements = {e["id"]: e for e in design["elements"]}
    connections = design["connections"]
    prev_map = defaultdict(list)
    for conn in connections:
        prev_map[conn["endId"]].append(conn["startId"])

    sorted_order = topological_sort(elements, connections)
    model_types = set()

    for section in config["sections"].values():
        for key in ["classification", "regression", "anomalyDetection"]:
            for model in section.get(key, []):
                model_types.add(model["type"])

    pipelines = []

    for element_id in sorted_order:
        element = elements[element_id]
        el_type = element["type"]

        if el_type in model_types:
            pipeline_steps = []
            visited = set()
            stack = [element_id]

            while stack:
                node = stack.pop()
                if node in visited:
                    continue
                visited.add(node)

                for prev_id in prev_map.get(node, []):
                    stack.append(prev_id)
                    prev_type = elements[prev_id]["type"]
                    pkl_path = os.path.join(base_path, f'{prev_id}_{scenario_uuid}.pkl')
                    if os.path.exists(pkl_path):
                        instance = joblib.load(pkl_path)
                        pipeline_steps.insert(0, (prev_type, instance))

            model_path = os.path.join(base_path, f'{element_id}_{scenario_uuid}.pkl')
            if os.path.exists(model_path):
                model_instance = joblib.load(model_path)
                pipelines.append((element_id, model_instance, pipeline_steps))

    return pipelines


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def play_scenario_production_by_uuid(request, uuid):
    user = request.user
    try:
        scenario = Scenario.objects.get(uuid=uuid, user=user)
        config = load_config()
        design = json.loads(scenario.design) if isinstance(scenario.design, str) else scenario.design
        anomaly_detector = AnomalyDetector.objects.get(scenario=scenario)
        execution = anomaly_detector.execution
        base_path = os.path.join(settings.MEDIA_ROOT, 'models_storage')
        pipelines = build_pipelines_from_design(design, scenario.uuid, config, base_path)

        if not pipelines:
            return JsonResponse({'error': 'No pipelines found for this scenario.'}, status=400)

        def capture_and_predict_streaming(uuid):
            ssh_command = [
                "ssh", "edulb96@host.docker.internal",
                "sudo -n /opt/homebrew/bin/tshark -l -i en0 -T ek"
            ]
            try:
                logger.info("[START] Lanzando captura en vivo por SSH...")
                proc = subprocess.Popen(ssh_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1)

                flow_dict = defaultdict(list)
                last_flush = time.time()
                interval = 1
                image_counter = get_next_anomaly_index(anomaly_detector)
                logger.info(f"[INFO] Contador de anomalías: {image_counter}")

                while thread_controls.get(uuid, True):
                    line = proc.stdout.readline()
                    if not line:
                        stderr_line = proc.stderr.readline()
                        if stderr_line:
                            logger.warning(f"[SSH STDERR] {stderr_line.strip()}")
                        continue

                    try:
                        pkt = json.loads(line.strip())
                        
                        if "layers" not in pkt:
                            continue

                        layers = pkt["layers"]

                        frame_time = layers["frame"].get("frame_frame_time_epoch")
                        time_ = float(pd.to_datetime(frame_time).timestamp())
                        length = int(layers["frame"].get("frame_frame_len"))

                        src = dst = ttl = proto = None

                        if "ipv6" in layers:
                            proto = layers["ipv6"].get("ipv6_ipv6_nxt", "UNKNOWN")
                            src = layers["ipv6"].get("ipv6_ipv6_src")
                            dst = layers["ipv6"].get("ipv6_ipv6_dst")
                            ttl = layers["ipv6"].get("ipv6_ipv6_hlim")
                        elif "ip" in layers:
                            proto = layers["ip"].get("ip_ip_proto", "UNKNOWN")
                            src = layers["ip"].get("ip_ip_src")
                            dst = layers["ip"].get("ip_ip_dst")
                            ttl = layers["ip"].get("ip_ip_ttl")

                        proto_name = PROTOCOL_MAP.get(str(proto), str(proto)) if proto else "UNKNOWN"
                        logger.info(f"[INFO] Protocolo: {proto_name}, Tiempo: {time_}, Longitud: {length}, TTL: {ttl}")

                        tcp_layer = layers.get("tcp", {})
                        udp_layer = layers.get("udp", {})

                        src_port = tcp_layer.get("tcp_tcp_srcport") or udp_layer.get("udp_udp_srcport") or -1
                        dst_port = tcp_layer.get("tcp_tcp_dstport") or udp_layer.get("udp_udp_dstport") or -1

                        try:
                            src_port = int(src_port)
                        except:
                            src_port = -1

                        try:
                            dst_port = int(dst_port)
                        except:
                            dst_port = -1

                        if not src or not dst:
                            continue

                        if proto_name in ['TCP', 'UDP']:
                            flow_key = tuple(sorted([(src, src_port), (dst, dst_port)])) + (proto_name,)
                        else:
                            flow_key = (src, dst, proto_name)

                        flow_dict[flow_key].append({
                            'time': time_,
                            'length': length,
                            'ttl': int(ttl) if ttl else None
                        })

                    except Exception as parse_err:
                        logger.warning(f"[PARSE ERROR] {parse_err}")
                        continue

                    if time.time() - last_flush >= interval:
                        rows = []
                        for flow, packets in flow_dict.items():
                            times = [p['time'] for p in packets if p['time'] is not None]
                            lengths = [p['length'] for p in packets if p['length'] is not None]
                            ttls = [p['ttl'] for p in packets if p['ttl'] is not None]

                            try:
                                if isinstance(flow[0], tuple) and isinstance(flow[1], tuple):
                                    src, src_port = flow[0]
                                    dst, dst_port = flow[1]
                                    proto = flow[2]
                                else:
                                    src = flow[0]
                                    dst = flow[1]
                                    proto = flow[2]
                                    src_port = -1
                                    dst_port = -1

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
                            except Exception as row_err:
                                logger.warning(f"[FLOW ERROR] Error procesando flow {flow}: {row_err}")
                                continue

                        logger.info(f"[INFO] Flujos procesados: {len(rows)}")
                        flow_dict.clear()
                        last_flush = time.time()

                        df = pd.DataFrame(rows)
                        #df['src_port'] = df['src_port'].fillna(-1)
                        #df['dst_port'] = df['dst_port'].fillna(-1)
                        #df['protocol'] = df['protocol'].fillna('UNKNOWN')
                        logger.info(f"[INFO] Paquetes procesados: {len(df)}")

                        logger.info(f"[INFO] DataFrame antes del preprocesamiento: {df}")

                        if df.empty:
                            continue

                        for element_id, model_instance, steps in pipelines:
                            df_proc = df.copy()
                            
                            for step_type, transformer in steps:
                                if step_type in ["StandardScaler", "MinMaxScaler", "Normalizer", "KNNImputer", "PCA"]:
                                    expected_cols = transformer.feature_names_in_
                                    logger.info(f"[INFO] Columnas esperadas por el transformador {step_type}: {expected_cols}")
                                    
                                    df_proc_transformable = df_proc.reindex(columns=expected_cols, fill_value=0)

                                    df_proc_transformed = transformer.transform(df_proc_transformable)

                                    df_proc_transformed = pd.DataFrame(df_proc_transformed, columns=expected_cols, index=df_proc.index)

                                    df_proc[expected_cols] = df_proc_transformed

                                elif step_type == "OneHotEncoding":
                                    df_proc = pd.get_dummies(df_proc)

                            for ip_col in ['src', 'dst']:
                                if ip_col in df_proc.columns:
                                    df_proc[ip_col] = df_proc[ip_col].apply(ip_to_int)

                            if 'protocol' in df_proc.columns:
                                df_proc['protocol'] = df_proc['protocol'].astype('category').cat.codes

                            logger.info(f"[INFO] DataFrame antes del predict: {df_proc}")
                            logger.info("Columnas al hacer predict: %s", df_proc.columns.tolist())



                            preds = model_instance.predict(df_proc)
                            preds = [1 if x == -1 else 0 for x in preds]

                            df_proc["anomaly"] = preds
                            df["anomaly"] = preds

                            logger.info(f"[MODEL] {model_instance.__class__.__name__} → Anomalías: {sum(preds)}")

                            df_anomalous = df_proc[df_proc["anomaly"] == 1]
                            if not df_anomalous.empty:
                                logger.info("[SHAP] Explicando anomalías con nodo de explicabilidad dinámico...")

                                try:
                                    elements_map = {e["id"]: e for e in design["elements"]}
                                    connections = design["connections"]

                                    explainer_id = next((conn["endId"] for conn in connections if conn["startId"] == element_id and elements_map[conn["endId"]]["type"] in ["SHAP", "LIME"]), None)

                                    if not explainer_id:
                                        logger.info("No se encontró nodo de explicabilidad conectado.")
                                        anomalous_data = df_anomalous.drop(columns=["anomaly"])
                                        for i, row in anomalous_data.iterrows():
                                            anomaly_description = (
                                                f"src: {df.loc[i, 'src']}, "
                                                f"dst: {df.loc[i, 'dst']}, "
                                                f"ports: {df.loc[i, 'src_port']}->{df.loc[i, 'dst_port']} "
                                            )
                                        logger.info(anomaly_description)
                                        save_anomaly_metrics(
                                            detector=anomaly_detector,
                                            model_name=model_instance.__class__.__name__,
                                            feature_name="",
                                            feature_values="",
                                            anomalies=anomaly_description,
                                            execution=execution,
                                            production=True,
                                            anomaly_image=None,
                                            global_shap_image=None,
                                            local_shap_image=None
                                        )
                                    else:
                                        logger.info(f"Encontrado nodo de explicabilidad: {explainer_id}")
                                        explainer_element = elements_map[explainer_id]
                                        el_type = explainer_element["type"]
                                        params = explainer_element.get("parameters", {})
                                        explainer_type = params.get("explainer_type", "").strip()
                                        explainer_module_path = config["sections"]["dataModel"]["explainability"][0]["class"] if el_type == "SHAP" else "lime"

                                        if not explainer_module_path or not explainer_type:
                                            logger.warning(f"Faltan datos de configuración en el nodo de explicabilidad {el_type}")
                                        else:
                                            explainer_class = find_explainer_class(explainer_module_path, explainer_type)

                                            input_data = df_proc.drop(columns=["anomaly"])
                                            anomalous_data = df_anomalous.drop(columns=["anomaly"])

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

                                                if el_type == "SHAP":
                                                    if explainer_type == "KernelExplainer":
                                                        def anomaly_score(X):
                                                            if isinstance(X, np.ndarray):
                                                                X = pd.DataFrame(X, columns=input_data.columns)
                                                            scores = model_instance.decision_function(X)
                                                            return scores

                                                        explainer = explainer_class(anomaly_score, input_data)

                                                    elif explainer_type in ["LinearExplainer", "TreeExplainer", "DeepExplainer"]:
                                                        explainer = explainer_class(model_instance, input_data)

                                                    else:
                                                        explainer = explainer_class(model_instance)

                                                    shap_values = explainer(row_df)

                                                    logger.info(f"[DEBUG] row_df.columns: {row_df.columns}")
                                                    logger.info(f"[DEBUG] input_data.columns: {input_data.columns}")

                                                    contribs = shap_values[0].values 
                                                    shap_contribs = sorted(
                                                        zip(contribs, row.values, row.index),
                                                        key=lambda x: abs(x[0]),
                                                        reverse=True
                                                    )
                                                    top_feature = shap_contribs[0]
                                                    feature_name = top_feature[2]

                                                    src_port_str = str(df.loc[i, 'src_port']) if pd.notna(df.loc[i, 'src_port']) else "N/A"
                                                    dst_port_str = str(df.loc[i, 'dst_port']) if pd.notna(df.loc[i, 'dst_port']) else "N/A"

                                                    anomaly_description = (
                                                        f"src: {df.loc[i, 'src']}, "
                                                        f"dst: {df.loc[i, 'dst']}, "
                                                        f"ports: {src_port_str}->{dst_port_str}, "
                                                        f"protocol: {df.loc[i, 'protocol']}"
                                                    )

                                                    for col in ['src_port', 'dst_port']:
                                                        if col in row and not pd.isnull(row[col]):
                                                            try:
                                                                row[col] = int(row[col])
                                                            except:
                                                                row[col] = -1

                                                    feature_values = row.apply(lambda x: x.item() if hasattr(x, "item") else x).to_dict()

                                                    for ip_key in ['src', 'dst']:
                                                        if ip_key in feature_values:
                                                            val = feature_values[ip_key]
                                                            if isinstance(val, str):
                                                                feature_values[ip_key] = val 
                                                            else:
                                                                try:
                                                                    feature_values[ip_key] = int_to_ip(int(val)) 
                                                                except:
                                                                    feature_values[ip_key] = "UNDEFINED"

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

                                                    logger.info(f"[EXPLANATION] Flujo anómalo #{i}, feature destacada: {feature_name}")

                                                    logger.info(f"[EXPLANATION] Generando anomalía con índice: {image_counter}")

                                                    anomaly_path = save_anomaly_information(feature_values, scenario.uuid, image_counter, df.loc[i, 'protocol'])
                                                    shap_path = save_shap_bar_local(shap_values[0], scenario.uuid, image_counter)

                                                    logger.info(f"[EXPLANATION] Generada anomalía con índice: {image_counter}")

                                                    save_anomaly_metrics(
                                                        detector=anomaly_detector,
                                                        model_name=model_instance.__class__.__name__,
                                                        feature_name=feature_name,
                                                        feature_values=clean_for_json(feature_values),
                                                        anomalies=anomaly_description,
                                                        execution=execution,
                                                        production=True,
                                                        anomaly_image=anomaly_path,
                                                        global_shap_image=None,
                                                        local_shap_image=shap_path,
                                                        global_lime_image=None,
                                                        local_lime_image=None
                                                    )

                                                    image_counter += 1

                                                elif el_type == "LIME":
                                                    logger.info(f"[LIME] Explicando fila {i} con LIME...")
                                                    explainer = explainer_class(
                                                        training_data=input_data.values,
                                                        feature_names=input_data.columns.tolist(),
                                                        mode="regression"
                                                    )

                                                    def anomaly_score(X):
                                                        if isinstance(X, np.ndarray):
                                                            X = pd.DataFrame(X, columns=input_data.columns)
                                                        return model_instance.decision_function(X).reshape(-1, 1)

                                                    exp = explainer.explain_instance(
                                                        row.values,
                                                        anomaly_score,
                                                        num_features=10
                                                    )

                                                    sorted_contribs = sorted(exp.as_list(), key=lambda x: abs(x[1]), reverse=True)
                                                    feature_name = sorted_contribs[0][0] 

                                                    for col in ['src_port', 'dst_port']:
                                                        if col in row and not pd.isnull(row[col]):
                                                            try:
                                                                row[col] = int(row[col])
                                                            except:
                                                                row[col] = -1

                                                    feature_values = row.apply(lambda x: x.item() if hasattr(x, "item") else x).to_dict()
                                                    for ip_key in ['src', 'dst']:
                                                        if ip_key in feature_values:
                                                            val = feature_values[ip_key]
                                                            try:
                                                                feature_values[ip_key] = int_to_ip(int(val))
                                                            except:
                                                                feature_values[ip_key] = "UNDEFINED"

                                                    src_port_str = str(df.loc[i, 'src_port']) if pd.notna(df.loc[i, 'src_port']) else "N/A"
                                                    dst_port_str = str(df.loc[i, 'dst_port']) if pd.notna(df.loc[i, 'dst_port']) else "N/A"

                                                    anomaly_description = (
                                                        f"src: {df.loc[i, 'src']}, "
                                                        f"dst: {df.loc[i, 'dst']}, "
                                                        f"ports: {src_port_str}->{dst_port_str}, "
                                                        f"protocol: {df.loc[i, 'protocol']}"
                                                    )

                                                    anomaly_path = save_anomaly_information(feature_values, scenario.uuid, image_counter, df.loc[i, 'protocol'])

                                                    lime_path = save_lime_bar_local(exp, scenario.uuid, image_counter)

                                                    save_anomaly_metrics(
                                                        detector=anomaly_detector,
                                                        model_name=model_instance.__class__.__name__,
                                                        feature_name=feature_name,
                                                        feature_values=clean_for_json(feature_values),
                                                        anomalies=anomaly_description,
                                                        execution=execution,
                                                        production=True,
                                                        anomaly_image=anomaly_path,
                                                        global_shap_image=None,
                                                        local_shap_image=None,
                                                        global_lime_image=None,
                                                        local_lime_image=lime_path
                                                    )

                                                    image_counter += 1

                                                else:
                                                    logger.warning(f"Nodo explainability no soportado aún: {el_type}")
                                except Exception as e:
                                    logger.warning(f"[SHAP ERROR] No se pudo interpretar con explainer dinámico: {e}")

            except Exception as e:
                logger.error(f"[FATAL ERROR] {e}")
            finally:
                proc.terminate()
                logger.info("[STOP] Captura detenida.")

        thread_controls[uuid] = True
        thread = threading.Thread(target=capture_and_predict_streaming, args=(uuid,), daemon=True)
        thread.start()

        return JsonResponse({'message': 'Captura en tiempo real iniciada'}, status=200)

    except Scenario.DoesNotExist:
        return JsonResponse({'error': 'Scenario not found'}, status=404)
    except Exception as e:
        logger.error("Error en ejecución en producción: %s", str(e))
        return JsonResponse({'error': str(e)}, status=500)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def stop_scenario_production_by_uuid(request, uuid):
    try:
        thread_controls[uuid] = False
        logger.info(f"Parando producción para el escenario {uuid}")
        return JsonResponse({'message': 'Captura detenida'}, status=status.HTTP_200_OK)
    except Exception as e:
        logger.error(f"Error al detener captura: {str(e)}")
        return JsonResponse({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
