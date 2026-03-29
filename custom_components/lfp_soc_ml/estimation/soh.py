from __future__ import annotations


class SohEstimator:
    """Estimate SoH from observed usable energy between anchor events (100 % → 0 %)."""

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


class PartialCycleSohEstimator:
    """Estimate SoH from *partial* charge / discharge cycles.

    Monitors BMS SoC together with the energy-charged and energy-discharged
    counters.  Whenever a significant SoC swing (>= *min_soc_swing* %) is
    observed, the implied full battery capacity is calculated from the net
    energy transferred and the SoC delta:

        implied_capacity = net_energy_kwh / (|Δ SoC| / 100)

    Multiple observations are smoothed with an exponential moving average,
    and implausible values (< 30 % or > 130 % of nominal) are rejected.

    This method works without ever reaching 0 % or 100 %.
    """

    _EMA_ALPHA = 0.2
    _MIN_CAPACITY_RATIO = 0.30
    _MAX_CAPACITY_RATIO = 1.30

    def __init__(
        self,
        nominal_capacity_kwh: float,
        charge_efficiency: float = 0.99,
        min_soc_swing: float = 20.0,
    ) -> None:
        self._nominal_kwh = max(0.1, nominal_capacity_kwh)
        self._charge_efficiency = min(1.0, max(0.8, charge_efficiency))
        self._min_soc_swing = min_soc_swing

        # Current observation segment
        self._seg_soc: float | None = None
        self._seg_charged_kwh: float | None = None
        self._seg_discharged_kwh: float | None = None

        self._capacity_ema_kwh: float | None = None
        self._n_estimates: int = 0
        self._latest_soh_pct: float | None = None

    @property
    def latest_soh_pct(self) -> float | None:
        return self._latest_soh_pct

    @property
    def n_estimates(self) -> int:
        return self._n_estimates

    def update(
        self,
        bms_soc: float,
        charged_total_kwh: float | None,
        discharged_total_kwh: float | None,
    ) -> None:
        """Feed a new observation.  Called every coordinator tick."""
        if charged_total_kwh is None or discharged_total_kwh is None:
            return

        if self._seg_soc is None:
            self._start_segment(bms_soc, charged_total_kwh, discharged_total_kwh)
            return

        # Detect energy-counter reset (e.g. HA restart, sensor reset)
        if (
            charged_total_kwh < (self._seg_charged_kwh or 0.0)
            or discharged_total_kwh < (self._seg_discharged_kwh or 0.0)
        ):
            self._start_segment(bms_soc, charged_total_kwh, discharged_total_kwh)
            return

        delta_soc = bms_soc - self._seg_soc

        if abs(delta_soc) < self._min_soc_swing:
            return

        delta_charged = charged_total_kwh - (self._seg_charged_kwh or 0.0)
        delta_discharged = discharged_total_kwh - (self._seg_discharged_kwh or 0.0)

        # Net energy that entered (+) or left (−) the battery
        if delta_soc > 0:
            net_energy = delta_charged * self._charge_efficiency - delta_discharged
        else:
            net_energy = delta_discharged - delta_charged * self._charge_efficiency

        if net_energy <= 0:
            self._start_segment(bms_soc, charged_total_kwh, discharged_total_kwh)
            return

        implied_capacity = net_energy / (abs(delta_soc) / 100.0)

        ratio = implied_capacity / self._nominal_kwh
        if ratio < self._MIN_CAPACITY_RATIO or ratio > self._MAX_CAPACITY_RATIO:
            self._start_segment(bms_soc, charged_total_kwh, discharged_total_kwh)
            return

        if self._capacity_ema_kwh is None:
            self._capacity_ema_kwh = implied_capacity
        else:
            self._capacity_ema_kwh = (
                self._EMA_ALPHA * implied_capacity
                + (1.0 - self._EMA_ALPHA) * self._capacity_ema_kwh
            )
        self._n_estimates += 1
        self._latest_soh_pct = round(
            min(120.0, max(10.0, (self._capacity_ema_kwh / self._nominal_kwh) * 100.0)),
            3,
        )

        self._start_segment(bms_soc, charged_total_kwh, discharged_total_kwh)

    def _start_segment(self, soc: float, charged: float, discharged: float) -> None:
        self._seg_soc = soc
        self._seg_charged_kwh = charged
        self._seg_discharged_kwh = discharged

    def export_state(self) -> dict[str, float | int | None]:
        return {
            "seg_soc": self._seg_soc,
            "seg_charged_kwh": self._seg_charged_kwh,
            "seg_discharged_kwh": self._seg_discharged_kwh,
            "capacity_ema_kwh": self._capacity_ema_kwh,
            "n_estimates": self._n_estimates,
            "latest_soh_pct": self._latest_soh_pct,
        }

    def import_state(self, state: dict[str, float | int | None]) -> None:
        v = state.get("seg_soc")
        if isinstance(v, (float, int)):
            self._seg_soc = float(v)
        v = state.get("seg_charged_kwh")
        if isinstance(v, (float, int)):
            self._seg_charged_kwh = float(v)
        v = state.get("seg_discharged_kwh")
        if isinstance(v, (float, int)):
            self._seg_discharged_kwh = float(v)
        v = state.get("capacity_ema_kwh")
        if isinstance(v, (float, int)):
            self._capacity_ema_kwh = float(v)
        v = state.get("n_estimates")
        if isinstance(v, int):
            self._n_estimates = int(v)
        v = state.get("latest_soh_pct")
        if isinstance(v, (float, int)):
            self._latest_soh_pct = float(v)


