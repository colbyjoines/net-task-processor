# custom_host.py
from typing import List, Callable, Any
from nornir.core.inventory import Host


# host_extension.py
from abc import ABC, abstractmethod
from nornir.core.inventory import Host
from nornir.core.task import Task, Result
from nornir_netmiko.tasks import netmiko_send_command
from nornir.core.exceptions import ConnectionException


# custom_host.py
from typing import List, Callable, Any, Dict
from nornir.core.inventory import Host
from host_extension import HostExtension


# core/custom_host.py

from nornir.core.inventory import Host
from .host_extension import HostExtension
from typing import List, Dict, Any, Callable


class CustomHost(Host):
    def __init__(
        self, *args, extensions: List[Callable[[Host], HostExtension]] = None, **kwargs
    ):
        super().__init__(*args, **kwargs)
        self.extensions = extensions or []
        self.extension_map = self._initialize_extensions()

    def _initialize_extensions(self) -> Dict[str, HostExtension]:
        extension_map = {}
        for extension_cls in self.extensions:
            extension = extension_cls(self)
            extension_map[extension.name] = extension
        return extension_map

    def run_extension(self, name: str, **kwargs):
        if name in self.extension_map:
            return self.extension_map[name].execute(**kwargs)
        else:
            raise ValueError(f"Extension {name} not found in host {self.name}")


# host_extension.py
from abc import ABC, abstractmethod
from nornir.core.inventory import Host
from nornir.core.task import Task


# core/host_extension.py

from nornir.core.inventory import Host
from abc import ABC, abstractmethod
from typing import Any


class HostExtension(ABC):
    def __init__(self, host: Host):
        self.host = host

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the unique name of the extension."""
        pass

    @abstractmethod
    def execute(self, **kwargs) -> Any:
        """Execute the extension logic."""
        pass


class NetmikoCommandExtension(HostExtension):
    def __init__(self, host: Host, command: str):
        super().__init__(host)
        self.command = command

    def execute(self, task: Task) -> Result:
        """
        Execute a Netmiko command using the host's connection options.

        Returns:
            Result: The result of the command execution.
        """
        try:
            return task.run(task=netmiko_send_command, command_string=self.command)
        except ConnectionException as e:
            return Result(host=self.host, failed=True, exception=e)
