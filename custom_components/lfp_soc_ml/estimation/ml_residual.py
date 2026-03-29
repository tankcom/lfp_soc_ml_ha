from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from statistics import mean


@dataclass
class ResidualResult:
    value: float
    confidence: float


class ResidualModel:
    """Adaptive residual model that learns correction bias from historical samples."""

    def __init__(
        self,
        *,
        learning_enabled: bool,
        window_samples: int,
        min_samples: int,
        learning_rate: float,
        max_residual: float,
    ) -> None:
        self._learning_enabled = learning_enabled
        self._window_samples = max(10, window_samples)
        self._min_samples = max(3, min_samples)
        self._learning_rate = min(1.0, max(0.001, learning_rate))
        self._max_residual = max(1.0, max_residual)
        self._history: deque[float] = deque(maxlen=self._window_samples)
        self._bias = 0.0

        self.model_version = "adaptive-history-1"

    @property
    def history_samples(self) -> int:
        return len(self._history)

    def observe(self, *, target_soc: float | None, physical_soc: float) -> None:
        if not self._learning_enabled or target_soc is None:
            return

        error = target_soc - physical_soc
        error = max(-self._max_residual, min(self._max_residual, error))
        self._history.append(error)

        if len(self._history) < self._min_samples:
            return

        history_center = mean(self._history)
        self._bias += self._learning_rate * (history_center - self._bias)

    def predict(self, features: dict[str, float]) -> ResidualResult:
        _ = features
        if not self._learning_enabled:
            return ResidualResult(value=0.0, confidence=0.35)

        if len(self._history) < self._min_samples:
            return ResidualResult(value=self._bias, confidence=0.4)

        maturity = min(1.0, len(self._history) / float(self._window_samples))
        confidence = min(0.9, 0.45 + 0.45 * maturity)
        value = max(-self._max_residual, min(self._max_residual, self._bias))
        return ResidualResult(value=value, confidence=confidence)

    def export_state(self) -> dict[str, float | list[float]]:
        return {
            "bias": self._bias,
            "history": list(self._history),
        }

    def import_state(self, state: dict[str, float | list[float]]) -> None:
        bias = state.get("bias")
        if isinstance(bias, (float, int)):
            self._bias = float(bias)

        history = state.get("history")
        if isinstance(history, list):
            self._history.clear()
            for item in history[-self._window_samples :]:
                if isinstance(item, (float, int)):
                    clipped = max(-self._max_residual, min(self._max_residual, float(item)))
                    self._history.append(clipped)
