from nornir.core import Nornir
from nornir_utils.plugins.functions import print_result
from typing import List, Optional, Dict, Any, Type, Literal
import yaml
from src.inventory.base_inventory import BaseInventory
from src.filters.base_filter import BaseFilter
from src.tasks.base_task import BaseTask
from src.core.post_processing.base_post_processor import BasePostProcessor


class ExecutionFramework:
    def __init__(
        self,
        inventory_source: Type[BaseInventory],
        task: Type[BaseTask],
        config_file: str,
        filter_obj: Optional[Type[BaseFilter]],
        execution_mode: Literal["proposal", "apply"] = None,
        post_processors: Optional[List[Type[BasePostProcessor]]] = None,
    ) -> None:
        self.inventory_source = inventory_source
        self.filter_obj = filter_obj
        self.task = task
        self.post_processors = post_processors if post_processors else []
        self.config = self.load_config(config_file)
        self.execution_mode = execution_mode

    def load_config(self, config_file: str) -> Dict[str, Any]:
        with open(config_file, "r") as f:
            return yaml.safe_load(f)

    def execute(self) -> None:
        nr: Nornir = self.inventory_source.get_inventory()
        if self.filter_obj:
            nr = self.filter_obj.apply(nr)
        if self.execution_mode == "proposal":
            result = self.task.propose(nr)
        elif self.execution_mode == "apply":
            result = self.task.apply(nr)
        print_result(result)
        self.run_post_processors(result)

    def propose_inventory(self) -> None:
        nr: Nornir = self.inventory_source.get_inventory()
        if self.filter_obj:
            nr = self.filter_obj.apply(nr)
        self.inventory_source.propose_inventory(nr)

    def run_post_processors(self, data: List[Dict[str, Any]]) -> None:
        for processor in self.post_processors:
            processor.process(data)
