import logging
import os
import re
import random
import string
from dotenv import load_dotenv
from ipaddress import IPv4Interface, ip_network, ip_address
import pynetbox
import meraki

load_dotenv()


def is_valid_ip(ip):
    try:
        IPv4Interface(ip)
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


def get_or_create_site(nb, ip, network_name):
    ip_obj = ip_address(ip)
    prefixes = nb.ipam.prefixes.all()
    for prefix in prefixes:
        network = ip_network(prefix.prefix)
        if ip_obj in network:
            return prefix.site.name

    # If no matching site found, create a new site if the network name is valid
    if re.match(r"^[a-zA-Z]{2}\d$", network_name):
        site_data = {"name": network_name, "slug": network_name.lower()}
        new_site = nb.dcim.sites.create(site_data)
        return new_site.name
    return "Unknown"


class UpdateNetBoxWAPInventory:
    def __init__(self):
        self.nb = pynetbox.api(
            os.getenv("NETBOX_API_URL"), token=os.getenv("NETBOX_API_TOKEN")
        )
        self.meraki_dashboard = meraki.DashboardAPI(
            api_key=os.getenv("MERAKI_API_KEY"), output_log=False
        )

    def get_meraki_devices(self):
        orgs = self.meraki_dashboard.organizations.getOrganizations()
        org_id = [
            org["id"] for org in orgs if org["name"] == os.getenv("MERAKI_ORG_NAME")
        ][0]
        return self.meraki_dashboard.organizations.getOrganizationDevices(org_id)

    def update_netbox_inventory(self):
        logging.info("Updating NetBox inventory with Meraki WAPs...")

        # Get Meraki devices
        meraki_devices = self.get_meraki_devices()

        cisco_manufacturer = self.nb.dcim.manufacturers.get(name="Cisco", slug="cisco")

        for device in meraki_devices:
            if device["model"].startswith("MR"):
                hostname = device["name"]
                ip_address = device.get("lanIp")
                if not ip_address:
                    logging.warning(f"Device {hostname} has no LAN IP. Skipping.")
                    continue

                network_name = device["networkId"]
                site_name = get_or_create_site(self.nb, ip_address, network_name)
                device_role = 3
                device_type_model = device["model"]

                devices = list(self.nb.dcim.devices.all())
                matching_device = next(
                    (dev for dev in devices if dev.name.lower() == hostname.lower()),
                    None,
                )

                if device["model"] not in [
                    platform.model
                    for platform in list(
                        self.nb.dcim.device_types.filter(
                            manufacturer_id=cisco_manufacturer.id
                        )
                    )
                ]:
                    device_type_data = {
                        "manufacturer": cisco_manufacturer.id,
                        "slug": generate_slug(
                            raw_string=device["model"], prefix=cisco_manufacturer.name
                        ),
                        "model": device["model"],
                    }
                    device_type_query = self.nb.dcim.device_types.create(
                        device_type_data
                    )
                else:
                    device_type_query = self.nb.dcim.device_types.get(
                        model=device["model"]
                    )

                if matching_device is None:
                    device_data = {
                        "name": hostname,
                        "role": device_role,
                        "device_type": device_type_query.id,
                        "slug": generate_slug(
                            raw_string=device["name"], prefix=cisco_manufacturer.name
                        ),
                    }
                    if site_name:
                        device_data["site"] = {"name": site_name}

                    device_nb = self.nb.dcim.devices.create(device_data)
                else:
                    device_nb = matching_device

                data = {
                    "device": device_nb.id,
                    "name": hostname,
                    "role": device_role,
                    "manufacturer": {
                        "name": cisco_manufacturer.name,
                        "slug": cisco_manufacturer.slug,
                    },
                    "part_id": device["model"],
                    "serial": device["serial"],
                    "asset_tag": device["mac"],
                }

                if device["model"] not in [
                    platform.model
                    for platform in self.nb.dcim.device_types.filter(
                        manufacturer_id=cisco_manufacturer.id
                    )
                ]:
                    device_type_data = {
                        "manufacturer": cisco_manufacturer.id,
                        "slug": generate_slug(
                            raw_string=device["model"], prefix=cisco_manufacturer.name
                        ),
                        "model": device["model"],
                    }
                    new_device_type = self.nb.dcim.device_types.create(device_type_data)
                    device_nb.device_type = new_device_type.id
                else:
                    device_type_data = {
                        "manufacturer_id": cisco_manufacturer.id,
                        "model": device["model"],
                    }
                    existing_device_type = self.nb.dcim.device_types.get(
                        model=device["model"]
                    )
                    slug = generate_slug(
                        raw_string=device["model"], prefix=cisco_manufacturer.name
                    )
                    if existing_device_type.slug != slug:
                        existing_device_type.slug = slug
                        existing_device_type.save()

                device_nb.save()

                print(f"Created/Updated device {device_nb.name} with data: {data}")

                # Process interfaces and IPs for the device
                interfaces = {
                    "eth0": {
                        "ip_address": ip_address,
                        "description": "Primary interface",
                        "mac_address": device.get("mac"),
                    }
                }
                print(interfaces)

                for interface_name, interface_details in interfaces.items():
                    try:
                        vrf = self.nb.ipam.vrfs.get(name="Global")
                        interface_data = {
                            "device": device_nb.id,
                            "name": interface_name,
                            "type": "virtual",
                            "vrf": vrf.id,
                        }
                        existing_interface = self.nb.dcim.interfaces.get(
                            device_id=device_nb.id, name=interface_name
                        )
                        if existing_interface:
                            interface = existing_interface
                        else:
                            interface = self.nb.dcim.interfaces.create(interface_data)

                        ip_address_with_prefix = f"{interface_details['ip_address']}/16"
                        interface.description = interface_details.get(
                            "description", None
                        )
                        interface.mac_address = interface_details.get(
                            "mac_address", None
                        )
                        interface.save()

                        existing_ip_address = self.nb.ipam.ip_addresses.get(
                            address=ip_address_with_prefix
                        )
                        if is_valid_ip(ip_address_with_prefix):
                            if existing_ip_address:
                                netbox_ip = self.nb.ipam.ip_addresses.get(
                                    address=ip_address_with_prefix
                                )
                            else:
                                netbox_ip = self.nb.ipam.ip_addresses.create(
                                    address=ip_address_with_prefix
                                )

                            network_obj = IPv4Interface(ip_address_with_prefix)
                            ipam_prefix = self.nb.ipam.prefixes.get(
                                prefix=str(network_obj.network)
                            )
                            if not ipam_prefix:
                                data = {
                                    "site": device_nb.site.id,
                                    "prefix": str(network_obj.network),
                                    "vrf": vrf.id,
                                }
                                if network_obj.network.prefixlen > 30:
                                    data["role"] = self.nb.ipam.roles.get(
                                        name="Transit Network"
                                    ).id

                                self.nb.ipam.prefixes.create(data)
                            else:
                                ipam_prefix.site = device_nb.site.id
                                ipam_prefix.vrf = vrf.id
                                ipam_prefix.save()

                            netbox_ip.assigned = True
                            netbox_ip.vrf = vrf.id
                            netbox_ip.device_id = device_nb.id
                            netbox_ip.device = device_nb.name
                            netbox_ip.primary_ip = interface.id
                            netbox_ip.primary_ip4 = interface.id
                            netbox_ip.assigned_object_type = "dcim.interface"
                            netbox_ip.assigned_object_id = interface.id
                            netbox_ip.save()
                            device_nb.primary_ip = netbox_ip.id
                            device_nb.primary_ip4 = netbox_ip.id
                            device_nb.save()

                    except Exception as e:
                        logging.error(
                            f"Error processing interface {interface_name}: {e}"
                        )
