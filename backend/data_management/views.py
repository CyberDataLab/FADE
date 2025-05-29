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
import importlib
import shap
from celery import shared_task
from collections import defaultdict
from sklearn.model_selection import train_test_split
from sklearn.metrics import f1_score, precision_score, recall_score, accuracy_score, confusion_matrix, mean_squared_error, mean_absolute_error, r2_score

logger = logging.getLogger('backend')

thread_controls = {}


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
    
    data_processing_types = [el["type"] for el in config.get("dataProcessing", {}).get("elements", [])]
    classification_types = [el["type"] for el in config.get("sections", {}).get("dataModel", {}).get("classification", [])]
    regression_types = [el["type"] for el in config.get("sections", {}).get("dataModel", {}).get("regression", [])]
    
    must_be_start_and_end = set(data_processing_types + classification_types + regression_types)
    
    for element_id, element in elements.items():
        el_type = element["type"]
        appears_in_start = element_id in start_ids
        appears_in_end = element_id in end_ids
        
        if el_type in ["CSV", "Network"]:
            if not appears_in_start:
                raise ValueError(f"El {el_type} '{element_id}' no aparece como startId.")
            if appears_in_end:
                raise ValueError(f"El {el_type} '{element_id}' no puede aparecer como endId.")
        
        if el_type in ["ClassificationMonitor", "RegressionMonitor"]:
            if not appears_in_end:
                raise ValueError(f"El {el_type} '{element_id}' debe ser endId")
            if appears_in_start:
                raise ValueError(f"El {el_type} '{element_id}' no puede ser startId")
        
        elif el_type in must_be_start_and_end:
            if not appears_in_start:
                raise ValueError(f"El elemento '{element_id}' ({el_type}) debería aparecer como startId y no lo hace.")
            if not appears_in_end:
                raise ValueError(f"El elemento '{element_id}' ({el_type}) debería aparecer como endId y no lo hace.")

def import_class(full_class_name):
    module_name, class_name = full_class_name.rsplit(".", 1)
    module = importlib.import_module(module_name)
    return getattr(module, class_name)

import tempfile

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
                proto = pkt.transport_layer if hasattr(pkt, 'transport_layer') else pkt.highest_layer

                src_port = pkt[pkt.transport_layer].srcport if proto and hasattr(pkt[pkt.transport_layer], 'srcport') else None
                dst_port = pkt[pkt.transport_layer].dstport if proto and hasattr(pkt[pkt.transport_layer], 'dstport') else None

                flags = pkt.tcp.flags if hasattr(pkt, 'tcp') and hasattr(pkt.tcp, 'flags') else None
                ttl = pkt.ip.ttl if hasattr(pkt.ip, 'ttl') else None

                flow_key = tuple(sorted([(src, src_port), (dst, dst_port)])) + (proto,)

                flow_dict[flow_key].append({
                    'time': time,
                    'length': length,
                    'ttl': int(ttl) if ttl else None,
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
            'src': flow[0][0],
            'src_port': flow[0][1],
            'dst': flow[1][0],
            'dst_port': flow[1][1],
            'protocol': flow[2],
            'packet_count': len(packets),
            'total_bytes': sum(lengths),
            'avg_packet_size': sum(lengths) / len(lengths) if lengths else 0,
            'flow_duration': max(times) - min(times) if times else 0,
            'avg_ttl': sum(ttls) / len(ttls) if ttls else None,
        })

    df = pd.DataFrame(aggregated)
    df.to_csv("features_por_flujo.csv", index=False)
    logger.info("DataFrame agregado: %s", df)
    return df

import ipaddress

def ip_to_int(ip_str):
    try:
        return int(ipaddress.IPv4Address(ip_str))
    except:
        return 0
    
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

