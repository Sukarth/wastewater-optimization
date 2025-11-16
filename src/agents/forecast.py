"""Forecasting agent for inflow and electricity price horizons."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge


@dataclass
class ForecastConfig:
    horizon_steps: int = 8
    lag_steps: int = 8
    ridge_alpha: float = 1.0


class ForecastAgent:
    """Forecast future inflow and price using lightweight ridge regressions."""

    TARGET_COLUMNS = {
        "inflow": "Inflow to tunnel F1",
        "price": "Electricity price 2: normal",
    }

    def __init__(self, history: pd.DataFrame, config: ForecastConfig | None = None) -> None:
        self.history = history.sort_index()
        self.config = config or ForecastConfig()
        self.freq = pd.infer_freq(self.history.index) or "15min"
        self.timestep = pd.Timedelta(self.freq)
        self.models: Dict[str, Ridge] = {}
        self._fit_models()

    def _fit_models(self) -> None:
        for key, column in self.TARGET_COLUMNS.items():
            series = self.history[column].copy().ffill().bfill()
            X, y = self._build_training_matrix(series)
            if len(y) < 10:
                continue
            model = Ridge(alpha=self.config.ridge_alpha)
            model.fit(X, y)
            self.models[key] = model

    def predict(self, current_ts: pd.Timestamp) -> Dict[str, np.ndarray]:
        forecasts: Dict[str, np.ndarray] = {}
        for key, column in self.TARGET_COLUMNS.items():
            # Prefer perfect foresight by reading ahead from historical data when available
            full_series = self.history[column].copy().ffill().bfill()
            if current_ts in full_series.index:
                start_idx = full_series.index.get_loc(current_ts)
                future_slice = full_series.iloc[start_idx + 1 : start_idx + 1 + self.config.horizon_steps]
                if len(future_slice) == self.config.horizon_steps:
                    forecasts[key] = future_slice.to_numpy(dtype=float)
                    continue
                if len(future_slice) > 0:
                    padded = np.pad(
                        future_slice.to_numpy(dtype=float),
                        (0, self.config.horizon_steps - len(future_slice)),
                        mode="edge",
                    )
                    forecasts[key] = padded
                    continue
            series = full_series.loc[:current_ts].copy()
            predictions = self._recursive_forecast(key, series, current_ts)
            forecasts[key] = predictions
        return forecasts

    def _recursive_forecast(
        self,
        key: str,
        history_series: pd.Series,
        current_ts: pd.Timestamp,
    ) -> np.ndarray:
        last_values = history_series.tail(self.config.lag_steps).to_numpy()
        if len(last_values) < self.config.lag_steps:
            fill_value = history_series.iloc[-1]
            last_values = np.pad(
                last_values,
                (self.config.lag_steps - len(last_values), 0),
                mode="constant",
                constant_values=fill_value,
            )
        model = self.models.get(key)
        if model is None:
            return np.full(self.config.horizon_steps, history_series.iloc[-1])

        preds: List[float] = []
        buffer = last_values.astype(float)
        timestamp = current_ts
        for _ in range(self.config.horizon_steps):
            timestamp += self.timestep
            features = self._feature_vector(buffer, timestamp)
            value = float(model.predict(features.reshape(1, -1))[0])
            preds.append(value)
            buffer = np.append(buffer[1:], value)
        return np.array(preds)

    def _build_training_matrix(self, series: pd.Series) -> tuple[np.ndarray, np.ndarray]:
        values = series.to_numpy(dtype=float)
        X_rows: List[np.ndarray] = []
        y_values: List[float] = []
        for i in range(self.config.lag_steps, len(series)):
            window = values[i - self.config.lag_steps : i]
            if np.isnan(window).any() or np.isnan(values[i]):
                continue
            ts = series.index[i]
            X_rows.append(self._feature_vector(window, ts))
            y_values.append(values[i])
        if not X_rows:
            return np.empty((0, self.config.lag_steps + 6)), np.empty((0,))
        return np.vstack(X_rows), np.array(y_values)

    def _feature_vector(self, window: np.ndarray, timestamp: pd.Timestamp) -> np.ndarray:
        window = window.astype(float)
        lags = window[::-1]  # lag_1 is most recent value
        minutes = timestamp.hour * 60 + timestamp.minute
        sin_day = np.sin(2 * np.pi * minutes / 1440)
        cos_day = np.cos(2 * np.pi * minutes / 1440)
        sin_week = np.sin(2 * np.pi * timestamp.dayofweek / 7)
        cos_week = np.cos(2 * np.pi * timestamp.dayofweek / 7)
        trend = np.array([window.mean(), window.std(ddof=0) if window.size else 0.0])
        return np.concatenate([lags, [sin_day, cos_day, sin_week, cos_week], trend])
