from rest_framework import serializers
from .models import Scenario, File, AnomalyDetector, ClassificationMetric, RegressionMetric,AnomalyMetric

class FileSerializer(serializers.ModelSerializer):
    class Meta:
        model = File
        fields = ['id', 'name', 'file_type', 'entry_count', 'content', 'references']
        extra_kwargs = {'user': {'read_only': True}}

class ScenarioSerializer(serializers.ModelSerializer):
    files = FileSerializer(many=True, read_only=True)

    class Meta:
        model = Scenario
        fields = ['id', 'name', 'user', 'design', 'uuid', 'status', 'date', 'files']


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
        fields = ['id', 'detector', 'execution', 'model_name', 'feature_name', 'anomalies', 'date', 'production', 'anomaly_image', 'global_shap_image', 'local_shap_image', 'global_lime_image', 'local_lime_image']
        extra_kwargs = {'user': {'read_only': True}}