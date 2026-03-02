"""Light platform for AVE dominaplus integration (dimmers)."""

import logging
from typing import Any

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ColorMode,
    LightEntity,
)
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
    """Set up AVE dominaplus light (dimmer) entities."""
    webserver: AveWebServer = entry.runtime_data
    if not webserver:
        _LOGGER.error("AVE dominaplus: Web server not initialized")
        raise ConfigEntryNotReady("Can't reach webserver")

    await webserver.set_async_add_light_entities(async_add_entities)
    await webserver.set_update_light(update_light)
    if not webserver.settings.fetch_lights:
        return
    await adopt_existing_sensors(webserver, entry)


async def adopt_existing_sensors(server: AveWebServer, entry: ConfigEntry) -> None:
    """Adopt existing light entities from the entity registry."""
    try:
        entity_registry = er.async_get(server.hass)
        if entity_registry is None:
            return
        entities = er.async_entries_for_config_entry(entity_registry, entry.entry_id)
        for entity in entities:
            if not (entity.platform == "ave_dominaplus" and entity.domain == "light"):
                continue
            if entity.unique_id not in server.lights:
                family = int(entity.unique_id.split("_")[2])
                ave_device_id = int(entity.unique_id.split("_")[3])
                name = None
                if entity.name is not None:
                    name = entity.name
                elif entity.original_name is not None:
                    name = entity.original_name

                light = AveDimmerLight(
                    unique_id=entity.unique_id,
                    family=family,
                    ave_device_id=ave_device_id,
                    device_status=None,
                    name=name,
                    webserver=server,
                )
                light.hass = server.hass
                light.entity_id = entity.entity_id

                server.lights[entity.unique_id] = light
                server.async_add_light_entities([light])
    except Exception as e:  # noqa: BLE001
        _LOGGER.error("Error adopting existing light entities: %s", str(e))


def set_light_uid(webserver: AveWebServer, family, ave_device_id):
    """Set the unique ID for the light entity."""
    return f"ave_light_{family}_{ave_device_id}"


def update_light(
    server: AveWebServer, family, ave_device_id, device_status, name=None
):
    """Update light entity based on the family and device status."""
    if family != 2:
        _LOGGER.debug(
            "Not updating light for family %s, device_id %s",
            family,
            ave_device_id,
        )
        return

    if not server.settings.fetch_lights:
        return

    _LOGGER.debug("Updating light for family %s, device_id %s, status %s", family, ave_device_id, device_status)

    unique_id = set_light_uid(server, family, ave_device_id)
    already_exists = unique_id in server.lights
    if already_exists:
        light: AveDimmerLight = server.lights[unique_id]
        if device_status is not None and device_status >= 0:
            light.update_state(device_status)
        if name is not None and server.settings.get_entity_names:
            light.set_ave_name(name)
            if not check_name_changed(server.hass, unique_id):
                light.set_name(name)
    else:
        entity_name = None
        entity_ave_name = None
        if name is not None and server.settings.get_entity_names:
            entity_name = name
            entity_ave_name = name

        light = AveDimmerLight(
            unique_id=unique_id,
            device_status=device_status,
            family=family,
            ave_device_id=ave_device_id,
            webserver=server,
            name=entity_name,
            ave_name=entity_ave_name,
        )

        _LOGGER.info("Creating new light entity %s", name)
        server.lights[unique_id] = light
        server.async_add_light_entities([light])


def check_name_changed(hass: HomeAssistant, unique_id: str) -> bool:
    """Check if the name of the entity has changed."""
    entity_registry = er.async_get(hass)

    entry_id = entity_registry.async_get_entity_id(
        "light", "ave_dominaplus", unique_id
    )
    if entry_id:
        entity_entry = entity_registry.async_get(entry_id)
        if entity_entry is not None:
            return (
                entity_entry.name is not None
                and entity_entry.original_name != entity_entry.name
            )
    return False


class AveDimmerLight(LightEntity):
    """Representation of an AVE dimmer light."""

    _attr_color_mode = ColorMode.BRIGHTNESS
    _attr_supported_color_modes = {ColorMode.BRIGHTNESS}

    def __init__(
        self,
        unique_id: str,
        family: int,
        ave_device_id: int,
        device_status: int | None,
        name=None,
        webserver: AveWebServer | None = None,
        ave_name: str | None = None,
    ) -> None:
        """Initialize the dimmer light."""
        self._unique_id = unique_id
        self.ave_device_id = ave_device_id
        self.family = family
        self._webserver = webserver
        self._ave_name = ave_name
        if self._webserver:
            self.hass = self._webserver.hass

        # AVE dimmer status: 0=off, 1-31 where 1=10%, 31=100%
        if device_status is not None and device_status >= 0:
            self._attr_is_on = device_status > 0
            if device_status > 0:
                self._attr_brightness = self._ave_to_ha_brightness(device_status)
            else:
                self._attr_brightness = 0

        if name is None:
            self._name = self.build_name()
        else:
            self._name = name

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the light on using SIL command."""
        if not self._webserver:
            return

        brightness = kwargs.get(ATTR_BRIGHTNESS)
        if brightness is not None:
            ave_brightness = self._ha_to_ave_brightness(brightness)
            await self._webserver.light_turn_on(self.ave_device_id, ave_brightness)
            self._attr_brightness = brightness
        else:
            # Restore last known brightness, or full if unknown
            if self._attr_brightness and self._attr_brightness > 0:
                ave_brightness = self._ha_to_ave_brightness(self._attr_brightness)
            else:
                ave_brightness = 31
                self._attr_brightness = 255
            await self._webserver.light_turn_on(self.ave_device_id, ave_brightness)
        self._attr_is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the light off."""
        if not self._webserver:
            return
        await self._webserver.light_turn_off(self.ave_device_id)
        self._attr_is_on = False
        self.async_write_ha_state()

    @property
    def unique_id(self) -> str:
        """Return the unique ID of the light."""
        return self._unique_id

    @property
    def name(self) -> str:
        """Return the name of the light."""
        return self._name

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes."""
        return {
            "AVE_family": self.family,
            "AVE_device_id": self.ave_device_id,
            "AVE_name": self._ave_name,
        }

    @staticmethod
    def _ave_to_ha_brightness(ave_value: int) -> int:
        """Scale AVE 1-31 to HA 1-255. AVE 1=10%, 31=100%."""
        pct = (ave_value - 1) * 90 / 30 + 10  # 10% to 100%
        return max(1, round(pct * 255 / 100))

    @staticmethod
    def _ha_to_ave_brightness(ha_brightness: int) -> int:
        """Scale HA 1-255 to AVE 1-31."""
        pct = ha_brightness * 100 / 255
        ave_value = round((pct - 10) * 30 / 90) + 1
        return max(1, min(31, ave_value))

    def update_state(self, device_status: int):
        """Update the state from AVE device status (0-31 range)."""
        if device_status is None or device_status < 0:
            return
        self._attr_is_on = device_status > 0
        if device_status > 0:
            self._attr_brightness = self._ave_to_ha_brightness(device_status)
        else:
            self._attr_brightness = 0
        self.async_write_ha_state()

    def set_name(self, name: str | None):
        """Set the name of the light."""
        if name is None:
            return
        self._name = name
        self.async_write_ha_state()

    def set_ave_name(self, name: str | None):
        """Set the AVE name of the light."""
        if name is not None:
            self._ave_name = name
            self.async_write_ha_state()

    def build_name(self) -> str:
        """Build the name of the light based on its family and device ID."""
        return f"{BRAND_PREFIX} dimmer {self.ave_device_id}"
