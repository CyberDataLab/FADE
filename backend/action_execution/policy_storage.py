import os
import json
from django.conf import settings

# Path to the file where alert policies are stored
POLICY_FILE = os.path.join(settings.BASE_DIR, "alert_policies.json")

def load_alert_policies():
    """
    Loads the current alert policies from the JSON file.

    If the file does not exist, it is created as an empty JSON object.

    Returns:
        dict: Dictionary of current alert policies.
    """
    # Create the file with an empty JSON object if it doesn't exist
    if not os.path.exists(POLICY_FILE):
        with open(POLICY_FILE, "w") as f:
            json.dump({}, f)
        return {}
    
    # Read and return the policies from the file
    with open(POLICY_FILE, "r") as f:
        return json.load(f)

def save_alert_policies(policies):
    """
    Saves the given alert policies dictionary to the JSON file.

    Args:
        policies (dict): Dictionary containing all alert policies.
    """
    with open(POLICY_FILE, "w") as f:
        json.dump(policies, f, indent=2)

def add_alert_policy(reason: str, threshold: int, target_email: str):
    """
    Adds or updates an alert policy with a threshold and target email.

    Args:
        reason (str): Identifier for the alert reason.
        threshold (int): Number of detections before triggering the alert.
        target_email (str): Email to notify when the threshold is exceeded.
    """
    policies = load_alert_policies()
    policies[reason] = {
        "threshold": threshold,
        "target": target_email
    }
    save_alert_policies(policies)

def delete_alert_policy(reason: str):
    """
    Deletes an existing alert policy by its reason key.

    Args:
        reason (str): Identifier of the alert policy to remove.
    """
    policies = load_alert_policies()
    if reason in policies:
        del policies[reason]
        save_alert_policies(policies)