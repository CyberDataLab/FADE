from django.shortcuts import render
from django.contrib.auth import authenticate, login
from .serializers import UserSerializer
from django.contrib.auth.models import User
from .models import CustomUser
from django.http import JsonResponse
from django.core.mail import send_mail
from django.conf import settings
import jwt
import json
import logging
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated

logger = logging.getLogger('backend')

@api_view(['POST'])
def register_view(request):
    """
    Registers a new user.

    Requires admin credentials to authorize registration.
    Validates uniqueness of username and email.

    Expects:
        - admin_username: str (admin's username)
        - admin_password: str (admin's password)
        - username: str (new user's username)
        - email: str (new user's email)

    Returns:
        - 201 Created with user data and JWT tokens if registration is successful.
        - 403 Forbidden if admin credentials are invalid or user is not authorized.
        - 409 Conflict if username or email is already registered.
        - 400 Bad Request if data validation fails.
    """
    admin_username = request.data.get('admin_username')
    admin_password = request.data.get('admin_password')
    user_username = request.data.get('username')
    user_email = request.data.get('email')
    
    # Authenticate admin
    admin_user = authenticate(username=admin_username, password=admin_password)
    if admin_user is None or not admin_user.is_staff:
        return JsonResponse({'error': 'Admin not authorized or invalid credentials'}, status=status.HTTP_403_FORBIDDEN)
    
    # Validate uniqueness of username and email
    if CustomUser.objects.filter(username=user_username).exists():
        return JsonResponse({'error': 'User already registered'}, status=status.HTTP_409_CONFLICT)
    
    if CustomUser.objects.filter(email=user_email).exists():
        return JsonResponse({'error': 'Email already registered'}, status=status.HTTP_409_CONFLICT)
    
    # Clean and validate data
    user_data = request.data.copy()
    user_data.pop('admin_password', None)
    user_data.pop('confirm_password', None)
    serializer = UserSerializer(data=user_data)
    
    # Create user if data is valid
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
    """
    Authenticates a user and returns JWT tokens along with user information.

    Expects:
        - username: str
        - password: str

    Returns:
        - 200 OK with access and refresh tokens and user metadata if authentication is successful.
        - 400 Bad Request if credentials are invalid.
    """
    # Extract username and password from request
    username = request.data.get('username')
    password = request.data.get('password')

    logger.info("HOLAAAAAAAAA")

    logger.info(username)
    logger.info(password)

    # Authenticate user
    user = authenticate(username=username, password=password)

    if user is not None:
        # Increment the user's login counter
        user.number_times_connected += 1
        user.save()

        # Log in the user and generate JWT tokens
        login(request, user)
        refresh = RefreshToken.for_user(user)

        # Return access and refresh tokens along with user information
        return JsonResponse({
            'access_token': str(refresh.access_token),
            'refresh_token': str(refresh),
            'user': {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'numberTimesConnected': user.number_times_connected,
                'numberTimesModifiedPassword': user.number_times_modified_password,
                'numberDesignsCreated': user.number_designs_created,
                'numberExecutedScenarios': user.number_executed_scenarios,
            }
            }, status=status.HTTP_200_OK)
    
    # Return error if credentials are invalid
    return JsonResponse({'error': 'Invalid credentials'}, status=status.HTTP_400_BAD_REQUEST)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_user_view(request):
    """
    Returns the authenticated user's profile information.

    Permissions:
        - Requires authentication via JWT.

    Returns:
        - 200 OK with user metadata including usage stats.
    """
    # Get the authenticated user from the request
    user = request.user

    # Return user data as JSON response
    return JsonResponse({
        'user': {
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'numberTimesConnected': user.number_times_connected,
            'numberTimesModifiedPassword': user.number_times_modified_password,
            'numberDesignsCreated': user.number_designs_created,
            'numberExecutedScenarios': user.number_executed_scenarios
            }
    })

@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def update_user_view(request):
    """
    Updates the authenticated user's profile information.

    Permissions:
        - Requires authentication via JWT.

    Expects:
        - username (optional): str
        - first_name (optional): str
        - last_name (optional): str
        - email (optional): str

    Returns:
        - 200 OK with the updated user data.
    """
    # Get the authenticated user
    user = request.user

    # Update user fields with provided data or keep existing values
    user.username = request.data.get('username', user.username)
    user.first_name = request.data.get('first_name', user.first_name)
    user.last_name = request.data.get('last_name', user.last_name)
    user.email = request.data.get('email', user.email)
    user.save()

    # Return the updated profile
    return JsonResponse({
        'username': user.username,
        'first_name': user.first_name,
        'last_name': user.last_name,
        'email': user.email
    })

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def change_password_view(request):
    """
    Allows an authenticated user to change their password.

    Permissions:
        - Requires authentication via JWT.

    Expects:
        - current_password: str (the user's current password)
        - new_password: str (the new password to set)

    Returns:
        - 200 OK if the password is successfully changed.
        - 400 Bad Request if validation fails.
    """
    # Get the authenticated user
    user = request.user

    # Extract current and new passwords from the request
    current_password = request.data.get('current_password')
    new_password = request.data.get('new_password')

    # Return error if both passwords are not provided
    if not current_password or not new_password:
        return JsonResponse({'error': 'Both current and new password are required.'}, status=400)

    # Return error if current password is incorrect
    if not user.check_password(current_password):
        return JsonResponse({'error': 'Current password is incorrect'}, status=400)

    # Set new password and increment modification counter
    user.set_password(new_password)
    user.number_times_modified_password += 1
    user.save()

    # Return success message
    return JsonResponse({'message': 'Password updated successfully'}, status=200)
    
