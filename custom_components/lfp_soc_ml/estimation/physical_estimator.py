from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone

from .imbalance import imbalance_summary, module_spreads
from .soh import SohEstimator
from .state_machine import OperationMode, infer_mode


@dataclass
class Snapshot:
    timestamp: datetime
    bms_soc: float | None
    bms_soh: float | None
    total_voltage: float | None
    charge_power: float | None
    discharge_power: float | None
    raw_power: float | None
    current_abs: float | None
    temp_min: float | None
    temp_max: float | None
    temp_mid: float | None
    charged_total_kwh: float | None
    discharged_total_kwh: float | None
    module_min_v: list[float]
    module_max_v: list[float]


class PhysicalSocEstimator:
    def __init__(
        self,
        nominal_capacity_ah: float,
        nominal_capacity_kwh: float,
        charge_efficiency: float,
        balance_soc_threshold: float,
        balance_spread_threshold_v: float,
        discharge_cutoff_cell_v: float,
        max_soc_step_per_update: float,
    ) -> None:
        self._capacity_ah = max(1.0, nominal_capacity_ah)
        self._charge_efficiency = min(1.0, max(0.8, charge_efficiency))
        self._balance_soc_threshold = balance_soc_threshold
        self._balance_spread_threshold_v = balance_spread_threshold_v
        self._discharge_cutoff_cell_v = discharge_cutoff_cell_v
        self._max_soc_step_per_update = max(0.2, max_soc_step_per_update)

        self._soh_estimator = SohEstimator(nominal_capacity_kwh=nominal_capacity_kwh)

        self._soc_estimate: float | None = None
        self._last_timestamp: datetime | None = None
        self._last_anchor_ts: datetime | None = None
        self._last_anchor_type: str | None = None
        self._last_signed_current: float = 0.0
        self._voltage_history: deque[float] = deque(maxlen=8)

    def estimate(self, snapshot: Snapshot) -> dict[str, float | str | list[float] | None]:
        timestamp = snapshot.timestamp.astimezone(timezone.utc)

        spreads = module_spreads(snapshot.module_min_v, snapshot.module_max_v)
        spread_summary = imbalance_summary(spreads)

        voltage_trend = 0.0
        if snapshot.total_voltage is not None:
            self._voltage_history.append(snapshot.total_voltage)
        if len(self._voltage_history) >= 2:
            voltage_trend = self._voltage_history[-1] - self._voltage_history[0]

        mode = infer_mode(
            charge_power=snapshot.charge_power,
            discharge_power=snapshot.discharge_power,
            raw_power=snapshot.raw_power,
            voltage_trend=voltage_trend,
        )

        signed_current = self._signed_current(snapshot, mode)
        self._last_signed_current = signed_current

        if self._soc_estimate is None:
            self._soc_estimate = snapshot.bms_soc if snapshot.bms_soc is not None else 50.0

        if self._last_timestamp is not None:
            dt_seconds = max(0.0, (timestamp - self._last_timestamp).total_seconds())
            self._integrate_soc(signed_current=signed_current, dt_seconds=dt_seconds)

        anchor_type = self._maybe_anchor(snapshot, spreads)
        if anchor_type == "full":
            self._soc_estimate = 100.0
            self._last_anchor_ts = timestamp
            self._last_anchor_type = "full"
            self._soh_estimator.on_anchor_100(snapshot.discharged_total_kwh)
        elif anchor_type == "empty":
            self._soc_estimate = 0.0
            self._last_anchor_ts = timestamp
            self._last_anchor_type = "empty"
            self._soh_estimator.on_anchor_0(snapshot.discharged_total_kwh)

        soh_estimated = self._soh_estimator.latest_soh_pct
        if soh_estimated is None and snapshot.bms_soh is not None:
            soh_estimated = snapshot.bms_soh

        self._last_timestamp = timestamp

        last_anchor_age_min: float | None = None
        if self._last_anchor_ts is not None:
            last_anchor_age_min = (timestamp - self._last_anchor_ts).total_seconds() / 60.0

        confidence = self._confidence(anchor_age_min=last_anchor_age_min, mode=mode, snapshot=snapshot)

        return {
            "soc_physical": round(self._soc_estimate, 3),
            "soh_estimated": None if soh_estimated is None else round(soh_estimated, 3),
            "mode": mode.value,
            "signed_current_a": round(signed_current, 3),
            "last_anchor_type": self._last_anchor_type,
            "last_anchor_age_min": None if last_anchor_age_min is None else round(last_anchor_age_min, 2),
            "imbalance_spreads_v": [round(s, 5) for s in spreads],
            "imbalance_max_v": round(spread_summary["max_v"], 5),
            "imbalance_median_v": round(spread_summary["median_v"], 5),
            "confidence": round(confidence, 3),
        }

    def _signed_current(self, snapshot: Snapshot, mode: OperationMode) -> float:
        if snapshot.current_abs is None:
            return 0.0
        if mode == OperationMode.CHARGING:
            return abs(snapshot.current_abs)
        if mode == OperationMode.DISCHARGING:
            return -abs(snapshot.current_abs)
        return 0.0

    def _integrate_soc(self, signed_current: float, dt_seconds: float) -> None:
        dt_h = dt_seconds / 3600.0
        if dt_h <= 0:
            return

        delta_soc = (signed_current * dt_h / self._capacity_ah) * 100.0
        if delta_soc > 0:
            delta_soc *= self._charge_efficiency
        else:
            delta_soc /= self._charge_efficiency

        delta_soc = max(-self._max_soc_step_per_update, min(self._max_soc_step_per_update, delta_soc))
        self._soc_estimate = min(100.0, max(0.0, (self._soc_estimate or 0.0) + delta_soc))

    def _maybe_anchor(self, snapshot: Snapshot, spreads: list[float]) -> str | None:
        min_cell_v = min(snapshot.module_min_v) if snapshot.module_min_v else None

        is_full_by_bms = snapshot.bms_soc is not None and snapshot.bms_soc >= 99.9
        is_balancing_done = (
            snapshot.bms_soc is not None
            and snapshot.bms_soc >= self._balance_soc_threshold
            and (max(spreads) if spreads else 0.0) <= self._balance_spread_threshold_v
            and (snapshot.charge_power or 0.0) < 300.0
        )
        if is_full_by_bms or is_balancing_done:
            return "full"

        is_empty_by_bms = snapshot.bms_soc is not None and snapshot.bms_soc <= 0.1
        is_empty_by_voltage = min_cell_v is not None and min_cell_v <= self._discharge_cutoff_cell_v
        if is_empty_by_bms or is_empty_by_voltage:
            return "empty"

        return None

    def _confidence(
        self,
        anchor_age_min: float | None,
        mode: OperationMode,
        snapshot: Snapshot,
    ) -> float:
        score = 0.75

        if anchor_age_min is None:
            score -= 0.2
        elif anchor_age_min > 24 * 60:
            score -= 0.2
        elif anchor_age_min > 8 * 60:
            score -= 0.1

        if snapshot.current_abs is None or snapshot.total_voltage is None:
            score -= 0.2

        if mode == OperationMode.TRANSITION:
            score -= 0.1

        return min(1.0, max(0.0, score))

    def export_state(self) -> dict[str, object]:
        return {
            "soc_estimate": self._soc_estimate,
            "last_timestamp": None if self._last_timestamp is None else self._last_timestamp.isoformat(),
            "last_anchor_ts": None if self._last_anchor_ts is None else self._last_anchor_ts.isoformat(),
            "last_anchor_type": self._last_anchor_type,
            "last_signed_current": self._last_signed_current,
            "voltage_history": list(self._voltage_history),
            "soh": self._soh_estimator.export_state(),
        }

    def import_state(self, state: dict[str, object]) -> None:
        soc = state.get("soc_estimate")
        if isinstance(soc, (float, int)):
            self._soc_estimate = float(soc)

        ts = state.get("last_timestamp")
        if isinstance(ts, str):
            try:
                self._last_timestamp = datetime.fromisoformat(ts).astimezone(timezone.utc)
            except ValueError:
                self._last_timestamp = None

        anchor_ts = state.get("last_anchor_ts")
        if isinstance(anchor_ts, str):
            try:
                self._last_anchor_ts = datetime.fromisoformat(anchor_ts).astimezone(timezone.utc)
            except ValueError:
                self._last_anchor_ts = None

        anchor_type = state.get("last_anchor_type")
        if isinstance(anchor_type, str):
            self._last_anchor_type = anchor_type

        signed_current = state.get("last_signed_current")
        if isinstance(signed_current, (float, int)):
            self._last_signed_current = float(signed_current)

        voltage_history = state.get("voltage_history")
        if isinstance(voltage_history, list):
            self._voltage_history.clear()
            for item in voltage_history[-self._voltage_history.maxlen :]:
                if isinstance(item, (float, int)):
                    self._voltage_history.append(float(item))

        soh = state.get("soh")
        if isinstance(soh, dict):
            self._soh_estimator.import_state(soh)
