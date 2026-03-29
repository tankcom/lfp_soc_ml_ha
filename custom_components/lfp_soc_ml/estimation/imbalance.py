from __future__ import annotations

import bisect
from statistics import median


# ---------------------------------------------------------------------------
# Default LFP OCV curve (Open Circuit Voltage → SoC %)
# Typical LiFePO4 characteristic: very flat 3.20-3.33 V in the 20-80 % range.
# This is used as initial guess; the OcvCurve class learns the real curve online.
# ---------------------------------------------------------------------------

_DEFAULT_OCV_TABLE: list[tuple[float, float]] = [
    # (cell voltage V, SoC %)
    (2.50,   0.0),
    (2.80,   1.0),
    (3.00,   5.0),
    (3.10,  10.0),
    (3.20,  20.0),
    (3.25,  30.0),
    (3.27,  40.0),
    (3.29,  50.0),
    (3.31,  60.0),
    (3.33,  70.0),
    (3.35,  80.0),
    (3.40,  90.0),
    (3.45,  95.0),
    (3.50,  98.0),
    (3.60,  99.5),
    (3.65, 100.0),
]


class OcvCurve:
    """Online-learning piecewise-linear OCV → SoC curve.

    Starts with a default LFP table, then refines from observed (voltage, soc)
    pairs collected during rest periods (when voltage ≈ true OCV).

    The curve is stored as sorted (voltage, soc) control points. New
    observations are blended into the nearest existing control point or
    inserted if no point is close enough.
    """

    _MERGE_DIST_V = 0.015  # merge into existing point if within this distance
    _LEARNING_RATE = 0.08
    _MAX_POINTS = 40
    _MIN_OBSERVED = 5  # minimum observations before using learned curve

    def __init__(self) -> None:
        self._voltages: list[float] = [v for v, _ in _DEFAULT_OCV_TABLE]
        self._socs: list[float] = [s for _, s in _DEFAULT_OCV_TABLE]
        self._n_observed: int = 0

    @property
    def n_observed(self) -> int:
        return self._n_observed

    def voltage_to_soc(self, voltage: float) -> float:
        """Interpolate the OCV curve to get SoC % for a given cell voltage."""
        if not self._voltages:
            return 50.0

        if voltage <= self._voltages[0]:
            return self._socs[0]
        if voltage >= self._voltages[-1]:
            return self._socs[-1]

        idx = bisect.bisect_right(self._voltages, voltage) - 1
        idx = max(0, min(idx, len(self._voltages) - 2))

        v_lo, v_hi = self._voltages[idx], self._voltages[idx + 1]
        s_lo, s_hi = self._socs[idx], self._socs[idx + 1]
        dv = v_hi - v_lo
        if dv < 1e-6:
            return (s_lo + s_hi) / 2.0
        t = (voltage - v_lo) / dv
        return s_lo + t * (s_hi - s_lo)

    def observe(self, voltage: float, soc: float) -> None:
        """Feed an observed (voltage, soc) pair from a rest period."""
        soc = max(0.0, min(100.0, soc))
        self._n_observed += 1

        # Find nearest existing control point
        best_idx = -1
        best_dist = float("inf")
        for i, v in enumerate(self._voltages):
            d = abs(v - voltage)
            if d < best_dist:
                best_dist = d
                best_idx = i

        if best_dist <= self._MERGE_DIST_V and best_idx >= 0:
            # Blend into nearest point
            lr = self._LEARNING_RATE
            self._voltages[best_idx] += lr * (voltage - self._voltages[best_idx])
            self._socs[best_idx] += lr * (soc - self._socs[best_idx])
        else:
            # Insert new point
            insert_at = bisect.bisect_right(self._voltages, voltage)
            self._voltages.insert(insert_at, voltage)
            self._socs.insert(insert_at, soc)

            # Prune if too many points: remove the one with smallest
            # contribution (closest to its neighbours' linear interpolation)
            if len(self._voltages) > self._MAX_POINTS:
                self._prune_one()

        # Ensure monotonicity: SoC must be non-decreasing with voltage
        self._enforce_monotonic()

    def _prune_one(self) -> None:
        """Remove the interior control point that deviates least from its neighbours."""
        if len(self._voltages) <= 3:
            return
        best_err = float("inf")
        best_idx = 1
        for i in range(1, len(self._voltages) - 1):
            v_lo, v_hi = self._voltages[i - 1], self._voltages[i + 1]
            s_lo, s_hi = self._socs[i - 1], self._socs[i + 1]
            dv = v_hi - v_lo
            if dv < 1e-6:
                interp = (s_lo + s_hi) / 2.0
            else:
                t = (self._voltages[i] - v_lo) / dv
                interp = s_lo + t * (s_hi - s_lo)
            err = abs(self._socs[i] - interp)
            if err < best_err:
                best_err = err
                best_idx = i
        del self._voltages[best_idx]
        del self._socs[best_idx]

    def _enforce_monotonic(self) -> None:
        """Fix any SoC inversions so the curve is non-decreasing."""
        for i in range(1, len(self._socs)):
            if self._socs[i] < self._socs[i - 1]:
                self._socs[i] = self._socs[i - 1]

    def export_state(self) -> dict[str, object]:
        return {
            "voltages": self._voltages[:],
            "socs": self._socs[:],
            "n_observed": self._n_observed,
        }

    def import_state(self, state: dict[str, object]) -> None:
        voltages = state.get("voltages")
        socs = state.get("socs")
        if (
            isinstance(voltages, list)
            and isinstance(socs, list)
            and len(voltages) == len(socs)
            and len(voltages) >= 2
        ):
            self._voltages = [float(v) for v in voltages]
            self._socs = [float(s) for s in socs]
        n = state.get("n_observed")
        if isinstance(n, (int, float)):
            self._n_observed = int(n)


