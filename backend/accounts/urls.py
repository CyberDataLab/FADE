from django.urls import path
from .views import register_view, login_view, send_email_view, reset_password_view, token_obtain_pair_view, token_refresh_view

urlpatterns = [
    path('register', register_view, name='register'),
    path('login', login_view, name='login'),
    path('send-email', send_email_view, name='send-email'),
    path('reset-password', reset_password_view, name='reset-password'),
    path('token/', token_obtain_pair_view, name='token_obtain_pair_view'),
    path('token/refresh/', token_refresh_view, name='token_refresh_view'),

]
