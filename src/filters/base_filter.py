from abc import ABC, abstractmethod
from nornir.core import Nornir

class BaseFilter(ABC):
    @abstractmethod
    def apply(self, nr: Nornir) -> Nornir:
        pass
