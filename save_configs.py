import os
from src.core.execution_framework import ExecutionFramework
from src.inventory.csv_inventory import CSVInventory
from src.tasks.save_configs_task import SaveConfigsTask
from src.core.post_processing import PrintPostProcessor
from src.filters.custom_filter import CustomFilter


def main() -> None:
    config_path = os.path.join("config", "config.yaml")
    secrets_path = os.path.join("config", "secrets.yaml")

    inventory_source = CSVInventory(config_path)

    task = SaveConfigsTask()

    strategy = ExecutionFramework(
        inventory_source=inventory_source,
        filter_obj=None,
        task=task,
        config_file=config_path,
        execution_mode="apply",
    )
    strategy.post_processors.append(PrintPostProcessor())
    strategy.propose_inventory()
    strategy.execute()


if __name__ == "__main__":
    main()
