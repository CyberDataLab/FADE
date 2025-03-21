from django.urls import path
from . import views

urlpatterns = [
    # DataController URLs
    path('put-data-controller/', views.put_data_controller, name='put_data_controller'),
    path('sync-data-controller/', views.sync_data_controller, name='sync_data_controller'),
    path('set-aggregation-technique/<str:technique>/', views.set_aggregation_technique, name='set_aggregation_technique'),
    path('set-filtering-strategy-controller/<str:strategy>/', views.set_filtering_strategy_controller, name='set_filtering_strategy_controller'),

    # DataReceiver URLs
    path('put-data-receiver/', views.put_data_receiver, name='put_data_receiver'),
    path('validate-data-receiver/', views.validate_data_receiver, name='validate_data_receiver'),

    # DataFilter URLs
    path('set-filtering-strategy-filter/<str:strategy>/', views.set_filtering_strategy_filter, name='set_filtering_strategy_filter'),
    path('filter-data/', views.filter_data, name='filter_data'),

    # DataStorage URLs
    path('serialize-data/', views.serialize_data, name='serialize_data'),
    path('store-data/', views.store_data, name='store_data'),
    path('get-available-space/', views.get_available_space, name='get_available_space'),

    # DataMixer URLs
    path('set-aggregation-technique-mixer/<str:technique>/', views.set_aggregation_technique_mixer, name='set_aggregation_technique_mixer'),
    path('check-for-data-to-aggregate/', views.check_for_data_to_aggregate, name='check_for_data_to_aggregate'),
    path('aggregate-data/', views.aggregate_data, name='aggregate_data'),

    # DataSync URLs
    path('check-sync-status/', views.check_sync_status, name='check_sync_status'),
    path('sync-data-sync/', views.sync_data_sync, name='sync_data_sync'),
    path('verify-sync-data/', views.verify_sync_data, name='verify_sync_data'),

    # Scenarios URL
    path('scenarios/create/', views.create_scenario, name='create_scenario'),
    path('scenarios/', views.get_scenarios_by_user, name='get_scenarios_by_user'), 
    path('scenarios/<uuid:uuid>/', views.get_scenario_by_uuid, name='get_scenario_by_uuid'), 
    path('scenarios/run/<uuid:uuid>/', views.run_scenario_by_uuid, name='run_scenario_by_uuid'),
    path('scenarios/delete/<uuid:uuid>/', views.delete_scenario_by_uuid, name='delete_scenario_by_uuid'),
    path('scenarios/put/<uuid:uuid>/', views.put_scenario_by_uuid, name='put_scenario_by_uuid'),
    path('scenarios/<uuid:uuid>/classification-metrics/', views.get_scenario_classification_metrics_by_uuid, name='get_scenario_classification_metrics_by_uuid'),
    path('scenarios/<uuid:uuid>/anomaly-metrics/', views.get_scenario_anomaly_metrics_by_uuid, name='get_scenario_anomaly_metrics_by_uuid'),
]