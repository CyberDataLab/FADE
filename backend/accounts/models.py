from django.contrib.auth.models import AbstractUser
from django.db import models
import secrets
from datetime import timedelta
from django.utils import timezone
import jwt
from datetime import datetime, timedelta
from django.conf import settings

class CustomUser(AbstractUser):
    first_name = models.CharField(max_length=255, null=False, blank=True, default="Name")
    last_name = models.CharField(max_length=255, null=False, blank=True, default="Last name")
    admin_username = models.CharField(max_length=255, null=False, blank=True, default='edulb96')
    '''
    password_reset_token = models.CharField(max_length=64, blank=True, null=True)
    password_reset_expiration = models.DateTimeField(blank=True, null=True)

    def generate_password_reset_token(self):
        self.password_reset_token = secrets.token_hex(32)
        self.password_reset_expiration = timezone.now() + timedelta(hours=1)
        self.save()
    '''

    def generate_token(username, user_id):
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