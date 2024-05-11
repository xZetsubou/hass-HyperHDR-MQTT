"""Constants for the HyperHDR MQTT integration."""

from enum import StrEnum
from dataclasses import dataclass
from homeassistant.const import CONF_FRIENDLY_NAME

DOMAIN = "hyperhdr_mqtt"


# Configs

CONF_TOPIC = "topic"
CONF_HOST = "host"
CONF_PORT = "port"
CONF_USERNAME = "command"
CONF_PASSWORD = "serverinfo"
CONF_BROKER = "broker"
PRIORITY = "priority"


# HyperHDR
JSON_API = "JsonAPI"
JSON_API_RESPONSE = "JsonAPI/response"
FRIENDLY_NAME = CONF_FRIENDLY_NAME


# COMMANDS
class Data(StrEnum):
    NAME = "name"
    ENABLED = "enabled"


class Components(StrEnum):
    ALL = "ALL"
    HDR = "HDR"
    SMOOTHING = "SMOOTHING"
    BLACKBORDER = "BLACKBORDER"
    FORWARDER = "FORWARDER"
    VIDEOGRABBER = "VIDEOGRABBER"
    SYSTEMGRABBER = "SYSTEMGRABBER"
    LEDDEVICE = "LEDDEVICE"


class Path(StrEnum):
    INFO = "info"
    INSTANCE = "instance"
    COMPONENTS = "components"
    RUNNING = "running"
    CURRENTINSTANCE = "currentInstance"
    EFFECTS = "effects"


class Errors(StrEnum):
    NOT_READY = "Not ready"
