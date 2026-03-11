"""Shared device_info helpers for all Toniebox platforms.

Device hierarchy in Home Assistant:
  Haushalt [Hub/Service]
    ├── Toniebox (Gerät, model="Toniebox")
    │     entities: media_player, LED switch, mute switch, firmware sensor, last-seen sensor, refresh button
    └── Creative Tonie (Gerät, model="Creative Tonie")
          entities: media_player, chapter sensors, sort/clear buttons, private/live switches

All device_info dicts call these helpers so the hierarchy is defined in ONE place.
"""
from __future__ import annotations

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
    return {
        "identifiers": {(DOMAIN, f"tb_{tb_id}")},
        "name": tb.get("name", "Toniebox"),
        "manufacturer": "Boxine GmbH",
        "model": "Toniebox",
        "sw_version": fw.get("version") or fw.get("toniesVersion"),
        "via_device": (DOMAIN, f"hh_{hh_id}"),
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
