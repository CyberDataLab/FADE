from django.db import models

# Create your models here.

class ActionController(models.Model):
    name = models.CharField(max_length=100, default='ActionController')

    def perform_action(self, action):
        pass

    def sync_action(self):
        pass

    def get_action_status(self, action_id):
        pass


class ActionReceiver(models.Model):
    name = models.CharField(max_length=100, default='ActionReceiver')

    def receive_action(self, action):
        pass


class PolicyManagement(models.Model):
    name = models.CharField(max_length=100, default='PolicyManagement')

    def get_policies(self):
        pass

    def is_action_allowed(self, action):
        pass

    def create_policy(self, policy):
        pass

    def sync_policies(self):
        pass


class ActionSync(models.Model):
    name = models.CharField(max_length=100, default='ActionSync')

    def check_sync_status(self):
        pass

    def sync(self):
        pass

    def verify_sync_actions(self):
        pass


class PerformAction(models.Model):
    name = models.CharField(max_length=100, default='PerformAction')

    def do_action(self, action):
        pass

    def get_action_status(self, action_id):
        pass
