import os
from src.core.execution_framework import ExecutionFramework
from src.inventory.csv_inventory import CSVInventory
from src.filters.custom_filter import CustomFilter
from src.tasks.bounce_ports_task import BouncePortsTask
from src.core.post_processing import PrintPostProcessor
from config.statics import site_id, switch_name


def main() -> None:
    config_path = os.path.join("config", "config.yaml")
    secrets_path = os.path.join("config", "secrets.yaml")

    inventory_source = CSVInventory(config_path)

    filter_config = CustomFilter(
        {"site_id": site_id, "function": "access_switch", "name": switch_name}
    )

    task = BouncePortsTask()

    strategy = ExecutionFramework(
        inventory_source=inventory_source,
        filter_obj=filter_config,
        task=task,
        config_file=config_path,
        execution_mode="proposal",
    )
    strategy.post_processors.append(PrintPostProcessor())
    strategy.propose_inventory()
    strategy.execute()


if __name__ == "__main__":
    main()
