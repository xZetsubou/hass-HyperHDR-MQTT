"""The HyperHDR MQTT integration."""

from __future__ import annotations
import asyncio
from datetime import timedelta

import logging
from typing import NamedTuple
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, CALLBACK_TYPE
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from .mqtt import HyperHDRInstance, HyperHDRManger

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

# For your initial PR, limit it to 1 platform.
PLATFORMS: list[Platform] = [Platform.LIGHT, Platform.SWITCH]


class HyperHDRMqtt_Data(NamedTuple):
    """LocalTuya data stored in homeassistant data object."""

    isntances_data: dict[int, HyperHDRInstance]


async def reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up HyperHDR MQTT from a config entry."""
    _LOGGER.info(f"Set up HyperHDR MQTT integration")
    hass.data.setdefault(DOMAIN, {})
    instances_data: dict[int, HyperHDRInstance] = {}

    manager = HyperHDRManger(entry.data)
    await manager.async_connect()
    if manager.connected:
        instance = manager.instances
        for i, v in instance.items():
            instances_data[i] = HyperHDRInstance(entry.data, i, manager)
        manager.instances_manager = instances_data
    else:
        raise CannotConnect("Cannot connect MQTT Broker")

    connect = [
        asyncio.create_task(device.instance_connect())
        for device in instances_data.values()
    ]
    await asyncio.wait(connect)

    hass.data[DOMAIN][entry.entry_id] = HyperHDRMqtt_Data(instances_data)
    # await hass.config_entries.async_forward_entry_setups(entry, Platform.LIGHT)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Reload entry when its updated
    entry.async_on_unload(entry.add_update_listener(reload_entry))
    reconnectTask(hass, entry)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    data: HyperHDRMqtt_Data = hass.data[DOMAIN][entry.entry_id]
    for i, dev in data.isntances_data.items():
        dev.disconnect()
        dev.manager.disconnect()

    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


def reconnectTask(hass: HomeAssistant, entry: ConfigEntry):
    """Add a task to reconnect to the devices if is not connected [interval: RECONNECT_INTERVAL]"""
    data: HyperHDRMqtt_Data = hass.data[DOMAIN][entry.entry_id]

    async def _async_reconnect(now):
        """Try connecting to devices not already connected to."""
        tasks = []
        for instance, dev in data.isntances_data.items():
            if not dev.connected:
                tasks.append(asyncio.create_task(dev.instance_connect()))
                await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)

    # Add unsub callbeack in unsub_listeners object.
    entry.async_on_unload(
        async_track_time_interval(hass, _async_reconnect, timedelta(seconds=5))
    )


class HyperHDR_MQTT_Entity(Entity):
    """HyperHDR MQTT Entity"""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, hass: HomeAssistant, device: HyperHDRInstance) -> None:
        self.device = device
        self._instance = self.device.selected_instance
        self._hass = hass

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to hass.

        To be extended by integrations.
        """
        signal = f"hyperhdr_mqtt_{self.device._topic}_{self._instance}"

        def dispatch_update_states():
            async_dispatcher_send(self._hass, signal)

        self.device.update_callback = dispatch_update_states

        self.async_on_remove(
            async_dispatcher_connect(self.hass, signal, self.device_update)
        )

    def device_update(self):
        self.schedule_update_ha_state()

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self.device.state

    @property
    def unique_id(self) -> str | None:
        return f"{self.device._topic}_{self._instance}_{self.name.lower()}"

    @property
    def device_info(self) -> dict:
        return DeviceInfo(
            name=self.device.name,
            model=f"Instance: {self._instance}",
            manufacturer="HyperHDR",
            identifiers={(DOMAIN, f"{self.device._topic}_{self._instance}")},
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
