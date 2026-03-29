from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfElectricCurrent, UnitOfElectricPotential
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import LfpSocCoordinator


BASE_SENSORS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="soc",
        name="Estimated SoC",
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:battery-50",
    ),
    SensorEntityDescription(
        key="soh",
        name="Estimated SoH",
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:battery-heart-variant",
    ),
    SensorEntityDescription(
        key="confidence",
        name="Estimator Confidence",
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:shield-check",
    ),
    SensorEntityDescription(
        key="signed_current_a",
        name="Signed Current",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        icon="mdi:current-dc",
    ),
    SensorEntityDescription(
        key="imbalance_max_v",
        name="Max Module Imbalance",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        icon="mdi:sine-wave",
    ),
    SensorEntityDescription(
        key="imbalance_median_v",
        name="Median Module Imbalance",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        icon="mdi:sine-wave",
    ),
    SensorEntityDescription(
        key="soc_voltage_ml",
        name="Voltage-ML SoC",
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:chart-scatter-plot",
    ),
    SensorEntityDescription(
        key="voltage_ml_confidence",
        name="Voltage-ML Confidence",
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:shield-check-outline",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: LfpSocCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities: list[SensorEntity] = [
        LfpSocSensor(coordinator=coordinator, entry=entry, description=description)
        for description in BASE_SENSORS
    ]

    initial_spreads = coordinator.data.get("imbalance_spreads_v", []) if coordinator.data else []
    for idx in range(len(initial_spreads)):
        entities.append(LfpImbalanceModuleSensor(coordinator=coordinator, entry=entry, module_index=idx))

    entities.append(LfpDiagnosticTextSensor(coordinator=coordinator, entry=entry, key="mode", name="Operation Mode"))
    entities.append(
        LfpDiagnosticTextSensor(
            coordinator=coordinator,
            entry=entry,
            key="last_anchor_type",
            name="Last Anchor Type",
        )
    )
    entities.append(
        LfpDiagnosticTextSensor(
            coordinator=coordinator,
            entry=entry,
            key="model_version",
            name="Model Version",
        )
    )

    async_add_entities(entities)


class LfpBaseCoordinatorEntity(CoordinatorEntity[LfpSocCoordinator]):
    def __init__(self, coordinator: LfpSocCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._entry = entry


class LfpSocSensor(LfpBaseCoordinatorEntity, SensorEntity):
    entity_description: SensorEntityDescription

    def __init__(
        self,
        coordinator: LfpSocCoordinator,
        entry: ConfigEntry,
        description: SensorEntityDescription,
    ) -> None:
        super().__init__(coordinator=coordinator, entry=entry)
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"

    @property
    def native_value(self) -> float | None:
        if not self.coordinator.data:
            return None
        value = self.coordinator.data.get(self.entity_description.key)
        if value is None:
            return None
        if self.entity_description.key in ("confidence", "voltage_ml_confidence"):
            return round(float(value) * 100.0, 2)
        return float(value)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        if not self.coordinator.data:
            return None
        if self.entity_description.key == "soc_voltage_ml":
            return {"n_trained": self.coordinator.data.get("voltage_ml_n_trained")}
        return {
            "operation_mode": self.coordinator.data.get("mode"),
            "last_anchor_type": self.coordinator.data.get("last_anchor_type"),
            "last_anchor_age_min": self.coordinator.data.get("last_anchor_age_min"),
        }


class LfpImbalanceModuleSensor(LfpBaseCoordinatorEntity, SensorEntity):
    def __init__(self, coordinator: LfpSocCoordinator, entry: ConfigEntry, module_index: int) -> None:
        super().__init__(coordinator=coordinator, entry=entry)
        self._module_index = module_index
        self._attr_unique_id = f"{entry.entry_id}_imbalance_module_{module_index + 1}"
        self._attr_name = f"Module {module_index + 1} Imbalance"
        self._attr_native_unit_of_measurement = UnitOfElectricPotential.VOLT
        self._attr_icon = "mdi:sine-wave"

    @property
    def native_value(self) -> float | None:
        spreads = self.coordinator.data.get("imbalance_spreads_v", []) if self.coordinator.data else []
        if self._module_index >= len(spreads):
            return None
        return float(spreads[self._module_index])


class LfpDiagnosticTextSensor(LfpBaseCoordinatorEntity, SensorEntity):
    def __init__(self, coordinator: LfpSocCoordinator, entry: ConfigEntry, key: str, name: str) -> None:
        super().__init__(coordinator=coordinator, entry=entry)
        self._key = key
        self._attr_name = name
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_icon = "mdi:information-outline"

    @property
    def native_value(self) -> str | None:
        if not self.coordinator.data:
            return None
        value = self.coordinator.data.get(self._key)
        if value is None:
            return None
        return str(value)
