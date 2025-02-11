from django.shortcuts import render
from django.contrib.auth import authenticate, login
from rest_framework import status
from rest_framework.decorators import api_view
from .serializers import UserSerializer
from django.contrib.auth.models import User
from .models import CustomUser
from django.http import JsonResponse
from django.core.mail import send_mail
from django.conf import settings
import jwt
import json
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError


@api_view(['POST'])
def register_view(request):
    admin_username = request.data.get('admin_username')
    admin_password = request.data.get('admin_password')
    user_username = request.data.get('username')
    user_email = request.data.get('email')
    
    admin_user = authenticate(username=admin_username, password=admin_password)
    if admin_user is None or not admin_user.is_staff:
        return JsonResponse({'error': 'Admin not authorized or invalid credentials'}, status=status.HTTP_403_FORBIDDEN)
    
    if CustomUser.objects.filter(username=user_username).exists():
        return JsonResponse({'error': 'User already registered'}, status=status.HTTP_409_CONFLICT)
    
    if CustomUser.objects.filter(email=user_email).exists():
        return JsonResponse({'error': 'Email already registered'}, status=status.HTTP_409_CONFLICT)
    
    user_data = request.data.copy()
    user_data.pop('admin_password', None)
    user_data.pop('confirm_password', None)
    serializer = UserSerializer(data=user_data)
    
    if serializer.is_valid():
        user = serializer.save()
        refresh = RefreshToken.for_user(user)
        return JsonResponse({
            'user': serializer.data,
            'access_token': str(refresh.access_token),
            'refresh_token': str(refresh)
        }, status=status.HTTP_201_CREATED)
    
    return JsonResponse(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@api_view(['POST'])
def login_view(request):
    username = request.data.get('username')
    password = request.data.get('password')

    user = authenticate(username=username, password=password)

    if user is not None:
        login(request, user)
        refresh = RefreshToken.for_user(user)
        return JsonResponse({
            'access_token': str(refresh.access_token),
            'refresh_token': str(refresh),
            'user': {
                'username': user.username,
                'email': user.email,
            }
        }, status=status.HTTP_200_OK)
    
    return JsonResponse({'error': 'Invalid credentials'}, status=status.HTTP_400_BAD_REQUEST)

    
@api_view(['POST'])
def send_email_view(request):
    email = request.data.get('email')
    try:
        user = CustomUser.objects.get(email=email)

        token = CustomUser.generate_token(user.username, user.id)

        reset_url = f"http://localhost:4200/reset-password?token={token}"
        
        send_mail(
            subject='Reset your password',
            message=f'Hi {user.first_name} \n\n Click the following link to reset your password: {reset_url} \n\n If you have not requested a password change, please ignore this message.\n\n Best regards.',
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email],
        )
        return JsonResponse({'message': 'Password reset email sent.'}, status=status.HTTP_200_OK)
    except CustomUser.DoesNotExist:
        return JsonResponse({'error': 'User not found.'}, status=status.HTTP_404_NOT_FOUND)
    
@api_view(['POST'])
def reset_password_view(request):
    try:
        body = json.loads(request.body)
        token = body.get('token')
        new_password = body.get('password')
    except (json.JSONDecodeError, KeyError):
        return JsonResponse({'error': 'Data not valid'}, status=status.HTTP_400_BAD_REQUEST)

    secret = settings.SECRET_KEY

    try:
        payload = jwt.decode(token, secret, algorithms=['HS256'])
        username = payload['username']
        user_id = payload['id']

        user = CustomUser.objects.get(id=user_id, username=username)

        if new_password and not user.check_password(new_password):
            user.set_password(new_password)
            user.save()
            return JsonResponse({'data': 'Password changed succesfully'})

        return JsonResponse({'error': 'Please enter a previously unused password'}, status=status.HTTP_400_BAD_REQUEST)

    except jwt.ExpiredSignatureError:
        return JsonResponse({'error': 'Token has expired'}, status=status.HTTP_400_BAD_REQUEST)
    except jwt.InvalidTokenError:
        return JsonResponse({'error': 'Invalid token'}, status=status.HTTP_400_BAD_REQUEST)
    except User.DoesNotExist:
        return JsonResponse({'error': 'User not found no encontrado'}, status=status.HTTP_404_NOT_FOUND)

@api_view(['POST'])
def token_obtain_pair_view(request):
    """
    View for obtaining the JWT access and refresh tokens using username and password.
    """
    username = request.data.get('username')
    password = request.data.get('password')

    user = authenticate(username=username, password=password)
    
    if user is None:
        return JsonResponse({'error': 'Invalid credentials'}, status=status.HTTP_400_BAD_REQUEST)

    refresh = RefreshToken.for_user(user)

    return JsonResponse({
        'access_token': str(refresh.access_token),
        'refresh_token': str(refresh),
        'user': {
            'username': user.username,
            'email': user.email,
        }
    }, status=status.HTTP_200_OK)


@api_view(['POST'])
def token_refresh_view(request):
    """
    View for refreshing the JWT access token using a valid refresh token.
    """
    refresh_token = request.data.get('refresh')  

    if not refresh_token:
        return JsonResponse({'error': 'Refresh token is required'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        refresh = RefreshToken(refresh_token)
        access_token = str(refresh.access_token)
        return JsonResponse({'access_token': access_token}, status=status.HTTP_200_OK)

    except TokenError:
        return JsonResponse({'error': 'Invalid refresh token'}, status=status.HTTP_400_BAD_REQUEST)
