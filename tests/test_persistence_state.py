from datetime import datetime, timezone

from custom_components.lfp_soc_ml.estimation.ml_residual import ResidualModel
from custom_components.lfp_soc_ml.estimation.physical_estimator import PhysicalSocEstimator


def test_residual_state_roundtrip() -> None:
    model = ResidualModel(
        learning_enabled=True,
        window_samples=10,
        min_samples=3,
        learning_rate=0.5,
        max_residual=10.0,
    )
    for _ in range(5):
        model.observe(target_soc=55.0, physical_soc=50.0)

    state = model.export_state()

    restored = ResidualModel(
        learning_enabled=True,
        window_samples=10,
        min_samples=3,
        learning_rate=0.5,
        max_residual=10.0,
    )
    restored.import_state(state)
    pred = restored.predict({})

    assert restored.history_samples == 5
    assert pred.value > 0.0


def test_physical_state_roundtrip() -> None:
    estimator = PhysicalSocEstimator(
        nominal_capacity_ah=280.0,
        nominal_capacity_kwh=10.0,
        charge_efficiency=0.99,
        balance_soc_threshold=98.9,
        balance_spread_threshold_v=0.015,
        discharge_cutoff_cell_v=2.8,
        max_soc_step_per_update=2.0,
    )

    state = {
        "soc_estimate": 67.5,
        "last_timestamp": datetime.now(timezone.utc).isoformat(),
        "last_anchor_ts": datetime.now(timezone.utc).isoformat(),
        "last_anchor_type": "full",
        "last_signed_current": -5.2,
        "voltage_history": [250.0, 249.7, 249.5],
        "soh": {"cycle_start_discharge_kwh": 100.0, "latest_soh_pct": 92.3},
    }

    estimator.import_state(state)
    exported = estimator.export_state()

    assert exported["soc_estimate"] == 67.5
    assert exported["last_anchor_type"] == "full"
    assert exported["soh"]["latest_soh_pct"] == 92.3
