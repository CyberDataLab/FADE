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

# Funciones auxiliares
def load_config():
    # Usamos BASE_DIR para obtener la ruta del directorio del proyecto
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    # Asegúrate de que la ruta hacia config.json esté correcta
    CONFIG_PATH = os.path.join(BASE_DIR, 'frontend', 'src', 'assets', 'config.json')

    # Cargar la configuración
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
    
    # Obtener todos los tipos que deben ser "conectados" (start y end)
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
        
        elif el_type == "Monitor":
            if not appears_in_end:
                raise ValueError(f"El Monitor '{element_id}' no aparece como endId.")
            if appears_in_start:
                raise ValueError(f"El Monitor '{element_id}' no puede aparecer como startId.")
        
        elif el_type in must_be_start_and_end:
            if not appears_in_start:
                raise ValueError(f"El elemento '{element_id}' ({el_type}) debería aparecer como startId y no lo hace.")
            if not appears_in_end:
                raise ValueError(f"El elemento '{element_id}' ({el_type}) debería aparecer como endId y no lo hace.")

# Importar clases dinámicamente
def import_class(full_class_name):
    module_name, class_name = full_class_name.rsplit(".", 1)
    module = importlib.import_module(module_name)
    return getattr(module, class_name)

# Extraer parámetros del elemento
def extract_parameters(properties, params):
    extracted = {}
    custom_params = {}  # Almacena parámetros custom para reemplazar

    # Primera pasada: extraer parámetros principales y detectar custom
    for prop in properties:
        prop_name = prop["name"]
        if prop_name in params:
            value = params[prop_name]
            
            # Manejar valores especiales
            if isinstance(value, str):
                if value.lower() == "none":
                    extracted[prop_name] = None
                elif value.lower() == "true":
                    extracted[prop_name] = True
                elif value.lower() == "false":
                    extracted[prop_name] = False
                else:
                    # Intentar convertir a número si es posible
                    try:
                        extracted[prop_name] = int(value)
                    except ValueError:
                        try:
                            extracted[prop_name] = float(value)
                        except ValueError:
                            extracted[prop_name] = value
            else:
                extracted[prop_name] = value

            # Detectar si es un parámetro condicional padre (ej: max_depth="custom")
            if prop.get("type") == "conditional-select" and value == "custom":
                # Buscar el parámetro hijo (ej: custom_max_depth)
                dependent_prop = next(
                    (p for p in properties if p.get("conditional", {}).get("dependsOn") == prop_name),
                    None
                )
                if dependent_prop and params.get(dependent_prop["name"]):
                    custom_params[prop_name] = params[dependent_prop["name"]]

    # Segunda pasada: reemplazar parámetros principales con valores custom
    for main_param, custom_value in custom_params.items():
        extracted[main_param] = int(custom_value)
        # Eliminar el parámetro custom para evitar conflictos
        dependent_prop_name = f"custom_{main_param}"
        if dependent_prop_name in extracted:
            del extracted[dependent_prop_name]

    # Verificar condiciones generales basadas en 'conditional'
    for prop in properties:
        if "conditional" in prop:
            depends_on = prop["conditional"].get("dependsOn")
            
            # Verificar si hay un 'value' o 'values' en la condición
            condition_values = prop["conditional"].get("values", [])
            condition_value = prop["conditional"].get("value", None)

            # Si la propiedad depende de otro parámetro y se especifican valores condicionales
            if depends_on and depends_on in extracted:
                parent_value = extracted[depends_on]
                
                # Verificar si el valor condicional es un solo valor o una lista de valores
                if condition_value:
                    # Si 'value' está presente, lo comparamos con el valor extraído
                    if parent_value != condition_value:
                        extracted.pop(prop["name"], None)
                elif condition_values:
                    # Si 'values' está presente, comparamos si el valor extraído está en la lista
                    if parent_value not in condition_values:
                        extracted.pop(prop["name"], None)

    return extracted