def save_anomaly_metrics(detector, model_name, feature_name, feature_values, anomalies, execution, production):
    if production:
        AnomalyMetric.objects.create(
            detector=detector,
            model_name=model_name,
            feature_name=feature_name,
            anomalies={
                'values': feature_values,
                'anomaly_indices': anomalies
            },
            execution=execution,
            production=production
        )
    else:
        AnomalyMetric.objects.create(
            detector=detector,
            model_name=model_name,
            feature_name=feature_name,
            anomalies={
                'values': feature_values.tolist(),
                'anomaly_indices': anomalies
            },
            execution=execution,
            production=production
        )

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
                "production": metric.production
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
                    "production": metric.production
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

        # Gestionar archivos actuales
        current_files = list(scenario.files.all())

        updated_files = []

        # Procesar archivos CSV nuevos
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

        # Procesar archivos PCAP nuevos
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

        # Eliminar referencias anteriores que ya no están en los nuevos archivos
        for old_file in current_files:
            if old_file not in updated_files:
                old_file.references -= 1
                if old_file.references <= 0:
                    file_path = os.path.join(settings.MEDIA_ROOT, old_file.content.name)
                    if os.path.exists(file_path):
                        os.remove(file_path)
                    old_file.delete()
                else:
                    old_file.save()

        # Asociar nuevos archivos al escenario
        scenario.files.set(updated_files)

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

        # Procesar todos los archivos asociados (csv y pcap)
        for file_instance in scenario.files.all():
            file_instance.references -= 1
            if file_instance.references <= 0:
                # Construir ruta del archivo
                file_path = os.path.join(settings.MEDIA_ROOT, file_instance.content.name)
                if os.path.exists(file_path):
                    os.remove(file_path)
                file_instance.delete()
            else:
                file_instance.save()

        # Eliminar métrica y detector si existe
        anomaly_detector = AnomalyDetector.objects.filter(scenario=scenario).first()
        if anomaly_detector:
            ClassificationMetric.objects.filter(detector=anomaly_detector).delete()
            anomaly_detector.delete()

        # Eliminar modelos almacenados
        base_path = os.path.join(settings.BASE_DIR, 'models_storage')
        scenario_uuid = str(scenario.uuid)

        for filename in os.listdir(base_path):
            if scenario_uuid in filename:
                model_path = os.path.join(base_path, filename)
                logger.info(f"Eliminando modelo: {model_path}")
                try:
                    os.remove(model_path)
                    logger.info(f"Modelo eliminado: {model_path}")
                except Exception as e:
                    logger.warning(f"No se pudo eliminar {model_path}: {str(e)}")

        # Eliminar el escenario
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


        data_storage = {} 
        models = {}

        for element_id in sorted_order:
            element = elements[element_id]
            el_type = element["type"]
            logger.info("Procesando elemento %s", el_type)
            params = element.get("parameters", {})
            
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

                    # Detección automática
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
                cls = import_class(element_def["class"])
                
                category = element_def.get("category", "")
                
                if category == "preprocessing":
                    applies_to = element_def.get("appliesTo", "all")
                    transformer = cls(**extract_parameters(element_def["properties"], params))
                    
                    if input_data is not None:
                        if 'target' in input_data.columns:
                            target_column = input_data['target']
                            input_features = input_data.drop(columns=['target'])

                            if applies_to == "numeric":
                                numeric_cols = input_features.select_dtypes(include=['number']).columns
                                transformed = transformer.fit_transform(input_features[numeric_cols])
                                
                                output_data = input_data.copy()
                                output_data[numeric_cols] = transformed

                            elif applies_to == "categorical":
                                categorical_cols = input_features.select_dtypes(exclude=['number']).columns
                                output_data = pd.get_dummies(input_data, columns=categorical_cols)

                            else:
                                output_data = input_data.copy()
                                output_data[input_features.columns] = transformer.fit_transform(input_features)
                            
                            output_data['target'] = target_column
                            
                        else:
                            if applies_to == "numeric":
                                numeric_cols = input_data.select_dtypes(include=['number']).columns
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
                        step_path = os.path.join(settings.BASE_DIR, 'models_storage', f"{step_id}.pkl")

                        joblib.dump(transformer, step_path)
                        logger.info(f"Guardado: {step_path}")

                        data_storage[element_id] = output_data
                        logger.info("Datos inicial: %s", input_data.head())
                        logger.info("Datos transformados: %s", output_data.head())
                        logger.info(data_storage)

                elif category == "model" and input_data is not None:
                    logger.info("Entrenando modelo")
                    model = cls(**extract_parameters(element_def["properties"], params))
                    logger.info(model.get_params())

                    if element_def.get("model_type") in ["classification", "regression"]:
                        logger.info(f"Entrenamiento modelo {element_def.get('model_type')}")

                        if splitter or code_splitter:
                            for conn in connections:
                                if conn["endId"] == element_id:
                                    source_id = conn["startId"]
                                    output_type = conn.get("startOutput")

                                    if output_type == "train":
                                        X_train, y_train = data_storage[source_id]["train"]
                                        logger.info(X_train)
                                        logger.info(y_train)

                                        model.fit(X_train, y_train)
                                        data_storage[element_id] = model

                                    elif output_type == "test":
                                        X_test, y_test = data_storage[source_id]["test"]
                                        logger.info(X_test)
                                        logger.info(y_test)
                                        trained_model = data_storage.get(element_id)

                                        if trained_model:
                                            y_pred = trained_model.predict(X_test)
                                            models[element_id] = {
                                                "type": el_type,
                                                "y_test": y_test,
                                                "y_pred": y_pred
                                            }

                        else:
                            logger.info("Entrenando modelo sin splitter - 80/20")
                            X = input_data.iloc[:, :-1]
                            y = input_data.iloc[:, -1]
                            X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

                            model.fit(X_train, y_train)
                            y_pred = model.predict(X_test)

                            models[element_id] = {
                                "type": el_type,
                                "y_test": y_test,
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

                        # Eliminar columnas claramente no numéricas
                        #input_copy = input_copy.drop(columns=[col for col in input_copy.columns if input_copy[col].dtype == 'object'])

                        if input_copy.empty:
                            return {"error": "No hay columnas numéricas después del preprocesamiento"}
                        
                        logger.info("Datos preprocesados para detección de anomalías: %s", input_copy)

                        input_copy.to_csv("input_copy.csv", index=False)

                        model.fit(input_copy)
                        step_id = f"{element_id}_{scenario.uuid}"
                        step_path = os.path.join(settings.BASE_DIR, 'models_storage', f"{step_id}.pkl")

                        joblib.dump(model, step_path)
                        logger.info(f"Guardado: {step_path}")

                        predictions = model.predict(input_copy)
                        y_pred = [1 if x == -1 else 0 for x in predictions]
                        logger.info("Predicciones: %s", y_pred)

                        for column in input_copy.columns:
                            feature_values = input_copy[column].values
                            anomalies = [i for i, (val, pred) in enumerate(zip(feature_values, y_pred)) if pred == 1]

                            save_anomaly_metrics(anomaly_detector, el_type, column, feature_values, anomalies, anomaly_detector.execution, production=False)

                        models[element_id] = {
                            "type": el_type,
                            "y_pred": y_pred
                        }


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
                pipelines.append((model_instance, pipeline_steps))

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
        base_path = os.path.join(settings.BASE_DIR, 'models_storage')
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

                        src_port = layers.get("tcp", {}).get("tcp_tcp_srcport") or layers.get("udp", {}).get("udp_udp_srcport")
                        dst_port = layers.get("tcp", {}).get("tcp_tcp_dstport") or layers.get("udp", {}).get("udp_udp_dstport")

                        if not src or not dst:
                            continue

                        flow_key = tuple(sorted([(src, src_port), (dst, dst_port)])) + (proto,)
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

                            rows.append({
                                'src': flow[0][0],
                                'src_port': flow[0][1],
                                'dst': flow[1][0],
                                'dst_port': flow[1][1],
                                'protocol': flow[2],
                                'packet_count': len(packets),
                                'total_bytes': sum(lengths),
                                'avg_packet_size': sum(lengths) / len(lengths) if lengths else 0,
                                'flow_duration': max(times) - min(times) if times else 0,
                                'avg_ttl': sum(ttls) / len(ttls) if ttls else None,
                            })
                        logger.info(f"[INFO] Flujos procesados: {len(rows)}")
                        flow_dict.clear()
                        last_flush = time.time()

                        df = pd.DataFrame(rows)
                        logger.info(f"[INFO] Paquetes procesados: {len(df)}")

                        if df.empty:
                            continue

                        for model_instance, steps in pipelines:
                            df_proc = df.copy()
                            for step_type, transformer in steps:
                                if step_type in ["StandardScaler", "MinMaxScaler", "Normalizer", "KNNImputer", "PCA"]:
                                    numeric_cols = df_proc.select_dtypes(include=['number']).columns
                                    df_proc[numeric_cols] = transformer.fit_transform(df_proc[numeric_cols])
                                elif step_type == "OneHotEncoding":
                                    df_proc = pd.get_dummies(df_proc)

                            for ip_col in ['src', 'dst']:
                                if ip_col in df_proc.columns:
                                    df_proc[ip_col] = df_proc[ip_col].apply(ip_to_int)

                            if 'protocol' in df_proc.columns:
                                df_proc['protocol'] = df_proc['protocol'].astype('category').cat.codes

                            preds = model_instance.predict(df_proc)
                            preds = [1 if x == -1 else 0 for x in preds]

                            df_proc["anomaly"] = preds
                            df["anomaly"] = preds

                            logger.info(f"[MODEL] {model_instance.__class__.__name__} → Anomalías: {sum(preds)}")

                            df_anomalous = df_proc[df_proc["anomaly"] == 1]
                            if not df_anomalous.empty:
                                logger.info("[SHAP] Explicando anomalías con SHAP...")

                                try:
                                    explainer = shap.KernelExplainer(model_instance.decision_function, df_proc.drop(columns=["anomaly"]))
                                    shap_values = explainer.shap_values(df_anomalous.drop(columns=["anomaly"]))

                                    anomaly_indices = df_anomalous.index.tolist()

                                    for i, index in enumerate(anomaly_indices):
                                        logger.info(f"[ANOMALY FLOW #{index}] src: {df.loc[index, 'src']}, dst: {df.loc[index, 'dst']}, ports: {df.loc[index, 'src_port']}->{df.loc[index, 'dst_port']}, proto: {df.loc[index, 'protocol']}")

                                        row_data = df_anomalous.drop(columns=["anomaly"]).iloc[i]
                                        contribs = shap_values[i]
                                        shap_contribs = sorted(
                                            zip(contribs, row_data.values, row_data.index),
                                            key=lambda x: abs(x[0]),
                                            reverse=True
                                        )

                                        top_feature = shap_contribs[0]
                                        feature_name = top_feature[2]

                                        anomaly_description = (
                                            f"src: {df.loc[index, 'src']}, "
                                            f"dst: {df.loc[index, 'dst']}, "
                                            f"ports: {df.loc[index, 'src_port']}->{df.loc[index, 'dst_port']} "
                                        )

                                        feature_values = row_data.apply(lambda x: x.item() if hasattr(x, "item") else x).to_dict()
                                        logger.info("PRUEBA")
                                        logger.info(feature_values)

                                        save_anomaly_metrics(
                                            detector=anomaly_detector,
                                            model_name=model_instance.__class__.__name__,
                                            feature_name=feature_name,
                                            feature_values=feature_values,
                                            anomalies=anomaly_description,
                                            execution=execution,
                                            production=True
                                        )

                                except Exception as shap_err:
                                    logger.warning(f"[SHAP ERROR] No se pudo interpretar: {shap_err}")

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
