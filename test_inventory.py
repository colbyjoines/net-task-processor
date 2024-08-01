# Load environment variables for sensitive data
from typing import Any, Dict

from dotenv import load_dotenv
from inventory.mongodb_inventory import (
    CommandOperation,
    MongoDBInventory,
    MongoInventorySettings,
)
from nornir import InitNornir
from nornir.core.plugins.inventory import InventoryPluginRegister
from nornir.core.task import Task
from nornir.core.inventory import ConnectionOptions
from nornir_utils.plugins.functions import print_result
from src.config import networking_settings

load_dotenv()


# Define a transformation function
def transform_function(doc: Dict[str, Any]) -> Dict[str, Any]:
    doc["hostname"] = doc["hostname"].upper()
    return doc


# Settings dictionary with an example query
settings_dict = {
    "mongo_uri": "mongodb://localhost:27017",
    "db_name": "network_inventory",
    "collection_name": "devices",
    "query": {"name": "KSQLAB-02-SW02"},  # Example query to filter active devices
    "transformations": [transform_function],  # List of transformation functions
    "operations": {
        "get_routes": CommandOperation(
            mongo_uri="mongodb://localhost:27017",
            db_name="test_data",
            collection_name="routing_tables",
        )
    },
    "username": "cjoines",
    "password": "Cosmo13579!!!",
}

# Create MongoInventorySettings object
settings = MongoInventorySettings(**settings_dict)

# Register the MongoDB inventory plugin
InventoryPluginRegister.register("MongoDBInventoryPlugin", MongoDBInventory)

# Initialize Nornir
nr = InitNornir(
    inventory={
        "plugin": "MongoDBInventoryPlugin",
        "options": {
            "settings": settings,
            "group_file": "inventory/groups.yaml",
            "defaults_file": "inventory/defaults.yaml",
        },
    },
    runner={
        "plugin": "threaded",
        "options": {
            "num_workers": 50,
        },
    },
)

# Set connection options for each host in the inventory
for host in nr.inventory.hosts.values():
    host.username = settings.username
    host.password = settings.password
    host.connection_options["netmiko"] = ConnectionOptions(
        hostname=host.hostname, username=settings.username, password=settings.password
    )


# Define your tasks
def save_config(task: Task):
    command = "show ip route"
    data = task.host.operations["get_routes"].execute(task, command)
    if task.host.operations["get_routes"].validate_data(data):
        task.host.operations["get_routes"].save_to_db(data)
    else:
        task.fail(f"Validation failed for host {task.host.name}")


# Run the task
nr.run(task=save_config)

print_result(nr)
