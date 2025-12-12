# Create your views here.
from django.shortcuts import render
import csv
from django.core.files.base import ContentFile
from io import StringIO
import os
import joblib
import subprocess
import threading
from django.conf import settings
from rest_framework.parsers import MultiPartParser
from rest_framework.decorators import api_view, permission_classes, parser_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from .models import Scenario, File, ScenarioModel, ClassificationMetric, RegressionMetric, AnomalyMetric
from .serializers import ScenarioSerializer
from django.http import JsonResponse
from system_monitor.models import SystemConfiguration
import logging
import json
import pandas as pd
import numpy as np
import copy
import shap
from celery import shared_task
from collections import defaultdict
from sklearn.model_selection import train_test_split

from .utils import *
from netanoms_runtime.detection import run_live_production
from netanoms_runtime.ssh_config import SSHConfig
from netanoms_runtime.capture_config import CaptureConfig
from netanoms_runtime.explainability_config import ExplainabilityConfig

logger = logging.getLogger('backend')

production_handles = {}

@api_view(['POST'])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser])
def create_scenario(request):
    """
    Creates a new scenario by uploading one or more CSV or PCAP files.

    Expects (multipart/form-data):
        - csv_files: List of CSV files.
        - network_files: List of PCAP files.
        - jsonl_files: List of JSONL files.
        - Additional scenario metadata fields (e.g., name, description, etc.) as part of the form data.

    Behavior:
        - Parses the form data and associates the scenario with the authenticated user.
        - For each CSV file:
            - If it already exists in the database (by name), increments reference count.
            - If new, counts its entries, stores its content, and saves it.
        - For each PCAP file:
            - If it already exists in the database (by name), increments reference count.
            - If new, stores its binary content and saves it.
        - For each JSONL file:
            - If it already exists in the database (by name), increments reference count.
            - If new, stores its binary content and saves it.
        - Links all uploaded files to the created scenario.

    Returns:
        - 201 Created with the serialized scenario if successful.
        - 400 Bad Request if files are missing or errors occur in processing or serialization.
    """

    # Get the user from the request
    user = request.user  

    # Parse the request data and prepare the scenario data
    data = request.data.dict()
    data['user'] = user.id  

    logger.info(f"[CREATE SCENARIO] Request data: {request.data}")

    # Get the uploaded files from the request
    csv_files = request.FILES.getlist('csv_files')
    network_files = request.FILES.getlist('network_files')
    jsonl_files = request.FILES.getlist('jsonl_files')

    logger.info(f"[CREATE SCENARIO] CSV files received: {[f.name for f in csv_files]}")
    logger.info(f"[CREATE SCENARIO] PCAP files received: {[f.name for f in network_files]}")
    logger.info(f"[CREATE SCENARIO] JSONL files received: {[f.name for f in jsonl_files]}")

    # Check if at least one CSV or PCAP file is provided
    if not csv_files and not network_files and not jsonl_files:
        # Return an error response if no files are provided
        return JsonResponse({"error": "At least one CSV, PCAP or JSONL file is required."}, status=status.HTTP_400_BAD_REQUEST)

    saved_files = []

    try:
        # Process CSV files
        for csv_file in csv_files:

            # Check if the file already exists in the database
            existing_file = File.objects.filter(name=csv_file.name).first()

            # If it exists, increment the reference count
            if existing_file:
                existing_file.references += 1
                existing_file.save()
                saved_files.append(existing_file)
                logger.info(f"[CREATE SCENARIO] Existing CSV file found: {csv_file.name} (references updated to {existing_file.references})")
            
            # If it does not exist, read the content, count entries, and save it
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
                logger.info(f"[CREATE SCENARIO] New CSV file saved: {csv_file.name} (entries: {entry_count})")

        # Process PCAP files
        for network_file in network_files:

            # Check if the file already exists in the database
            existing_file = File.objects.filter(name=network_file.name).first()

            # If it exists, increment the reference count
            if existing_file:
                existing_file.references += 1
                existing_file.save()
                saved_files.append(existing_file)
                logger.info(f"[CREATE SCENARIO] Existing PCAP file found: {network_file.name} (references updated to {existing_file.references})")
            
            # If it does not exist, read the content and save it
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
                logger.info(f"[CREATE SCENARIO] New PCAP file saved: {network_file.name}")

        for jsonl_file in jsonl_files:

            # Check if the file already exists in the database
            existing_file = File.objects.filter(name=jsonl_file.name).first()

            # If it exists, increment the reference count
            if existing_file:
                existing_file.references += 1
                existing_file.save()
                saved_files.append(existing_file)
                logger.info(f"[CREATE SCENARIO] Existing Log file found: {jsonl_file.name} (references updated to {existing_file.references})")
            
            # If it does not exist, read the content, count entries, and save it
            else:
                log_content = jsonl_file.read()
                new_file = File.objects.create(
                    name=jsonl_file.name,
                    file_type='jsonl',
                    entry_count=0,
                    content=ContentFile(log_content, name=jsonl_file.name),
                    references=1
                )
                saved_files.append(new_file)
                logger.info(f"[CREATE SCENARIO] New JSONL file saved: {jsonl_file.name}")

    except Exception as e:
        # Return an error response if there is an issue processing the files
        return JsonResponse({"error": f"Error while processing the files: {str(e)}"}, status=status.HTTP_400_BAD_REQUEST)

    # Prepare the scenario data with the uploaded files
    serializer = ScenarioSerializer(data=data)

    # If the serializer is valid, save the scenario and associate it with the user and files
    if serializer.is_valid():
        user.number_designs_created += 1
        user.save()
        scenario_instance = serializer.save(user=user)
        scenario_instance.files.set(saved_files)

        # Return a success response with the serialized scenario data
        return JsonResponse(ScenarioSerializer(scenario_instance).data, status=status.HTTP_201_CREATED)

    # Return an error response if the serializer is not valid
    return JsonResponse(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_scenarios_by_user(request):
    """
    Retrieves all scenarios created by the authenticated user.

    Returns:
        - 200 OK with a list of serialized scenarios if any exist.
        - Always returns an empty list if no scenarios exist for the user.
    """

    # Get the user from the request
    user = request.user  

    # Fetch all scenarios associated with the user
    scenarios = Scenario.objects.filter(user=user.id)

    # If no scenarios are found, return an empty list
    serializer = ScenarioSerializer(scenarios, many=True)
    
    # Return the serialized scenarios as a JSON response
    return JsonResponse(serializer.data, safe=False, status=status.HTTP_200_OK)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_scenario_by_uuid(request, uuid):
    """
    Retrieves a specific scenario by UUID for the authenticated user.

    Args:
        uuid (str): UUID of the scenario to retrieve.

    Returns:
        - 200 OK with serialized scenario if found.
        - 404 Not Found if the scenario does not exist or is not owned by the user.
    """

    # Get the user from the request
    user = request.user 

    try:
        # Fetch the scenario by UUID and user ID
        scenario = Scenario.objects.get(uuid=uuid, user=user.id)

        # Serialize the scenario data
        serializer = ScenarioSerializer(scenario)  

        # Return the serialized data as a JSON response
        return JsonResponse(serializer.data, safe=False, status=status.HTTP_200_OK) 
    
    except Scenario.DoesNotExist:

        # Return 404 if the scenario does not exist or the user does not have permission to access it
        return JsonResponse({'error': 'Scenario not found or you do not have permission to access it'}, status=status.HTTP_404_NOT_FOUND)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_scenario_classification_metrics_by_uuid(request, uuid):
    """
    Retrieves all classification metrics for a given scenario UUID.

    Args:
        uuid (str): UUID of the scenario.

    Behavior:
        - Fetches the Scenario instance by UUID.
        - Finds the associated AnomalyDetector instance.
        - Retrieves all ClassificationMetric entries related to that scenario model, ordered by date descending.
        - Ensures that SHAP/LIME image fields are returned as lists (even if stored as single strings).

    Returns:
        - 200 OK with a list of metrics and associated explanation images.
        - 404 Not Found if scenario or scenario model is missing.
        - 500 Internal Server Error for any other exception.
    """

    try:

        # Fetch the scenario by UUID
        scenario = Scenario.objects.get(uuid=uuid)

        # Fetch the associated scenario model
        scenario_model = ScenarioModel.objects.get(scenario=scenario)

        # Retrieve all classification metrics for the scenario model, ordered by date
        metrics = ClassificationMetric.objects.filter(scenario_model=scenario_model).order_by('-date')

        # Prepare the metrics data for the response
        metrics_data = [
            {
                "model_name": metric.model_name,
                "accuracy": metric.accuracy,
                "precision": metric.precision,
                "recall": metric.recall,
                "f1_score": metric.f1_score,
                "confusion_matrix": metric.confusion_matrix,
                "date": metric.date,
                "execution": metric.execution,
                "global_shap_images": (
                    [metric.global_shap_images] if isinstance(metric.global_shap_images, str)
                    else (metric.global_shap_images or [])
                ),
                "global_lime_images": (
                    [metric.global_lime_images] if isinstance(metric.global_lime_images, str)
                    else (metric.global_lime_images or [])
                )
            }
            for metric in metrics
        ]

        # Return the metrics data as a JSON response
        return JsonResponse({"metrics": metrics_data}, safe=False)
    
    # Return error if scenario is not found
    except Scenario.DoesNotExist:
        return JsonResponse({"error": "Scenario not found"}, status=404)
    
    # Return error if scenario model is not found
    except ScenarioModel.DoesNotExist:
        return JsonResponse({"error": "Scenario model not found"}, status=404)
    
    # Return error for any other exceptions
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)
    
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_scenario_regression_metrics_by_uuid(request, uuid):
    """
    Retrieves all regression metrics for a given scenario UUID.

    Args:
        uuid (str): UUID of the scenario.

    Behavior:
        - Looks up the Scenario instance by UUID.
        - Retrieves the associated ScenarioModel instance.
        - Filters RegressionMetric entries by scenario model, ordered by date descending.
        - Normalizes SHAP and LIME global image fields to always be lists.

    Returns:
        - 200 OK with list of regression metrics.
        - 404 Not Found if the scenario or scenario model does not exist.
        - 500 Internal Server Error for unexpected issues.
    """

    try:
        # Fetch the scenario by UUID
        scenario = Scenario.objects.get(uuid=uuid)

        # Fetch the associated scenario model
        scenario_model = ScenarioModel.objects.get(scenario=scenario)

        # Retrieve all regression metrics for the scenario model, ordered by date
        metrics = RegressionMetric.objects.filter(scenario_model=scenario_model).order_by('-date')

        # Prepare the metrics data for the response
        metrics_data = [
            {
                "model_name": metric.model_name,
                "mse": metric.mse,
                "rmse": metric.rmse,
                "mae": metric.mae,
                "r2": metric.r2,
                "msle": metric.msle,
                "date": metric.date,
                "execution": metric.execution,
                "global_shap_images": (
                    [metric.global_shap_images] if isinstance(metric.global_shap_images, str)
                    else (metric.global_shap_images or [])
                ),
                "global_lime_images": (
                    [metric.global_lime_images] if isinstance(metric.global_lime_images, str)
                    else (metric.global_lime_images or [])
                )
            }
            for metric in metrics
        ]

        # Return the metrics data as a JSON response
        return JsonResponse({"metrics": metrics_data}, safe=False)
    
    # Return error if scenario is not found
    except Scenario.DoesNotExist:
        return JsonResponse({"error": "Scenario not found"}, status=404)
    
    # Return error if scenario model is not found
    except ScenarioModel.DoesNotExist:
        return JsonResponse({"error": "Scenario Model not found"}, status=404)
    
    # Return error for any other exceptions
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)
    
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_scenario_anomaly_metrics_by_uuid(request, uuid):
    """
    Retrieves all non-production anomaly detection metrics for a given scenario UUID.

    Args:
        uuid (str): UUID of the scenario.

    Behavior:
        - Finds the associated scenario and scenario model.
        - Filters anomaly metrics that are not from production mode, ordered by date descending.
        - Parses the anomalies field (stored as JSON string or list).
        - Ensures SHAP and LIME global images are returned as lists.

    Returns:
        - 200 OK with metrics list if found.
        - 500 Internal Server Error on unexpected failure.
    """

    try:
        # Fetch the scenario by UUID
        scenario = Scenario.objects.get(uuid=uuid)

        # Fetch the associated scenario model
        scenario_model = ScenarioModel.objects.get(scenario=scenario)

        # Retrieve all anomaly metrics for the scenario model that are not in production mode, ordered by date
        metrics = AnomalyMetric.objects.filter(scenario_model=scenario_model, production=False).order_by('-date')

        # Prepare the metrics data for the response
        metrics_data = []
        for metric in metrics:
            # Attempt to parse anomalies field, fallback to raw value if parsing fails
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
                "global_shap_images": (
                    [metric.global_shap_images] if isinstance(metric.global_shap_images, str)
                    else (metric.global_shap_images or [])
                ),
                "global_lime_images": (
                    [metric.global_lime_images] if isinstance(metric.global_lime_images, str)
                    else (metric.global_lime_images or [])
                )
            })

        # Return the metrics data as a JSON response
        return JsonResponse({"metrics": metrics_data}, safe=False)
    
    # Return error if scenario or scenario model or metrics are not found
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)
    
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_scenario_production_anomaly_metrics_by_uuid(request, uuid):
    """
    Retrieves all production anomaly detection metrics for a given scenario UUID.

    Args:
        uuid (str): UUID of the scenario.

    Behavior:
        - Finds the associated scenario and scenario model.
        - Filters anomaly metrics marked as production=True, ordered by date descending.
        - Parses anomalies field (stored as JSON or plain text).
        - Returns full explanation image paths for SHAP and LIME (global + local), and anomaly details if available.

    Returns:
        - 200 OK with metrics list.
        - 500 Internal Server Error on unexpected failure.
    """

    try:

        # Fetch the scenario by UUID
        scenario = Scenario.objects.get(uuid=uuid)

        # Fetch the associated scenario model
        scenario_model = ScenarioModel.objects.get(scenario=scenario)

        # Retrieve all anomaly metrics for the scenario model that are in production mode, ordered by date
        metrics = AnomalyMetric.objects.filter(scenario_model=scenario_model, production=True).order_by('-date')

        # Prepare the metrics data for the response
        metrics_data = []
        for metric in metrics:
            # Attempt to parse anomalies field, fallback to raw value if parsing fails
            try:
                anomalies = json.loads(metric.anomalies)
            except:
                anomalies = metric.anomalies

            if metric.production == True:
                metrics_data.append({
                    "id": metric.id,
                    "model_name": metric.model_name,
                    "feature_name": metric.feature_name,
                    "anomalies": anomalies,
                    "date": metric.date,
                    "execution": metric.execution,
                    "production": metric.production,
                    "anomaly_details": metric.anomaly_details if metric.anomaly_details else None,
                    "global_shap_images": metric.global_shap_images or [],
                    "local_shap_images": metric.local_shap_images or [],
                    "global_lime_images": metric.global_lime_images or [],
                    "local_lime_images": metric.local_lime_images or []
                })

        # Return the metrics data as a JSON response
        return JsonResponse({"metrics": metrics_data}, safe=False)
    
    # Return error if scenario or scenario model or metrics are not found
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)

