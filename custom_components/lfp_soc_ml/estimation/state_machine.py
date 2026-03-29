from __future__ import annotations

from enum import Enum


class OperationMode(str, Enum):
    CHARGING = "charging"
    DISCHARGING = "discharging"
    IDLE = "idle"
    TRANSITION = "transition"


def infer_mode(
    charge_power: float | None,
    discharge_power: float | None,
    raw_power: float | None,
    voltage_trend: float,
) -> OperationMode:
    if charge_power is not None and charge_power > 20.0:
        return OperationMode.CHARGING
    if discharge_power is not None and discharge_power > 20.0:
        return OperationMode.DISCHARGING

    if raw_power is None or raw_power < 30.0:
        return OperationMode.IDLE

    if voltage_trend > 0.001:
        return OperationMode.CHARGING
    if voltage_trend < -0.001:
        return OperationMode.DISCHARGING
    return OperationMode.TRANSITION
