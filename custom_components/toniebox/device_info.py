"""Shared device_info helpers for all Toniebox platforms.

Device hierarchy in Home Assistant:
  Haushalt [Hub/Service]
    ├── Toniebox (Gerät, model="Toniebox")
    │     ├── entities: media_player, LED switch, mute switch, firmware sensor, last-seen sensor, refresh button
    │     └── Headphones (Sub-Device, model="Tonie Headphones")
    │           entities: connected binary_sensor, battery sensor, color sensor
    └── Creative Tonie (Gerät, model="Creative Tonie")
          entities: media_player, chapter sensors, sort/clear buttons, private/live switches

All device_info dicts call these helpers so the hierarchy is defined in ONE place.
"""
from __future__ import annotations

from homeassistant.helpers import device_registry as dr

from .const import DOMAIN


def household_device_info(coordinator, hh_id: str) -> dict:
    """Hub device — the Toniebox cloud household."""
    hh = coordinator.data.get("households", {}).get(hh_id, {})
    return {
        "identifiers": {(DOMAIN, f"hh_{hh_id}")},
        "name": hh.get("name", "Toniebox Haushalt"),
        "manufacturer": "Boxine GmbH",
        "model": "Toniebox Cloud",
        "entry_type": "service",
    }


def toniebox_device_info(coordinator, hh_id: str, tb_id: str) -> dict:
    """Physical Toniebox speaker — child of household hub."""
    tb = (
        coordinator.data
        .get("households", {}).get(hh_id, {})
        .get("tonieboxes", {}).get(tb_id, {})
    )
    fw = tb.get("firmware", {})
    mac = tb.get("mac_address")
    sw_version = (
        tb.get("firmware_version")
        or fw.get("version")
        or fw.get("toniesVersion")
    )
    info = {
        "identifiers": {(DOMAIN, f"tb_{tb_id}")},
        "name": tb.get("name", "Toniebox"),
        "manufacturer": "Boxine GmbH",
        "model": "Toniebox",
        "serial_number": tb_id,
        "sw_version": sw_version,
        "via_device": (DOMAIN, f"hh_{hh_id}"),
    }
    if mac:
        info["connections"] = {(dr.CONNECTION_NETWORK_MAC, mac.lower())}
    return info


def headphones_device_info(coordinator, hh_id: str, tb_id: str) -> dict:
    """Headphones sub-device — child of the Toniebox it is connected to."""
    tb = (
        coordinator.data
        .get("households", {}).get(hh_id, {})
        .get("tonieboxes", {}).get(tb_id, {})
    )
    tb_name = tb.get("name", "Toniebox")
    return {
        "identifiers": {(DOMAIN, f"tb_{tb_id}_headphones")},
        "name": f"{tb_name} Headphones",
        "manufacturer": "Boxine GmbH",
        "model": "Tonie Headphones",
        "via_device": (DOMAIN, f"tb_{tb_id}"),
    }


def creative_tonie_device_info(coordinator, hh_id: str, t_id: str) -> dict:
    """Creative Tonie figurine — child of household hub."""
    tonie = (
        coordinator.data
        .get("households", {}).get(hh_id, {})
        .get("creativetonies", {}).get(t_id, {})
    )
    return {
        "identifiers": {(DOMAIN, f"ct_{t_id}")},
        "name": tonie.get("name", "Creative Tonie"),
        "manufacturer": "Boxine GmbH",
        "model": "Creative Tonie",
        "via_device": (DOMAIN, f"hh_{hh_id}"),
    }


def disc_device_info(coordinator, hh_id: str, disc_id: str) -> dict:
    """Content Disc — child of household hub."""
    disc = (
        coordinator.data
        .get("households", {}).get(hh_id, {})
        .get("discs", {}).get(disc_id, {})
    )
    return {
        "identifiers": {(DOMAIN, f"disc_{disc_id}")},
        "name": disc.get("name", "Content Disc"),
        "manufacturer": "Boxine GmbH",
        "model": "Content Disc",
        "via_device": (DOMAIN, f"hh_{hh_id}"),
    }


def content_tonie_device_info(coordinator, hh_id: str, ct_id: str) -> dict:
    """Content Tonie figurine — child of household hub."""
    ct = (
        coordinator.data
        .get("households", {}).get(hh_id, {})
        .get("contenttonies", {}).get(ct_id, {})
    )
    return {
        "identifiers": {(DOMAIN, f"content_{ct_id}")},
        "name": ct.get("name", "Content Tonie"),
        "manufacturer": "Boxine GmbH",
        "model": "Content Tonie",
        "via_device": (DOMAIN, f"hh_{hh_id}"),
    }
