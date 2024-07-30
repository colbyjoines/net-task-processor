from .base_task import BaseTask
from nornir_netmiko.tasks import netmiko_save_config
from nornir_utils.plugins.functions import print_result
from nornir.core import Nornir
from typing import List, Dict, Any
import logging


class SaveConfigsTask(BaseTask):
    def propose(self, nr: Nornir) -> List[Dict[str, Any]]:
        logging.info("Proposal does not apply")
        ...
        return self.collect_results(nr)

    def apply(self, nr: Nornir) -> List[Dict[str, Any]]:
        logging.info("Applying configuration save...")
        result = nr.run(task=netmiko_save_config)
        print_result(result)
        return self.collect_results(nr)

    def print_proposed_configuration(self, nr: Nornir) -> None:
        for host in nr.inventory.hosts.values():
            if "running_config" in host.keys():
                print(f"Proposed configuration for {host.name}:")
                print(host["running_config"])

    def collect_results(self, nr: Nornir) -> List[Dict[str, Any]]:
        data = []
        for host in nr.inventory.hosts.values():
            if "running_config" in host.keys():
                data.append(
                    {"host": host.name, "running_config": host["running_config"]}
                )
        return data
