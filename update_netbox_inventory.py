import os
import logging
from nornir import InitNornir
from nornir.core.task import Task, Result
from nornir.core.configuration import Config
from src.core.execution_framework import ExecutionFramework
from src.inventory.csv_inventory import CSVInventory
from src.tasks.update_netbox_inventory import UpdateNetBoxInventoryTask
from src.filters.custom_filter import CustomFilter
from src.core.post_processing import PrintPostProcessor
from config.statics import site_id, switch_name


def test_credentials(task):
    # Simple task to test credentials
    return Result(host=task.host, result="Credentials valid", failed=False)


def main() -> None:
    config_path = os.path.join("config", "config.yaml")

    inventory_source = CSVInventory(config_path)
    switch_filter = {"name": switch_name}
    filter_config = CustomFilter()

    task = UpdateNetBoxInventoryTask()

    strategy = ExecutionFramework(
        inventory_source=inventory_source,
        filter_obj=filter_config,
        task=task,
        config_file=config_path,
        execution_mode="apply",
    )
    strategy.post_processors.append(PrintPostProcessor())
    strategy.execute()


if __name__ == "__main__":
    main()
