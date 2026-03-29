from custom_components.lfp_soc_ml.estimation.soh import SohEstimator


def test_soh_estimator_from_anchor_cycle() -> None:
    estimator = SohEstimator(nominal_capacity_kwh=10.0)

    estimator.on_anchor_100(discharged_total_kwh=1000.0)
    soh = estimator.on_anchor_0(discharged_total_kwh=1008.0)

    assert soh == 80.0
    assert estimator.latest_soh_pct == 80.0
