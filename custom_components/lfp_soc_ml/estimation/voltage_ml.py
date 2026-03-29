from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone

_N_FEATURES = 10
_MIN_TRAIN_SAMPLES = 60
_CONFIDENT_TRAIN_SAMPLES = 300


@dataclass
class VoltageMLResult:
    soc: float
    confidence: float
    n_trained: int


@dataclass
class _Sample:
    ts: datetime
    v_min: float
    v_max: float
    power_kw: float  # signed: positive = charging, negative = discharging
    temp_c: float


class _OnlineLinearModel:
    """Online ridge regression with Welford running normalisation.

    The 10-feature input vector is normalised to zero mean / unit variance
    online (Welford), then updated via SGD with L2 regularisation.
    """

    def __init__(self, learning_rate: float = 0.005, l2: float = 0.001) -> None:
        self._w = [0.0] * _N_FEATURES
        self._b = 50.0  # initial bias: mid-range SoC
        self._lr = learning_rate
        self._l2 = l2
        self._n_trained: int = 0
        self._n_norm: int = 0
        self._mean = [0.0] * _N_FEATURES
        self._m2 = [0.0] * _N_FEATURES

    @property
    def n_trained(self) -> int:
        return self._n_trained

    def _update_norm(self, x: list[float]) -> None:
        self._n_norm += 1
        for i, xi in enumerate(x):
            delta = xi - self._mean[i]
            self._mean[i] += delta / self._n_norm
            self._m2[i] += delta * (xi - self._mean[i])

    def _normalize(self, x: list[float]) -> list[float]:
        if self._n_norm < 2:
            return [0.0] * len(x)
        result: list[float] = []
        for i, xi in enumerate(x):
            var = self._m2[i] / (self._n_norm - 1)
            std = math.sqrt(max(var, 1e-10))
            result.append((xi - self._mean[i]) / std)
        return result

    def predict_raw(self, x: list[float]) -> float:
        xn = self._normalize(x)
        return self._b + sum(wi * xi for wi, xi in zip(self._w, xn))

    def train(self, x: list[float], target: float) -> None:
        self._update_norm(x)
        xn = self._normalize(x)
        pred = self._b + sum(wi * xi for wi, xi in zip(self._w, xn))
        error = max(-20.0, min(20.0, target - pred))
        self._b += self._lr * error
        for i, xi in enumerate(xn):
            self._w[i] += self._lr * (error * xi - self._l2 * self._w[i])
        self._n_trained += 1

    def export_state(self) -> dict[str, object]:
        return {
            "w": self._w[:],
            "b": self._b,
            "n_trained": self._n_trained,
            "n_norm": self._n_norm,
            "mean": self._mean[:],
            "m2": self._m2[:],
        }

    def import_state(self, state: dict[str, object]) -> None:
        if isinstance(state.get("w"), list) and len(state["w"]) == _N_FEATURES:  # type: ignore[arg-type]
            self._w = [float(v) for v in state["w"]]  # type: ignore[union-attr]
        if isinstance(state.get("b"), (int, float)):
            self._b = float(state["b"])  # type: ignore[arg-type]
        if isinstance(state.get("n_trained"), int):
            self._n_trained = int(state["n_trained"])  # type: ignore[arg-type]
        if isinstance(state.get("n_norm"), int):
            self._n_norm = int(state["n_norm"])  # type: ignore[arg-type]
        if isinstance(state.get("mean"), list) and len(state["mean"]) == _N_FEATURES:  # type: ignore[arg-type]
            self._mean = [float(v) for v in state["mean"]]  # type: ignore[union-attr]
        if isinstance(state.get("m2"), list) and len(state["m2"]) == _N_FEATURES:  # type: ignore[arg-type]
            self._m2 = [float(v) for v in state["m2"]]  # type: ignore[union-attr]


