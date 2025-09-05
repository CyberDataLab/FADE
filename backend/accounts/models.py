from django.contrib.auth.models import AbstractUser
from django.db import models
import secrets
from datetime import timedelta
from django.utils import timezone
import jwt
from datetime import datetime, timedelta
from django.conf import settings

class CustomUser(AbstractUser):
    """
    Custom user model that extends Django's AbstractUser.

    Adds additional fields for tracking user activity, such as:
    - first_name: User's first name. Defaults to "Name".
    - last_name: User's last name. Defaults to "Last name".
    - admin_username: Administrator username who created the user. Defaults to "edulb96".
    - number_times_connected: Number of times the user has logged in.
    - number_times_modified_password: Number of times the user has changed their password.
    - number_designs_created: Number of designs the user has created in the system.
    - number_executed_scenarios: Number of scenarios the user has executed.
    """
    first_name = models.CharField(max_length=255, null=False, blank=True, default="Name")
    last_name = models.CharField(max_length=255, null=False, blank=True, default="Last name")
    admin_username = models.CharField(max_length=255, null=False, blank=True, default='edulb96')
    number_times_connected = models.IntegerField(default=0)
    number_times_modified_password = models.IntegerField(default=0)
    number_designs_created = models.IntegerField(default=0)
    number_executed_scenarios = models.IntegerField(default=0)

    def generate_token(username, user_id):
        """
        Generates a JSON Web Token (JWT) for the given user.

        Args:
            username (str): The username of the user.
            user_id (int): The ID of the user.

        Returns:
            str: A JWT token string encoded with the user's information and expiration.
        """
        duration = timedelta(hours=1)
        secret = settings.SECRET_KEY  
        
        payload = {
            'username': username,
            'id': user_id,
            'exp': datetime.utcnow() + duration
        }
        
        token = jwt.encode(payload, secret, algorithm='HS256')
        return token
    
    class Meta:
        db_table = "User"