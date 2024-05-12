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
import homeassistant.util.color as color_util
from homeassistant.helpers.entity_platform import AddEntitiesCallback
import logging

from .const import DOMAIN, Components, Adjustments

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


def map_range(value, from_lower, from_upper, to_lower=0, to_upper=255, reverse=False):
    """Map a value in one range to another."""
    if reverse:
        value = from_upper - value + from_lower
    mapped = (value - from_lower) * (to_upper - to_lower) / (
        from_upper - from_lower
    ) + to_lower
    return round(min(max(mapped, to_lower), to_upper))


class HyperHDRLight(HyperHDR_MQTT_Entity, LightEntity):
    def __init__(self, hass, device) -> None:
        super().__init__(hass, device)
        self._instance = self.device.selected_instance
        self._attr_color_mode = ColorMode.HS

    @property
    def name(self):
        return "Light"

    @property
    def is_on(self):
        return self.device.components.leddevice

    @property
    def brightness(self):
        """Return the brightness of the light."""
        if self.device.brightness is not None:
            return map_range(self.device.brightness, 0, 100)
        return None

    @property
    def hs_color(self):
        """Return the hs color value."""
        if rgb := self.device.rgb_value:
            return color_util.color_RGB_to_hs(*rgb)
        return None

    @property
    def color_temp(self):
        """Return the color_temp of the light."""
        return None

    @property
    def supported_color_modes(self) -> set[ColorMode] | set[str] | None:
        """Flag supported color modes."""
        color_modes: set[ColorMode] = set()
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
        return self.device.light_effects

    @property
    def effect(self) -> str | None:
        """Return the current effect."""
        return self.device.active_effect

    async def async_turn_on(self, **kwargs):
        commands = []
        on_payload = await self.device.set_component(Components.LEDDEVICE, True, True)
        commands.append(on_payload)

        if effect := kwargs.get(ATTR_EFFECT):
            commands.append(await self.device.set_color_efect(effect, True))

        if hs_color := kwargs.get(ATTR_HS_COLOR):
            rgb_color = color_util.color_hs_to_RGB(*hs_color)
            commands.append(await self.device.set_color(rgb_color, True))

        if brightness := kwargs.get(ATTR_BRIGHTNESS):
            brightness = map_range(brightness, 0, 255, 0, 100)
            brightness_payload = await self.device.set_adjustment(
                Adjustments.BRIGHTNESS, brightness, True
            )
            commands.append(brightness_payload)

        await self.device.publish(commands, True)

    async def async_turn_off(self, **kwargs):
        await self.device.set_component(Components.LEDDEVICE, False)
