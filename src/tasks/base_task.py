from abc import ABC, abstractmethod
from nornir.core import Nornir

class BaseTask(ABC):
    @abstractmethod
    def propose(self, nr: Nornir) -> list:
        pass

    @abstractmethod
    def apply(self, nr: Nornir) -> list:
        pass
