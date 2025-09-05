# edge_controller/serializers.py
from .models import CustomUser
from rest_framework import serializers

class UserSerializer(serializers.ModelSerializer):
    """
    Serializer for the CustomUser model.

    Handles serialization and deserialization of user data,
    including custom fields like connection count, password changes,
    and design/scenario tracking.

    The password field is write-only and is properly hashed during creation.
    """
    class Meta:
        model = CustomUser
        fields = (
            'username',
            'password',
            'first_name',
            'last_name',
            'email',
            'admin_username',
            'number_times_connected',
            'number_times_modified_password',
            'number_designs_created',
            'number_executed_scenarios',
        )
        extra_kwargs = {'password': {'write_only': True}}

    def create(self, validated_data):
        """
        Create and return a new CustomUser instance with a hashed password.

        Args:
            validated_data (dict): Validated user data from the request.

        Returns:
            CustomUser: The newly created user instance.
        """
        user = CustomUser(**validated_data)  
        user.set_password(validated_data['password'])
        user.save()
        return user
