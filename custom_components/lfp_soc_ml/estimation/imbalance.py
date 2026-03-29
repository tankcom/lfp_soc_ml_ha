from __future__ import annotations

from statistics import median


def module_spreads(min_voltages: list[float], max_voltages: list[float]) -> list[float]:
    spreads: list[float] = []
    for min_v, max_v in zip(min_voltages, max_voltages, strict=False):
        spreads.append(max(0.0, max_v - min_v))
    return spreads


def imbalance_summary(spreads: list[float]) -> dict[str, float]:
    if not spreads:
        return {"max_v": 0.0, "median_v": 0.0}
    return {"max_v": max(spreads), "median_v": float(median(spreads))}
