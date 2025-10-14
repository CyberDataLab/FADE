from django.db import models
import uuid
from django.db.models import JSONField


# Create your models here.
class File(models.Model):
    """
    Represents an uploaded file used in the system, such as a CSV dataset or network capture.

    Fields:
    - id: Auto-incremented unique identifier for the file.
    - name: Human-readable name assigned to the file.
    - file_type: Type of the file (either 'csv' or 'red').
    - entry_count: Number of rows or records contained in the file.
    - content: Actual file uploaded and stored under MEDIA_ROOT/files/.
    - references: Number of times the file is referenced across designs or scenarios.
    """
    
    FILE_TYPES = [
        ('csv', 'CSV'),
        ('red', 'Network'),
    ]

    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=255)
    file_type = models.CharField(max_length=10, choices=FILE_TYPES)
    entry_count = models.IntegerField(default=0)
    content = models.FileField(upload_to='files/')
    references = models.IntegerField(default=1)

    class Meta:
        db_table = "File"
        
class Scenario(models.Model):
    """
    Represents a user-defined scenario consisting of a visual design and associated metadata.

    Fields:
    - name: Name assigned to the scenario. Defaults to "Scenario name".
    - user: Reference to the CustomUser who created the scenario.
    - design: JSON representation of the visual node structure or configuration.
    - uuid: Unique identifier for the scenario, auto-generated and immutable.
    - status: Current state of the scenario (e.g., 'Draft', 'Running', 'Completed').
    - date: Timestamp when the scenario was created.
    - files: Files associated with this scenario (e.g., CSVs, network data).
    """
    name = models.CharField(max_length=255, null=False, blank=True, default="Scenario name")
    user = models.ForeignKey('accounts.CustomUser', on_delete=models.CASCADE)
    design = models.JSONField()
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    status = models.CharField(max_length=255, default='Draft')
    date = models.DateTimeField(auto_now_add=True)
    files = models.ManyToManyField('File', blank=True)

    class Meta:
        db_table = "Scenario"

class ScenarioModel(models.Model):
    """
    Represents a model associated with a scenario.

    Fields:
    - scenario: Foreign key to the Scenario this scenario model belongs to.
    - execution: Execution number to track multiple runs of the scenario model.
    """
    scenario = models.ForeignKey(Scenario, on_delete=models.CASCADE, null=True, blank=True)
    execution = models.IntegerField(default=0)
    
    class Meta:
        db_table = "ScenarioModel"

class ClassificationMetric(models.Model):
    """
    Represents metrics for classification models used in anomaly detection.

    Fields:
    - scenario_model: Foreign key to the ScenarioModel this metric belongs to.
    - execution: Execution number to track multiple runs of the scenario model.
    - model_name: Name of the classification model used.
    - accuracy, precision, recall, f1_score: Performance metrics of the classification model.
    - confusion_matrix: Text representation of the confusion matrix.
    - date: Timestamp when the metrics were recorded.
    - global_shap_images, local_shap_images, global_lime_images, local_lime_images: JSON fields to store images related to SHAP and LIME explanations.
    """
    scenario_model = models.ForeignKey(ScenarioModel, on_delete=models.CASCADE, null=True, blank=True)
    execution = models.IntegerField(default=0)
    model_name = models.CharField(max_length=255, default='model_name')
    accuracy = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    precision = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    recall = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    f1_score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    confusion_matrix = models.TextField(null=True, blank=True)
    date = models.DateTimeField(auto_now_add=True)

    global_shap_images = JSONField(null=True, blank=True)
    local_shap_images = JSONField(null=True, blank=True)
    global_lime_images = JSONField(null=True, blank=True)
    local_lime_images = JSONField(null=True, blank=True)

    class Meta:
        db_table = "ClassificationMetric"

class RegressionMetric(models.Model):
    """
    Represents metrics for regression models used in anomaly detection.

    Fields:
    - scenario_model: Foreign key to the ScenarioModel this metric belongs to.
    - execution: Execution number to track multiple runs of the scenario model.
    - model_name: Name of the regression model used.
    - mse, rmse, mae, r2, msle: Performance metrics of the regression model.
    - date: Timestamp when the metrics were recorded.
    - global_shap_images, local_shap_images, global_lime_images, local_lime_images: JSON fields to store images related to SHAP and LIME explanations.
    """
    scenario_model = models.ForeignKey(ScenarioModel, on_delete=models.CASCADE, null=True, blank=True)
    execution = models.IntegerField(default=0)
    model_name = models.CharField(max_length=255, default='model_name')
    mse = models.DecimalField(max_digits=10, decimal_places=5, null=True, blank=True)
    rmse = models.DecimalField(max_digits=10, decimal_places=5, null=True, blank=True)
    mae = models.DecimalField(max_digits=10, decimal_places=5, null=True, blank=True)
    r2 = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    msle = models.DecimalField(max_digits=10, decimal_places=5, null=True, blank=True)
    date = models.DateTimeField(auto_now_add=True)

    global_shap_images = JSONField(null=True, blank=True)
    local_shap_images = JSONField(null=True, blank=True)
    global_lime_images = JSONField(null=True, blank=True)
    local_lime_images = JSONField(null=True, blank=True)

    class Meta:
        db_table = "RegressionMetric"

class AnomalyMetric(models.Model):
    """
    Represents metrics for anomaly detection models, including detected anomalies and associated metadata.
    
    Fields:
    - scenario_model: Foreign key to the ScenarioModel this metric belongs to.
    - execution: Execution number to track multiple runs of the scenario model.
    - model_name: Name of the anomaly detection model used.
    - feature_name: Name of the feature being analyzed for anomalies.
    - anomalies: JSON field containing details about detected anomalies.
    - date: Timestamp when the metrics were recorded.
    - anomaly_details: Text field for additional details about the anomalies.
    - global_shap_images, local_shap_images, global_lime_images, local_lime_images: JSON fields to store images related to SHAP and LIME explanations.
    """
    scenario_model = models.ForeignKey(ScenarioModel, on_delete=models.CASCADE)
    execution = models.IntegerField()
    model_name = models.CharField(max_length=255, default='model_name')
    feature_name = models.CharField(max_length=255)
    anomalies = models.JSONField()
    date = models.DateTimeField(auto_now_add=True)
    production = models.BooleanField(default=False)

    anomaly_details = models.TextField(null=True, blank=True)
    global_shap_images = JSONField(null=True, blank=True)
    local_shap_images = JSONField(null=True, blank=True)
    global_lime_images = JSONField(null=True, blank=True)
    local_lime_images = JSONField(null=True, blank=True)

    class Meta:
        db_table = "AnomalyMetric"
