from enum import StrEnum

import numpy as np


class SensorMode(StrEnum):
    ACCONLY = "accelerometer only"
    NDOF = "Nine degree of freedom Kalman filter"


class ActivityClassifier:
    """Lightweight activity classifier using sensor data."""

    def __init__(
        self,
        sensor_mode: SensorMode = SensorMode.NDOF,
        rest_threshold: float = 1.0,
        active_threshold: float = 3.0,
    ) -> None:
        self.sensor_mode = sensor_mode
        self.rest_threshold = rest_threshold
        self.active_threshold = active_threshold

    def classify(self, data: np.ndarray) -> dict[str, str | float]:
        """Classify activity level based on a window of acceleration samples.

        Parameters:
            data: Array-like of shape (N, 3) with acceleration samples (x, y, z)
                  in m/s^2. If a single 3-vector is provided, it will be treated
                  as a window of length 1.

        Returns:
            dict[str, str | float]: Classification result containing one of 'resting', 'active', or 'highly active'
                                      with the mean dynamic acceleration reported in ms-2 units.

        """

        arr = np.asarray(data, dtype=float)
        if arr.ndim == 1:
            if arr.size != 3:
                raise ValueError("Expected a 3-vector or an (N,3) array of samples")
            arr = arr[None, :]  # (1, 3)
        if arr.shape[1] != 3:
            raise ValueError("Input must have shape (N, 3)")

        if self.sensor_mode == SensorMode.ACCONLY:
            # Approximate gravity as the mean acceleration vector in the window (bad precision but power efficient)
            g_vec = arr.mean(axis=0)
            dynamic = arr - g_vec
        elif self.sensor_mode == SensorMode.NDOF:
            dynamic = arr
        else:
            raise ValueError(f"Unsupported sensor mode: {self.sensor_mode}")

        # Mean magnitude of dynamic acceleration (m/s^2)
        mean_acc = float(np.mean(np.linalg.norm(dynamic, axis=1)))

        if mean_acc < self.rest_threshold:
            return {"activity": "resting", "mean_acc": mean_acc}
        elif mean_acc < self.active_threshold:
            return {"activity": "active", "mean_acc": mean_acc}
        else:
            return {"activity": "highly active", "mean_acc": mean_acc}