# ---------------------------------------------------------------------------
# Per-module SoH tracker
# ---------------------------------------------------------------------------

class _ModuleSegment:
    """Tracks the start of a per-module observation window."""

    __slots__ = ("soc_start", "charged_start", "discharged_start")

    def __init__(self, soc_start: float, charged_start: float, discharged_start: float) -> None:
        self.soc_start = soc_start
        self.charged_start = charged_start
        self.discharged_start = discharged_start


class ModuleSohTracker:
    """Per-module SoH estimation via OCV-derived SoC swing analysis.

    All modules in a series string carry identical current.  Energy per
    module ≈ pack_energy / n_modules (valid for LFP where inter-module
    voltage differences are typically < 3 %).

    For each module an independent observation segment is maintained.
    When the OCV-derived SoC change exceeds *_MIN_SOC_SWING*, the
    implied module capacity is computed and smoothed with an EMA.

    During detected **balancing** (high SoC + significant spread + low
    power) all segments are invalidated, because the balancer diverts
    current to individual modules so they no longer share identical current.
    """

    _EMA_ALPHA = 0.15
    _MIN_SOC_SWING = 15.0
    _MIN_CAPACITY_RATIO = 0.30
    _MAX_CAPACITY_RATIO = 1.30
    _BALANCE_POWER_THRESHOLD_W = 500.0

    def __init__(
        self,
        nominal_capacity_kwh: float,
        charge_efficiency: float = 0.99,
        balance_soc_threshold: float = 98.9,
        balance_spread_threshold_v: float = 0.015,
    ) -> None:
        self._nominal_kwh = max(0.1, nominal_capacity_kwh)
        self._charge_efficiency = min(1.0, max(0.8, charge_efficiency))
        self._balance_soc_threshold = balance_soc_threshold
        self._balance_spread_threshold_v = balance_spread_threshold_v

        self._segments: dict[int, _ModuleSegment | None] = {}
        self._capacity_ema: dict[int, float] = {}
        self._soh_pct: dict[int, float] = {}
        self._n_estimates: dict[int, int] = {}

    # -- public interface ---------------------------------------------------

    def update(
        self,
        module_mid_v: list[float],
        ocv_curve: "OcvCurve",  # noqa: F821 – imported at call-site
        charged_total_kwh: float | None,
        discharged_total_kwh: float | None,
        bms_soc: float | None,
        spreads: list[float],
        charge_power: float | None,
    ) -> None:
        """Feed a new tick.  Call every coordinator update."""
        if charged_total_kwh is None or discharged_total_kwh is None:
            return
        n_modules = len(module_mid_v)
        if n_modules == 0:
            return

        if self._is_balancing(bms_soc, spreads, charge_power):
            for idx in range(n_modules):
                self._segments[idx] = None
            return

        nominal_per_module = self._nominal_kwh / n_modules

        for idx, mid_v in enumerate(module_mid_v):
            module_soc = ocv_curve.voltage_to_soc(mid_v)
            seg = self._segments.get(idx)

            if seg is None:
                self._segments[idx] = _ModuleSegment(module_soc, charged_total_kwh, discharged_total_kwh)
                continue

            # Counter-reset detection
            if charged_total_kwh < seg.charged_start or discharged_total_kwh < seg.discharged_start:
                self._segments[idx] = _ModuleSegment(module_soc, charged_total_kwh, discharged_total_kwh)
                continue

            delta_soc = module_soc - seg.soc_start
            if abs(delta_soc) < self._MIN_SOC_SWING:
                continue

            delta_charged = charged_total_kwh - seg.charged_start
            delta_discharged = discharged_total_kwh - seg.discharged_start

            if delta_soc > 0:
                net_pack = delta_charged * self._charge_efficiency - delta_discharged
            else:
                net_pack = delta_discharged - delta_charged * self._charge_efficiency

            if net_pack <= 0:
                self._segments[idx] = _ModuleSegment(module_soc, charged_total_kwh, discharged_total_kwh)
                continue

            net_module = net_pack / n_modules
            implied_capacity = net_module / (abs(delta_soc) / 100.0)

            ratio = implied_capacity / nominal_per_module
            if ratio < self._MIN_CAPACITY_RATIO or ratio > self._MAX_CAPACITY_RATIO:
                self._segments[idx] = _ModuleSegment(module_soc, charged_total_kwh, discharged_total_kwh)
                continue

            old = self._capacity_ema.get(idx)
            if old is None:
                self._capacity_ema[idx] = implied_capacity
            else:
                self._capacity_ema[idx] = self._EMA_ALPHA * implied_capacity + (1.0 - self._EMA_ALPHA) * old

            self._n_estimates[idx] = self._n_estimates.get(idx, 0) + 1
            self._soh_pct[idx] = round(
                min(120.0, max(10.0, (self._capacity_ema[idx] / nominal_per_module) * 100.0)), 2,
            )

            self._segments[idx] = _ModuleSegment(module_soc, charged_total_kwh, discharged_total_kwh)

    def get_module_soh_pct(self, n_modules: int) -> list[float | None]:
        """Return SoH % for each module, or *None* if not yet estimated."""
        return [self._soh_pct.get(i) for i in range(n_modules)]

    def get_module_capacity_kwh(self, n_modules: int) -> list[float | None]:
        """Return estimated capacity in kWh per module, or *None*."""
        return [self._capacity_ema.get(i) for i in range(n_modules)]

    def get_total_n_estimates(self) -> int:
        return sum(self._n_estimates.values())

    # -- balancing detection ------------------------------------------------

    def _is_balancing(
        self,
        bms_soc: float | None,
        spreads: list[float],
        charge_power: float | None,
    ) -> bool:
        if bms_soc is None or bms_soc < self._balance_soc_threshold:
            return False
        max_spread = max(spreads) if spreads else 0.0
        if max_spread < self._balance_spread_threshold_v:
            return False
        return abs(charge_power or 0.0) < self._BALANCE_POWER_THRESHOLD_W

    # -- persistence --------------------------------------------------------

    def export_state(self) -> dict[str, object]:
        segments: dict[str, list[float] | None] = {}
        for k, seg in self._segments.items():
            if seg is None:
                segments[str(k)] = None
            else:
                segments[str(k)] = [seg.soc_start, seg.charged_start, seg.discharged_start]
        return {
            "segments": segments,
            "capacity_ema": {str(k): v for k, v in self._capacity_ema.items()},
            "soh_pct": {str(k): v for k, v in self._soh_pct.items()},
            "n_estimates": {str(k): v for k, v in self._n_estimates.items()},
        }

    def import_state(self, state: dict[str, object]) -> None:
        raw_seg = state.get("segments")
        if isinstance(raw_seg, dict):
            self._segments.clear()
            for k, v in raw_seg.items():
                idx = int(k)
                if isinstance(v, list) and len(v) == 3:
                    self._segments[idx] = _ModuleSegment(float(v[0]), float(v[1]), float(v[2]))
                else:
                    self._segments[idx] = None

        raw_ema = state.get("capacity_ema")
        if isinstance(raw_ema, dict):
            self._capacity_ema = {int(k): float(v) for k, v in raw_ema.items() if isinstance(v, (int, float))}

        raw_soh = state.get("soh_pct")
        if isinstance(raw_soh, dict):
            self._soh_pct = {int(k): float(v) for k, v in raw_soh.items() if isinstance(v, (int, float))}

        raw_n = state.get("n_estimates")
        if isinstance(raw_n, dict):
            self._n_estimates = {int(k): int(v) for k, v in raw_n.items() if isinstance(v, (int, float))}
