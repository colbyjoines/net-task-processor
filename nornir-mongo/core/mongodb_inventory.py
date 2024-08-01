# core/mongodb_inventory.py

from pymongo import MongoClient
from pydantic import BaseModel
from nornir.core.plugins.inventory import InventoryPlugin
from nornir.core.inventory import (
    Inventory,
    Groups,
    Defaults,
    Group,
    ParentGroups,
    ConnectionOptions,
)
from typing import Dict, Any, List, Callable, Optional, Type
from .host_extension import CustomHost


class MongoInventorySettings(BaseModel):
    mongo_uri: str
    db_name: str
    collection_name: str
    query: Optional[Dict[str, Any]] = None
    transformations: Optional[List[Callable[[Dict[str, Any]], Dict[str, Any]]]] = None
    extensions: Optional[List[Type]] = None  # List of host extension classes
    username: Optional[str] = None
    password: Optional[str] = None

    class Config:
        arbitrary_types_allowed = True


class MongoDBInventory(InventoryPlugin):
    def __init__(self, settings: Dict[str, Any], **kwargs):
        self.settings = settings
        self.mongo_uri = settings["mongo_uri"]
        self.db_name = settings["db_name"]
        self.collection_name = settings["collection_name"]
        self.query = settings.get("query", {})
        self.transformations = settings.get("transformations", [])
        self.extensions = settings.get("extensions", [])

        self.groups_data = {}
        self.defaults = Defaults()

        if "group_file" in kwargs:
            self._load_groups(kwargs["group_file"])
        if "defaults_file" in kwargs:
            self._load_defaults(kwargs["defaults_file"])

    def _load_groups(self, group_file: str):
        import ruamel.yaml

        yml = ruamel.yaml.YAML(typ="safe")
        with open(group_file, "r") as f:
            groups_dict = yml.load(f) or {}

        for n, g in groups_dict.items():
            self.groups_data[n] = Group(
                name=n,
                hostname=g.get("hostname"),
                port=g.get("port"),
                username=g.get("username"),
                password=g.get("password"),
                platform=g.get("platform"),
                data=g.get("data"),
                connection_options=self._get_connection_options(g),
                groups=g.get("groups", []),
                defaults=self.defaults,
            )

        for group in self.groups_data.values():
            group.groups = ParentGroups([self.groups_data[g] for g in group.groups])

    def _load_defaults(self, defaults_file: str):
        import ruamel.yaml

        yml = ruamel.yaml.YAML(typ="safe")
        with open(defaults_file, "r") as f:
            defaults_dict = yml.load(f) or {}

        self.defaults = Defaults(
            hostname=defaults_dict.get("hostname"),
            port=defaults_dict.get("port"),
            username=defaults_dict.get("username"),
            password=defaults_dict.get("password"),
            platform=defaults_dict.get("platform"),
            data=defaults_dict.get("data"),
            connection_options=self._get_connection_options(
                defaults_dict.get("connection_options", {})
            ),
        )

    def _get_connection_options(
        self, data: Dict[str, Any]
    ) -> Dict[str, ConnectionOptions]:
        options = {}
        for name, conn in data.items():
            options[name] = ConnectionOptions(
                hostname=conn.get("hostname"),
                port=conn.get("port"),
                username=conn.get("username"),
                password=conn.get("password"),
                platform=conn.get("platform"),
                extras=conn.get("extras"),
            )
        return options

    def load(self) -> Inventory:
        client = MongoClient(self.mongo_uri)
        db = client[self.db_name]
        collection = db[self.collection_name]

        hosts_data = {}
        groups = Groups(self.groups_data)

        for doc in collection.find(self.query):
            if self.transformations:
                for transform in self.transformations:
                    doc = transform(doc)

            host_name = doc.pop("name")
            group_names = doc.pop("groups", "").split(",")
            connection_options = self._get_connection_options(
                doc.pop("connection_options", {})
            )

            host_data = {
                "name": host_name,
                "hostname": doc.pop("hostname", ""),
                "username": doc.pop("username", ""),
                "password": doc.pop("password", ""),
                "platform": doc.pop("platform", ""),
                "port": doc.pop("port", None),
                "groups": ParentGroups(
                    [
                        self.groups_data[group_name]
                        if group_name in self.groups_data
                        else Group(name=group_name)
                        for group_name in group_names
                    ]
                ),
                "data": doc,
                "connection_options": connection_options,
                "defaults": self.defaults,
            }

            hosts_data[host_name] = CustomHost(**host_data, extensions=self.extensions)

        return Inventory(hosts=hosts_data, groups=groups, defaults=self.defaults)
