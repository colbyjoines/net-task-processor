from abc import ABC, abstractmethod
from typing import List

class BasePostProcessor(ABC):
    @abstractmethod
    def process(self, data: List[dict]) -> None:
        pass