class VoltageSocEstimator:
    """Voltage + power + temperature based SoC estimator using online linear regression.

    Feature vector (10 elements):
      f0  v_min_now       – current minimum cell/module voltage (V)
      f1  v_max_now       – current maximum cell/module voltage (V)
      f2  v_spread_now    – cell imbalance spread right now (V)
      f3  v_min_trend     – delta v_min over last ~60 s (V/min)
      f4  v_max_trend     – delta v_max over last ~60 s (V/min)
      f5  power_kw_now    – signed pack power right now (+charge, kW)
      f6  power_mean_kw   – mean signed power over last ~60 s (kW)
      f7  power_trend_kw  – delta power over last ~60 s (kW/min)
      f8  temperature_c   – pack temperature (°C)
      f9  is_resting      – 1.0 when |power| < 100 W for all of last 30 s

    Training signal: BMS SoC on every update + anchor events (100 % / 0 %).
    """

    def __init__(self) -> None:
        self._model = _OnlineLinearModel()
        # Keep last ~20 min of samples at a 10 s update interval
        self._buffer: deque[_Sample] = deque(maxlen=120)

    def add_sample(
        self,
        *,
        v_min: float,
        v_max: float,
        power_kw: float,
        temp_c: float,
        timestamp: datetime,
    ) -> None:
        self._buffer.append(
            _Sample(
                ts=timestamp.astimezone(timezone.utc),
                v_min=v_min,
                v_max=v_max,
                power_kw=power_kw,
                temp_c=temp_c,
            )
        )

    def observe(self, target_soc: float) -> None:
        """Train the model on a known SoC label (BMS reading or anchor event)."""
        features = self._extract_features()
        if features is None:
            return
        self._model.train(features, max(0.0, min(100.0, target_soc)))

    def predict(self) -> VoltageMLResult:
        features = self._extract_features()
        n = self._model.n_trained
        if features is None or n < _MIN_TRAIN_SAMPLES:
            return VoltageMLResult(soc=50.0, confidence=0.0, n_trained=n)

        raw = self._model.predict_raw(features)
        soc = max(0.0, min(100.0, raw))

        maturity = min(1.0, n / _CONFIDENT_TRAIN_SAMPLES)
        conf = 0.25 + 0.40 * maturity

        # Boost confidence when pack is at rest (voltage ≈ OCV → most informative for LFP)
        if features[9] > 0.5:
            conf = min(0.85, conf + 0.15)

        # Reduce confidence under high dynamic current (IR-drop distorts voltage)
        abs_power = abs(features[5])
        if abs_power > 5.0:
            conf = max(0.0, conf - 0.20)
        elif abs_power > 2.0:
            conf = max(0.0, conf - 0.10)

        return VoltageMLResult(soc=round(soc, 3), confidence=round(conf, 3), n_trained=n)

    def export_state(self) -> dict[str, object]:
        return {"model": self._model.export_state()}

    def import_state(self, state: dict[str, object]) -> None:
        model_state = state.get("model")
        if isinstance(model_state, dict):
            self._model.import_state(model_state)

    def _extract_features(self) -> list[float] | None:
        if not self._buffer:
            return None

        now_s = self._buffer[-1]
        now_ts = now_s.ts

        v_spread_now = now_s.v_max - now_s.v_min

        window = [s for s in self._buffer if (now_ts - s.ts).total_seconds() <= 65]
        if len(window) >= 2:
            oldest = window[0]
            dt = max(1.0, (now_ts - oldest.ts).total_seconds())
            v_min_trend = (now_s.v_min - oldest.v_min) / dt * 60.0
            v_max_trend = (now_s.v_max - oldest.v_max) / dt * 60.0
            power_mean_kw = sum(s.power_kw for s in window) / len(window)
            power_trend_kw = (now_s.power_kw - oldest.power_kw) / dt * 60.0
        else:
            v_min_trend = 0.0
            v_max_trend = 0.0
            power_mean_kw = now_s.power_kw
            power_trend_kw = 0.0

        recent_30s = [s for s in self._buffer if (now_ts - s.ts).total_seconds() <= 30]
        is_resting = 1.0 if recent_30s and all(abs(s.power_kw) < 0.1 for s in recent_30s) else 0.0

        return [
            now_s.v_min,      # f0
            now_s.v_max,      # f1
            v_spread_now,     # f2
            v_min_trend,      # f3
            v_max_trend,      # f4
            now_s.power_kw,   # f5
            power_mean_kw,    # f6
            power_trend_kw,   # f7
            now_s.temp_c,     # f8
            is_resting,       # f9
        ]
