from __future__ import annotations


class SohEstimator:
    """Estimate SoH from observed usable energy between anchor events."""

    def __init__(self, nominal_capacity_kwh: float) -> None:
        self._nominal_capacity_kwh = max(0.1, nominal_capacity_kwh)
        self._cycle_start_discharge_kwh: float | None = None
        self._latest_soh_pct: float | None = None

    @property
    def latest_soh_pct(self) -> float | None:
        return self._latest_soh_pct

    def on_anchor_100(self, discharged_total_kwh: float | None) -> None:
        if discharged_total_kwh is not None:
            self._cycle_start_discharge_kwh = discharged_total_kwh

    def on_anchor_0(self, discharged_total_kwh: float | None) -> float | None:
        if self._cycle_start_discharge_kwh is None or discharged_total_kwh is None:
            return self._latest_soh_pct

        usable_kwh = discharged_total_kwh - self._cycle_start_discharge_kwh
        if usable_kwh <= 0:
            return self._latest_soh_pct

        soh = (usable_kwh / self._nominal_capacity_kwh) * 100.0
        self._latest_soh_pct = min(120.0, max(10.0, soh))
        self._cycle_start_discharge_kwh = None
        return self._latest_soh_pct

    def export_state(self) -> dict[str, float | None]:
        return {
            "cycle_start_discharge_kwh": self._cycle_start_discharge_kwh,
            "latest_soh_pct": self._latest_soh_pct,
        }

    def import_state(self, state: dict[str, float | None]) -> None:
        self._cycle_start_discharge_kwh = state.get("cycle_start_discharge_kwh")
        self._latest_soh_pct = state.get("latest_soh_pct")