@api_view(['POST'])
def send_email_view(request):
    """
    Sends a password reset email to the user if the email is registered.

    Expects:
        - email: str (The registered user's email)

    Returns:
        - 200 OK if the email was sent successfully.
        - 404 Not Found if no user is associated with the provided email.
    """
    # Extract the email from the request
    email = request.data.get('email')
    try:
        # Look up user by email
        user = CustomUser.objects.get(email=email)

        # Generate JWT token for password reset
        token = CustomUser.generate_token(user.username, user.id)

        # Construct the reset URL to be used in the email
        reset_url = f"http://localhost:4200/reset-password?token={token}"
        
        # Send the password reset email
        send_mail(
            subject='Reset your password',
            message=f'Hi {user.first_name} \n\n Click the following link to reset your password: {reset_url} \n\n If you have not requested a password change, please ignore this message.\n\n Best regards.',
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email],
        )
        # Return success response
        return JsonResponse({'message': 'Password reset email sent.'}, status=status.HTTP_200_OK)
    
    # Return error if no user is found with the provided email
    except CustomUser.DoesNotExist:
        return JsonResponse({'error': 'User not found.'}, status=status.HTTP_404_NOT_FOUND)
    
@api_view(['POST'])
def reset_password_view(request):
    """
    Resets the user's password using a JWT token received via email.

    Expects:
        - token: str (JWT token sent to user's email)
        - password: str (new password to set)

    Returns:
        - 200 OK if password was successfully changed.
        - 400 Bad Request if token is invalid, expired, or password is reused.
        - 404 Not Found if the user does not exist.
    """
    try:
        # Parse token and new password from the request body
        body = json.loads(request.body)
        token = body.get('token')
        new_password = body.get('password')

    # Return error if JSON parsing fails or required fields are missing
    except (json.JSONDecodeError, KeyError):
        return JsonResponse({'error': 'Data not valid'}, status=status.HTTP_400_BAD_REQUEST)

    secret = settings.SECRET_KEY

    try:
        # Decode the JWT token
        payload = jwt.decode(token, secret, algorithms=['HS256'])
        username = payload['username']
        user_id = payload['id']

        # Look up the user from the decoded payload
        user = CustomUser.objects.get(id=user_id, username=username)

        # Prevent using the same password again
        if new_password and not user.check_password(new_password):
            user.set_password(new_password)
            user.number_times_modified_password += 1
            user.save()

            # Return success response
            return JsonResponse({'data': 'Password changed succesfully'})

        # Return error if the new password is the same as the old one
        return JsonResponse({'error': 'Please enter a previously unused password'}, status=status.HTTP_400_BAD_REQUEST)

    # Return error if token is expired
    except jwt.ExpiredSignatureError:
        return JsonResponse({'error': 'Token has expired'}, status=status.HTTP_400_BAD_REQUEST)
    
    # Return error if token is invalid
    except jwt.InvalidTokenError:
        return JsonResponse({'error': 'Invalid token'}, status=status.HTTP_400_BAD_REQUEST)
    
    # Return error if user does not exist
    except User.DoesNotExist:
        return JsonResponse({'error': 'User not found no encontrado'}, status=status.HTTP_404_NOT_FOUND)

@api_view(['POST'])
def token_obtain_pair_view(request):
    """
    Authenticates the user and returns a new pair of JWT tokens (access and refresh).

    Expects:
        - username: str
        - password: str

    Returns:
        - 200 OK with access_token, refresh_token, and basic user info if credentials are valid.
        - 400 Bad Request if authentication fails.
    """
    # Extract credentials from the request
    username = request.data.get('username')
    password = request.data.get('password')

    # Authenticate user
    user = authenticate(username=username, password=password)
    
    # Return error if authentication fails
    if user is None:
        return JsonResponse({'error': 'Invalid credentials'}, status=status.HTTP_400_BAD_REQUEST)

    # Generate JWT refresh and access tokens
    refresh = RefreshToken.for_user(user)

    # Return the tokens and user information
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
    Refreshes the JWT access token using a valid refresh token.

    Expects:
        - refresh: str (valid refresh token)

    Returns:
        - 200 OK with a new access token.
        - 400 Bad Request if token is missing or invalid.
    """
    # Get the refresh token from the request
    refresh_token = request.data.get('refresh')  

    # Return error if refresh token is not provided
    if not refresh_token:
        return JsonResponse({'error': 'Refresh token is required'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        # Refresh the token
        refresh = RefreshToken(refresh_token)
        access_token = str(refresh.access_token)

        # Return the new access token
        return JsonResponse({'access_token': access_token}, status=status.HTTP_200_OK)

    # Return error if the refresh token is invalid or expired
    except TokenError:
        return JsonResponse({'error': 'Invalid refresh token'}, status=status.HTTP_400_BAD_REQUEST)