# ---------------------------------------------------------------------------
# Voltage spreads (kept for backward compat / diagnostic use)
# ---------------------------------------------------------------------------

def module_spreads(min_voltages: list[float], max_voltages: list[float]) -> list[float]:
    spreads: list[float] = []
    for min_v, max_v in zip(min_voltages, max_voltages, strict=False):
        spreads.append(max(0.0, max_v - min_v))
    return spreads


def imbalance_summary(spreads: list[float]) -> dict[str, float]:
    if not spreads:
        return {"max_v": 0.0, "median_v": 0.0}
    return {"max_v": max(spreads), "median_v": float(median(spreads))}


# ---------------------------------------------------------------------------
# ML-based percentage imbalance (via OCV curve)
# ---------------------------------------------------------------------------

def intra_module_imbalance_pct(
    min_voltages: list[float],
    max_voltages: list[float],
    ocv: OcvCurve,
) -> list[float]:
    """Per-module cell imbalance in SoC-%.

    For each module: soc(max_cell_v) - soc(min_cell_v).
    0 % = all cells identical, 100 % = one cell empty while another is full.
    """
    result: list[float] = []
    for min_v, max_v in zip(min_voltages, max_voltages, strict=False):
        soc_lo = ocv.voltage_to_soc(min_v)
        soc_hi = ocv.voltage_to_soc(max_v)
        result.append(min(100.0, max(0.0, soc_hi - soc_lo)))
    return result


def inter_module_imbalance_pct(
    min_voltages: list[float],
    max_voltages: list[float],
    ocv: OcvCurve,
) -> float:
    """Cross-module imbalance in SoC-%.

    Each module's representative SoC = soc((min_v + max_v) / 2).
    Returns max(module_socs) - min(module_socs).
    0 % = all modules at same SoC, 100 % = one module empty while another is full.
    """
    if len(min_voltages) < 2 or len(max_voltages) < 2:
        return 0.0
    module_socs = [
        ocv.voltage_to_soc((lo + hi) / 2.0)
        for lo, hi in zip(min_voltages, max_voltages, strict=False)
    ]
    return min(100.0, max(0.0, max(module_socs) - min(module_socs)))
