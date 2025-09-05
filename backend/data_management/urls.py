from django.urls import path
from . import views

urlpatterns = [
    # Scenarios URL
    path('scenarios/create/', views.create_scenario, name='create_scenario'),
    path('scenarios/', views.get_scenarios_by_user, name='get_scenarios_by_user'), 
    path('scenarios/<uuid:uuid>/', views.get_scenario_by_uuid, name='get_scenario_by_uuid'), 
    path('scenarios/run/<uuid:uuid>/', views.run_scenario_by_uuid, name='run_scenario_by_uuid'),
    path('scenarios/delete/<uuid:uuid>/', views.delete_scenario_by_uuid, name='delete_scenario_by_uuid'),
    path('scenarios/put/<uuid:uuid>/', views.put_scenario_by_uuid, name='put_scenario_by_uuid'),
    path('scenarios/<uuid:uuid>/classification-metrics/', views.get_scenario_classification_metrics_by_uuid, name='get_scenario_classification_metrics_by_uuid'),
    path('scenarios/<uuid:uuid>/play-production/', views.play_scenario_production_by_uuid, name='play_scenario_production_by_uuid'),
    path('scenarios/<uuid:uuid>/stop-production/', views.stop_scenario_production_by_uuid, name='stop_scenario_production_by_uuid'),
    path('scenarios/<uuid:uuid>/regression-metrics/', views.get_scenario_regression_metrics_by_uuid, name='get_scenario_regression_metrics_by_uuid'),
    path('scenarios/<uuid:uuid>/anomaly-metrics/', views.get_scenario_anomaly_metrics_by_uuid, name='get_scenario_anomaly_metrics_by_uuid'),
    path('scenarios/<uuid:uuid>/anomaly-production-metrics/', views.get_scenario_production_anomaly_metrics_by_uuid, name='get_scenario_production_anomaly_metrics_by_uuid'),
    path('scenarios/<uuid:uuid>/delete-anomaly/<int:anomaly_id>/', views.delete_anomaly, name='delete_anomaly'),

]