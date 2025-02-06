from rest_framework import serializers
from .models import Scenario

class ScenarioSerializer(serializers.ModelSerializer):
    class Meta:
        model = Scenario
        fields = ['id', 'name', 'user', 'design', 'uuid', 'status', 'date']
        extra_kwargs = {'user': {'read_only': True}}
