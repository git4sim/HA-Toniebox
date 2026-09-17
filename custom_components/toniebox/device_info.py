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


def _via_device_id(coordinator, parent_identifier: str) -> dict:
    """Resolve a parent device's via-device kwarg for DeviceInfo.

    HA 2026.9 deprecated DeviceInfo's "via_device" (an identifiers tuple,
    resolved for us) in favor of "via_device_id" (the parent's actual
    DeviceEntry.id, which we must resolve ourselves); via_device is removed
    in 2027.8.0. async_get_device_by_identifier only exists on 2026.8+, so
    fall back to the old key on older HA.
    """
    dev_reg = dr.async_get(coordinator.hass)
    if hasattr(dev_reg, "async_get_device_by_identifier"):
        parent = dev_reg.async_get_device_by_identifier(
            (DOMAIN, parent_identifier), coordinator.entry.entry_id
        )
        return {"via_device_id": parent.id} if parent else {}
    return {"via_device": (DOMAIN, parent_identifier)}


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
        **_via_device_id(coordinator, f"hh_{hh_id}"),
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
        **_via_device_id(coordinator, f"tb_{tb_id}"),
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
        **_via_device_id(coordinator, f"hh_{hh_id}"),
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
        **_via_device_id(coordinator, f"hh_{hh_id}"),
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
        **_via_device_id(coordinator, f"hh_{hh_id}"),
    }
