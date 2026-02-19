"""Climate sensor platform for AVE dominaplus integration."""

import logging
from typing import Any

from homeassistant.components.climate import (
    DEFAULT_MAX_TEMP,
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PRECISION_TENTHS, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .ave_thermostat import AveThermostatProperties
from .const import BRAND_PREFIX
from .web_server import AveWebServer

_LOGGER = logging.getLogger(__name__)

SUPPORT_FLAGS = (
    ClimateEntityFeature.TARGET_TEMPERATURE
    # | ClimateEntityFeature.PRESET_MODE
    # | ClimateEntityFeature.TURN_OFF
    # | ClimateEntityFeature.TURN_ON
)
PRESET_SCHEDULE = "schedule"
PRESET_MANUAL = "manual"


async def async_setup_entry(
    hass: HomeAssistant | None,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up AVE dominaplus thermostats.

    Args:
        hass: Home Assistant instance.
        entry: Config entry for the integration.
        async_add_entities: Callback to add entities to Home Assistant.

    """
    webserver: AveWebServer = entry.runtime_data
    if not webserver:
        _LOGGER.error("AVE dominaplus: Web server not initialized")
        raise ConfigEntryNotReady("Can't reach webserver")

    await webserver.set_async_add_th_entities(async_add_entities)
    await webserver.set_update_thermostat(update_thermostat)
    if not webserver.settings.fetch_lights:
        return
    await adopt_existing_sensors(webserver, entry)


async def adopt_existing_sensors(server: AveWebServer, entry: ConfigEntry) -> None:
    return
    """Adopt existing sensors from the entity registry."""
    try:
        entity_registry = er.async_get(server.hass)
        if entity_registry is None:
            return
        entities = er.async_entries_for_config_entry(entity_registry, entry.entry_id)
        for entity in entities:
            if not (entity.platform == "ave_dominaplus" and entity.domain == "climate"):
                continue
            # Check if the sensor is already registered
            if entity.unique_id not in server.thermostats:
                # Create a new sensor instance
                family = int(entity.unique_id.split("_")[2])
                ave_device_id = int(entity.unique_id.split("_")[3])
                name = None
                if entity.name is not None:
                    name = entity.name
                elif entity.original_name is not None:
                    name = entity.original_name

                sensor = AveThermostat(
                    unique_id=entity.unique_id,
                    family=family,
                    ave_device_id=ave_device_id,
                    is_on=None,
                    name=name,
                )
                sensor.hass = server.hass
                sensor.entity_id = entity.entity_id

                server.switches[entity.unique_id] = sensor
                server.async_add_sw_entities([sensor])
    except Exception as e:  # noqa: BLE001
        _LOGGER.error("Error adopting existing sensors: %s", str(e))
        # raise ConfigEntryNotReady("Error adopting existing sensors") from e


def set_sensor_uid(webserver: AveWebServer, family, ave_device_id):
    """Set the unique ID for the sensor."""
    return f"ave_{webserver.mac_address}_thermostat_{family}_{ave_device_id}"  # Unique ID for the sensor


def update_thermostat(
    server: AveWebServer,
    family: int,
    ave_device_id: int,
    properties: AveThermostatProperties,
):
    """Update thermostat based on the family and device status."""

    _LOGGER.debug(" Updating thermostat device_id %s", ave_device_id)

    unique_id = set_sensor_uid(server, family, ave_device_id)
    already_exists = unique_id in server.thermostats
    if already_exists:
        # Update the existing sensor's state
        thermostat: AveThermostat = server.thermostats[unique_id]
        if properties is not None:
            thermostat.update_state(properties)
        if properties.device_name is not None and server.settings.get_entity_names:
            thermostat.set_ave_name(properties.device_name)
            if not check_name_changed(server.hass, unique_id):
                thermostat.set_name(properties.device_name)
    else:
        # Create a new thermostat entity
        entity_name = None
        if properties.device_name is not None and server.settings.get_entity_names:
            entity_name = properties.device_name

        thermostat = AveThermostat(
            unique_id=unique_id,
            family=family,
            ave_properties=properties,
            webserver=server,
            name=entity_name,
        )

        _LOGGER.info("Creating new thermostat entity %s", entity_name)
        server.thermostats[unique_id] = thermostat
        server.async_add_th_entities(
            [thermostat]
        )  # Add the new sensor to Home Assistant


def check_name_changed(hass: HomeAssistant, unique_id: str) -> bool:
    """Check if the name of the sensor has changed."""
    entity_registry = er.async_get(hass)

    entry_id = entity_registry.async_get_entity_id(
        "climate", "ave_dominaplus", unique_id
    )
    if entry_id:
        entity_entry = entity_registry.async_get(entry_id)
        if entity_entry is not None:
            return (
                entity_entry.name is not None
                and entity_entry.original_name != entity_entry.name
            )
    return False


class AveThermostat(ClimateEntity):
    """Representation of a thermostat controller."""

    _attr_hvac_mode = HVACMode.AUTO
    _attr_max_temp = DEFAULT_MAX_TEMP
    _attr_preset_modes = [PRESET_MANUAL, PRESET_SCHEDULE]

    _attr_supported_features = SUPPORT_FLAGS
    _attr_target_temperature_step = PRECISION_TENTHS
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_translation_key = "thermostat"
    _attr_name = None
    _away: bool | None = None
    _connected: bool | None = None

    def __init__(
        self,
        unique_id: str,
        family: int,
        ave_properties: AveThermostatProperties,
        webserver: AveWebServer | None = None,
        name: str | None = None,
    ) -> None:
        """Initialize the thermostat sensor."""
        self._unique_id = unique_id
        self._attr_unique_id = unique_id
        self.family = family
        self._webserver = webserver
        self.hass = self._webserver.hass
        self.ave_properties: AveThermostatProperties = ave_properties

        if name is not None:
            self._name = name
        elif ave_properties.device_name is None:
            self._name = self.build_name()
        else:
            self._name = ave_properties.device_name

        self._attr_capability_attributes = {
            "supported_features": [ClimateEntityFeature.TARGET_TEMPERATURE]
        }

        self._selected_schedule = None
        self._attr_hvac_modes = [HVACMode.AUTO, HVACMode.HEAT]
        self.update_all_properties(ave_properties, first_update=True)

    def update_from_wts(self, parameters: list[str], records: list[list[str]]):
        """Update the thermostat properties from WTS data."""
        ave_properties = AveThermostatProperties.from_wts(parameters, records)
        self.update_all_properties(ave_properties)

    def update_all_properties(
        self, properties: AveThermostatProperties, first_update: bool = False
    ):
        """Update all properties of the thermostat."""
        self.ave_properties = properties
        self._attr_current_temperature = self.ave_properties.temperature
        self._attr_target_temperature = self.ave_properties.set_point

        if self.ave_properties.mode in {"1F", "1"}:
            self._attr_preset_mode = PRESET_MANUAL
        else:
            self._attr_preset_mode = PRESET_SCHEDULE

        if not first_update:
            self.async_write_ha_state()

    async def async_toggle(self, **kwargs: Any) -> None:
        """Toggle the switch."""
        if self._webserver:
            await self._webserver.switch_toggle(self.ave_device_id)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        if self._webserver:
            await self._webserver.switch_turn_on(self.ave_device_id)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        if self._webserver:
            await self._webserver.switch_turn_off(self.ave_device_id)

    @property
    def unique_id(self) -> str:
        """Return the unique ID of the sensor."""
        return self._unique_id

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return self._name

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes."""
        return {
            "AVE_family": self.family,
            "AVE_device_id": self.ave_properties.device_id,
            "AVE_name": self.ave_properties.device_name,
        }

    def update_state(self, is_on: int):
        """Update the state of the switch."""
        return
        if is_on is None:
            return
        if is_on < 0:
            return
        self._attr_is_on = bool(is_on)  # Set the state to True (on) or False (off)
        self.async_write_ha_state()

    def update_ave_properties(self, properties: AveThermostatProperties):
        """Update the AVE properties of the thermostat."""
        self.ave_properties = properties
        self.async_write_ha_state()

    def set_name(self, name: str | None):
        """Set the name of the sensor."""
        if name is None:
            return
        self._name = name
        self.async_write_ha_state()

    def set_ave_name(self, name: str | None):
        """Set the AVE name of the sensor."""
        if name is not None:
            self._ave_name = name
            self.async_write_ha_state()

    def build_name(self) -> str:
        """Build the name of the sensor based on its family and device ID."""
        suffix = "thermostat"
        return f"{BRAND_PREFIX} {suffix} {self.ave_device_id}"
