# edge_controller/serializers.py
from .models import CustomUser
from rest_framework import serializers

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = ('username', 'password', 'name', 'lastName', 'email')
        extra_kwargs = {'password': {'write_only': True}}

    def create(self, validated_data):
        user = CustomUser(**validated_data)  # Usa el modelo personalizado
        user.set_password(validated_data['password'])  # Establecer la contraseña
        user.save()
        return user
