"""Binary sensor platform for AVE dominaplus integration."""

import logging
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import BRAND_PREFIX
from .web_server import AveWebServer

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant | None,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up AVE dominaplus number entities.

    Args:
        hass: Home Assistant instance.
        entry: Config entry for the integration.
        async_add_entities: Callback to add entities to Home Assistant.

    """
    webserver: AveWebServer = entry.runtime_data
    if not webserver:
        _LOGGER.error("AVE dominaplus: Web server not initialized")
        raise ConfigEntryNotReady("Can't reach webserver")

    await webserver.set_async_add_number_entities(async_add_entities)
    await webserver.set_update_th_offset(update_th_offset)
    if not webserver.settings.fetch_thermostats:
        return
    await adopt_existing_sensors(webserver, entry)


async def adopt_existing_sensors(server: AveWebServer, entry: ConfigEntry) -> None:
    """Adopt existing sensors from the entity registry."""
    try:
        entity_registry = er.async_get(server.hass)
        if entity_registry is None:
            return
        entities = er.async_entries_for_config_entry(entity_registry, entry.entry_id)
        for entity in entities:
            if not (entity.platform == "ave_dominaplus" and entity.domain == "number"):
                continue
            # Check if the sensor is already registered
            if entity.unique_id not in server.numbers:
                # Create a new sensor instance
                family = int(entity.unique_id.split("_")[4])
                ave_device_id = int(entity.unique_id.split("_")[5])
                name = None
                if entity.name is not None:
                    name = entity.name
                elif entity.original_name is not None:
                    name = entity.original_name

                sensor = ThermostatOffset(
                    unique_id=entity.unique_id,
                    family=family,
                    ave_device_id=ave_device_id,
                    name=name,
                    webserver=server,
                    value=None,
                )
                sensor.hass = server.hass
                sensor.entity_id = entity.entity_id

                server.numbers[entity.unique_id] = sensor
                server.async_add_number_entities([sensor])
    except Exception as e:  # noqa: BLE001
        _LOGGER.error("Error adopting existing sensors: %s", str(e))
        # raise ConfigEntryNotReady("Error adopting existing sensors") from e


def set_sensor_uid(webserver: AveWebServer, family, ave_device_id):
    """Set the unique ID for the sensor."""
    if family == 4:
        return f"ave_{webserver.mac_address}_thermostat_offset_{family}_{ave_device_id}"
    return f"ave_{webserver.mac_address}_number_{family}_{ave_device_id}"


def update_th_offset(
    server: AveWebServer, family, ave_device_id, offset_value, name=None
):
    """Update switch based on the family and device status."""
    if family == 4:
        if not server.settings.fetch_thermostats:
            return
    else:
        _LOGGER.debug(
            " Not updating number entity for family %s, device_id %s",
            family,
            ave_device_id,
        )
        return

    _LOGGER.debug(
        " Updating number entity for family %s, device_id %s", family, ave_device_id
    )

    unique_id = set_sensor_uid(server, family, ave_device_id)
    already_exists = unique_id in server.numbers
    if already_exists:
        # Update the existing sensor's state
        number: ThermostatOffset = server.numbers[unique_id]
        number.update_value(offset_value)
    else:
        # Create a new switch sensor
        entity_name = None
        entity_ave_name = None
        if name is not None and server.settings.get_entity_names:
            entity_name = name
            entity_ave_name = name

        number = ThermostatOffset(
            unique_id=unique_id,
            family=family,
            ave_device_id=ave_device_id,
            webserver=server,
            name=None,
            ave_name=entity_ave_name,
            value=offset_value,
        )

        _LOGGER.info("Creating new number entity %s", name)
        server.numbers[unique_id] = number
        server.async_add_number_entities(
            [number]
        )  # Add the new sensor to Home Assistant


def check_name_changed(hass: HomeAssistant, unique_id: str) -> bool:
    """Check if the name of the sensor has changed."""
    entity_registry = er.async_get(hass)

    entry_id = entity_registry.async_get_entity_id(
        "number", "ave_dominaplus", unique_id
    )
    if entry_id:
        entity_entry = entity_registry.async_get(entry_id)
        if entity_entry is not None:
            return (
                entity_entry.name is not None
                and entity_entry.original_name != entity_entry.name
            )
    return False


class ThermostatOffset(SensorEntity):
    """Representation of a thermostat offset."""

    _attr_native_max_value = 5.0
    _attr_native_min_value = -5.0
    _attr_native_step = 0.1
    _attr_native_unit_of_measurement = "°C"

    def __init__(
        self,
        unique_id: str,
        family: int,
        ave_device_id: int,
        name=None,
        webserver: AveWebServer | None = None,
        ave_name: str | None = None,
        value: float | None = None,
    ) -> None:
        """Initialize the thermostat offset."""
        self._unique_id = unique_id
        self.ave_device_id = ave_device_id
        self.family = family
        self._ave_name = ave_name
        self._webserver = webserver
        self.hass = self._webserver.hass

        if name is None:
            if webserver.settings.get_entity_names:
                self._name = f"Thermostat offset {self._ave_name or self.ave_device_id}"
            else:
                self._name = self.build_name()
        else:
            self._name = name

        if value is not None:
            self.update_value(value, first_update=True)

    @property
    def unique_id(self) -> str:
        """Return the unique ID of the sensor."""
        return self._unique_id

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return self._name

    @property
    def device_class(self) -> SensorDeviceClass | None:
        """Return the device class of the sensor."""
        return SensorDeviceClass.TEMPERATURE_DELTA

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes."""
        return {
            "AVE_source_device_family": self.family,
            "AVE_source_device_id": self.ave_device_id,
            "AVE_source_name": self._ave_name,
        }

    def update_value(self, offset_value: float, first_update=False):
        """Update the state of the thermostat offset."""
        if offset_value is None:
            return
        self._attr_native_value = offset_value
        if not first_update:
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
            self._ave_name = name + " offset"
            self.async_write_ha_state()

    def build_name(self) -> str:
        """Build the name of the sensor based on its family and device ID."""
        suffix = "offset for thermostat"
        mac = self._webserver.mac_address if self._webserver else "unknown"
        return f"{BRAND_PREFIX} {mac} {suffix} {self._ave_name or self.ave_device_id}"
