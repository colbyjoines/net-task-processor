from .base_post_processor import BasePostProcessor
from typing import List
import pymongo

class MongoDBPostProcessor(BasePostProcessor):
    def __init__(self, uri: str, db_name: str, collection_name: str) -> None:
        self.client = pymongo.MongoClient(uri)
        self.db = self.client[db_name]
        self.collection = self.db[collection_name]

    def process(self, data: List[dict]) -> None:
        self.collection.insert_many(data)
