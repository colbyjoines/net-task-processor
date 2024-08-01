# src/tasks/update_netbox_inventory_task.py

import logging
import os
import random
import string
import re
from dotenv import load_dotenv
import meraki
from nornir.core.task import Task, Result
from nornir_netmiko.tasks import netmiko_send_command
from nornir_utils.plugins.functions import print_result
from ntc_templates.parse import parse_output
from netutils.interface import canonical_interface_name
from netutils.ip import ipaddress_interface
from ipaddress import IPv4Interface
import pynetbox
from .base_task import BaseTask

load_dotenv()


def is_valid_ip(ip):
    try:
        ipaddress_interface(ip, "version")
        return True
    except ValueError:
        return False


def generate_slug(raw_string, prefix):
    pattern = r"[^-a-zA-Z0-9_]"
    converted = re.sub(pattern, "_", raw_string)
    return (f"{prefix}-{converted}").lower()


def generate_unique_string(min_length=1, max_length=100):
    allowed_chars = string.ascii_letters + string.digits + "-_"
    length = random.randint(min_length, max_length)
    return "".join(random.choice(allowed_chars) for _ in range(length))


class UpdateNetBoxInventoryTask(BaseTask):
    def __init__(self):
        self.nb = pynetbox.api(
            os.getenv("NETBOX_API_URL"), token=os.getenv("NETBOX_API_TOKEN")
        )

    def propose(self, nr):
        logging.info("Proposing NetBox inventory update...")
        result = nr.run(task=self.update_netbox_inventory)
        print_result(result)
        self.print_proposed_changes(nr)
        return self.collect_results(nr)

    def apply(self, nr):
        logging.info("Applying NetBox inventory update...")
        result = nr.run(task=self.update_netbox_inventory)
        # print_result(result)
        return self.collect_results(nr)

    def update_netbox_inventory(self, task: Task) -> Result:
        hostname = task.host.name
        site = task.host.data.get("site_id")
        device_type = task.host.data.get("device_type")
        device_role = task.host.data.get("function")
        device_role = "Access Switch"

        print(task.host.data)

        if not all([site, device_type, device_role]):
            return Result(
                host=task.host,
                result="Missing required host information: site, device_type, or device_role.",
                failed=True,
            )

        try:
            # Discover interfaces and IPs
            interfaces = self.discover_interfaces(task)
            vrfs = self.discover_vrfs(task)
            version_info = self.show_version(task)

            cisco_manufacturer = self.nb.dcim.manufacturers.get(
                name="Cisco", slug="cisco"
            )

            devices = list(self.nb.dcim.devices.all())
            matching_device = next(
                (
                    device
                    for device in devices
                    if device.name.lower() == hostname.lower()
                ),
                None,
            )

            if matching_device is None:
                device_data = {
                    "name": hostname,
                    "site": {"name": site},
                    "device_type": {
                        "model": "C9300L-48P-4G",
                        "manufacturer": cisco_manufacturer.id,
                    },
                    "role": {"name": device_role},
                }
                device = self.nb.dcim.devices.create(device_data)
            else:
                device = matching_device

            cisco_manufacturer = self.nb.dcim.manufacturers.get(
                name="Cisco", slug="cisco"
            )
            platforms = [
                platform.model
                for platform in list(
                    self.nb.dcim.device_types.filter(
                        manufacturer_id=cisco_manufacturer.id
                    )
                )
            ]

            stack_count = 1

            inventory_items = self.nb.dcim.inventory_items.all()
            asset_tags = [item["asset_tag"] for item in inventory_items]

            for version in version_info:
                for hardware, serial, mac_address in zip(
                    version["hardware"],
                    version["serial"],
                    version["mac_address"],
                ):
                    try:
                        data = {
                            "device": device.id,
                            "name": f"{device.name} (Stack Unit: {stack_count})",
                            "role": 1,
                            "manufacturer": {
                                "name": cisco_manufacturer.name,
                                "slug": cisco_manufacturer.slug,
                            },
                            "part_id": hardware,
                            "serial": serial,
                            "asset_tag": mac_address,
                        }

                        if hardware not in platforms:
                            device_type_data = {
                                "manufacturer": cisco_manufacturer.id,
                                "slug": generate_unique_string(),
                                "model": hardware,
                            }
                            new_device_type = self.nb.dcim.device_types.create(
                                device_type_data
                            )
                            device.device_type = new_device_type.id
                        else:
                            device_type_data = {
                                "manufacturer_id": cisco_manufacturer.id,
                                "model": hardware,
                            }
                            existing_device_type = self.nb.dcim.device_types.get(
                                model=hardware
                            )
                            slug = generate_slug(
                                raw_string=hardware, prefix=cisco_manufacturer.name
                            )
                            if existing_device_type.slug != slug:
                                existing_device_type.slug = slug
                                existing_device_type.save()
                        if (
                            str(device.device_type.model) not in version["hardware"]
                            or str(device.device_type.model) == "9300L"
                        ):
                            device.device_type = list(
                                self.nb.dcim.device_types.filter(
                                    model=hardware,
                                    manufacturer_id=cisco_manufacturer.id,
                                )
                            )[0].id
                            print("Incorrect device type identified")
                            device.save()

                        device.save()
                        device_type_query = self.nb.dcim.device_types.get(
                            model=hardware, manufacturer_id=cisco_manufacturer.id
                        )

                        device_type_slug = generate_slug(
                            hardware, cisco_manufacturer.name
                        )
                        if device_type_query.slug != device_type_slug:
                            device_type_query.slug = device_type_slug
                            device_type_query.save()
                            print(f"Updated device type slug of {hardware}")
                        print(
                            f"Created inventory item for stack unit {stack_count}: {data}"
                        )
                        stack_count += 1
                    except Exception as e:
                        logging.error(f"Error processing hardware {hardware}: {e}")

            for interface_name, interface_details in interfaces.items():
                try:
                    vrf = self.nb.ipam.vrfs.get(name="Global")
                    interface_data = {
                        "device": device.id,
                        "name": interface_name,
                        "type": "virtual",
                        "vrf": vrf.id,
                    }
                    existing_interface = self.nb.dcim.interfaces.get(
                        device_id=device.id, name=interface_name
                    )
                    if existing_interface:
                        interface = existing_interface
                    else:
                        interface = self.nb.dcim.interfaces.create(interface_data)

                    ip_address = f"{interface_details['ip_address']}/{interface_details['prefix_length']}"
                    interface.description = interface_details.get("description", None)
                    interface.mac_address = interface_details.get("mac_address", None)
                    interface.save()

                    existing_ip_address = self.nb.ipam.ip_addresses.get(
                        address=ip_address
                    )
                    if is_valid_ip(ip_address):
                        if existing_ip_address:
                            netbox_ip = self.nb.ipam.ip_addresses.get(
                                address=ip_address
                            )
                        else:
                            netbox_ip = self.nb.ipam.ip_addresses.create(
                                address=ip_address
                            )

                        network_obj = IPv4Interface(ip_address)
                        ipam_prefix = self.nb.ipam.prefixes.get(
                            prefix=str(network_obj.network)
                        )
                        if not ipam_prefix:
                            data = {
                                "site": device.site.id,
                                "prefix": str(network_obj.network),
                                "vrf": vrf.id,
                            }
                            if network_obj.network.prefixlen > 30:
                                data["role"] = self.nb.ipam.roles.get(
                                    name="Transit Network"
                                ).id

                            self.nb.ipam.prefixes.create(data)
                        else:
                            ipam_prefix.site = device.site.id
                            ipam_prefix.vrf = vrf.id
                            ipam_prefix.save()

                        netbox_ip.assigned = True
                        netbox_ip.vrf = vrf.id
                        netbox_ip.device_id = device.id
                        netbox_ip.device = device.name
                        netbox_ip.assigned_object_type = "dcim.interface"
                        netbox_ip.assigned_object_id = interface.id
                        netbox_ip.pa
                        if interface.name == "Vlan69":
                            netbox_ip.primary_ip = interface.id
                            netbox_ip.primary_ip4 = interface.id
                            netbox_ip.save()
                            device.primary_ip = netbox_ip.id
                            device.primary_ip4 = netbox_ip.id
                            device.save()
                        else:
                            print(netbox_ip.__dict__)
                            netbox_ip.save()
                except Exception as e:
                    logging.error(f"Error processing interface {interface_name}: {e}")

        except Exception as e:
            logging.error(f"Error updating device {hostname}: {e}")
            return Result(
                host=task.host,
                result=f"Failed to update device {hostname}: {e}",
                failed=True,
            )

        return Result(
            host=task.host,
            result=f"Device {hostname} and its interfaces have been added to NetBox.",
            failed=False,
        )

    def create_device(self, name, site, device_type, role):
        device_data = {
            "name": name,
            "site": {"name": site},
            "device_type": {"model": device_type},
            "role": {"name": role},
        }
        return self.nb.dcim.devices.create(device_data)

    def create_interface(self, device_id, name, interface_type):
        interface_data = {"device": device_id, "name": name, "type": interface_type}
        return self.nb.dcim.interfaces.create(interface_data)

    def discover_interfaces(self, task: Task) -> dict:
        vlan_result = task.run(
            task=netmiko_send_command, command_string="show interface"
        )
        parsed_vlan = parse_output(
            platform="cisco_ios",
            command="show interface",
            data=vlan_result.result,
        )
        return {
            entry["interface"]: entry
            for entry in parsed_vlan
            if entry["interface"].startswith("Vlan")
        }

    def discover_vrfs(self, task: Task) -> dict:
        result = task.run(task=netmiko_send_command, command_string="show vrf")
        parsed = parse_output(
            platform="cisco_ios",
            command="show vrf",
            data=result.result,
        )
        return {
            canonical_interface_name(interface): entry["name"]
            for entry in parsed
            for interface in entry["interfaces"]
        }

    def show_version(self, task: Task) -> dict:
        result = task.run(task=netmiko_send_command, command_string="show version")
        return parse_output(
            platform="cisco_ios",
            command="show version",
            data=result.result,
        )

    def print_proposed_changes(self, nr):
        for host in nr.inventory.hosts.values():
            print(f"Proposing to add device {host.name} to NetBox.")
            for interface, ip in host["interfaces"].items():
                print(f" - Interface {interface} with IP {ip}")

    def collect_results(self, nr):
        return [
            {"host": host.name, "status": "updated"}
            for host in nr.inventory.hosts.values()
        ]