# Calcular métricas
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
    
    # MSE (Mean Squared Error)
    metrics["mse"] = round(mean_squared_error(y_true, y_pred), 2)
    
    # RMSE (Root Mean Squared Error)
    metrics["rmse"] = round(np.sqrt(metrics["mse"]), 2)
    
    # MAE (Mean Absolute Error)
    metrics["mae"] = round(mean_absolute_error(y_true, y_pred), 2)
    
    # R2 (R-squared)
    metrics["r2"] = round(r2_score(y_true, y_pred), 2)
    
    # MSLE (Mean Squared Logarithmic Error)
    metrics["msle"] = round(mean_squared_error(np.log1p(y_true), np.log1p(y_pred)), 2)
    
    return metrics

# Guardar métricas en la base de datos
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

# YA NO HAY DUPLICIDAD DE FICHEROS, FALTA QUE LAS REFERENCIAS SE ACUALICEN SI SE ELIMINA UN ESCENARIO CON ESE FICHERO. SI LAS REFERENCIAS ES 0 QUE SE ELIMINE LA ENTRADA DE LA BBDD
# AL MODIFICAR UN ESCENARIO VER SI HA CAMBIADO EL FICHERO, SI HA CAMBIADO QUE LAS REFERENCIAS DEL ANTERIOR SE DECREMENTEN EN 1 Y SE AÑADA UNA NUEVA ENTRADA EN LA BBDD CON EL NUEVO FICHERO

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
            # Si el archivo ya existe, solo incrementamos las referencias
            existing_file.references += 1
            existing_file.save()
            file_instance = existing_file
        else:
            # Si no existe, lo guardamos como nuevo
            csv_content = csv_file.read().decode('utf-8')
            csv_reader = csv.reader(StringIO(csv_content))
            entry_count = sum(1 for _ in csv_reader) - 1  

            file_instance = File.objects.create(
                name=csv_file.name,
                file_type='csv',
                entry_count=entry_count,
                content=ContentFile(csv_content.encode('utf-8'), name=csv_file.name),
                references=1  # Primera referencia
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

        # Actualizamos el diseño
        scenario.design = design

        # Si hay un nuevo CSV, verificamos si es diferente del actual
        if csv_file:
            current_file = scenario.file  # Archivo actual del escenario

            if not current_file or csv_file.name != current_file.name:
                # Si hay un archivo previo, reducimos las referencias
                if current_file:
                    current_file.references -= 1
                    if current_file.references == 0:
                        current_file.delete()  # Si ya no tiene referencias, lo eliminamos
                    else:
                        current_file.save()

                # Procesamos el nuevo archivo
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

                scenario.file = new_file  # Asignamos el nuevo archivo

        serializer = ScenarioSerializer(instance=scenario, data={'design': design}, partial=True)
        if serializer.is_valid():
            serializer.save(user=user)
            return JsonResponse({'message': 'Scenario updated correctly'}, status=status.HTTP_200_OK)
        else:
            logger.error("Serializer errors: %s", serializer.errors)
            return JsonResponse(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    except Scenario.DoesNotExist:
        return JsonResponse({'error': 'Scenario not found or without permits'}, status=status.HTTP_404_NOT_FOUND)

@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_scenario_by_uuid(request, uuid):
    user = request.user  

    try:
        scenario = Scenario.objects.get(uuid=uuid, user=user.id)

        # Verificar si el escenario tiene un archivo asociado
        file_instance = scenario.file  
        if file_instance:
            file_instance.references -= 1  # Decrementamos referencias
            if file_instance.references == 0:
                # Si las referencias son 0, eliminamos el archivo físico y la entrada en la BD
                file_path = os.path.join('files', file_instance.name)  # Usamos 'files' como directorio
                if os.path.exists(file_path):  
                    os.remove(file_path)  # Borra el archivo del sistema de archivos
                file_instance.delete()  # Borra la entrada en la base de datos
            else:
                file_instance.save()  # Guardamos el decremento de referencias

        # Eliminar anomaly detector y métricas asociadas
        anomaly_detector = AnomalyDetector.objects.filter(scenario=scenario).first()
        if anomaly_detector:
            ClassificationMetric.objects.filter(detector=anomaly_detector).delete()
            anomaly_detector.delete()

        # Finalmente, eliminamos el escenario
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

# Función principal
def execute_scenario(anomaly_detector, design):
    try:
        anomaly_detector.execution += 1
        anomaly_detector.save()
        config = load_config()
        element_types = {}

        validate_design(config, design)
        
        # Cargar tipos de elementos desde la configuración
        for section_name, section in config["sections"].items():
            if section_name == "dataModel":
                # Modelos clasificacion
                for model in section.get("classification", []):
                    model["model_type"] = "classification"  # Nueva clave
                    element_types[model["type"]] = model
                # Modelos regresion
                for model in section.get("regression", []):
                    model["model_type"] = "regression"  # Nueva clave
                    element_types[model["type"]] = model
                # Modelos deteccion de anomalias
                for model in section.get("anomalyDetection", []):
                    model["model_type"] = "anomalyDetection"  # Nueva clave
                    element_types[model["type"]] = model
                # Monitoring
                for model in section.get("monitoring", []):
                    element_types[model["type"]] = model
            elif "elements" in section:
                for element in section["elements"]:
                    element_types[element["type"]] = element


        elements = {e["id"]: e for e in design["elements"]}
        connections = design["connections"]
        
        # Construir grafo de dependencias
        adj = defaultdict(list)
        in_degree = defaultdict(int)
        for conn in connections:
            adj[conn["startId"]].append(conn["endId"])
            in_degree[conn["endId"]] += 1
            if conn["startId"] not in in_degree:
                in_degree[conn["startId"]] = 0

        # Orden topológico
        queue = [node for node, count in in_degree.items() if count == 0]
        sorted_order = []
        while queue:
            node = queue.pop(0)
            sorted_order.append(node)
            for neighbor in adj[node]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)


        data_storage = {}  # Almacena DataFrames por elemento
        models = {}

        for element_id in sorted_order:
            element = elements[element_id]
            el_type = element["type"]
            logger.info("Procesando elemento %s", el_type)
            params = element.get("parameters", {})
            
            # Obtener datos de entrada de las conexiones entrantes
            input_data = None
            for conn in connections:
                if conn["endId"] == element_id:
                    predecessor_id = conn["startId"]
                    input_data = data_storage.get(predecessor_id)
                    break  # Asume una sola conexión entrante
            
            # Procesar elemento
            # En la sección donde se procesa el CSV, cambiar:
            if el_type == "CSV":
                logger.info("Cargando CSV")
                # Cargar CSV desde la base de datos
                csv_file_name = params.get("csvFileName")
                try:
                    file = File.objects.get(name=csv_file_name)
                    df = pd.read_csv(file.content)
                except Exception as e:
                    return {"error": f"Error loading CSV: {str(e)}"}
                
                # Nueva lógica para manejar ambos formatos (backward compatibility)
                columns = params.get("columns", [])
                selected_columns = []
                
                if isinstance(columns, list):
                    # Nuevo formato: array de objetos ordenados
                    selected_columns = [col["name"] for col in columns if col.get("selected", True)]
                elif isinstance(columns, dict):
                    # Formato antiguo: diccionario (mantener para compatibilidad)
                    selected_columns = [col for col, keep in columns.items() if keep]
                
                logger.info("Columnas seleccionadas en orden original: %s", selected_columns)
                
                try:
                    # Preservar orden original del CSV
                    df = df[selected_columns]
                except KeyError as e:
                    return {"error": f"Columna no encontrada en CSV: {str(e)}"}
                except Exception as e:
                    return {"error": f"Error procesando columnas: {str(e)}"}
                
                data_storage[element_id] = df

            elif el_type == "Monitor":
                logger.info("Monitorizando")
                # Procesar todas las entradas de modelos conectados
                for conn in connections:
                    if conn["endId"] == element_id:
                        model_id = conn["startId"]
                        model_data = models.get(model_id)
                        if model_data:
                            y_test, y_pred = model_data["y_test"], model_data["y_pred"]
                            metrics_config = params.get("metrics", {})
                            metrics = calculate_classification_metrics(y_test, y_pred, metrics_config)
                            save_classification_metrics(anomaly_detector, model_data["type"], metrics, anomaly_detector.execution)

            else:
                # Obtener configuración del elemento
                element_def = element_types.get(el_type)
                logger.info("Definición del elemento: %s", element_def)
                if not element_def:
                    return {"error": f"Tipo de elemento desconocido: {el_type}"}
                
                # Cargar clase dinámicamente
                cls = import_class(element_def["class"])
                category = element_def.get("category", "")
                
                # Procesamiento según categoría
                if category == "preprocessing":
                    applies_to = element_def.get("appliesTo", "all")
                    transformer = cls(**extract_parameters(element_def["properties"], params))
                    
                    if input_data is not None:
                        # Detectar si hay variable objetivo
                        if 'target' in input_data.columns:
                            # Si tienes una columna de target, es supervisado
                            target_column = input_data['target']  # O usa el nombre de la columna de target que tengas
                            input_features = input_data.drop(columns=['target'])  # Eliminar la columna objetivo

                            if applies_to == "numeric":
                                # Seleccionar solo las columnas numéricas
                                numeric_cols = input_features.select_dtypes(include=['number']).columns
                                transformed = transformer.fit_transform(input_features[numeric_cols])
                                
                                # Crear una copia de los datos originales
                                output_data = input_data.copy()
                                output_data[numeric_cols] = transformed  # Reemplazar solo las columnas numéricas

                            elif applies_to == "categorical":
                                # Para columnas categóricas
                                categorical_cols = input_features.select_dtypes(exclude=['number']).columns
                                output_data = pd.get_dummies(input_data, columns=categorical_cols)

                            else:
                                # Si no se aplica ni a numéricas ni a categóricas, aplicamos la transformación a todo
                                output_data = input_data.copy()
                                output_data[input_features.columns] = transformer.fit_transform(input_features)
                            
                            # Reincluir la columna de target que se había eliminado
                            output_data['target'] = target_column
                            
                        else:
                            # Si no tienes columna de target, es no supervisado
                            if applies_to == "numeric":
                                # Seleccionar solo las columnas numéricas
                                numeric_cols = input_data.select_dtypes(include=['number']).columns
                                transformed = transformer.fit_transform(input_data[numeric_cols])
                                
                                # Crear una copia de los datos originales
                                output_data = input_data.copy()
                                output_data[numeric_cols] = transformed  # Reemplazar solo las columnas numéricas

                            elif applies_to == "categorical":
                                # Para columnas categóricas
                                categorical_cols = input_data.select_dtypes(exclude=['number']).columns
                                output_data = pd.get_dummies(input_data, columns=categorical_cols)

                            else:
                                # Para otros casos, transformamos todas las columnas numéricas
                                output_data = pd.DataFrame(
                                    transformer.fit_transform(input_data),
                                    columns=input_data.columns
                                )
                        
                        # Almacenar los datos transformados
                        data_storage[element_id] = output_data
                        logger.info("Datos inicial: %s", input_data.head())
                        logger.info("Datos transformados: %s", output_data.head())
                        logger.info(data_storage)

                elif category == "model" and input_data is not None:
                    logger.info("Entrenando modelo")
                    # Entrenar modelo
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
                        
                        # Calcular las métricas de regresión
                        metrics = calculate_regression_metrics(y_test, y_pred)
                        
                        # Guardar las métricas de regresión
                        save_regression_metrics(anomaly_detector, model_data["type"], metrics, anomaly_detector.execution)

                    elif element_def.get("model_type") == "anomalyDetection":
                        logger.info("Modelo Detección de anomalías")
                        model.fit(input_data)
                        predictions = model.predict(input_data)
                        y_pred = [1 if x == -1 else 0 for x in predictions]
                        logger.info("Predicciones: %s", y_pred)
                        for column in input_data.columns:
                            feature_values = input_data[column].values
                            anomalies = [i for i, (val, pred) in enumerate(zip(feature_values, y_pred)) if pred == 1]

                            # Llamar a la función para guardar las métricas de anomalía
                            save_anomaly_metrics(anomaly_detector, el_type, column, feature_values, anomalies, anomaly_detector.execution)
                            
                        models[element_id] = {
                            "type": el_type,
                            "y_pred": y_pred
                        }

        return {"message": "Ejecución exitosa"}

    except Exception as e:
        logger.error(f"Error en execute_scenario: {str(e)}")
        return {"error": str(e)}