@api_view(['PUT'])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser])
def put_scenario_by_uuid(request, uuid):

    """
    Updates an existing scenario by UUID. Accepts a new design and optionally new CSV or PCAP files.

    Args:
        uuid (str): UUID of the scenario to update.

    Behavior:
        - Validates the design JSON sent in the form data.
        - Updates references for newly uploaded or existing files.
        - Removes unused files and decrements their references.
        - Updates the scenario's design and associated files.

    Returns:
        - 200 OK if scenario updated successfully.
        - 400 Bad Request if design is missing or invalid, or serializer fails.
        - 404 Not Found if the scenario does not exist.
    """

    # Get the user from the request
    user = request.user

    try:
        # Fetch the scenario by UUID and user
        scenario = Scenario.objects.get(uuid=uuid, user=user)

        # Get the design JSON and file uploads from the request
        design_json = request.POST.get('design')
        csv_files = request.FILES.getlist('csv_files')
        network_files = request.FILES.getlist('network_files')
        jsonl_files = request.FILES.getlist('jsonl_files')

        # Return error if design field is missing
        if not design_json:
            return JsonResponse({'error': 'Design field is required'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            # Parse the design JSON
            design = json.loads(design_json)

        # Return error if design JSON is invalid
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid design JSON'}, status=status.HTTP_400_BAD_REQUEST)

        # Get the design from the scenario in the database
        scenario.design = design

        # Validate the design structure
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
            elif element.get("type") == "JSONL":
                jsonl_name = element.get("parameters", {}).get("jsonlFileName")
                if jsonl_name:
                    referenced_file_names.add(jsonl_name)

        # Fetch all referenced files from the database
        referenced_files = list(File.objects.filter(name__in=referenced_file_names))

        updated_files = []

        # Process the uploaded CSV files 
        for csv_file in csv_files:
            # Check if the file already exists in the database
            existing = File.objects.filter(name=csv_file.name).first()

            # If it exists, increment the reference count
            if existing:
                existing.references += 1
                existing.save()
                updated_files.append(existing)
                logger.info(f"[UPDATE SCENARIO] Existing CSV file found: {csv_file.name} (references updated to {existing.references})")

            # If it does not exist, read the content, count entries, and save it
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
                logger.info(f"[UPDATE SCENARIO] New CSV file saved: {csv_file.name} (entries: {entry_count})")

        # Process the uploaded PCAP files
        for network_file in network_files:

            # Check if the file already exists in the database
            existing = File.objects.filter(name=network_file.name).first()

            # If it exists, increment the reference count
            if existing:
                existing.references += 1
                existing.save()
                updated_files.append(existing)
                logger.info(f"[UPDATE SCENARIO] Existing PCAP file found: {network_file.name} (references updated to {existing.references})")

            # If it does not exist, read the content and save it
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
                logger.info(f"[UPDATE SCENARIO] New PCAP file saved: {network_file.name}")

        # Process the uploaded Log files
        for jsonl_file in jsonl_files:

            # Check if the file already exists in the database
            existing = File.objects.filter(name=jsonl_file.name).first()

            # If it exists, increment the reference count
            if existing:
                existing.references += 1
                existing.save()
                updated_files.append(existing)
                logger.info(f"[UPDATE SCENARIO] Existing JSONL file found: {jsonl_file.name} (references updated to {existing.references})")

            # If it does not exist, read the content and save it
            else:
                log_content = jsonl_file.read()
                new_file = File.objects.create(
                    name=jsonl_file.name,
                    file_type='jsonl',
                    entry_count=0,
                    content=ContentFile(log_content, name=jsonl_file.name),
                    references=1
                )
                updated_files.append(new_file)
                logger.info(f"[UPDATE SCENARIO] New JSONL file saved: {jsonl_file.name}")

        # Combine referenced files and updated files
        all_files_to_keep = {f.name: f for f in referenced_files + updated_files}

        # Remove files that are no longer referenced in the scenarios in the database
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

        # Serialize the updated scenario with the new design
        serializer = ScenarioSerializer(instance=scenario, data={'design': design}, partial=True)

        # If the serializer is valid, save the scenario and return success response
        if serializer.is_valid():
            serializer.save(user=user)
            return JsonResponse({'message': 'Scenario updated correctly'}, status=status.HTTP_200_OK)
        
        # If the serializer is not valid, return error response with serializer errors
        else:
            return JsonResponse(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    # Return error if the scenario does not exist or the user does not have permission to update it
    except Scenario.DoesNotExist:
        return JsonResponse({'error': 'Scenario not found'}, status=status.HTTP_404_NOT_FOUND)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_scenario_by_uuid(request, uuid):

    """
    Deletes a scenario by UUID along with:
        - Associated files (if no longer referenced).
        - Linked scenario model and classification metrics.
        - Related SHAP/LIME/model files from disk.

    Args:
        uuid (str): UUID of the scenario to delete.

    Returns:
        - 200 OK if deletion is successful.
        - 404 Not Found if the scenario does not exist or is not owned by the user.
    """

    # Get the user from the request
    user = request.user

    try:
        # Fetch the scenario by UUID and user
        scenario = Scenario.objects.get(uuid=uuid, user=user.id)

        # Delete the scenario's files. If a file's reference count reaches zero, delete it from disk.
        for file_instance in scenario.files.all():
            file_instance.references -= 1
            if file_instance.references <= 0:
                file_path = os.path.join(settings.MEDIA_ROOT, file_instance.content.name)
                if os.path.exists(file_path):
                    os.remove(file_path)
                    logger.info(f"[DELETE SCENARIO] Deleted file from disk: {file_path}")
                file_instance.delete()
                logger.info(f"[DELETE SCENARIO] File record deleted from DB: {file_instance.name}")
            else:
                file_instance.save()
                logger.info(f"[DELETE SCENARIO] Decremented reference for file: {file_instance.name}")

        # Find the scenario model associated with the scenario
        scenario_model = ScenarioModel.objects.filter(scenario=scenario).first()

        # If an scenario model exists, delete its metrics and the scenario model itself
        if scenario_model:
            ClassificationMetric.objects.filter(scenario_model=scenario_model).delete()
            RegressionMetric.objects.filter(scenario_model=scenario_model).delete()
            AnomalyMetric.objects.filter(scenario_model=scenario_model).delete()
            logger.info(f"[DELETE SCENARIO] Deleted metrics for scenario model ID: {scenario_model.id}")

            scenario_model.delete()
            logger.info(f"[DELETE SCENARIO] Deleted scenario model for scenario UUID: {scenario.uuid}")

        # Folders to clean related to the scenario
        folders_to_clean = [
            'models_storage',
            'shap_global_images',
            'shap_local_images',
            'lime_global_images',
            'lime_local_images'
        ]

        scenario_uuid = str(scenario.uuid)

        # Clean up files in the specified folders that match the scenario UUID
        for folder in folders_to_clean:
            folder_path = os.path.join(settings.MEDIA_ROOT, folder)
            if not os.path.exists(folder_path):
                continue
            for filename in os.listdir(folder_path):
                if scenario_uuid in filename:
                    file_to_delete = os.path.join(folder_path, filename)
                    logger.info(f"Deleting file: {file_to_delete}")
                    try:
                        os.remove(file_to_delete)
                    except Exception as e:
                        logger.warning(f"Can't be deleted {file_to_delete}: {str(e)}")

        # Finally, delete the scenario itself
        scenario.delete()
        logger.info(f"[DELETE SCENARIO] Scenario deleted successfully: {scenario.name} (UUID: {uuid})")

        # Return success response
        return JsonResponse({'message': 'Scenario and related data deleted successfully'}, status=status.HTTP_200_OK)

    # Return error if the scenario does not exist or the user does not have permission to delete it
    except Scenario.DoesNotExist:
        return JsonResponse({'error': 'Scenario not found or you do not have permission to delete it'}, status=status.HTTP_404_NOT_FOUND)

@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def run_scenario_by_uuid(request, uuid):

    """
    Executes a scenario by UUID for the authenticated user.

    Behavior:
        - Marks the scenario as "Running".
        - Creates or reuses the associated scenario model.
        - Parses and executes the scenario design using execute_scenario().
        - Updates the scenario's status to "Finished" or "Error" depending on execution.
        - Increments the user's executed scenario counter on success.

    Returns:
        - 200 OK if execution completes successfully.
        - 400 Bad Request if an error occurred during execution.
        - 404 Not Found if the scenario does not exist or does not belong to the user.
    """

    # Get the user from the request
    user = request.user  

    try:
        # Fetch the scenario by UUID and user
        scenario = Scenario.objects.get(uuid=uuid, user=user)

        # Set the scenario status to "Running"
        scenario.status = "Running"

        # Save the scenario to update its status
        scenario.save()

        logger.info(f"[RUN SCENARIO] Scenario status updated to 'Running'")

        # Create or get the scenario model for this scenario
        scenario_model, created = ScenarioModel.objects.get_or_create(scenario=scenario)

        if created:
            logger.info(f"[RUN SCENARIO] Created new ScenarioModel for scenario: {scenario.name}")
        else:
            logger.info(f"[RUN SCENARIO] Using existing ScenarioModel for scenario: {scenario.name}")

        # Retrieve the design from the scenario and parse it
        design = scenario.design
        if isinstance(design, str):  
            design = json.loads(design)

        # Execute the scenario using the execute_scenario function
        result = execute_scenario(scenario_model, scenario, design)

        # Return error response if the execution result indicates an error
        if result.get('error'):
            scenario.status = "Error"
            scenario.save()

            logger.warning(f"[RUN SCENARIO] Scenario execution failed: {result['error']}")
            return JsonResponse(result, status=status.HTTP_400_BAD_REQUEST)

        # If execution was successful, update the scenario status and increment user's executed scenarios
        scenario.status = 'Finished'
        scenario.save()
        user.number_executed_scenarios += 1
        user.save()
        logger.info(f"[RUN SCENARIO] Scenario execution finished successfully.")

        # Return success response
        return JsonResponse({
            'message': 'Scenario run successfully'
        }, status=status.HTTP_200_OK)

    # Return error if the scenario does not exist or the user does not have permission to run it
    except Scenario.DoesNotExist:
        return JsonResponse({'error': 'Scenario not found or without permits to run it'}, status=status.HTTP_404_NOT_FOUND)

@shared_task
def execute_scenario(scenario_model, scenario, design):
    try:

        logger.info(f"[EXECUTE SCENARIO] Starting execution for scenario: {scenario.name} (UUID: {scenario.uuid})")

        # Increment the execution count for the scenario model
        scenario_model.execution += 1
        scenario_model.save()

        # Load the configuration for the scenario
        config = load_config()
        element_types = {}

        # Get the execution mode from environment variable
        execution_mode_env = os.getenv("EXECUTION_MODE", "").strip().lower()

        logger.info(f"[EXECUTE SCENARIO] Execution mode environment: {execution_mode_env}")

        # Validate the design structure
        validate_design(config, design)

        logger.info(f"[EXECUTE SCENARIO] Design validated successfully for scenario: {scenario.name} (UUID: {scenario.uuid})")
        
        # Build the element types from the configuration
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

        classification_types = [el["type"] for el in config["sections"]["dataModel"]["classification"]]
        regression_types = [el["type"] for el in config["sections"]["dataModel"]["regression"]]
        anomaly_types = [el["type"] for el in config["sections"]["dataModel"]["anomalyDetection"]]

        # Get the elements and connections from the design
        elements = {e["id"]: e for e in design["elements"]}
        connections = design["connections"]
        
        # Sort the elements topologically based on their connections
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

        logger.info(f"[EXECUTE SCENARIO] Sorted elements in topological order: {sorted_order}")
        
        data_storage = {} 
        models = {}

        # Process each element in the sorted order
        for element_id in sorted_order:
            element = elements[element_id]
            el_type = element["type"]
            logger.info(f"[EXECUTE SCENARIO] Processing element: {el_type} (ID: {element_id})")

            # Get the parameters for the element, defaulting to an empty dict if not present
            params = copy.deepcopy(element.get("parameters", {}))
            
            input_data = None
            for conn in connections:
                if conn["endId"] == element_id:
                    predecessor_id = conn["startId"]
                    input_data = data_storage.get(predecessor_id)
                    break 

            # Case element type is CSV
            if el_type == "CSV":
                logger.info("[EXECUTE SCENARIO] Processing CSV element")

                # Get the CSV file name from parameters
                csv_file_name = params.get("csvFileName")

                # Get the file from the database
                try:
                    file = File.objects.get(name=csv_file_name)
                    df = pd.read_csv(file.content)
                except Exception as e:
                    logger.error(f"[EXECUTE SCENARIO] Error loading CSV file: {str(e)}")
                    return {"error": f"Error loading CSV: {str(e)}"}
                
                # Get the columns to keep from parameters
                columns = params.get("columns", [])
                selected_columns = []
                
                # If columns is a list, filter by selected columns
                if isinstance(columns, list):
                    selected_columns = [col["name"] for col in columns if col.get("selected", True)]
                elif isinstance(columns, dict):
                    selected_columns = [col for col, keep in columns.items() if keep]
                
                logger.info(f"[EXECUTE SCENARIO] Selected columns: {selected_columns}")
                
                try:
                    # Generate a dataframe with the selected columns
                    df = df[selected_columns]
                except KeyError as e:
                    logger.error(f"[EXECUTE SCENARIO] Column not found in CSV: {str(e)}")
                    return {"error": f"Column not found in the CSV: {str(e)}"}
                except Exception as e:
                    logger.error(f"[EXECUTE SCENARIO] Error processing columns: {str(e)}")
                    return {"error": f"Error processing columns: {str(e)}"}
                
                # Store the DataFrame in the data storage
                data_storage[element_id] = df

            # Case element type is Network
            elif el_type == "Network":
                logger.info("[EXECUTE SCENARIO] Processing Network element")

                # Get the network file name from parameters
                network_file_name = params.get("networkFileName")

                logger.info(f"[EXECUTE SCENARIO] Network file name: {network_file_name}")

                # Get the analysis mode from parameters, defaulting to "flow"
                analysis_mode = params.get("analysisMode", "flow")

                logger.info(f"[EXECUTE SCENARIO] Analysis mode selected: {analysis_mode}")
                logger.info(f"[EXECUTE SCENARIO] Network file name: {network_file_name}")

                # Check if the file exists in the database
                try:
                    file = File.objects.get(name=network_file_name)
                    with open(file.content.path, 'rb') as f:
                        # Extract features from the PCAP file based on the analysis mode
                        if analysis_mode == "flow":
                            logger.info("[EXECUTE SCENARIO] Extracting features by flow")
                            df = extract_features_by_flow_from_pcap(f)
                        else:
                            logger.info("[EXECUTE SCENARIO] Extracting features by packet")
                            df = extract_features_by_packet_from_pcap(f)
                    logger.info(f"[EXECUTE SCENARIO] Extracted DataFrame: {df.head()}")
                
                # Handle errors when loading the PCAP file
                except Exception as e:
                    return {"error": f"Error loading PCAP: {str(e)}"}

                # Check if the DataFrame is empty
                if df.empty:
                    return {"error": "The PCAP file does not contain usable data"}

                # Store the DataFrame in the data storage
                data_storage[element_id] = df



            elif el_type == "JSONL":
                logger.info("[EXECUTE SCENARIO] Processing JSONL element")

                jsonl_file_name = params.get("jsonlFileName")
                logger.info(f"[EXECUTE SCENARIO] JSONL file name: {jsonl_file_name}")

                try:

                    file = File.objects.get(name=jsonl_file_name)
                    file_path = file.content.path

                    # Si el archivo contiene SOLO JSON por línea, esto basta:
                    # df = pd.read_json(file_path, lines=True)

                    # Versión robusta por si hubiera líneas no-JSON (se filtran):
                    with open(file_path, "r", encoding="utf-8", errors="replace") as fh:
                        only_json = "".join(line for line in fh if line.lstrip().startswith("{"))
                    df = pd.read_json(io.StringIO(only_json), lines=True)

                    # (Opcional) asegurar orden de columnas si lo quieres fijo:
                    expected_cols = [
                        "window_start_ns","window_end_ns","read","write","openat","close","fstat",
                        "mmap","mprotect","munmap","brk","rt_sigaction","rt_sigprocmask","ioctl",
                        "poll","select","futex","nanosleep","sched_yield","total_syscalls"
                    ]
                    df = df.reindex(columns=expected_cols)

                    logger.info(df)

                    # Ahora 'df' es el DataFrame que querías
                    logger.info(f"[EXECUTE SCENARIO] DataFrame shape: {df.shape}")

                # Handle errors when loading the JSONL file
                except Exception as e:
                    return {"error": f"Error loading JSONL: {str(e)}"}

                # Check if the DataFrame is empty
                if df.empty:
                    return {"error": "The JSONL file does not contain usable data"}

                # Store the DataFrame in the data storage
                data_storage[element_id] = df







            # Case element type is ClassificationModel or RegressionModel
            elif el_type in ["ClassificationMonitor", "RegressionMonitor"]:
                logger.info("[EXECUTE SCENARIO] Processing Classification/Regression Monitor element")

                # Get the model that has been trained
                for conn in connections:
                    if conn["endId"] == element_id:
                        model_id = conn["startId"]
                        model_element = elements.get(model_id)

                        # Check if the model element exists
                        if not model_element:
                            raise ValueError(f"Modelo {model_id} no encontrado para el monitor")

                        # Check the model type and determine the monitor type
                        model_type = element_types.get(model_element["type"], {}).get("model_type")
                        monitor_type = "classification" if el_type == "ClassificationMonitor" else "regression"
                        logger.info(f"[EXECUTE SCENARIO] Model type: {model_type}, Monitor type: {monitor_type}")

                        # Check if the model type matches the monitor type
                        if model_type != monitor_type:
                            raise ValueError(f"Error de tipo: {el_type} conectado a modelo {model_type}")

                        model_data = models.get(model_id)
                        logger.info(f"[EXECUTE SCENARIO] Model data: {model_data}")

                        if model_data:
                            # Calculate metrics based on the model type
                            if el_type == "ClassificationMonitor":
                                logger.info("[EXECUTE SCENARIO] Calculating classification metrics")
                                metrics_config = params.get("metrics", {})
                                metrics = calculate_classification_metrics(model_data["y_test"], model_data["y_pred"], metrics_config)
                                save_classification_metrics(scenario_model, model_element["type"], metrics, scenario_model.execution)
                                logger.info("[EXECUTE SCENARIO] Classification metrics saved for model")
                            else:
                                logger.info("[EXECUTE SCENARIO] Calculating regression metrics")
                                metrics_config = params.get("metrics", {})
                                metrics = calculate_regression_metrics(model_data["y_test"], model_data["y_pred"], metrics_config)
                                save_regression_metrics(scenario_model, model_element["type"], metrics, scenario_model.execution)
                                logger.info("[EXECUTE SCENARIO] Regression metrics saved for model")

            # Case element type is DataSplitter
            elif el_type == "DataSplitter":
                logger.info("[EXECUTE SCENARIO] Processing DataSplitter element")

                # Get the input data from the previous element
                if input_data is None:
                    return {"error": "DataSplitter requires input data"}

                try:
                    # Get the parameters for the DataSplitter
                    splitter_params = extract_parameters(element_types[el_type]["properties"], params)
                    logger.info(f"[EXECUTE SCENARIO] DataSplitter parameters: {splitter_params}", splitter_params)

                    # Check if train_size and test_size are provided
                    train_size = splitter_params.get("train_size", 80) / 100
                    test_size = splitter_params.get("test_size", 20) / 100
            
                    logger.info(f"[EXECUTE SCENARIO] Train and test sizes: {train_size}, {test_size}")

                    # Validate the sizes
                    if round(train_size + test_size, 2) > 1.0:
                        return {"error": "The sum of train_size and test_size cannot be greater than 100%"}
                    X = input_data.iloc[:, :-1]
                    y = input_data.iloc[:, -1]

                    # Split the data into training and testing sets with the specified sizes
                    X_train, X_test, y_train, y_test = train_test_split(
                        X, y,
                        train_size=train_size,
                        test_size=test_size
                    )
                    

                    # Store the split data in the data storage
                    data_storage[element_id] = {
                        "train": (X_train, y_train),
                        "test": (X_test, y_test)
                    }

                    logger.info(f"[EXECUTE SCENARIO] Current data storage: {data_storage}")

                # Return error if there is an issue with the DataSplitter
                except Exception as e:
                    return {"error": f"Error in DataSplitter: {str(e)}"}
                
            # Case element type is CodeProcessing or CodeSplitter
            elif el_type in ["CodeProcessing", "CodeSplitter"]:
                logger.info("[EXECUTE SCENARIO] Processing CustomCode element")

                # Get the code from the parameters
                user_code = params.get("code", "")

                # Check if the code is provided and input data is available
                if input_data is None:
                    return {"error": "CustomCode requires input data"}
                if not user_code.strip():
                    return {"error": "No code was provided in the CustomCode element"}

                exec_context = {
                    "__builtins__": __builtins__,
                    "pd": pd,
                    "np": __import__('numpy'),
                }

                # Require the function name based on the element type
                required_function_name = "processing" if el_type == "CodeProcessing" else "splitter"

                try:
                    # Execute the user code in a controlled context
                    exec(user_code, exec_context)
                    user_functions = {k: v for k, v in exec_context.items() if callable(v)}
                    if len(user_functions) != 1:
                        return {"error": "You must define exactly one function in the code"}

                    user_function = list(user_functions.values())[0]

                    # Check if the function name matches the required one
                    if required_function_name != user_function.__name__:
                        return {"error": f"The function must be named '{required_function_name}'"}
                    
                    output_data = user_function(input_data)

                    # Store the output data based on its type
                    if isinstance(output_data, pd.DataFrame):
                        logger.info("CustomCode detected as processing function")
                        data_storage[element_id] = output_data
                        logger.info(f"[EXECUTE SCENARIO] Current data storage: {data_storage}")

                    elif isinstance(output_data, dict) and "train" in output_data and "test" in output_data:
                        logger.info("CustomCode detected as splitter function")
                        data_storage[element_id] = output_data
                        logger.info(f"[EXECUTE SCENARIO] Current data storage: {data_storage}")

                    else:
                        return {"error": "The function must return a DataFrame or a dict with 'train' and 'test' keys"}

                except Exception as e:
                    return {"error": f"Error executing custom function: {str(e)}"}

            # Case element type is in Processing, Model, or Explainability
            else:
                element_def = element_types.get(el_type)

                logger.info(f"[EXECUTE SCENARIO] Element definition: {element_def}")
                if not element_def:
                    return {"error": f"Unknown element type: {el_type}"}
                
                # Check if the element has a category
                category = element_def.get("category", "")

                logger.info(f"[EXECUTE SCENARIO] Element category: {category}")

                # Import the class based on the category
                if category not in ["model", "explainability"]:
                    logger.info(f"[EXECUTE SCENARIO] Importing class: {element_def['class']}")
                    cls = import_class(element_def["class"])
                
                # Check if category is preprocessing
                if category == "preprocessing":

                    # Get the element to transform
                    applies_to = element_def.get("appliesTo", "all")

                    # Get the transformer
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

                        # Check if the input data has target or label columns
                        if 'target' in input_data.columns or 'label' in input_data.columns:
                            target_column = input_data.pop('target') if 'target' in input_data.columns else None
                            label_column = input_data.pop('label') if 'label' in input_data.columns else None

                            # Store the original targets
                            original_targets = {}
                            if target_column is not None:
                                original_targets['target'] = target_column
                            if label_column is not None:
                                original_targets['label'] = label_column

                            # Transform the input data based on the applies_to parameter
                            if applies_to == "numeric":
                                excluded_numeric = ['src_port', 'dst_port']
                                numeric_cols = [col for col in input_data.select_dtypes(include=['number']).columns if col not in excluded_numeric]
                                logger.info(f"[EXECUTE SCENARIO] [TRAINING] Columns used for fitting in {el_type}: {numeric_cols}")
                                
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
                        
                        # If no target or label columns, transform the entire input data
                        else:
                            if applies_to == "numeric":
                                excluded_numeric = ['src_port', 'dst_port']
                                numeric_cols = [col for col in input_data.select_dtypes(include=['number']).columns if col not in excluded_numeric]
                                logger.info(f"[EXECUTE SCENARIO] [TRAINING] Columns used for fitting in {el_type}: {numeric_cols}")
                                
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
                        logger.info(f"Saved: {step_path}")

                        # Store the transformed data in the data storage
                        data_storage[element_id] = output_data
                        logger.info(f"[EXECUTE SCENARIO] Initial input data: {input_data.head()}")
                        logger.info(f"[EXECUTE SCENARIO] Transformed output data: {output_data.head()}")

                        logger.info(f"[EXECUTE SCENARIO] Current data storage: {data_storage}")

                # Case category is model and input data is available
                elif category == "model" and input_data is not None:
                    logger.info(f"[EXECUTE SCENARIO] Training model")

                    # Get the execution mode from parameters
                    execution_mode_model = params.pop("execution_mode", None)

                    logger.info(f"[EXECUTE SCENARIO] Model execution mode: {execution_mode_model}")
                    logger.info(f"[EXECUTE SCENARIO] Environment execution mode: {execution_mode_env}")

                    if execution_mode_model and execution_mode_env and execution_mode_model.strip().lower() != execution_mode_env:
                        error_msg = f"Incompatible execution mode: model='{execution_mode_model}', env='{execution_mode_env}'"
                        logger.error(f"[EXECUTE SCENARIO] Error: {error_msg}")
                        return {"error": error_msg}
                    
                    # Import the class based on the execution mode
                    if execution_mode_model.strip().lower() == "cpu":
                        cls = import_class(element_def["class_cpu"])
                    else:
                        cls = import_class(element_def["class_gpu"])
                    
                    # Extract the parameters for the model
                    if el_type not in ["CNNClassifier", "RNNClassifier", "MLPClassifier"]:
                        model = cls(**extract_parameters(element_def["properties"], params))
                        logger.error(f"[EXECUTE SCENARIO] Model params: {model.get_params()}")

                    # Case the model is a classification or a regression model
                    if element_def.get("model_type") in ["classification", "regression"]:
                        logger.info(f"[EXECUTE SCENARIO] Training a {element_def.get('model_type')} model")

                        X_train_all, y_train_all = [], []
                        X_test_all, y_test_all = [], []
                        has_train = has_test = False

                        # Iterate through connections to find the data for training and testing
                        for conn in connections:
                            if conn["endId"] == element_id:
                                source_id = conn["startId"]
                                output_type = conn.get("startOutput")

                                split_data = data_storage.get(source_id)
                                if not isinstance(split_data, dict) or "train" not in split_data or "test" not in split_data:
                                    return {"error": f"The connected node ({source_id}) does not produce an output with train and test data"}

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

                        # If the previous element does not provide both train and test outputs, return an error
                        if not has_train or not has_test:
                            return {"error": f"Model {element_id} requires at least one connection with 'train' and 'test' outputs"}

                        # Concatenate all training and testing data
                        X_train_concat = pd.concat(X_train_all)
                        y_train_concat = pd.concat(y_train_all)
                        X_test_concat = pd.concat(X_test_all)
                        y_test_concat = pd.concat(y_test_all)

                        # Case the model is a neural network
                        if el_type in ["CNNClassifier", "RNNClassifier", "MLPClassifier"]:
                            from tensorflow.keras.utils import to_categorical
                            logger.info(f"[EXECUTE SCENARIO] Training neural network model: {el_type}")

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

                            # Build the neural network model
                            model = build_neural_network(input_shape, el_type, params)

                            # Train the neural network model
                            model.fit(
                                X_train_reshaped, y_train_encoded,
                                epochs=params.get("epochs", 50),
                                batch_size=params.get("batch_size", 32),
                                verbose=0
                            )

                            # Predict using the trained model
                            y_pred_proba = model.predict(X_test_reshaped)

                            y_pred = np.argmax(y_pred_proba, axis=1)
                            y_test_labels = np.argmax(y_test_encoded, axis=1)

                            # Store the model and results
                            models[element_id] = {
                                "type": el_type,
                                "y_test": y_test_labels,
                                "y_pred": y_pred,
                                "model_object": model,
                                "X_train": X_train_reshaped,
                            }

                            # Store the reshaped training data
                            data_storage[element_id] = X_train_reshaped

                        # Case the model is a classic model
                        else:
                            logger.info(f"[EXECUTE SCENARIO] Training classic model: {el_type}")
                            logger.info(f"[EXECUTE SCENARIO] Concatenated training data:\n{X_train_concat}")
                            logger.info(f"[EXECUTE SCENARIO] Concatenated testing data:\n{X_test_concat}")


                            # Fit the model with the concatenated training data
                            model.fit(X_train_concat, y_train_concat)

                            # Predict using the trained model
                            y_pred = model.predict(X_test_concat)

                            # Store the model and results
                            models[element_id] = {
                                "type": el_type,
                                "y_test": y_test_concat,
                                "y_pred": y_pred,
                                "model_object": model,
                                "X_train": X_train_concat,
                            }

                            # Store the concatenated training data
                            data_storage[element_id] = X_train_concat

                            logger.info(f"[EXECUTE SCENARIO] Current data storage: {data_storage}")

                    # Case the model is an anomaly detection model
                    elif element_def.get("model_type") == "anomalyDetection":
                        logger.info(f"[EXECUTE SCENARIO] Anomaly detection model")

                        if not isinstance(input_data, pd.DataFrame):
                            return {"error": "Input data for anomaly detection must be a DataFrame"}

                        input_copy = input_data.copy()

                        # Convert IP addresses to integers if applicable
                        for ip_col in ['src', 'dst']:
                            if ip_col in input_copy.columns:
                                input_copy[ip_col] = input_copy[ip_col].apply(ip_to_int)
                        
                        # Convert protocol strings to numerical codes
                        if 'protocol' in input_copy.columns:
                            def protocol_to_code(p):
                                if isinstance(p, str):
                                    p_clean = p.strip().upper()
                                    code = PROTOCOL_REVERSE_MAP.get(p_clean, -1)
                                    if code == -1:
                                        logger.warning(f"[EXECUTE SCENARIO] Unknown protocol: {p}")
                                    return code
                                return p

                            input_copy['protocol'] = input_copy['protocol'].apply(protocol_to_code)

                        #input_copy = input_copy.drop(columns=[col for col in input_copy.columns if input_copy[col].dtype == 'object'])

                        # Return error if the input data is empty
                        if input_copy.empty:
                            return {"error": "There are no numerical columns after preprocessing"}
                        
                        logger.info(f"[EXECUTE SCENARIO] Preprocessed data for anomaly detection:\n{input_copy}")

                        # Fit the model with the input data
                        model.fit(input_copy)
                        logger.info(f"[EXECUTE SCENARIO] Model feature names: {model.feature_names_in_}")

                        # Store the training model
                        step_id = f"{element_id}_{scenario.uuid}"
                        model_dir = os.path.join(settings.MEDIA_ROOT, 'models_storage')
                        os.makedirs(model_dir, exist_ok=True)
                        step_path = os.path.join(model_dir, f"{step_id}.pkl")

                        joblib.dump({
                            "model": model,
                            "X_train": input_copy
                        }, step_path)

                        logger.info(f"[EXECUTE SCENARIO] Model saved at: {step_path}")

                        # Predict anomalies
                        predictions = model.predict(input_copy)
                        y_pred = [1 if x == -1 else 0 for x in predictions]
                        logger.info(f"[EXECUTE SCENARIO] Predictions: {y_pred}")

                        # Save anomaly metrics
                        for column in input_copy.columns:
                            feature_values = input_copy[column].values
                            anomalies = [i for i, (val, pred) in enumerate(zip(feature_values, y_pred)) if pred == 1]

                            save_anomaly_metrics(scenario_model, el_type, column, feature_values, anomalies, 
                                                 scenario_model.execution, production=False, anomaly_details=None,
                                                 global_shap_images=[], local_shap_images=[], global_lime_images=[], 
                                                 local_lime_images=[])

                        # Store the model and results
                        models[element_id] = {
                            "type": el_type,
                            "y_pred": y_pred,
                            "model_object": model,
                            "X_train": input_copy
                        }

                        # Store the input data for future use
                        data_storage[element_id] = input_copy

                        logger.info(f"[EXECUTE SCENARIO] Current data storage: {data_storage}")

                        logger.info(f"[EXECUTE SCENARIO] Anomaly detection model trained and saved")

                # Case category is explainability
                elif category == "explainability":
                    logger.info(f"[EXECUTE SCENARIO] Processing explainability node: {el_type}")

                    # Check if the input data is available
                    if input_data is None:
                        return {"error": f"No input data found for node {el_type}"}
                    
                    logger.info(f"[EXECUTE SCENARIO] Input data for explainability: {input_data}")

                    # Get the parameters for the explainer
                    explainer_type = params.get("explainer_type", "").strip()
                    explainer_module_path = element_def.get("class")

                    # Get the selected classes to be explained
                    selected_classes_raw = params.get("selectedClasses", [])

                    selected_classes = [
                        str(c["name"]).replace(" ", "_").replace("/", "_")
                        for c in selected_classes_raw
                        if c.get("selected")
                    ]

                    # Validate the configuration data
                    if not explainer_module_path or not explainer_type:
                        return {"error": f"Missing configuration data in {el_type}"}

                    # Check if the node connected is a model node
                    model_id = next((c["startId"] for c in connections if c["endId"] == element_id), None)
                    if not model_id or model_id not in models:
                        return {"error": f"No valid connected model found for {el_type}"}

                    model_info = models[model_id]
                    model_object = model_info.get("model_object")
                    if not model_object:
                        return {"error": f"Model object not found in {model_id}"}

                    try:
                        # Import the explainer class dynamically
                        explainer_class = find_explainer_class(explainer_module_path, explainer_type)

                        # Case the explainer is SHAP
                        if el_type == "SHAP":
                            model_type = model_info.get("type")

                            # Check input data for SHAP
                            if el_type in classification_types + regression_types:
                                input_data = model_info.get("X_train")
                                if input_data is None:
                                    return {"error": f"No training data found for model {model_id} to apply SHAP"}

                            elif input_data is None:
                                return {"error": f"No input data found for node {el_type}"}

                            logger.info(f"[EXECUTE SCENARIO] Calculating SHAP values with data: {input_data}")

                            # Case explainer type is KernelExplainer, LinearExplainer, DeepExplainer, or TreeExplainer
                            if explainer_type == "KernelExplainer":
                                def model_score(X):
                                    if isinstance(X, np.ndarray):
                                        X = pd.DataFrame(X, columns=input_data.columns)

                                    if hasattr(model_object, "decision_function"):
                                        return model_object.decision_function(X)
                                    elif hasattr(model_object, "predict_proba"):
                                        return model_object.predict_proba(X)
                                    else:
                                        return model_object.predict(X)

                                background = shap.kmeans(input_data, 20)
                                explainer = explainer_class(model_score, background)

                            elif explainer_type in ["LinearExplainer", "DeepExplainer"]:
                                explainer = explainer_class(model_object, input_data)

                            elif explainer_type == "TreeExplainer":
                                explainer = explainer_class(model_object, input_data, feature_perturbation="interventional")

                            else:
                                explainer = explainer_class(model_object)

                            try:
                                logger.info(f"[EXECUTE SCENARIO] Applying SHAP to element: {model_type}")
                                metrics = []

                                # Case model connected is anomaly detection model
                                if model_type in anomaly_types:
                                    logger.info(f"[EXECUTE SCENARIO] Anomaly detection model detected, applying SHAP")
                                    y_pred = model_info.get("y_pred")

                                    if y_pred is None:
                                        return {"error": "Missing y_pred to apply SHAP in anomaly detection model"}

                                    y_pred_arr = np.array(y_pred)
                                    input_df = input_data.copy()

                                    # Get normal and anomaly data based on predictions
                                    normal_data = input_df[y_pred_arr == 0]
                                    anomaly_data = input_df[y_pred_arr == 1]

                                    shap_image_paths = []

                                    # Generate global shap values for normal and anomaly data depending on selected classes
                                    if not normal_data.empty and "normal" in selected_classes:
                                        if explainer_type == "TreeExplainer":
                                            shap_normal = explainer(normal_data, check_additivity=False)
                                        else:
                                            shap_normal = explainer(normal_data)
                                        path_normal = save_shap_bar_global(shap_normal, scenario.uuid, model_type, label="normal")
                                        shap_image_paths.append(path_normal)

                                    if not anomaly_data.empty and "anomaly" in selected_classes:
                                        if explainer_type == "TreeExplainer":
                                            shap_anomaly = explainer(anomaly_data, check_additivity=False)
                                        else:
                                            shap_anomaly = explainer(anomaly_data)
                                        path_anomaly = save_shap_bar_global(shap_anomaly, scenario.uuid, model_type, label="anomaly")
                                        shap_image_paths.append(path_anomaly)

                                    # Save the anomaly metrics
                                    if shap_image_paths:
                                        metrics = AnomalyMetric.objects.filter(
                                            scenario_model=scenario_model,
                                            execution=scenario_model.execution,
                                        )

                                # Case model connected is classification or regression model
                                else:
                                    shap_values = explainer(input_data)
                                    class_names = getattr(model_object, "classes_", None)

                                    logger.info(f"[EXECUTE SCENARIO] Model classes: {class_names}")
                                    logger.info(f"[EXECUTE SCENARIO] Selected classes for SHAP: {selected_classes}")

                                    # Generate global SHAP values for the selected classes
                                    shap_image_paths = save_shap_bar_global(
                                        shap_values, scenario.uuid, model_type, class_names, selected_classes=selected_classes
                                    )

                                    if shap_image_paths:
                                        logger.info(f"[EXECUTE SCENARIO] Saving global SHAP images: {shap_image_paths}")
                                                    
                                        # Case model type is classification 
                                        if model_type in classification_types:
                                            logger.info("[EXECUTE SCENARIO] Classification model detected, retrieving metrics")

                                            # Get or create the classification metric
                                            metric, created = ClassificationMetric.objects.get_or_create(
                                                scenario_model=scenario_model,
                                                execution=scenario_model.execution,
                                                model_name=model_type,
                                                defaults={"global_shap_images": shap_image_paths}
                                            )

                                            # If the metric already exists, update the global SHAP images
                                            if not created:
                                                metric.global_shap_images = shap_image_paths
                                                metric.save()

                                        # Case model type is regression
                                        elif model_type in regression_types:
                                            logger.info("[EXECUTE SCENARIO] Regression model detected, retrieving metrics")

                                            # Get or create the regression metric
                                            metric, created = RegressionMetric.objects.get_or_create(
                                                scenario_model=scenario_model,
                                                execution=scenario_model.execution,
                                                model_name=model_type,
                                                defaults={"global_shap_images": shap_image_paths}
                                            )

                                            # If the metric already exists, update the global SHAP images
                                            if not created:
                                                metric.global_shap_images = shap_image_paths
                                                metric.save()

                                logger.info(f"[EXECUTE SCENARIO] Saving global SHAP images: {shap_image_paths}")
                                logger.info(f"[EXECUTE SCENARIO] Retrieved metrics: {metrics}")

                                for metric in metrics:
                                    metric.global_shap_images = shap_image_paths
                                    metric.save()

                            except Exception as e:
                                return {"error": f"Error generating SHAP values: {str(e)}"}

                        # Case the explainer is LIME
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

                            # Save the LIME bar chart
                            lime_image_path = save_lime_bar_global(mean_weights, scenario.uuid)

                            metrics = AnomalyMetric.objects.filter(
                                scenario_model=scenario_model,
                                execution=scenario_model.execution,
                            )

                            for metric in metrics:
                                metric.global_lime_image = lime_image_path
                                metric.save()

                        else:
                            return {"error": f"Explainability node not yet supported: {el_type}"}

                    except Exception as e:
                        return {"error": f"Failed to apply explainer '{explainer_type}' on '{el_type}': {str(e)}"}

        return {"message": "Execution successful"}

    except Exception as e:
        logger.error(f"Error en execute_scenario: {str(e)}")
        return {"error": str(e)}

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def play_scenario_production_by_uuid(request, uuid):
    """
    Starts real-time packet capture and anomaly detection in production mode
    for a given scenario UUID, using either flow or packet-level analysis.

    Behavior:
        - Loads user-specific system configuration (SSH user, interface, tshark path).
        - Loads scenario and pipeline design.
        - Detects analysis mode from the design (flow or packet).
        - Builds pipelines from the design.
        - Launches a background thread that:
            - Connects via SSH to run tshark in live mode.
            - Streams packets to a handler function depending on analysis mode.
            - Performs prediction and anomaly detection in real time.

    Returns:
        - 200 OK when thread starts successfully.
        - 400 if no pipeline is found.
        - 404 if user config or scenario does not exist.
        - 500 for any other failure.
    """

    # Get the user from the request
    user = request.user

    try:
        # 1) Load scenario + design + global config
        scenario = Scenario.objects.get(uuid=uuid, user=user)
        config = load_config()
        design = json.loads(scenario.design) if isinstance(scenario.design, str) else scenario.design

        # 2) Detect source type from design: Network vs JSONL
        source_type = None
        for element in design.get("elements", []):
            etype = element.get("type")
            if etype == "Network":
                source_type = "Network"
                break
            if etype == "JSONL":
                source_type = "JSONL"
                break

        if not source_type:
            logger.warning(f"[PRODUCTION EXECUTION] Source element (Network/JSONL) not found in design (UUID: {uuid})")
            return JsonResponse({'error': 'Source element (Network/JSONL) not found in the design.'}, status=400)

        # 3) Load user-specific system configuration
        try:
            user_config = SystemConfiguration.objects.get(user=user)
        except SystemConfiguration.DoesNotExist:
            logger.info(f"[PRODUCTION EXECUTION] Scenario found: {scenario.name} (UUID: {uuid})")
            return JsonResponse({'error': 'User system config not found'}, status=404)

        host_username = user_config.host_username or 'default_user'
        interface = user_config.interface or 'eth0'

        # 4) Detect analysis mode from design
        if source_type == "Network":
            analysis_mode = "flow"
            for element in design.get("elements", []):
                if element.get("type") == "Network":
                    analysis_mode = (
                        element.get("parameters", {})
                               .get("analysisMode", "flow")
                               .strip()
                               .lower()
                    )
                    break
            logger.info(f"[PRODUCTION EXECUTION] Analysis mode detected: {analysis_mode}")
        else:
            # For JSONL source, we map to "syscalls" in this branch
            analysis_mode = "syscalls"
            logger.info(f"[PRODUCTION EXECUTION] Analysis mode detected: {analysis_mode}")

        # 5) Build pipelines from design (returns List[PipelineDef])
        scenario_model = ScenarioModel.objects.get(scenario=scenario)
        execution = scenario_model.execution
        base_path = os.path.join(settings.MEDIA_ROOT, 'models_storage')
        pipelines = build_pipelines_from_design(design, scenario.uuid, config, base_path)

        if not pipelines:
            logger.warning(f"[PRODUCTION EXECUTION] No pipelines found for scenario UUID: {uuid}")
            return JsonResponse({'error': 'No pipelines found for this scenario.'}, status=400)

        # 6) Build ExplainabilityConfig from design + config (simplified)
        expl_cfg = None
        try:
            elements = design.get("elements", [])

            # Build a map from explainability "type" ("SHAP"/"LIME") to its config entry
            expl_cfg_by_type = {}
            for expl_def in config["sections"]["dataModel"]["explainability"]:
                expl_type = expl_def.get("type")  # "SHAP" or "LIME"
                if expl_type:
                    expl_cfg_by_type[expl_type.upper()] = expl_def

            expl_kind = None        # "shap" | "lime"
            expl_module = ""
            expl_class = ""

            # We only need to know IF there is any explainability node in the design
            for el in elements:
                el_type = el.get("type")
                if el_type not in ["SHAP", "LIME"]:
                    continue

                params = el.get("parameters", {})
                expl_type_from_design = params.get("explainer_type", "").strip()
                if not expl_type_from_design:
                    continue

                cfg_entry = expl_cfg_by_type.get(el_type)
                if not cfg_entry:
                    continue

                module_path = cfg_entry.get("class")  # e.g. "shap" or "lime.lime_tabular"

                if el_type == "SHAP":
                    expl_kind = "shap"
                elif el_type == "LIME":
                    expl_kind = "lime"

                expl_module = module_path
                expl_class = expl_type_from_design
                break  # first explainability node is enough

            if expl_kind and expl_module and expl_class:
                expl_cfg = ExplainabilityConfig(
                    kind=expl_kind,              # "shap" | "lime"
                    module=expl_module,          # e.g. "shap" or "lime.lime_tabular"
                    explainer_class=expl_class,  # e.g. "KernelExplainer", "LimeTabularExplainer"
                    explainer_kwargs={},         # add extra kwargs if needed
                )

        except Exception:
            logger.exception("[PRODUCTION EXECUTION] Error building ExplainabilityConfig from design")
            expl_cfg = None

        # 7) Build SSH + capture configuration depending on source type / mode
        if source_type == "Network":
            tshark_path = user_config.tshark_path or '/usr/bin/tshark'
            ssh = SSHConfig(
                username=host_username,
                host="host.docker.internal",
                tshark_path=tshark_path,
                interface=interface,
                sudo=True,
            )
            cap = CaptureConfig(
                mode=analysis_mode,  # "flow" or "packet"
                run_env="docker",
                # bpftrace_script is kept for compatibility, but not used for plain network capture
                bpftrace_script="/home/anomalydetector/defender_software/syscalls_event.bt",
            )
        else:
            # Syscalls mode with bpftrace
            bpftrace_path = '/usr/bin/bpftrace'
            ssh = SSHConfig(
                username=host_username,
                host="host.docker.internal",
                bpftrace_path=bpftrace_path,
                interface=interface,
                sudo=True,
            )
            cap = CaptureConfig(
                mode=analysis_mode,  # "syscalls"
                run_env="docker",
            )

        # 8) Application-level callbacks (they know about Scenario, DB, etc.)

        def on_anomaly(evt):
            logger.info("[ANOMALY EVENT RAW] %s", evt)

            # clean_for_json may not always be available (e.g. in tests)
            try:
                from .utils import clean_for_json
            except Exception:
                def clean_for_json(x): return x

            try:
                # Unwrap kwargs if event comes as {'kwargs': {...}}
                payload = evt.get('kwargs', evt) if isinstance(evt, dict) else evt

                # Helper to retrieve values from dict or object attributes
                def getv(obj, *names, default=None):
                    for name in names:
                        if isinstance(obj, dict):
                            if name in obj:
                                return obj[name]
                        else:
                            if hasattr(obj, name):
                                return getattr(obj, name)
                    return default

                model_name         = getv(payload, 'model_name')
                feature_name       = getv(payload, 'feature_name')
                feature_values     = getv(payload, 'feature_values', 'features')
                anomaly_desc       = getv(payload, 'anomaly_description', 'anomalies')
                anomaly_details    = getv(payload, 'anomaly_details', 'details')
                global_shap_images = getv(payload, 'global_shap_images', default=[]) or []
                local_shap_images  = getv(payload, 'local_shap_images',  default=[]) or []
                global_lime_images = getv(payload, 'global_lime_images', default=[]) or []
                local_lime_images  = getv(payload, 'local_lime_images',  default=[]) or []

                # Persist anomaly metrics using your existing models
                save_anomaly_metrics(
                    scenario_model=scenario_model,
                    model_name=model_name,
                    feature_name=feature_name,
                    feature_values=clean_for_json(feature_values),
                    anomalies=anomaly_desc,
                    execution=execution,
                    production=True,
                    anomaly_details=anomaly_details,
                    global_shap_images=global_shap_images,
                    local_shap_images=local_shap_images,
                    global_lime_images=global_lime_images,
                    local_lime_images=local_lime_images,
                )

                logger.info("[ANOMALY EVENT SAVED] model=%s feature=%s", model_name, feature_name)

            except Exception:
                logger.exception("Error in on_anomaly callback")

        def on_status(msg):
            logger.info(f"[STATUS] {msg}")

        def on_error(err):
            logger.error(f"[ERROR] {err}")

        # 9) Start generic live capture (library-level function, no Scenario/Design inside)
        handle = run_live_production(
            ssh=ssh,
            capture=cap,
            pipelines=pipelines,
            explainability=expl_cfg,   # may be None → no SHAP/LIME
            scenario_uuid=str(uuid),            # used as session_id and scenario_uuid in the library
            execution=execution,
            on_anomaly=on_anomaly,
            on_status=on_status,
            on_error=on_error,
        )

        production_handles[uuid] = handle
        return JsonResponse({'message': 'Real-time capture started'}, status=200)

    except Scenario.DoesNotExist:
        return JsonResponse({'error': 'Scenario not found'}, status=404)
    except Exception as e:
        logger.error("Error in production execution: %s", str(e))
        return JsonResponse({'error': str(e)}, status=500)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def stop_scenario_production_by_uuid(request, uuid):
    """
    Para la captura en vivo de un escenario dado.
    """

    handle = production_handles.get(uuid)
    if not handle:
        return JsonResponse({"error": "No active capture for this UUID"}, status=status.HTTP_404_NOT_FOUND)

    try:
        handle.stop()
        handle.join(timeout=2.0)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    finally:
        production_handles.pop(uuid, None)

    return JsonResponse({"message": f"Capture {uuid} stopped"})


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_anomaly(request, uuid, anomaly_id):
    """
    Deletes a specific anomaly and its associated local SHAP images.

    Args:
        uuid (str): UUID of the scenario.
        anomaly_id (int): ID of the anomaly to delete.

    Returns:
        - 204 No Content if successfully deleted.
        - 404 Not Found if scenario, scenario model, or anomaly does not exist.
        - 500 Internal Server Error on failure.
    """

    # Get the user from the request
    user = request.user

    try:
        # Retrieve the scenario, scenario model, and anomaly
        scenario = Scenario.objects.get(uuid=uuid, user=user.id)
        scenario_model = ScenarioModel.objects.get(scenario=scenario)
        anomaly = AnomalyMetric.objects.get(id=anomaly_id, scenario_model=scenario_model)

        local_shap_images = anomaly.local_shap_images or []

        # Delete local SHAP images
        for image_shap in local_shap_images:
            filename_shap = os.path.basename(image_shap)
            full_path_shap = os.path.join(settings.MEDIA_ROOT, 'shap_local_images', filename_shap)
            logger.info(f"[DELETE ANOMALY] Attempting to delete local SHAP image: {full_path_shap}")

            if os.path.exists(full_path_shap):
                try:
                    os.remove(full_path_shap)
                    logger.info(f"[DELETE ANOMALY] Deleted file: {full_path_shap}")
                except Exception as e:
                    logger.warning(f"[DELETE ANOMALY] Could not delete {full_path_shap}: {str(e)}")

        # Delete the anomaly metric
        anomaly.delete()

        logger.info(f"[DELETE ANOMALY] Anomaly ID {anomaly_id} deleted from database.")

        # Return success response
        return JsonResponse({'message': 'Anomaly and associated local images deleted.'}, status=204)

    # Return error if scenario does not exist
    except Scenario.DoesNotExist:
        logger.warning(f"[DELETE ANOMALY] Scenario with UUID {uuid} not found or permission denied.")
        return JsonResponse({'error': 'Scenario not found or permission denied.'}, status=404)

    # Return error if scenario model does not exist
    except ScenarioModel.DoesNotExist:
        logger.warning(f"[DELETE ANOMALY] Scenario model not found for scenario UUID: {uuid}")
        return JsonResponse({'error': 'Scenario model not found.'}, status=404)

    # Return error if anomaly does not exist
    except AnomalyMetric.DoesNotExist:
        logger.warning(f"[DELETE ANOMALY] Anomaly ID {anomaly_id} not found for scenario UUID: {uuid}")
        return JsonResponse({'error': 'Anomaly not found.'}, status=404)

    # Handle any other exceptions
    except Exception as e:
        logger.exception(f"[DELETE ANOMALY] Unexpected error deleting anomaly ID {anomaly_id}: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)
