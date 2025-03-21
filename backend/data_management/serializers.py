from rest_framework import serializers
from .models import Scenario, File, AnomalyDetector, ClassificationMetric, RegressionMetric,AnomalyMetric

class ScenarioSerializer(serializers.ModelSerializer):
    class Meta:
        model = Scenario
        fields = ['id', 'name', 'user', 'design', 'uuid', 'status', 'date', 'file']
        extra_kwargs = {'user': {'read_only': True}}

class FileSerializer(serializers.ModelSerializer):
    class Meta:
        model = File
        fields = ['id', 'name', 'file_type', 'entry_count', 'content', 'references']
        extra_kwargs = {'user': {'read_only': True}}

class AnomalyDetectorSerializer(serializers.ModelSerializer):
    class Meta:
        model = AnomalyDetector
        fields = ['id', 'scenario', 'execution']
        extra_kwargs = {'user': {'read_only': True}}

class ClassificationMetricSerializer(serializers.ModelSerializer):
    class Meta:
        model = ClassificationMetric
        fields = ['id', 'detector', 'execution', 'model_name', 'accuracy', 'precision', 'recall', 'f1_score', 'confusion_matrix', 'date']
        extra_kwargs = {'user': {'read_only': True}}

class RegressionMetricSerializer(serializers.ModelSerializer):
    class Meta:
        model = RegressionMetric
        fields = ['id', 'detector', 'execution', 'model_name', 'mse', 'rmse', 'mae', 'r2', 'msle', 'date']
        extra_kwargs = {'detector': {'read_only': True}}

class AnomalyMetricSerializer(serializers.ModelSerializer):
    class Meta:
        model = AnomalyMetric
        fields = ['id', 'detector', 'execution', 'model_name', 'feature_name', 'anomalies', 'date']
        extra_kwargs = {'user': {'read_only': True}}