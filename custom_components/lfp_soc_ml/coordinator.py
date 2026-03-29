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
from .estimation.voltage_ml import VoltageSocEstimator


class LfpSocCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    _STORE_VERSION = 1
    _POWER_EMA_ALPHA = 0.25
    _MIN_ESTIMATION_POWER_KW = 0.05

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry

        merged = {**entry.data, **entry.options}
        self._cfg = merged
        self._state_store = Store[dict[str, Any]](hass, self._STORE_VERSION, f"{DOMAIN}_{entry.entry_id}_state")
        self._state_loaded = False
        self._last_persist_time: datetime | None = None
        self._power_ema_kw: float | None = None

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

        self._voltage_ml = VoltageSocEstimator()

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
        soc_coulomb = min(100.0, max(0.0, soc_physical + residual.value))
        fused_conf = min(1.0, max(0.0, 0.7 * float(physical["confidence"]) + 0.3 * residual.confidence))

        # --- Voltage ML estimator ---
        if snapshot.module_min_v and snapshot.module_max_v:
            vml_v_min = min(snapshot.module_min_v)
            vml_v_max = max(snapshot.module_max_v)
        elif snapshot.total_voltage is not None:
            vml_v_min = vml_v_max = snapshot.total_voltage
        else:
            vml_v_min = vml_v_max = 0.0

        # raw_power is always positive; sign via known mode
        vml_mode = physical.get("mode", "idle")
        if snapshot.charge_power is not None or snapshot.discharge_power is not None:
            vml_power_kw = ((snapshot.charge_power or 0.0) - (snapshot.discharge_power or 0.0)) / 1000.0
        elif snapshot.raw_power is not None:
            if vml_mode == "charging":
                vml_power_kw = snapshot.raw_power / 1000.0
            elif vml_mode == "discharging":
                vml_power_kw = -snapshot.raw_power / 1000.0
            else:
                vml_power_kw = 0.0
        else:
            vml_power_kw = 0.0

        vml_temp_c = float(snapshot.temp_mid or snapshot.temp_max or snapshot.temp_min or 25.0)

        self._voltage_ml.add_sample(
            v_min=vml_v_min,
            v_max=vml_v_max,
            power_kw=vml_power_kw,
            temp_c=vml_temp_c,
            timestamp=snapshot.timestamp,
        )
        if snapshot.bms_soc is not None:
            self._voltage_ml.observe(snapshot.bms_soc)

        # Reinforce with anchor labels when anchor just fired (age < 30 s)
        anchor_type = physical.get("last_anchor_type")
        anchor_age = physical.get("last_anchor_age_min")
        if isinstance(anchor_age, float) and anchor_age < 0.5:
            if anchor_type == "full":
                self._voltage_ml.observe(100.0)
            elif anchor_type == "empty":
                self._voltage_ml.observe(0.0)

        vml = self._voltage_ml.predict()

        # Blend Coulomb counting + voltage ML
        if vml.confidence >= 0.30:
            w_phys = float(physical["confidence"])
            w_vml = vml.confidence * 0.6
            total_w = w_phys + w_vml
            soc_final = (
                min(100.0, max(0.0, (w_phys * soc_coulomb + w_vml * vml.soc) / total_w))
                if total_w > 0
                else soc_coulomb
            )
            fused_conf = min(1.0, fused_conf + 0.03)
        else:
            soc_final = soc_coulomb

        nominal_kwh = float(self._cfg.get(CONF_NOMINAL_CAPACITY_KWH, DEFAULT_NOMINAL_CAPACITY_KWH))
        soh_pct = physical.get("soh_estimated")
        soh_method = physical.get("soh_method")
        soh_factor = (float(soh_pct) / 100.0) if soh_pct is not None else 1.0
        usable_energy_kwh = round(nominal_kwh * soh_factor * soc_final / 100.0, 3)
        total_usable_capacity_kwh = nominal_kwh * soh_factor

        # Apply light smoothing so ETA sensors do not jump on short spikes.
        if self._power_ema_kw is None:
            self._power_ema_kw = vml_power_kw
        else:
            alpha = self._POWER_EMA_ALPHA
            self._power_ema_kw = alpha * vml_power_kw + (1.0 - alpha) * self._power_ema_kw

        time_to_empty_h: float | None = None
        time_to_full_h: float | None = None
        smooth_power_kw = float(self._power_ema_kw)
        if smooth_power_kw <= -self._MIN_ESTIMATION_POWER_KW:
            discharge_kw = abs(smooth_power_kw)
            time_to_empty_h = round(usable_energy_kwh / discharge_kw, 2) if discharge_kw > 0 else None
        elif smooth_power_kw >= self._MIN_ESTIMATION_POWER_KW:
            remaining_kwh = max(0.0, total_usable_capacity_kwh - usable_energy_kwh)
            time_to_full_h = round(remaining_kwh / smooth_power_kw, 2) if smooth_power_kw > 0 else None

        await self._async_periodic_persist()

        return {
            "soc": round(soc_final, 3),
            "soc_physical": soc_physical,
            "soc_voltage_ml": round(vml.soc, 3) if vml.confidence > 0.0 else None,
            "voltage_ml_confidence": round(vml.confidence, 3),
            "voltage_ml_n_trained": vml.n_trained,
            "soh": physical.get("soh_estimated"),
            "soh_method": soh_method,
            "soh_partial_n_estimates": physical.get("soh_partial_n_estimates", 0),
            "mode": physical.get("mode"),
            "confidence": round(fused_conf, 3),
            "usable_energy_kwh": usable_energy_kwh,
            "time_to_empty_h": time_to_empty_h,
            "time_to_full_h": time_to_full_h,
            "power_smoothed_kw": round(smooth_power_kw, 3),
            "last_anchor_type": physical.get("last_anchor_type"),
            "last_anchor_age_min": physical.get("last_anchor_age_min"),
            "signed_current_a": physical.get("signed_current_a"),
            "model_version": self._residual_model.model_version,
            "history_samples": self._residual_model.history_samples,
            "imbalance_spreads_v": physical.get("imbalance_spreads_v", []),
            "imbalance_max_v": physical.get("imbalance_max_v"),
            "imbalance_median_v": physical.get("imbalance_median_v"),
            "intra_module_imbalance_pct": physical.get("intra_module_imbalance_pct", []),
            "inter_module_imbalance_pct": physical.get("inter_module_imbalance_pct"),
            "module_soh_pct": physical.get("module_soh_pct", []),
            "module_capacity_kwh": physical.get("module_capacity_kwh", []),
            "module_soh_n_estimates": physical.get("module_soh_n_estimates", 0),
            "ocv_n_observed": physical.get("ocv_n_observed", 0),
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

        voltage_ml = stored.get("voltage_ml")
        if isinstance(voltage_ml, dict):
            self._voltage_ml.import_state(voltage_ml)

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
            "voltage_ml": self._voltage_ml.export_state(),
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

    def _entity_list_values(self, entity_ids: str | list[str]) -> list[float]:
        values: list[float] = []
        if isinstance(entity_ids, list):
            raw_ids = [x.strip() for x in entity_ids if isinstance(x, str) and x.strip()]
        elif isinstance(entity_ids, str):
            raw_ids = [x.strip() for x in entity_ids.split(",") if x.strip()]
        else:
            raw_ids = []

        for entity_id in raw_ids:
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
