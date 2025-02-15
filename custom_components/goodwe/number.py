"""GoodWe PV inverter numeric settings entities."""
from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
import logging

from goodwe import Inverter, InverterError

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfPower
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, KEY_DEVICE_INFO, KEY_INVERTER

_LOGGER = logging.getLogger(__name__)


@dataclass
class GoodweNumberEntityDescriptionBase:
    """Required values when describing Goodwe number entities."""

    getter: Callable[[Inverter], Awaitable[any]]
    mapper: Callable[[any], int]
    setter: Callable[[Inverter, int], Awaitable[None]]
    filter: Callable[[Inverter], bool]


@dataclass
class GoodweNumberEntityDescription(
    NumberEntityDescription, GoodweNumberEntityDescriptionBase
):
    """Class describing Goodwe number entities."""


NUMBERS = (
    # non DT inverters (limit in W)
    GoodweNumberEntityDescription(
        key="grid_export_limit",
        name="Grid export limit",
        icon="mdi:transmission-tower",
        entity_category=EntityCategory.CONFIG,
        device_class=NumberDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        native_step=100,
        native_min_value=0,
        native_max_value=10000,
        getter=lambda inv: inv.get_grid_export_limit(),
        mapper=lambda v: v,
        setter=lambda inv, val: inv.set_grid_export_limit(val),
        filter=lambda inv: type(inv).__name__ != "DT",
    ),
    # DT inverters (limit is in %)
    GoodweNumberEntityDescription(
        key="grid_export_limit",
        name="Grid export limit",
        icon="mdi:transmission-tower",
        entity_category=EntityCategory.CONFIG,
        native_unit_of_measurement=PERCENTAGE,
        native_step=1,
        native_min_value=0,
        native_max_value=100,
        getter=lambda inv: inv.get_grid_export_limit(),
        mapper=lambda v: v,
        setter=lambda inv, val: inv.set_grid_export_limit(val),
        filter=lambda inv: type(inv).__name__ == "DT",
    ),
    GoodweNumberEntityDescription(
        key="battery_discharge_depth",
        name="Depth of discharge (on-grid)",
        icon="mdi:battery-arrow-down",
        entity_category=EntityCategory.CONFIG,
        native_unit_of_measurement=PERCENTAGE,
        native_step=1,
        native_min_value=0,
        native_max_value=99,
        getter=lambda inv: inv.get_ongrid_battery_dod(),
        mapper=lambda v: v,
        setter=lambda inv, val: inv.set_ongrid_battery_dod(val),
        filter=lambda inv: True,
    ),
    GoodweNumberEntityDescription(
        key="eco_mode_power",
        name="Eco mode power",
        icon="mdi:battery-charging-low",
        entity_category=EntityCategory.CONFIG,
        native_unit_of_measurement=PERCENTAGE,
        native_step=1,
        native_min_value=0,
        native_max_value=100,
        getter=lambda inv: inv.read_setting("eco_mode_1"),
        mapper=lambda v: abs(v.power) if v else 0,
        setter=None,
        filter=lambda inv: True,
    ),
    GoodweNumberEntityDescription(
        key="eco_mode_soc",
        name="Eco mode SoC",
        icon="mdi:battery-charging-low",
        entity_category=EntityCategory.CONFIG,
        native_unit_of_measurement=PERCENTAGE,
        native_step=1,
        native_min_value=0,
        native_max_value=100,
        getter=lambda inv: inv.read_setting("eco_mode_1"),
        mapper=lambda v: v.soc if v else 0,
        setter=None,
        filter=lambda inv: True,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the inverter select entities from a config entry."""
    inverter = hass.data[DOMAIN][config_entry.entry_id][KEY_INVERTER]
    device_info = hass.data[DOMAIN][config_entry.entry_id][KEY_DEVICE_INFO]

    entities = []

    for description in filter(lambda dsc: dsc.filter(inverter), NUMBERS):
        try:
            current_value = description.mapper(await description.getter(inverter))
        except (InverterError, ValueError):
            # Inverter model does not support this setting
            _LOGGER.debug("Could not read inverter setting %s", description.key)
            continue

        entities.append(
            InverterNumberEntity(device_info, description, inverter, current_value)
        )

    async_add_entities(entities)


class InverterNumberEntity(NumberEntity):
    """Inverter numeric setting entity."""

    _attr_should_poll = False
    entity_description: GoodweNumberEntityDescription

    def __init__(
        self,
        device_info: DeviceInfo,
        description: GoodweNumberEntityDescription,
        inverter: Inverter,
        current_value: int,
    ) -> None:
        """Initialize the number inverter setting entity."""
        self.entity_description = description
        self._attr_unique_id = f"{DOMAIN}-{description.key}-{inverter.serial_number}"
        self._attr_device_info = device_info
        self._attr_native_value = float(current_value)
        self._inverter: Inverter = inverter

    async def async_set_native_value(self, value: float) -> None:
        """Set new value."""
        if self.entity_description.setter:
            await self.entity_description.setter(self._inverter, int(value))
        self._attr_native_value = value
        self.async_write_ha_state()
