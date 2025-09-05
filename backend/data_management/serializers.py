from rest_framework import serializers
from .models import Scenario, File, AnomalyDetector, ClassificationMetric, RegressionMetric,AnomalyMetric

class FileSerializer(serializers.ModelSerializer):
    """
    Serializer for the File model.
    Handles serialization and deserialization of file data,
    including file type, entry count, content, and references.
    The user field is read-only, ensuring that it is set automatically.
    """
    class Meta:
        model = File
        fields = ['id', 'name', 'file_type', 'entry_count', 'content', 'references']
        extra_kwargs = {'user': {'read_only': True}}

class ScenarioSerializer(serializers.ModelSerializer):
    """
    Serializer for the Scenario model.
    Handles serialization and deserialization of scenario data,
    including user, design, UUID, status, date, and associated files.
    """
    # Nested serializer for files
    files = FileSerializer(many=True, read_only=True)

    class Meta:
        model = Scenario
        fields = ['id', 'name', 'user', 'design', 'uuid', 'status', 'date', 'files']

class AnomalyDetectorSerializer(serializers.ModelSerializer):
    """
    Serializer for the AnomalyDetector model.
    Handles serialization and deserialization of anomaly detector data,
    including scenario, execution, and user.
    The user field is read-only, ensuring that it is set automatically.
    """
    class Meta:
        model = AnomalyDetector
        fields = ['id', 'scenario', 'execution']
        extra_kwargs = {'user': {'read_only': True}}

class ClassificationMetricSerializer(serializers.ModelSerializer):
    """
    Serializer for the ClassificationMetric model.
    Handles serialization and deserialization of classification metric data,
    including detector, execution, model name, accuracy, precision, recall,
    f1 score, confusion matrix, date, and associated SHAP/LIME images.
    The detector field is read-only, ensuring that it is set automatically.
    """
    class Meta:
        model = ClassificationMetric
        fields = ['id', 'detector', 'execution', 'model_name', 'accuracy', 'precision', 'recall', 'f1_score', 'confusion_matrix', 'date', 'global_shap_images', 'local_shap_images', 'global_lime_images', 'local_lime_images']
        extra_kwargs = {'detector': {'read_only': True}}

class RegressionMetricSerializer(serializers.ModelSerializer):
    """
    Serializer for the RegressionMetric model.
    Handles serialization and deserialization of regression metric data,
    including detector, execution, model name, mean squared error (MSE),
    root mean squared error (RMSE), mean absolute error (MAE), R-squared (R2),
    mean squared logarithmic error (MSLE), date, and associated SHAP/LIME images.
    The detector field is read-only, ensuring that it is set automatically.
    """
    class Meta:
        model = RegressionMetric
        fields = ['id', 'detector', 'execution', 'model_name', 'mse', 'rmse', 'mae', 'r2', 'msle', 'date', 'global_shap_images', 'local_shap_images', 'global_lime_images', 'local_lime_images']
        extra_kwargs = {'detector': {'read_only': True}}

class AnomalyMetricSerializer(serializers.ModelSerializer):
    """
    Serializer for the AnomalyMetric model.
    Handles serialization and deserialization of anomaly metric data,
    including detector, execution, model name, feature name, anomalies,
    date, production status, and associated SHAP/LIME images.
    The detector field is read-only, ensuring that it is set automatically.
    """
    class Meta:
        model = AnomalyMetric
        fields = ['id', 'detector', 'execution', 'model_name', 'feature_name', 'anomalies', 'date', 'production', 'packet_image', 'global_shap_images', 'local_shap_images', 'global_lime_images', 'local_lime_images']
        extra_kwargs = {'detector': {'read_only': True}}