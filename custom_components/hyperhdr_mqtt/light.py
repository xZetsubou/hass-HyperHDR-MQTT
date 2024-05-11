from . import HyperHDR_MQTT_Entity, HyperHDRMqtt_Data
from homeassistant.const import STATE_ON, STATE_OFF
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP,
    ATTR_EFFECT,
    ATTR_HS_COLOR,
    DOMAIN,
    LightEntityFeature,
    ColorMode,
    LightEntity,
)
from homeassistant.helpers.entity_platform import AddEntitiesCallback
import logging

from .const import DOMAIN, Components

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities,
) -> None:
    """Setup the lights platform for HyperHDR MQTT."""
    data: HyperHDRMqtt_Data = hass.data[DOMAIN][entry.entry_id]
    for i, api in data.isntances_data.items():
        async_add_entities([HyperHDRLight(hass, api)])


class HyperHDRLight(HyperHDR_MQTT_Entity, LightEntity):
    def __init__(self, hass, device) -> None:
        super().__init__(hass, device)
        self._instance = self.device.selected_instance

    @property
    def name(self):
        return "Light"

    @property
    def is_on(self):
        return self.device.components.leddevice

    @property
    def brightness(self):
        """Return the brightness of the light."""
        return None

    @property
    def hs_color(self):
        """Return the hs color value."""
        return None

    @property
    def color_temp(self):
        """Return the color_temp of the light."""
        return None

    @property
    def supported_color_modes(self) -> set[ColorMode] | set[str] | None:
        """Flag supported color modes."""
        color_modes: set[ColorMode] = set()
        color_modes.add(ColorMode.COLOR_TEMP)
        color_modes.add(ColorMode.HS)

        if not color_modes:
            return {ColorMode.ONOFF}

        return color_modes

    @property
    def supported_features(self) -> LightEntityFeature:
        """Flag supported features."""
        supports = LightEntityFeature(0)
        supports |= LightEntityFeature.EFFECT
        return supports

    @property
    def effect_list(self) -> list:
        """Return the list of supported effects for this light."""
        return self.device._light_effects

    async def async_turn_on(self, **kwargs):
        await self.device.set_component(Components.LEDDEVICE, True)

    async def async_turn_off(self, **kwargs):
        await self.device.set_component(Components.LEDDEVICE, False)
