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

class Scenario(models.Model):
    name = models.CharField(max_length=255, null=False, blank=True, default="Scenario name")
    user = models.ForeignKey('accounts.CustomUser', on_delete=models.CASCADE) 
    design = models.JSONField()
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    status = models.CharField(max_length=255, default='Draft')
    date = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "Scenario"