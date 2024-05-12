"""HANDLE MQTT FOR HyperHDR."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import StrEnum
import ssl
import time
from typing import Any, Self
from homeassistant.components.mqtt import (
    async_subscribe_connection_status,
    is_connected as mqtt_connected,
)
import asyncio
import logging
import json

from homeassistant.components.mqtt import client
from homeassistant.const import (
    CONF_HOST,
    CONF_USERNAME,
    CONF_PASSWORD,
    CONF_PORT,
)
from .const import (
    Components,
    Data,
    Errors,
    FRIENDLY_NAME,
    JSON_API,
    JSON_API_RESPONSE,
    CONF_PRIORITY,
    Path,
    Adjustments,
)

# from .const import(JSON_API,JSON_API_RESPONSE,PATH_INSTANCE,[Path.INFO], PATH_COMPONENTS, PATH_RUNNING)
INSTANCE_OFF = "Instance is OFF"

CONF_BROKER = "broker"
CONF_TOPIC = "topic"
CONF_CLIENT_ID = "client_id"

COMMAND = "command"
SERVERINFO = "serverinfo"
PIORITY = 1

STATES_UPDATE_INTERVAL = 2

CMD_UPDATEINFO = {COMMAND: SERVERINFO}
_LOGGER = logging.getLogger(__name__)


def change_index(instance):
    select_index = {
        "command": "instance",
        "subcommand": "switchTo",
        "instance": instance,
    }
    return select_index


def dumps_payload(payload):

    return str(payload).replace("'", '"').replace('"{', "{").replace('}"', "}")


class HyperHDRManger:
    def __init__(self, config: dict) -> None:
        self.loop = asyncio.get_running_loop()
        self._payload: dict = None
        self.instances: dict = {}
        self.instances_manager: dict[int, HyperHDRInstance] = {}

        # User config
        self._topic = config.get(CONF_TOPIC)
        self._topic_push = self._topic + "/" + JSON_API
        self._host = config.get(CONF_BROKER)
        self._port = int(config.get(CONF_PORT, 1883))
        self._user = config.get(CONF_USERNAME)
        self._password = config.get(CONF_PASSWORD)
        self._priority = int(config.get(CONF_PRIORITY))

        # Commands Responses.
        self._serverInfo: dict = {}

    def debug(self, message):
        _LOGGER.debug(f"{self._topic}: {message}")

    async def async_connect(self):
        self.debug(f"Connecting to {self._host}:{self._port}")

        _client = client.MqttClientSetup(
            {
                CONF_CLIENT_ID: f"HA-{self._topic}",
                CONF_TOPIC: self._topic,
                CONF_BROKER: self._host,
                CONF_PORT: self._port,
                CONF_USERNAME: self._user,
                CONF_PASSWORD: self._password,
            }
        ).client
        if self._user and self._password:
            _client.username_pw_set(username=self._user, password=str(self._password))

        _client.connect(self._host, self._port)
        _client.loop()
        _client.loop_start()
        _client.on_message = self.onMessage
        _client.on_connect = self.onConnect
        _client.on_disconnect = self.onDisconnect

        self.client = _client
        self.connected = _client.is_connected()
        self.subscribes()
        await self.serverInfo()

        if not self.connected:
            raise Exception("Couldn't connect.")

    async def serverInfo(self, instance=0) -> dict:
        async def getserverInfo():
            while True:
                payload = CMD_UPDATEINFO
                await self.publish(instance, payload, wait=True)

                if self._serverInfo != None:
                    break

        await asyncio.wait_for(getserverInfo(), 10)

    def subscribes(self) -> bool:
        if self.connected:
            topic = self._topic + "/" + JSON_API_RESPONSE
            self.client.subscribe(topic)
            self.debug(f"Subscribed to {topic} successfully")
            return True

    def onMessage(self, _client, userdata, msg) -> dict:
        payload = json.loads(msg.payload.decode())
        self._payload = payload.copy()
        if isinstance(payload, dict) and (result := payload.get("success")):
            return result
        if "success" in payload:
            return

        for cmd_response in payload:
            success, error = cmd_response.get("success"), cmd_response.get("error")
            command = cmd_response.get(COMMAND)
            if command == SERVERINFO:
                if error == Errors.NOT_READY:
                    # The instance is stopped
                    main_info = self._serverInfo[Path.INFO]
                    for instance_info in main_info[Path.INSTANCE]:
                        instance = instance_info.get(Path.INSTANCE)
                        if not main_info[Path.INSTANCE][instance][Path.RUNNING]:
                            if i_manager := self.instances_manager.get(instance):
                                i_manager._serverInfo = INSTANCE_OFF
                    return

                info = cmd_response[Path.INFO]
                i = info.get(Path.CURRENTINSTANCE, None)
                if i == 0:
                    self._serverInfo = cmd_response

                if i in self.instances_manager:
                    self.instances_manager[i]._serverInfo = cmd_response

                # Update instance.
                self.instances = {i[Path.INSTANCE]: i for i in info[Path.INSTANCE]}

    def onConnect(self, _client, userdata, flags, rc):
        self.debug(f"Has been connected successfully")

    def onDisconnect(self, _client, userdata, rc):
        self.disconnect()

    def disconnect(self):
        self.debug(f"Disconnecting from {self._host}:{self._port} and clean subs")
        self.client.unsubscribe(self._topic)
        self.client.disconnect()
        self.client.loop_stop()
        self.connected = None

    async def publish(self, instance, msg: dict, wait=False) -> bool:
        if isinstance(msg, list):
            payload = [change_index(instance)] + msg
        else:
            payload = [change_index(instance), msg]
        if self.connected:
            self._payload = None

            # Change selected index.
            async def publish_and_wait():
                self.client.publish(self._topic_push, dumps_payload(payload))
                while True:
                    await asyncio.sleep(0.2)
                    if self._payload is not None:
                        break

            # We will wait for any message for the next 3 seconds else we will return
            self.debug(f"Publishing: {dumps_payload(payload)}")
            task = asyncio.create_task(publish_and_wait())
            if wait:
                await asyncio.wait_for(task, 5)
        else:
            self.debug(f"Couldn't publish {payload} because broker isn't connected.")

    @property
    def is_connected(self) -> bool:
        return self.client and self.client.is_connected()


class HyperHDRInstance:

    def __init__(
        self,
        config: dict,
        instance=0,
        manager: HyperHDRManger = None,
    ) -> None:
        self.loop = asyncio.get_running_loop()

        self.components = ComponentsStates({})
        self._cache_components: dict = {}
        self._states_updater_task: asyncio.Task = None

        # Mqtt preapre configs.
        self._topic = config.get(CONF_TOPIC)
        self._topic_push = self._topic + "/" + JSON_API
        self.manager = manager
        self.connected = False

        self.time_last_publish = time.time()
        self._wait_for_new_states = False
        self.selected_instance: int = instance
        self.update_callback = None
        self.light_effects = []
        self.active_effect = ""
        self.rgb_value = ()
        self.brightness = None

    def debug(self, message):
        _LOGGER.debug(f"{self._topic} Instance: {self.selected_instance}: {message}")

    def warning(self, message):
        _LOGGER.warning(f"{self._topic} Instance: {self.selected_instance}: {message}")

    async def instance_connect(self):
        if self.manager.is_connected:
            try:
                await self.serverInfo(update=True)
                self._states_updater()
                self.connected = True
            except asyncio.TimeoutError:
                _LOGGER.error(
                    f"Instance {self.selected_instance}: There is no response from HyperHDR"
                )

    async def serverInfo(self, update=False) -> dict:
        # Payload requesting ServerINFO
        if update:
            self._serverInfo = None

            async def getserverInfo():
                payload = CMD_UPDATEINFO
                await self.publish(payload)
                while True:
                    await asyncio.sleep(0.01)
                    if self._serverInfo != None:
                        break

            try:
                await asyncio.wait_for(getserverInfo(), 3)
                if not self.connected:
                    self.connected = True
            except asyncio.TimeoutError:
                self.disconnect()
                await self.fetch_states(INSTANCE_OFF)
            await self.fetch_states(self._serverInfo)
        else:
            await self.fetch_states()

        return self._serverInfo

    async def fetch_states(self, payload=None):
        # Update device INFO
        updated = False
        data = payload or self._serverInfo
        if data == INSTANCE_OFF:
            self._cache_components = {}
            self._update()
            return

        if data and data.get(Path.INFO):
            info = data[Path.INFO]
            if not self.light_effects:
                self._effects(info[Path.EFFECTS])

            # Update RGB Colors
            if active_color := info.get("activeLedColor"):
                rgb_value = tuple(c for c in active_color[0]["RGB Value"])
                if self.rgb_value != rgb_value:
                    self.rgb_value = rgb_value
                    updated = True
            # Update Brightness
            if adjustments := info.get("adjustment"):
                brightness = adjustments[0]["brightness"]
                if self.brightness != brightness:
                    self.brightness = brightness
                    updated = True
            # Update The effect
            if activeeffects := info.get("activeEffects"):
                active_effect = activeeffects[0]["name"]
            else:
                active_effect = None
            if self.active_effect != active_effect:
                self.active_effect = active_effect
                updated = True

            components = {}
            for com in info[Path.COMPONENTS]:
                components[com[Data.NAME]] = com[Data.ENABLED]
                if self._cache_components.get(com[Data.NAME]) != com[Data.ENABLED]:
                    self._cache_components[com[Data.NAME]] = com[Data.ENABLED]
                    updated = True

            if components:
                self.components = ComponentsStates(components)

            if updated:
                self._update()
        return True

    async def set_component(self, component: Components, state, return_payload=False):
        payload = {
            "command": "componentstate",
            "componentstate": {"component": component.value, "state": state},
        }
        if return_payload:
            return json.dumps(payload)

        await self.publish(payload, True)

    async def set_instance(self, state):
        subcommand = "startInstance" if state else "stopInstance"
        payload = {
            "command": "instance",
            "subcommand": subcommand,
            "instance": self.selected_instance,
        }
        self._wait_for_new_states = True
        await self.manager.publish(0, payload)

    async def set_color_efect(self, effect, return_payload=False):
        payload = {
            "command": "effect",
            "effect": {"name": effect},
            "duration": 0,
            "priority": 64,
            "origin": "JSON API",
        }
        if return_payload:
            return json.dumps(payload)
        await self.publish(payload, True)

    async def set_color(self, color: tuple, return_payload=False):
        payload = {
            "command": "color",
            "color": color,
            "duration": 0,
            "priority": 64,
            "origin": "JSON API",
        }
        if return_payload:
            return json.dumps(payload)

        await self.publish(payload, True)

    async def set_adjustment(
        self, adjustment: Adjustments, value, return_payload=False
    ):
        payload = {
            "command": "adjustment",
            "adjustment": {"classic_config": False, adjustment.value: value},
        }
        if return_payload:
            return json.dumps(payload)

        await self.publish(payload, True)

    async def publish(self, payload: dict | list, wait_for_states=False):
        """Publish instance payload"""
        if wait_for_states:
            self._wait_for_new_states = True

        if isinstance(payload, list):
            await self.manager.publish(self.selected_instance, payload)
        else:
            await self.manager.publish(self.selected_instance, json.dumps(payload))

    def disconnect(self):
        self.debug(f"HyperHDR MQTT Disconnected")
        self.connected = False
        if self._states_updater_task:
            self._states_updater_task.cancel()
            self._states_updater_task = None

    def _effects(self, effects: list[dict[str, str]]):
        """Sort Effetcts"""
        classic_effects = []
        music_effects = []
        for e in effects:
            for _, value in e.items():
                if value.startswith("Music:"):
                    music_effects.append(value)
                else:
                    classic_effects.append(value)

        self.light_effects = classic_effects + music_effects

    def _states_updater(self):
        """Start the state updater to poll the states of instances"""

        async def start_loop():
            self.debug("Started state fetch loop")

            while True:
                try:
                    interval = STATES_UPDATE_INTERVAL
                    asyncio.create_task(self.serverInfo(True))
                    if self._wait_for_new_states:
                        interval = 0.45
                    await asyncio.sleep(interval)
                except (Exception, asyncio.CancelledError) as ex:
                    self.debug(f"State fetch loop stopped: {ex}")
                    break

        if self._states_updater_task is None:
            self._states_updater_task = self.loop.create_task(
                start_loop(), name=f"hyperhdr_mqtt_{self.selected_instance}"
            )

    def _update(self):
        if self.update_callback:
            self.update_callback()
            self._wait_for_new_states = False

    @property
    def name(self) -> str:
        return self.manager.instances[self.selected_instance].get(FRIENDLY_NAME)

    @property
    def state(self) -> str:
        if not self.connected:
            return False
        return self.manager.instances[self.selected_instance].get("running")

    @property
    def is_connected(self) -> bool:
        return self.manager.is_connected and self.connected


class DeviceUpdated(ABC):

    @abstractmethod
    def device_update(self, status):
        """Device updated status."""


@dataclass
class ComponentsStates:
    """Represent the components states."""

    data: dict[str, Any]

    def __post_init__(self) -> None:
        self.all: bool = self.data.get(Components.ALL, False)
        self.hdr: bool = self.data.get(Components.HDR, False)
        self.smoothing: bool = self.data.get(Components.SMOOTHING, False)
        self.blackborder: bool = self.data.get(Components.BLACKBORDER, False)
        self.forwarder: bool = self.data.get(Components.FORWARDER, False)
        self.videograbber: bool = self.data.get(Components.VIDEOGRABBER, False)
        self.systemgrabber: bool = self.data.get(Components.SYSTEMGRABBER, False)
        self.leddevice: bool = self.data.get(Components.LEDDEVICE, False)

    def as_dict(self) -> dict:
        return self.__dict__["data"]
