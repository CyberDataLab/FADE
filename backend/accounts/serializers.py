# edge_controller/serializers.py
from .models import CustomUser
from rest_framework import serializers

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = ('username', 'password', 'first_name', 'last_name', 'email', 'admin_username')
        extra_kwargs = {'password': {'write_only': True}}

    def create(self, validated_data):
        user = CustomUser(**validated_data)  
        user.set_password(validated_data['password'])
        user.save()
        return user
