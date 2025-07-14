from django.urls import path
from . import views

urlpatterns = [
    path('system-info/', views.system_info, name='system_info'),
]