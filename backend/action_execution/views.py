from django.shortcuts import render
from django.http import JsonResponse
from .models import ActionController, ActionReceiver, PolicyManagement, ActionSync, PerformAction

# Create your views here.

# Views for ActionController
def perform_action(request):
    controller = ActionController(name='Example ActionController')
    action = request.POST.get('action', '')
    controller.perform_action(action)
    return JsonResponse({'message': 'Action performed successfully'})

def sync_action(request):
    controller = ActionController(name='Example ActionController')
    controller.sync_action()
    return JsonResponse({'message': 'Actions synchronized'})

def get_action_status(request, action_id):
    controller = ActionController(name='Example ActionController')
    status = controller.get_action_status(action_id)
    return JsonResponse({'status': status})


# Views for ActionReceiver
def receive_action(request):
    receiver = ActionReceiver(name='Example ActionReceiver')
    action = request.POST.get('action', '')
    receiver.receive_action(action)
    return JsonResponse({'message': 'Action received successfully'})


# Views for PolicyManagement
def get_policies(request):
    manager = PolicyManagement(name='Example PolicyManager')
    policies = manager.get_policies()
    return JsonResponse({'policies': policies})

def is_action_allowed(request):
    manager = PolicyManagement(name='Example PolicyManager')
    action = request.POST.get('action', '')
    allowed = manager.is_action_allowed(action)
    return JsonResponse({'allowed': allowed})

def create_policy(request):
    manager = PolicyManagement(name='Example PolicyManager')
    policy = request.POST.get('policy', '')
    manager.create_policy(policy)
    return JsonResponse({'message': 'Policy created successfully'})

def sync_policies(request):
    manager = PolicyManagement(name='Example PolicyManager')
    manager.sync_policies()
    return JsonResponse({'message': 'Policies synchronized successfully'})


# Views for ActionSync
def check_sync_status(request):
    sync = ActionSync(name='Example ActionSync')
    sync.check_sync_status()
    return JsonResponse({'message': 'Sync status checked'})

def sync_data(request):
    sync = ActionSync(name='Example ActionSync')
    sync.sync()
    return JsonResponse({'message': 'Data synchronized successfully'})

def verify_sync_actions(request):
    sync = ActionSync(name='Example ActionSync')
    sync.verify_sync_actions()
    return JsonResponse({'message': 'Sync actions verified successfully'})


# Views for PerformAction
def do_action(request):
    action = PerformAction(name='Example PerformAction')
    action_data = request.POST.get('action', '')
    action.do_action(action_data)
    return JsonResponse({'message': 'Action performed successfully'})

def get_action_status_perform(request, action_id):
    action = PerformAction(name='Example PerformAction')
    status = action.get_action_status(action_id)
    return JsonResponse({'status': status})
