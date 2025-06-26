from django.db import models
import uuid


# Create your models here.
class DataController(models.Model):
    name = models.CharField(max_length=100, default='DataController')

    def put_data(self):
        pass

    def sync_data(self):
        pass

    def set_aggregation_technique(self, technique):
        pass

    def set_filtering_strategy(self, strategy):
        pass


class DataReceiver(models.Model):
    name = models.CharField(max_length=100, default='DataReceiver')

    def put_data(self, data):
        pass

    def validate_data(self, data):
        pass

class DataFilter(models.Model):
    name = models.CharField(max_length=100, default='DataFilter')

    def set_filtering_strategy(self, strategy):
        pass

    def filter_data(self, data):
        pass


class DataStorage(models.Model):
    name = models.CharField(max_length=100, default='DataStorage')

    def serialize_data(self, data):
        pass

    def store_data(self, data):
        pass

    def get_available_space(self):
        pass


class DataMixer(models.Model):
    name = models.CharField(max_length=100, default='DataMixer')

    def set_aggregation_technique(self, technique):
        pass

    def check_for_data_to_aggregate(self):
        pass

    def aggregate_data(self, data_list):
        pass

class DataSync(models.Model):
    name = models.CharField(max_length=100, default='DataSync')

    def check_sync_status(self):
        pass

    def sync(self):
        pass

    def verify_sync_data(self):
        pass

class File(models.Model):
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
    name = models.CharField(max_length=255, null=False, blank=True, default="Scenario name")
    user = models.ForeignKey('accounts.CustomUser', on_delete=models.CASCADE)
    design = models.JSONField()
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    status = models.CharField(max_length=255, default='Draft')
    date = models.DateTimeField(auto_now_add=True)
    files = models.ManyToManyField('File', blank=True)

    class Meta:
        db_table = "Scenario"

class AnomalyDetector(models.Model):
    scenario = models.ForeignKey(Scenario, on_delete=models.CASCADE, null=True, blank=True)
    execution = models.IntegerField(default=0)
    
    class Meta:
        db_table = "AnomalyDetector"

class ClassificationMetric(models.Model):
    detector = models.ForeignKey(AnomalyDetector, on_delete=models.CASCADE, null=True, blank=True)
    execution = models.IntegerField(default=0)
    model_name = models.CharField(max_length=255, default='model_name')
    accuracy = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    precision = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    recall = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    f1_score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    confusion_matrix = models.TextField(null=True, blank=True)
    date = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "ClassificationMetric"

class RegressionMetric(models.Model):
    detector = models.ForeignKey(AnomalyDetector, on_delete=models.CASCADE, null=True, blank=True)
    execution = models.IntegerField(default=0)
    model_name = models.CharField(max_length=255, default='model_name')
    mse = models.DecimalField(max_digits=10, decimal_places=5, null=True, blank=True)
    rmse = models.DecimalField(max_digits=10, decimal_places=5, null=True, blank=True)
    mae = models.DecimalField(max_digits=10, decimal_places=5, null=True, blank=True)
    r2 = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    msle = models.DecimalField(max_digits=10, decimal_places=5, null=True, blank=True)
    date = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "RegressionMetric"

class AnomalyMetric(models.Model):
    detector = models.ForeignKey(AnomalyDetector, on_delete=models.CASCADE)
    execution = models.IntegerField()
    model_name = models.CharField(max_length=255, default='model_name')
    feature_name = models.CharField(max_length=255)
    anomalies = models.JSONField()
    date = models.DateTimeField(auto_now_add=True)
    production = models.BooleanField(default=False)

    anomaly_image = models.ImageField(upload_to='anomaly_images/', null=True, blank=True)
    global_shap_image = models.ImageField(upload_to='shap_global_images/', null=True, blank=True)
    local_shap_image = models.ImageField(upload_to='shap_local_images/', null=True, blank=True)
    global_lime_image = models.ImageField(upload_to='lime_global_images/', null=True, blank=True)
    local_lime_image = models.ImageField(upload_to='lime_local_images/', null=True, blank=True)

    class Meta:
        db_table = "AnomalyMetric"
