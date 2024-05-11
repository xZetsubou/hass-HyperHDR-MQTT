from . import HyperHDR_MQTT_Entity, HyperHDRMqtt_Data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.components.switch import DOMAIN, SwitchEntity
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.const import EntityCategory
import logging

from .const import DOMAIN, Components

_LOGGER = logging.getLogger(__name__)

INSTANCE = "Instance"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities,
) -> None:
    """Setup the Switches platform for HyperHDR MQTT."""
    ignore = (Components.LEDDEVICE,)
    data: HyperHDRMqtt_Data = hass.data[DOMAIN][entry.entry_id]
    for i, api in data.isntances_data.items():
        entities = []
        if i != 0:
            entities.append(HyperHDRSwitch(hass, api, INSTANCE))
        for comp, state in api.components.as_dict().items():
            if comp in ignore:
                continue
            if comp == Components.ALL and i != 0:
                continue

            entities.append(HyperHDRSwitch(hass, api, comp))

        async_add_entities(entities)


class HyperHDRSwitch(HyperHDR_MQTT_Entity, SwitchEntity):
    def __init__(self, hass, device, component: str) -> None:
        super().__init__(hass, device)
        self._instance = self.device.selected_instance
        self._component = component

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        if self.is_instance:
            return self.device.is_connected

        return super().available

    @property
    def is_instance(self) -> bool:
        return self._component == INSTANCE

    @property
    def entity_category(self) -> EntityCategory | None:
        """Return the category of the entity, if any."""
        if self.is_instance:
            return None

        return EntityCategory.CONFIG

    @property
    def name(self):
        return self._component.capitalize()

    @property
    def is_on(self):
        if self.is_instance:
            return self.device.state

        return self.device.components.as_dict().get(self._component)

    async def async_turn_on(self, **kwargs):
        if self.is_instance:
            return self.device.set_instance(True)

        await self.device.set_component(Components(self._component), True)

    async def async_turn_off(self, **kwargs):
        if self.is_instance:
            return self.device.set_instance(False)
        await self.device.set_component(Components(self._component), False)
