from rest_framework import serializers
from .models import Scenario, File, AnomalyDetector, Metric

class ScenarioSerializer(serializers.ModelSerializer):
    class Meta:
        model = Scenario
        fields = ['id', 'name', 'user', 'design', 'uuid', 'status', 'date', 'file']
        extra_kwargs = {'user': {'read_only': True}}

class FileSerializer(serializers.ModelSerializer):
    class Meta:
        model = File
        fields = ['id', 'name', 'file_type', 'entry_count', 'content']
        extra_kwargs = {'user': {'read_only': True}}

class AnomalyDetectorSerializer(serializers.ModelSerializer):
    class Meta:
        model = AnomalyDetector
        fields = ['id', 'scenario']
        extra_kwargs = {'user': {'read_only': True}}

class MetricSerializer(serializers.ModelSerializer):
    class Meta:
        model = Metric
        fields = ['id', 'detector', 'model_name', 'accuracy', 'precision', 'recall', 'f1_score', 'confusion_matrix', 'date']
        extra_kwargs = {'user': {'read_only': True}}