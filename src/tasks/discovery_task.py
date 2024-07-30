from .base_task import BaseTask
from nornir_netmiko.tasks import netmiko_send_command
from nornir_utils.plugins.functions import print_result
from ntc_templates.parse import parse_output
from nornir.core import Nornir
import logging

class DiscoveryTask(BaseTask):
    def execute(self, nr: Nornir) -> list:
        logging.info("Getting dot1x-enabled interfaces...")
        result = nr.run(task=self.get_dot1x_enabled_interfaces)
        print_result(result)
        return self.collect_results(nr)

    def get_dot1x_enabled_interfaces(self, task) -> None:
        result = task.run(task=netmiko_send_command, command_string="show dot1x all")
        parsed_output = result.result
        task.host["dot1x_interfaces"] = self.parse_dot1x_output(parsed_output)

    def parse_dot1x_output(self, output: str) -> list:
        parsed_output = parse_output(
            platform="cisco_ios", command="show dot1x all", data=output
        )
        interfaces = [entry["interface"] for entry in parsed_output if "interface" in entry]
        return interfaces

    def collect_results(self, nr: Nornir) -> list:
        data = []
        for host in nr.inventory.hosts.values():
            if "dot1x_interfaces" in host.keys():
                for interface in host["dot1x_interfaces"]:
                    data.append({
                        "host": host.name,
                        "interface": interface
                    })
        return data
