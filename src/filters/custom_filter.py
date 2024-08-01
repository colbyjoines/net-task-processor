from nornir.core.filter import F
from .base_filter import BaseFilter
from nornir.core import Nornir


class CustomFilter(BaseFilter):
    def __init__(self, filter_criteria: dict = None) -> None:
        self.filter_criteria = filter_criteria

    def apply(self, nr: Nornir) -> Nornir:
        if not self.filter_criteria:
            return nr
        return nr.filter(F(**self.filter_criteria))
