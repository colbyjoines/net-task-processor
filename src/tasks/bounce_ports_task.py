import logging
import time
from typing import List, Any
from nornir_netmiko.tasks import netmiko_send_command, netmiko_send_config
from nornir_utils.plugins.functions import print_result
from ntc_templates.parse import parse_output
from netutils.interface import abbreviated_interface_name
from nornir.core import Nornir
from nornir.core.task import Task, Result
from .base_task import BaseTask


class BouncePortsTask(BaseTask):
    def propose(self, nr: Nornir) -> list:
        logging.info(
            "Getting interfaces on VLAN 21 with dot1x configured (Proposal)..."
        )
        nr.run(task=self.get_vlan_21_dot1x_interfaces)
        self.print_proposed_configuration(nr)
        return self.collect_results(nr)

    def apply(self, nr: Nornir) -> list:
        logging.info(
            "Applying configuration to bounce interfaces on VLAN 21 with dot1x..."
        )
        result = nr.run(task=self.get_vlan_21_dot1x_interfaces)
        nr.run(task=self.apply_configuration)
        print_result(result, failed=True)
        return self.collect_results(nr)

    def get_vlan_21_dot1x_interfaces(self, task: Task) -> Result:
        vlan_result = task.run(
            task=netmiko_send_command, command_string="show vlan brief"
        )
        vlan_interfaces = self.parse_vlan_output(vlan_result.result)

        dot1x_result = task.run(
            task=netmiko_send_command, command_string="show dot1x all"
        )
        dot1x_interfaces = self.parse_dot1x_output(dot1x_result.result)
        flat_vlan_interfaces = self.remove_outer_list(vlan_interfaces)
        task.host["bounce_ports"] = list(
            set(flat_vlan_interfaces) & set(dot1x_interfaces)
        )
        return Result(
            host=task.host,
            result=f"Identified bounce ports: {task.host['bounce_ports']}",
            failed=False,
        )

    def parse_vlan_output(self, output: str) -> List[str]:
        parsed_output = parse_output(
            platform="cisco_ios", command="show vlan brief", data=output
        )
        interfaces = []
        for entry in parsed_output:
            if entry["vlan_id"] == "21":
                interfaces.append(entry["interfaces"])
        return interfaces

    def parse_dot1x_output(self, output: str) -> List[str]:
        parsed_output = parse_output(
            platform="cisco_ios", command="show dot1x all", data=output
        )
        interfaces = [
            abbreviated_interface_name(entry["interface"])
            for entry in parsed_output
            if "interface" in entry
        ]
        return interfaces

    def remove_outer_list(self, nested_list: List[Any]) -> List[Any]:
        flat_list = []
        for item in nested_list:
            if isinstance(item, list):
                flat_list.extend(item)
            else:
                flat_list.append(item)
        return flat_list

    def collect_results(self, nr: Nornir) -> List[dict]:
        data = []
        for host in nr.inventory.hosts.values():
            if "bounce_ports" in host.keys():
                for interface in host["bounce_ports"]:
                    data.append({"host": host.name, "interface": interface})
        return data

    def generate_bounce_commands(self, interface: str) -> List[str]:
        return [f"interface {interface}", " shutdown", " no shutdown"]

    def print_proposed_configuration(self, nr: Nornir) -> None:
        for host in nr.inventory.hosts.values():
            if "bounce_ports" in host.keys():
                for interface in host["bounce_ports"]:
                    commands = self.generate_bounce_commands(interface)
                    print(
                        f"Proposed configuration for {host.name} on interface {interface}:"
                    )
                    for command in commands:
                        print(command)

    def apply_configuration(self, task: Task) -> Result:
        if "bounce_ports" in task.host.keys():
            for interface in task.host["bounce_ports"]:
                shutdown_commands = [
                    f"interface {interface}",
                    " shutdown",
                    " no shutdown",
                ]

                result = task.run(
                    task=netmiko_send_config, config_commands=shutdown_commands
                )
                print_result(result)
                time.sleep(3)
        return Result(
            host=task.host, result="Configuration applied successfully", failed=False
        )
