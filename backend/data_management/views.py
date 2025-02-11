# Create your views here.
from django.shortcuts import render
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from .models import Scenario
from accounts.models import CustomUser
from .serializers import ScenarioSerializer
from django.http import JsonResponse
from .models import DataController, DataReceiver, DataFilter, DataStorage, DataMixer, DataSync
import logging

# Obtén un logger
logger = logging.getLogger(__name__)

# Views for DataController
def put_data_controller(request):
    controller = DataController(name='Example Controller')
    controller.put_data()  # Aquí puedes pasar parámetros si es necesario
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
def create_scenario(request):
    user = request.user  # Obtenemos el usuario autenticado

    data = request.data.copy()
    #data.pop('confirm_password', None)  # Eliminar campos innecesarios
    data['user'] = user.id  # Asignamos el usuario autenticado al campo `user`

    serializer = ScenarioSerializer(data=data)
    if serializer.is_valid():
        serializer.save(user=user)  # Guardamos con el usuario autenticado
        return JsonResponse({'message': 'Scenario created successfully'}, status=status.HTTP_201_CREATED)
    
    return JsonResponse(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_scenarios_by_user(request):
    user = request.user  # Usuario autenticado

    # Filtrar los escenarios que pertenecen al usuario autenticado
    scenarios = Scenario.objects.filter(user=user.id)

    # Serializar los escenarios encontrados
    serializer = ScenarioSerializer(scenarios, many=True)
    
    return JsonResponse(serializer.data, safe=False, status=status.HTTP_200_OK)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_scenario_by_uuid(request, uuid):
    user = request.user  # Usuario autenticado

    try:
        # Buscar el escenario por UUID y asegurarse de que pertenece al usuario autenticado
        scenario = Scenario.objects.get(uuid=uuid, user=user.id)
        serializer = ScenarioSerializer(scenario)  # Serializar el escenario
        return JsonResponse(serializer.data, safe=False, status=status.HTTP_200_OK)  # Devolver el escenario serializado
    except Scenario.DoesNotExist:
        return JsonResponse({'error': 'Scenario not found or you do not have permission to access it'}, status=status.HTTP_404_NOT_FOUND)

@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def put_scenario_by_uuid(request, uuid):
    user = request.user  # Usuario autenticado

    try:
        # Buscar el escenario por UUID y asegurarse de que pertenece al usuario autenticado
        scenario = Scenario.objects.get(uuid=uuid, user=user.id)
        
        # Actualizar los campos del escenario con los datos recibidos en la solicitud
        scenario.design = request.data.get('design', scenario.design)  # Actualiza el diseño si se pasa uno nuevo
        serializer = ScenarioSerializer(scenario)
        serializer.save()  # Guardar los cambios
        
        # Opcionalmente, podrías serializar los datos actualizados para devolver la respuesta
        
        return JsonResponse(serializer.data, status=status.HTTP_200_OK)

    except Scenario.DoesNotExist:
        return JsonResponse({'error': 'Scenario not found or you do not have permission to update it'}, status=status.HTTP_404_NOT_FOUND)

@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_scenario_by_uuid(request, uuid):
    user = request.user  # Usuario autenticado

    try:
        # Buscar el escenario por UUID y asegurarse de que pertenece al usuario autenticado
        scenario = Scenario.objects.get(uuid=uuid, user=user.id)
        scenario.delete()  # Eliminar el escenario
        return JsonResponse({'message': 'Scenario deleted successfully'}, status=status.HTTP_200_OK)
    except Scenario.DoesNotExist:
        return JsonResponse({'error': 'Scenario not found or you do not have permission to delete it'}, status=status.HTTP_404_NOT_FOUND)

