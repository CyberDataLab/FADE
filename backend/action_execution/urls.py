from django.urls import path
from . import views

urlpatterns = [
    # PolicyManagement URLs
    path('apply-policy/', views.apply_policy, name='apply_policy'),
]
