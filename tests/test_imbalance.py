from custom_components.lfp_soc_ml.estimation.imbalance import imbalance_summary, module_spreads


def test_module_spreads_and_summary() -> None:
    spreads = module_spreads([3.21, 3.20, 3.22], [3.25, 3.24, 3.30])

    assert spreads == [0.04, 0.04, 0.08]

    summary = imbalance_summary(spreads)
    assert summary["max_v"] == 0.08
    assert summary["median_v"] == 0.04
