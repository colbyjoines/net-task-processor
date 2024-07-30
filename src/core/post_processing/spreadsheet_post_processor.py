from .base_post_processor import BasePostProcessor
from typing import List
import pandas as pd

class SpreadsheetPostProcessor(BasePostProcessor):
    def __init__(self, filename: str) -> None:
        self.filename = filename

    def process(self, data: List[dict]) -> None:
        df = pd.DataFrame(data)
        df.to_excel(self.filename, index=False)
