# Create your views here.
from django.shortcuts import render
import csv
from django.core.files.base import ContentFile
from io import StringIO
import os
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
from collections import defaultdict
from sklearn.model_selection import train_test_split
from sklearn.metrics import f1_score, precision_score, recall_score, accuracy_score, confusion_matrix, mean_squared_error, mean_absolute_error, r2_score

logger = logging.getLogger('backend')


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
        
        if el_type == "CSV":
            if not appears_in_start:
                raise ValueError(f"El CSV '{element_id}' no aparece como startId.")
            if appears_in_end:
                raise ValueError(f"El CSV '{element_id}' no puede aparecer como endId.")
        
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

def save_anomaly_metrics(detector, model_name, feature_name, feature_values, anomalies, execution):
    AnomalyMetric.objects.create(
        detector=detector,
        model_name=model_name,
        feature_name=feature_name,
        anomalies={
            'values': feature_values.tolist(),
            'anomaly_indices': anomalies
        },
        execution=execution
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

# Views for Scenarios management
@api_view(['POST'])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser])
def create_scenario(request):
    user = request.user  
    data = request.data.dict()
    data['user'] = user.id  

    logger.info(request.data)

    csv_file = request.FILES.get('csv_file')

    if not csv_file:
        return JsonResponse({"error": "At least one CSV file is required."}, status=status.HTTP_400_BAD_REQUEST)

    try:
        existing_file = File.objects.filter(name=csv_file.name).first()

        if existing_file:
            existing_file.references += 1
            existing_file.save()
            file_instance = existing_file
        else:
            csv_content = csv_file.read().decode('utf-8')
            csv_reader = csv.reader(StringIO(csv_content))
            entry_count = sum(1 for _ in csv_reader) - 1  

            file_instance = File.objects.create(
                name=csv_file.name,
                file_type='csv',
                entry_count=entry_count,
                content=ContentFile(csv_content.encode('utf-8'), name=csv_file.name),
                references=1  
            )

    except Exception as e:
        return JsonResponse({"error": f"Error while processing the CSV file: {str(e)}"}, status=status.HTTP_400_BAD_REQUEST)

    data['file'] = file_instance.id
    serializer = ScenarioSerializer(data=data)

    if serializer.is_valid():
        serializer.save(user=user)
        return JsonResponse(serializer.data, status=status.HTTP_201_CREATED)

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
                "execution": metric.execution
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
        csv_file = request.FILES.get('csv_file')  

        if not design_json:
            return JsonResponse({'error': 'Design field is required'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            design = json.loads(design_json)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid design JSON'}, status=status.HTTP_400_BAD_REQUEST)

        scenario.design = design

        if csv_file:
            current_file = scenario.file  

            if not current_file or csv_file.name != current_file.name:
                existing_file = File.objects.filter(name=csv_file.name).first()

                if current_file:
                    current_file.references -= 1
                    if current_file.references == 0:
                        file_path = os.path.join('files', current_file.name) 
                        if os.path.exists(file_path):  
                            os.remove(file_path)
                        current_file.delete()
                    else:
                        current_file.save()

                if existing_file:
                    existing_file.references += 1
                    existing_file.save()
                    scenario.file = existing_file 
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

                    scenario.file = new_file

        serializer = ScenarioSerializer(instance=scenario, data={'design': design}, partial=True)
        if serializer.is_valid():
            serializer.save(user=user)
            return JsonResponse({'message': 'Scenario updated correctly'}, status=status.HTTP_200_OK)
        else:
            logger.error("Serializer errors: %s", serializer.errors)
            return JsonResponse(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    except Scenario.DoesNotExist:
        return JsonResponse({'error': 'Scenario not found'}, status=status.HTTP_404_NOT_FOUND)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_scenario_by_uuid(request, uuid):
    user = request.user  

    try:
        scenario = Scenario.objects.get(uuid=uuid, user=user.id)

        file_instance = scenario.file  
        if file_instance:
            file_instance.references -= 1 
            if file_instance.references == 0:
                file_path = os.path.join('files', file_instance.name)
                if os.path.exists(file_path):  
                    os.remove(file_path)
                file_instance.delete()
            else:
                file_instance.save()

        anomaly_detector = AnomalyDetector.objects.filter(scenario=scenario).first()
        if anomaly_detector:
            ClassificationMetric.objects.filter(detector=anomaly_detector).delete()
            anomaly_detector.delete()

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

        result = execute_scenario(anomaly_detector, design)

        if result.get('error'):
            return JsonResponse(result, status=status.HTTP_400_BAD_REQUEST)

        scenario.status = 'Finished'
        scenario.save()

        return JsonResponse({
            'message': 'Scenario run successfully'
        }, status=status.HTTP_200_OK)

    except Scenario.DoesNotExist:
        return JsonResponse({'error': 'Scenario not found or without permits to run it'}, status=status.HTTP_404_NOT_FOUND)

def execute_scenario(anomaly_detector, design):
    try:
        anomaly_detector.execution += 1
        anomaly_detector.save()
        config = load_config()
        element_types = {}

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
                        if model_data:
                            if el_type == "ClassificationMonitor":
                                metrics_config = params.get("metrics", {})
                                metrics = calculate_classification_metrics(model_data["y_test"], model_data["y_pred"], metrics_config)
                                save_classification_metrics(anomaly_detector, model_element["type"], metrics, anomaly_detector.execution)
                            else:
                                logger.info("Calculando métricas de regresión")
                                metrics = calculate_regression_metrics(model_data["y_test"], model_data["y_pred"])
                                save_regression_metrics(anomaly_detector, model_element["type"], metrics, anomaly_detector.execution)

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
                        
                        data_storage[element_id] = output_data
                        logger.info("Datos inicial: %s", input_data.head())
                        logger.info("Datos transformados: %s", output_data.head())
                        logger.info(data_storage)

                elif category == "model" and input_data is not None:
                    logger.info("Entrenando modelo")
                    model = cls(**extract_parameters(element_def["properties"], params))
                    logger.info("Parámetros: %s", model.get_params())
                    if element_def.get("model_type") == "classification":
                        logger.info("Modelo clasificacion")
                        X = input_data.iloc[:, :-1]
                        y = input_data.iloc[:, -1]
                        logger.info("X: %s", X.head())
                        logger.info("y: %s", y.head())
                        
                        X_train, X_test, y_train, y_test = train_test_split(
                            X, y, test_size=0.2, random_state=42
                        )
                        model.fit(X_train, y_train)
                        y_pred = model.predict(X_test)
                        
                        models[element_id] = {
                            "type": el_type,
                            "y_test": y_test,
                            "y_pred": y_pred
                        }

                    elif element_def.get("model_type") == "regression":
                        logger.info("Modelo regresión")
                        X = input_data.iloc[:, :-1]
                        y = input_data.iloc[:, -1]
                        
                        X_train, X_test, y_train, y_test = train_test_split(
                            X, y, test_size=0.2, random_state=42
                        )
                        
                        model.fit(X_train, y_train)
                        y_pred = model.predict(X_test)

                        models[element_id] = {
                            "type": el_type,
                            "y_test": y_test,
                            "y_pred": y_pred
                        }

                    elif element_def.get("model_type") == "anomalyDetection":
                        logger.info("Modelo Detección de anomalías")
                        model.fit(input_data)
                        predictions = model.predict(input_data)
                        y_pred = [1 if x == -1 else 0 for x in predictions]
                        logger.info("Predicciones: %s", y_pred)
                        for column in input_data.columns:
                            feature_values = input_data[column].values
                            anomalies = [i for i, (val, pred) in enumerate(zip(feature_values, y_pred)) if pred == 1]

                            save_anomaly_metrics(anomaly_detector, el_type, column, feature_values, anomalies, anomaly_detector.execution)
                            
                        models[element_id] = {
                            "type": el_type,
                            "y_pred": y_pred
                        }

        return {"message": "Ejecución exitosa"}

    except Exception as e:
        logger.error(f"Error en execute_scenario: {str(e)}")
        return {"error": str(e)}