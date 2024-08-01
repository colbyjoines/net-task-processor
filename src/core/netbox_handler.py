# src/core/netbox_handler.py

import pynetbox
import os


class NetBoxHandler:
    def __init__(self, api_url, token):
        self.nb: pynetbox.api = pynetbox.api(api_url, token=token)

    def create_device(self, name, site, device_type, role="Access Switch"):
        device_data = {
            "name": name,
            "site": {"name": site},
            "device_type": {"model": device_type},
            "role": {"name": role},
        }
        device = self.nb.dcim.devices.create(device_data)
        return device

    def create_interface(self, device_id, name, interface_type):
        interface_data = {"device": device_id, "name": name, "type": interface_type}
        interface = self.nb.dcim.interfaces.create(interface_data)
        return interface

    def assign_ip_to_interface(self, interface_id, ip_address):
        ip_data = {
            "address": ip_address,
            "assigned_object_type": "dcim.interface",
            "assigned_object_id": interface_id,
        }
        ip = self.nb.ipam.ip_addresses.create(ip_data)
        return ip
