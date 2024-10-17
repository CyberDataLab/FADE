from django.urls import path
from . import views

urlpatterns = [
    # ActionController URLs
    path('perform-action/', views.perform_action, name='perform_action'),
    path('sync-action/', views.sync_action, name='sync_action'),
    path('get-action-status/<int:action_id>/', views.get_action_status, name='get_action_status'),

    # ActionReceiver URLs
    path('receive-action/', views.receive_action, name='receive_action'),

    # PolicyManagement URLs
    path('get-policies/', views.get_policies, name='get_policies'),
    path('is-action-allowed/', views.is_action_allowed, name='is_action_allowed'),
    path('create-policy/', views.create_policy, name='create_policy'),
    path('sync-policies/', views.sync_policies, name='sync_policies'),

    # ActionSync URLs
    path('check-sync-status/', views.check_sync_status, name='check_sync_status'),
    path('sync-data/', views.sync_data, name='sync_data'),
    path('verify-sync-actions/', views.verify_sync_actions, name='verify_sync_actions'),

    # PerformAction URLs
    path('do-action/', views.do_action, name='do_action'),
    path('get-action-status-perform/<int:action_id>/', views.get_action_status_perform, name='get_action_status_perform'),
]
