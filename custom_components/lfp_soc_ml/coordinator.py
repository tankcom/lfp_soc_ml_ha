from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_BALANCE_SOC_THRESHOLD,
    CONF_BALANCE_SPREAD_THRESHOLD_V,
    CONF_BMS_SOC_ENTITY,
    CONF_BMS_SOH_ENTITY,
    CONF_CHARGE_EFFICIENCY,
    CONF_CHARGE_POWER_ENTITY,
    CONF_CURRENT_ABS_ENTITY,
    CONF_DISCHARGE_CUTOFF_CELL_V,
    CONF_DISCHARGE_POWER_ENTITY,
    CONF_ENERGY_CHARGED_TOTAL_ENTITY,
    CONF_ENERGY_DISCHARGED_TOTAL_ENTITY,
    CONF_HISTORY_LEARNING_ENABLED,
    CONF_HISTORY_LEARNING_RATE,
    CONF_HISTORY_MAX_RESIDUAL,
    CONF_HISTORY_MIN_SAMPLES,
    CONF_HISTORY_WINDOW_SAMPLES,
    CONF_MAX_SOC_STEP_PER_UPDATE,
    CONF_MODULE_MAX_VOLTAGE_ENTITIES,
    CONF_MODULE_MIN_VOLTAGE_ENTITIES,
    CONF_NOMINAL_CAPACITY_AH,
    CONF_NOMINAL_CAPACITY_KWH,
    CONF_RAW_POWER_ENTITY,
    CONF_TEMPERATURE_ENTITY,
    CONF_TEMPERATURE_MAX_ENTITY,
    CONF_TEMPERATURE_MIN_ENTITY,
    CONF_TOTAL_VOLTAGE_ENTITY,
    CONF_UPDATE_INTERVAL_SECONDS,
    DEFAULT_BALANCE_SOC_THRESHOLD,
    DEFAULT_BALANCE_SPREAD_THRESHOLD_V,
    DEFAULT_CHARGE_EFFICIENCY,
    DEFAULT_DISCHARGE_CUTOFF_CELL_V,
    DEFAULT_HISTORY_LEARNING_ENABLED,
    DEFAULT_HISTORY_LEARNING_RATE,
    DEFAULT_HISTORY_MAX_RESIDUAL,
    DEFAULT_HISTORY_MIN_SAMPLES,
    DEFAULT_HISTORY_WINDOW_SAMPLES,
    DEFAULT_MAX_SOC_STEP_PER_UPDATE,
    DEFAULT_NOMINAL_CAPACITY_AH,
    DEFAULT_NOMINAL_CAPACITY_KWH,
    DEFAULT_UPDATE_INTERVAL_SECONDS,
    DOMAIN,
)
from .estimation.ml_residual import ResidualModel
from .estimation.physical_estimator import PhysicalSocEstimator, Snapshot


class LfpSocCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    _STORE_VERSION = 1

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry

        merged = {**entry.data, **entry.options}
        self._cfg = merged
        self._state_store = Store[dict[str, Any]](hass, self._STORE_VERSION, f"{DOMAIN}_{entry.entry_id}_state")
        self._state_loaded = False
        self._last_persist_time: datetime | None = None

        self._residual_model = ResidualModel(
            learning_enabled=bool(merged.get(CONF_HISTORY_LEARNING_ENABLED, DEFAULT_HISTORY_LEARNING_ENABLED)),
            window_samples=int(merged.get(CONF_HISTORY_WINDOW_SAMPLES, DEFAULT_HISTORY_WINDOW_SAMPLES)),
            min_samples=int(merged.get(CONF_HISTORY_MIN_SAMPLES, DEFAULT_HISTORY_MIN_SAMPLES)),
            learning_rate=float(merged.get(CONF_HISTORY_LEARNING_RATE, DEFAULT_HISTORY_LEARNING_RATE)),
            max_residual=float(merged.get(CONF_HISTORY_MAX_RESIDUAL, DEFAULT_HISTORY_MAX_RESIDUAL)),
        )
        self._physical = PhysicalSocEstimator(
            nominal_capacity_ah=float(merged.get(CONF_NOMINAL_CAPACITY_AH, DEFAULT_NOMINAL_CAPACITY_AH)),
            nominal_capacity_kwh=float(merged.get(CONF_NOMINAL_CAPACITY_KWH, DEFAULT_NOMINAL_CAPACITY_KWH)),
            charge_efficiency=float(merged.get(CONF_CHARGE_EFFICIENCY, DEFAULT_CHARGE_EFFICIENCY)),
            balance_soc_threshold=float(merged.get(CONF_BALANCE_SOC_THRESHOLD, DEFAULT_BALANCE_SOC_THRESHOLD)),
            balance_spread_threshold_v=float(
                merged.get(CONF_BALANCE_SPREAD_THRESHOLD_V, DEFAULT_BALANCE_SPREAD_THRESHOLD_V)
            ),
            discharge_cutoff_cell_v=float(merged.get(CONF_DISCHARGE_CUTOFF_CELL_V, DEFAULT_DISCHARGE_CUTOFF_CELL_V)),
            max_soc_step_per_update=float(
                merged.get(CONF_MAX_SOC_STEP_PER_UPDATE, DEFAULT_MAX_SOC_STEP_PER_UPDATE)
            ),
        )

        update_interval = timedelta(seconds=int(merged.get(CONF_UPDATE_INTERVAL_SECONDS, DEFAULT_UPDATE_INTERVAL_SECONDS)))

        super().__init__(
            hass,
            logger=__import__("logging").getLogger(__name__),
            name=f"{DOMAIN}_{entry.entry_id}",
            update_interval=update_interval,
        )

    async def _async_update_data(self) -> dict[str, Any]:
        if not self._state_loaded:
            await self._async_restore_state()

        snapshot = self._build_snapshot()
        if snapshot is None:
            raise UpdateFailed("Missing required entities for snapshot")

        physical = self._physical.estimate(snapshot)
        self._residual_model.observe(
            target_soc=snapshot.bms_soc,
            physical_soc=float(physical["soc_physical"]),
        )
        residual = self._residual_model.predict(self._feature_map(snapshot, physical))

        soc_physical = float(physical["soc_physical"])
        soc_final = min(100.0, max(0.0, soc_physical + residual.value))
        fused_conf = min(1.0, max(0.0, 0.7 * float(physical["confidence"]) + 0.3 * residual.confidence))

        await self._async_periodic_persist()

        return {
            "soc": round(soc_final, 3),
            "soc_physical": soc_physical,
            "soh": physical.get("soh_estimated"),
            "mode": physical.get("mode"),
            "confidence": round(fused_conf, 3),
            "last_anchor_type": physical.get("last_anchor_type"),
            "last_anchor_age_min": physical.get("last_anchor_age_min"),
            "signed_current_a": physical.get("signed_current_a"),
            "model_version": self._residual_model.model_version,
            "history_samples": self._residual_model.history_samples,
            "imbalance_spreads_v": physical.get("imbalance_spreads_v", []),
            "imbalance_max_v": physical.get("imbalance_max_v"),
            "imbalance_median_v": physical.get("imbalance_median_v"),
        }

    async def async_shutdown(self) -> None:
        await self._async_persist_state()

    async def _async_restore_state(self) -> None:
        stored = await self._state_store.async_load()
        self._state_loaded = True
        if not isinstance(stored, dict):
            return

        physical = stored.get("physical")
        if isinstance(physical, dict):
            self._physical.import_state(physical)

        residual = stored.get("residual")
        if isinstance(residual, dict):
            self._residual_model.import_state(residual)

    async def _async_periodic_persist(self) -> None:
        now = datetime.now(timezone.utc)
        if self._last_persist_time is not None and (now - self._last_persist_time).total_seconds() < 60:
            return
        await self._async_persist_state(now)

    async def _async_persist_state(self, now: datetime | None = None) -> None:
        payload: dict[str, Any] = {
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "physical": self._physical.export_state(),
            "residual": self._residual_model.export_state(),
        }
        await self._state_store.async_save(payload)
        self._last_persist_time = now or datetime.now(timezone.utc)

    def _feature_map(self, snapshot: Snapshot, physical: dict[str, Any]) -> dict[str, float]:
        return {
            "soc_physical": float(physical["soc_physical"]),
            "voltage": float(snapshot.total_voltage or 0.0),
            "current_abs": float(snapshot.current_abs or 0.0),
            "temperature": float(snapshot.temp_mid or snapshot.temp_max or snapshot.temp_min or 0.0),
            "imbalance_max": float(physical.get("imbalance_max_v") or 0.0),
        }

    def _build_snapshot(self) -> Snapshot | None:
        bms_soc = self._state_float(self._cfg.get(CONF_BMS_SOC_ENTITY, ""))
        total_voltage = self._state_float(self._cfg.get(CONF_TOTAL_VOLTAGE_ENTITY, ""))

        if bms_soc is None or total_voltage is None:
            return None

        module_min_v = self._entity_list_values(self._cfg.get(CONF_MODULE_MIN_VOLTAGE_ENTITIES, ""))
        module_max_v = self._entity_list_values(self._cfg.get(CONF_MODULE_MAX_VOLTAGE_ENTITIES, ""))

        return Snapshot(
            timestamp=datetime.now(timezone.utc),
            bms_soc=bms_soc,
            bms_soh=self._state_float(self._cfg.get(CONF_BMS_SOH_ENTITY, "")),
            total_voltage=total_voltage,
            charge_power=self._state_float(self._cfg.get(CONF_CHARGE_POWER_ENTITY, "")),
            discharge_power=self._state_float(self._cfg.get(CONF_DISCHARGE_POWER_ENTITY, "")),
            raw_power=self._state_float(self._cfg.get(CONF_RAW_POWER_ENTITY, "")),
            current_abs=self._state_float(self._cfg.get(CONF_CURRENT_ABS_ENTITY, "")),
            temp_min=self._state_float(self._cfg.get(CONF_TEMPERATURE_MIN_ENTITY, "")),
            temp_max=self._state_float(self._cfg.get(CONF_TEMPERATURE_MAX_ENTITY, "")),
            temp_mid=self._state_float(self._cfg.get(CONF_TEMPERATURE_ENTITY, "")),
            charged_total_kwh=self._state_float(self._cfg.get(CONF_ENERGY_CHARGED_TOTAL_ENTITY, "")),
            discharged_total_kwh=self._state_float(self._cfg.get(CONF_ENERGY_DISCHARGED_TOTAL_ENTITY, "")),
            module_min_v=module_min_v,
            module_max_v=module_max_v,
        )

    def _entity_list_values(self, csv_entity_ids: str) -> list[float]:
        values: list[float] = []
        for entity_id in [x.strip() for x in csv_entity_ids.split(",") if x.strip()]:
            value = self._state_float(entity_id)
            if value is not None:
                values.append(value)
        return values

    def _state_float(self, entity_id: str) -> float | None:
        if not entity_id:
            return None
        state = self.hass.states.get(entity_id)
        if state is None:
            return None
        if state.state in ("unknown", "unavailable", "none", "None", ""):
            return None
        try:
            return float(state.state)
        except (TypeError, ValueError):
            return None
