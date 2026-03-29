from custom_components.lfp_soc_ml.estimation.ml_residual import ResidualModel


def test_residual_model_learns_bias_from_history() -> None:
    model = ResidualModel(
        learning_enabled=True,
        window_samples=20,
        min_samples=5,
        learning_rate=0.5,
        max_residual=10.0,
    )

    for _ in range(10):
        model.observe(target_soc=60.0, physical_soc=55.0)

    result = model.predict({"soc_physical": 55.0})

    assert result.value > 1.0
    assert result.confidence >= 0.4
    assert model.history_samples == 10


def test_residual_model_disabled_has_no_learning() -> None:
    model = ResidualModel(
        learning_enabled=False,
        window_samples=20,
        min_samples=5,
        learning_rate=0.5,
        max_residual=10.0,
    )

    for _ in range(10):
        model.observe(target_soc=60.0, physical_soc=55.0)

    result = model.predict({"soc_physical": 55.0})

    assert result.value == 0.0
    assert model.history_samples == 0
