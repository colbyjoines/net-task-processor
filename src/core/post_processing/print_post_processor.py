from .base_post_processor import BasePostProcessor
from typing import List

class PrintPostProcessor(BasePostProcessor):
    def process(self, data: List[dict]) -> None:
        for item in data:
            print(item)
