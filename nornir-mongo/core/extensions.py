# netmiko_command_extension.py
from nornir_netmiko.tasks import netmiko_send_command
from nornir.core.task import Result
from nornir.core.exceptions import ConnectionException
from host_extension import HostExtension
from nornir.core.inventory import Host
from nornir.core.task import Task

# core/netmiko_command_extension.py

from .host_extension import HostExtension
from nornir_netmiko.tasks import netmiko_send_command
from nornir.core.task import Result
from typing import Any


class NetmikoCommandExtension(HostExtension):
    @property
    def name(self) -> str:
        return "netmiko_command"

    def execute(self, command: str, **kwargs) -> Any:
        if not self.host.platform:
            raise ValueError("Platform must be specified to run Netmiko commands.")

        task = kwargs.get("task")
        if not task:
            raise ValueError("A valid Nornir task must be provided.")

        result = task.run(task=netmiko_send_command, command_string=command)

        return result
