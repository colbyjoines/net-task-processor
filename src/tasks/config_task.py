from .base_task import BaseTask
from nornir_netmiko.tasks import netmiko_send_config
from nornir_utils.plugins.functions import print_result
from nornir.core import Nornir
import logging


class ConfigTask(BaseTask):
    def execute(self, nr: Nornir) -> list:
        logging.info("Printing proposed configuration...")
        nr.run(task=self.print_proposed_configuration)
        input("Press Enter to apply the configuration...")
        logging.info("Applying configuration...")
        result = nr.run(task=self.apply_configuration)
        print_result(result)
        return self.collect_results(nr)

    def print_proposed_configuration(self, task) -> None:
        if "dot1x_interfaces" in task.host.keys():
            for interface in task.host["dot1x_interfaces"]:
                commands = self.generate_configuration_commands(interface)
                print(
                    f"Proposed configuration for {task.host.name} on interface {interface}:"
                )
                for command in commands:
                    print(command)

    def apply_configuration(self, task) -> None:
        if "dot1x_interfaces" in task.host.keys():
            for interface in task.host["dot1x_interfaces"]:
                commands = self.generate_configuration_commands(interface)
                task.run(task=netmiko_send_config, config_commands=commands)

    def generate_configuration_commands(self, interface: str) -> list:
        return [
            f"interface {interface}",
            " authentication order mab dot1x",
            " authentication priority mab dot1x",
        ]

    def collect_results(self, nr: Nornir) -> list:
        data = []
        for host in nr.inventory.hosts.values():
            if "dot1x_interfaces" in host.keys():
                for interface in host["dot1x_interfaces"]:
                    data.append({"host": host.name, "interface": interface})
        return data
